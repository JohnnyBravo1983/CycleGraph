# cli/rust_bindings.py
from __future__ import annotations

import json
from typing import Any, Dict, Sequence

try:
    import cyclegraph_core as cg  # PyO3-extension
except Exception:  # pragma: no cover
    cg = None  # type: ignore


__all__ = [
    "calibrate_session",
    "calibrate_session_dict",
]


def _coerce_jsonish(x: Any) -> Any:
    """Til intern bruk: gjør JSON-aktige str/bytes til Python-objekt (dict/list)."""
    if isinstance(x, (str, bytes, bytearray)):
        try:
            return json.loads(x)
        except Exception:
            return x  # la være; kallende kode får håndtere dette
    return x


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def calibrate_session(
    watts: Sequence[float],
    speed_ms: Sequence[float],
    altitude_m: Sequence[float],
    profile: Dict[str, Any],
    weather: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Kaller Rust-kalibrering og normaliserer retur for testene:
    - returnerer dict
    - out["profile"] er alltid en *gyldig JSON-streng*
    - cda/crr/mae er floats
    - calibrated er bool

    Målet er å være bakoverkompatibel med testens antakelse om at
    `json.loads(out["profile"])` kan kalles uten TypeError.
    """
    if cg is None or not hasattr(cg, "rust_calibrate_session"):
        raise RuntimeError("rust_calibrate_session ikke tilgjengelig (bygg core med --features python).")

    # 1) Kjør Rust
    out: Any = cg.rust_calibrate_session(watts, speed_ms, altitude_m, profile, weather)

    # 2) Hvis Rust returnerer JSON-streng, dekod til dict
    if isinstance(out, (str, bytes, bytearray)):
        try:
            out = json.loads(out)
        except Exception:
            # Nødutvei: pakk råstreng så vi i alle fall returnerer et dict
            out = {"raw": out}

    # 3) Sørg for dict
    out = dict(out or {})

    # 4) Normaliser nøkler/typer
    # calibrated → bool
    out["calibrated"] = bool(out.get("calibrated", False))

    # cda/crr/mae → float
    out["cda"] = _to_float(out.get("cda", 0.0))
    out["crr"] = _to_float(out.get("crr", 0.0))
    out["mae"] = _to_float(out.get("mae", 0.0))

    # 5) profile → JSON-streng som representerer et objekt (helst dict)
    prof = out.get("profile")

    if isinstance(prof, dict):
        # Gjør dict → JSON-streng
        try:
            out["profile"] = json.dumps(prof, ensure_ascii=False)
        except Exception:
            out["profile"] = "{}"

    elif isinstance(prof, (str, bytes, bytearray)):
        # Sikre at strengen faktisk er gyldig JSON; hvis ikke, fall tilbake til "{}"
        try:
            _parsed = json.loads(prof)
            # Sørg for at vi returnerer en "kompakt" JSON-streng tilbake
            out["profile"] = json.dumps(_parsed, ensure_ascii=False)
        except Exception:
            out["profile"] = "{}"
    else:
        # Mangler/ukjent type → tomt objekt
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

    # Nå er out["profile"] garantert å være en gyldig JSON-streng; last til dict
    try:
        out["profile"] = json.loads(out.get("profile", "{}"))
        if not isinstance(out["profile"], dict):
            # Sikre at vi får dict (ikke f.eks. en liste) for videre bruk
            out["profile"] = {}
    except Exception:
        out["profile"] = {}

    return out
