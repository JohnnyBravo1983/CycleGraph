from __future__ import annotations

# -----------------------------------------------------------------------------
# Pre-flight: .env (last .env tidlig og med override)
# -----------------------------------------------------------------------------
import os
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # viktig: alltid hente oppdatert .env
except Exception:
    # Mangler python-dotenv skal ikke knekke appen; vi validerer senere
    pass

import time
import logging
import hashlib
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Callable, List

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------------------------------
# Konfig
# -----------------------------------------------------------------------------
API_HOST = os.getenv("CG_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("CG_API_PORT", "5179"))  # default 5179

app = FastAPI(title="CycleGraph API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("VITE_DEV_ORIGIN", "http://127.0.0.1:5173"),
        "http://localhost:5173",
        os.getenv("ALT_DEV_ORIGIN", "http://localhost:5173"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cyclegraph.app")

def ts_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

# -----------------------------------------------------------------------------
# Oppstartsmåling & core-import guard (for /api/health 503 ved feil)
# -----------------------------------------------------------------------------
_t0 = time.perf_counter()
_start_iso = datetime.now(timezone.utc).isoformat()

CORE_IMPORT_OK = True
CORE_IMPORT_ERROR = None
try:
    # Import-guard: sikrer at PyO3-bindingen er tilgjengelig (maturin develop)
    import cyclegraph_core  # noqa: F401
except Exception as e:
    CORE_IMPORT_OK = False
    CORE_IMPORT_ERROR = repr(e)

# Strava env-krav for token-check
REQUIRED_ENV_KEYS: List[str] = [
    "STRAVA_CLIENT_ID",
    "STRAVA_CLIENT_SECRET",
    "STRAVA_REFRESH_TOKEN",
    "STRAVA_ACCESS_TOKEN",
    "STRAVA_TOKEN_EXPIRES_AT",
]

def _missing_env(env_keys: List[str]) -> List[str]:
    missing = []
    for k in env_keys:
        v = os.getenv(k, "").strip()
        if not v:
            missing.append(k)
    return missing

# -----------------------------------------------------------------------------
# Session storage + publish helpers (beholdt)
# -----------------------------------------------------------------------------
try:
    from cyclegraph.session_storage import (
        load_session as cg_load_session,
        save_session as cg_save_session,
        set_publish_pending,
        set_publish_done,
        set_publish_failed,
    )
except Exception as e:
    raise RuntimeError(f"cyclegraph.session_storage mangler/feiler: {e}")

def load_session(session_id: str) -> Dict[str, Any]:
    return cg_load_session(session_id)

def save_session(session_id: str, data: Dict[str, Any]) -> None:
    cg_save_session(session_id, data)

_settings_cache = None
def get_settings_cached():
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    try:
        from cyclegraph.settings import get_settings
        _settings_cache = get_settings()
    except Exception:
        _settings_cache = None
    return _settings_cache

def maybe_publish_to_strava(session_id: str, token: str, enabled: bool) -> Dict[str, Any]:
    """Wrapper som alltid returnerer dict."""
    try:
        from cyclegraph.publish import maybe_publish_to_strava as impl
        out = impl(session_id, token, enabled)
        return out or {}
    except Exception as e:
        return {"ok": False, "error": f"publish exception: {e}"}

# -----------------------------------------------------------------------------
# Analyzer-resolver (Rust PyO3 eller Python) – beholdt, lett kommentert
# -----------------------------------------------------------------------------
_ANALYZER: Optional[Callable[..., Dict[str, Any]]] = None
_ANALYZER_MODE: Optional[str] = None  # "series" (watts,pulses,device_watts) eller "dict" (session)

def _resolve_analyzer():
    """Finn analyzeren og hvilken modus den krever."""
    global _ANALYZER, _ANALYZER_MODE
    if _ANALYZER is not None:
        return _ANALYZER

    # 1) Rust-modul (PyO3) med series-signatur
    try:
        import cyclegraph_core as m  # type: ignore
        cand = getattr(m, "analyze_session", None)
        if callable(cand):
            sig = inspect.signature(cand)
            params = list(sig.parameters.keys())
            if params[:2] == ["watts", "pulses"]:
                _ANALYZER = cand
                _ANALYZER_MODE = "series"
                return _ANALYZER
    except Exception:
        pass

    # 2) Python analyzer (series eller dict)
    for mod in ("cyclegraph.analyzer", "cyclegraph.analyze"):
        try:
            m = __import__(mod, fromlist=["*"])
            for cand_name in ("analyze_session", "analyze"):
                cand = getattr(m, cand_name, None)
                if callable(cand):
                    sig = inspect.signature(cand)
                    params = list(sig.parameters.keys())
                    if params[:2] == ["watts", "pulses"]:
                        _ANALYZER = cand
                        _ANALYZER_MODE = "series"
                    else:
                        _ANALYZER = cand
                        _ANALYZER_MODE = "dict"
                    return _ANALYZER
        except Exception:
            continue

    return None

# -----------------------------------------------------------------------------
# Serie/physics extractors – beholdt
# -----------------------------------------------------------------------------
def _first_nonempty(*cands):
    for c in cands:
        if isinstance(c, (list, tuple)) and len(c) > 0:
            return list(c)
    return None

def _extract_streams(session: Dict[str, Any]):
    """
    Les ut potensielle inndata. Ikke kast HTTPException her; valider i api_analyze().
    """
    s = session
    streams = s.get("streams", {}) or {}

    # Powermeter/HR
    watts = _first_nonempty(
        s.get("watts"),
        s.get("power"),
        streams.get("watts"),
        streams.get("power"),
        (s.get("data") or {}).get("streams", {}).get("watts")
            if isinstance((s.get("data") or {}).get("streams"), dict) else None,
    )
    pulses = _first_nonempty(
        s.get("pulses"),
        s.get("hr"),
        streams.get("pulses"),
        streams.get("hr"),
        (s.get("data") or {}).get("streams", {}).get("pulses")
            if isinstance((s.get("data") or {}).get("streams"), dict) else None,
    )

    # Physics mode inputs
    velocity = _first_nonempty(
        streams.get("velocity_smooth"),
        (s.get("data") or {}).get("streams", {}).get("velocity_smooth")
            if isinstance((s.get("data") or {}).get("streams"), dict) else None,
    )
    altitude = _first_nonempty(
        streams.get("altitude"),
        (s.get("data") or {}).get("streams", {}).get("altitude")
            if isinstance((s.get("data") or {}).get("streams"), dict) else None,
    )

    device_watts = s.get("device_watts")
    if device_watts is None:
        device_watts = s.get("has_power_meter") or s.get("power_meter") or False

    def _safe_cast(xs):
        if xs is None:
            return None
        try:
            return [float(x) if x is not None else 0.0 for x in xs]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Kunne ikke caste serier til float: {e}")

    return (
        _safe_cast(watts),
        _safe_cast(pulses),
        bool(device_watts),
        _safe_cast(velocity),
        _safe_cast(altitude),
    )

# -----------------------------------------------------------------------------
# Resultat-merger – beholdt
# -----------------------------------------------------------------------------
def _merge_analysis(session: Dict[str, Any], analysis: Any) -> Dict[str, Any]:
    out = dict(session)
    out["analysis_raw"] = analysis

    def pick(*keys):
        for k in keys:
            if isinstance(analysis, dict) and k in analysis:
                return analysis[k]
        return None

    pw = pick("precision_watt", "pw", "precisionWatt") or pick("avg_watt")
    if pw is not None:
        out["precision_watt"] = pw

    ci = pick("precision_watt_ci", "pw_ci", "precisionWattCI") or pick("mae")
    if ci is not None:
        out["precision_watt_ci"] = ci

    cda = pick("CdA", "cda")
    if cda is not None:
        out["CdA"] = cda

    crr = pick("crr_used", "Crr", "crr")
    if crr is not None:
        out["crr_used"] = crr

    reason = pick("reason", "explanation", "status", "mode")
    if reason is not None:
        out["reason"] = reason

    if isinstance(analysis, dict):
        if "avg" in analysis and "avg_pulse" in analysis:
            out.setdefault("avg_watt_session", analysis["avg"])
            out.setdefault("avg_hr_session", analysis["avg_pulse"])
        if "calibrated" in analysis:
            out.setdefault("calibrated", analysis["calibrated"])

    return out

# -----------------------------------------------------------------------------
# Oppstartshook (logging + metrikk)
# -----------------------------------------------------------------------------
@app.on_event("startup")
def _on_startup() -> None:
    dur = time.perf_counter() - _t0
    cid = os.getenv("STRAVA_CLIENT_ID", "<unset>")
    logger.info(f"Starting app at { _start_iso } (UTC)")
    logger.info(f"Startup: cyclegraph_core import ok = {CORE_IMPORT_OK}")
    if not CORE_IMPORT_OK:
        logger.error(f"Core import error: {CORE_IMPORT_ERROR}")
    logger.info(f"Startup duration ~ {dur:.3f}s")
    logger.info(f"STRAVA_CLIENT_ID={cid}")

# -----------------------------------------------------------------------------
# API: Health / Get / Analyze / Publish
# -----------------------------------------------------------------------------
@app.get("/api/health")
def health():
    """
    200 OK: system oppe; inkluderer startup_duration_seconds og core=ok
    503: core-import feilet (krever 'maturin develop' i riktig venv)
    """
    if not CORE_IMPORT_OK:
        raise HTTPException(status_code=503, detail={
            "ok": False,
            "reason": "core_import_failed",
            "error": CORE_IMPORT_ERROR,
        })
    dur = time.perf_counter() - _t0
    return {
        "ok": True,
        "time": int(time.time()),
        "startup_duration_seconds": round(dur, 3),
        "core": "ok",
    }

@app.get("/api/sessions/{sid}")
def api_get_session(sid: str):
    try:
        return load_session(sid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"load_session feilet: {e}")

@app.post("/api/sessions/{sid}/analyze")
def api_analyze(sid: str):
    analyzer = _resolve_analyzer()
    if analyzer is None:
        raise HTTPException(
            status_code=501,
            detail=(
                "Ingen analyzer funnet. Forventet cyclegraph_core.analyze_session(watts,pulses,device_watts) "
                "eller en Python-wrapper som eksponerer analyze_session(session)."
            ),
        )

    try:
        session = load_session(sid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"load_session feilet: {e}")

    # Hent potensielle serier
    watts, pulses, device_watts, velocity, altitude = _extract_streams(session)
    has_powermeter = bool(watts)             # serie-modus
    has_physics    = bool(velocity) and bool(altitude)  # fysikk-modus

    try:
        if _ANALYZER_MODE == "series":
            if not has_powermeter:
                # Series-analyzer krever watts/puls – gi tydelig beskjed
                raise HTTPException(
                    status_code=501,
                    detail=(
                        "Analyzer i 'series'-modus krever watts+puls (powermeter). "
                        "Du har ikke watts. Aktiver en dict-basert analyzer som støtter fysikk-modus "
                        "(analyze_session(session)) eller skaff powermeter-watts."
                    ),
                )
            analysis = analyzer(watts, pulses or [], device_watts)
        else:
            # Dict-analyzer kan støtte begge moduser. Minst én modus må være mulig.
            if not (has_powermeter or has_physics):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Mangler data: trenger enten watts+hr (powermeter) ELLER velocity_smooth(+altitude) for fysikk-beregning."
                    ),
                )
            analysis = analyzer(session)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"analyze_session feilet: {e}")

    merged = _merge_analysis(session, analysis)

    try:
        save_session(sid, merged)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"save_session feilet: {e}")

    return {
        "ok": True,
        "session_id": sid,
        "metrics": {
            "precision_watt": merged.get("precision_watt"),
            "precision_watt_ci": merged.get("precision_watt_ci"),
            "CdA": merged.get("CdA"),
            "crr_used": merged.get("crr_used"),
            "reason": merged.get("reason"),
        },
        "debug": {"analyzer_mode": _ANALYZER_MODE, "has_raw": "analysis_raw" in merged},
    }

