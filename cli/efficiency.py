# cli/efficiency.py
import argparse
import os
import sys
import json

from cli.io import read_efficiency_csv
from cli.eff_calc import _calc_eff_series  # ← ikke fra analyze lenger
from cli.weather_client_mock import WeatherClient
# from cli.validation import validate_rdf  # aktiver når SHACL brukes

from cli.weather_client_mock import WeatherClient  # legg denne øverst i efficiency.py

def cmd_efficiency(args: argparse.Namespace) -> int:
    if getattr(args, "dry_run", False):
        # 🔍 Mock værdata for test
        weather = WeatherClient().get_weather(lat=59.43, lon=10.66, timestamp="2023-06-01T12:00:00Z")
        print("Weather:", weather)
        print("✅ cmd_efficiency triggered with --dry-run =", args.dry_run)
        return 0

    if not getattr(args, "file", None):
        print("Feil: --file er påkrevd uten --dry-run", file=sys.stderr)
        return 2

    watts, pulses = read_efficiency_csv(args.file)
    avg_eff, session_status, per_point_eff, per_point_status = _calc_eff_series(watts, pulses)

    print("\n📊 CycleGraph Report (Efficiency)")
    print("=================================")
    print(f"Snitteffektivitet: {avg_eff:.2f} watt/puls")
    print(f"Øktstatus: {session_status}\n")

    print("Per datapunkt:")
    for i, (eff, status) in enumerate(zip(per_point_eff, per_point_status), start=1):
        print(f"  Punkt {i}: {eff:.2f} watt/puls – {status}")

    if getattr(args, "json", None):
        # 🔍 Mock værdata for JSON-output
        weather = WeatherClient().get_weather(lat=59.43, lon=10.66, timestamp="2023-06-01T12:00:00Z")

        report_data = {
            "average_efficiency": round(avg_eff, 2),
            "session_status": session_status,
            "weather": weather,
            "points": [
                {"point": i + 1, "efficiency": round(eff, 2), "status": status}
                for i, (eff, status) in enumerate(zip(per_point_eff, per_point_status))
            ],
        }
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Rapport lagret som JSON: {args.json}")

    return 0