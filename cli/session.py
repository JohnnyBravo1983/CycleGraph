# cli/session.py
from __future__ import annotations

def _ensure_cli_fields(d: dict) -> dict:
    """Garanter at watts/wind_rel finnes, map calibrated til Ja/Nei, og sett status."""
    if not isinstance(d, dict):
        return d
    r = dict(d)

    # watts / wind_rel (hent fra samples hvis mulig)
    if "watts" not in r:
        if isinstance(r.get("samples"), list):
            r["watts"] = [s.get("watts") for s in r["samples"]]
        else:
            r["watts"] = []
    if "wind_rel" not in r:
        if isinstance(r.get("samples"), list):
            r["wind_rel"] = [s.get("wind_rel") for s in r["samples"]]
        else:
            r["wind_rel"] = []

    # v_rel (valgfritt)
    if "v_rel" not in r and isinstance(r.get("samples"), list):
        r["v_rel"] = [s.get("v_rel") for s in r["samples"]]

    # calibrated: bool -> "Ja"/"Nei" (default "Nei" hvis mangler/ukjent)
    cal_val = r.get("calibrated")
    if isinstance(cal_val, bool):
        r["calibrated"] = "Ja" if cal_val else "Nei"
    elif isinstance(cal_val, str):
        pass
    else:
        prof = r.get("profile")
        if isinstance(prof, dict) and isinstance(prof.get("calibrated"), bool):
            r["calibrated"] = "Ja" if prof["calibrated"] else "Nei"
        else:
            r["calibrated"] = "Nei"

    # status fra puls (default "OK" hvis vi ikke har puls)
    if "status" not in r:
        hr = r.get("avg_hr", r.get("avg_pulse"))
        if isinstance(hr, (int, float)):
            r["status"] = "OK" if hr < 160 else ("Høy puls" if hr > 180 else "Lav")
        else:
            r["status"] = "OK"

    return r

import argparse
import glob
import sys
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple

# ── Konstanter ────────────────────────────────────────────────────────────────
MIN_SAMPLES_FOR_CAL = 15          # min. antall punkter for å prøve kalibrering
MIN_SPEED_SPREAD_MS = 0.8         # krever litt variasjon i fart
MIN_ALT_SPAN_M      = 3.0         # eller litt høydeforskjell

# ── Konfig (ingen circular) ───────────────────────────────────────────────────
from .config import load_cfg

# ── Lesing av samples ─────────────────────────────────────────────────────────
from .io import read_session_csv  # type: ignore

# ── Publisering/badges/Strava: robuste imports ────────────────────────────────
# Badges kan mangle → definer no-op fallback
try:
    from .badges import maybe_apply_big_engine_badge  # type: ignore
except Exception:
    def maybe_apply_big_engine_badge(_report: Dict[str, Any]) -> None:
        return

try:
    from cyclegraph_core import compute_power_with_wind_json as rs_power_json
except Exception:
    rs_power_json = None

# Strava-klient kan mangle → trygg fallback-stub
try:
    from .strava_client import StravaClient  # type: ignore
except Exception:
    class StravaClient:  # fallback stub
        def __init__(self, lang: str = "no") -> None:
            self.lang = lang
        def publish_to_strava(self, _pieces, dry_run: bool = True):
            # gjør ingenting i fallback
            return (None, "skipped")

# build_publish_texts ligger i formatters/strava_publish
try:
    from .formatters.strava_publish import build_publish_texts
except Exception:  # fallback hvis kjørt uten pakke-kontekst
    from cli.formatters.strava_publish import build_publish_texts  # type: ignore

# ─────────────────────────────────────────────────────────────
# Lokale helpers (slik at vi ikke trenger cli.ids/cli.metrics)
# ─────────────────────────────────────────────────────────────
def session_id_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]

def infer_duration_sec(samples: List[Dict[str, Any]]) -> float:
    if not samples:
        return 0.0
    ts_raw = [s.get("t") for s in samples if s.get("t") is not None]
    if not ts_raw:
        return 0.0

    # 1) Prøv numerisk tid (sekunder)
    try:
        ts_num = [float(t) for t in ts_raw]
        return float(max(ts_num) - min(ts_num) + 1.0)
    except Exception:
        pass

    # 2) Prøv ISO8601 timestamps
    def _parse_iso(x: str):
        x = str(x).strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(x)
        except Exception:
            return None

    ts_dt = [d for d in (_parse_iso(t) for t in ts_raw) if d is not None]
    if len(ts_dt) >= 2:
        delta = (max(ts_dt) - min(ts_dt)).total_seconds()
        # anta ~1 Hz sampling; +1s for å inkludere endepunktene hvis jevnt samplet
        return float(delta + 1.0)

    # 3) Fallback: lengden (≈ 1 Hz)
    return float(len(ts_raw))

