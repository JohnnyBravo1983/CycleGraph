import csv, glob, os

base = "data/streams"
candidates = []

for path in glob.glob(os.path.join(base, "*.csv")):
    kept = 0
    with open(path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            watts = (row.get("watts") or "").strip()
            hr = (row.get("hr") or "").strip()
            if watts != "" and hr != "":
                kept += 1
    candidates.append((kept, path))

candidates.sort(reverse=True)
for kept, path in candidates[:15]:
    print(f"{kept:7d}  {path}")