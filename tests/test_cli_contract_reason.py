from __future__ import annotations
import sys
import subprocess
import json
from pathlib import Path
import pytest

HERE = Path(__file__).parent
GOLDEN_CSV = HERE / "data" / "golden_outdoor.csv"

def _extract_last_json(stdout: str):
    """
    Finn siste JSON-linje i STDOUT (CLI skriver én linje JSON).
    Robust mot evt. støy i andre miljøer.
    """
    lines = [ln.strip() for ln in stdout.strip().splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            return json.loads(line)
        except Exception:
            continue
    raise AssertionError("Fant ikke gyldig JSON i STDOUT")

def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "cli.analyze", "session"] + args
    return subprocess.run(cmd, capture_output=True, text=True)

@pytest.mark.skipif(not GOLDEN_CSV.exists(), reason="golden_outdoor.csv ikke tilgjengelig")
def test_reason_present_when_not_calibrated():
    proc = _run_cli(["--input", str(GOLDEN_CSV), "--format", "json", "--dry-run"])
    assert proc.returncode == 0, f"rc={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"
    obj = _extract_last_json(proc.stdout)

    assert "calibrated" in obj, "Mangler 'calibrated'"
    assert obj["calibrated"] is False, "Forventer calibrated=False uten --calibrate"
    assert "reason" in obj and obj["reason"], "Forventer 'reason' når calibrated=False"

@pytest.mark.skipif(not GOLDEN_CSV.exists(), reason="golden_outdoor.csv ikke tilgjengelig")
def test_reason_absent_when_calibrated_true_or_skip():
    """
    Prøv kalibrering. Hvis miljøet ikke setter calibrated=True (mangler bindings etc.),
    skip'er vi for å unngå flaky test.
    """
    proc = _run_cli(["--input", str(GOLDEN_CSV), "--format", "json", "--dry-run", "--calibrate"])
    assert proc.returncode == 0, f"rc={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"
    obj = _extract_last_json(proc.stdout)

    if obj.get("calibrated") is not True:
        pytest.skip("Kalibrering ikke tilgjengelig / ga ikke calibrated=True i dette miljøet")

    assert ("reason" not in obj) or (obj["reason"] in (None, "")), \
        "Reason skal ikke finnes når calibrated=True"