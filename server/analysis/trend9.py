from __future__ import annotations
import json, os, csv, re
from pathlib import Path
from typing import Dict, Any, Iterable, List, Tuple, Optional, Union
import pandas as pd

# Obligatoriske metrikker vi ønsker inn i analysen
REQUIRED_METRICS = ["precision_watt", "drag_watt", "rolling_watt", "calibration_mae"]
# Gruppér på profilversjon og værkilde
GROUP_COLS = ["profile_version", "weather_source"]

# Feltnavn vi aksepterer for heart rate i samples
HR_KEYS = ("hr", "heartrate", "heart_rate", "bpm")
# Feltnavn for per-sample precision (om vi noen gang logger det per sample)
PW_KEYS = ("precision_watt", "pw", "precision")

def _as_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _pick(d: Dict[str, Any], *keys):
    for k in keys:
        if k in d:
            return d[k]
    return None

def _load_json(path: Path):
    """
    Les JSON med støtte for både UTF-8 og UTF-8 med BOM (Windows PowerShell skriver ofte BOM).
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return None

def _extract_id_from_filename(name: str) -> Optional[str]:
    """
    Idiotsikker id-uttak uten regex: fjern kjent prefiks og .json-suffiks.
    """
    lower = name.lower()
    if lower.startswith("result_") and lower.endswith(".json"):
        return name[len("result_") : -5]
    if lower.startswith("session_") and lower.endswith(".json"):
        return name[len("session_") : -5]
    return None

def _mean(vals: List[float]) -> Optional[float]:
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return float(sum(vals) / len(vals))

def _avg_hr_from_session(session_rec: Optional[Dict[str, Any]]) -> Optional[float]:
    """
    Finn gjennomsnittlig HR fra session-samples, filtrert til moving=True.
    Godtar feltnavn: hr, heartrate, heart_rate, bpm.
    """
    try:
        if not isinstance(session_rec, dict):
            return None
        samples = session_rec.get("samples")
        if not isinstance(samples, list) or not samples:
            return None
        hrs: List[float] = []
        for s in samples:
            if not isinstance(s, dict):
                continue
            if not s.get("moving"):
                continue  # kun HR i bevegelse
            hr_val = None
            for k in HR_KEYS:
                if k in s:
                    hr_val = _as_float(s.get(k))
                    break
            if hr_val is not None:
                hrs.append(hr_val)
        return _mean(hrs)
    except Exception:
        return None

def _canon_from_result_and_session(
    result_rec: Dict[str, Any], session_rec: Optional[Dict[str, Any]], record_path: str
) -> Dict[str, Any]:
    """
    Bygg en kanonisk rad pr ride fra result_*.json (+ valgfri session_*.json).
    """
    rec = result_rec or {}
    metrics = rec.get("metrics") if isinstance(rec.get("metrics"), dict) else {}

    precision = _as_float(_pick(metrics, "precision_watt", "precision"))
    drag = _as_float(_pick(metrics, "drag_watt"))
    rolling = _as_float(_pick(metrics, "rolling_watt"))
    mae = _as_float(_pick(metrics, "calibration_mae"))

    # weather_source: toppnivå -> metrics.weather_source -> fallback
    weather_source = _pick(rec, "weather_source", "ws")
    if isinstance(weather_source, dict):
        weather_source = weather_source.get("name") or weather_source.get("source")
    if weather_source is None:
        wm = rec.get("metrics")
        if isinstance(wm, dict):
            weather_source = wm.get("weather_source")
    if weather_source is None:
        weather_source = "unknown"

    # profile_version: toppnivå -> profile_used.profile_version -> fallback
    profile_version = _pick(rec, "profile_version")
    if not profile_version and isinstance(rec.get("profile_used"), dict):
        profile_version = rec["profile_used"].get("profile_version")
    if not profile_version:
        profile_version = "unknown"

    # device: toppnivå -> profile_used.device -> default "strava"
    device = _pick(rec, "device")
    if device is None and isinstance(rec.get("profile_used"), dict):
        device = rec["profile_used"].get("device")
    if device is None:
        device = "strava"

    # avg_watt: hvis ikke samples finnes, fall tilbake til metrics.total_watt -> precision_watt
    avg_watt = None
    w_per_beat = None

    # Prøv først å lese precision_watt per sample (hvis vi en dag logger det)
    per_sample_pw: List[float] = []
    if isinstance(session_rec, dict):
        samples = session_rec.get("samples")
        if isinstance(samples, list) and samples:
            for s in samples:
                if not isinstance(s, dict):
                    continue
                val = None
                for pk in PW_KEYS:
                    if pk in s:
                        val = _as_float(s.get(pk))
                        break
                if val is not None:
                    per_sample_pw.append(val)

    if per_sample_pw:
        avg_watt = _mean(per_sample_pw)

    if avg_watt is None:
        tw = _as_float(_pick(metrics, "total_watt"))
        if tw is not None:
            avg_watt = tw
        elif precision is not None:
            avg_watt = precision

    # HR: beregn gjennomsnittlig HR fra moving-samples
    avg_hr = _avg_hr_from_session(session_rec)

    # w_per_beat: definert som precision_watt (ride-nivå) delt på avg_hr
    if precision is not None and avg_hr is not None and avg_hr > 0:
        w_per_beat = precision / avg_hr
    elif avg_watt is not None and avg_hr is not None and avg_hr > 0:
        # fallback – om precision mangler, bruk avg_watt (mindre presist)
        w_per_beat = avg_watt / avg_hr

    return {
        "profile_version": str(profile_version),
        "weather_source": str(weather_source),
        "device": str(device or "unknown"),
        "precision_watt": precision,
        "drag_watt": drag,
        "rolling_watt": rolling,
        "calibration_mae": mae,
        "avg_watt": _as_float(avg_watt),
        "avg_hr": _as_float(avg_hr),
        "w_per_beat": _as_float(w_per_beat),
        "_record_path": record_path,
    }

def _walk_results_and_sessions(log_dir: Path) -> Iterable[Dict[str, Any]]:
    """
    Robust: finn result_*.json og match mot session_*.json via os.walk (case-insensitive).
    """
    log_dir = Path(log_dir)
    found: Dict[str, Dict[str, Optional[Path]]] = {}
    for dirpath, _, filenames in os.walk(str(log_dir)):
        for name in filenames:
            if not name.lower().endswith(".json"):
                continue
            rid = _extract_id_from_filename(name)
            if not rid:
                continue
            pair = found.setdefault(rid, {"result": None, "session": None})
            lower = name.lower()
            full = Path(dirpath) / name
            if lower.startswith("result_"):
                pair["result"] = full
            elif lower.startswith("session_"):
                pair["session"] = full

    for rid, pair in found.items():
        rpath = pair.get("result")
        if not rpath:
            continue
        spath = pair.get("session")
        result_rec = _load_json(rpath) if rpath and rpath.exists() else None
        session_rec = _load_json(spath) if spath and spath.exists() else None
        if isinstance(result_rec, dict):
            yield _canon_from_result_and_session(result_rec, session_rec, str(rpath))

def _iter_csv_records(log_dir: Path) -> Iterable[Dict[str, Any]]:
    """
    Tillat innlesing av tidligere CSV-logger (ikke T8 pivot), hvis de inneholder precision_watt.
    """
    for dirpath, _, filenames in os.walk(str(log_dir)):
        for name in filenames:
            if not name.lower().endswith(".csv"):
                continue
            p = Path(dirpath) / name
            lname = name.lower()
            if lname.startswith("t8_") or "t8_" in lname or "trinn8" in lname:
                continue
            if "manual_sanity" in lname or "analyze" in lname or "session" in lname:
                try:
                    with p.open("r", encoding="utf-8", newline="") as fh:
                        for row in csv.DictReader(fh):
                            if "precision_watt" in row or "metrics.precision_watt" in row:
                                row["_record_path"] = str(p)
                                row.setdefault("profile_version", "unknown")
                                row.setdefault("weather_source", "unknown")
                                yield row
                except Exception:
                    continue

def collect_records(log_dir: Union[str, Path]) -> pd.DataFrame:
    log_dir = Path(log_dir)
    rows: List[Dict[str, Any]] = []
    for rec in _walk_results_and_sessions(log_dir):
        rows.append(rec)
    for rec in _iter_csv_records(log_dir):
        rows.append(rec)
    if not rows:
        return pd.DataFrame(
            columns=GROUP_COLS + REQUIRED_METRICS + ["avg_watt", "avg_hr", "w_per_beat", "device", "_record_path"]
        )
    df = pd.DataFrame(rows)
    for c in GROUP_COLS:
        if c not in df.columns:
            df[c] = "unknown"
        df[c] = df[c].fillna("unknown").astype(str)
    return df

def save_pivots(df: pd.DataFrame, out_dir: Union[str, Path]) -> List[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    metrics = ["precision_watt", "drag_watt", "rolling_watt", "avg_watt", "avg_hr", "w_per_beat", "calibration_mae"]
    for metric in metrics:
        if metric not in df.columns:
            continue
        for v in sorted(df["profile_version"].unique()):
            sdf = df.loc[df["profile_version"] == v, GROUP_COLS + [metric]].copy()
            if sdf.empty:
                continue
            piv = sdf.groupby("weather_source")[metric].agg(["mean", "std", "count"]).reset_index()
            safe_v = re.sub(r"[^A-Za-z0-9_.-]", "_", str(v))
            outp = out_dir / f"trinn9_pivot_{metric}_v{safe_v}.csv"
            piv.to_csv(outp, index=False, float_format="%.6f")
            written.append(outp)
    return written

def trend_summary(df: pd.DataFrame, out_dir: Union[str, Path]) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = ["precision_watt", "drag_watt", "rolling_watt", "avg_watt", "avg_hr", "w_per_beat", "calibration_mae"]
    outp = out_dir / "trinn9_trend_summary.csv"
    if df.empty:
        pd.DataFrame(
            columns=["profile_version"]
            + [f"{m}_mean" for m in metrics]
            + [f"{m}_std" for m in metrics]
            + [f"{m}_count" for m in metrics]
        ).to_csv(outp, index=False)
        return outp
    agg = df.groupby("profile_version")[metrics].agg(["mean", "std", "count"])
    agg.columns = ["%s_%s" % (c[0], c[1]) for c in agg.columns]
    agg.reset_index().to_csv(outp, index=False, float_format="%.6f")
    return outp

def robustness_check(df: pd.DataFrame, out_dir: Union[str, Path]) -> Tuple[bool, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    anomalies: List[Dict[str, Any]] = []
    ok = True

    # Kolonnekontroll
    for c in ["precision_watt", "drag_watt", "rolling_watt", "calibration_mae", "avg_watt"]:
        if c not in df.columns:
            anomalies.append({"kind": "missing_column", "column": c})
            ok = False

    # Nøkler
    if "profile_version" not in df.columns or df["profile_version"].isna().any():
        anomalies.append({"kind": "null_profile_version"})
        ok = False
    if "weather_source" not in df.columns or df["weather_source"].isna().any():
        anomalies.append({"kind": "null_weather_source"})
        ok = False

    # Negativverdier (bør ikke forekomme)
    for c in ["precision_watt", "drag_watt", "rolling_watt", "avg_watt", "avg_hr", "w_per_beat"]:
        if c in df.columns:
            bad = df[c].dropna().lt(0).sum()
            if bad:
                anomalies.append({"kind": "negative_values", "column": c, "count": int(bad)})
                ok = False

    outp = out_dir / "trinn9_anomalies.csv"
    (pd.DataFrame(anomalies) if anomalies else pd.DataFrame([{"kind": "none"}])).to_csv(outp, index=False)
    return ok, outp
