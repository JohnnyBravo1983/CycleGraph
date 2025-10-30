# cli/session.py
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
import time
import math
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from cli.rust_bindings import rs_power_json 

import click


# --- arrays-API bridge (unngår sirkulær import ved å importere inni funksjonen)
def _arrays_analyze_call(watts, pulses, device=None):
    """
    Kaller arrays-APIet (cli.analyze_session) som har signatur (watts, hr, device_watts=None).
    Dette unngår å kalle native PyO3-funksjonen (session-API) direkte.
    """
    try:
        # Importér ved behov for å slippe sirkulær import
        from cli import analyze_session as _arrays
        return _arrays(watts, pulses, device or "powermeter")
    except Exception:
        # Siste utvei: safe fallback (no-op verdi) – resten av pipeline håndterer/ logger
        return 0.0

# Importer session_storage modulært slik at vi kan tvinge DATA_DIR ved behov
try:
    from . import session_storage as ss
except Exception:  # fallback hvis relative imports ikke fungerer i miljøet
    import cli.session_storage as ss  # type: ignore


@click.group(name="sessions", help="Arbeid med økter")
def sessions():
    """Gruppe for økt-relaterte kommandoer."""
    pass


@sessions.command("list", help="Vis siste 5 økter med PW og publish-status")
@click.option("--limit", default=5, show_default=True, type=int, help="Antall økter")
def sessions_list_cmd(limit: int):
    """
    Minimal og robust implementasjon:
    - Sikrer at DATA_DIR peker til ./data hvis ikke eksisterer
    - Leser siste rader via ss.read_last_sessions
    - Skriver tabell til stdout
    """
    # Sørg for at ss.DATA_DIR peker til en faktisk mappe (fall back til ./data)
    try:
        data_dir = ss.DATA_DIR
    except Exception:
        data_dir = Path("data")

    if not data_dir.exists():
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        ss.DATA_DIR = data_dir  # bind tilbake til modulen

    rows = ss.read_last_sessions(limit=limit)
    if not rows:
        click.echo("Ingen økter funnet.")
        return

    # header
    click.echo(
        "session_id  precision_watt  CI(low,high)  publish_state  publish_time        crr_used  CdA  reason"
    )

    for row in rows:
        m = (row.get("metrics") or {})
        pw = m.get("precision_watt")
        ci = m.get("precision_watt_ci")
        ci_txt = (
            f"{ci[0]:.1f},{ci[1]:.1f}"
            if isinstance(ci, (list, tuple)) and len(ci) == 2
            else "-"
        )
        click.echo(
            f"{row.get('session_id','-'):10}  "
            f"{(f'{pw:.1f}' if isinstance(pw,(int,float)) else '-'):>13}  "
            f"{ci_txt:>11}  "
            f"{(m.get('publish_state') or '-'):>12}  "
            f"{(m.get('publish_time') or '-'):>19}  "
            f"{(m.get('crr_used') if m.get('crr_used') is not None else '-'):>7}  "
            f"{(m.get('CdA') if m.get('CdA') is not None else '-'):>4}  "
            f"{(m.get('reason') or '-')}"
        )


# -----------------------------
# sessions analyze
# -----------------------------

def _print_json_stdout(obj: Any) -> None:
    """Skriv KUN JSON til stdout (ingen støy)."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()

def _log(msg: str, level: str = "ERROR", **fields: Any) -> None:
    """
    Strukturerte logger til stderr.
    NB: En del tester forventer disse feltene ved oppstart:
        {"level":"INFO","step":"startup","component":"analyze.py","subcommand":"session","log_level":"info"}
    """
    payload = {
        "level": level,
        **fields,
        "message": msg,
    }
    click.echo(json.dumps(payload, ensure_ascii=False), err=True)

@sessions.command("analyze", help="Analyser en økt fra fil")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    help="Sti til øktfil (JSON)",
)
@click.option(
    "--weather",
    "weather_path",
    required=False,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    help="Valgfri sti til værdata (JSON)",
)
@click.option("--no-weather", is_flag=True, default=False, help="Kjør uten værdata")
@click.option("--calibrate/--no-calibrate", default=True, help="Aktiver/deaktiver kalibrering")
def analyze_cmd(input_path: str, weather_path: Optional[str], no_weather: bool, calibrate: bool) -> None:
    """
    Kjør file-APIet (cli.session_api.analyze_session) og skriv kun JSON på stdout.
    Logger går til stderr, exit codes: 0 ved suksess, 1 ved kontrollert feil.
    """
    # Info-linje som flere tester forventer ved oppstart
    _log(
        msg="startup",
        level="INFO",
        step="startup",
        component="analyze.py",
        subcommand="session",
        log_level="info",
        input=input_path,
        weather=bool(weather_path) and not no_weather,
        calibrate=calibrate,
    )

    # no-weather overstyrer weather_path
    if no_weather:
        weather_path = None

    try:
        from .session_api import analyze_session as run  # file-API som returnerer dict
    except Exception as e:
        _log(f"Importfeil: {e}", level="ERROR", step="startup", component="analyze.py", subcommand="session")
        raise SystemExit(1)

    try:
        result = run(input_path=input_path, weather_path=weather_path, calibrate=calibrate)
        _print_json_stdout(result)
        raise SystemExit(0)
    except Exception as e:
        _log(
            f"Kjøringsfeil: {e}",
            level="ERROR",
            step="run",
            component="analyze.py",
            subcommand="session",
            input=input_path,
            weather=bool(weather_path),
            calibrate=calibrate,
        )
        raise SystemExit(1)


# ─────────────────────────────────────────────────────────────
# Global logger + wrappers (alltid tom msg, data i extra)
# Konfigurer handler/formatter/level i cmd_session()
# ─────────────────────────────────────────────────────────────
_LOG = logging.getLogger("cyclegraph.cli")

def _log(level: str, step: str, **kwargs) -> None:
    extra = {"step": step, **kwargs}
    if level == "INFO":
        _LOG.info("", extra=extra)
    elif level == "WARNING":
        _LOG.warning("", extra=extra)
    elif level == "ERROR":
        _LOG.error("", extra=extra)
    else:
        _LOG.debug("", extra=extra)

def _log_info(step: str, **kwargs) -> None:
    _log("INFO", step, **kwargs)

def _log_warn(step: str, msg: str = "", **kwargs) -> None:
    if msg:
        kwargs["msg"] = msg
    _log("WARNING", step, **kwargs)

# Unngå sirkulærimport; selve session-kjøringen ligger i denne fila (cmd_session)
from .config import load_cfg  # noqa: F401

# (Valgfritt) andre CLI-avhengigheter
from cli.weather_client_mock import WeatherClient  # noqa: F401
from cli.formatters.strava_publish import PublishPieces, build_publish_texts  # noqa: F401
from cli.strava_client import StravaClient  # noqa: F401



# Rust-funksjon for kalibrering (valgfri, fail-safe import)
try:
    from cyclegraph_core import calibrate_session as rust_calibrate_session  # type: ignore
except Exception:
    rust_calibrate_session = None

# Lese samples hvis --calibrate brukes
try:
    from cli.io import read_session_csv  # type: ignore
except Exception:
    read_session_csv = None  # pylint: disable=invalid-name

# Helper for normalisering (schema_version + avg_hr) for CLI-path
# Ryddig import med trygg fallback
try:
    from .session_api import _ensure_schema_and_avg_hr  # type: ignore  # noqa: F401
except Exception:
    try:
        from cli.session_api import _ensure_schema_and_avg_hr  # type: ignore  # noqa: F401
    except Exception:
        def _ensure_schema_and_avg_hr(report: dict) -> dict:
            """Fallback-helper hvis session_api ikke kan importeres."""
            r = dict(report) if report else {}
            # Lås semver for CLI-kontrakt
            r.setdefault("schema_version", "0.7.0")
            if "avg_hr" not in r:
                # 1) legacy avg_pulse
                ap = r.get("avg_pulse")
                if isinstance(ap, (int, float)):
                    r["avg_hr"] = float(ap)
                else:
                    # 2) metrics.avg_hr
                    metrics = r.get("metrics") or {}
                    m_avg = metrics.get("avg_hr")
                    if isinstance(m_avg, (int, float)):
                        r["avg_hr"] = float(m_avg)
                    else:
                        # 3) serier (hr/hr_series/metrics.hr_series)
                        hr_series = r.get("hr_series") or r.get("hr") or metrics.get("hr_series")
                        if hr_series:
                            vals = [float(x) for x in hr_series if x is not None]
                            r["avg_hr"] = (sum(vals) / len(vals)) if vals else 0.0
                        else:
                            # 4) siste utvei
                            r["avg_hr"] = 0.0
            return r

# ─────────────────────────────────────────────────────────────
# (resten av helperne og cmd_session følger under)

# ─────────────────────────────────────────────────────────────
# (evt. øvrige helpers/konstanter/regex etc. følger under)
# ─────────────────────────────────────────────────────────────
def _normalize_for_cli(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Idempotent normalisering for CLI-stdout-banen:
      - Sikrer avg_hr via _ensure_schema_and_avg_hr
      - Tilstedeværelse: status, wind_rel, v_rel
      - Calibrated/Reason-regel
      - Lås schema_version = "1.1.0" (semver string)
    """
    r: Dict[str, Any] = _ensure_schema_and_avg_hr(dict(report) if report else {})

    # Presence (tolerant typer for wind_rel/v_rel)
    r.setdefault("status", "ok")
    r.setdefault("wind_rel", None)  # kan være tall ELLER liste
    r.setdefault("v_rel", None)

    # Calibrated/Reason-regel (ingen duplikat)
    if r.get("calibrated") is True:
        r.pop("reason", None)
    else:
        r.setdefault("reason", "calibration_context_missing")

    # Lås schema_version som streng (semver)
    r["schema_version"] = "0.7.0"
    return r


