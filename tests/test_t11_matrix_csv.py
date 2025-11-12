# tests/test_t11_matrix_csv.py
import csv
from pathlib import Path

REQUIRED = [
    "git_sha","profile_version","weather_source","ride_id",
    "precision_watt","drag_watt","rolling_watt","total_watt","calibration_mae"
]

def test_t11_csv_contract():
    p = Path("artifacts/t11_matrix.csv")
    assert p.exists(), "mangler t11_matrix.csv (kjør scripts/T11_Run_Matrix.ps1)"
    with p.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        assert r.fieldnames == REQUIRED, f"Feil header: {r.fieldnames}"
        rows = list(r)
        assert len(rows) == 5, f"Forventet 5 rader, fikk {len(rows)}"
        for i, row in enumerate(rows, 1):
            for col in ("precision_watt","drag_watt","rolling_watt","total_watt"):
                v = row.get(col, "")
                assert v not in ("", None), f"Rad {i}: {col} tom"
                float(v)
