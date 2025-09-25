# tests/test_metric_no_power.py
import json
import os
import subprocess
import sys
from typing import Dict, Any, List, Tuple

INPUT_CSV = os.path.join("tests", "test_golden_segment.csv")
EXPECTED_SESSION_ID = "test_golden_segment"

def _find_first_json_object(s: str) -> Dict[str, Any]:
    """
    Finn første GYLDIGE JSON-objekt i en tekststrøm (stdout).
    Ignorerer evt. Python-dict-repr med enkeltfnutter.
    """
    starts = [i for i, ch in enumerate(s) if ch == "{"]
    for start in starts:
        depth = 0
        end = None
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        candidate = s[start:end]
        if '"' not in candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    raise AssertionError("Fant ikke gyldig JSON-rapport i stdout.")

def _parse_json_logs(stderr_text: str) -> List[Dict[str, Any]]:
    """Plukk ut JSON-linjer fra stderr og parse dem (ignorerer støy)."""
    out: List[Dict[str, Any]] = []
    for line in stderr_text.splitlines():
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict) and "level" in obj and ("step" in obj or "metric" in obj):
            out.append(obj)
    return out

def _run_cli() -> Tuple[Dict[str, Any], str, str, List[Dict[str, Any]]]:
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
    assert proc.returncode == 0, f"CLI returnerte {proc.returncode}\nSTDERR:\n{proc.stderr}"
    report = _find_first_json_object(proc.stdout)
    logs = _parse_json_logs(proc.stderr)
    return report, proc.stdout, proc.stderr, logs

def test_sessions_no_power_total_metric_logged_with_value_and_session_id():
    report, out, err, logs = _run_cli()

    metric_logs = [l for l in logs if l.get("metric") == "sessions_no_power_total"]
    assert metric_logs, f"Mangler logg for 'sessions_no_power_total'. STDERR:\n{err}"

    # Minst én metrikklinje med value=1 og session_id
    assert any(l.get("value") == 1 for l in metric_logs), "Forventet value=1 for sessions_no_power_total."
    assert any("session_id" in l for l in metric_logs), "Mangler session_id på metrikklinje."

    # Sjekk at session_id faktisk matcher forventet (basename uten .csv)
    assert any(l.get("session_id") == EXPECTED_SESSION_ID for l in metric_logs), \
        f"session_id bør være '{EXPECTED_SESSION_ID}'. Fikk: {[l.get('session_id') for l in metric_logs]}"

def test_report_fields_exist_and_logs_are_structured():
    report, out, err, logs = _run_cli()

    # Hurtigsjekk av sentrale rapportfelt (vises i CLI-output)
    for key in ("np", "avg_power", "vi", "pa_hr", "w_per_beat", "PrecisionWatt"):
        assert key in report, f"Mangler felt '{key}' i rapportoutput."

    # Logger i strukturert format: har level/step og cache_hit på compute_power_with_wind
    assert any(l.get("level") in ("INFO", "DEBUG", "WARNING") for l in logs), "Fant ingen strukturerte logglinjer."
    cpw = [l for l in logs if l.get("step") == "compute_power_with_wind"]
    assert cpw, "Mangler logg for step='compute_power_with_wind'."
    assert any("cache_hit" in l for l in cpw), "compute_power_with_wind mangler 'cache_hit'."

    # Dry-run + debug gir ekstra innsikt (ikke strengt krav hvilke felt, men vi forventer flere linjer)
    assert len(logs) >= 3, "For få strukturerte logglinjer i --dry-run --debug-modus."