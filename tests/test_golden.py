import sys, json, subprocess, csv
from pathlib import Path

# ⬇️ point to where your files actually are
GOLDEN_CSV = Path("tests/test_golden_segment.csv")
GOLDEN_WX  = Path("tests/weather.json")

def _extract_last_json(stdout: str):
    blocks, depth, start, in_str, escape = [], 0, None, False, False
    s = stdout or ""
    for i, ch in enumerate(s):
        if start is None:
            if ch in "{[":
                start, depth, in_str, escape = i, 1, False, False
        else:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch in "{[":
                    depth += 1
                elif ch in "}]":
                    depth -= 1
                    if depth == 0:
                        blocks.append(s[start:i+1]); start = None
    assert blocks, f"No JSON in stdout:\n{stdout}"
    for b in reversed(blocks):
        try:
            return json.loads(b)
        except Exception:
            pass
    raise AssertionError(f"No valid JSON in stdout:\n{stdout}")

def _read_speed_series(csv_path: Path):
    speeds = []
    with csv_path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            v = row.get("speed")
            if v:
                try:
                    speeds.append(float(v))
                except ValueError:
                    pass
    # lag v_mid (gj.snitt av to nabopunkter)
    v_mid = []
    for i in range(1, len(speeds)):
        v_mid.append(0.5 * (speeds[i] + speeds[i-1]))
    return v_mid

def test_golden_segment_output():
    cmd = [
        sys.executable, "-m", "cli.analyze", "session",
        "--input", str(GOLDEN_CSV),
        "--weather", str(GOLDEN_WX),
        "--format", "json",
        "--calibrate",
        "--dry-run",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout, stderr = proc.stdout or "", proc.stderr or ""
    assert proc.returncode == 0, f"CLI failed rc={proc.returncode}\nSTDERR:\n{stderr}\nSTDOUT:\n{stdout}"

    obj = _extract_last_json(stdout)
    assert isinstance(obj, dict), f"Expected dict, got {type(obj)}"

    # Required fields
    for k in ("watts", "wind_rel", "v_rel", "calibrated", "status"):
        assert k in obj, f"Missing key: {k}"

    watts    = obj["watts"] or []
    wind_rel = obj["wind_rel"] or []
    v_rel    = obj["v_rel"] or []

    v_mid = _read_speed_series(GOLDEN_CSV)
    assert v_mid, "No v_mid speeds read from golden CSV"
    n = min(len(watts), len(wind_rel), len(v_rel), len(v_mid))
    assert n > 0, "Empty series"

    # NOTE on sign: in core physics we defined positive wind_rel = headwind (motvind).
    EPS = 1e-6
    for i in range(1, n):  # hopper over første sample
        w  = float(watts[i])
        wr = float(wind_rel[i])
        vr = float(v_rel[i])
        vm = float(v_mid[i])

        # If you really want device_watts ~= 200–250, change this to check the CSV field instead.
        assert w >= 0.0, f"watts[{i}]={w} should be non-negative"

        if wr == 0.0:
            continue  # hopper over samples uten vindkomponent
        assert wr > 0.0, f"wind_rel[{i}]={wr} should be positive for headwind (motvind)"

        assert vr > (vm - wr) - EPS, f"v_rel[{i}]={vr} <= v_mid[{i}] - wind_rel[{i}] ({vm} - {wr})"

    # Accept both new (bool) and legacy ("Ja"/"Nei") formats for 'calibrated'
    cal = obj.get("calibrated", None)
    if isinstance(cal, bool):
        pass  # OK: ny kontrakt (bool)
    elif cal in ("Ja", "Nei"):
        pass  # OK: legacy streng
    else:
        assert False, f"Ugyldig 'calibrated' type/verdi: {cal!r}"

    assert obj["status"] in ("OK", "Lav", "Høy puls", "LIMITED")

    # Helpful when running with --capture=no
    print(json.dumps(obj, ensure_ascii=False, indent=2))