def estimate_ftp_20min95(samples: List[Dict[str, Any]]) -> float:
    if not samples:
        return 0.0
    S = sorted([s for s in samples if isinstance(s.get("t"), (int, float))], key=lambda x: x["t"])
    if not S:
        return 0.0
    t = [s["t"] for s in S]
    w = [float(s["watts"]) if s.get("watts") is not None else 0.0 for s in S]

    left = 0
    pow_sum = 0.0
    best_avg = 0.0
    for right in range(len(S)):
        pow_sum += w[right]
        while t[right] - t[left] + 1.0 > 1200.0 and left < right:
            pow_sum -= w[left]
            left += 1
        window_sec = t[right] - t[left] + 1.0
        if window_sec >= 1195.0:
            avg = pow_sum / max(1.0, (right - left + 1))
            if avg > best_avg:
                best_avg = avg
    return float(best_avg * 0.95)

# ── NYE HELPERE (TRINN D) – plasseres her ─────────────────────────────────────
def _parse_time_to_seconds(x) -> float | None:
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

def _normalize_sample_for_core(s: dict) -> dict:
    """Map CSV-sample til kjernens Sample-format."""
    t = _parse_time_to_seconds(s.get("t") or s.get("time") or s.get("timestamp"))

    v = s.get("v_ms")
    if v is None:
        v = s.get("speed") or s.get("speed_ms") or s.get("velocity")
    try:
        v = float(v) if v is not None else 0.0
    except Exception:
        v = 0.0
    if v > 50.0:  # km/t → m/s
        v = v / 3.6

    alt = s.get("altitude_m")
    if alt is None:
        alt = s.get("altitude") or s.get("elev") or s.get("elevation")
    try:
        alt = float(alt) if alt is not None else 0.0
    except Exception:
        alt = 0.0

    lat = s.get("latitude")
    lon = s.get("longitude")
    try:
        lat = float(lat) if lat is not None else None
    except Exception:
        lat = None
    try:
        lon = float(lon) if lon is not None else None
    except Exception:
        lon = None

    dw = s.get("device_watts")
    try:
        dw = float(dw) if dw is not None else None
    except Exception:
        dw = None

    return {
        "t": float(t) if t is not None else 0.0,
        "v_ms": max(0.0, v),
        "altitude_m": alt,
        "heading_deg": float(s.get("heading_deg") or 0.0),
        "moving": bool(v > 0.1),
        "device_watts": dw,
        "latitude": lat,
        "longitude": lon,
    }

def _read_csv_for_core_samples(csv_path: str, debug: bool = False) -> list[dict]:
    """Les CSV direkte og bygg core-samples med v_ms/altitude_m/lat/lon/device_watts."""
    import csv

    def _to_float(v):
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            s = str(v).strip().replace(",", ".")
            try:
                return float(s)
            except Exception:
                return None

    def _t_to_sec(x):
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

    samples: list[dict] = []
    for r in rows[1:]:
        t_raw  = pick(r, "timestamp", "t", "time", "time_s", "sec", "seconds")
        lat    = _to_float(pick(r, "latitude", "lat"))
        lon    = _to_float(pick(r, "longitude", "lon", "lng"))
        speed  = _to_float(pick(r, "speed", "v_ms", "speed_ms", "velocity"))
        alt    = _to_float(pick(r, "altitude", "altitude_m", "elev", "elevation"))
        dw     = _to_float(pick(r, "device_watts", "watts", "power", "pwr"))

        if speed is not None and speed > 50.0:  # km/t → m/s
            speed = speed / 3.6

        t_sec = _t_to_sec(t_raw)
        s = {
            "t": float(t_sec) if t_sec is not None else 0.0,
            "v_ms": float(speed) if speed is not None else 0.0,
            "altitude_m": float(alt) if alt is not None else 0.0,
            "heading_deg": 0.0,
            "moving": bool((speed or 0.0) > 0.1),
            "device_watts": float(dw) if dw is not None else None,
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lon) if lon is not None else None,
        }
        samples.append(s)

    if debug:
        print(f"DEBUG CSV-FALLBACK: built {len(samples)} core samples", file=sys.stderr)
        if samples:
            print(f"DEBUG CSV-FALLBACK: first={samples[0]}", file=sys.stderr)
    return samples
# ── SLUTT: nye helpere ────────────────────────────────────────────────────────

DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")

def _parse_date_from_sid_or_name(name: str):
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group("date"), "%Y-%m-%d")
    except Exception:
        return None

