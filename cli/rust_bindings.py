# cli/rust_bindings.py
import json
from typing import Any, Dict, Sequence
import cyclegraph_core as cg


def _coerce_jsonish(x: Any) -> Any:
    if isinstance(x, (str, bytes, bytearray)):
        try:
            return json.loads(x)
        except Exception:
            return x
    return x


def calibrate_session(
    watts: Sequence[float],
    speed_ms: Sequence[float],
    altitude_m: Sequence[float],
    profile: Dict[str, Any],
    weather: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Kaller Rust-kalibrering og normaliserer retur for testene:

    - out: dict
    - out["profile"]: JSON-streng (ikke dict)
    - cda/crr/mae: float
    - calibrated: bool

    I tillegg håndteres input-forskjeller på tvers av PyO3-signaturer:
    - Hvis Rust-bindingen forventer str for profile/weather så serialiserer vi dict → JSON.
    """

    # --- NY: myk fallback dersom rust_calibrate_session ikke finnes ---
    if cg is None or not hasattr(cg, "rust_calibrate_session"):
        prof_out = dict(profile or {})
        out: Dict[str, Any] = {
            "calibrated": False,
            "cda": float(prof_out.get("cda") or prof_out.get("CdA") or 0.30),
            "crr": float(prof_out.get("crr") or prof_out.get("Crr") or 0.004),
            "mae": 0.0,
            "profile": "{}",
        }
        try:
            out["profile"] = json.dumps(prof_out, ensure_ascii=False)
        except Exception:
            pass
        return out
    # -----------------------------------------------------------------

    # 0) Gjør input robust mht. PyO3-signatur (str vs dict)
    prof_arg: Any = json.dumps(profile, ensure_ascii=False) if isinstance(profile, dict) else profile
    wthr_arg: Any = json.dumps(weather, ensure_ascii=False) if isinstance(weather, dict) else weather

    # 1) Kjør Rust
    out: Any = cg.rust_calibrate_session(watts, speed_ms, altitude_m, prof_arg, wthr_arg)

    # 2) Hvis Rust returnerer JSON-streng, dekod til dict
    if isinstance(out, str):
        try:
            out = json.loads(out)
        except Exception:
            out = {"raw": out}

    out = dict(out or {})

    # 3) Normaliser typer/keys
    out.setdefault("calibrated", False)
    out["calibrated"] = bool(out["calibrated"])

    for k in ("cda", "crr", "mae"):
        v = out.get(k)
        try:
            out[k] = 0.0 if v is None else float(v)
        except Exception:
            out[k] = 0.0

    # 4) Profile: testene forventer JSON-streng
    prof = out.get("profile")
    if isinstance(prof, dict):
        try:
            out["profile"] = json.dumps(prof, ensure_ascii=False)
        except Exception:
            out["profile"] = "{}"
    elif isinstance(prof, str):
        pass
    else:
        out["profile"] = "{}"

    return out


def calibrate_session_dict(
    watts: Sequence[float],
    speed_ms: Sequence[float],
    altitude_m: Sequence[float],
    profile: Dict[str, Any],
    weather: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Backend-variant: samme som over, men koercer out["profile"] til dict
    slik at resten av systemet kan jobbe typetrygt uten json.loads.
    """
    out = calibrate_session(watts, speed_ms, altitude_m, profile, weather)
    out["profile"] = _coerce_jsonish(out.get("profile"))
    return out


# --- Compute adapter (v1/v3-tolerant, tåler str eller dict) ---

def _hasattr(obj, name: str) -> bool:
    try:
        return hasattr(obj, name)
    except Exception:
        return False


# Oppdag v3/v1 på runtime
_USE_V3 = _hasattr(cg, "compute_power_with_wind_json_v3")


def _call_rust_compute(payload: Dict[str, Any]) -> str:
    """
    Kaller v3 hvis tilgjengelig (med 'estimat': {}), ellers v1.
    Fallback fra v3→v1 ved parse-feil.
    Returnerer alltid str (JSON fra Rust).
    """
    if _USE_V3:
        payload.setdefault("estimat", {})  # v3 krever dette
        try:
            return cg.compute_power_with_wind_json_v3(json.dumps(payload, ensure_ascii=False))
        except Exception:
            # v3 feilet – prøv v1
            payload.pop("estimat", None)
            return cg.compute_power_with_wind_json(json.dumps(payload, ensure_ascii=False))
    else:
        payload.pop("estimat", None)
        return cg.compute_power_with_wind_json(json.dumps(payload, ensure_ascii=False))


def _looks_like_weather(x: Any) -> bool:
    if not isinstance(x, dict):
        return False
    keys = x.keys()
    return any(k in keys for k in (
        "air_temp_c", "rho", "pressure_hpa", "humidity",
        "wind_speed", "wind_ms", "wind_dir_deg"
    ))


def rs_power_json(samples, profile, third=None) -> str:
    """
    Backcompat for gamle 3-args kall (samples, profile, weather|estimat).
    Aksepterer både dict/list og JSON-strenger for alle tre.
    Pakker alltid om til ett JSON-argument før Rust-kallet.
    Returnerer str (Rust JSON).
    """
    # Koercer innkommende (kan være JSON-strenger)
    samples = _coerce_jsonish(samples)
    profile = _coerce_jsonish(profile)
    third = _coerce_jsonish(third)

    # Bygg payload
    payload: Dict[str, Any] = {"samples": samples, "profile": profile}

    # Legg 'weather' hvis third ligner vær, ellers tom
    payload["weather"] = third if _looks_like_weather(third) else {}

    # Kjør Rust
    return _call_rust_compute(payload)
