# cli/find_hr_watts_candidates.py
import json
from pathlib import Path

acts_path = Path("data/activities.json")
if not acts_path.exists():
    raise SystemExit("Fant ikke data/activities.json – kjør først: strava_import.py activities")

with acts_path.open("r", encoding="utf-8") as f:
    acts = json.load(f)

# Vi krever: sykkeltype + puls + "device_watts == True" (garanterer per-punkt watt-strøm)
TYPES = {"Ride", "VirtualRide", "EBikeRide"}
cands = []
for a in acts:
    if a.get("type") not in TYPES:
        continue
    if not a.get("has_heartrate"):
        continue
    if not a.get("device_watts"):    # <-- viktig: MÅ ha ekte watt-strøm
        continue
    cands.append((
        a["id"],
        a.get("start_date_local") or a.get("start_date") or "",
        a.get("name",""),
        a.get("type")
    ))

# Nyeste først
cands.sort(key=lambda x: x[1], reverse=True)

for id_, dt, name, atype in cands[:20]:
    print(id_, dt, atype, "|", name)

# Skriv en ferdig PowerShell-linje for enkel kopiering
if cands:
    top3 = [str(c[0]) for c in cands[:3]]
    print("\n# Kopier denne linja i PowerShell:")
    print(f"$ids = @({', '.join(top3)})")
else:
    print("Ingen kandidater funnet. Hent større intervall og prøv igjen:")
    print("  python cli\\strava_import.py activities --since 2022-01-01 --out data\\activities.json")