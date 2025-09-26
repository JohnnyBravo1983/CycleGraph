# tests/test__utils_smoke.py
import importlib.util
from pathlib import Path
import pytest


def _load_test_utils():
    """
    Laster tests/test_utils.py eksplisitt som modul uansett PYTHONPATH/packaging-oppsett.
    Returnerer modulen.
    """
    mod_path = Path(__file__).parent / "test_utils.py"
    assert mod_path.exists(), f"Finner ikke {mod_path}"
    spec = importlib.util.spec_from_file_location("test_utils", mod_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader, "Kunne ikke lage import-spec for test_utils"
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_test_utils_importable_and_semver():
    tu = _load_test_utils()
    # Finnes funksjoner?
    assert callable(tu.is_semver)
    assert callable(tu.assert_semver)
    # Semver happy/negative path
    assert tu.is_semver("1.2.3")
    assert not tu.is_semver("1.2")
    with pytest.raises(AssertionError):
        tu.assert_semver("1.2")  # ikke X.Y.Z


def test_csv_helpers_count_and_min_samples(tmp_path):
    tu = _load_test_utils()
    p = tmp_path / "mini.csv"
    # Skriv en liten CSV med header + 3 rader
    p.write_text(
        "time_s,speed,gradient,hr,watts\n"
        "0,5.2,0.01,142,210\n"
        "1,5.3,0.01,144,215\n"
        "2,5.4,0.02,146,220\n",
        encoding="utf-8",
    )
    # count_samples og assert_min_samples
    assert tu.count_samples(p) == 3
    with pytest.raises(AssertionError):
        tu.assert_min_samples(p, min_samples=5)

    # Utvid til 30 rader og test at kravet passeres
    with p.open("a", encoding="utf-8") as f:
        for i in range(3, 30):
            f.write(f"{i},5.{i%10},0.0{(i%3)},150,200\n")
    tu.assert_min_samples(p, min_samples=30)


def test_hr_plausibility_basic_variation():
    tu = _load_test_utils()
    hr = [120.0, 121.0, 122.0, 120.5, 121.5]
    # Ingen exceptions => OK
    tu.hr_plausibility_basic(hr, require_variation=True, min_std_tol=0.3)