def emit_cli_json(report: Dict[str, Any]) -> None:
    """
    Normaliser rapport for CLI-stdout og print nøyaktig én JSON-linje til STDOUT.
    All logging skal gå via logging-handler på STDERR (ikke her).
    """
    out = _normalize_for_cli(report)
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))

class JsonLogger:
    def __init__(self, level="info"):
        self.level_name = level
    def debug(self, **kwargs):
        pass
    def info(self, **kwargs):
        pass
    def warning(self, **kwargs):
        pass

def _norm_level(level: str | None) -> str:
    """Normaliserer loggnivå til 'debug', 'info', eller 'warning'."""
    if not level:
        return "info"
    s = str(level).strip().lower()
    if s in ("debug", "d"):
        return "debug"
    if s in ("warning", "warn", "w"):
        return "warning"
    return "info"

def _init_logger(args: argparse.Namespace) -> JsonLogger:
    # Prioritet: CLI-flagget (--log-level) > miljøvariabel (LOG_LEVEL) > default ("info")
    cli_lvl = getattr(args, "log_level", None)
    env_lvl = os.environ.get("LOG_LEVEL")
    level = _norm_level(cli_lvl) if cli_lvl else (_norm_level(env_lvl) if env_lvl else "info")
    logger = JsonLogger(level=level)
    return logger


@contextmanager
def _timed(step: str, cache_hit: Optional[bool] = None):
    """
    Mål varighet for et steg og logg som strukturert DEBUG på STDERR.
    Bruker alltid tom 'msg' og legger felter i 'extra'.
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dur_ms = int((time.perf_counter() - t0) * 1000)
        data = {"duration_ms": dur_ms}
        if cache_hit is not None:
            data["cache_hit"] = cache_hit
        _log_debug(step, **data)

def _log_warn(step: str, msg: str) -> None:
    if _LOG:
        _LOG.warning(step=step, msg=msg)

def _log_info(step: str, **kw: Any) -> None:
    if _LOG:
        _LOG.info(step=step, **kw)

# ── S6 helper: rensing som kun fjerner None (beholder False/0) ────────────────
def _clean_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Behold False/0; dropp bare None.
    Kall _ensure_schema_and_avg_hr rett før rens/return/print.
    """
    report = _ensure_schema_and_avg_hr(report)
    return {k: v for k, v in report.items() if v is not None}

