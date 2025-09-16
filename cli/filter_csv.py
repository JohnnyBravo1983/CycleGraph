#!/usr/bin/env python3
import csv
import os
import sys

# Finn prosjektrot og data-stier relativt til denne fila
def project_paths():
    script_path = os.path.abspath(__file__)
    cli_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(cli_dir)
    data_dir = os.path.join(project_root, "data")
    input_path = os.path.join(data_dir, "strava_ride_clean.csv")
    output_path = os.path.join(data_dir, "strava_ride_filtered.csv")
    return input_path, output_path

def main():
    input_path, output_path = project_paths()

    if not os.path.exists(input_path):
        sys.stderr.write(
            f"❌ Fant ikke inputfilen: {os.path.abspath(input_path)}\n"
        )
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            sys.stderr.write("❌ Fant ingen kolonneheader i CSV.\n")
            sys.exit(2)

        rows = []
        for row in reader:
            hr = row.get("hr", "").strip()
            watts = row.get("watts", "").strip()
            if hr and watts:  # behold kun hvis begge har verdi
                rows.append(row)

    valid_count = len(rows)
    print(f"✅ Antall gyldige rader: {valid_count}")

    if valid_count < 100:
        print("⚠️  Advarsel: Mindre enn 100 gyldige rader — økten kan være for kort eller mangler sensordata.")

    # Skriv til ny CSV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"💾 Filtrert fil lagret: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()