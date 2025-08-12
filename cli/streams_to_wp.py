# cli/streams_to_wp.py
import csv, argparse, os
from pathlib import Path

ap = argparse.ArgumentParser(description="Konverter streams-CSV til 2 kolonner (watt,puls) for analyze.py")
ap.add_argument("--csv", required=True, help="Input: streams CSV (activity_id,index,time_s,hr,watts,...)")
ap.add_argument("--out", required=True, help="Output: 2-kolonne CSV (watt,puls)")
args = ap.parse_args()

# Sørg for at utmappa finnes
Path(os.path.dirname(args.out) or ".").mkdir(parents=True, exist_ok=True)

kept = 0
dropped = 0

with open(args.csv, encoding="utf-8") as f, open(args.out, "w", newline="", encoding="utf-8") as g:
    r = csv.DictReader(f)
    w = csv.writer(g)
    w.writerow(["watt", "puls"])
    for row in r:
        watts = (row.get("watts") or "").strip()
        hr = (row.get("hr") or "").strip()
        # behold kun rader som har både watt og puls
        if watts == "" or hr == "":
            dropped += 1
            continue
        try:
            w_val = float(watts)
            h_val = float(hr)
        except ValueError:
            dropped += 1
            continue
        # valg: dropp nuller hvis ønskelig – kommenter ut neste to linjer hvis du vil beholde 0
        # if w_val <= 0 or h_val <= 0:
        #     dropped += 1; continue
        w.writerow([w_val, h_val])
        kept += 1

print(f"✅ Skrev kompatibilitetsfil: {args.out} (beholdt {kept} rader, droppet {dropped})")
