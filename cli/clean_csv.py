#!/usr/bin/env python3
import argparse
import csv
import os
import sys
import unicodedata

# ---------------- Utils ----------------

def normalize_col(name: str) -> str:
    """Trim, normaliser og lower kolonnenavn; fjerner zero-width chars."""
    if name is None:
        return ""
    n = unicodedata.normalize("NFKC", name)
    n = n.replace("\u200b", "")  # zero-width space
    return n.strip().lower()

def project_paths():
    """
    Finn prosjektrot og standard data-stier relativt til denne fila.
    Forventet struktur:
      CycleGraph/
        ├─ cli/clean_csv.py  <-- __file__
        └─ data/strava_ride.csv
    """
    script_path = os.path.abspath(__file__)
    cli_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(cli_dir)
    data_dir = os.path.join(project_root, "data")
    default_in = os.path.join(data_dir, "strava_ride.csv")
    default_out = os.path.join(data_dir, "strava_ride_clean.csv")
    return project_root, default_in, default_out

def read_and_clean_csv(input_path):
    """Les CSV med utf-8-sig, rens header, returner (clean_fieldnames, rows)."""
    with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Fant ingen header i CSV (fieldnames=None).")

        original_fields = list(reader.fieldnames)
        clean_fields = [normalize_col(h) for h in original_fields]

        rows = []
        for row in reader:
            clean_row = {}
            # Bevar rekkefølge ved å mappe original->renset navn én-til-én
            for orig, clean in zip(original_fields, clean_fields):
                clean_row[clean] = row.get(orig, "")
            rows.append(clean_row)

        return clean_fields, rows

def write_csv(output_path, fieldnames, rows):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

# ---------------- Main ----------------

def main():
    parser = argparse.ArgumentParser(
        description="Rens Strava CSV: normaliser kolonnenavn og skriv renset kopi."
    )
    parser.add_argument(
        "-i", "--input",
        help="Sti til input CSV. Hvis utelatt, brukes <repo>/data/strava_ride.csv"
    )
    parser.add_argument(
        "-o", "--output",
        help="Sti til output CSV. Hvis utelatt, brukes <repo>/data/strava_ride_clean.csv"
    )
    args = parser.parse_args()

    project_root, default_in, default_out = project_paths()

    # Viktig: bruk __file__-baserte standardstier hvis argument ikke er oppgitt
    input_path = os.path.abspath(args.input) if args.input else os.path.abspath(default_in)
    output_path = os.path.abspath(args.output) if args.output else os.path.abspath(default_out)

    if not os.path.exists(input_path):
        # Tydelig feilmelding med absolutt sti + forslag
        sys.stderr.write(
            "\n❌ Fant ikke input-filen.\n"
            f"   Forventet plassering: {input_path}\n\n"
            "✅ Forslag til løsninger:\n"
            f"  1) Legg filen her: {os.path.abspath(default_in)}\n"
            "  2) Eller kjør med eksplisitt sti, f.eks.:\n"
            "     python cli/clean_csv.py --input /full/sti/til/strava_ride.csv\n"
            f"  3) Sjekk at prosjektroten er korrekt: {project_root}\n\n"
        )
        sys.exit(1)

    try:
        clean_fields, rows = read_and_clean_csv(input_path)
    except Exception as e:
        sys.stderr.write(f"❌ Feil ved lesing/parsing av CSV: {e}\n")
        sys.exit(2)

    # Output: kolonner + 5 første rader
    print("🧼 Rensede kolonnenavn:")
    print(clean_fields)

    print("\n📋 Første 5 rader:")
    for r in rows[:5]:
        print(r)

    try:
        write_csv(output_path, clean_fields, rows)
        print(f"\n💾 Renset fil lagret: {output_path}")
    except Exception as e:
        sys.stderr.write(f"❌ Feil ved skriving av renset CSV: {e}\n")
        sys.exit(3)

if __name__ == "__main__":
    main()