def _median(vals: list[float] | List[float]):
    v = sorted([x for x in vals if isinstance(x, (int, float))])
    if not v:
        return None
    n = len(v)
    return float(v[n // 2]) if n % 2 == 1 else float((v[n // 2 - 1] + v[n // 2]) / 2.0)

def load_baseline_wpb(history_dir: str, cur_sid: str, cur_dur_min: float):
    now = datetime.utcnow()
    window_start = now - timedelta(days=28)
    files = sorted(glob.glob(os.path.join(history_dir, "*.json")))
    candidates: List[float] = []
    for p in files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                r = json.load(f)
        except Exception:
            continue
        sid_name = r.get("session_id") or os.path.basename(p)
        dt = _parse_date_from_sid_or_name(sid_name) or _parse_date_from_sid_or_name(os.path.basename(p))
        if not dt:
            try:
                dt = datetime.utcfromtimestamp(os.path.getmtime(p))
            except Exception:
                dt = None
        if dt and dt < window_start:
            continue
        wpb = r.get("w_per_beat")
        dmin = r.get("duration_min")
        if not isinstance(wpb, (int, float)) or not isinstance(dmin, (int, float)):
            continue
        lo, hi = cur_dur_min * 0.75, cur_dur_min * 1.25
        if lo <= dmin <= hi:
            candidates.append(float(wpb))
    return _median(candidates)

def apply_trend_last3(reports: List[Dict[str, Any]]) -> None:
    scores = [r.get("scores", {}).get("cgs") for r in reports]
    for i in range(len(reports)):
        last3 = [scores[j] for j in range(max(0, i - 3), i) if isinstance(scores[j], (int, float))]
        if len(last3) >= 3:
            avg3 = sum(last3) / 3.0
            cur = reports[i].get("scores", {}).get("cgs")
            if isinstance(cur, (int, float)) and avg3 > 0:
                delta = ((cur - avg3) / avg3) * 100.0
                reports[i].setdefault("trend", {})
                reports[i]["trend"]["cgs_last3_avg"] = round(avg3, 2)
                reports[i]["trend"]["cgs_delta_vs_last3"] = round(delta, 2)

# ─────────────────────────────────────────────────────────────
# write_* helpers lokalt (unngår import fra annen modul)
# ─────────────────────────────────────────────────────────────
def write_report(outdir: str, sid: str, report: Dict[str, Any], fmt: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    if fmt in ("json", "both"):
        p = os.path.join(outdir, f"{sid}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if fmt in ("csv", "both"):
        import csv
        p = os.path.join(outdir, f"{sid}.csv")
        fields = [
            "session_id", "duration_min", "avg_power", "avg_hr", "np", "if", "vi", "pa_hr_pct",
            "w_per_beat", "scores.intensity", "scores.duration", "scores.quality", "scores.cgs"
        ]
        row = {
            "session_id": report.get("session_id"),
            "duration_min": report.get("duration_min"),
            "avg_power": report.get("avg_power"),
            "avg_hr": report.get("avg_hr"),
            "np": report.get("np"),
            "if": report.get("if"),
            "vi": report.get("vi"),
            "pa_hr_pct": report.get("pa_hr_pct"),
            "w_per_beat": report.get("w_per_beat"),
            "scores.intensity": report.get("scores", {}).get("intensity"),
            "scores.duration": report.get("scores", {}).get("duration"),
            "scores.quality": report.get("scores", {}).get("quality"),
            "scores.cgs": report.get("scores", {}).get("cgs"),
        }
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerow(row)

def write_history_copy(history_dir: str, report: Dict[str, Any]) -> None:
    os.makedirs(history_dir, exist_ok=True)
    sid = report.get("session_id") or "session"
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(history_dir, f"{sid}_{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────────────────────
# Rust-bro lokalt (unngår egen bridge-modul)
# ─────────────────────────────────────────────────────────────
try:
    from cyclegraph_core import analyze_session as rust_analyze_session
except Exception:
    rust_analyze_session = None

def _analyze_session_bridge(samples, meta, cfg):
    if rust_analyze_session is None:
        raise ImportError(
            "Ingen analyze_session i cyclegraph_core. "
            "Bygg i core/: 'maturin develop --release'."
        )

    # Aksepter synonymer (lowercase + strip)
    POWER_KEYS = ("watts", "watt", "power", "power_w", "pwr", "device_watts")
    HR_KEYS    = ("hr", "heartrate", "heart_rate", "bpm", "pulse")

    def norm_keys(d: dict) -> dict:
        # lower/strip keys
        return { (str(k).lower().strip() if k is not None else ""): v for k, v in d.items() }

    def pick(d: dict, keys: tuple[str, ...]):
        for k in keys:
            if k in d and d[k] is not None and d[k] != "":
                return d[k]
        return None

    try:
        valid = []
        for s in samples:
            if not isinstance(s, dict):
                continue
            sn = norm_keys(s)

            pw = pick(sn, POWER_KEYS)
            hr = pick(sn, HR_KEYS)
            if pw is None or hr is None:
                continue

            try:
                pwf = float(pw)
                hrf = float(hr)
            except (TypeError, ValueError):
                continue

            valid.append((pwf, hrf))

        watts = [pw for pw, _ in valid]
        pulses = [hr for _, hr in valid]
    except Exception as e:
        raise ValueError(f"Feil ved uthenting av watt/puls: {e}")

    # Debug: vis noen keys fra første sample hvis mismatch
    if not pulses or len(watts) != len(pulses):
        example_keys = []
        if samples and isinstance(samples[0], dict):
            example_keys = list(norm_keys(samples[0]).keys())
        print(
            "DEBUG: samples={} valid={} len(watts)={} len(hr)={} "
            "POWER_KEYS={} HR_KEYS={} example_first_keys={}".format(
                len(samples), len(valid), len(watts), len(pulses),
                POWER_KEYS, HR_KEYS, example_keys
            ),
            file=sys.stderr
        )

    try:
        # NB: Rust-funksjonen aksepterer Option[bool] for device_watts; vi sender None
        result = rust_analyze_session(watts, pulses, None)
        print(f"DEBUG: rust_analyze_session output = {result}", file=sys.stderr)
        return result
    except TypeError:
        # Eldre binding som bare tar (watts, pulses)
        result = rust_analyze_session(watts, pulses)  # type: ignore
        print(f"DEBUG: rust_analyze_session output = {result}", file=sys.stderr)
        return result
    except ValueError as e:
        print("⚠️ Ingen effekt-data registrert – enkelte metrikker begrenset.", file=sys.stderr)
        print(f"DEBUG: rust_analyze_session feilet med: {e}", file=sys.stderr)
        avg_p = (sum(pulses) / len(pulses)) if pulses else None
        return {"mode": "hr_only", "status": "LIMITED", "avg_pulse": avg_p}

# ─────────────────────────────────────────────────────────────
# Robust tall-parsing for kalibrering + CSV-fallback
# ─────────────────────────────────────────────────────────────
NUM_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")

def _parse_float_loose(v: Any) -> Tuple[float | None, bool]:
    """
    Returnerer (verdi, hadde_prosent_tegn).
    Tåler '25 km/h', '7,3', '5%', '  12.0  ' osv.
    """
    if v is None:
        return None, False
    if isinstance(v, (int, float)):
        return float(v), False
    s = str(v).strip().lower()
    had_pct = "%" in s or "pct" in s
    s = s.replace(",", ".")
    m = NUM_RE.search(s)
    if not m:
        return None, had_pct
    try:
        return float(m.group(0)), had_pct
    except Exception:
        return None, had_pct

def _fallback_extract_for_calibration(csv_path: str) -> Tuple[List[float], List[float], List[float]]:
    """Leser CSV direkte for å hente watts/speed/altitude/time når samples mangler disse."""
    import csv
    POWER_KEYS = ("watts", "watt", "power", "power_w", "pwr")
    SPEED_KEYS = ("v_ms", "speed_ms", "speed", "velocity")
    ALTI_KEYS  = ("altitude_m", "altitude", "elev", "elevation")
    GRAD_KEYS  = ("gradient", "grade", "slope", "incline", "gradient_pct")
    TIME_KEYS  = ("t", "time_s", "time", "sec", "seconds", "timestamp")

    watts_arr: List[float] = []
    speed_arr: List[float] = []
    alti_arr:  List[float] = []

    # Sniff delimiter for robusthet
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
        return watts_arr, speed_arr, alti_arr

    header = [str(h).strip().lower() for h in rows[0]]
    idx = {h: i for i, h in enumerate(header)}
    def pick_idx(cands: tuple[str, ...]) -> int | None:
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
        if i_w is not None and i_w < len(r): w, _ = _parse_float_loose(r[i_w])
        if i_v is not None and i_v < len(r): v, _ = _parse_float_loose(r[i_v])
        if i_a is not None and i_a < len(r): a, _ = _parse_float_loose(r[i_a])
        if i_g is not None and i_g < len(r): g, g_is_pct = _parse_float_loose(r[i_g])
        else: g_is_pct = False
        if i_t is not None and i_t < len(r): t, _ = _parse_float_loose(r[i_t])

        if v is not None and v > 50:  # trolig km/t → m/s
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

# ─────────────────────────────────────────────────────────────
# Profilbygging for kalibrering
# ─────────────────────────────────────────────────────────────
def _build_profile_for_cal(report: Dict[str, Any], cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    # Prøv report → cfg → lagret profil → fallback
    tw = report.get("weight") or cfg.get("total_weight") or cfg.get("weight")
    bt = report.get("bike_type") or cfg.get("bike_type")

    if tw is None or bt is None:
        # Forsøk å hente lagret profil
        try:
            try:
                from .profile import load_profile as _lp  # type: ignore
            except Exception:
                from cli.profile import load_profile as _lp  # type: ignore
            prof = _lp()
            tw = tw or prof.get("total_weight") or prof.get("weight")
            bt = bt or prof.get("bike_type")
        except Exception:
            pass

    if tw is None:
        tw = 78.0  # trygg fallback
        if getattr(args, "debug", False):
            print("DEBUG CAL: total_weight manglet – bruker fallback 78.0 kg", file=sys.stderr)

    prof = {
        "total_weight": float(tw) if isinstance(tw, (int, float)) else float(str(tw)),
        "bike_type": bt or "road",
        "crr": None,
        "cda": None,
        "calibrated": False,
        "calibration_mae": None,
        "estimat": True,
    }
    if getattr(args, "debug", False):
        print(f"DEBUG CAL: profile_for_cal={prof}", file=sys.stderr)
    return prof

def _load_weather_for_cal(args: argparse.Namespace) -> Dict[str, float]:
    """Les weather JSON fra --weather, eller bruk defaults."""
    default_w = {
        "wind_ms": 0.0,
        "wind_dir_deg": 0.0,
        "air_temp_c": 15.0,
        "air_pressure_hpa": 1013.0,
    }
    w = default_w
    if hasattr(args, "weather") and args.weather:
        try:
            with open(args.weather, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Slå sammen med defaults for å håndtere manglende felt
            w = {**default_w, **(data or {})}
        except Exception as e:
            print(f"⚠️ Klarte ikke å lese weather-fil '{args.weather}': {e}. Bruker defaults.", file=sys.stderr)
    if getattr(args, "debug", False):
        print(f"DEBUG CAL: weather_for_cal={w}", file=sys.stderr)
    return w

# ─────────────────────────────────────────────────────────────
# Kommandofunksjonen
# ─────────────────────────────────────────────────────────────
def cmd_session(args: argparse.Namespace) -> int:
    cfg = load_cfg(getattr(args, "cfg", None))
    history_dir = cfg.get("history_dir", "history")
    outdir = getattr(args, "out", "output")
    fmt = getattr(args, "format", "json")
    lang = getattr(args, "lang", "no")

    paths = sorted(glob.glob(args.input))
    if getattr(args, "debug", False):
        print("DEBUG: input filer:", paths, file=sys.stderr)
    if not paths:
        print(f"Ingen filer for pattern: {args.input}", file=sys.stderr)
        return 2

    reports: List[Dict[str, Any]] = []

    for path in paths:
        samples = read_session_csv(path, debug=getattr(args, "debug", False))
        if getattr(args, "debug", False):
            print(f"DEBUG: {path} -> {len(samples)} samples", file=sys.stderr)
        if not samples:
            print(f"ADVARSEL: {path} har ingen gyldige samples.", file=sys.stderr)
            continue

        sid = session_id_from_path(path)
        duration_sec = infer_duration_sec(samples)
        meta: Dict[str, Any] = {
            "session_id": sid,
            "duration_sec": duration_sec,
            "ftp": None,
            "hr_max": cfg.get("hr_max"),
            "start_time_utc": None,
        }

        if getattr(args, "mode", None):
            print(f"🎛️ Overstyrt modus: {args.mode}")
            meta["mode"] = args.mode
        else:
            print("Ingen overstyring – modus settes automatisk senere hvis relevant.")

        # FTP
        if getattr(args, "set_ftp", None) is not None:
            meta["ftp"] = float(args.set_ftp)
        elif getattr(args, "auto_ftp", False):
            ftp_est = estimate_ftp_20min95(samples)
            if ftp_est > 0:
                meta["ftp"] = round(ftp_est, 1)
        elif "ftp" in cfg:
            meta["ftp"] = cfg.get("ftp")

        # Kjør analyse via Rust-broen
        report_raw = _analyze_session_bridge(samples, meta, cfg)

        if isinstance(report_raw, str) and report_raw.strip() == "":
            print(f"ADVARSEL: _analyze_session_bridge returnerte tom streng for {path}", file=sys.stderr)
            continue

        try:
            report = json.loads(report_raw) if isinstance(report_raw, str) else report_raw
        except json.JSONDecodeError as e:
            print(f"ADVARSEL: Klarte ikke å parse JSON for {path}: {e}", file=sys.stderr)
            continue

        # --- Vind/kraft fra kjernen (PowerOutputs) ---
        try:
            from cyclegraph_core import compute_power_with_wind_json as rs_power_json
        except Exception:
            rs_power_json = None

        if rs_power_json is not None:
            # Normaliser fra read_session_csv
            core_samples = [_normalize_sample_for_core(s) for s in samples]

            # Hvis normaliseringen ga "tomme" data → bruk CSV-fallback (les direkte fra inputfilen)
            def _looks_empty(core: list[dict]) -> bool:
                if not core:
                    return True
                pos_ok = any((c.get("latitude") is not None and c.get("longitude") is not None) for c in core)
                speed_ok = sum(1 for c in core if (c.get("v_ms") or 0.0) > 0.2) >= max(1, len(core)//4)
                return (not pos_ok) or (not speed_ok)

            if _looks_empty(core_samples):
                if getattr(args, "debug", False):
                    print("DEBUG CORE: normalized samples look empty -> using CSV fallback", file=sys.stderr)
                core_samples = _read_csv_for_core_samples(path, debug=getattr(args, "debug", False))

            if getattr(args, "debug", False):
                print(f"DEBUG CORE: n_samples={len(core_samples)}", file=sys.stderr)
                if core_samples:
                    print(f"DEBUG CORE: first_sample={core_samples[0]}", file=sys.stderr)

            profile_for_core = {
                "total_weight": report.get("weight") or cfg.get("total_weight") or cfg.get("weight") or 78.0,
                "bike_type": report.get("bike_type") or cfg.get("bike_type") or "road",
                "crr": report.get("crr") or cfg.get("crr") or 0.005,
                "cda": report.get("cda") or cfg.get("cda") or None,
                "calibrated": bool(report.get("calibrated")) if isinstance(report.get("calibrated"), bool) else False,
                "calibration_mae": report.get("mae"),
                "estimat": True,
            }
            weather_for_core = _load_weather_for_cal(args)

            if getattr(args, "debug", False):
                print(f"DEBUG CORE: profile_for_core={profile_for_core}", file=sys.stderr)
                print(f"DEBUG CORE: weather_for_core={weather_for_core}", file=sys.stderr)

            power_json = rs_power_json(
                json.dumps(core_samples, ensure_ascii=False),
                json.dumps(profile_for_core, ensure_ascii=False),
                json.dumps(weather_for_core, ensure_ascii=False),
            )
            power_obj = json.loads(power_json) if isinstance(power_json, str) else power_json

            if getattr(args, "debug", False):
                print(f"DEBUG CORE: keys={list(power_obj.keys())}", file=sys.stderr)
                print(f"DEBUG CORE: watts_head={power_obj.get('watts', [])[:3]}", file=sys.stderr)
                print(f"DEBUG CORE: wind_head={power_obj.get('wind_rel', [])[:3]}", file=sys.stderr)
                print(f"DEBUG CORE: vrel_head={power_obj.get('v_rel', [])[:3]}", file=sys.stderr)

            for k in ("watts", "wind_rel", "v_rel"):
                v = power_obj.get(k)
                if v is not None:
                    report[k] = v

        # ── KALIBRERING (kun hvis --calibrate) ────────────────────────────────
        if getattr(args, "calibrate", False):
            POWER_KEYS = ("watts", "watt", "power", "power_w", "pwr")
            SPEED_KEYS = ("v_ms", "speed_ms", "speed", "velocity")
            ALTI_KEYS  = ("altitude_m", "altitude", "elev", "elevation")
            GRAD_KEYS  = ("gradient", "grade", "slope", "incline", "gradient_pct")
            TIME_KEYS  = ("t", "time_s", "time", "sec", "seconds", "timestamp")

            watts_arr: List[float] = []
            speed_arr: List[float] = []
            alti_arr:  List[float] = []

            prev_t = None
            cur_alt = 0.0

            for s in samples:
                if not isinstance(s, dict):
                    continue
                sn = { (str(k).lower().strip() if k is not None else ""): v for k, v in s.items() }

                def pick_val(keys: tuple[str, ...]):
                    for k in keys:
                        if k in sn and sn[k] is not None and sn[k] != "":
                            return sn[k]
                    return None

                w_raw = pick_val(POWER_KEYS)
                v_raw = pick_val(SPEED_KEYS)
                a_raw = pick_val(ALTI_KEYS)
                g_raw = pick_val(GRAD_KEYS)
                t_raw = pick_val(TIME_KEYS)

                w, _ = _parse_float_loose(w_raw)
                v, _ = _parse_float_loose(v_raw)
                a, _ = _parse_float_loose(a_raw)
                g, g_is_pct = _parse_float_loose(g_raw)
                t, _ = _parse_float_loose(t_raw)

                if v is not None and v > 50:  # trolig km/t
                    v = v / 3.6

                # hvis altitude mangler men gradient+tid+fart finnes → integrér
                if a is None and g is not None and v is not None:
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
                elif a is not None:
                    cur_alt = float(a)

                prev_t = t if isinstance(t, (int, float)) else prev_t

                if w is not None and v is not None and a is not None:
                    watts_arr.append(float(w)); speed_arr.append(float(v)); alti_arr.append(float(a))

            # Fallback: bruk CSV direkte hvis arrays er utilstrekkelige (< MIN_SAMPLES_FOR_CAL)
            if (len(watts_arr) < MIN_SAMPLES_FOR_CAL) or (len(speed_arr) < MIN_SAMPLES_FOR_CAL) or (len(alti_arr) < MIN_SAMPLES_FOR_CAL):
                fw, fv, fa = _fallback_extract_for_calibration(path)
                if len(fw) >= MIN_SAMPLES_FOR_CAL and len(fv) >= MIN_SAMPLES_FOR_CAL and len(fa) >= MIN_SAMPLES_FOR_CAL:
                   watts_arr, speed_arr, alti_arr = fw, fv, fa
                   if getattr(args, "debug", False):
                      print(f"DEBUG CAL: using CSV fallback arrays n={len(watts_arr)}", file=sys.stderr)

            if not watts_arr or not speed_arr or not alti_arr or not (len(watts_arr) == len(speed_arr) == len(alti_arr)):
                print("⚠️ Kalibrering hoppes over: mangler speed/altitude/watts med like lengder.", file=sys.stderr)
                if getattr(args, "debug", False):
                    print(f"DEBUG CAL: lens -> watts={len(watts_arr)} speed={len(speed_arr)} alti={len(alti_arr)}", file=sys.stderr)
            elif len(watts_arr) < MIN_SAMPLES_FOR_CAL:
                if getattr(args, "debug", False):
                    print(f"DEBUG CAL: too few samples for calibration (have {len(watts_arr)}, need >= {MIN_SAMPLES_FOR_CAL})", file=sys.stderr)
                report["calibrated"] = False
                report["reason"] = f"insufficient_segment(min_samples={MIN_SAMPLES_FOR_CAL}, have={len(watts_arr)})"
            else:
                # Variasjons-sjekk før kall til Rust
                try:
                    v_spread = (max(speed_arr) - min(speed_arr)) if speed_arr else 0.0
                    alt_span = (max(alti_arr) - min(alti_arr)) if alti_arr else 0.0
                except Exception:
                    v_spread, alt_span = 0.0, 0.0
                if v_spread < MIN_SPEED_SPREAD_MS and alt_span < MIN_ALT_SPAN_M:
                    report["calibrated"] = False
                    report["reason"] = f"insufficient_variation(speed_spread={v_spread:.2f} m/s, alt_span={alt_span:.1f} m)"
                    if getattr(args, "debug", False):
                        print(f"DEBUG CAL: insufficient variation → v_spread={v_spread:.2f} m/s, alt_span={alt_span:.1f} m", file=sys.stderr)
                else:
                    # Robust import av Rust-binding
                    try:
                        from .rust_bindings import calibrate_session as rs_cal
                    except Exception:
                        from cli.rust_bindings import calibrate_session as rs_cal  # type: ignore

                    profile_for_cal = _build_profile_for_cal(report, cfg, args)
                    weather_for_cal = _load_weather_for_cal(args)

                    # ekstra kvalitets-logging
                    if getattr(args, "debug", False):
                        try:
                            vmin, vmax = min(speed_arr), max(speed_arr)
                            wmin, wmax = min(watts_arr), max(watts_arr)
                            alt_span_dbg = (alti_arr[-1] - alti_arr[0]) if alti_arr else 0.0
                            print(f"DEBUG CAL: n={len(watts_arr)} v=[{vmin:.2f},{vmax:.2f}] m/s "
                                  f"watts=[{wmin:.1f},{wmax:.1f}] alt_span={alt_span_dbg:.1f} m", file=sys.stderr)
                        except Exception:
                            pass

                    try:
                        cal = rs_cal(watts_arr, speed_arr, alti_arr, profile_for_cal, weather_for_cal)

                                     # slå cal-resultater inn i report
                        for k in ("calibrated", "cda", "crr", "mae"):
                            if cal.get(k) is not None:
                                report[k] = cal[k]
                        # overskriv alltid reason, selv om None (rydder tidligere placeholder)
                        report["reason"] = cal.get("reason")

                        # --- Små oppryddinger etter kalibrering ---
                        # 1) Hvis kalibrering lykkes, null ut reason
                        if isinstance(report.get("calibrated"), bool) and report["calibrated"]:
                            report["reason"] = None
                            # Hvis vi tidligere havnet i hr_only-modus, sett modus til outdoor
                            if report.get("mode") == "hr_only":
                                report["mode"] = "outdoor"

                        # 2) Sett modus til 'outdoor' når vi faktisk bruker GPS/vind pipeline
                        if not report.get("mode"):
                            report["mode"] = "outdoor"

                        # 3) Sett status fra puls hvis mulig; ellers behold 'LIMITED'
                        if report.get("status") in (None, "LIMITED"):
                            hr = report.get("avg_hr") or report.get("avg_pulse")
                            if isinstance(hr, (int, float)):
                                report["status"] = "OK" if hr < 160 else ("Høy puls" if hr > 180 else "Lav")

                        # (Valgfritt) lagre profil.json hvis medfulgt
                        if cal.get("profile"):
                            try:
                                os.makedirs(outdir, exist_ok=True)
                                with open(os.path.join(outdir, "profile.json"), "w", encoding="utf-8") as f:
                                    f.write(cal["profile"])
                                print("✅ Lagret oppdatert profile.json fra kalibrering.", file=sys.stderr)
                            except Exception as e:
                                print(f"⚠️ Klarte ikke å lagre profile.json: {e}", file=sys.stderr)
                    except Exception as e:
                        print(f"⚠️ Kalibrering feilet: {e}", file=sys.stderr)

        # Baseline/badge/skriving
        baseline = load_baseline_wpb(history_dir, sid, report.get("duration_min", 0.0))
        if baseline is not None:
            report["w_per_beat_baseline"] = round(baseline, 4)

        maybe_apply_big_engine_badge(report)
        reports.append(report)

        # Ikke-batch
        if not getattr(args, "batch", False):
            if getattr(args, "dry_run", False):
                print(json.dumps(_ensure_cli_fields(report), ensure_ascii=False, indent=2))
                try:
                    pieces = build_publish_texts(report, lang=lang)
                    print(f"[DRY-RUN] COMMENT: {pieces.comment}")
                    print(f"[DRY-RUN] DESC: {pieces.desc_header}")
                except Exception as e:
                    print(f"[DRY-RUN] build_publish_texts feilet: {e}")
            else:
                write_report(outdir, sid, report, fmt)
                write_history_copy(history_dir, report)

            if getattr(args, "publish_to_strava", False):
                try:
                    pieces = build_publish_texts(report, lang=lang)
                    aid, status = StravaClient(lang=lang).publish_to_strava(
                        pieces, dry_run=getattr(args, "dry_run", False)
                    )
                    print(f"[STRAVA] activity_id={aid} status={status}")
                except Exception as e:
                    print(f"[STRAVA] publisering feilet: {e}")

    # Batch
    if getattr(args, "batch", False) and reports:
        if getattr(args, "with_trend", False):
            apply_trend_last3(reports)

        for r in reports:
            sid = r.get("session_id", "session")
            baseline = load_baseline_wpb(history_dir, sid, r.get("duration_min", 0.0))
            if baseline is not None:
                r["w_per_beat_baseline"] = round(baseline, 4)
            maybe_apply_big_engine_badge(r)

            if getattr(args, "dry_run", False):
                print(json.dumps(_ensure_cli_fields(r), ensure_ascii=False, indent=2))
                try:
                    pieces = build_publish_texts(r, lang=lang)
                    print(f"[DRY-RUN] COMMENT: {pieces.comment}")
                    print(f"[DRY-RUN] DESC: {pieces.desc_header}")
                except Exception as e:
                    print(f"[DRY-RUN] build_publish_texts feilet: {e}")
            else:
                write_report(outdir, sid, r, fmt)
                write_history_copy(history_dir, r)

        if getattr(args, "publish_to_strava", False):
            try:
                pieces = build_publish_texts(reports[-1], lang=lang)
                aid, status = StravaClient(lang=lang).publish_to_strava(
                    pieces, dry_run=getattr(args, "dry_run", False)
                )
                print(f"[STRAVA] activity_id={aid} status={status}")
            except Exception as e:
                print(f"[STRAVA] publisering feilet: {e}")

    return 0
