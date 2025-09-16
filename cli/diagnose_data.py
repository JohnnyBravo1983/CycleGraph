#!/usr/bin/env python3
import csv
import os
import sys

def project_paths():
    script_path = os.path.abspath(__file__)
    cli_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(cli_dir)
    data_dir = os.path.join(project_root, "data")
    input_path = os.path.join(data_dir, "strava_ride_clean.csv")
    watts_only_path = os.path.join(data_dir, "strava_ride_watts_only.csv")
    return input_path, watts_only_path

def is_nonempty(s: str) -> bool:
    return s is not None and str(s).strip() != ""

def main():
    input_path, watts_only_path = project_paths()

    if not os.path.exists(input_path):
        sys.stderr.write(f"❌ Fant ikke inputfilen: {os.path.abspath(input_path)}\n")
        sys.exit(1)

    only_hr = 0
    only_watts = 0
    both = 0
    none = 0
    watts_rows = []

    with open(input_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            sys.stderr.write("❌ Fant ingen kolonneheader i CSV.\n")
            sys.exit(2)

        fieldnames = reader.fieldnames

        for row in reader:
            has_hr = is_nonempty(row.get("hr"))
            has_watts = is_nonempty(row.get("watts"))

            if has_hr and has_watts:
                both += 1
            elif has_hr and not has_watts:
                only_hr += 1
            elif has_watts and not has_hr:
                only_watts += 1
                watts_rows.append(row)
            else:
                none += 1

    # 📋 Skriv rapport
    print("📊 Data-tilstedeværelse i filen:")
    print(f"  • Begge hr+watts : {both}")
    print(f"  • Kun hr         : {only_hr}")
    print(f"  • Kun watts      : {only_watts}")
    print(f"  • Ingen av delene: {none}")

    # 📌 Foreslå neste steg
    if both == 0 and only_watts < 100 and only_hr < 100:
        print("\n⚠️  Ingen nok data til analyse. Vurder å hente en annen økt med sensordata.")
    elif both == 0 and only_watts >= 100:
        print("\nℹ️  Ingen kombinerte data, men mange watt-verdier — kan kjøre watt-effekt analyse.")
    elif both == 0 and only_hr >= 100:
        print("\nℹ️  Ingen kombinerte data, men mange pulsverdier — kan kjøre puls-basert analyse.")
    else:
        print("\n✅ Det finnes kombinerte data — bruk filter_valid_rows.py og kjør vanlig CLI-analyse.")

    # 🎁 Bonus: lag watts-only-fil hvis nok data
    if only_watts >= 100:
        os.makedirs(os.path.dirname(watts_only_path), exist_ok=True)
        with open(watts_only_path, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(watts_rows)
        print(f"💾 Watts-only fil lagret: {os.path.abspath(watts_only_path)}")

if __name__ == "__main__":
    main()