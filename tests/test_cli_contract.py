# tests/test_cli_contract.py
from __future__ import annotations
import json
import sys
import subprocess
import pytest
from pathlib import Path

# ---- Helpers ---------------------------------------------------------------

HERE = Path(__file__).parent
DATA = HERE / "data"
GOLDEN = DATA / "golden_outdoor.csv"

def _num_or_num_list(x):
    num = (int, float)
    return isinstance(x, num) or (isinstance(x, list) and all(isinstance(v, num) for v in x))

def _last_json(stdout: str) -> dict:
    lines = [ln for ln in (stdout or "").splitlines() if ln.strip()]
    assert lines, "STDOUT was empty (no JSON lines)"
    return json.loads(lines[-1])

# ---- Tests ----------------------------------------------------------------

@pytest.mark.contract
def test_cli_contract_fields_without_weather():
    """
    Kontraktstest (ingen vær): sjekk kun felt/typer, ikke tall.
    """
    cmd = [
        sys.executable, "-m", "cli.analyze", "session",
        "--input", str(GOLDEN),
        "--format", "json",
        "--dry-run",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, f"rc={p.returncode}\nSTDERR:\n{p.stderr}\nSTDOUT:\n{p.stdout}"

    obj = _last_json(p.stdout)

    # Påkrevde nøkler
    for k in ("schema_version", "status", "calibrated", "wind_rel", "v_rel"):
        assert k in obj, f"Missing key: {k}"

    # Typer og kontrakter
    assert isinstance(obj["schema_version"], str)
    assert isinstance(obj["status"], str)
    assert isinstance(obj["calibrated"], bool)
    assert _num_or_num_list(obj["wind_rel"])
    assert _num_or_num_list(obj["v_rel"])

    # Reason-regel:
    if obj["calibrated"] is True:
        assert "reason" not in obj, "reason skal utebli når calibrated=True"
    else:
        assert "reason" in obj and isinstance(obj["reason"], str) and obj["reason"], \
            "reason må finnes og være en kort streng når calibrated=False"


@pytest.mark.e2e
def test_cli_stdout_is_only_json_and_logs_are_stderr():
    """
    E2E: STDOUT skal kun inneholde 1 gyldig JSON-linje.
    Logger skal på STDERR (heuristikk: vi forventer 'level'/'Profil' e.l.).
    """
    cmd = [
        sys.executable, "-m", "cli.analyze", "session",
        "--input", str(GOLDEN),
        "--format", "json",
        "--dry-run",
        "--log-level", "debug",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, f"rc={p.returncode}\nSTDERR:\n{p.stderr}\nSTDOUT:\n{p.stdout}"

    out_lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip()]
    assert len(out_lines) == 1, f"Forventet én JSON-linje på STDOUT, fikk {len(out_lines)}"
    _ = json.loads(out_lines[0])  # parse OK

    # Heuristikk på STDERR: enten strukturerte logger ("level") eller våre _stderr-meldinger
    stderr_lower = (p.stderr or "").lower()
    assert ("level" in stderr_lower) or ("profil:" in stderr_lower) or ("debug" in stderr_lower) \
        or ("ingen overstyring" in stderr_lower), \
        "Forventer logger på STDERR; fant ikke kjente markører"