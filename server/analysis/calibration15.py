from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import json

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _has_value(x: Any) -> bool:
    return x is not None and x != ""

def compute_profile_completeness(profile: Dict[str, Any]) -> Tuple[int, Dict[str, bool]]:
    fields = ["rider_weight_kg", "bike_weight_kg", "tire_width_mm",
              "tire_quality", "bike_type", "cda"]
    present = {k: _has_value(profile.get(k)) for k in fields}
    pct = round(100 * sum(1 for v in present.values() if v) / len(fields))
    return pct, present

def compute_estimated_error_and_hint(
    profile: Dict[str, Any],
    weather: Dict[str, Any] | None
) -> Tuple[List[float], str, int]:
    base_error = 18.0
    bonus = 0
    bonus += 4 if _has_value(profile.get("rider_weight_kg")) else 0
    bonus += 3 if _has_value(profile.get("bike_weight_kg")) else 0
    bonus += 3 if _has_value(profile.get("tire_width_mm")) else 0
    bonus += 3 if _has_value(profile.get("tire_quality")) else 0
    bonus += 2 if _has_value(profile.get("bike_type")) else 0
    bonus += 3 if _has_value(profile.get("cda")) else 0

    center = _clamp(base_error - bonus, 2.0, 20.0)
    lo = _clamp(center - 1.0, 2.0, 20.0)
    hi = _clamp(center + 1.0, 2.0, 20.0)

    hint = "normal"
    if weather:
        try:
            wind_speed = float(weather.get("wind_ms") or weather.get("wind_speed") or 0.0)
        except Exception:
            wind_speed = 0.0
        cond = (weather.get("condition") or "").strip().lower()
        is_wet = cond in ("rain", "wet")
        if wind_speed > 4.0:
            hint = "windy"
        if is_wet:
            hint = "wet"

    completeness, _ = compute_profile_completeness(profile)
    return [round(lo, 1), round(hi, 1)], hint, completeness

def append_benchmark_candidate(
    *,
    ride_id: str,
    profile_version: str,
    calibration_mae: Optional[float],
    estimated_error_pct_range: List[Optional[float]],
    profile_completeness: int,
    has_device_data: bool,
    hint: str,
) -> bool:
    """Append én linje til logs/benchmark_candidates.jsonl når kriterier er oppfylt."""
    try:
        if not (has_device_data and (hint == "normal")):
            return False

        outdir = Path("logs")
        outdir.mkdir(parents=True, exist_ok=True)
        fp = outdir / "benchmark_candidates.jsonl"

        rec = {
            "ride_id": str(ride_id),
            "profile_version": str(profile_version or ""),
            "calibration_mae": (None if calibration_mae is None else float(calibration_mae)),
            "estimated_error_pct_range": [
                (float(estimated_error_pct_range[0]) if (len(estimated_error_pct_range) > 0 and estimated_error_pct_range[0] is not None) else None),
                (float(estimated_error_pct_range[1]) if (len(estimated_error_pct_range) > 1 and estimated_error_pct_range[1] is not None) else None),
            ],
            "profile_completeness": int(profile_completeness),
            "has_device_data": bool(has_device_data),
            "hint": str(hint),
        }

        with fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
        return True
    except Exception:
        return False
