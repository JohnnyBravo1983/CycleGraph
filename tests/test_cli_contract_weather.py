# tests/test_cli_contract_weather.py
from __future__ import annotations
import json, sys, subprocess, pytest
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
GOLDEN = DATA / "golden_outdoor.csv"
WX = DATA / "golden_weather.json"

pytestmark = pytest.mark.contract

def _num_or_num_list(x):
    num = (int, float)
    return isinstance(x, num) or (isinstance(x, list) and all(isinstance(v, num) for v in x))

@pytest.mark.skipif(not WX.exists(), reason="weather file not present")
def test_cli_contract_fields_with_weather():
    cmd = [sys.executable, "-m", "cli.analyze", "session",
           "--input", str(GOLDEN),
           "--weather", str(WX),
           "--format", "json", "--dry-run"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    obj = json.loads((p.stdout or "").splitlines()[-1])

    for k in ("schema_version", "status", "calibrated", "wind_rel", "v_rel"):
        assert k in obj
    assert isinstance(obj["schema_version"], str)
    assert isinstance(obj["calibrated"], bool)
    assert _num_or_num_list(obj["wind_rel"])
    assert _num_or_num_list(obj["v_rel"])

    if obj["calibrated"] is True:
        assert "reason" not in obj
    else:
        assert "reason" in obj and isinstance(obj["reason"], str) and obj["reason"]