from __future__ import annotations
import argparse
from pathlib import Path
import sys, os
# add repo root to sys.path (this file lives in /scripts)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from server.analysis.trend9 import collect_records, save_pivots, trend_summary, robustness_check

def main():
    ap = argparse.ArgumentParser("Trinn 9 – Trendanalyse (E2E-output)")
    ap.add_argument("--log-dir", default="logs/actual10/latest", help="Mappen med result_*.json + session_*.json")
    ap.add_argument("--out-dir", default=None, help="Skriver artefakter her (default=log-dir)")
    args = ap.parse_args()

    log_dir = Path(args.log_dir)
    out_dir = Path(args.out_dir) if args.out_dir else log_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    df = collect_records(log_dir)
    pivots = save_pivots(df, out_dir)
    summary = trend_summary(df, out_dir)
    ok, anomalies = robustness_check(df, out_dir)

    print("[T9] records:", len(df))
    print("[T9] pivots:", len(pivots))
    print("[T9] summary:", summary)
    print("[T9] anomalies:", anomalies)
    print("[T9] robustness_ok:", ok)
    return 0 if ok else 2

if __name__ == "__main__":
    raise SystemExit(main())

