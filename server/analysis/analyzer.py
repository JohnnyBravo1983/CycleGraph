# server/analysis/analyzer.py
from __future__ import annotations
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from .calibration15 import compute_estimated_error_and_hint

RHO_STD = 1.225   # kg/m3 (Trinn 3: vær AV)
G = 9.80665
V_REF = 9.5       # m/s (≈34.2 km/t)
P_MISC = 8.0      # drivverk/annet

@dataclass
class SeriesSnapshot:
    mean_power: Optional[float] = None  # kan hentes fra persistert serie om tilgjengelig

def compute_profile_sensitive_metrics(
    profile: Dict[str, Any],
    series: Union[SeriesSnapshot, Dict[str, Any]],
    no_weather: bool = True
) -> Dict[str, float]:
    CdA = float(profile["CdA"])
    Crr = float(profile["Crr"])
    Wkg = float(profile["weight_kg"])

    rho = RHO_STD                 # vær av i Trinn 3
    v = V_REF

    drag_watt = 0.5 * rho * CdA * (v ** 3)
    rolling_watt = Crr * Wkg * G * v
    total_watt = drag_watt + rolling_watt + P_MISC

    # Hent mean_power uavhengig av type
    if isinstance(series, SeriesSnapshot):
        mean_power = series.mean_power
    else:
        mean_power = series.get("mean_power")

    baseline = mean_power if (mean_power or 0) > 0 else total_watt
    precision_watt = 0.9 * total_watt + 0.1 * baseline  # stabil, men profil-sensitiv

    precision_watt_ci = max(5.0, 0.05 * precision_watt) # konservativ inntil robust CI finnes
    aero_fraction = drag_watt / max(1e-6, total_watt)

    m = {
        "precision_watt": precision_watt,
        "precision_watt_ci": precision_watt_ci,
        "total_watt": total_watt,
        "drag_watt": drag_watt,
        "rolling_watt": rolling_watt,
        "aero_fraction": aero_fraction,
    }

    # --- Trinn 15: Heuristisk presisjonsindikator ---
    # Finn et "weather-ish" objekt i series eller i aggregert resultat hvis det speiles der.
    weather_obj = None
    if isinstance(series, dict):
        weather_obj = series.get("weather") or series.get("weather_used") or series.get("weather_applied")

    est_range, hint, _compl = compute_estimated_error_and_hint(profile, weather_obj or {})
    # Legg to nye nøkler i metrics (kontraktsutvidelse, bakoverkompatibel)
    m["estimated_error_pct_range"] = est_range  # f.eks. [6.0, 8.0]
    m["precision_quality_hint"] = hint          # "normal" | "windy" | "wet" | "unsupported"
    print("[ANALYZER-DEBUG] metrics keys before return:", list(m.keys()))

    return m

def analyze_series(
    sid: str,
    profile: Dict[str, Any],
    force_recompute: bool,
    no_weather: bool,
    persisted: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ignored_persist = False
    if force_recompute:
        ignored_persist = True
        series = SeriesSnapshot(mean_power=(persisted or {}).get("mean_power"))
    else:
        series = SeriesSnapshot(mean_power=(persisted or {}).get("mean_power"))

    m = compute_profile_sensitive_metrics(profile, series, no_weather=no_weather)

    return {
        "metrics": m,
        "debug": {
            "analyzer_mode": "series",
            "force_recompute": bool(force_recompute),
            "ignored_persist": bool(ignored_persist),
            "reason": "ok",
        }
    }