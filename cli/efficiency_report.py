#!/usr/bin/env python3
import argparse
import csv
import os
import sys
from statistics import median

# ---------- Path helpers ----------

def resolve_defaults():
    """
    Forventet struktur:
      CycleGraph/
        ├─ cli/efficiency_report.py   <-- __file__
        └─ data/strava_ride_clean.csv
    """
    script = os.path.abspath(__file__)
    cli_dir = os.path.dirname(script)
    project_root = os.path.dirname(cli_dir)
    data_dir = os.path.join(project_root, "data")
    out_dir = os.path.join(project_root, "output")

    default_input = os.path.join(data_dir, "strava_ride_clean.csv")
    default_output = os.path.join(out_dir, "efficiency_report.txt")
    return project_root, default_input, default_output

# ---------- Core ----------

def is_nonempty(v):
    return v is not None and str(v).strip() != ""

def parse_float(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None

def load_valid_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames is None:
            raise ValueError("Fant ingen header i CSV.")
        rows_all = list(r)

    valid = []
    for row in rows_all:
        hr = parse_float(row.get("hr"))
        w = parse_float(row.get("watts"))
        if hr is not None and hr > 0 and w is not None and w >= 0:
            # Gyldig datapunkt (begge finnes)
            valid.append(row)
    return valid

def compute_w_per_beat(row):
    hr = parse_float(row.get("hr"))
    w = parse_float(row.get("watts"))
    if hr and hr > 0 and w is not None:
        return w / hr
    return None

def classify(delta_pct):
    """
    Enkel vurdering relativt til sesjonsmedian for W/beat.
    """
    if delta_pct is None:
        return "n/a"
    x = abs(delta_pct)
    if x <= 5:
        return "stabil"
    elif x <= 12:
        return "moderat avvik"
    else:
        return "utligger"

def fmt_num(x, n=2):
    try:
        return f"{x:.{n}f}"
    except Exception:
        return str(x)

def build_line(idx, row, wpb, delta_pct, baseline):
    time_s = row.get("time_s")
    index = row.get("index")
    w = parse_float(row.get("watts"))
    hr = parse_float(row.get("hr"))
    tag = classify(delta_pct)
    # Velg en identifikator (time_s hvis finnes, ellers index)
    ident = f"t={int(float(time_s))}s" if is_nonempty(time_s) else f"idx={index if is_nonempty(index) else idx}"
    if delta_pct is None:
        delta_str = "Δ n/a"
    else:
        sign = "+" if delta_pct >= 0 else ""
        delta_str = f"Δ {sign}{fmt_num(delta_pct,1)}% vs med {fmt_num(baseline,3)}"
    return (f"{ident} | watts={fmt_num(w,0)}  hr={fmt_num(hr,0)}  "
            f"w/beat={fmt_num(wpb,3)}  {delta_str}  → {tag}")

def main():
    project_root, default_input, default_output = resolve_defaults()

    p = argparse.ArgumentParser(
        description="Skriv ut alle gyldige effektivitetspunkter (watts/hr) med vurdering."
    )
    p.add_argument("-i", "--input", help=f"Input CSV (default: {default_input})")
    p.add_argument("-l", "--limit", type=int, default=None,
                   help="Begrens antall linjer (f.eks. --limit 100). Default: ingen grense.")
    p.add_argument("-o", "--outfile", nargs="?", const="__DEFAULT__", default=None,
                   help="Lagre rapport til fil (default path hvis ingen verdi oppgis).")
    args = p.parse_args()

    input_path = os.path.abspath(args.input) if args.input else os.path.abspath(default_input)
    if not os.path.exists(input_path):
        sys.stderr.write(
            "\n❌ Fant ikke input-filen.\n"
            f"   Forventet plassering: {input_path}\n\n"
            "✅ Forslag:\n"
            f"  • Legg filen her: {default_input}\n"
            "  • Eller oppgi eksplisitt sti med --input\n\n"
        )
        sys.exit(1)

    try:
        valid_rows = load_valid_rows(input_path)
    except Exception as e:
        sys.stderr.write(f"❌ Feil ved lesing/parsing: {e}\n")
        sys.exit(2)

    if not valid_rows:
        print("⚠️  Fant ingen gyldige punkter (hr & watts).")
        print("   Tips: Kjør analyse av manglende data eller velg en annen økt.")
        sys.exit(0)

    # Beregn baseline (median W/beat)
    wpb_values = [compute_w_per_beat(r) for r in valid_rows]
    wpb_values = [x for x in wpb_values if x is not None]
    if not wpb_values:
        print("⚠️  Kunne ikke beregne w/beat for noen rader.")
        sys.exit(0)

    baseline = median(wpb_values)

    # Bygg output-linjer
    lines = []
    for idx, row in enumerate(valid_rows):
        wpb = compute_w_per_beat(row)
        if wpb is None:
            continue
        delta_pct = None
        if baseline and baseline > 0:
            delta_pct = (wpb / baseline - 1.0) * 100.0
        line = build_line(idx, row, wpb, delta_pct, baseline)
        lines.append(line)

    # Begrensning
    if args.limit is not None and args.limit >= 0:
        lines_to_print = lines[:args.limit]
    else:
        lines_to_print = lines

    # Print til stdout
    print(f"✅ Gyldige punkter: {len(lines)} (baseline median w/beat = {fmt_num(baseline,3)})")
    for ln in lines_to_print:
        print(ln)

    # Lagre til fil om ønsket
    if args.outfile is not None:
        out_path = (default_output if args.outfile == "__DEFAULT__"
                    else os.path.abspath(args.outfile))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"# Efficiency report\n")
                f.write(f"# Source: {input_path}\n")
                f.write(f"# Baseline median w/beat: {fmt_num(baseline,3)}\n")
                f.write(f"# Total valid points: {len(lines)}\n\n")
                for ln in lines:
                    f.write(ln + "\n")
            print(f"\n💾 Rapport lagret: {out_path}")
        except Exception as e:
            sys.stderr.write(f"❌ Feil ved lagring av rapport: {e}\n")
            sys.exit(3)

if __name__ == "__main__":
    main()