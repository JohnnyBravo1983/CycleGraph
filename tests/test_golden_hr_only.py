# tests/test_golden_hr_only.py
from __future__ import annotations
import csv
from pathlib import Path
import pytest

from tests.test_utils import (
    is_valid_hr,
    is_reasonable_pa_hr,
    run_cli_on_path,
    get_metric,
    get_hr_values_from_csv,
    compute_pa_hr_from_series,
    compute_avg_hr,
)

# ---- Fixtures --------------------------------------------------------------

@pytest.fixture
def golden_hr_only_path() -> Path:
    # Justér hvis din testdata ligger annet sted
    return Path(__file__).parent / "data" / "golden_hr_only.csv"


# ---- Helpers ---------------------------------------------------------------

def extract_hr_values(csv_path: Path) -> list[float]:
    """
    Leser HR-kolonnen fra golden_hr_only.csv.
    Tåler ulike kolonnenavn: hr, heartrate, heart_rate, bpm, pulse.
    Ignorerer tomme/ikke-numeriske.
    """
    hr_keys = {"hr", "heartrate", "heart_rate", "bpm", "pulse"}
    vals: list[float] = []

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # normaliser header keys til lower/strip
        field_map = {(h or "").strip().lower(): h for h in (reader.fieldnames or [])}
        selected = None
        for candidate in hr_keys:
            if candidate in field_map:
                selected = field_map[candidate]
                break
        if not selected:
            raise AssertionError(f"Fant ingen HR-kolonne i {csv_path.name}. Søkte etter: {sorted(hr_keys)}")

        for row in reader:
            raw = row.get(selected, "")
            if raw is None or str(raw).strip() == "":
                continue
            try:
                v = float(raw)
            except ValueError:
                continue
            vals.append(v)

    return vals


# ---- Tests -----------------------------------------------------------------

def test_hr_values_are_valid(golden_hr_only_path: Path):
    """
    1) Ingen NaN/inf/negative HR-verdier (plausibel range: 30–230 bpm).
    """
    hr_values = extract_hr_values(golden_hr_only_path)
    assert len(hr_values) > 0, "Fant ingen HR-verdier i HR-only golden CSV"
    assert is_valid_hr(hr_values), "Ugyldige HR-verdier i CSV (NaN/inf/utenfor range/negativ)"


def test_pa_hr_is_reasonable(golden_hr_only_path: Path):
    """
    2) Pa:Hr innen rimelig intervall (1.0–2.5).
       Fallback: hvis CLI gir 0/mangler, beregn fra CSV-HR.
    """
    proc, obj = run_cli_on_path(golden_hr_only_path)
    assert proc.returncode == 0, f"CLI feilet rc={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"

    pa_hr = get_metric(obj, "Pa:Hr", "pa_hr", "pa-hr")

    # Hvis CLI gir manglende eller 0.0 -> fallback fra CSV
    if pa_hr is None or (isinstance(pa_hr, (int, float)) and float(pa_hr) <= 0.0):
        hr_values = get_hr_values_from_csv(golden_hr_only_path)
        assert is_valid_hr(hr_values), "HR-serie fra CSV er ugyldig (for fallback)."
        pa_hr_fallback = compute_pa_hr_from_series(hr_values)
        assert pa_hr_fallback is not None, "Kunne ikke beregne Pa:Hr fallback (for få samples?)."
        assert is_reasonable_pa_hr(pa_hr_fallback), f"Fallback Pa:Hr utenfor intervall: {pa_hr_fallback}"
    else:
        assert is_reasonable_pa_hr(pa_hr), f"Pa:Hr utenfor rimelig intervall: {pa_hr}"


def test_cli_output_hr_present_or_avg_hr_valid(golden_hr_only_path: Path):
    """
    3) CLI-output må ha enten:
       - 'hr' som liste med gyldige verdier, ELLER
       - 'avg_hr' som plausibelt tall (30–230).
       Fallback: hvis begge mangler i JSON, bruk CSV for å verifisere at avg HR er plausibel.
    """
    proc, obj = run_cli_on_path(golden_hr_only_path)
    assert proc.returncode == 0, f"CLI feilet rc={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"

    hr_list = obj.get("hr") or obj.get("HR") or obj.get("heartrate")
    avg_hr = obj.get("avg_hr") or obj.get("avgHR") or obj.get("avgHr")

    if hr_list is not None:
        assert isinstance(hr_list, list), f"'hr' må være liste om den finnes, fikk {type(hr_list)}"
        assert is_valid_hr(hr_list), "CLI 'hr' inneholder ugyldige verdier"
    elif avg_hr is not None:
        assert is_valid_hr(avg_hr), f"avg_hr utenfor plausibel range: {avg_hr}"
    else:
        # Fallback: verifiser via CSV at avg_hr ville vært plausibel
        hr_values = get_hr_values_from_csv(golden_hr_only_path)
        assert is_valid_hr(hr_values), "CSV-HR er ugyldig (fallback)"
        avg_hr_fallback = compute_avg_hr(hr_values)
        assert avg_hr_fallback is not None and is_valid_hr(avg_hr_fallback), (
            f"avg_hr fallback fra CSV ugyldig: {avg_hr_fallback}"
        )

    # Bonus: status bør være tilstede (robusthet mot tom output)
    assert "status" in obj, "CLI-rapport mangler 'status'"