@app.post("/api/sessions/{sid}/publish")
def api_publish(sid: str):
    try:
        sess = load_session(sid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"load_session feilet: {e}")

    # --- Toggle: ENV og session må begge være true ---
    def _env_bool(name: str):
        val = os.getenv(name)
        if val is None:
            return None
        return str(val).strip().lower() in ("1", "true", "yes", "on")

    env_toggle = _env_bool("CG_PUBLISH_TOGGLE")         # None / True / False
    session_toggle = bool(sess.get("publish_toggle", False))

    publish_enabled = (env_toggle and session_toggle) if (env_toggle is not None) else session_toggle
    if not publish_enabled:
        set_publish_failed(sess, "publish_toggle=false")
        save_session(sid, sess)
        return {"ok": False, "skipped": True, "reason": "publish_toggle=false"}

    settings = get_settings_cached()

    token = os.getenv("STRAVA_ACCESS_TOKEN") or (
        getattr(settings, "strava_access_token", None) if settings else None
    )
    if not token:
        set_publish_failed(sess, "Missing STRAVA_ACCESS_TOKEN")
        save_session(sid, sess)
        raise HTTPException(status_code=400, detail="Missing STRAVA_ACCESS_TOKEN")

    activity_id = sess.get("strava_activity_id")
    if not activity_id:
        set_publish_failed(sess, "Missing strava_activity_id")
        save_session(sid, sess)
        raise HTTPException(status_code=400, detail="Missing strava_activity_id")

    # sett pending
    set_publish_pending(sess)
    save_session(sid, sess)

    pw = sess.get("precision_watt")
    ci = sess.get("precision_watt_ci")
    cda = sess.get("CdA")
    crr = sess.get("crr_used")
    # ASCII-bindestrek → unngå 'â' i Windows-konsollen
    msg = f"Precision Watt: {pw} (CI {ci}) | CdA {cda} | Crr {crr} - posted by CycleGraph"

    # publish
    raw = maybe_publish_to_strava(str(sid), str(token), True)
    result = raw if isinstance(raw, dict) else {}
    ok = bool(result.get("ok"))
    err = result.get("error") or ("empty result from cyclegraph.publish.maybe_publish_to_strava" if not result else None)

    stamp = int(time.time())
    phash = hashlib.sha256(f"{activity_id}-{stamp}-{msg}".encode()).hexdigest()[:16]
    if ok:
        set_publish_done(sess, phash)
    else:
        set_publish_failed(sess, err or "publish failed")

    save_session(sid, sess)

    return {
        "ok": ok,
        "session_id": sid,
        "publish_state": sess.get("publish_state"),
        "publish_time": sess.get("publish_time"),
        "publish_hash": sess.get("publish_hash"),
        "message": msg,
        "publisher": {**result, "normalized": True},
    }

