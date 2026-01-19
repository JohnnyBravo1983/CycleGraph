from __future__ import annotations
# -----------------------------------------------------------------------------
# Pre-flight: .env (last .env tidlig og med override)
# -----------------------------------------------------------------------------
import os
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # viktig: alltid hente oppdatert .env
except Exception:
    pass  # dotenv er valgfritt; valideres senere

import math
import time
import logging
import hashlib
import inspect
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Callable, List, Literal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, Query, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from cyclegraph.weather_client import get_weather_for_session, WeatherError

# ✅ Importer router-objektene direkte (unngå navnekollisjon)
from server.routes.auth_local import router as local_auth_router
from server.routes.profile_router import router as profile_router
from server.routes.auth_strava import router as strava_auth_router

# Andre routers du allerede bruker videre i filen
from server.routes.sessions_list_router import router as sessions_list_router
from server.routes.strava_import_router import router as strava_import_router
from server.routes import sessions  # kun hvis du faktisk trenger denne importen

# Import for local auth middleware
from server.auth.local_auth import COOKIE_NAME as AUTH_COOKIE_NAME, verify_session as verify_auth_session

# -----------------------------------------------------------------------------
# Konfig
# -----------------------------------------------------------------------------
API_HOST = os.getenv("CG_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("CG_API_PORT", "5179"))  # default 5179

app = FastAPI(title="CycleGraph API", version="0.1.0")

# ✅ Core routers
app.include_router(local_auth_router)
app.include_router(profile_router)

# ✅ Task 2.2 Strava OAuth
app.include_router(
    strava_auth_router,
    prefix="/api/auth/strava",
    tags=["auth-strava"],
)



# ✅ PATCH: public global healthcheck (skal alltid være tilgjengelig)
@app.get("/status", include_in_schema=False)
def status():
    return {"ok": True}

# Inkluder routerne i app
app.include_router(sessions.router)
app.include_router(profile_router)
app.include_router(sessions_list_router)
app.include_router(strava_auth_router)         # OAuth (routeren har prefix internt)
app.include_router(strava_import_router)       # Sprint 2 ingest
app.include_router(local_auth_router)          # B3.2: Inkluder lokal auth router

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    os.getenv("VITE_DEV_ORIGIN", "http://localhost:5173"),
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    os.getenv("ALT_DEV_ORIGIN", "http://localhost:5173"),
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# B3.3: Middleware som setter user_id i request context
@app.middleware("http")
async def attach_user_id(request, call_next):
    request.state.user_id = None
    raw = request.cookies.get(AUTH_COOKIE_NAME)
    payload = verify_auth_session(raw or "")
    if payload:
        # user_id idiomatisk = cg_uid
        request.state.user_id = payload.get("uid")
    return await call_next(request)


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
    import cyclegraph_core  # noqa: F401
except Exception as e:
    CORE_IMPORT_OK = False
    CORE_IMPORT_ERROR = repr(e)

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
# Session storage + publish helpers
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
    try:
        from cyclegraph.publish import maybe_publish_to_strava as impl
        out = impl(session_id, token, enabled)
        return out or {}
    except Exception as e:
        return {"ok": False, "error": f"publish exception: {e}"}

# -----------------------------------------------------------------------------
# Profil-normaliserings helper
# -----------------------------------------------------------------------------

def _norm_profile(p: dict) -> dict:
    def _first(*keys, default=None):
        for k in keys:
            if k in p and p[k] is not None:
                return p[k]
        return default
    # Tillat begge konvensjoner, returner i ett konsistent format
    return {
        "CdA": float(_first("cda", "CdA", "CDA", default=0.28)),
        "Crr": float(_first("crr", "Crr", "CRR", default=0.004)),
        "weight_kg": float(_first("weight_kg", "weightKg", "WeightKg", default=78.0)),
        "device": _first("device", "Device", default="strava"),
    }

# -----------------------------------------------------------------------------
# Analyzer-resolver (Rust PyO3 eller Python) + with_profile støtte
# -----------------------------------------------------------------------------

_ANALYZER: Optional[Callable[..., Dict[str, Any]]] = None
_ANALYZER_MODE: Optional[str] = None  # "series" eller "dict"
_HAS_ANALYZE_WITH_PROFILE: bool = False
_HAS_COMPUTE_POWER_WITH_WIND: bool = False

def _resolve_analyzer():
    """Finn beste tilgjengelige analyzer."""
    global _ANALYZER, _ANALYZER_MODE, _HAS_ANALYZE_WITH_PROFILE, _HAS_COMPUTE_POWER_WITH_WIND

    if _ANALYZER is not None:
        return _ANALYZER

    # Sjekk om core har compute_power_with_wind (foretrukket)
    try:
        from cyclegraph_core import compute_power_with_wind as _cpww
        if callable(_cpww):
            _HAS_COMPUTE_POWER_WITH_WIND = True
            logger.info("Analyzer available: cyclegraph_core.compute_power_with_wind (modern)")
    except Exception:
        _HAS_COMPUTE_POWER_WITH_WIND = False

    # Sjekk om core har analyze_session_with_profile
    try:
        from cyclegraph_core import analyze_session_with_profile as _awp  # type: ignore
        if callable(_awp):
            _HAS_ANALYZE_WITH_PROFILE = True
            logger.info("Analyzer available: cyclegraph_core.analyze_session_with_profile (session+profile)")
    except Exception:
        _HAS_ANALYZE_WITH_PROFILE = False

    # Vanlig analyze_session (series / dict)
    try:
        import cyclegraph_core as m  # type: ignore
        cand = getattr(m, "analyze_session", None)
        if callable(cand):
            sig = inspect.signature(cand)
            params = list(sig.parameters.keys())
            if params[:2] == ["watts", "pulses"]:
                _ANALYZER = cand
                _ANALYZER_MODE = "series"
                logger.info("Analyzer resolved: cyclegraph_core.analyze_session (series)")
                return _ANALYZER
    except Exception as e:
        logger.warning(f"PyO3 analyzer not available: {e}")

    # Python fallback
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
                        logger.info(f"Analyzer resolved: {mod}.{cand_name} (series)")
                    else:
                        _ANALYZER = cand
                        _ANALYZER_MODE = "dict"
                        logger.info(f"Analyzer resolved: {mod}.{cand_name} (dict)")
                    return _ANALYZER
        except Exception:
            continue

    return None

# -----------------------------------------------------------------------------
# Serie/physics extractors
# -----------------------------------------------------------------------------

def _first_nonempty(*cands):
    for c in cands:
        if isinstance(c, (list, tuple)) and len(c) > 0:
            return list(c)
    return None

def _extract_streams(session: Dict[str, Any]):
    s = session
    streams = s.get("streams", {}) or {}
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
# Resultat-merger
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

    # Hvis core returnerer profil / weather_applied, ta de inn
    prof = pick("profile")
    if prof is not None:
        out["profile"] = prof

    wa = pick("weather_applied")
    if wa is not None:
        out["weather_applied"] = bool(wa)

    if isinstance(analysis, dict):
        if "avg" in analysis and "avg_pulse" in analysis:
            out.setdefault("avg_watt_session", analysis["avg"])
            out.setdefault("avg_hr_session", analysis["avg_pulse"])
        if "calibrated" in analysis:
            out.setdefault("calibrated", analysis["calibrated"])

    return out

# -----------------------------------------------------------------------------
# Request-modeller (vær-override + profil + options.force_recompute)
# -----------------------------------------------------------------------------

class ProfileIn(BaseModel):
    CdA: Optional[float] = Field(default=None, ge=0.15, le=0.6)
    Crr: Optional[float] = Field(default=None, ge=0.002, le=0.02)
    weight_kg: Optional[float] = Field(default=None, ge=35, le=150)
    device: Optional[Literal["strava", "garmin", "zwift", "unknown"]] = "strava"

class AnalyzeOptions(BaseModel):
    force_recompute: Optional[bool] = None

class AnalyzeRequest(BaseModel):
    wind_angle_deg: Optional[float] = None
    air_density_kg_per_m3: Optional[float] = None
    profile: Optional[ProfileIn] = None
    options: Optional[AnalyzeOptions] = None

# ---- Inline payload modeller (gir requestBody i OpenAPI) ----

class Sample(BaseModel):
    timestamp_ms: Optional[int] = Field(None, description="Epoch ms")
    time: Optional[str] = Field(None, description="ISO8601Z")
    lat: Optional[float] = None
    lon: Optional[float] = None
    elev: Optional[float] = None
    speed: Optional[float] = None
    hr: Optional[float] = None
    cadence: Optional[float] = None
    watts: Optional[float] = None
    temp: Optional[float] = None

class Record(BaseModel):
    timestamp_ms: int
    pw: Optional[float] = None
    np: Optional[float] = None
    source: Optional[str] = None
    calibrated: Optional[bool] = None

class Profile(BaseModel):
    CdA: Optional[float] = 0.28
    Crr: Optional[float] = 0.004
    weight_kg: Optional[float] = 78.0
    device: Optional[str] = "strava"

class InlineAnalyzeRequest(BaseModel):
    profile: Optional[Profile] = None
    samples: Optional[List[Sample]] = None
    records: Optional[List[Record]] = None

# Utvidet kombinasjonsmodell for å beholde eksisterende felt + inline
class AnalyzeRequest2(AnalyzeRequest):
    samples: Optional[List[Sample]] = None
    records: Optional[List[Record]] = None

# profilerings-metrikker (enkle tellere for observabilitet)
PROFILE_USED_TOTAL = 0
PROFILE_MISSING_TOTAL = 0

# -----------------------------------------------------------------------------
# Profil-hjelpere
# -----------------------------------------------------------------------------

DEFAULT_PROFILE: Dict[str, Any] = {"CdA": 0.30, "Crr": 0.005, "weight_kg": 80.0, "device": "unknown"}

def _merge_profile(base: Optional[Dict[str, Any]], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = dict(base or {})
    for k, v in (override or {}).items():
        if v is not None:
            out[k] = v
    return out

def _debug_power_proxy(profile: Dict[str, Any]) -> Dict[str, float]:
    """
    Enkel, profilsensitiv proxy for å sikre testbarhet i Trinn 3.
    Fjern/erstatt når ekte komponenter leveres fra core.
    """
    CdA = float(profile.get("CdA") or 0.30)
    Crr = float(profile.get("Crr") or 0.005)
    w = float(profile.get("weight_kg") or 80.0)
    total = 120.0 + CdA*520.0 + Crr*1800.0 + (w-75.0)*2.5
    drag = CdA*400.0 + 60.0
    roll = Crr*1200.0 + max(0.0, (w-75.0))*0.9
    aero_fraction = drag/total if total > 0 else None
    return {
        "total_watt": round(total, 1),
        "drag_watt": round(drag, 1),
        "rolling_watt": round(roll, 1),
        "aero_fraction": round(aero_fraction, 3) if aero_fraction is not None else None,
        "_debug_model": True,
    }

# -----------------------------------------------------------------------------
# Inline normaliserings-hjelpere
# -----------------------------------------------------------------------------

def _iso_to_ms(iso: str) -> int:
    # Robust ISO8601 → epoch ms
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)

def _records_to_samples(records: List[Record]) -> List[dict]:
    out = []
    for r in records:
        out.append({
            "timestamp_ms": r.timestamp_ms,
            "watts": r.pw,  # speed/alt/HR ukjent – kan evt. estimeres i core
        })
    return out

def _normalize_samples(samples: List[Sample]) -> List[dict]:
    out = []
    for s in samples:
        ts = s.timestamp_ms
        if ts is None and s.time:
            try:
                ts = _iso_to_ms(s.time)
            except Exception:
                pass
        item = {
            "timestamp_ms": ts,
            "lat": s.lat,
            "lon": s.lon,
            "elev": s.elev,
            "speed": s.speed,
            "hr": s.hr,
            "cadence": s.cadence,
            "watts": s.watts,
            "temp": s.temp,
        }
        out.append(item)
    return out

# -----------------------------------------------------------------------------
# Oppstartshook
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

@app.on_event("startup")
async def _debug_dump_routes():
    print("DEBUG ROUTES AT STARTUP:", file=sys.stderr)
    for r in app.routes:
        try:
            ep = getattr(r, "endpoint", None)
            mod = getattr(ep, "__module__", None)
            name = getattr(ep, "__name__", None)
            path = getattr(r, "path", None)
            methods = getattr(r, "methods", None)
            try:
                src = (inspect.getsourcefile(ep) or inspect.getfile(ep)) if ep else None
            except Exception:
                src = None
            print(f"  methods={methods} path={path} → {mod}.{name} src={src}", file=sys.stderr)
        except Exception as e:
            print(f"  route-print-error: {e}", file=sys.stderr)

# -----------------------------------------------------------------------------
# API: Health / Get / Analyze / Publish
# -----------------------------------------------------------------------------

@app.get("/api/health")
def health():
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

# -----------------------------------------------------------------------------
# PATCH 1: Endre navnet for å unngå kollisjon med sessions.py
# OBS: Denne funksjonen må IKKE kalle seg selv rekursivt
# -----------------------------------------------------------------------------

@app.post("/api/sessions/{sid}/analyze_apppy")
def api_analyze_session_apppy(
    sid: str,
    body: Optional[AnalyzeRequest2] = Body(None),
    force_recompute_q: Optional[bool] = Query(None, alias="force"),
    x_cyclegraph_force: Optional[int] = Header(None),
):
    return JSONResponse(
        status_code=410,
        content={
            "error": "deprecated_endpoint",
            "message": (
                "Dette endepunktet er avviklet. "
                "Bruk POST /api/sessions/{sid}/analyze "
                "(implementert i server/routes/sessions.py)."
            ),
            "recommended": f"/api/sessions/{sid}/analyze",
        },
    )

    """
    PATCH: Denne er NAVNENDRET til /analyze_apppy for å unngå kollisjon med sessions.py.
    Den skal IKKE kalle seg selv rekursivt.
    """
    global PROFILE_USED_TOTAL, PROFILE_MISSING_TOTAL

    print("DEBUG MARK: top of analyze handler", file=sys.stderr)
    print(f"DEBUG WHO: module={__name__} file={__file__}", file=sys.stderr)
    print(f"[HIT] api_analyze_session_apppy from app.py sid={sid}", file=sys.stderr)
    # Hent toggles
    settings = get_settings_cached()
    allow_inline = False
    use_stub = True
    if settings is not None:
        if isinstance(settings, dict):
            allow_inline = bool(settings.get("ANALYZE_ALLOW_INLINE", False))
            use_stub = bool(settings.get("USE_STUB_FALLBACK", True))
        else:
            allow_inline = bool(getattr(settings, "ANALYZE_ALLOW_INLINE", False))
            use_stub = bool(getattr(settings, "USE_STUB_FALLBACK", True))

    analyzer = _resolve_analyzer()
    if analyzer is None and not CORE_IMPORT_OK:
        raise HTTPException(
            status_code=501,
            detail=(
                "Ingen analyzer funnet. Forventet cyclegraph_core.analyze_session(watts,pulses,device_watts) "
                "eller en Python-wrapper som eksponerer analyze_session(session)."
            ),
        )

    # --- Datakildevalg: inline vs persist ------------------------------------
    inline_session: Optional[Dict[str, Any]] = None
    source = "unknown"
    norm_samples = None

    if allow_inline and body is not None and (body.samples or body.records):
        if body.samples:
            norm_samples = _normalize_samples(body.samples)
        else:
            norm_samples = _records_to_samples(body.records or [])

        watts_series = [s.get("watts") for s in norm_samples if s.get("watts") is not None]
        hr_series = [s.get("hr") for s in norm_samples if s.get("hr") is not None]
        speed_series = [s.get("speed") for s in norm_samples if s.get("speed") is not None]
        elev_series = [s.get("elev") for s in norm_samples if s.get("elev") is not None]

        inline_session = {
            "id": sid,
            "streams": {
                "watts": watts_series if watts_series else None,
                "hr": hr_series if hr_series else None,
                "velocity_smooth": speed_series if speed_series else None,
                "altitude": elev_series if elev_series else None,
            },
            "device_watts": bool(watts_series),
        }
        if body.profile:
            inline_session["profile"] = {
                "CdA": body.profile.CdA,
                "Crr": body.profile.Crr,
                "weight_kg": body.profile.weight_kg,
                "device": body.profile.device,
            }
        source = "inline"

    # --- Bestem force_recompute (må være før persisted-fastpath) ---
    force_from_body = bool(body and body.options and body.options.force_recompute)
    force = bool(force_recompute_q or force_from_body or (x_cyclegraph_force == 1))

    # --- PATCH: Prioriter full persisted result hvis ikke inline og ikke force ---
    if inline_session is None and not force:
        from pathlib import Path
        import json as _json

        def _find_repo_root() -> Path:
            """
            Finn en rotmappe som inneholder 'logs/' ved å gå oppover fra denne filen.
            Dette gjør at vi ikke er avhengig av Path.cwd().
            """
            p = Path(__file__).resolve().parent
            for _ in range(0, 8):
                if (p / "logs").exists():
                    return p
                if p.parent == p:
                    break
                p = p.parent
            # fallback: cwd hvis alt feiler
            return Path.cwd()

        def _is_full_doc(doc: Dict[str, Any]) -> bool:
            try:
                watts_ = doc.get("watts") or []
                v_rel_ = doc.get("v_rel") or []
                wind_rel_ = doc.get("wind_rel") or []
                if isinstance(watts_, list) and len(watts_) > 0:
                    return True
                if isinstance(v_rel_, list) and len(v_rel_) > 0:
                    return True
                if isinstance(wind_rel_, list) and len(wind_rel_) > 0:
                    return True
                m = doc.get("metrics") or {}
                pw = m.get("precision_watt")
                if isinstance(pw, (int, float)) and pw > 0:
                    return True
            except Exception:
                pass
            return False

        def _pick_best_path(sid_: str) -> Optional[Path]:
            root = _find_repo_root()
            logs = root / "logs"
            fn = f"result_{sid_}.json"

            p1 = logs / "actual10" / "latest" / fn
            if p1.exists():
                sz = p1.stat().st_size
                print(f"[persisted_pick] candidate1={p1} size={sz}", file=sys.stderr)
                if sz > 20_000:
                    return p1

            base = logs / "actual10"
            if base.exists():
                candidates = list(base.rglob(fn))
                if candidates:
                    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
                    print(
                        f"[persisted_pick] actual10 candidates={len(candidates)} top={candidates[0]} size={candidates[0].stat().st_size}",
                        file=sys.stderr,
                    )
                    for p in candidates:
                        if p.exists() and p.stat().st_size > 20_000:
                            return p

            p3 = logs / "results" / fn
            if p3.exists():
                print(f"[persisted_pick] fallback results={p3} size={p3.stat().st_size}", file=sys.stderr)
                return p3

            print(f"[persisted_pick] NO FILE FOUND for sid={sid_} root={root}", file=sys.stderr)
            return None

        best_path = _pick_best_path(sid)
        if best_path is not None:
            try:
                with best_path.open("r", encoding="utf-8") as f:
                    doc = _json.load(f)

                if isinstance(doc, dict) and _is_full_doc(doc):
                    dbg = doc.get("debug") or {}
                    if isinstance(dbg, dict):
                        dbg.setdefault("reason", "persisted_hit")
                        dbg.setdefault("persist_path", str(best_path))
                        dbg.setdefault("force_recompute", False)
                        doc["debug"] = dbg

                    doc.setdefault("source", "persisted")
                    print(f"[persisted_hit] sid={sid} path={best_path}", file=sys.stderr)
                    return doc
                else:
                    print(f"[persisted_skip] sid={sid} path={best_path} reason=not_full_doc", file=sys.stderr)
            except Exception as e:
                print(f"[api_analyze_session_apppy] persisted read failed sid={sid} path={best_path}: {e}", file=sys.stderr)

    # --- Last session (persist) hvis ikke inline
    if inline_session is not None:
        session = inline_session
    else:
        try:
            session = load_session(sid)
            source = "persist"
        except Exception as e:
            session = {}
            source = "none"
            logger.warning(f"load_session feilet for sid={sid}: {e}")

    persisted_before = bool(session)

    # --- Bygg brukt profil (profile_used) ---
    body_profile_dict: Dict[str, Any] = {}
    if body and body.profile:
        body_profile_dict = {
            "CdA": body.profile.CdA,
            "Crr": body.profile.Crr,
            "weight_kg": body.profile.weight_kg,
            "device": getattr(body.profile, "device", "unknown"),
        }
        PROFILE_USED_TOTAL += 1
    else:
        PROFILE_MISSING_TOTAL += 1

    if force:
        profile_used = _merge_profile(DEFAULT_PROFILE, body_profile_dict)
    else:
        base = (session.get("profile") if isinstance(session, dict) else None) or DEFAULT_PROFILE
        profile_used = _merge_profile(base, body_profile_dict)

    logger.info(
        "Profile used (pre-analyze): sid=%s CdA=%s Crr=%s weight=%s device=%s force=%s persisted_before=%s source=%s",
        sid,
        profile_used.get("CdA"),
        profile_used.get("Crr"),
        profile_used.get("weight_kg"),
        profile_used.get("device"),
        force,
        persisted_before,
        source
    )

    # --- Hent potensielle serier ---
    watts, pulses, device_watts, velocity, altitude = _extract_streams(session)
    has_powermeter = bool(watts)
    has_physics = bool(velocity) and bool(altitude)

    print(
        f"DEBUG inline counts: watts={len(watts or [])} hr={len(pulses or [])} speed={len(velocity or [])}",
        flush=True
    )

    if not (has_powermeter or has_physics):
        if use_stub:
            proxy_vals = _debug_power_proxy(profile_used)
            merged = {
                "precision_watt": proxy_vals["total_watt"],
                "CdA": profile_used.get("CdA"),
                "crr_used": profile_used.get("Crr"),
                "weather_applied": False,
                "wind_angle_deg": 0.0,
                "air_density_kg_per_m3": 0.0,
                "total_watt": proxy_vals["total_watt"],
                "drag_watt": proxy_vals["drag_watt"],
                "rolling_watt": proxy_vals["rolling_watt"],
                "aero_fraction": proxy_vals["aero_fraction"],
                "profile": dict(profile_used),
                "analysis_raw": {"reason": "stub_fallback"},
            }
            try:
                save_session(sid, merged)
            except Exception as e:
                logger.warning(f"save_session feilet i stub for sid={sid}: {e}")
            logger.info("Analyze stub fallback: sid=%s", sid)
            return {
                "ok": True,
                "session_id": sid,
                "metrics": {
                    "precision_watt": merged.get("precision_watt"),
                    "precision_watt_ci": merged.get("precision_watt_ci"),
                    "CdA": merged.get("CdA"),
                    "crr_used": merged.get("crr_used"),
                    "reason": "stub_fallback",
                    "weather_applied": merged.get("weather_applied"),
                    "wind_angle_deg": merged.get("wind_angle_deg"),
                    "air_density_kg_per_m3": merged.get("air_density_kg_per_m3"),
                    "total_watt": merged.get("total_watt"),
                    "drag_watt": merged.get("drag_watt"),
                    "rolling_watt": merged.get("rolling_watt"),
                    "aero_fraction": merged.get("aero_fraction"),
                },
                "debug": {
                    "analyzer_mode": _ANALYZER_MODE,
                    "call_path": "stub",
                    "used_override": False,
                    "has_raw": True,
                    "profile_used_total": PROFILE_USED_TOTAL,
                    "profile_missing_total": PROFILE_MISSING_TOTAL,
                    "force_recompute": force,
                },
                "profile": profile_used,
            }
        raise HTTPException(
            status_code=400,
            detail="No inline/persisted timeseries available; stub disabled by USE_STUB_FALLBACK=0",
        )

    # --- NY KODE: Direkte Rust-integrasjon for inline data ---
    call_path = "unknown"
    analysis = None

    if _HAS_COMPUTE_POWER_WITH_WIND and norm_samples:
        print(f"DEBUG FLAG: HAS_COMPUTE_POWER_WITH_WIND={_HAS_COMPUTE_POWER_WITH_WIND} inline={bool(norm_samples)}", file=sys.stderr)
        print(f"DEBUG INLINE: samples_in={len(norm_samples or [])}", file=sys.stderr)

        try:
            from cyclegraph_core import compute_power_with_wind as rust_compute_power

            profile_normalized = _norm_profile(body_profile_dict if body and body.profile else {})

            weather = {}
            if body and body.wind_angle_deg is not None:
                weather["wind_angle_deg"] = body.wind_angle_deg
            if body and body.air_density_kg_per_m3 is not None:
                weather["air_density_kg_per_m3"] = body.air_density_kg_per_m3

            print("DEBUG PATH: using compute_power_with_wind (3-args)", file=sys.stderr)

            try:
                result_json = rust_compute_power(norm_samples, profile_normalized, weather)
                call_path = "compute_power_with_wind:3-args"
            except TypeError:
                payload = {"samples": norm_samples, "profile": profile_normalized, "weather": weather}
                result_json = rust_compute_power(json.dumps(payload))
                call_path = "compute_power_with_wind:json"

            result = json.loads(result_json)

            def _avg(xs):
                return (sum(xs) / len(xs)) if xs else 0.0

            drag = result.get("drag_watt")
            roll = result.get("rolling_watt")
            prec = result.get("precision_watt")

            if drag is None and "drag_watt_series" in result:
                drag = _avg(result["drag_watt_series"])
            if roll is None and "rolling_watt_series" in result:
                roll = _avg(result["rolling_watt_series"])
            if prec is None and "precision_watt_series" in result:
                prec = _avg(result["precision_watt_series"])

            analysis = {
                "drag_watt": float(drag or 0.0),
                "rolling_watt": float(roll or 0.0),
                "precision_watt": float(prec or 0.0),
                "calibrated": False,
                "profile": json.dumps(profile_normalized),
                "reason": "ok",
            }

            dbg = result.get("debug", {})
            dbg.update({
                "analyzer_mode": "compute_power_with_wind",
                "received_inline": bool(norm_samples),
                "samples_in": len(norm_samples),
            })
            analysis["_debug"] = dbg

        except Exception as e:
            logger.warning(f"compute_power_with_wind feilet: {e}, fallback til standard analyzer")

    # --- WEATHER: body override > weather_client ---
    wind_angle_deg: Optional[float]
    air_density_kg_per_m3: Optional[float]
    used_override = False

    if body and (body.wind_angle_deg is not None or body.air_density_kg_per_m3 is not None):
        wind_angle_deg = body.wind_angle_deg
        air_density_kg_per_m3 = body.air_density_kg_per_m3
        used_override = True
        logger.info(
            "Analyze override: using weather from request body (wind_angle_deg=%s, air_density_kg_per_m3=%s)",
            wind_angle_deg, air_density_kg_per_m3
        )
    else:
        try:
            wind_angle_deg, air_density_kg_per_m3 = get_weather_for_session(session)
        except WeatherError as we:
            raise HTTPException(status_code=502, detail=f"Weather fetch/compute failed: {we}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Weather unexpected error: {e}")

    if any(
        (v is None) or (isinstance(v, float) and math.isnan(v))
        for v in (wind_angle_deg, air_density_kg_per_m3)
    ):
        raise HTTPException(status_code=422, detail="Weather values NaN/None")

    session.setdefault("weather", {})
    session["weather"]["wind_angle_deg"] = float(wind_angle_deg)  # type: ignore[arg-type]
    session["weather"]["air_density_kg_per_m3"] = float(air_density_kg_per_m3)  # type: ignore[arg-type]

    if analysis is None:
        try:
            if _HAS_ANALYZE_WITH_PROFILE:
                from cyclegraph_core import analyze_session_with_profile as analyze_with_profile  # type: ignore
                analysis = analyze_with_profile(session, profile_used)
                call_path = "core:with_profile(session+profile)"
            elif _ANALYZER_MODE == "series":
                if not has_powermeter:
                    raise HTTPException(
                        status_code=501,
                        detail=(
                            "Analyzer i 'series'-modus krever watts+puls (powermeter). "
                            "Mangler watts."
                        ),
                    )

                sig = None
                names: List[str] = []
                try:
                    sig = inspect.signature(analyzer)
                    names = list(sig.parameters.keys())
                except Exception:
                    names = []

                def _try_call(**kwargs):
                    return analyzer(**kwargs)

                if ("speed" in names or "velocity" in names) and "profile" in names:
                    try:
                        kw = {
                            "watts": watts,
                            "pulses": pulses or [],
                            "device_watts": device_watts,
                            ("speed" if "speed" in names else "velocity"): (velocity or []),
                            "profile": profile_used,
                            "wind_angle_deg": float(wind_angle_deg),
                            "air_density_kg_per_m3": float(air_density_kg_per_m3),
                        }
                        analysis = _try_call(**kw)
                        call_path = "series:kwargs-speed+profile+weather"
                    except TypeError:
                        analysis = None

                if call_path == "unknown" and ("speed" in names or "velocity" in names):
                    try:
                        kw = {
                            "watts": watts,
                            "pulses": pulses or [],
                            "device_watts": device_watts,
                            ("speed" if "speed" in names else "velocity"): (velocity or []),
                            "wind_angle_deg": float(wind_angle_deg),
                            "air_density_kg_per_m3": float(air_density_kg_per_m3),
                        }
                        analysis = _try_call(**kw)
                        call_path = "series:kwargs-speed+weather"
                    except TypeError:
                        analysis = None

                if call_path == "unknown":
                    try:
                        kw = {
                            "watts": watts,
                            "pulses": pulses or [],
                            "device_watts": device_watts,
                            "wind_angle_deg": float(wind_angle_deg),
                            "air_density_kg_per_m3": float(air_density_kg_per_m3),
                        }
                        analysis = _try_call(**kw)
                        call_path = "series:kwargs-5"
                    except TypeError:
                        analysis = None

                if call_path == "unknown":
                    try:
                        analysis = analyzer(
                            watts, pulses or [], device_watts,
                            float(wind_angle_deg), float(air_density_kg_per_m3)
                        )
                        call_path = "series:positional-5"
                    except TypeError:
                        analysis = None

                if call_path == "unknown":
                    analysis = analyzer(watts, pulses or [], device_watts)
                    call_path = "series:positional-3"
            else:
                analysis = analyzer(session)
                call_path = "dict:session"
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"analyze_session feilet: {e}")

    merged = _merge_analysis(session, analysis)

    merged["profile"] = dict(profile_used)
    merged["weather_applied"] = bool(merged.get("weather_applied", True))
    merged["wind_angle_deg"] = float(wind_angle_deg)  # type: ignore[arg-type]
    merged["air_density_kg_per_m3"] = float(air_density_kg_per_m3)  # type: ignore[arg-type]

    analysis_raw = merged.get("analysis_raw", {}) if isinstance(merged.get("analysis_raw"), dict) else {}
    has_components_in_core = all(k in analysis_raw for k in ("total_watt", "drag_watt", "rolling_watt"))

    if has_components_in_core:
        merged["total_watt"] = analysis_raw.get("total_watt")
        merged["drag_watt"] = analysis_raw.get("drag_watt")
        merged["rolling_watt"] = analysis_raw.get("rolling_watt")
        merged["aero_fraction"] = analysis_raw.get("aero_fraction")
    else:
        proxy_vals = _debug_power_proxy(profile_used)
        for k in ("total_watt", "drag_watt", "rolling_watt", "aero_fraction"):
            if force or (k not in merged):
                merged[k] = proxy_vals[k]

    try:
        save_session(sid, merged)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"save_session feilet: {e}")

    logger.info(
        "Profile used: sid=%s CdA=%.3f Crr=%.4f weight=%.1f device=%s force=%s persisted_before=%s recomputed=%s total_watt=%s source=%s",
        sid,
        float(profile_used.get("CdA") or 0.0),
        float(profile_used.get("Crr") or 0.0),
        float(profile_used.get("weight_kg") or 0.0),
        str(profile_used.get("device") or "unknown"),
        str(force),
        str(persisted_before),
        "True",
        str(merged.get("total_watt")),
        source,
    )
    logger.info(
        "Weather applied: wind_angle=%.2f°, rho=%.4f | call_path=%s | override=%s",
        float(wind_angle_deg), float(air_density_kg_per_m3), call_path, used_override
    )

    return {
        "ok": True,
        "session_id": sid,
        "metrics": {
            "precision_watt": merged.get("precision_watt"),
            "precision_watt_ci": merged.get("precision_watt_ci"),
            "CdA": merged.get("CdA") if merged.get("CdA") is not None else profile_used.get("CdA"),
            "crr_used": merged.get("crr_used") if merged.get("crr_used") is not None else profile_used.get("Crr"),
            "reason": merged.get("reason"),
            "weather_applied": merged.get("weather_applied"),
            "wind_angle_deg": merged.get("wind_angle_deg"),
            "air_density_kg_per_m3": merged.get("air_density_kg_per_m3"),
            "total_watt": merged.get("total_watt"),
            "drag_watt": merged.get("drag_watt"),
            "rolling_watt": merged.get("rolling_watt"),
            "aero_fraction": merged.get("aero_fraction"),
        },
        "debug": {
            "analyzer_mode": _ANALYZER_MODE,
            "call_path": call_path,
            "used_override": used_override,
            "has_raw": "analysis_raw" in merged,
            "profile_used_total": PROFILE_USED_TOTAL,
            "profile_missing_total": PROFILE_MISSING_TOTAL,
            "force_recompute": force,
        },
        "profile": profile_used,
    }

@app.post("/api/sessions/{sid}/publish")
def api_publish(sid: str):
    try:
        sess = load_session(sid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"load_session feilet: {e}")

    def _env_bool(name: str):
        val = os.getenv(name)
        if val is None:
            return None
        return str(val).strip().lower() in ("1", "true", "yes", "on")

    env_toggle = _env_bool("CG_PUBLISH_TOGGLE")
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
    msg = f"Precision Watt: {pw} (CI {ci}) | CdA {cda} | Crr {crr} - posted by CycleGraph"

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
# Debug-endepunkter
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
# Stubs
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
