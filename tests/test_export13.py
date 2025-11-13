# tests/test_export13.py
# Rask kontraktstest for Trinn 13-eksport

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _run_export_script() -> subprocess.CompletedProcess[str]:
    """
    Kjør scripts/export_all.ps1 på en måte som funker både lokalt (Windows)
    og i CI (ubuntu-latest med pwsh).
    """
    if sys.platform.startswith("win"):
        # Windows: klassisk PowerShell
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "scripts/export_all.ps1",
        ]
    else:
        # Linux/macOS: bruk PowerShell Core (pwsh) hvis tilgjengelig
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            pytest.skip("PowerShell Core (pwsh) ikke tilgjengelig på denne plattformen")
        cmd = [
            pwsh,
            "-NoProfile",
            "-File",
            "scripts/export_all.ps1",
        ]

    return subprocess.run(cmd, capture_output=True, text=True)


def test_export13_minimal_contract():
    # Kjør eksport (skriver til export/<YYYYMMDD>/)
    ps = _run_export_script()
    assert ps.returncode == 0, f"export_all.ps1 failed: {ps.stderr}\n{ps.stdout}"

    export_root = Path("export")
    assert export_root.exists(), "export/ mangler"

    # Finn siste datomappe
    latest = sorted(
        [p for p in export_root.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[0]

    sessions = latest / "sessions.jsonl"
    assert sessions.exists(), "sessions.jsonl missing"

    # Parse 1–3 linjer for felt-sjekk
    lines: list[str] = []
    with sessions.open("r", encoding="utf-8") as f:
        for _ in range(3):
            ln = f.readline()
            if not ln:
                break
            ln = ln.strip()
            if ln:
                lines.append(ln)

    # Hvis sessions.jsonl er veldig kort, les alle linjer
    if not lines:
        lines = [
            ln.strip()
            for ln in sessions.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]

    assert (
        len(lines) >= 1
    ), "sessions.jsonl should have >= 1 line (sjekk at logs/result_*.json finnes)"

    rec = json.loads(lines[0])

    for k in ["ride_id", "profile_version", "weather_source", "metrics"]:
        assert k in rec, f"missing key: {k}"

    for mk in [
        "precision_watt",
        "drag_watt",
        "rolling_watt",
        "total_watt",
        "calibration_mae",
        "weather_source",
    ]:
        assert mk in rec["metrics"], f"missing metrics key: {mk}"
