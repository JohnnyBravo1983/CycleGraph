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

# Standardbibliotek
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
from typing import Any, Dict, List, Optional

# Prosjekt/importer
from cyclegraph.pipeline import persist_and_maybe_publish

# Unngå sirkulærimport – bruk relativ import til config
try:
    from .config import load_cfg  # type: ignore  # noqa: F401
except Exception:
    # Fallback: forsøk absolutt sti om modul layout varierer i noen miljøer
    from cli.config import load_cfg  # type: ignore  # noqa: F401

# Valgfrie CLI-avhengigheter (grei å ha som try/except)
try:
    from cli.weather_client_mock import WeatherClient  # noqa: F401
except Exception:
    WeatherClient = None  # type: ignore

try:
    from cli.formatters.strava_publish import PublishPieces, build_publish_texts  # noqa: F401
except Exception:
    PublishPieces = None  # type: ignore
    def build_publish_texts(*_args, **_kwargs):  # type: ignore
        return None

try:
    from cli.strava_client import StravaClient  # noqa: F401
except Exception:
    StravaClient = None  # type: ignore

# Vi trenger å lese samples hvis --calibrate brukes
try:
    from cli.io import read_session_csv  # type: ignore
except Exception:
    try:
        from .io import read_session_csv  # type: ignore
    except Exception:
        read_session_csv = None  # type: ignore

# Helper for å standardisere schema/avg_hr for CLI-path
try:
    from .session_api import _ensure_schema_and_avg_hr  # type: ignore  # noqa: F401
except Exception:
    try:
        from cli.session_api import _ensure_schema_and_avg_hr  # type: ignore  # noqa: F401
    except Exception:
        def _ensure_schema_and_avg_hr(report: dict) -> dict:
            r = dict(report) if report else {}
            r.setdefault("schema_version", "1.1")
            if "avg_hr" not in r:
                ap = r.get("avg_pulse")
                if isinstance(ap, (int, float)):
                    r["avg_hr"] = float(ap)
                else:
                    metrics = r.get("metrics") or {}
                    m_avg = metrics.get("avg_hr")
                    if isinstance(m_avg, (int, float)):
                        r["avg_hr"] = float(m_avg)
                    else:
                        hr_series = r.get("hr_series") or r.get("hr") or metrics.get("hr_series")
                        if hr_series:
                            vals = [float(x) for x in hr_series if x is not None]
                            r["avg_hr"] = (sum(vals) / len(vals)) if vals else 0.0
                        else:
                            r["avg_hr"] = 0.0
            return r

# Rust-binding: kalibrering (5 args) → dict
try:
    # Eksponert fra cyclegraph_core (PyO3): rust_calibrate_session(watts, speed_ms, altitude_m, profile, weather) -> dict
    from cyclegraph_core import rust_calibrate_session  # type: ignore
except Exception:
    rust_calibrate_session = None  # type: ignore


