# cli/analyze.py
# -*- coding: utf-8 -*-
"""
CycleGraph CLI
- Subcommand 'efficiency': dispatch via parser -> efficiency.py
- Subcommand 'session'   : NP/IF/VI/Pa:Hr/W/beat/CGS + batch/trend + baseline
"""

import csv
import glob
import json
import os
import re
import sys


from datetime import datetime, timedelta
from typing import List, Dict, Any
from cli.weather_client_mock import WeatherClient
from cli.formatters.strava_publish import PublishPieces, build_publish_texts
from cli.strava_client import StravaClient

# --------- Rust-kjerne ----------
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

    try:
        valid = [
            s for s in samples
            if "watts" in s and "hr" in s and s["watts"] is not None and s["hr"] is not None
        ]
        watts = [s["watts"] for s in valid]
        pulses = [s["hr"] for s in valid]
    except Exception as e:
        raise ValueError(f"Feil ved uthenting av watt/puls: {e}")

    try:
        result = rust_analyze_session(watts, pulses)
        print(f"DEBUG: rust_analyze_session output = {result}", file=sys.stderr)
        return result
    except ValueError as e:
        print("⚠️ Ingen effekt-data registrert – enkelte metrikker begrenset.", file=sys.stderr)
        print(f"DEBUG: rust_analyze_session feilet med: {e}", file=sys.stderr)
        avg_p = (sum(pulses) / len(pulses)) if pulses else None
        return {"mode": "hr_only", "status": "LIMITED", "avg_pulse": avg_p}

# ---------- Hjelpere (session) ----------
def infer_duration_sec(samples: List[Dict[str, Any]]) -> float:
    if not samples:
        return 0.0
    ts = [s.get("t") for s in samples if s.get("t") is not None]
    if not ts:
        return 0.0
    return float(max(ts) - min(ts) + 1.0)

def estimate_ftp_20min95(samples: List[Dict[str, Any]]) -> float:
    if not samples:
        return 0.0
    S = sorted([s for s in samples if isinstance(s.get("t"), (int, float))], key=lambda x: x["t"])
    if not S:
        return 0.0
    t = [s["t"] for s in S]
    w = [float(s["watts"]) if s.get("watts") is not None else 0.0 for s in S]

    import math
    left = 0
    pow_sum = 0.0
    best_avg = 0.0
    for right in range(len(S)):
        pow_sum += w[right]
        while t[right] - t[left] + 1.0 > 1200.0 and left < right:
            pow_sum -= w[left]; left += 1
        window_sec = t[right] - t[left] + 1.0
        if window_sec >= 1195.0:
            avg = pow_sum / max(1.0, (right - left + 1))
            if avg > best_avg:
                best_avg = avg
    return float(best_avg * 0.95)

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

def session_id_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]

def load_cfg(path: str) -> Dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_report(outdir: str, sid: str, report: Dict[str, Any], fmt: str):
    os.makedirs(outdir, exist_ok=True)
    if fmt in ("json", "both"):
        p = os.path.join(outdir, f"{sid}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if fmt in ("csv", "both"):
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
            w.writeheader(); w.writerow(row)

def write_history_copy(history_dir: str, report: Dict[str, Any]):
    os.makedirs(history_dir, exist_ok=True)
    sid = report.get("session_id") or "session"
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(history_dir, f"{sid}_{date_str}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"ADVARSEL: Klarte ikke å skrive history-fil: {path} ({e})", file=sys.stderr)

def publish_to_strava_stub(report: Dict[str, Any], dry_run: bool):
    lang = (report.get("args", {}) or {}).get("lang", "no")
    try:
        res = build_publish_texts(report, lang=lang)
        if hasattr(res, "comment"):
            comment_text = getattr(res, "comment", "") or ""
            desc_header_text = getattr(res, "desc_header", "") or ""
            desc_body_text = getattr(res, "desc_body", "") or ""
        else:
            comment_text, desc_header_text, desc_body_text = res
    except Exception as e:
        print(f"[strava] build_publish_texts feilet: {e}")
        return None

    pieces = PublishPieces(comment=comment_text, desc_header=desc_header_text, desc_body=desc_body_text)
    try:
        aid, status = StravaClient(lang=lang).publish_to_strava(pieces, dry_run=dry_run)
        print(f"[strava] activity_id={aid} status={status}")
        return aid, status
    except Exception as e:
        print(f"[strava] publisering feilet: {e}")
        return None

# -----------------------------
# Baseline (28d) + helpers
# -----------------------------
DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")

def parse_date_from_sid_or_name(name: str):
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group("date"), "%Y-%m-%d")
    except Exception:
        return None

def median(vals: list[float]):
    v = sorted([x for x in vals if isinstance(x, (int, float))])
    if not v:
        return None
    n = len(v)
    return float(v[n // 2]) if n % 2 == 1 else float((v[n // 2 - 1] + v[n // 2]) / 2.0)

def load_baseline_wpb(history_dir: str, cur_sid: str, cur_dur_min: float):
    now = datetime.utcnow()
    window_start = now - timedelta(days=28)
    files = sorted(glob.glob(os.path.join(history_dir, "*.json")))
    candidates = []
    for p in files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                r = json.load(f)
        except Exception:
            continue
        sid_name = r.get("session_id") or os.path.basename(p)
        dt = parse_date_from_sid_or_name(sid_name) or parse_date_from_sid_or_name(os.path.basename(p))
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
    return median(candidates)

def load_profile():
    """Prøv å bruke eksisterende loader om den finnes, ellers fallback til tom profil med estimat."""
    try:
        from cli.profile import load_profile as _lp
        profile = _lp()
        profile["estimat"] = False
        return profile
    except Exception:
        return {
            "bike_type": "unknown",
            "weight": None,
            "crr": None,
            "estimat": True
        }

def main() -> None:
    # Viktig: importer parser her for å unngå sirkulær import
    from cli.parser import build_parser

    parser = build_parser()
    args = parser.parse_args()

    profile = load_profile()
    print("Profil:", profile)

    rc = args.func(args) if hasattr(args, "func") else (parser.print_help() or 2)
    sys.exit(rc)

if __name__ == "__main__":
    main()