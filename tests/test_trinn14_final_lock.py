# tests/test_trinn14_final_lock.py
from __future__ import annotations
import os, re, json, csv
from pathlib import Path
import pytest

def _latest_export_dir() -> Path | None:
    root = Path("export")
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir() and re.fullmatch(r"\d{8}", p.name)]
    if not dirs:
        return None
    return sorted(dirs)[-1]

@pytest.mark.order(-1)
def test_final14_export_and_lock():
    d = _latest_export_dir()
    if d is None:
        pytest.skip("Final14 ikke kjørt (ingen export/YYYYMMDD).")

    sessions = d / "sessions.jsonl"
    t11csv   = d / "t11_matrix.csv"
    manifest = d / "final14_manifest.json"

    assert sessions.exists(), "sessions.jsonl mangler i eksport."
    assert t11csv.exists(), "t11_matrix.csv mangler i eksport."
    assert manifest.exists(), "final14_manifest.json mangler."

    rows = []
    with sessions.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    assert len(rows) >= 5, "Forventer minst 5 sessions i slutt-eksport (≥ golden rides)."

    # Speilings- og ikke-null-krav
    for r in rows:
        m = r.get("metrics") or {}
        assert r.get("ride_id"), "ride_id mangler"
        assert r.get("profile_version"), "profile_version mangler"
        assert r.get("weather_source") is not None, "weather_source mangler"
        assert (r.get("profile_used") or {}).get("profile_version") == r.get("profile_version"), "profile_version ikke speilet i profile_used"
        assert (m.get("weather_source") == r.get("weather_source")), "weather_source ikke speilet i metrics"
        assert m.get("precision_watt") is not None, "precision_watt må være ikke-null i Final"
        assert m.get("total_watt") is not None, "total_watt må være ikke-null i Final"
