from __future__ import annotations
import json
from typing import Any, Dict, List

try:
    from cyclegraph_core import rust_calibrate_session as _rs_cal
except Exception:
    _rs_cal = None

def calibrate_session(
    watts: List[float],
    speed_ms: List[float],
    altitude_m: List[float],
    profile: Dict[str, Any],
    weather: Dict[str, Any],
) -> Dict[str, Any]:
    if _rs_cal is None:
        raise RuntimeError(
            "cyclegraph_core.rust_calibrate_session ikke tilgjengelig. "
            "Har du kjørt `maturin develop --release -F python`?"
        )

    prof_json = json.dumps(profile or {})
    weat_json = json.dumps(weather or {})
    out = _rs_cal(watts, speed_ms, altitude_m, prof_json, weat_json)  # PyO3-dict

    # Konverter eksplisitt til vanlig dict
    return {
        "calibrated": out.get("calibrated"),
        "cda": out.get("cda"),
        "crr": out.get("crr"),
        "mae": out.get("mae"),
        "reason": out.get("reason"),
        # serialisert profil (JSON) for lagring:
        "profile": out.get("profile"),
    }