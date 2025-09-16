# weather_metrics.py
import json
import os
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone

DEBUG_WEATHER = os.environ.get("CG_DEBUG_WEATHER") == "1"

def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        return float(s) if s else default
    except Exception:
        return default

def _get_at(seq, idx: int):
    try:
        return seq[idx]
    except Exception:
        return None

def _parse_iso(ts: str) -> Optional[datetime]:
    """Tåler 'Z', offset og naive ISO-strenger."""
    if not ts:
        return None
    s = str(ts).strip()
    try:
        # Håndter 'Z' som UTC
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except Exception:
        # Siste utvei: prøv veldig vanlig format uten sekunder
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
    return None

def _parse_start_time(st: Any) -> Optional[datetime]:
    """Tillat ISO-streng eller epoch-sekunder."""
    if st is None:
        return None
    if isinstance(st, (int, float)) and not isinstance(st, bool):
        try:
            return datetime.fromtimestamp(float(st), tz=timezone.utc)
        except Exception:
            return None
    return _parse_iso(str(st))

def _parse_weather_times(hourly: Dict[str, Any]) -> List[Optional[datetime]]:
    """Returner liste av datetime for hourly['time'] hvis mulig."""
    times = hourly.get("time") or []
    out: List[Optional[datetime]] = []
    for t in times:
        out.append(_parse_iso(str(t)) if t is not None else None)
    return out

def _nearest_index(target: datetime, candidates: List[Optional[datetime]]) -> Optional[int]:
    best_i = None
    best_dt = None
    for i, dtv in enumerate(candidates):
        if dtv is None:
            continue
        # Hvis target er naive, sammenlign som naive; hvis aware, konverter begge til UTC
        a = dtv
        b = target
        if (a.tzinfo is not None) != (b.tzinfo is not None):
            # normaliser til naive uten å endre klokkeslett
            a = a.replace(tzinfo=None)
            b = b.replace(tzinfo=None)
        diff = abs((a - b).total_seconds())
        if best_dt is None or diff < best_dt:
            best_dt = diff
            best_i = i
    return best_i

def load_weather_context(path: str,
                         idx: Optional[int] = None,
                         start_time: Optional[Any] = None,
                         *,
                         index_fallback: str = "last") -> Dict[str, float]:
    """
    Les vær-JSON og returner alltid tallverdier for:
      temperature, humidity, wind_speed, wind_direction, pressure

    Match-logikk:
      - Hvis start_time er gitt (ISO-streng eller epoch), velg nærmeste time i hourly['time'].
      - Ellers: bruk idx hvis gitt.
      - Ellers: fallback = 'last' (siste time) eller 'first' (første time).

    Debug (CG_DEBUG_WEATHER=1) logger valgt idx og timestamp.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hourly = data.get("hourly") or {}

    # Finn indeks
    chosen_idx: Optional[int] = None
    chosen_ts: Optional[str] = None

    weather_times = _parse_weather_times(hourly)
    if start_time is not None:
        st_dt = _parse_start_time(start_time)
        if st_dt is not None and weather_times:
            ni = _nearest_index(st_dt, weather_times)
            if ni is not None:
                chosen_idx = ni
                chosen_ts = (_get_at(hourly.get("time", []), ni)
                             or (weather_times[ni].isoformat() if weather_times[ni] else None))

    if chosen_idx is None:
        if idx is not None:
            chosen_idx = idx
        else:
            # Fallback: siste (default) eller første
            times_len = len(hourly.get("time", []))
            if index_fallback == "first":
                chosen_idx = 0
            else:
                chosen_idx = max(0, times_len - 1)
        chosen_ts = _get_at(hourly.get("time", []), chosen_idx)

    # Hent verdier med safe_float
    temperature = safe_float(_get_at(hourly.get("temperature_2m", [None]), chosen_idx))
    humidity = safe_float(_get_at(hourly.get("relative_humidity_2m", [None]), chosen_idx))
    wind_speed = safe_float(_get_at(hourly.get("wind_speed_10m", [None]), chosen_idx))
    wind_direction = safe_float(_get_at(hourly.get("wind_direction_10m", [None]), chosen_idx))
    pressure = safe_float(_get_at(hourly.get("surface_pressure", [None]), chosen_idx))

    ctx = {
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "pressure": pressure,
    }

    if DEBUG_WEATHER:
        print(f"[DBG] load_weather_context: idx={chosen_idx}, ts={chosen_ts}, ctx={ctx}")

    return ctx