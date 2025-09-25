# -*- coding: utf-8 -*-
"""
CycleGraph CLI
- Subcommand 'efficiency': dispatch via parser -> efficiency.py
- Subcommand 'session'   : NP/IF/VI/Pa:Hr/W/beat/CGS + batch/trend + baseline
- --calibrate: valgfri kalibrering mot powermeter
- --weather: path til værfil (JSON) som brukes i kalibrering
- --indoor : kjør indoor pipeline uten GPS (device_watts-policy)

TRINN 3 (Sprint 6): Strukturerte JSON-logger
- Logger som JSON på stderr med felter: level, step, duration_ms (+ev. extras)
- Nivåstyring via --log-level (debug/info/warning) eller miljøvariabel LOG_LEVEL
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Flyttet: bruker config.load_cfg for å unngå sirkulærimport
from .config import load_cfg  # noqa: F401
# NB: selve session-kjøringen ligger i cli/session.py (cmd_session)

# (Valgfritt) andre CLI-avhengigheter
from cli.weather_client_mock import WeatherClient  # noqa: F401  (hvis ikke brukt, kan fjernes)
from cli.formatters.strava_publish import PublishPieces, build_publish_texts  # noqa: F401
from cli.strava_client import StravaClient  # noqa: F401

# Rust-funksjon for kalibrering (valgfri, fail-safe import)
try:
    from cyclegraph_core import calibrate_session as rust_calibrate_session  # type: ignore
except Exception:
    rust_calibrate_session = None  # kjør uten kalibrering hvis ikke eksponert

# Vi trenger å lese samples hvis --calibrate brukes
try:
    from cli.io import read_session_csv  # type: ignore
except Exception:
    read_session_csv = None  # pylint: disable=invalid-name


# ─────────────────────────────────────────────────────────────
# TRINN 3: Strukturerte logger (enkelt JSON-logger på stderr)
# ─────────────────────────────────────────────────────────────
_LEVELS = {"debug": 10, "info": 20, "warning": 30}

def _norm_level(s: Optional[str]) -> str:
    if not s:
        return "info"
    s2 = str(s).strip().lower()
    return s2 if s2 in _LEVELS else "info"

class JsonLogger:
    def __init__(self, level: str = "info") -> None:
        self.level_name = _norm_level(level)
        self.level = _LEVELS[self.level_name]

    def _emit(self, lvl_name: str, **fields: Any) -> None:
        if _LEVELS[lvl_name] < self.level:
            return
        rec = {"level": lvl_name.upper()}
        for k, v in fields.items():
            if v is None:
                continue
            try:
                json.dumps(v)
                rec[k] = v
            except Exception:
                rec[k] = str(v)
        print(json.dumps(rec, ensure_ascii=False), file=sys.stderr)

    def debug(self, step: str, duration_ms: Optional[int] = None, **kw: Any) -> None:
        self._emit("debug", step=step, duration_ms=duration_ms, **kw)

    def info(self, step: str, duration_ms: Optional[int] = None, **kw: Any) -> None:
        self._emit("info", step=step, duration_ms=duration_ms, **kw)

    def warning(self, step: str, msg: str, **kw: Any) -> None:
        self._emit("warning", step=step, message=msg, **kw)

_LOG: Optional[JsonLogger] = None

def _init_logger_from_args_env(args: argparse.Namespace) -> JsonLogger:
    cli_lvl = getattr(args, "log_level", None)
    env_lvl = os.environ.get("LOG_LEVEL")
    level = _norm_level(cli_lvl) if cli_lvl else (_norm_level(env_lvl) if env_lvl else "info")
    return JsonLogger(level=level)

@contextmanager
def _timed(step: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dur_ms = int((time.perf_counter() - t0) * 1000.0)
        if _LOG:
            _LOG.debug(step=step, duration_ms=dur_ms)

def _log_warn(step: str, msg: str) -> None:
    if _LOG:
        _LOG.warning(step=step, msg=msg)

def _log_info(step: str, **kw: Any) -> None:
    if _LOG:
        _LOG.info(step=step, **kw)


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

def write_report(outdir: str, sid: str, report: Dict[str, Any], fmt: str):
    os.makedirs(outdir, exist_ok=True)

    # ----------------- S5: avledede felt før serialisering -----------------
    # 1) Fallback: hent wind_rel fra et enkelt sample om tilgjengelig
    sample = report.get("sample")
    if isinstance(sample, dict) and "wind_rel" not in report:
        report = dict(report)  # kopier for å ikke mutere referanse
        report["wind_rel"] = sample.get("wind_rel", None)

    # 2) Mapp calibrated (bool -> "Ja"/"Nei")
    calibrated_val = report.get("calibrated")
    if isinstance(calibrated_val, bool):
        if report.get("calibrated") != ("Ja" if calibrated_val else "Nei"):
            report = dict(report)
            report["calibrated"] = "Ja" if calibrated_val else "Nei"

    # 3) Sett status fra puls (avg_hr → fallback avg_pulse)
    if "status" not in report:
        hr = report.get("avg_hr")
        if hr is None:
            hr = report.get("avg_pulse")
        if isinstance(hr, (int, float)):
            report = dict(report)
            report["status"] = "OK" if hr < 160 else ("Høy puls" if hr > 180 else "Lav")

    # 4) S5 defaults: garanter at nøklene finnes (for tester/CLI)
    report.setdefault("watts", [])      # <<— viktig for testen
    report.setdefault("wind_rel", [])   # <<— viktig for testen
    # ----------------------------------------------------------------------

    # Berik rapporten med nye felter hvis de finnes i data
    enriched = {
        "session_id": report.get("session_id"),
        "duration_min": report.get("duration_min"),
        "duration_sec": report.get("duration_sec"),
        "avg_power": report.get("avg_power"),
        "avg_hr": report.get("avg_hr"),
        "avg_watt": report.get("avg_watt"),
        "avg_pulse": report.get("avg_pulse"),
        "np": report.get("np"),
        "np_watt": report.get("np_watt"),
        "if": report.get("if"),
        "vi": report.get("vi"),
        "pa_hr_pct": report.get("pa_hr_pct"),
        "w_per_beat": report.get("w_per_beat"),
        "efficiency": report.get("efficiency"),
        "ftp_estimate": report.get("ftp_estimate"),
        "hr_zone_dist": report.get("hr_zone_dist"),
        "calibrated": report.get("calibrated"),
        "cda": report.get("cda"),
        "crr": report.get("crr"),
        "mae": report.get("mae"),
        "reason": report.get("reason"),
        "bike_type": report.get("bike_type"),
        "weight": report.get("weight"),
        "mode": report.get("mode"),
        "status": report.get("status"),

        # ---- S5: vind/effekt arrays ----
        "watts": report.get("watts"),
        "wind_rel": report.get("wind_rel"),
        "v_rel": report.get("v_rel"),

        # scorer
        "scores.intensity": report.get("scores", {}).get("intensity"),
        "scores.duration": report.get("scores", {}).get("duration"),
        "scores.quality": report.get("scores", {}).get("quality"),
        "scores.cgs": report.get("scores", {}).get("cgs"),
    }

    # Fjern None-verdier, men behold tomme lister (de er gyldige)
    enriched = {k: v for k, v in enriched.items() if v is not None}

    # Skriv JSON
    if fmt in ("json", "both"):
        p = os.path.join(outdir, f"{sid}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)

    # Skriv CSV
    if fmt in ("csv", "both"):
        p = os.path.join(outdir, f"{sid}.csv")
        fields = list(enriched.keys())
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerow(enriched)

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
    from cli.formatters.strava_publish import PublishPieces, build_publish_texts  # local import
    from cli.strava_client import StravaClient  # local import
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


# -----------------------------
# Kalibrering helper (Python-side)
# (Historisk – beholdt for bakoverkompatibilitet)
# -----------------------------
def _run_calibration_from_args(args: argparse.Namespace) -> int:
    if rust_calibrate_session is None:
        print("⚠️ Kalibrering ikke tilgjengelig (rust_calibrate_session ikke eksponert).")
        return 3
    if read_session_csv is None:
        print("⚠️ Kan ikke lese samples (read_session_csv mangler).")
        return 3

    paths = sorted(glob.glob(args.input))
    if not paths:
        print(f"Ingen filer for pattern: {args.input}", file=sys.stderr)
        return 2

    # Les kun første fil for kalibrering (enkelt)
    samples = read_session_csv(paths[0], debug=getattr(args, "debug", False))
    if not samples:
        print(f"ADVARSEL: {paths[0]} har ingen gyldige samples.", file=sys.stderr)
        return 2

    # Plukk ut watts/hr
    POWER_KEYS = ("watts", "watt", "power", "power_w", "pwr")
    HR_KEYS    = ("hr", "heartrate", "heart_rate", "bpm", "pulse")

    def norm_keys(d: dict) -> dict:
        return {(str(k).lower().strip() if k is not None else ""): v for k, v in d.items()}

    valid = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        sn = norm_keys(s)
        pw = next((sn[k] for k in POWER_KEYS if k in sn and sn[k] not in (None, "")), None)
        hr = next((sn[k] for k in HR_KEYS if k in sn and sn[k] not in (None, "")), None)
        if pw is None or hr is None:
            continue
        try:
            valid.append((float(pw), float(hr)))
        except (TypeError, ValueError):
            continue

    if not valid:
        print("⚠️ Fant ingen gyldige watt/hr-par for kalibrering.")
        return 3

    watts = [w for w, _ in valid]
    pulses = [h for _, h in valid]

    # Kjør rust-kalibrering; API kan variere – vi håndterer dict/JSON/string
    try:
        result = rust_calibrate_session(watts, pulses)  # type: ignore
    except Exception as e:
        print(f"Kalibrering feilet i Rust: {e}")
        return 3

    try:
        data = json.loads(result) if isinstance(result, str) else result
    except Exception:
        data = result

    mae = data.get("mae") if isinstance(data, dict) else None
    print(f"✅ Kalibrering OK. MAE={mae}" if mae is not None else "✅ Kalibrering OK.")
    # Her kunne vi evt. lagret til profile.json via Python-siden også
    return 0


def main() -> None:
    # Importer parser her for å unngå sirkulær-import
    with _timed("build_parser"):
        from cli.parser import build_parser
        parser = build_parser()

    # ⚙️ Legg til --weather, --indoor og --log-level på 'session'-subparseren dersom de ikke finnes
    with _timed("ensure_session_flags"):
        try:
            for a in parser._actions:  # type: ignore[attr-defined]
                if isinstance(a, argparse._SubParsersAction):
                    if "session" in a.choices:
                        sp = a.choices["session"]

                        def _ensure_flag(flag: str, **kwargs):
                            already = any(
                                hasattr(ac, "option_strings") and (flag in getattr(ac, "option_strings", []))
                                for ac in getattr(sp, "_actions", [])
                            )
                            if not already:
                                sp.add_argument(flag, **kwargs)

                        # --weather PATH
                        _ensure_flag(
                            "--weather",
                            type=str,
                            help="Path to weather JSON file with wind/temp/pressure",
                        )

                        # --indoor (bool flag)
                        _ensure_flag(
                            "--indoor",
                            action="store_true",
                            help="Run indoor pipeline without GPS (device_watts policy)",
                        )

                        # --log-level (debug/info/warning) -> brukes også i cli/session.py
                        _ensure_flag(
                            "--log-level",
                            type=str,
                            choices=["debug", "info", "warning"],
                            help="Structured log level (overrides LOG_LEVEL env).",
                        )
                    break
        except Exception:
            # Ikke-kritisk; hvis vi ikke får lagt til her, kjører resten som før
            pass

    with _timed("parse_args"):
        args = parser.parse_args()

    # Init logger (bruk CLI > env > default)
    global _LOG
    _LOG = _init_logger_from_args_env(args)
    _log_info("startup", component="analyze.py", subcommand=getattr(args, "command", None), log_level=_LOG.level_name)

    # (Valgfritt) vis enkel profilstatus (beholdt fra tidligere)
    with _timed("load_profile"):
        try:
            from cli.profile import load_profile as _lp
            profile = _lp()
            profile["estimat"] = False
        except Exception:
            profile = {"bike_type": "unknown", "weight": None, "crr": None, "estimat": True}
    print("Profil:", profile)

    # Viktig: IKKE kjør noen kalibrering her. Håndteres i cli/session.py.

    # Kjør valgt subkommando (f.eks. cmd_session i cli/session.py)
    with _timed("dispatch_subcommand"):
        rc = args.func(args) if hasattr(args, "func") else (parser.print_help() or 2)

    _log_info("done", rc=rc)
    sys.exit(rc)


if __name__ == "__main__":
    main()