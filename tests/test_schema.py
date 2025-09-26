# tests/test_schema.py
from pathlib import Path
import re
import pytest

@pytest.fixture
def semver_pattern():
    # SemVer 2.0.0 – tillater pre-release + build metadata
    return re.compile(
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
    )

from tests.test_utils import run_cli_json

# Ekstra: verifiser konstant og helper-idempotens direkte
from cli.session import SCHEMA_VERSION as SCHEMA_VERSION_CONST, inject_schema_version

SCHEMA_VERSION_EXPECTED = "0.7.0"  # oppdater ved schema-endring


# ── S7 helper: tillat tall ELLER liste av tall for wind_rel/v_rel ─────────────
def _is_num_or_num_list(x):
    num = (int, float)
    if isinstance(x, num):
        return True
    if isinstance(x, list) and all(isinstance(v, num) for v in x):
        return True
    return False
# ──────────────────────────────────────────────────────────────────────────────


def _run_sample():
    # Juster input om nødvendig; denne ligger normalt i repoet fra tidligere sprint
    sample = Path("tests/strava_segment.csv")
    assert sample.exists(), f"Mangler testinput: {sample}"
    return run_cli_json([
        "session",
        "--input", str(sample),
        "--format", "json",
        "--dry-run",
    ])


def test_schema_version_present_and_semver(semver_pattern):
    d = _run_sample()
    sv = d.get("schema_version", "")
    assert semver_pattern.match(sv or ""), f"schema_version mangler/ugyldig: {sv!r}"
    # S7 låser 0.7.0 (hindrer regress uten bevisst bump)
    assert sv == SCHEMA_VERSION_EXPECTED, f"Forventet schema_version {SCHEMA_VERSION_EXPECTED}, fikk {sv}"


@pytest.mark.parametrize("field", [
    "session_id", "duration_s", "samples", "avg_power",
    "np", "if_", "vi", "pa_hr", "w_per_beat",
    "precision_watt", "calibrated", "status",
    "wind_rel", "v_rel",
])
def test_required_fields_present(field):
    d = _run_sample()
    assert field in d, f"Mangler påkrevd felt: {field}"


def test_required_field_types_basic():
    d = _run_sample()
    # Typetester (basic) – vi er tolerante på int/float via isinstance med (int,float)
    num = (int, float)
    assert isinstance(d["session_id"], str)
    assert isinstance(d["duration_s"], num)
    assert isinstance(d["samples"], int)
    assert isinstance(d["avg_power"], num)
    assert isinstance(d["np"], num)
    assert isinstance(d["if_"], num)
    assert isinstance(d["vi"], num)
    assert isinstance(d["pa_hr"], num)
    assert isinstance(d["w_per_beat"], num)
    assert isinstance(d["precision_watt"], num)
    assert isinstance(d["calibrated"], bool)
    assert isinstance(d["status"], str)
    # Tolerant for tall eller liste av tall:
    assert _is_num_or_num_list(d["wind_rel"]), "wind_rel må være tall eller liste av tall"
    assert _is_num_or_num_list(d["v_rel"]), "v_rel må være tall eller liste av tall"


# ── Ekstra valideringer for S7-kontrakten ─────────────────────────────────────

def test_schema_version_constant_matches_expected(semver_pattern):
    # Konstanten i koden skal være nøyaktig 0.7.0 og valid semver
    assert SCHEMA_VERSION_CONST == SCHEMA_VERSION_EXPECTED
    assert semver_pattern.match(SCHEMA_VERSION_CONST)


def test_inject_schema_version_is_idempotent():
    # Helperen skal sette feltet hvis det mangler, men ikke overskrive/endre ellers
    r = {"session_id": "s1", "avg_power": 200.0}
    inject_schema_version(r)
    assert r["schema_version"] == SCHEMA_VERSION_EXPECTED
    # Kall igjen – verdien skal være uendret og fortsatt gyldig semver
    inject_schema_version(r)
    assert r["schema_version"] == SCHEMA_VERSION_EXPECTED