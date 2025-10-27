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
    if cg is None or not hasattr(cg, "rust_calibrate_session"):
        raise RuntimeError("rust_calibrate_session ikke tilgjengelig (bygg core med --features python).")

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
