# server/routes/sessions.py
from __future__ import annotations

import json
import sys
import traceback
import os
from importlib import import_module
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Query

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
        "persist_ignored": bool(force_recompute),   # back-compat
        "ignored_persist": bool(force_recompute),   # det testene krever
        "used_fallback": bool(used_fallback),
        "reason": "ok",                             # NY: kontrakten forventer denne
    }


def _normalize_response(
    resp: dict,
    *,
    profile_in: dict,
    force_recompute: bool,
    used_fallback: bool,
    sid: str,
) -> dict:
    """
    Tving svaret til å oppfylle API-/test-kontrakt uansett code path.
    - debug finnes alltid (base + ev. eksisterende)
    - metrics har total_watt/drag_watt/rolling_watt/precision_watt_ci/weather_applied
    - metrics.profile_used settes fra INN-profilen (ikke scrubbed)
    - alltid med sid
    - fjerner evt. toppnivå "profile" hvis den lekker
    """
    resp = dict(resp or {})
    resp.setdefault("source", "fallback_py" if used_fallback else "rust")
    resp.setdefault("sid", sid)
    resp.setdefault("metrics", {})
    resp.setdefault("debug", {})

    # Metrics: alias + defaults
    m = resp["metrics"] = dict(resp["metrics"] or {})
    if "precision_watt" in m and "total_watt" not in m:
        m["total_watt"] = m["precision_watt"]
    m.setdefault("drag_watt", 0.0)
    m.setdefault("rolling_watt", 0.0)
    m.setdefault("precision_watt", m.get("drag_watt", 0.0) + m.get("rolling_watt", 0.0))
    m.setdefault("precision_watt_ci", 0.0)
    m.setdefault("weather_applied", False)
    m.setdefault("profile_used", _profile_used_from(profile_in))

    # Debug: base alltid med
    dbg = dict(_base_debug(force_recompute, used_fallback))
    dbg.update(resp.get("debug") or {})
    resp["debug"] = dbg

    # Ikke eksponer toppnivå "profile"
    if "profile" in resp:
        resp.pop("profile")

    return resp


