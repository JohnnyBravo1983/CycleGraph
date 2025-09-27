import sys
import csv
import subprocess
from pathlib import Path
import pytest
import json
import re

def _extract_last_json(s: str):
    """
    Robust: Finn siste gyldige JSON-objekt i stdout.
    1) Prøv baklengs gjennom linjer (vanligvis er JSON én linje).
    2) Som fallback: finn alle { ... } ikke-grådig, og returner siste som kan json.loads.
    """
    # 1) Linje-for-linje (baklengs)
    for line in reversed((s or "").splitlines()):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            return json.loads(line)
        except Exception:
            continue

    # 2) Fallback: ikke-grådig match av objekt-fragmenter
    last_ok = None
    for m in re.finditer(r"\{.*?\}", s or "", re.DOTALL):
        frag = m.group(0)
        try:
            last_ok = json.loads(frag)
        except Exception:
            pass
    return last_ok

# --- Fixtures for filstier ----------------------------------------------------

@pytest.fixture
def golden_outdoor_path() -> Path:
    return Path("tests/data/golden_outdoor.csv")

@pytest.fixture
def golden_hr_only_path() -> Path:
    return Path("tests/data/golden_hr_only.csv")

# --- Intern helper: kjør CLI og parse JSON -----------------------------------

def _run_cli(input_path: Path, weather_path: Path | None = None):
    """
    Kjør CLI 'session' mot input_path. Returner (proc, obj) der:
      - proc: CompletedProcess
      - obj: dict eller None (sist printede JSON-objekt ved rc==0)
    """
    cmd = [
        sys.executable, "-m", "cli.analyze", "session",
        "--input", str(input_path),
        "--format", "json",
        "--calibrate",
        "--dry-run",
    ]
    if weather_path is not None:
        cmd += ["--weather", str(weather_path)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout, stderr = proc.stdout or "", proc.stderr or ""

    obj = None
    if proc.returncode == 0:
        obj = _extract_last_json(stdout)
    return proc, obj

# --- 1) Manglende værdata -----------------------------------------------------

def test_missing_weather(golden_outdoor_path: Path):
    """
    Kjør outdoor uten --weather. Forvent:
      - Ingen crash (rc==0)
      - JSON-objekt returneres
      - 'status' finnes (innholdsdetaljer kan variere uten vær)
    """
    proc, obj = _run_cli(golden_outdoor_path, weather_path=None)
    assert proc.returncode == 0, f"CLI failed rc={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"
    assert isinstance(obj, dict), "Expected dict JSON output"
    assert "status" in obj, "Missing 'status' in output"

# --- 2) GPS-drift (store hopp i posisjon) ------------------------------------

def test_gps_drift(tmp_path: Path, golden_outdoor_path: Path):
    """
    Lag en midlertidig CSV der vi injiserer kunstig GPS-drift.
    Forvent:
      - Ingen crash (rc==0)
      - JSON-objekt med 'status'
    """
    drift_path = tmp_path / "outdoor_drift.csv"

    # Les original, injiser drift på noen rader
    with golden_outdoor_path.open("r", encoding="utf-8", newline="") as f_in:
        rdr = csv.DictReader(f_in)
        rows = list(rdr)
        fieldnames = rdr.fieldnames or ["time_s", "latitude", "longitude", "v_ms", "hr", "watts"]

    if len(rows) >= 15:
        # store hopp ved ~1/3 og ~2/3 av fila
        idxs = [len(rows)//3, (2*len(rows))//3]
        for i in idxs:
            try:
                rows[i]["latitude"]  = str(float(rows[i]["latitude"])  + 0.25)
                rows[i]["longitude"] = str(float(rows[i]["longitude"]) - 0.25)
            except Exception:
                # Hvis felter mangler/ikke-flyt, hopp rolig over
                pass

    with drift_path.open("w", encoding="utf-8", newline="") as f_out:
        w = csv.DictWriter(f_out, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    proc, obj = _run_cli(drift_path, weather_path=None)
    assert proc.returncode == 0, f"CLI failed rc={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"
    assert isinstance(obj, dict), "Expected dict JSON output"
    assert "status" in obj, "Missing 'status' in output"

# --- 3) Null HR (HR = 0) -----------------------------------------------------

def test_null_hr(tmp_path: Path, golden_hr_only_path: Path):
    """
    Sett all HR=0 i en kopi av HR-only datasettet.
    Forvent:
      - Ingen crash (rc==0)
      - JSON-objekt med 'status'
      - Hvis avg_hr finnes, skal den være >= 0
    """
    hr0_path = tmp_path / "hr_only_zero.csv"

    with golden_hr_only_path.open("r", encoding="utf-8", newline="") as f_in:
        rdr = csv.DictReader(f_in)
        rows = list(rdr)
        fieldnames = rdr.fieldnames or ["time_s", "hr"]

    for r in rows:
        if "hr" in r:
            r["hr"] = "0"

    with hr0_path.open("w", encoding="utf-8", newline="") as f_out:
        w = csv.DictWriter(f_out, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    proc, obj = _run_cli(hr0_path, weather_path=None)
    assert proc.returncode == 0, f"CLI failed rc={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"
    assert isinstance(obj, dict), "Expected dict JSON output"
    assert "status" in obj, "Missing 'status' in output"
    if "avg_hr" in obj and obj["avg_hr"] is not None:
        assert obj["avg_hr"] >= 0, f"avg_hr should be >= 0, got {obj['avg_hr']}"

# --- 4) Kort økt (<10 samples) -----------------------------------------------

def test_short_session(tmp_path: Path):
    """
    Lag en kunstig HR-only sesjon med 8 samples.
    Forvent:
      - Enten (A) rc==0 og gyldig JSON
      - Eller (B) kontrollert feilmelding i stderr (inneholder hint som 'short', 'few', '<10', 'minimum')
    Begge to er OK så lenge det ikke crasher ukontrollert.
    """
    short_path = tmp_path / "short_hr_only.csv"

    fieldnames = ["time_s", "hr"]
    rows = [{"time_s": str(i), "hr": str(140 + (i % 4))} for i in range(8)]

    with short_path.open("w", encoding="utf-8", newline="") as f_out:
        w = csv.DictWriter(f_out, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    proc, obj = _run_cli(short_path, weather_path=None)

    if proc.returncode == 0:
        # OK: CLI håndterte kort økt uten crash
        assert isinstance(obj, dict), "Expected dict JSON output"
        assert "status" in obj, "Missing 'status' in output"
    else:
        # OK: Kontrollert feilmelding
        msg = (proc.stderr or "").lower()
        ok_terms = ["short", "few", "<10", "minimum", "too short", "for få", "kort"]
        assert any(t in msg for t in ok_terms), f"Forventet kontrollert kort-økt-feil i stderr, fikk:\n{proc.stderr}"