# -----------------------------------------------------------------------------
# Debug-endepunkter (utvidet token_present i tråd med Trinn 1-krav)
# -----------------------------------------------------------------------------
@app.get("/api/debug/publish_flags/{sid}")
def debug_flags(sid: str):
    settings = get_settings_cached()
    env = os.getenv("CG_PUBLISH_TOGGLE")
    sess = load_session(sid)
    return {
        "env.CG_PUBLISH_TOGGLE": env,
        "settings.publish_to_strava": None if settings is None else getattr(settings, "publish_to_strava", None),
        "session.publish_toggle": sess.get("publish_toggle"),
    }

@app.get("/api/debug/token_present")
def debug_token_present():
    """
    Ny kontrakt:
      - 200 og { "ok": true } hvis alle required STRAVA_* nøkler finnes
      - 500 og { ok:false, reason:'missing_env', missing:[...] } hvis noe mangler
    Beholder "has_token" for bakoverkompatibilitet (true hvis ACCESS_TOKEN er satt).
    """
    missing = _missing_env(REQUIRED_ENV_KEYS)
    has_access_token = bool(os.getenv("STRAVA_ACCESS_TOKEN"))
    if missing:
        raise HTTPException(status_code=500, detail={
            "ok": False,
            "reason": "missing_env",
            "missing": missing,
            "has_token": has_access_token,
        })
    return {"ok": True, "has_token": has_access_token}

