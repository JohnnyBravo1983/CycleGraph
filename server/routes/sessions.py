# server/routes/sessions.py
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _bool(val: Any) -> bool:
    try:
        return bool(val)
    except Exception:
        return False


@router.post("/{sid}/analyze")
async def analyze_session(
    sid: str,
    request: Request,
    force_recompute: bool = False,
):
    """
    Analyze a session's time-series samples with physics + (optional) weather,
    delegating heavy lifting to Rust via PyO3 bindings.

    Deterministisk kallesekvens:
      1) compute_power_with_wind_json(TRIPLE [samples, profile, estimat])  ← preferert
      2) compute_power_with_wind_json(OBJECT {"samples","profile","estimat"})
      3) PY-fallback (midlertidig) for å verifisere API-pipen
    """
    try:
        print("DEBUG MARK: top of analyze handler", file=sys.stderr)
        print('DEBUG WHO: module=server.routes.sessions file=' + __file__, file=sys.stderr)

        body: Dict[str, Any] = {}
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
        except Exception:
            # Tillat tomt/ugyldig JSON; vi bruker defaults og feiler senere hvis nødvendig
            body = {}

        # ---- profile (safe defaults) ----
        profile: Dict[str, Any] = body.get("profile") or {}
        if not isinstance(profile, dict):
            raise ValueError("profile must be an object/dict")

        profile.setdefault("CdA", 0.28)
        profile.setdefault("Crr", 0.004)
        profile.setdefault("weightKg", 78.0)
        profile.setdefault("device", "strava")
        profile.setdefault("calibrated", False)
        print(f"DEBUG PROFILE (normalized): {profile}", file=sys.stderr)

        # ---- samples ----
        samples: Optional[List[Dict[str, Any]]] = body.get("samples")
        if samples is not None and not isinstance(samples, list):
            raise ValueError("samples must be a list")

        if samples:
            print(f"DEBUG SAMPLES LEN: {len(samples)} HEAD: {samples[0]}", file=sys.stderr)
        else:
            print("DEBUG SAMPLES LEN: 0", file=sys.stderr)

        # ---- utvidet mapping og trygge defaults ----
        mapped: List[Dict[str, Any]] = []
        for s in (samples or []):
            d = dict(s)

            # --- tid ---
            if "t" in d:
                try:
                    d["t"] = float(d["t"])
                except Exception:
                    raise ValueError("sample.t må være numerisk")

            # --- hastighet ---
            if "v_ms" not in d:
                if "v_mps" in d:
                    d["v_ms"] = float(d.pop("v_mps"))
                elif "v" in d:
                    d["v_ms"] = float(d["v"])
                else:
                    raise ValueError("sample mangler fart: forventet v_ms/v_mps")

            # --- høyde ---
            if "altitude_m" not in d:
                if "alt" in d:
                    d["altitude_m"] = float(d["alt"])
                elif "elev" in d:
                    d["altitude_m"] = float(d["elev"])
                else:
                    d["altitude_m"] = 0.0  # trygg default

            # --- retning (grader, 0–360). Konservativ default = None (ukjent) ---
            if "heading_deg" not in d:
                if "heading" in d:
                    try:
                        d["heading_deg"] = float(d["heading"])
                    except Exception:
                        d["heading_deg"] = None
                elif "bearing" in d:
                    try:
                        d["heading_deg"] = float(d["bearing"])
                    except Exception:
                        d["heading_deg"] = None
                else:
                    d["heading_deg"] = None

            # --- bevegelse ---
            if "moving" not in d:
                v_ok = False
                try:
                    v_ok = float(d.get("v_ms", 0.0)) > 0.0
                except Exception:
                    v_ok = False
                watts_ok = False
                try:
                    watts_ok = float(d.get("watts", 0.0)) > 0.0
                except Exception:
                    watts_ok = False
                d["moving"] = bool(v_ok or watts_ok)

            # --- miljøfelter (la være None om ukjent) ---
            d.setdefault("rho", None)            # kg/m^3
            d.setdefault("wind_speed", None)     # m/s (legacy)
            d.setdefault("wind_dir_deg", None)   # 0–360 (fra)
            d.setdefault("air_temp_c", None)     # °C
            d.setdefault("pressure_hpa", None)   # hPa
            d.setdefault("humidity", None)       # 0–1 eller %
            mapped.append(d)

        if mapped:
            print(f"DEBUG SAMPLES MAPPED[0]: {mapped[0]}", file=sys.stderr)

        # ---- force_recompute (kun logging her) ----
        print(f"DEBUG force_recompute={force_recompute}", file=sys.stderr)

        # ---- estimat fra body (kun logging; vi shimer uansett like før Rust) ----
        estimat_body: Dict[str, Any] = body.get("estimat") or {}
        if not isinstance(estimat_body, dict):
            raise ValueError("estimat must be an object/dict (if provided)")
        print(f"DEBUG ESTIMAT (body): {estimat_body}", file=sys.stderr)

        # ======================================================================
        # ROBUST SKRUBBING – rett før Rust-kall
        # ======================================================================
        # Utvidet: inkluderer rho/humidity/wind_* slik at ingenting blir None
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
                        print(f"DEBUG SANITIZE: sample[{i}].{k}={v!r} -> 0.0", file=sys.stderr)
                        d[k] = 0.0
            # moving skal være bool
            try:
                d["moving"] = bool(d.get("moving", (float(d.get("v_ms", 0.0)) > 0.1)))
            except Exception:
                d["moving"] = bool(d.get("moving", False))
            sanitized.append(d)

        mapped = sanitized
        print(f"DEBUG SANITIZED HEAD: {mapped[0] if mapped else None}", file=sys.stderr)

        # Scrub profile: sikre float-felt
        def _to_float(x, default=0.0):
            try:
                return float(0.0 if x is None else x)
            except Exception:
                return default

        profile["CdA"] = _to_float(profile.get("CdA"), 0.28)
        profile["Crr"] = _to_float(profile.get("Crr"), 0.004)
        profile["weightKg"] = _to_float(profile.get("weightKg"), 78.0)
        profile["calibrated"] = bool(profile.get("calibrated", False))
        print(f"DEBUG PROFILE SCRUBBED: {profile}", file=sys.stderr)
        # ======================================================================

        # ======================================================================
        # DETERMINISTISK RUST-KALL — tvang ikke-tomt estimat + TRIPLE først
        # ======================================================================
        # --- estimat shim (non-empty) ---
        estimat: Dict[str, Any] = {"mode": "inline", "version": 1, "force": False, "notes": "shim"}
        print(f"DEBUG ESTIMAT (shim): {estimat}", file=sys.stderr)

        # --- build the TRIPLE ARRAY payload ---
        payload_triple = [mapped, profile, estimat]
        payload_triple_str = json.dumps(payload_triple)
        print(f"DEBUG CALL: rust_json TRIPLE len={len(payload_triple_str)}", file=sys.stderr)

        try:
            from cyclegraph_core import compute_power_with_wind_json as rust_json
        except Exception as e_imp:
            # Hvis json-varianten ikke finnes, gi tydelig feilmelding
            raise HTTPException(status_code=500, detail=f"Rust binding import error: {e_imp}") from e_imp

        try:
            result_json = rust_json(payload_triple_str)
            print(f"DEBUG OK : rust_json TRIPLE → {str(result_json)[:160]}...", file=sys.stderr)
            result_json_or_dict: Any = result_json

        except Exception as e_triple:
            print(f"DEBUG FAIL TRIPLE: {e_triple!r}", file=sys.stderr)
            # fallback: OBJECT form with non-empty estimat
            payload_obj = {"samples": mapped, "profile": profile, "estimat": estimat}
            payload_obj_str = json.dumps(payload_obj)
            print(f"DEBUG CALL: rust_json OBJECT len={len(payload_obj_str)}", file=sys.stderr)
            try:
                result_json = rust_json(payload_obj_str)  # vil raise hvis inkompatibel
                print(f"DEBUG OK : rust_json OBJECT → {str(result_json)[:160]}...", file=sys.stderr)
                result_json_or_dict = result_json
            except Exception as e_obj:
                # ================== PY-FALLBACK (midlertidig) ==================
                print(f"DEBUG RUST FAIL, using PY fallback: {e_obj!r}", file=sys.stderr)
                # Minimal “fysikk”: P ~ 0.5*rho*CdA*v^3 + Crr*mg*v
                rho = 1.225
                CdA = float(profile.get("CdA", profile.get("cda", 0.28)))
                Crr = float(profile.get("Crr", profile.get("crr", 0.004)))
                m   = float(profile.get("weightKg", profile.get("weight_kg", 78.0)))
                g   = 9.81

                v = sum((s.get("v_ms") if s.get("v_ms") is not None else s.get("v_mps", 0.0)) for s in mapped) / max(len(mapped), 1)
                try:
                    v = float(v)
                except Exception:
                    v = 0.0

                drag = 0.5 * rho * CdA * (v ** 3)
                roll = Crr * m * g * v
                pw   = drag + roll

                result_json_or_dict = {
                    "metrics": {
                        "precision_watt": pw,
                        "precision_watt_ci": 0.0
                    },
                    "profile": profile,
                    "source": "fallback_py",
                }
                print(f"DEBUG PY FALLBACK RESULT: pw={pw:.3f} (v={v:.3f}, CdA={CdA}, Crr={Crr}, m={m})", file=sys.stderr)
                # ================================================================

        # ---- Normaliser retur: kan være JSON-string eller dict ----
        if isinstance(result_json_or_dict, str):
            try:
                result = json.loads(result_json_or_dict)
            except Exception as e:
                raise ValueError(f"Rust returned non-JSON string: {e}") from e
        elif isinstance(result_json_or_dict, dict):
            result = result_json_or_dict
        else:
            raise ValueError("Rust returned unsupported type (expected str or dict)")

        # Suksess
        return result

    except HTTPException:
        raise
    except Exception as e:
        # Behold bred feilhåndtering for gode meldinger
        tb = traceback.format_exc()
        print("DEBUG ERROR in analyze_session:", file=sys.stderr)
        print(tb, file=sys.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {e}",
        ) from e
