#!/usr/bin/env python3
import argparse
import csv
import os
import sys

def resolve_paths():
    """
    Prosjektstruktur antatt:
      CycleGraph/
        ├─ cli/filter_valid_rows.py   <-- __file__
        └─ data/strava_ride_clean.csv
    """
    script_path = os.path.abspath(__file__)
    cli_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(cli_dir)
    data_dir = os.path.join(project_root, "data")
    default_in = os.path.join(data_dir, "strava_ride_clean.csv")
    default_out = os.path.join(data_dir, "strava_ride_filtered.csv")
    return default_in, default_out

def is_nonempty(s: str) -> bool:
    return s is not None and str(s).strip() != ""

def main():
    parser = argparse.ArgumentParser(
        description="Filtrer bort rader uten hr/watts fra Strava CSV."
    )
    parser.add_argument("-i", "--input", help="Sti til input CSV (default: <repo>/data/strava_ride_clean.csv)")
    parser.add_argument("-o", "--output", help="Sti til output CSV (default: <repo>/data/strava_ride_filtered.csv)")
    args = parser.parse_args()

    default_in, default_out = resolve_paths()
    input_path = os.path.abspath(args.input) if args.input else os.path.abspath(default_in)
    output_path = os.path.abspath(args.output) if args.output else os.path.abspath(default_out)

    if not os.path.exists(input_path):
        sys.stderr.write(
            "\n❌ Fant ikke input-filen.\n"
            f"   Forventet plassering: {input_path}\n\n"
            "✅ Forslag:\n"
            f"  • Legg filen her: {os.path.abspath(default_in)}\n"
            "  • Eller oppgi eksplisitt sti:\n"
            "    python cli/filter_valid_rows.py --input /full/sti/strava_ride_clean.csv\n\n"
        )
        sys.exit(1)

    # Les, filtrer og skriv ut statistikk
    try:
        with open(input_path, "r", encoding="utf-8", newline="") as f_in:
            reader = csv.DictReader(f_in)
            if reader.fieldnames is None:
                sys.stderr.write("❌ Fant ingen header i CSV.\n")
                sys.exit(2)

            # Behold samme feltrekkefølge i output
            fieldnames = list(reader.fieldnames)

            filtered_rows = []
            total = 0
            for row in reader:
                total += 1
                hr = row.get("hr", "")
                watts = row.get("watts", "")
                if is_nonempty(hr) and is_nonempty(watts):
                    filtered_rows.append(row)

        valid_count = len(filtered_rows)
        print(f"✅ Antall gyldige rader: {valid_count} (av {total})")
        if valid_count < 100:
            print("⚠️  Advarsel: Mindre enn 100 gyldige rader — økten kan være for kort eller mangler sensordata.")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_rows)

        print(f"💾 Filtrert fil lagret: {output_path}")

    except Exception as e:
        sys.stderr.write(f"❌ Uventet feil under behandling: {e}\n")
        sys.exit(3)

if __name__ == "__main__":
    main()