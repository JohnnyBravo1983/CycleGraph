# server/routes/sessions.py
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict, List, Optional

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
    Sett sikre defaults og garanter kontrakt:
      - resp.source, resp.weather_applied, resp.profile_used
      - resp.metrics.precision_watt/drag_watt/rolling_watt/total_watt
      - debug.reason = "ok" (kan senere overstyres ved feil)
    """
    resp = dict(resp or {})

    # toppnivå defaults
    resp.setdefault("source", resp.get("source") or "fallback_py")
    resp.setdefault("weather_applied", False)
    resp.setdefault("profile_used", {})  # speil av metrics.profile_used om satt

    # metrics: alias + defaults
    m = resp.setdefault("metrics", {})
    m.setdefault("precision_watt", 0.0)
    m.setdefault("drag_watt", 0.0)
    m.setdefault("rolling_watt", 0.0)

    # total_watt = precision_watt (alias) hvis satt; ellers drag+rolling
    if "total_watt" not in m:
        total = m.get("precision_watt")
        if (total is None or float(total) == 0.0) and (
            float(m.get("drag_watt", 0.0)) != 0.0 or float(m.get("rolling_watt", 0.0)) != 0.0
        ):
            total = float(m.get("drag_watt", 0.0)) + float(m.get("rolling_watt", 0.0))
        m["total_watt"] = float(total or 0.0)

    # speil metrics.profile_used til toppnivå profile_used om tilstede
    if "profile_used" in m and isinstance(m["profile_used"], dict):
        resp["profile_used"] = m["profile_used"]

    # debug-defaults (inkl. reason)
    dbg = resp.setdefault("debug", {})
    dbg.setdefault("reason", "ok")

    return resp


def _nominal_metrics(profile: dict) -> dict:
    G_loc = 9.80665
    RHO = 1.225
    v = 6.0
    w = float(profile.get("weight_kg") or profile.get("weightKg") or 78.0)
    cda = float(profile.get("CdA", profile.get("cda", 0.30)))
    crr = float(profile.get("Crr", profile.get("crr", 0.004)))
    drag = 0.5 * RHO * cda * (v ** 3)
    roll = w * G_loc * crr * v
    return {"precision_watt": drag + roll, "drag_watt": drag, "rolling_watt": roll}


# --------------------------------------------------------------------------


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
def _canon_profile(p: dict) -> dict:
    """
    Dropper alias-duplikater og felter vi ikke skal sende i Trinn 3.
    Prioriterer snake_case (cda, crr, weight_kg), fjerner 'device',
    og sikrer eksplisitt bool for calibrated.
    """
    p = dict(p or {})
    # cda
    if "cda" not in p and "CdA" in p:
        p["cda"] = p.pop("CdA")
    else:
        p.pop("CdA", None)
    # crr
    if "crr" not in p and "Crr" in p:
        p["crr"] = p.pop("Crr")
    else:
        p.pop("Crr", None)
    # weight
    if "weight_kg" not in p and "weightKg" in p:
        p["weight_kg"] = p.pop("weightKg")
    else:
        p.pop("weightKg", None)

    # Felter vi ikke skal sende nå
    p.pop("device", None)

    # Sørg for eksplisitt bool for calibrated
    if "calibrated" not in p:
        p["calibrated"] = False

    return {
        "cda": p.get("cda"),
        "crr": p.get("crr"),
        "weight_kg": p.get("weight_kg"),
        "calibrated": bool(p.get("calibrated", False)),
    }


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
    third = data.get("estimat") or data.get("estimate")  # begge alias støttes

    try:
        out = rs_power_json(samples, profile, third)
        out_str = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)

        # En enkel probe: om brukeren sendte med "__probe"
        probe = "__probe" in (data or {})

        # Heuristikk for å gjette kilde
        src = "rust"
        try:
            parsed = json.loads(out_str)
            if isinstance(parsed, dict):
                s = parsed.get("source")
                if s and "fallback" in str(s):
                    src = "fallback"
        except Exception:
            if out_str.strip().startswith('{"calibrated"'):
                src = "rust"

        return {"source": src, "out": out_str, "probe": probe, "err": None}
    except Exception as e:
        return {"source": "error", "out": "", "probe": False, "err": repr(e)}


# ----------------- NY HJELPER FOR RUST-STIEN -----------------
def _scrub_profile(profile_in: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliser alias/kapitalisering og dropp None/støy."""
    p = dict(profile_in or {})
    if "cda" not in p and "CdA" in p:
        p["cda"] = p.pop("CdA")
    if "crr" not in p and "Crr" in p:
        p["crr"] = p.pop("Crr")
    # ✅ tillegg A: normaliser weightKg → weight_kg og dropp original
    if "weight_kg" not in p and "weightKg" in p:
        p["weight_kg"] = p.pop("weightKg")
    else:
        p.pop("weightKg", None)
    # fjern None-verdier
    for k in list(p.keys()):
        if p[k] is None:
            del p[k]
    return p


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
            rust_out = rs_power_json(samples, profile_scrubbed, estimat_cfg)
            # Adapter kan returnere str (JSON) eller dict
            rust_resp = json.loads(rust_out) if isinstance(rust_out, str) else rust_out

            if isinstance(rust_resp, dict):
                # ✅ tillegg B: koercer flat → metrics dersom nødvendig
                resp = dict(rust_resp)
                if "metrics" not in resp:
                    keys = ("precision_watt", "drag_watt", "rolling_watt", "total_watt")
                    if any(k in resp for k in keys):
                        m = {k: resp.pop(k) for k in keys if k in resp}
                        if "profile_used" in resp and isinstance(resp["profile_used"], dict):
                            m.setdefault("profile_used", resp["profile_used"])
                        resp["metrics"] = m
                resp.setdefault("source", "rust_1arg")
                resp.setdefault("weather_applied", False)
                final = _ensure_contract_shape(resp)
                print("[SVR] [RUST] success (coerced) → returning early")
                return final

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
        },
        "sid": sid,
    }
    print("[SVR] [FB] returning fallback_py")
    return _ensure_contract_shape(fb)
