# cli/session_api.py
from __future__ import annotations

import csv
import json
import os
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime, timezone

# ── Konstanter (samme terskler som CLI) ───────────────────────────────────────
MIN_SAMPLES_FOR_CAL = 30
MIN_SPEED_SPREAD_MS = 0.8
MIN_ALT_SPAN_M = 3.0


# ── Trygge imports av kjernebindinger ─────────────────────────────────────────
try:
    from cyclegraph_core import compute_power_with_wind_json as rs_power_json
except Exception:
    rs_power_json = None

try:
    # Eksponert i core/src/lib.rs som #[pyfunction] rust_calibrate_session
    from cyclegraph_core import rust_calibrate_session as rs_calibrate
except Exception:
    rs_calibrate = None


# ── Små helpers (kopiert/tilpasset fra CLI) ──────────────────────────────────
def _parse_time_to_seconds(x) -> Optional[float]:
    """ISO8601 ('2023-09-01T12:00:00Z') eller tall → sekunder (float)."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        pass
    try:
        return float(s)
    except Exception:
        return None


def _to_float_loose(v: Any) -> Tuple[Optional[float], bool]:
    """Robust tall-parsing. Returnerer (verdi, hadde_prosent_tegn)."""
    if v is None:
        return None, False
    if isinstance(v, (int, float)):
        return float(v), False
    s = str(v).strip().lower()
    had_pct = "%" in s or "pct" in s
    s = s.replace(",", ".")
    # trekk ut første tall
    num = ""
    hit = False
    for ch in s:
        if ch.isdigit() or ch in ".+-eE":
            num += ch
            hit = True
        elif hit:
            break
    if not hit:
        return None, had_pct
    try:
        return float(num), had_pct
    except Exception:
        return None, had_pct


def _read_csv_for_core_samples(csv_path: str) -> List[dict]:
    """Les CSV og bygg core-samples med v_ms/altitude_m/lat/lon/device_watts."""
    with open(csv_path, "r", encoding="utf-8") as f:
        head = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(head)
            rdr = csv.reader(f, dialect)
        except Exception:
            rdr = csv.reader(f)
        rows = list(rdr)

    if not rows:
        return []

    header = [str(h).strip().lower() for h in rows[0]]
    idx = {h: i for i, h in enumerate(header)}

    def pick(row, *keys):
        for k in keys:
            if k in idx and idx[k] < len(row):
                return row[idx[k]]
        return None

    samples: List[dict] = []
    for r in rows[1:]:
        t_raw = pick(r, "timestamp", "t", "time", "time_s", "sec", "seconds")
        lat_raw = pick(r, "latitude", "lat")
        lon_raw = pick(r, "longitude", "lon", "lng")
        v_raw = pick(r, "speed", "v_ms", "speed_ms", "velocity")
        a_raw = pick(r, "altitude", "altitude_m", "elev", "elevation")
        w_raw = pick(r, "device_watts", "watts", "power", "pwr")

        t_sec = _parse_time_to_seconds(t_raw)
        v, _ = _to_float_loose(v_raw)
        a, _ = _to_float_loose(a_raw)
        lat, _ = _to_float_loose(lat_raw)
        lon, _ = _to_float_loose(lon_raw)
        dw, _ = _to_float_loose(w_raw)

        if v is not None and v > 50.0:  # km/t → m/s
            v = v / 3.6

        samples.append({
            "t": float(t_sec) if t_sec is not None else 0.0,
            "v_ms": float(v) if v is not None else 0.0,
            "altitude_m": float(a) if a is not None else 0.0,
            "heading_deg": 0.0,
            "moving": bool((v or 0.0) > 0.1),
            "device_watts": float(dw) if dw is not None else None,
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lon) if lon is not None else None,
        })

    return samples


def _fallback_extract_for_calibration(csv_path: str) -> Tuple[List[float], List[float], List[float]]:
    """Leser CSV direkte for å hente watts/speed/altitude/time når samples mangler disse."""
    POWER_KEYS = ("watts", "watt", "power", "power_w", "pwr")
    SPEED_KEYS = ("v_ms", "speed_ms", "speed", "velocity")
    ALTI_KEYS  = ("altitude_m", "altitude", "elev", "elevation")
    GRAD_KEYS  = ("gradient", "grade", "slope", "incline", "gradient_pct")
    TIME_KEYS  = ("t", "time_s", "time", "sec", "seconds", "timestamp")

    with open(csv_path, "r", encoding="utf-8") as f:
        head = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(head)
            rdr = csv.reader(f, dialect)
        except Exception:
            rdr = csv.reader(f)
        rows = list(rdr)

    watts_arr: List[float] = []
    speed_arr: List[float] = []
    alti_arr:  List[float] = []

    if not rows:
        return watts_arr, speed_arr, alti_arr

    header = [str(h).strip().lower() for h in rows[0]]
    idx = {h: i for i, h in enumerate(header)}

    def pick_idx(cands: tuple[str, ...]) -> Optional[int]:
        for k in cands:
            if k in idx:
                return idx[k]
        return None

    i_w = pick_idx(POWER_KEYS)
    i_v = pick_idx(SPEED_KEYS)
    i_a = pick_idx(ALTI_KEYS)
    i_g = pick_idx(GRAD_KEYS)
    i_t = pick_idx(TIME_KEYS)

    prev_t = None
    cur_alt = 0.0

    for r in rows[1:]:
        w = v = a = g = t = None
        if i_w is not None and i_w < len(r): w, _ = _to_float_loose(r[i_w])
        if i_v is not None and i_v < len(r): v, _ = _to_float_loose(r[i_v])
        if i_a is not None and i_a < len(r): a, _ = _to_float_loose(r[i_a])
        if i_g is not None and i_g < len(r): g, g_is_pct = _to_float_loose(r[i_g])
        else: g_is_pct = False
        if i_t is not None and i_t < len(r): t = _parse_time_to_seconds(r[i_t])

        if v is not None and v > 50:  # trolig km/t
            v = v / 3.6

        # 1) Altitude: integrér hvis vi har gradient, ellers 'carry forward' siste høyde
        if a is None:
            if g is not None and v is not None:
                # Integrer gradient → ny høyde
                if g_is_pct or abs(g) <= 30.0:
                    slope = g / 100.0
                else:
                    slope = g
                dt = None
                if isinstance(t, (int, float)) and prev_t is not None:
                    dt = max(0.0, float(t) - float(prev_t))
                if dt is None or dt == 0.0:
                    dt = 1.0
                cur_alt += slope * float(v) * dt
                a = cur_alt
            else:
                # Ingen altitude og ingen gradient → bruk forrige høyde (flat antakelse)
                a = cur_alt
        else:
            cur_alt = float(a)

        prev_t = t if isinstance(t, (int, float)) else prev_t

        # 2) Watts: hvis mangler, fyll inn et forsiktig estimat basert på fart (for å unngå dropp)
        if w is None and v is not None:
            rho = 1.225
            cda = 0.30
            crr = 0.005
            mass = 78.0
            w_est = 0.5 * rho * cda * float(v) ** 3 + mass * 9.80665 * crr * float(v)
            w = w_est

        # 3) Append når vi har de tre (etter utfylling)
        if (w is not None) and (v is not None) and (a is not None):
            watts_arr.append(float(w))
            speed_arr.append(float(v))
            alti_arr.append(float(a))

    return watts_arr, speed_arr, alti_arr


def _load_weather(weather_path: Optional[str]) -> Dict[str, float]:
    w = {
        "wind_ms": 0.0,
        "wind_dir_deg": 0.0,
        "air_temp_c": 15.0,
        "air_pressure_hpa": 1013.0,
    }
    if weather_path and os.path.exists(weather_path):
        try:
            with open(weather_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            w.update({k: float(data.get(k, w[k])) for k in w.keys()})
        except Exception:
            pass
    return w


def _build_profile_for_cal() -> Dict[str, Any]:
    # En enkel, deterministisk profil (kan overstyres av kalibrering)
    return {
        "total_weight": 78.0,
        "bike_type": "road",
        "crr": None,
        "cda": None,
        "calibrated": False,
        "calibration_mae": None,
        "estimat": True,
    }


# ── Offentlig API ─────────────────────────────────────────────────────────────
def analyze_session(input_path: str, weather_path: str | None = None, calibrate: bool = True) -> dict:
    """
    Analyser en CSV-økt og returner resultat som dict:
    {
      "watts": [...],
      "v_rel": [...],
      "wind_rel": [...],
      "calibrated": "Ja" | "Nei",
      "status": "OK" | "LIMITED" | ...
      "mode": "outdoor" | "indoor"
    }
    """
    if rs_power_json is None:
        raise ImportError("cyclegraph_core.compute_power_with_wind_json mangler (bygg core med --features python).")

    # 1) Les data
    core_samples = _read_csv_for_core_samples(input_path)
    weather = _load_weather(weather_path)
    profile = _build_profile_for_cal()

    # Sett mode ut fra GPS-tilstedeværelse
    has_gps = any((s.get("latitude") is not None and s.get("longitude") is not None) for s in core_samples)
    mode = "outdoor" if has_gps else "indoor"

    # 2) (Valgfri) kalibrering – forsiktig, deterministisk
    status = None
    if calibrate and rs_calibrate is not None:
        watts_arr, speed_arr, alti_arr = _fallback_extract_for_calibration(input_path)

        ok_len = len(watts_arr) >= MIN_SAMPLES_FOR_CAL and len(speed_arr) == len(alti_arr) == len(watts_arr)
        v_spread = (max(speed_arr) - min(speed_arr)) if speed_arr else 0.0
        alt_span = (max(alti_arr) - min(alti_arr)) if alti_arr else 0.0
        ok_var = v_spread >= MIN_SPEED_SPREAD_MS or alt_span >= MIN_ALT_SPAN_M

        if ok_len and ok_var:
            try:
                cal = rs_calibrate(watts_arr, speed_arr, alti_arr, json.dumps(profile), json.dumps(weather))
                # cal er et Python-dict (PyO3 → PyDict)
                profile["calibrated"] = bool(cal.get("calibrated"))
                profile["cda"] = float(cal.get("cda")) if cal.get("cda") is not None else None
                profile["crr"] = float(cal.get("crr")) if cal.get("crr") is not None else None
                profile["calibration_mae"] = float(cal.get("mae")) if cal.get("mae") is not None else None
                profile["estimat"] = False
                # Ved vellykket kalibrering nuller vi reason/status-flaggs
                if profile["calibrated"]:
                    status = None
            except Exception:
                # Hvis kal feiler, beholder vi defaults – men ikke hard fail
                status = status or "LIMITED"
        else:
            status = "LIMITED"

    # 3) Beregn kraft/vind/v_rel via kjerne
    power_json = rs_power_json(
        json.dumps(core_samples, ensure_ascii=False),
        json.dumps(profile, ensure_ascii=False),
        json.dumps(weather, ensure_ascii=False),
    )
    power_obj = json.loads(power_json) if isinstance(power_json, str) else power_json
    watts = power_obj.get("watts") or []
    wind_rel = power_obj.get("wind_rel") or []
    v_rel = power_obj.get("v_rel") or []

    # 4) Konstruer retur (enkelt og deterministisk)
    ret = {
        "watts": watts,
        "v_rel": v_rel,
        "wind_rel": wind_rel,
        "calibrated": "Ja" if profile.get("calibrated") else "Nei",
        "status": status or "OK",
        "mode": mode,
    }
    return ret