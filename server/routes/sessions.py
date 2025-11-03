# server/routes/sessions.py
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, Query

# Primær import med trygg fallback (brukes i standardstien)
try:
    from cli.rust_bindings import rs_power_json  # ✅ primær
except Exception:
    try:
        from cyclegraph.cli.rust_bindings import rs_power_json  # ✅ pakket namespace fallback
    except Exception as e_imp:
        rs_power_json = None  # type: ignore
        _adapter_import_error = e_imp

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

G = 9.80665
RHO_DEFAULT = 1.225  # enkel fallback-rho


# ----------------- HELPERE (kontrakt + nominelle metrics) -----------------
def _ensure_contract_shape(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sett sikre defaults og garanter kontrakt — kun setdefault,
    ikke endre eksisterende tallverdier.
    """
    resp = dict(resp or {})

    # toppnivå defaults (ikke overskriv hvis Rust har satt disse)
    resp.setdefault("source", resp.get("source") or "fallback_py")
    resp.setdefault("weather_applied", False)
    resp.setdefault("profile_used", {})  # speiles ofte fra metrics.profile_used

    # metrics: bare default-nøkler, ingen beregning
    m = resp.setdefault("metrics", {})
    m.setdefault("precision_watt", 0.0)
    m.setdefault("drag_watt", 0.0)
    m.setdefault("rolling_watt", 0.0)
    # total_watt defaulter til precision_watt dersom mangler
    m.setdefault("total_watt", m.get("precision_watt", 0.0))
    m.setdefault("profile_used", {})
    # speil weather_applied inn i metrics kun hvis mangler
    m.setdefault("weather_applied", bool(resp.get("weather_applied", False)))

    # speil metrics.profile_used til toppnivå om det finnes (ikke tvang)
    if "profile_used" in m and isinstance(m["profile_used"], dict) and not resp.get("profile_used"):
        resp["profile_used"] = m["profile_used"]

    # debug-defaults (uten å overskrive eksisterende)
    dbg = resp.setdefault("debug", {})
    dbg.setdefault("reason", "ok")
    dbg.setdefault("force_recompute", False)
    dbg.setdefault("persist_ignored", False)
    dbg.setdefault("ignored_persist", False)

    return resp


def _nominal_metrics(profile: dict) -> dict:
    # (ikke brukt til beregning i kontrakt; beholdt for ev. tester)
    G_loc = 9.80665
    RHO = 1.225
    v = 6.0
    w = float(profile.get("weight_kg") or profile.get("weightKg") or 78.0)
    cda = float(profile.get("CdA", profile.get("cda", 0.30)))
    crr = float(profile.get("Crr", profile.get("crr", 0.004)))
    drag = 0.5 * RHO * cda * (v ** 3)
    roll = w * G_loc * crr * v
    return {"precision_watt": drag + roll, "drag_watt": drag, "rolling_watt": roll}


def _bool(val: Any) -> bool:
    try:
        return bool(val)
    except Exception:
        return False


def _profile_used_from(profile: dict) -> dict:
    """Bygg nøyaktig profile_used slik testene forventer (snake_case på weight_kg)."""
    out: Dict[str, Any] = {}
    if "CdA" in profile:
        out["CdA"] = float(profile["CdA"])
    if "Crr" in profile:
        out["Crr"] = float(profile["Crr"])
    if "weight_kg" in profile:
        out["weight_kg"] = float(profile["weight_kg"])
    elif "weightKg" in profile:
        out["weight_kg"] = float(profile["weightKg"])
    if "device" in profile:
        out["device"] = profile["device"]
    return out


def _base_debug(force_recompute: bool, used_fallback: bool) -> Dict[str, Any]:
    """Minimal debug-blokk som ALLTID returneres (med default reason='ok')."""
    return {
        "force_recompute": bool(force_recompute),
        "persist_ignored": bool(force_recompute),  # back-compat
        "ignored_persist": bool(force_recompute),  # det testene krever
        "used_fallback": bool(used_fallback),
        "reason": "ok",
    }


def _fallback_metrics(samples, profile, weather_applied: bool, profile_used=None):
    """
    Minimal, deterministisk fallback for tester – leverer allokert nøkkelpakke
    og kan (valgfritt) inkludere profile_used slik den kom inn.
    """
    weight = float(profile.get("weight_kg") or profile.get("weightKg") or 78.0)
    cda = float(profile.get("CdA", profile.get("cda", 0.28)))
    crr = float(profile.get("Crr", profile.get("crr", 0.004)))

    V_NOM = 6.0
    RHO_DEF = 1.225
    G_CONST = 9.80665

    def pack(drag: float, roll: float) -> Dict[str, Any]:
        total = drag + roll
        out = {
            "precision_watt": total,
            "total_watt": total,
            "drag_watt": drag,
            "rolling_watt": roll,
            "weather_applied": bool(weather_applied),
            "precision_watt_ci": 0.0,
        }
        if profile_used is not None:
            out["profile_used"] = profile_used  # legges inne i metrics
        return out

    if not samples:
        drag = 0.5 * RHO_DEF * cda * (V_NOM ** 3)
        roll = crr * weight * G_CONST * V_NOM
        return pack(drag, roll)

    n = 0
    sum_drag = 0.0
    sum_roll = 0.0
    for s in samples:
        v = float(s.get("v_ms") or s.get("v_mps") or s.get("v") or 0.0)
        if v <= 0.0:
            continue
        n += 1
        # ignorér vind i fallback; v_rel = v
        sum_drag += 0.5 * RHO_DEF * cda * (v ** 3)
        sum_roll += crr * weight * G_CONST * v

    drag = (sum_drag / n) if n else 0.0
    roll = (sum_roll / n) if n else 0.0
    return pack(drag, roll)


# ----------------- PROFIL-KANONISERING -----------------
def _scrub_profile(profile_in: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliser alias/kapitalisering og dropp None/støy."""
    p = dict(profile_in or {})
    if "cda" not in p and "CdA" in p:
        p["cda"] = p.pop("CdA")
    if "crr" not in p and "Crr" in p:
        p["crr"] = p.pop("Crr")
    # normaliser weightKg → weight_kg og dropp original
    if "weight_kg" not in p and "weightKg" in p:
        p["weight_kg"] = p.pop("weightKg")
    else:
        p.pop("weightKg", None)
    # fjern None-verdier
    for k in list(p.keys()):
        if p[k] is None:
            del p[k]
    return p


# ----------------- MIDlERTIDIG DEBUG-ENDepunkt (adapter passthrough) -----------------
@router.post("/debug/rb")
async def debug_rb(request: Request):
    """
    Minimal passthrough → kaller rs_power_json direkte med body som kommer inn.
    Forventer OBJECT: {"samples":[...], "profile":{...}, "estimat":{...}}
    Returnerer {"source":"rust"/"fallback"/"error", "out":<str>, "probe": <bool>, "err":<str|None>}
    """
    try:
        data = await request.json()
    except Exception as e:
        return {"source": "error", "out": "", "probe": False, "err": f"json body: {e}"}

    if rs_power_json is None:
        err_msg = (
            f"Rust adapter import error: {_adapter_import_error}"
            if "_adapter_import_error" in globals()
            else "Rust adapter not available"
        )
        return {"source": "error", "out": "", "probe": False, "err": err_msg}

    samples = data.get("samples", [])
    profile = data.get("profile", {})
    # estimat i body (kan brukes til echo i debug)
    body_estimat = data.get("estimat") or data.get("estimate")
    third = body_estimat  # begge alias støttes

    try:
        out = rs_power_json(samples, profile, third)
        out_str = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)

        # En enkel probe: om brukeren sendte med "__probe" / "probe"
        probe = data.get("__probe") or data.get("probe")

        # Heuristikk for å gjette kilde + form svar med setdefault-prinsipp
        src = "rust"
        try:
            parsed = json.loads(out_str)
            if isinstance(parsed, dict):
                s = parsed.get("source")
                if s and "fallback" in str(s):
                    src = "fallback"

                resp = dict(parsed)

                # --- debug (setdefault, ikke overskrive) ---
                dbg = resp.setdefault("debug", {})
                dbg.setdefault("reason", "ok")
                if "used_fallback" not in dbg:
                    dbg["used_fallback"] = (src == "fallback")
                if probe:
                    dbg.setdefault("probe", probe)

                # Echo estimat_cfg_used (whitelist nøkler) — kun for debug
                # 1) Hvis vi faktisk sendte estimat i denne stien (fra body)
                if isinstance(body_estimat, dict) and body_estimat:
                    echo = {}
                    for k in ("force",):
                        if k in body_estimat:
                            echo[k] = body_estimat[k]
                    if echo:
                        dbg.setdefault("estimat_cfg_used", echo)

                # --- toppnivå og metrics med setdefault ---
                resp.setdefault("weather_applied", False)

                m = resp.setdefault("metrics", {})
                m.setdefault("precision_watt", 0.0)
                m.setdefault("drag_watt", 0.0)
                m.setdefault("rolling_watt", 0.0)
                m.setdefault("total_watt", m.get("precision_watt", 0.0))
                m.setdefault("profile_used", {})

                out_str = json.dumps(resp, ensure_ascii=False)
        except Exception:
            # Hvis ikke JSON, la out_str være som den er
            pass

        return {"source": src, "out": out_str, "probe": bool(probe), "err": None}
    except Exception as e:
        return {"source": "error", "out": "", "probe": False, "err": repr(e)}


