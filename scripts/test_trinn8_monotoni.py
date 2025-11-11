# tests/test_trinn8_monotoni.py
import csv
from collections import defaultdict
from pathlib import Path

CSV = Path("logs/trinn8-sweep_matrix.csv")

def _rows():
    with CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            yield {
                "cda": float(r["cda"].replace(",", ".")),
                "crr": float(r["crr"].replace(",", ".")),
                "w": float(r["weight_kg"].replace(",", ".")),
                "eff": float(r["crank_eff_pct"].replace(",", ".")),
                "drag": float(r["drag_watt"].replace(",", ".")),
                "roll": float(r["rolling_watt"].replace(",", ".")),
                "prec": float(r["precision_watt"].replace(",", ".")),
            }

def test_drag_invariant_over_crr_weight_eff_per_cda():
    by_cda = defaultdict(list)
    for r in _rows():
        by_cda[r["cda"]].append(r["drag"])
    for cda, values in by_cda.items():
        assert max(values) == min(values), f"drag not invariant for CdA={cda}"

def test_drag_increases_with_cda():
    # sjekk per (crr,w,eff)
    buckets = defaultdict(list)
    for r in _rows():
        key = (r["crr"], r["w"], r["eff"])
        buckets[key].append((r["cda"], r["drag"]))
    for key, arr in buckets.items():
        arr = sorted(arr)
        vals = [v for _, v in arr]
        assert all(vals[i] < vals[i+1] for i in range(len(vals)-1)), f"drag↗ vs CdA failed for {key}"

def test_rolling_increases_with_crr():
    # sjekk per (cda,w,eff)
    buckets = defaultdict(list)
    for r in _rows():
        key = (r["cda"], r["w"], r["eff"])
        buckets[key].append((r["crr"], r["roll"]))
    for key, arr in buckets.items():
        arr = sorted(arr)
        vals = [v for _, v in arr]
        assert all(vals[i] < vals[i+1] for i in range(len(vals)-1)), f"rolling↗ vs Crr failed for {key}"

def test_rolling_increases_with_weight():
    # sjekk per (cda,crr,eff)
    buckets = defaultdict(list)
    for r in _rows():
        key = (r["cda"], r["crr"], r["eff"])
        buckets[key].append((r["w"], r["roll"]))
    for key, arr in buckets.items():
        arr = sorted(arr)
        vals = [v for _, v in arr]
        assert all(vals[i] < vals[i+1] for i in range(len(vals)-1)), f"rolling↗ vs weight failed for {key}"