@app.get("/api/debug/publish_probe/{sid}")
def debug_publish_probe(sid: str):
    token = os.getenv("STRAVA_ACCESS_TOKEN")
    try:
        from cyclegraph.publish import maybe_publish_to_strava as impl
    except Exception as e:
        return {"ok": False, "error": f"import publish failed: {e}", "has_token": bool(token)}
    out = impl(sid, token, True)
    return {
        "ok": True,
        "has_token": bool(token),
        "impl_return_type": type(out).__name__ if out is not None else "None",
        "impl_return": out,
    }

# -----------------------------------------------------------------------------
# Stubs (beholdt)
# -----------------------------------------------------------------------------
@app.get("/api/timeseries/stub")
def timeseries_stub():
    now = datetime.now(timezone.utc)
    days = 14
    out = []
    for i in range(days):
        d = now - timedelta(days=days - i)
        if i == 0:
            out.append({
                "id": f"stub-{i}",
                "timestamp": ts_ms(d),
                "np": 321,
                "pw": 111,
                "source": "API",
                "calibrated": True,
            })
            continue
        has_power = (i % 7 != 3)
        out.append({
            "id": f"stub-{i}",
            "timestamp": ts_ms(d),
            "np": 220 + (i % 5) * 3 if has_power else None,
            "pw": 210 + (i % 3) * 4 if has_power else None,
            "source": "API",
            "calibrated": (i % 4 != 0),
        })
    return out

@app.get("/api/sessions/summary")
def sessions_summary():
    now = datetime.now(timezone.utc)
    sessions = []
    for i in range(6):
        d = now - timedelta(days=6 - i)
        sessions.append({
            "id": f"s{i+1}",
            "timestamp": ts_ms(d),
            "np": 200 + i * 5,
            "pw": 195 + i * 5,
            "calibrated": True,
        })
    return {"sessions": sessions}

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

# -----------------------------------------------------------------------------
# Lokal kjøring
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=API_HOST, port=API_PORT, reload=True)