# ----------------- ANALYZE: RUST-FØRST + TIDLIG RETURN -----------------
@router.post("/{sid}/analyze")
async def analyze_session(
    sid: str,
    request: Request,
    no_weather: bool = Query(False),  # beholdt for signatur-compat (ikke brukt i trinn 3)
    force_recompute: bool = Query(False),
    debug: int = Query(0),
):
    want_debug = bool(debug)
    print(f"[SVR] >>> ANALYZE ENTER (Rust-first) sid={sid} debug={want_debug}")

    # Les body trygt
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Valider shape
    samples = list((body or {}).get("samples") or [])
    profile_in = dict((body or {}).get("profile") or {})
    if not isinstance(samples, list) or not isinstance(profile_in, dict):
        raise HTTPException(status_code=400, detail="Missing 'samples' or 'profile'")

    profile_scrubbed = _scrub_profile(profile_in)

    # Estimat-konfig (3. argument) – IKKE vær
    estimat_cfg: Dict[str, Any] = {}
    if force_recompute:
        estimat_cfg["force"] = True
    if isinstance(body.get("estimat"), dict):
        estimat_cfg.update(body["estimat"])
    elif isinstance(body.get("estimate"), dict):
        estimat_cfg.update(body["estimate"])

    # ---------- HARD RUST SHORT-CIRCUIT ----------
    if rs_power_json is not None:
        try:
            print("[SVR] [RUST] calling rs_power_json(...)")
            # tredje argument = ESTIMAT, aldri weather
            rust_out = rs_power_json(samples, profile_scrubbed, estimat_cfg)
            # Adapter kan returnere str (JSON) eller dict
            rust_resp = json.loads(rust_out) if isinstance(rust_out, str) else rust_out

            if isinstance(rust_resp, dict):
                resp = dict(rust_resp)

                # Pakk flat → metrics (belte & bukseseler), men ikke overskriv tall
                if "metrics" not in resp:
                    keys = ("precision_watt", "drag_watt", "rolling_watt", "total_watt")
                    if any(k in resp for k in keys):
                        m = {k: resp.pop(k) for k in keys if k in resp}
                        if "profile_used" in resp and isinstance(resp["profile_used"], dict):
                            m.setdefault("profile_used", resp["profile_used"])
                        resp["metrics"] = m

                # Kilde + weather (setdefault så vi ikke overstyrer)
                resp.setdefault("source", "rust_1arg")
                resp.setdefault("weather_applied", False)

                # TEST-KRAV: metrics.profile_used == innsendt profil (rå inn-profil)
                mm = resp.setdefault("metrics", {})
                mm.setdefault("profile_used", dict(profile_in))
                # TEST-KRAV: m["weather_applied"] finnes (False i Trinn 3)
                mm.setdefault("weather_applied", bool(resp.get("weather_applied", False)))

                # 🔹 debug-flagg (force + aliaser) + echo av estimat_cfg
                dbg = resp.setdefault("debug", {})
                dbg.setdefault("reason", "ok")
                dbg["force_recompute"] = bool(force_recompute)
                dbg["persist_ignored"] = bool(force_recompute)  # back-compat
                dbg["ignored_persist"] = bool(force_recompute)  # test key
                if force_recompute:
                    # Echo estimat_cfg for traceability (kun når force=True)
                    dbg["estimat_cfg_used"] = dict(estimat_cfg)

                final = _ensure_contract_shape(resp)
                return final  # ← tidlig retur ved Rust-suksess

            print("[SVR] [RUST] no dict/metrics in response → will try fallback")

        except Exception:
            print("[SVR] [RUST] exception → will try fallback", file=sys.stderr, flush=True)
            traceback.print_exc()

    # ---------- PURE FALLBACK_PY (minimal) ----------
    fb = {
        "source": "fallback_py",
        "weather_applied": False,
        "profile_used": profile_scrubbed,
        "metrics": {
            "precision_watt": 0.0,
            "drag_watt": 0.0,
            "rolling_watt": 0.0,
            "total_watt": 0.0,
        },
        "debug": {
            "reason": "fallback-path",
            "note": "Legacy Python path executed (no Rust result short-circuited).",
            "force_recompute": bool(force_recompute),
            "persist_ignored": bool(force_recompute),
            "ignored_persist": bool(force_recompute),
        },
        "sid": sid,
    }
    print("[SVR] [FB] returning fallback_py")
    return _ensure_contract_shape(fb)