# ─────────────────────────────────────────────────────────────
# S6/S7: Felles normalisering + emitter for CLI-stdout JSON
# ─────────────────────────────────────────────────────────────
def _normalize_for_cli(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Idempotent normalisering for CLI-stdout-banen:
      - Sikrer avg_hr + øvrige felter via _ensure_schema_and_avg_hr
      - Tilstedeværelse: status, wind_rel, v_rel
      - Calibrated/Reason-regel
      - Lås schema_version = "1.1" (string)
    """
    r: Dict[str, Any] = _ensure_schema_and_avg_hr(dict(report) if report else {})

    # Kontrakt: presence (tolerant typer for wind_rel/v_rel)
    r.setdefault("status", "ok")
    r.setdefault("wind_rel", None)  # kan være tall ELLER liste -> ikke cast
    r.setdefault("v_rel", None)

    # Calibrated/Reason-regel (ingen duplikat)
    if r.get("calibrated") is True:
        r.pop("reason", None)
    else:
        r.setdefault("reason", "calibration_context_missing")

    # Lås schema_version som streng
    r["schema_version"] = "0.7.0"
    return r


def emit_cli_json(report: Dict[str, Any]) -> None:
    """
    S7: Normaliser rapport for CLI-stdout og print nøyaktig én JSON-linje til STDOUT.
    All logging skal gå via logging-handler på STDERR (ikke her).
    """
    out = _normalize_for_cli(report)
    # separators hindrer ekstra whitespace -> én linje
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
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

    # --- S7: Normaliser rapporten (schema_version + avg_hr) før videre beriking ---
    report = _ensure_schema_and_avg_hr(report)

    # ----------------- S5: avledede felt før serialisering -----------------
    # 1) Fallback: hent wind_rel fra et enkelt sample om tilgjengelig
    sample = report.get("sample")
    if isinstance(sample, dict) and "wind_rel" not in report:
        report = dict(report)  # kopier for å ikke mutere referanse
        report["wind_rel"] = sample.get("wind_rel", None)

    # 2) Mapp calibrated (bool -> "Ja"/"Nei") for legacy-kompatibilitet i filrapport
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

        # --- S7: schema version for fil-JSON også ---
        "schema_version": report.get("schema_version"),
    }

    # Fjern None-verdier, men behold tomme lister (de er gyldige)
    enriched = {k: v for k, v in enriched.items() if v is not None or isinstance(v, list)}

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
    """
    Skriver en historikkfil for rapporten (for revisjon/sporbarhet) og
    kaller backend-hooken som persisterer session + (valgfri) publisering til Strava.
    Hooken er no-op safe dersom aktivitet/PW mangler eller toggle/token er av.
    """
    os.makedirs(history_dir, exist_ok=True)

    # --- identitet + payload for backend ---------------------------------------
    sid = report.get("session_id") or "session"
    session_payload = {
        "session_id": sid,
        # begge varianter støttes; hvis ingen finnes → no-op i hooken
        "strava_activity_id": report.get("strava_activity_id") or report.get("activity_id"),
        "precision_watt": report.get("precision_watt"),
        "precision_watt_ci": report.get("precision_watt_ci"),
    }
    # ---------------------------------------------------------------------------

    # Skriv historikk (best effort, uavhengig av backend-persist/publish)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(history_dir, f"{sid}_{date_str}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"ADVARSEL: Klarte ikke å skrive history-fil: {path} ({e})", file=sys.stderr)

    # --- CycleGraph backend: persist + (valgfri) auto-publish til Strava --------
    persist_and_maybe_publish(sid, session_payload)
    # --------------------------------------------------------------------------- #


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
        print(f"[strava] build_publish_texts feilet: {e}", file=sys.stderr)
        return None

    pieces = PublishPieces(comment=comment_text, desc_header=desc_header_text, desc_body=desc_body_text)
    try:
        aid, status = StravaClient(lang=lang).publish_to_strava(pieces, dry_run=dry_run)
        print(f"[strava] activity_id={aid} status={status}", file=sys.stderr)
        return aid, status
    except Exception as e:
        print(f"[strava] publisering feilet: {e}", file=sys.stderr)
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
    """
    Kjører enkel kalibrering fra en CSV (første fil i args.input).
    Bruker cyclegraph_core.rust_calibrate_session(watts, speed_ms, altitude_m, profile, weather) -> dict.
    Ingen json.loads på resultater; alt er allerede Python-objekter.
    """
    if rust_calibrate_session is None:
        print("⚠️ Kalibrering ikke tilgjengelig (rust_calibrate_session ikke eksponert).", file=sys.stderr)
        return 3

    if read_session_csv is None:
        print("⚠️ Kan ikke lese samples (read_session_csv mangler).", file=sys.stderr)
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

    # Plukk ut serier vi trenger
    POWER_KEYS = ("watts", "watt", "power", "power_w", "pwr")
    SPEED_KEYS = ("speed_ms", "speed", "v", "velocity")
    ALTI_KEYS  = ("altitude_m", "altitude", "alti", "elev_m", "elevation")

    def norm_keys(d: dict) -> dict:
        return {(str(k).lower().strip() if k is not None else ""): v for k, v in d.items()}

    watts: list[float] = []
    speed_ms: list[float] = []
    altitude_m: list[float] = []

    for s in samples:
        if not isinstance(s, dict):
            continue
        sn = norm_keys(s)

        def pick(keys: tuple[str, ...]):
            for k in keys:
                if k in sn and sn[k] not in (None, ""):
                    return sn[k]
            return None

        pw = pick(POWER_KEYS)
        sp = pick(SPEED_KEYS)
        al = pick(ALTI_KEYS)

        if pw is None or sp is None or al is None:
            continue
        try:
            watts.append(float(pw))
            speed_ms.append(float(sp))
            altitude_m.append(float(al))
        except (TypeError, ValueError):
            continue

    if not watts or not speed_ms or not altitude_m:
        print("⚠️ Fant ikke komplette (watt, speed_ms, altitude_m) serier for kalibrering.", file=sys.stderr)
        return 3

    # Minimal profil + vær (du kan senere koble til ekte profil/weather)
    profile: dict[str, object] = {
        "total_weight": 85.0,
        "bike_type": "road",
        "crr": None,
        "cda": None,
        "calibrated": False,
        "calibration_mae": None,
        "estimat": True,
    }
    weather: dict[str, object] = {
        "wind_ms": 0.0,
        "wind_dir_deg": 0.0,
        "air_temp_c": 15.0,
        "air_pressure_hpa": 1013.0,
    }

    # Kjør Rust-kalibrering: returnerer dict
    try:
        result = rust_calibrate_session(watts, speed_ms, altitude_m, profile, weather)  # type: ignore[arg-type]
    except Exception as e:
        print(f"Kalibrering feilet i Rust: {e}", file=sys.stderr)
        return 3

    if not isinstance(result, dict):
        print(f"Uventet returtype fra rust_calibrate_session: {type(result)}", file=sys.stderr)
        return 3

    # result inneholder: cda, crr, mae, calibrated, profile (dict)
    mae = result.get("mae")
    calibrated = result.get("calibrated")
    prof = result.get("profile")

    # IKKE json.loads her – prof er allerede dict
    if isinstance(prof, dict):
        pass  # her kan du evt. skrive prof til fil senere

    msg_bits = []
    if isinstance(mae, (int, float)):
        msg_bits.append(f"MAE={mae}")
    if isinstance(calibrated, bool):
        msg_bits.append(f"calibrated={calibrated}")
    print("✅ Kalibrering OK. " + ", ".join(msg_bits) if msg_bits else "✅ Kalibrering OK.", file=sys.stderr)

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

    # (Valgfritt) vis enkel profilstatus på STDERR (ikke STDOUT)
    with _timed("load_profile"):
        try:
            from cli.profile import load_profile as _lp
            profile = _lp()
            profile["estimat"] = False
        except Exception:
            profile = {"bike_type": "unknown", "weight": None, "crr": None, "estimat": True}
    _log_info("profile", profile=profile)

    # Viktig: IKKE kjør noen kalibrering her. Håndteres i cli/session.py.

    # Kjør valgt subkommando (f.eks. cmd_session i cli/session.py)
    with _timed("dispatch_subcommand"):
        rc = args.func(args) if hasattr(args, "func") else (parser.print_help() or 2)

    _log_info("done", rc=rc)
    sys.exit(rc)


if __name__ == "__main__":
    main()