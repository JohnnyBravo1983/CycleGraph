# tests/test_export13.py
# Rask kontraktstest for Trinn 13-eksport
import json
from pathlib import Path
import subprocess
import sys

def test_export13_minimal_contract():
    # Kjør eksport (skriver til export/<YYYYMMDD>/)
    ps = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "scripts/export_all.ps1"], capture_output=True, text=True)
    assert ps.returncode == 0, f"export_all.ps1 failed: {ps.stderr}\n{ps.stdout}"

    export_root = Path("export")
    assert export_root.exists()

    latest = sorted([p for p in export_root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)[0]
    sessions = latest / "sessions.jsonl"
    assert sessions.exists(), "sessions.jsonl missing"

    # Parse 1–3 linjer for felt-sjekk
    with sessions.open("r", encoding="utf-8") as f:
        lines = [next(f).strip() for _ in range(3) if not f.tell() == 0]
    # Hvis sessions.jsonl kan være kort, les alle
    if not lines:
        lines = [ln.strip() for ln in sessions.read_text(encoding="utf-8").splitlines() if ln.strip()]

    assert len(lines) >= 1, "sessions.jsonl should have >= 1 line (ensure logs/result_*.json exist from earlier trinn)"

    rec = json.loads(lines[0])
    for k in ["ride_id", "profile_version", "weather_source", "metrics"]:
        assert k in rec, f"missing key: {k}"
    for mk in ["precision_watt", "drag_watt", "rolling_watt", "total_watt", "calibration_mae", "weather_source"]:
        assert mk in rec["metrics"], f"missing metrics key: {mk}"
