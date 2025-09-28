# tests/conftest.py
import os
import sys
from pathlib import Path
import re
import pytest

# Sørg for at prosjektets rot er på sys.path slik at imports fungerer i tester
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# --- Generelle fixtures ------------------------------------------------------

@pytest.fixture(scope="session")
def data_dir() -> Path:
    """
    Rotkatalog for testdata.
    Justér her hvis datastrukturen endres (unngår hardkoding i mange tester).
    """
    return Path("tests/data")


@pytest.fixture(scope="session")
def semver_pattern():
    """
    Kompilert regex for semver X.Y.Z (kun siffer, uten prerelease/build).
    Brukes i schema-tester.
    """
    return re.compile(r"^\d+\.\d+\.\d+$")


@pytest.fixture
def env_log_level(monkeypatch):
    """
    Enkel måte å styre loggnivå i tester som kjører CLI.
    Bruk: def test_x(env_log_level): ... (default INFO)
    """
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    return "INFO"


# --- Golden-datasett fixtures ------------------------------------------------

@pytest.fixture
def golden_indoor_path(data_dir: Path) -> Path:
    """
    Path til golden indoor CSV-datasett.
    Skipper testen med forklarende melding hvis filen mangler.
    """
    p = data_dir / "golden_indoor.csv"
    if not p.exists():
        pytest.skip(f"Mangler testdatasett: {p}")
    return p


@pytest.fixture
def golden_outdoor_path(data_dir: Path) -> Path:
    """
    Path til golden outdoor CSV-datasett.
    Skipper testen med forklarende melding hvis filen mangler.
    """
    p = data_dir / "golden_outdoor.csv"
    if not p.exists():
        pytest.skip(f"Mangler testdatasett: {p}")
    return p


@pytest.fixture
def golden_hr_only_path(data_dir: Path) -> Path:
    """
    Path til golden HR-only CSV-datasett (uten powermeter).
    Skipper testen med forklarende melding hvis filen mangler.
    """
    p = data_dir / "golden_hr_only.csv"
    if not p.exists():
        pytest.skip(f"Mangler testdatasett: {p}")
    return p


@pytest.fixture
def all_golden_paths(golden_indoor_path, golden_outdoor_path, golden_hr_only_path):
    """
    Samlefixture når tester skal loope over alle goldens.
    """
    return {
        "indoor": golden_indoor_path,
        "outdoor": golden_outdoor_path,
        "hr_only": golden_hr_only_path,
    }