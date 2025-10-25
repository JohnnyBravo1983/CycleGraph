from __future__ import annotations
from typing import Tuple, Dict, Any
import math

class WeatherError(RuntimeError):
    pass

def _std_air_density(temp_c: float, pressure_hpa: float) -> float:
    """
    Enkel ρ-beregning: ρ = p / (R * T), med p i Pa, T i K, R=287.05 J/(kg·K).
    """
    p_pa = pressure_hpa * 100.0
    t_k = temp_c + 273.15
    if t_k <= 0:
        t_k = 273.15
    return p_pa / (287.05 * t_k)

def get_weather_for_session(session: Dict[str, Any]) -> Tuple[float, float]:
    """
    Returner (wind_angle_deg, air_density_kg_per_m3) med robuste fallbacks.
    - Prøver å hente fra session['weather'] hvis tilstede.
    - Ellers bruk fornuftige defaults.
    Kaster WeatherError hvis absolutt ingenting kan bestemmes (svært usannsynlig).
    """
    w = (session.get("weather") or {}) if isinstance(session, dict) else {}
    # Forsøk fra session:
    wind_angle = w.get("wind_angle_deg")
    rho = w.get("air_density_kg_per_m3")

    # Hvis ikke satt, forsøk å beregne rho fra temp/trykk
    if rho is None:
        temp_c = w.get("temp_c")
        pressure_hpa = w.get("pressure_hpa")
        if isinstance(temp_c, (int, float)) and isinstance(pressure_hpa, (int, float)):
            try:
                rho = _std_air_density(float(temp_c), float(pressure_hpa))
            except Exception:
                rho = None

    # Defaults (trygge og realistiske)
    if wind_angle is None:
        # Uten rute/heading velger vi 30° som konservativ “litt sidevind”.
        wind_angle = 30.0
    if rho is None:
        # Sjønivå, ~15°C: ca. 1.225 kg/m³
        rho = 1.225

    # Valider
    if not (isinstance(wind_angle, (int, float)) and isinstance(rho, (int, float))):
        raise WeatherError("Ugyldige værverdier")
    if math.isnan(wind_angle) or math.isnan(rho):
        raise WeatherError("NaN i værverdier")
    if not (0.0 <= float(wind_angle) <= 180.0):
        raise WeatherError("wind_angle_deg utenfor [0,180]")
    if not (0.9 <= float(rho) <= 1.5):  # veldig brede grenser
        raise WeatherError("air_density_kg_per_m3 utenfor [0.9,1.5]")

    return float(wind_angle), float(rho)