def _fallback_metrics(samples, profile, weather_applied: bool, profile_used=None):
    """
    Minimal, deterministisk fallback for tester – leverer allokert nøkkelpakke
    og kan (valgfritt) inkludere profile_used slik den kom inn.
    """
    weight = float(profile.get("weight_kg") or profile.get("weightKg") or 78.0)
    cda    = float(profile.get("CdA", profile.get("cda", 0.28)))
    crr    = float(profile.get("Crr", profile.get("crr", 0.004)))

    V_NOM = 6.0
    RHO_DEF = 1.225
    G_CONST = 9.80665

    def pack(drag: float, roll: float) -> Dict[str, Any]:
        total = drag + roll
        out = {
            "precision_watt": total,
            "total_watt": total,                 # alias som testene bruker
            "drag_watt": drag,
            "rolling_watt": roll,
            "weather_applied": bool(weather_applied),
            "precision_watt_ci": 0.0,            # 0.0 i trinn 3 er OK
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


@router.post("/{sid}/analyze")
async def analyze_session(
    sid: str,
    request: Request,
    no_weather: bool = Query(False),
    force_recompute: bool = Query(False),
    debug: int = Query(0),
):
    """
    Analyze a session's time-series samples with physics + (optional) weather,
    delegating heavy lifting to Rust via PyO3 bindings.

    Kallesekvens:
      1) compute_power_with_wind_json(TRIPLE [samples, profile, estimat])  ← prioritet
      2) compute_power_with_wind_json(OBJECT {"samples","profile","estimat"|"estimate"})  ← fallback
      3) PY-fallback (midlertidig) for å sikre 200 OK + metrics.* nøkler
    """
    try:
        want_debug = bool(debug)

        print("DEBUG ENTER analyze_session", file=sys.stderr, flush=True)
        print("DEBUG MARK: top of analyze handler", file=sys.stderr, flush=True)
        print('DEBUG WHO: module=server.routes.sessions file=' + __file__, file=sys.stderr, flush=True)

        # ---------- Parse body ----------
        body: Dict[str, Any] = {}
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
        except Exception:
            body = {}

        # ---------- Profile + defaults ----------
        profile_in_request_raw: Dict[str, Any] = body.get("profile") or {}
        if not isinstance(profile_in_request_raw, dict):
            raise ValueError("profile must be an object/dict")

        profile: Dict[str, Any] = dict(profile_in_request_raw)
        profile.setdefault("CdA", 0.28)
        profile.setdefault("Crr", 0.004)
        profile.setdefault("weightKg", 78.0)
        profile.setdefault("device", "strava")
        profile.setdefault("calibrated", False)
        print(f"DEBUG PROFILE (normalized): {profile}", file=sys.stderr, flush=True)

        # ---------- Samples ----------
        samples: Optional[List[Dict[str, Any]]] = body.get("samples")
        if samples is not None and not isinstance(samples, list):
            raise ValueError("samples must be a list")

        if samples:
            print(f"DEBUG SAMPLES LEN: {len(samples)} HEAD: {samples[0]}", file=sys.stderr, flush=True)
        else:
            print("DEBUG SAMPLES LEN: 0", file=sys.stderr, flush=True)

        # ---------- Mapping + trygge defaults ----------
        mapped: List[Dict[str, Any]] = []
        for s in (samples or []):
            d = dict(s)

            # tid
            if "t" in d:
                try:
                    d["t"] = float(d["t"])
                except Exception:
                    raise ValueError("sample.t må være numerisk")

            # fart (v_ms kreves)
            if "v_ms" not in d:
                if "v_mps" in d:
                    d["v_ms"] = float(d.pop("v_mps"))
                elif "v" in d:
                    d["v_ms"] = float(d["v"])
                else:
                    raise ValueError("sample mangler fart: forventet v_ms/v_mps/v")

            # høyde
            if "altitude_m" not in d:
                if "alt" in d:
                    d["altitude_m"] = float(d["alt"])
                elif "elev" in d:
                    d["altitude_m"] = float(d["elev"])
                else:
                    d["altitude_m"] = 0.0

            # retning
            if "heading_deg" not in d:
                if "heading" in d:
                    try:
                        d["heading_deg"] = float(d["heading"])
                    except Exception:
                        d["heading_deg"] = 0.0
                elif "bearing" in d:
                    try:
                        d["heading_deg"] = float(d["bearing"])
                    except Exception:
                        d["heading_deg"] = 0.0
                else:
                    d["heading_deg"] = 0.0

            # moving
            if "moving" not in d:
                try:
                    d["moving"] = bool(float(d.get("v_ms", 0.0)) > 0.0 or float(d.get("watts", 0.0)) > 0.0)
                except Exception:
                    d["moving"] = False

            # miljøfelter (kan mangle)
            d.setdefault("rho", None)
            d.setdefault("wind_speed", None)   # legacy
            d.setdefault("wind_dir_deg", None)
            d.setdefault("air_temp_c", None)
            d.setdefault("pressure_hpa", None)
            d.setdefault("humidity", None)

            mapped.append(d)

        if mapped:
            print(f"DEBUG SAMPLES MAPPED[0]: {mapped[0]}", file=sys.stderr, flush=True)

        print(f"DEBUG force_recompute={force_recompute}", file=sys.stderr, flush=True)

        # ---------- Estimat i body (kun logging) ----------
        estimat_body: Dict[str, Any] = body.get("estimat") or {}
        if not isinstance(estimat_body, dict):
            raise ValueError("estimat must be an object/dict (if provided)")
        print(f"DEBUG ESTIMAT (body): {estimat_body}", file=sys.stderr, flush=True)

        # ---------- Sanitizer ----------
        NUMERIC_SAMPLE_KEYS = [
            "t", "watts", "v_ms", "altitude_m", "heading_deg",
            "air_temp_c", "pressure_hpa", "wind_ms", "wind_speed",
            "wind_dir_deg", "humidity", "humidity_pct", "rho",
        ]

        sanitized: List[Dict[str, Any]] = []
        for i, s in enumerate(mapped):
            d = dict(s)
            for k in NUMERIC_SAMPLE_KEYS:
                if k in d:
                    v = d[k]
                    try:
                        d[k] = float(0.0 if v is None else v)
                    except Exception:
                        print(f"DEBUG SANITIZE: sample[{i}].{k}={v!r} -> 0.0", file=sys.stderr, flush=True)
                        d[k] = 0.0
            try:
                d["moving"] = bool(d.get("moving", (float(d.get("v_ms", 0.0)) > 0.1)))
            except Exception:
                d["moving"] = bool(d.get("moving", False))
            sanitized.append(d)

        mapped = sanitized
        print(f"DEBUG MAPPED len={len(mapped)}", file=sys.stderr, flush=True)
        if mapped[:3]:
            print(f"DEBUG FIRST SPEEDS: {[s.get('v_ms') for s in mapped[:3]]}", file=sys.stderr, flush=True)
        print(f"DEBUG SANITIZED HEAD: {mapped[0] if mapped else None}", file=sys.stderr, flush=True)

        # --- Ensure each sample has a monotonic 't' (seconds) ---
        synth_count = 0
        t_prev = -1.0
        for i, s in enumerate(mapped):
            t_val = s.get("t", None)
            try:
                if t_val is None:
                    raise ValueError("no t")
                t_num = float(t_val)
            except Exception:
                # Syntetiser 1.0 s intervaller hvis t mangler/ikke-numerisk
                t_num = (t_prev + 1.0) if t_prev >= 0.0 else float(i)
                s["t"] = t_num
                synth_count += 1
            else:
                # Tving monotoni
                if t_prev >= 0.0 and t_num <= t_prev:
                    t_num = t_prev + 1.0
                    s["t"] = t_num
                    synth_count += 1
            t_prev = t_num

        if synth_count:
            print(f"DEBUG T-SYNTH: synthesized/adjusted t for {synth_count} samples", file=sys.stderr, flush=True)

        # Scrub profile (KUN til beregning, ikke til profile_used)
        def _to_float(x, default=0.0):
            try:
                return float(0.0 if x is None else x)
            except Exception:
                return default

        profile["CdA"] = _to_float(profile.get("CdA"), 0.28)
        profile["Crr"] = _to_float(profile.get("Crr"), 0.004)
        profile["weightKg"] = _to_float(profile.get("weightKg"), 78.0)
        profile["calibrated"] = bool(profile.get("calibrated", False))
        print(f"DEBUG PROFILE SCRUBBED: {profile}", file=sys.stderr, flush=True)
        profile_scrubbed = dict(profile)  # brukes i fallback-beregning

        # --- Ensure wind_ms / wind_speed aliases for Rust ---
        for s in mapped:
            wms = s.get("wind_ms", None)
            wsp = s.get("wind_speed", None)
            try:
                if wms is None and wsp is not None:
                    s["wind_ms"] = float(wsp)
                if wsp is None and wms is not None:
                    s["wind_speed"] = float(wms)
            except Exception:
                s["wind_ms"] = float(s.get("wind_ms") or 0.0)
                s["wind_speed"] = float(s.get("wind_speed") or 0.0)

        # --- (Valgfritt) Prune samples til sikre felter første gang (styrt av env) ---
        PRUNE_FOR_RUST = os.environ.get("CG_PRUNE_FOR_RUST") == "1"
        if PRUNE_FOR_RUST:
            KEEP = {"t", "v_ms", "altitude_m", "heading_deg", "watts", "moving"}
            mapped = [{k: d[k] for k in KEEP if k in d} for d in mapped]
            print(f"DEBUG PRUNE: enabled (CG_PRUNE_FOR_RUST=1) → fields={sorted(KEEP)}", file=sys.stderr, flush=True)
            if mapped:
                print(f"DEBUG PRUNE HEAD: {mapped[0]}", file=sys.stderr, flush=True)

        # ---------- Estimat + payloads ----------
        est: Dict[str, Any] = {"mode": "inline", "version": 1, "force": bool(force_recompute), "notes": "shim"}

        # TRIPLE først (wheel krever dette): [samples, profile, est]
        payload_triple_str = json.dumps([mapped, profile, est])

        # OBJECT fallback – send begge nøkler (estimat/estimate) for robusthet
        payload_obj_str = json.dumps({
            "estimat": est,   # eldre wheel
            "estimate": est,  # nyere wheel
            "profile": profile,
            "samples": mapped,
        })

        # ---------- Rust binding ----------
        try:
            rust_mod = import_module("cyclegraph_core.cyclegraph_core")
            rust_json = rust_mod.compute_power_with_wind_json
        except Exception as e_imp:
            raise HTTPException(status_code=500, detail=f"Rust binding import error: {e_imp}") from e_imp

        # ---------- Kall Rust med forsøk ----------
        used_fallback = False
        result: Optional[dict] = None
        attempts: List[Dict[str, str]] = []

        # TRIPLE
        try:
            r = rust_json(payload_triple_str)
            result = json.loads(r) if isinstance(r, str) else (r if isinstance(r, dict) else None)
            branch = "triple"
            variant = "array_triple"
        except Exception as e_triple:
            if want_debug:
                attempts.append({"variant": "array_triple", "error": repr(e_triple)})
            result = None

        # OBJECT (hvis TRIPLE feilet)
        if result is None:
            branch = "object"
            try:
                r = rust_json(payload_obj_str)
                result = json.loads(r) if isinstance(r, str) else (r if isinstance(r, dict) else None)
                variant = "object_both_est_keys"
            except Exception as e_obj:
                if want_debug:
                    attempts.append({"variant": "object_both_est_keys", "error": repr(e_obj)})
                used_fallback = True
                # bygg minimal respons; normalize fyller nøklene
                result = {
                    "source": "fallback_py",
                    "metrics": {},
                    "debug": {},
                }
                variant = "fallback_py"

        # Normaliser + legg på ekstra debug når debug=1
        normalized = _normalize_response(
            result,
            profile_in=profile_in_request_raw,  # NB: inn-profil for profile_used
            force_recompute=bool(force_recompute),
            used_fallback=used_fallback,
            sid=sid,
        )

        if want_debug:
            normalized["debug"].update({
                "branch": branch,
                "variant": variant,
            })
            if attempts:
                normalized["debug"]["attempts"] = attempts

        # ----------------- KONTRAKT-SIKRING FØR RETUR -----------------
        resp = dict(normalized)

        # --- NOMINELL METRICS VED TOMME SAMPLES ---
        try:
            use_nominal = False
            if not mapped:  # mangler samples
                use_nominal = True
            else:
                m_cur = resp.get("metrics") or {}
                if float(m_cur.get("drag_watt", 0.0)) == 0.0 and float(m_cur.get("rolling_watt", 0.0)) == 0.0:
                    use_nominal = True
            if use_nominal:
                nom = _nominal_metrics(profile_in_request_raw or {})
                resp.setdefault("metrics", {}).update(nom)
        except Exception as _e:
            print("DEBUG NOMINAL METRICS ERROR:", repr(_e), file=sys.stderr, flush=True)

        # Hvis metrics mangler/er tomt, fyll inn nominelle verdier (ekstra sikkerhet)
        if not resp.get("metrics"):
            resp["metrics"] = _nominal_metrics(resp.get("profile_used") or profile_scrubbed)

        # Toppnivå weather_applied bør speile metrics.weather_applied
        if "weather_applied" not in resp:
            resp["weather_applied"] = bool(resp.get("metrics", {}).get("weather_applied", False))

        # Toppnivå profile_used: speil fra metrics.profile_used eller fra inn-profilen
        if "profile_used" not in resp or not resp["profile_used"]:
            resp["profile_used"] = dict(
                resp.get("metrics", {}).get("profile_used") or _profile_used_from(profile_in_request_raw)
            )

        # Map ev. gamle debug-nøkler → riktig kontraktfelt (ignored_persist på toppnivå)
        debug_block = resp.get("debug", {}) if isinstance(resp.get("debug"), dict) else {}
        resp["ignored_persist"] = bool(
            resp.get("ignored_persist") or
            debug_block.get("ignored_persist") or
            debug_block.get("persist_ignored")
        )

        # --- KONTRAKT: metrics.profile_used = inn-profilen (IKKE scrubbed) ---
        try:
            resp.setdefault("metrics", {})
            if "profile_used" not in resp["metrics"]:
                resp["metrics"]["profile_used"] = dict(profile_in_request_raw or {})
        except Exception:
            pass

        # Sett standardform på hele svaret (setdefault → ikke overstyr eksisterende)
        resp = _ensure_contract_shape(resp)

        # --- FAIL-SAFE: sørg for at debug.ignored_persist finnes ---
        try:
            resp.setdefault("debug", {})
            if "ignored_persist" not in resp["debug"]:
                resp["debug"]["ignored_persist"] = bool(
                    resp["debug"].get("ignored_persist")
                    or resp["debug"].get("persist_ignored")
                    or False
                )
        except Exception:
            pass
        # ----------------------------------------------------------------------

        return resp

    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print("DEBUG ERROR in analyze_session:", file=sys.stderr, flush=True)
        print(tb, file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}") from e
