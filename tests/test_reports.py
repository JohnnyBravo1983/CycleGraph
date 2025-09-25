# tests/test_reports.py
import json
import os
import re
import subprocess
import sys
from typing import Tuple

INPUT_CSV = os.path.join("tests", "test_golden_segment.csv")

def _find_first_json_object(s: str) -> dict:
    """
    Finn første *gyldige* JSON-objekt i strengen.
    Skanner alle balanserte {...}-blokker og prøver json.loads på hver
    til vi lykkes. Ignorerer Python-dict-repr med enkeltfnutter.
    """
    starts = [i for i, ch in enumerate(s) if ch == "{"]
    for start in starts:
        depth = 0
        end = None
        for i in range(start, len(s)):
            ch = s[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        candidate = s[start:end]
        # JSON må bruke doble fnutter for nøkler/strenger
        if '"' not in candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    raise AssertionError("Fant ikke gyldig JSON-objekt i stdout.")

def _run_cli_once() -> Tuple[dict, str, str]:
    """
    Kjør CLI én gang og returner (report_json, stdout_text, stderr_text).
    """
    cmd = [
        sys.executable, "-m", "cli.analyze",
        "session",
        "--input", INPUT_CSV,
        "--format", "json",
        "--dry-run",
        "--debug",
        "--log-level", "info",
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, ):
        raise AssertionError(f"CLI returnerte {proc.returncode}. stderr:\n{proc.stderr}")
    report = _find_first_json_object(proc.stdout)
    return report, proc.stdout, proc.stderr

def test_report_fields_present_and_typed():
    report, out, err = _run_cli_once()

    # Nøkkelfelt finnes
    for key in ("avg_power", "avg_hr", "np", "vi", "pa_hr", "w_per_beat", "PrecisionWatt"):
        assert key in report, f"Mangler felt '{key}' i rapport."

    # Typer/format
    def is_num(x):
        return isinstance(x, (int, float))

    assert (report["avg_power"] is None) or is_num(report["avg_power"])
    assert (report["avg_hr"] is None) or is_num(report["avg_hr"])
    assert is_num(report["np"])
    assert is_num(report["vi"])
    assert is_num(report["pa_hr"])
    assert is_num(report["w_per_beat"])

    # PrecisionWatt-format '±X.X W' (én desimal)
    pw = report["PrecisionWatt"]
    assert isinstance(pw, str), "PrecisionWatt skal være streng."
    assert pw.startswith("±") and pw.endswith(" W") and re.match(r"^±\d+(\.\d)?\sW$", pw), \
        f"Ugyldig PrecisionWatt-format: {pw!r}"

def test_vi_and_pa_hr_consistency():
    report, *_ = _run_cli_once()

    avg_p = report.get("avg_power") or 0.0
    avg_h = report.get("avg_hr") or 0.0
    np_val = report.get("np") or 0.0
    vi = report.get("vi") or 0.0
    pa_hr = report.get("pa_hr") or 0.0

    # VI ≈ NP / Avg (innen avrunding ~0.02)
    if avg_p and avg_p > 0:
        expected_vi = np_val / avg_p if avg_p else 0.0
        assert abs(vi - expected_vi) <= 0.02, f"VI avviker: {vi} vs {expected_vi}"

    # Pa:Hr ≈ AvgPower / AvgHR (innen avrunding ~0.02) når HR > 0
    if avg_h and avg_h > 0:
        expected_pa_hr = (avg_p / avg_h) if avg_p else 0.0
        assert abs(pa_hr - expected_pa_hr) <= 0.02, f"Pa:Hr avviker: {pa_hr} vs {expected_pa_hr}"

    # W/beat == Pa:Hr etter definisjon i CLI
    assert abs((report.get("w_per_beat") or 0.0) - pa_hr) <= 1e-9

def test_determinism_same_input_same_metrics():
    r1, _, _ = _run_cli_once()
    r2, _, _ = _run_cli_once()

    keys = ("avg_power", "avg_hr", "np", "vi", "pa_hr", "w_per_beat", "PrecisionWatt")
    for k in keys:
        assert r1.get(k) == r2.get(k), f"Ikke deterministisk for '{k}': {r1.get(k)} vs {r2.get(k)}"

def test_observability_metric_no_power_logged():
    """
    Når input mangler device-watt (hr_only/LIMITED), skal logger vise:
      {"metric": "sessions_no_power_total", "value": 1}
    I stderr-strømmen (JsonLogger->info).
    """
    report, out, err = _run_cli_once()

    # Grep etter metrikklinjen
    assert '"metric": "sessions_no_power_total"' in err or "'sessions_no_power_total'" in err, \
        f"Metrikk sessions_no_power_total ble ikke logget i stderr.\nstderr:\n{err}"
    assert '"value": 1' in err, \
        f"Metrikkverdi 1 ikke funnet i stderr for sessions_no_power_total.\nstderr:\n{err}"