# ── Eksisterende kode ─────────────────────────────────────────────────────────
def _ensure_cli_fields(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sikrer at påkrevde felter i CLI-output finnes og har riktig type.
    - Beholder serie-felt som LISTER: watts, wind_rel, v_rel (renser til numeriske).
    - Fyller/avleder: duration_s, samples (int), precision_watt (float), if_ (float).
    - Garanterer at 'calibrated' finnes og er bool (default False).
    - Garanterer at 'status' finnes og er str (default "OK").
    """
    d = dict(r) if isinstance(r, dict) else {}

    # --- små hjelpere ---------------------------------------------------------
    def _to_float(x):
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            try:
                import re
                m = re.search(r"[-+]?\d+(?:[.,]\d+)?", x)
                if m:
                    return float(m.group(0).replace(",", "."))
            except Exception:
                pass
        return None

    def _to_bool_loose(x):
        if isinstance(x, bool):
            return x
        if isinstance(x, (int, float)):
            return bool(x)
        if isinstance(x, str):
            s = x.strip().lower()
            if s in ("true", "ja", "yes", "y", "1"):
                return True
            if s in ("false", "nei", "no", "n", "0"):
                return False
        return None

    def _ensure_list_numbers(val):
        """Liste[float]. Skalar → [float], None/ukjent → []. Filtrerer bort None."""
        if val is None:
            return []
        if isinstance(val, (list, tuple)):
            out = []
            for item in val:
                f = _to_float(item)
                if f is not None:
                    out.append(f)
            return out
        f = _to_float(val)
        return [f] if f is not None else []

    # --- duration_s -----------------------------------------------------------
    if "duration_s" not in d:
        if isinstance(d.get("duration_sec"), (int, float)):
            d["duration_s"] = d["duration_sec"]
        else:
            d["duration_s"] = 0

    # --- serie-felt: behold som lister ----------------------------------------
    d["watts"]    = _ensure_list_numbers(d.get("watts"))
    d["wind_rel"] = _ensure_list_numbers(d.get("wind_rel"))
    d["v_rel"]    = _ensure_list_numbers(d.get("v_rel"))

    # --- samples (int) ---------------------------------------------------------
    if not isinstance(d.get("samples"), int):
        d["samples"] = max(len(d["watts"]), len(d["wind_rel"]), len(d["v_rel"]))

    # --- precision_watt (numerisk) --------------------------------------------
    if "precision_watt" not in d:
        txt = d.get("PrecisionWatt") or d.get("precisionWatt")
        pw = _to_float(txt)
        if pw is not None:
            d["precision_watt"] = pw
    else:
        pw = _to_float(d["precision_watt"])
        if pw is not None:
            d["precision_watt"] = pw

    # --- if_ (Intensity Factor) -----------------------------------------------
    if "if_" not in d:
        npv = _to_float(d.get("np"))
        ftp = _to_float(d.get("ftp"))
        if npv is not None and ftp and ftp > 0:
            d["if_"] = round(npv / ftp, 3)
        else:
            d["if_"] = 0.0

    # --- calibrated (bool, alltid tilstede) -----------------------------------
    b = _to_bool_loose(d.get("calibrated"))
    if b is None:
        prof = d.get("profile")
        if isinstance(prof, dict):
            b = _to_bool_loose(prof.get("calibrated"))
    if b is None:
        b = False
    d["calibrated"] = bool(b)

    # --- status (str, alltid tilstede) ----------------------------------------
    if not isinstance(d.get("status"), str) or not d["status"]:
        hr = d.get("avg_hr", d.get("avg_pulse"))
        if isinstance(hr, (int, float)):
            d["status"] = "OK" if hr < 160 else ("Høy puls" if hr > 180 else "Lav")
        else:
            d["status"] = "OK"

    # --- session_id fallback ---------------------------------------------------
    if not d.get("session_id"):
        d["session_id"] = "session"

    return d

def _canonicalize_report_keys(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliser nøkkelnavn fra Rust-output for å unngå case-insensitive kollisjoner
    (PowerShell ConvertFrom-Json behandler keys case-insensitivt).
    - 'NP'       -> 'np'
    - 'avg_watt' -> 'avg_power'
    - 'avg'      -> 'avg_power'
    - 'avg_pulse'-> 'avg_hr'
    Fjerner eldre/overflødige varianter når kanonisk finnes.
    """
    if not isinstance(report, dict):
        return report

    # NP -> np
    if "NP" in report:
        if "np" not in report:
            report["np"] = report["NP"]
        report.pop("NP", None)

    # avg_watt/avg -> avg_power
    if "avg_power" not in report:
        if "avg_watt" in report:
            report["avg_power"] = report["avg_watt"]
        elif "avg" in report:
            report["avg_power"] = report["avg"]
    report.pop("avg_watt", None)
    report.pop("avg", None)

    # avg_pulse -> avg_hr (behold eksisterende avg_hr hvis satt)
    if "avg_hr" not in report and "avg_pulse" in report:
        report["avg_hr"] = report["avg_pulse"]
    # behold gjerne avg_pulse for bakover-kompatibilitet

    return report

# ── Konstanter ────────────────────────────────────────────────────────────────
MIN_SAMPLES_FOR_CAL = 15          # min. antall punkter for å prøve kalibrering
MIN_SPEED_SPREAD_MS = 0.8         # krever litt variasjon i fart
MIN_ALT_SPAN_M      = 3.0         # eller litt høydeforskjell

# ── Schema version (Sprint 7) ─────────────────────────────────────────────────
# Merk: S6 skal IKKE injisere schema_version i output. Behold definisjonene her,
# men ikke bruk dem før S7.
import re
from typing import Any, Dict

SCHEMA_VERSION = "0.7.0"
_SCHEMA_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
assert _SCHEMA_RE.match(SCHEMA_VERSION), f"Invalid SCHEMA_VERSION: {SCHEMA_VERSION}"

def inject_schema_version(report: Dict[str, Any]) -> Dict[str, Any]:
    """S7: Idempotent injeksjon av schema_version (ikke brukt i S6)."""
    if isinstance(report, dict) and "schema_version" not in report:
        report["schema_version"] = SCHEMA_VERSION
    return report

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

# ── NY COMPUTE_POWER_WIND ADAPTER ─────────────────────────────────────────────
import json

# Prøv v3 først (som krever 'estimat'), ellers bruk v1
try:
    from cyclegraph_core import compute_power_with_wind_json_v3 as _rs_compute_json
    _USE_V3 = True
except Exception:
    _USE_V3 = False
    try:
        from cyclegraph_core import compute_power_with_wind_json as _rs_compute_json
    except Exception:
        _rs_compute_json = None

def _looks_like_weather(x: dict) -> bool:
    if not isinstance(x, dict):
        return False
    return any(k in x for k in (
        "air_temp_c","rho","pressure_hpa","humidity","wind_speed","wind_ms","wind_dir_deg"
    ))



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

# ── METRICS-HELPERS (NP/Avg/VI/Pa:Hr/W/beat + PrecisionWatt) ──────────────────
_POWER_KEYS = ("watts", "watt", "power", "power_w", "pwr", "device_watts")
_HR_KEYS    = ("hr", "heartrate", "heart_rate", "bpm", "pulse")

def _pick_first(d: dict, keys: tuple[str, ...]):
    for k in keys:
        if k in d and d[k] is not None and d[k] != "":
            return d[k]
    return None

def _extract_power_hr(samples: List[Dict[str, Any]]) -> tuple[list[float], list[float]]:
    watts: list[float] = []
    hr: list[float] = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        pw = _pick_first(s, _POWER_KEYS)
        hh = _pick_first(s, _HR_KEYS)
        try:
            pwf = float(pw) if pw is not None else None
            hrf = float(hh) if hh is not None else None
        except (TypeError, ValueError):
            pwf = None; hrf = None
        if pwf is not None and hrf is not None:
            watts.append(float(pwf))
            hr.append(float(hrf))
    return watts, hr

def _has_power_in_samples(samples: List[Dict[str, Any]]) -> bool:
    """Returnerer True hvis *device* watt finnes i input-samples (før eventuell beregning)."""
    for s in samples:
        if not isinstance(s, dict):
            continue
        if _pick_first(s, _POWER_KEYS) is not None:
            return True
    return False

def _mean(a: List[float]) -> float:
    return sum(a) / len(a) if a else 0.0

def _estimate_hz(n_samples: int, duration_sec: float) -> float:
    if duration_sec and duration_sec > 0:
        hz = n_samples / duration_sec
        if math.isfinite(hz) and hz > 0:
            return float(hz)
    return 1.0

def _np_py(power: List[float], hz: float) -> float:
    """30s rullende → ^4 → mean → ^0.25."""
    if not power:
        return 0.0
    win = max(1, int(math.floor(30.0 * max(hz, 1e-9))))
    win = min(win, len(power))
    rolling: List[float] = []
    s = 0.0
    for i, v in enumerate(power):
        s += v
        if i >= win:
            s -= power[i - win]
        avg = s / (win if i + 1 >= win else (i + 1))
        rolling.append(avg)
    m4 = sum((x ** 4.0) for x in rolling) / len(rolling)
    return float(m4 ** 0.25)

def _iqr_sigma(vals: List[float]) -> float:
    """Robust sigma estimert fra IQR (σ ≈ IQR / 1.349)."""
    if not vals:
        return 0.0
    v = sorted(vals)
    n = len(v)
    if n == 1:
        return 0.0
    def q(p: float) -> float:
        idx = max(0.0, min(p * (n - 1), n - 1.0))
        lo = int(math.floor(idx)); hi = int(math.ceil(idx))
        if lo == hi:
            return v[lo]
        w = idx - lo
        return v[lo] * (1.0 - w) + v[hi] * w
    iqr = abs(q(0.75) - q(0.25))
    return (iqr / 1.349) if iqr > 0 else 0.0

def _precision_watt_py(power: List[float], hz: float) -> float:
    """
    PrecisionWatt (±W): 30s rullende snitt → residualer → σ_IQR → σ_eff = σ / sqrt(window).
    Returnerer en *absolutt* watt-usikkerhet (f.eks. 1.8 for ±1.8 W).
    """
    if not power:
        return 0.0
    hz = float(hz) if (isinstance(hz, (int, float)) and hz > 0 and math.isfinite(hz)) else 1.0
    win = max(1, int(math.floor(30.0 * hz)))
    win = min(win, len(power))
    # rullende snitt
    rolling: List[float] = []
    s = 0.0
    for i, v in enumerate(power):
        s += v
        if i >= win:
            s -= power[i - win]
        avg = s / (win if i + 1 >= win else (i + 1))
        rolling.append(avg)
    # residualer og robust sigma
    resid = [p - m for p, m in zip(power, rolling)]
    sigma = _iqr_sigma(resid)
    eff = sigma / math.sqrt(win) if win > 0 else sigma
    return float(eff)

def _format_precision_watt(pw: float) -> str:
    """Format som '±1.8 W' med én desimal, ikke-negativ og deterministisk."""
    if not isinstance(pw, (int, float)) or not math.isfinite(pw) or pw < 0:
        pw = 0.0
    return f"±{pw:.1f} W"

def _compute_report_metrics_inline(report: Dict[str, Any], samples: List[Dict[str, Any]]) -> None:
    """Fyller inn avg_power, avg_hr, np, vi, pa_hr, w_per_beat, PrecisionWatt i report."""
    # Foretrukne kilder: arrays fra power-pipelinen hvis tilstede
    watts_arr = None
    hr_arr = None

    if isinstance(report.get("watts"), list) and report["watts"]:
        try:
            watts_arr = [float(x) if x is not None else 0.0 for x in report["watts"]]
        except Exception:
            watts_arr = None

    # HR-array finnes sjelden i report; trekk ut fra samples
    _, hr_arr = _extract_power_hr(samples)
    if watts_arr is None:
        watts_arr, _ = _extract_power_hr(samples)

    # Avg
    avg_p = _mean(watts_arr) if watts_arr else float(report.get("avg_power") or 0.0)
    avg_h = _mean(hr_arr) if hr_arr else float(report.get("avg_hr") or report.get("avg_pulse") or 0.0)

    # np/vi
    duration_sec = float(report.get("duration_sec") or infer_duration_sec(samples))
    hz = _estimate_hz(len(watts_arr) if watts_arr else 0, duration_sec)
    np_val = _np_py(watts_arr, hz) if watts_arr else 0.0
    vi = (np_val / avg_p) if avg_p > 0 else 0.0

    # pa:hr og w/beat (samme definisjon som i core: avgW/avgHR)
    pa_hr = (avg_p / avg_h) if avg_h > 0 else 0.0
    w_per_beat = pa_hr

    # PrecisionWatt ±usikkerhet
    pw_val = _precision_watt_py(watts_arr, hz) if watts_arr else 0.0
    pw_str = _format_precision_watt(pw_val)

    # Rounding for determinisme i CLI
    def r2(x): return None if x is None else round(float(x), 2)
    report["avg_power"]  = r2(avg_p)
    report["avg_hr"]     = r2(avg_h) if avg_h > 0 else report.get("avg_hr", None)
    report["np"]         = r2(np_val)
    report["vi"]         = r2(vi)
    report["pa_hr"]      = r2(pa_hr)
    report["pa_hr_pct"]  = r2(pa_hr * 100.0) if pa_hr > 0 else None
    report["w_per_beat"] = r2(w_per_beat)
    report["PrecisionWatt"] = pw_str

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
    # Lokal import for å unngå sirkulær import ved modul-load
    from cli.io import _open_with_best_encoding  # type: ignore
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

    # --- ROBUST ÅPNING + DELIMITER-SNIFF ---
    with _open_with_best_encoding(csv_path, debug=debug) as f:
        try:
            head = f.read(2048)
            f.seek(0)
        except UnicodeDecodeError as e:
            if debug:
                print(f"DEBUG CORE: failed to read head strictly: {e}", flush=True)
            # Siste utvei – reopen tolerant
            f.close()
            f = open(csv_path, "r", encoding="latin-1", errors="replace", newline="")
            head = f.read(2048)
            f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(head, delimiters=",;")
            delim = getattr(dialect, "delimiter", ",")
            rdr = csv.reader(f, dialect)
        except Exception:
            delim = ","
            rdr = csv.reader(f, delimiter=delim)

        if debug:
            try:
                print(f"DEBUG CORE: delimiter='{delim}'", flush=True)
            except Exception:
                pass

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

        # Hvis speed feilaktig er km/t, konverter til m/s
        if speed is not None and speed > 50.0:
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
# ─────────────────────────────────────────────────────────────
def write_report(outdir: str, sid: str, report: Dict[str, Any], fmt: str) -> None:
    """
    Skriv rapport til disk i JSON/CSV.
    - Normaliserer alltid rapporten først med _ensure_cli_fields
      slik at nøkler som duration_s, samples, precision_watt, if_ m.m. er på plass.
    - CSV-feltet "if" hentes fra rapportnøkkelen "if_".
    """
    os.makedirs(outdir, exist_ok=True)

    # Normaliser/utfyll rapporten før skriving (S6: ikke schema_version enda)
    data = _ensure_cli_fields(dict(report))
    # S7: inject_schema_version(data)

    if fmt in ("json", "both"):
        p_json = os.path.join(outdir, f"{sid}.json")
        with open(p_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    if fmt in ("csv", "both"):
        import csv

        # Trygg oppslag for nested scores
        scores = data.get("scores") or {}
        if not isinstance(scores, dict):
            scores = {}

        # if_ -> CSV-felt "if"
        if_val = data.get("if_")

        # pa_hr_pct – bruk eksisterende hvis satt, ellers forsøk å beregne (~ *100) fra pa_hr
        pa_hr_pct = data.get("pa_hr_pct")
        if pa_hr_pct is None:
            pa_hr = data.get("pa_hr")
            if isinstance(pa_hr, (int, float)):
                pa_hr_pct = round(float(pa_hr) * 100.0, 2)

        fields = [
            "session_id",
            "duration_min",
            "avg_power",
            "avg_hr",
            "np",
            "if",
            "vi",
            "pa_hr_pct",
            "w_per_beat",
            "scores.intensity",
            "scores.duration",
            "scores.quality",
            "scores.cgs",
        ]
        row = {
            "session_id": data.get("session_id"),
            "duration_min": data.get("duration_min"),
            "avg_power": data.get("avg_power"),
            "avg_hr": data.get("avg_hr"),
            "np": data.get("np"),
            "if": if_val,
            "vi": data.get("vi"),
            "pa_hr_pct": pa_hr_pct,
            "w_per_beat": data.get("w_per_beat"),
            "scores.intensity": scores.get("intensity"),
            "scores.duration": scores.get("duration"),
            "scores.quality": scores.get("quality"),
            "scores.cgs": scores.get("cgs"),
        }

        p_csv = os.path.join(outdir, f"{sid}.csv")
        with open(p_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerow(row)

def write_report(outdir: str, sid: str, report: Dict[str, Any], fmt: str) -> None:
    """
    Skriv rapport til disk i JSON/CSV.
    - Normaliserer alltid rapporten først med _ensure_cli_fields
      slik at nøkler som duration_s, samples, precision_watt, if_ m.m. er på plass.
    - CSV-feltet "if" hentes fra rapportnøkkelen "if_".
    """
    os.makedirs(outdir, exist_ok=True)

    # Normaliser/utfyll rapporten før skriving (S6: ikke schema_version enda)
    report = _ensure_schema_and_avg_hr(dict(report))
    data = _ensure_cli_fields(report)
    # S7: inject_schema_version(data)

    if fmt in ("json", "both"):
        p_json = os.path.join(outdir, f"{sid}.json")
        with open(p_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    if fmt in ("csv", "both"):
        import csv

        # Trygg oppslag for nested scores
        scores = data.get("scores") or {}
        if not isinstance(scores, dict):
            scores = {}

        # if_ -> CSV-felt "if"
        if_val = data.get("if_")

        # pa_hr_pct – bruk eksisterende hvis satt, ellers forsøk å beregne (~ *100) fra pa_hr
        pa_hr_pct = data.get("pa_hr_pct")
        if pa_hr_pct is None:
            pa_hr = data.get("pa_hr")
            if isinstance(pa_hr, (int, float)):
                pa_hr_pct = round(float(pa_hr) * 100.0, 2)

        fields = [
            "session_id",
            "duration_min",
            "avg_power",
            "avg_hr",
            "np",
            "if",
            "vi",
            "pa_hr_pct",
            "w_per_beat",
            "scores.intensity",
            "scores.duration",
            "scores.quality",
            "scores.cgs",
        ]
        row = {
            "session_id": data.get("session_id"),
            "duration_min": data.get("duration_min"),
            "avg_power": data.get("avg_power"),
            "avg_hr": data.get("avg_hr"),
            "np": data.get("np"),
            "if": if_val,
            "vi": data.get("vi"),
            "pa_hr_pct": pa_hr_pct,
            "w_per_beat": data.get("w_per_beat"),
            "scores.intensity": scores.get("intensity"),
            "scores.duration": scores.get("duration"),
            "scores.quality": scores.get("quality"),
            "scores.cgs": scores.get("cgs"),
        }

        p_csv = os.path.join(outdir, f"{sid}.csv")
        with open(p_csv, "w", encoding="utf-8", newline="") as f:
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


def _safe_load_weather(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else None
    except Exception as e:
        print(f"ADVARSEL: Klarte ikke å lese weather-fil: {path} ({e})", file=sys.stderr)
        return None


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

# ── Helpers for key/type normalization (3a + 3b) ─────────────────────────────
import re
from typing import Any, Dict, List

_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")

def _to_bool_loose(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("1", "true", "ja", "yes"):
        return True
    if s in ("0", "false", "nei", "no"):
        return False
    return None

def _extract_float(s: str) -> float | None:
    try:
        s = s.replace(",", ".")
    except Exception:
        pass
    m = _NUM_RE.search(str(s))
    return float(m.group(0)) if m else None

def _canonicalize_report_keys(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map alias/feil-keys til forventet schema, rydder noen typer.
    Sørger spesielt for:
      - duration_s (alias fra duration_sec)
      - avg_power (alias fra avg/avg_watt)
      - if_ (alias fra if/IF)
      - precision_watt (alias fra PrecisionWatt + trekker ut tall)
      - calibrated som bool der mulig
    """
    out: Dict[str, Any] = {}

    alias = {
        "duration_sec": "duration_s",
        "DurationSec": "duration_s",
        "avg": "avg_power",
        "avg_watt": "avg_power",
        "AvgPower": "avg_power",
        "if": "if_",
        "IF": "if_",
        "PrecisionWatt": "precision_watt",
        "precisionWatt": "precision_watt",
    }

    # 1) kopier med alias
    for k, v in r.items():
        k2 = alias.get(k, k)
        out[k2] = v

    # 2) booleans
    if "calibrated" in out:
        b = _to_bool_loose(out["calibrated"])
        if b is not None:
            out["calibrated"] = b

    # 3) precision_watt som tall
    if "precision_watt" in out and isinstance(out["precision_watt"], str):
        pw = _extract_float(out["precision_watt"])
        if pw is not None:
            out["precision_watt"] = pw

    # 4) sikre duration_s hvis bare duration_sec fantes i original
    if "duration_s" not in out and "duration_sec" in r:
        out["duration_s"] = r.get("duration_sec")

    return out

def _ensure_cli_fields(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sikrer at påkrevde felter finnes i CLI-output med riktige typer.
    Fyller ut/avleder: samples, duration_s, precision_watt (numerisk), if_.
    Flater også ut wind_rel og v_rel til skalarer (gjennomsnitt).
    """
    d = dict(r)  # shallow copy

    # duration_s
    if "duration_s" not in d and "duration_sec" in d:
        d["duration_s"] = d.get("duration_sec")

    # samples (hent fra lengste av kjente arrays hvis ikke satt)
    if "samples" not in d or not isinstance(d["samples"], int):
        candidates = []
        for key in ("watts", "wind_rel", "v_rel"):
            v = d.get(key)
            if isinstance(v, (list, tuple)):
                candidates.append(len(v))
        d["samples"] = max(candidates) if candidates else int(d.get("samples") or 0)

    # precision_watt (numerisk)
    if "precision_watt" not in d:
        txt = d.get("PrecisionWatt") or d.get("precisionWatt")
        if isinstance(txt, str):
            pw = _extract_float(txt)
            if pw is not None:
                d["precision_watt"] = pw
    if "precision_watt" in d and isinstance(d["precision_watt"], str):
        pw = _extract_float(d["precision_watt"])
        if pw is not None:
            d["precision_watt"] = pw

    # if_ – forsøk å regne ut fra np/ftp hvis mulig, ellers 0.0 for å sikre feltet
    if "if_" not in d:
        npv = d.get("np")
        ftp = d.get("ftp")
        try:
            npf = float(npv) if npv is not None else None
            ftpf = float(ftp) if ftp else None
        except Exception:
            npf, ftpf = None, None
        if npf is not None and ftpf and ftpf > 0:
            d["if_"] = round(npf / ftpf, 3)
        else:
            d["if_"] = 0.0

    # calibrated → bool om mulig
    if "calibrated" in d:
        b = _to_bool_loose(d["calibrated"])
        if b is not None:
            d["calibrated"] = b

    # status → str fallback
    if "status" in d and d["status"] is None:
        d["status"] = "OK"

    # sikre at wind_rel og v_rel er skalarer
    for arr_key in ("wind_rel", "v_rel"):
        v = d.get(arr_key)
        if isinstance(v, (list, tuple)):
            vals = [float(x) for x in v if isinstance(x, (int, float))]
            d[arr_key] = (sum(vals) / len(vals)) if vals else 0.0
        elif isinstance(v, (int, float)):
            d[arr_key] = float(v)
        else:
            d[arr_key] = 0.0

    # påkrevd: session_id
    if not d.get("session_id"):
        d["session_id"] = "session"

    return d

# ── Ekstra S6-sikring før rens/printing ───────────────────────────────────────
def _ensure_required_s6_fields(report: Dict[str, Any]) -> None:
    """
    Sikrer S6-krav før rensing/printing:
      - calibrated alltid bool (default False)
      - reason None hvis calibrated True, ellers behold eksisterende string hvis finnes
      - status 'LIMITED' hvis None/blank
      - watts/wind_rel/v_rel må finnes (minst tom liste)
    Muterer dict in-place.
    """
    calibrated = bool(report.get("calibrated", False))
    report["calibrated"] = calibrated

    if calibrated:
        report["reason"] = None
    else:
        # behold forklaring hvis tilgjengelig
        if "reason" not in report:
            report["reason"] = report.get("reason")  # no-op, lar None stå hvis ukjent

    status = report.get("status")
    if status is None or (isinstance(status, str) and not status.strip()):
        report["status"] = "LIMITED"

    for k in ("watts", "wind_rel", "v_rel"):
        v = report.get(k)
        if v is None:
            report[k] = []
        elif isinstance(v, (list, tuple)):
            # hold kun numerics
            report[k] = [float(x) for x in v if isinstance(x, (int, float))]
        else:
            try:
                report[k] = [float(v)]
            except Exception:
                report[k] = []

# ─────────────────────────────────────────────────────────────
# Kommandofunksjonen
# ─────────────────────────────────────────────────────────────
def cmd_session(args: argparse.Namespace) -> int:
    # Init/bruk JSON-logger lokalt (STDERR). Uavhengig av analyze.py.
    import logging as _logging, os as _os

    class _JsonFormatter(_logging.Formatter):
        def format(self, record: _logging.LogRecord) -> str:
            payload = {"level": record.levelname}  # "INFO"/"DEBUG"/"WARNING"
            # Ta med alle extras (step, component, metric, cache_hit, osv.)
            for k, v in record.__dict__.items():
                if k not in (
                    "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
                    "pathname", "process", "processName", "relativeCreated", "stack_info", "thread", "threadName"
                ):
                    payload[k] = v
            return json.dumps(payload, ensure_ascii=False)

    # Konfigurer global logger hvis den ikke allerede har handler(e)
    global _LOG
    _LOG = _logging.getLogger("cyclegraph.cli")
    if not _LOG.handlers:
        h = _logging.StreamHandler(sys.stderr)  # <- VIKTIG: STDERR
        h.setFormatter(_JsonFormatter())
        _LOG.handlers.clear()
        _LOG.addHandler(h)
        lvl = (getattr(args, "log_level", None) or _os.getenv("LOG_LEVEL") or "INFO").upper()
        _LOG.setLevel(getattr(_logging, lvl, _logging.INFO))
        _LOG.propagate = False

    # ── HARD REBIND (GLOBAL): sikre at wrapperne alltid bruker tom msg + extra=... ──
    def __json_debug(step: str, **kwargs):
        _LOG.debug("", extra={"step": step, **kwargs})

    def __json_info(step: str, **kwargs):
        _LOG.info("", extra={"step": step, **kwargs})

    def __json_warn(step: str, detail: str = "", **kwargs):
        # NB: IKKE bruk 'msg' eller 'message' i extra (reserverte)
        if detail:
            kwargs["detail"] = detail
        _LOG.warning("", extra={"step": step, **kwargs})

    # Viktig: rebind GLOBALT slik at også _timed() bruker disse
    global _log_debug, _log_info, _log_warn
    _log_debug = __json_debug
    _log_info = __json_info
    _log_warn = __json_warn
    # ────────────────────────────────────────────────────────────────────────────────

    _log_info("startup", config="session", log_level=(getattr(args, "log_level", None) or "info"))

    with _timed("load_cfg"):
        cfg = load_cfg(getattr(args, "cfg", None))

    history_dir = cfg.get("history_dir", "history")
    outdir = getattr(args, "out", "output")
    fmt = getattr(args, "format", "json")
    lang = getattr(args, "lang", "no")

    with _timed("parse_input_glob"):
        paths = sorted(glob.glob(args.input))

    if getattr(args, "debug", False):
        print("DEBUG: input filer:", paths, file=sys.stderr)
    if not paths:
        _log_warn("parse_input_glob", detail=f"Ingen filer for pattern: {args.input}")
        print(f"Ingen filer for pattern: {args.input}", file=sys.stderr)
        return 2

    reports: List[Dict[str, Any]] = []

    # --- LOKAL ARRAYS-BRIDGE (erstatter gamle rust_analyze_session-kall) ---
    def _arrays_analyze_call_local(watts, pulses, device=None):
        """Kall arrays-APIet fra cli.analyze_session (watts, hr, device_watts=None)."""
        from cli import analyze_session as _arrays
        return _arrays(watts, pulses, device or "powermeter")

    def _analyze_session_bridge_local(samples: List[Dict[str, Any]], meta: Dict[str, Any], cfg: Dict[str, Any]):
        """
        Trekker ut watts/hr fra samples, kaller arrays-API,
        og returnerer et lite dict som resten av pipeline kan bruke.
        """
        watts: List[float] = []
        pulses: List[float] = []

        for s in samples:
            w = s.get("watts") or s.get("power") or s.get("w")
            h = s.get("hr") or s.get("heart_rate") or s.get("pulse")
            if isinstance(w, (int, float)):
                watts.append(float(w))
            if isinstance(h, (int, float)):
                pulses.append(float(h))

        # Match lengder (arrays-API krever lik lengde og ikke tom hr)
        n = min(len(watts), len(pulses))
        watts = watts[:n]
        pulses = pulses[:n]

        # Kall arrays-API; robust mot tomme serier (da kan tests forventer kontrollert håndtering senere)
        try:
            val = _arrays_analyze_call_local(watts, pulses, cfg.get("device", "powermeter"))
        except Exception as e:
            _log_warn("analyze_session_bridge", detail=f"arrays-analyze feilet: {e}")
            val = 0.0

        # Returner et lite dict (resten av koden fyller ut metrics senere)
        return {"precision_watt": float(val) if isinstance(val, (int, float)) else val}

    for path in paths:
        # Les og parse CSV til samples
        with _timed("read_session_csv"):
            samples = read_session_csv(path, debug=getattr(args, "debug", False))

        if getattr(args, "debug", False):
            print(f"DEBUG: {path} -> {len(samples)} samples", file=sys.stderr)
        if not samples:
            _log_warn("read_session_csv", detail=f"{path} har ingen gyldige samples.")
            print(f"ADVARSEL: {path} har ingen gyldige samples.", file=sys.stderr)
            continue

        # Flag for "mangler device-wattdata"
        no_device_power = not _has_power_in_samples(samples)

        sid = session_id_from_path(path)
        with _timed("infer_duration"):
            duration_sec = infer_duration_sec(samples)

        meta: Dict[str, Any] = {
            "session_id": sid,
            "duration_sec": duration_sec,
            "duration_min": round(duration_sec / 60.0, 2) if duration_sec else None,
            "ftp": None,
            "hr_max": cfg.get("hr_max"),
            "start_time_utc": None,
        }

        if getattr(args, "mode", None):
            print(f"🎛️ Overstyrt modus: {args.mode}", file=sys.stderr)
            meta["mode"] = args.mode
        else:
            print("Ingen overstyring – modus settes automatisk senere hvis relevant.", file=sys.stderr)

        # FTP
        with _timed("resolve_ftp"):
            if getattr(args, "set_ftp", None) is not None:
                meta["ftp"] = float(args.set_ftp)
            elif getattr(args, "auto_ftp", False):
                ftp_est = estimate_ftp_20min95(samples)
                if ftp_est > 0:
                    meta["ftp"] = round(ftp_est, 1)
            elif "ftp" in cfg:
                meta["ftp"] = cfg.get("ftp")

        # Kjør analyse via arrays-wrapper (IKKE native session-API)
        with _timed("analyze_session", cache_hit=False):
            report_raw = _analyze_session_bridge_local(samples, meta, cfg)

        if isinstance(report_raw, str) and report_raw.strip() == "":
            _log_warn("analyze_session", detail=f"_analyze_session_bridge returnerte tom streng for {path}")
            print(f"ADVARSEL: _analyze_session_bridge returnerte tom streng for {path}", file=sys.stderr)
            continue

        try:
            with _timed("parse_analyze_json"):
                report = json.loads(report_raw) if isinstance(report_raw, str) else report_raw
                report = _canonicalize_report_keys(report)  # normaliser nøkler til snake_case der vi kan
        except json.JSONDecodeError as e:
            _log_warn("parse_analyze_json", detail=f"Klarte ikke å parse JSON for {path}: {e}")
            print(f"ADVARSEL: Klarte ikke å parse JSON for {path}: {e}", file=sys.stderr)
            continue

        # Sett basisfelter om de mangler
        report.setdefault("session_id", sid)
        report.setdefault("duration_sec", duration_sec)
        report.setdefault("duration_min", round(duration_sec / 60.0, 2) if duration_sec else None)

        # Sett hr_only/limited hvis vi mangler device power og mode ikke allerede er eksplisitt
        if no_device_power and not (report.get("mode") or "").strip():
            report["mode"] = "hr_only"
            report["status"] = "LIMITED"

        # sessions_no_power_total metric
        mode = str(report.get("mode") or "").lower()
        if no_device_power or mode == "hr_only":
            _log_info(
                "metric",
                metric="sessions_no_power_total",
                value=1,
                session_id=sid,
                component="cli/session",
            )

        # --- Vind/kraft fra kjernen (PowerOutputs) ---
        # BRUKER NY ADAPTER HER
        if _rs_compute_json is not None:
            # Normaliser fra read_session_csv
            with _timed("normalize_core_samples"):
                core_samples = [_normalize_sample_for_core(s) for s in samples]

            # CSV-fallback hvis normaliseringen ser "tom" ut
            def _looks_empty(core: list[dict]) -> bool:
                if not core:
                    return True
                pos_ok = any((c.get("latitude") is not None and c.get("longitude") is not None) for c in core)
                speed_ok = sum(1 for c in core if (c.get("v_ms") or 0.0) > 0.2) >= max(1, len(core)//4)
                return (not pos_ok) or (not speed_ok)

            if _looks_empty(core_samples):
                if getattr(args, "debug", False):
                    print("DEBUG CORE: normalized samples look empty -> using CSV fallback", file=sys.stderr)
                with _timed("csv_fallback_normalize"):
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

            # Last vær robust
            weather_for_core = _load_weather_for_cal(args)

            if getattr(args, "debug", False):
                print(f"DEBUG CORE: profile_for_core={profile_for_core}", file=sys.stderr)
                print(f"DEBUG CORE: weather_for_core={weather_for_core}", file=sys.stderr)

            with _timed("compute_power_with_wind"):
                # BRUK NY ADAPTER HER - sender dicts direkte
                power_json = rs_power_json(core_samples, profile_for_core, weather_for_core)
            power_obj = json.loads(power_json) if isinstance(power_json, str) else power_json

            cache_hit = False
            try:
                cache_hit = bool(power_obj.get("cache_hit", False))
            except Exception:
                cache_hit = False
            # Viktig: component på compute_power_with_wind
            _log_info("compute_power_with_wind", cache_hit=cache_hit, component="cli/session")

            if getattr(args, "debug", False):
                print(f"DEBUG CORE: keys={list(power_obj.keys())}", file=sys.stderr)
                print(f"DEBUG CORE: watts_head={power_obj.get('watts', [])[:3]}", file=sys.stderr)
                print(f"DEBUG CORE: wind_head={power_obj.get('wind_rel', [])[:3]}", file=sys.stderr)
                print(f"DEBUG CORE: vrel_head={power_obj.get('v_rel', [])[:3]}", file=sys.stderr)

            for k in ("watts", "wind_rel", "v_rel"):
                v = power_obj.get(k)
                if v is not None:
                    report[k] = v

        # ── BEREGN RAPPORTFELT (NP, Avg, VI, Pa:Hr, W/beat, PrecisionWatt) ────
        with _timed("compute_metrics"):
            _compute_report_metrics_inline(report, samples)

        # ── KALIBRERING (kun hvis --calibrate) ────────────────────────────────
        if getattr(args, "calibrate", False):
            with _timed("calibrate", cache_hit=False):
                try:
                    from .rust_bindings import calibrate_session as rs_cal
                except Exception:
                    from cli.rust_bindings import calibrate_session as rs_cal  # type: ignore

                profile_for_cal = _build_profile_for_cal(report, cfg, args)
                weather_for_cal = _load_weather_for_cal(args)

                try:
                    cal = rs_cal([], [], [], profile_for_cal, weather_for_cal)
                    for k in ("calibrated", "cda", "crr", "mae"):
                        if cal.get(k) is not None:
                            report[k] = cal[k]
                    report["reason"] = cal.get("reason")
                except Exception as e:
                    _log_warn("calibrate", detail=f"Kalibrering feilet: {e}")
                    print(f"⚠️ Kalibrering feilet: {e}", file=sys.stderr)

        # Baseline/badge
        with _timed("baseline_lookup"):
            baseline = load_baseline_wpb(history_dir, sid, report.get("duration_min", 0.0))
        if baseline is not None:
            report["w_per_beat_baseline"] = round(baseline, 4)

        with _timed("apply_badges"):
            maybe_apply_big_engine_badge(report)

        # Siste sikring: sørg for at serie-felt finnes og er lister
        for _k in ("watts", "wind_rel", "v_rel"):
            _v = report.get(_k)
            if _v is None:
                report[_k] = []
            elif isinstance(_v, (list, tuple)):
                report[_k] = [float(x) for x in _v if isinstance(x, (int, float))]
            else:
                try:
                    report[_k] = [float(_v)]
                except Exception:
                    report[_k] = []

        # Garanter obligatoriske felt (inkl. 'calibrated')
        report = _ensure_cli_fields(report)

        # 🔒 S6-krav før utskrift
        _ensure_required_s6_fields(report)

        reports.append(report)

 # --- Siste normalisering og utskriftshjelper -----------------------------
    def _finalize_cli_report(d: dict) -> dict:
        """
        Siste-sjekk før CLI-stdout:
        - Idempotent normalisering
        - schema_version som "0.7.0" (string)
        - calibrated: str ('Ja'/'Nei') -> bool
        - reason-regel: hvis calibrated==True -> fjern; ellers sett default
        - status default 'ok' hvis mangler
        - behold toleranse for wind_rel/v_rel (tall ELLER liste)
        """
        out = dict(d or {})
        # Sørg for basisfelt brukt av CLI (din eksisterende helper)
        try:
            out = _ensure_cli_fields(out)
        except Exception:
            pass

        # Ekstra S6-krav (din helper – gjør ikke noe hvis ikke finnes)
        try:
            _ensure_required_s6_fields(out)
        except Exception:
            pass

        # schema_version som streng (testene dine forventer "0.7.0")
        out["schema_version"] = "0.7.0"

        # status default
        out.setdefault("status", "ok")

        # calibrated -> bool
        cal = out.get("calibrated")
        if isinstance(cal, str):
            norm = cal.strip().lower()
            if norm in ("ja", "yes", "true", "1"):
                out["calibrated"] = True
            elif norm in ("nei", "no", "false", "0"):
                out["calibrated"] = False
            else:
                out["calibrated"] = False
        elif cal is None:
            out["calibrated"] = False  # safe default

        # reason-regel (ingen duplikat)
        if out.get("calibrated") is True:
            out.pop("reason", None)
        else:
            if not out.get("reason"):
                out["reason"] = "calibration_context_missing"

        # Garanter at seriefeltene finnes (tillat tall ELLER liste – ikke cast her)
        for k in ("watts", "wind_rel", "v_rel"):
            if k not in out or out[k] is None:
                out[k] = [] if k == "watts" else None

        return out

    # ------------------------------ Ikke-batch -------------------------------
    if not getattr(args, "batch", False):
        if getattr(args, "dry_run", False):
            with _timed("report_generation", cache_hit=False):
                # ÉN linje ren JSON til STDOUT
                emit_cli_json(_finalize_cli_report(report))

                # Alt annet til STDERR
                try:
                    pieces = build_publish_texts(report, lang=lang)
                    print(f"[DRY-RUN] COMMENT: {pieces.comment}", file=sys.stderr)
                    print(f"[DRY-RUN] DESC: {pieces.desc_header}", file=sys.stderr)
                except Exception as e:
                    print(f"[DRY-RUN] build_publish_texts feilet: {e}", file=sys.stderr)

                print(
                    "[DRY-RUN] METRICS: "
                    f"NP={report.get('np')} Avg={report.get('avg_power')} "
                    f"VI={report.get('vi')} Pa:Hr={report.get('pa_hr')} "
                    f"W/beat={report.get('w_per_beat')} {report.get('PrecisionWatt')}",
                    file=sys.stderr
                )
        else:
            with _timed("write_report", cache_hit=False):
                # Filskriving kan bruke ikke-finalisert report (write_report normaliserer selv)
                write_report(outdir, sid, report, fmt)
                write_history_copy(history_dir, report)

        if getattr(args, "publish_to_strava", False):
            with _timed("publish_to_strava", cache_hit=False):
                try:
                    pieces = build_publish_texts(report, lang=lang)
                    aid, status = StravaClient(lang=lang).publish_to_strava(
                        pieces, dry_run=getattr(args, "dry_run", False)
                    )
                    print(f"[STRAVA] activity_id={aid} status={status}", file=sys.stderr)
                except Exception as e:
                    print(f"[STRAVA] publisering feilet: {e}", file=sys.stderr)

    # ------------------------------- Batch -----------------------------------
    if getattr(args, "batch", False) and reports:
        if getattr(args, "with_trend", False):
            with _timed("apply_trend_last3"):
                apply_trend_last3(reports)

        for r in reports:
            sid = r.get("session_id", "session")
            with _timed("baseline_lookup"):
                baseline = load_baseline_wpb(history_dir, sid, r.get("duration_min", 0.0))
            if baseline is not None:
                r["w_per_beat_baseline"] = round(baseline, 4)

            with _timed("apply_badges"):
                maybe_apply_big_engine_badge(r)

            # Siste sikring for serier i batch (her holder vi oss til listetype for watts)
            for _k in ("watts",):
                _v = r.get(_k)
                if _v is None:
                    r[_k] = []
                elif isinstance(_v, (list, tuple)):
                    r[_k] = [float(x) for x in _v if isinstance(x, (int, float))]
                else:
                    try:
                        r[_k] = [float(_v)]
                    except Exception:
                        r[_k] = []

            # Garanter obligatoriske felt og S6-krav før utskrift/skriving
            try:
                r = _ensure_cli_fields(r)
            except Exception:
                pass
            try:
                _ensure_required_s6_fields(r)
            except Exception:
                pass

            if getattr(args, "dry_run", False):
                with _timed("report_generation", cache_hit=False):
                    emit_cli_json(_finalize_cli_report(r))

                    try:
                        pieces = build_publish_texts(r, lang=lang)
                        print(f"[DRY-RUN] COMMENT: {pieces.comment}", file=sys.stderr)
                        print(f"[DRY-RUN] DESC: {pieces.desc_header}", file=sys.stderr)
                    except Exception as e:
                        print(f"[DRY-RUN] build_publish_texts feilet: {e}", file=sys.stderr)

                    print(
                        "[DRY-RUN] METRICS: "
                        f"NP={r.get('np')} Avg={r.get('avg_power')} "
                        f"VI={r.get('vi')} Pa:Hr={r.get('pa_hr')} "
                        f"W/beat={r.get('w_per_beat')} {r.get('PrecisionWatt')}",
                        file=sys.stderr
                    )
            else:
                with _timed("write_report", cache_hit=False):
                    write_report(outdir, sid, r, fmt)
                    write_history_copy(history_dir, r)

        if getattr(args, "publish_to_strava", False):
            with _timed("publish_to_strava", cache_hit=False):
                try:
                    pieces = build_publish_texts(reports[-1], lang=lang)
                    aid, status = StravaClient(lang=lang).publish_to_strava(
                        pieces, dry_run=getattr(args, "dry_run", False)
                    )
                    print(f"[STRAVA] activity_id={aid} status={status}", file=sys.stderr)
                except Exception as e:
                    print(f"[STRAVA] publisering feilet: {e}", file=sys.stderr)

    _log_info(step="done")
    return 0