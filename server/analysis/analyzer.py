# server/analysis/analyzer.py
from typing import Dict, Any, Optional
from dataclasses import dataclass

RHO_STD = 1.225   # kg/m3 (Trinn 3: vær AV)
G = 9.80665
V_REF = 9.5       # m/s (≈34.2 km/t)
P_MISC = 8.0      # drivverk/annet

@dataclass
class SeriesSnapshot:
    mean_power: Optional[float] = None  # kan hentes fra persistert serie om tilgjengelig

def compute_profile_sensitive_metrics(
    profile: Dict[str, Any],
    series: SeriesSnapshot,
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

    baseline = series.mean_power if (series.mean_power or 0) > 0 else total_watt
    precision_watt = 0.9 * total_watt + 0.1 * baseline  # stabil, men profil-sensitiv

    precision_watt_ci = max(5.0, 0.05 * precision_watt) # konservativ inntil robust CI finnes
    aero_fraction = drag_watt / max(1e-6, total_watt)

    return {
        "precision_watt": precision_watt,
        "precision_watt_ci": precision_watt_ci,
        "total_watt": total_watt,
        "drag_watt": drag_watt,
        "rolling_watt": rolling_watt,
        "aero_fraction": aero_fraction,
    }

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
