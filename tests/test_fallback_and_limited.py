# tests/test_fallback_and_limited.py
import json
import os
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
        # Rask filter: JSON må bruke doble fnutter for nøkler
        if '"' not in candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    raise AssertionError("Fant ikke gyldig JSON-objekt i stdout.")

def _run_cli() -> Tuple[dict, str, str]:
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
    if proc.returncode != 0:
        raise AssertionError(f"CLI returnerte {proc.returncode}\nSTDERR:\n{proc.stderr}")
    report = _find_first_json_object(proc.stdout)
    return report, proc.stdout, proc.stderr

def test_hr_only_mode_and_limited_status():
    report, out, err = _run_cli()

    mode = (report.get("mode") or "").lower()
    status = report.get("status")

    assert mode == "hr_only", f"Forventet mode=hr_only, fikk {mode!r}"
    assert status == "LIMITED", f"Forventet status='LIMITED', fikk {status!r}"

def test_sessions_no_power_metric_logged():
    report, out, err = _run_cli()

    # Bekreft eksplisitt metrikklinje i stderr-logg
    assert '"metric": "sessions_no_power_total"' in err or "sessions_no_power_total" in err, \
        f"Metrikk sessions_no_power_total ikke funnet i stderr.\n{err}"
    assert '"value": 1' in err, \
        f"Forventet value=1 for sessions_no_power_total i stderr.\n{err}"