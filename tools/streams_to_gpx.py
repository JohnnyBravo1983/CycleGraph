import json, sys, datetime

def load_json(p):
    # Leser både UTF-8 og UTF-8 med BOM
    with open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def iso(epoch, t):
    return datetime.datetime.utcfromtimestamp(epoch + int(t)).strftime("%Y-%m-%dT%H:%M:%SZ")

def write_gpx(path, pts):
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<gpx version="1.1" creator="CycleGraph">\n  <trk>\n')
        f.write('    <name>Converted from Strava streams</name>\n    <trkseg>\n')
        for p in pts:
            f.write(f'      <trkpt lat="{p["lat"]}" lon="{p["lon"]}">\n')
            if p.get("ele") is not None:
                f.write(f'        <ele>{p["ele"]}</ele>\n')
            if p.get("time"):
                f.write(f'        <time>{p["time"]}</time>\n')
            f.write('      </trkpt>\n')
        f.write('    </trkseg>\n  </trk>\n</gpx>\n')

def main():
    if len(sys.argv) != 4:
        print("Usage: streams_to_gpx.py <activity.json> <streams.json> <out.gpx>")
        sys.exit(1)

    activity_json, streams_json, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    A = load_json(activity_json)
    S = load_json(streams_json)

    # start_epoch fra ISO8601
    start_epoch = None
    sd = A.get("start_date")
    if isinstance(sd, str) and sd.endswith("Z"):
        dt = datetime.datetime.strptime(sd, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        start_epoch = int(dt.timestamp())

    LL = (S.get("latlng") or {}).get("data", [])
    T  = (S.get("time")   or {}).get("data", [])
    H  = (S.get("altitude") or {}).get("data", [])

    if not LL:
        print("Ingen latlng-stream (innendørs?). Velg annen outdoor-økt.")
        sys.exit(2)

    pts = []
    for i, pair in enumerate(LL):
        # Sikre at elementet faktisk er [lat, lon]
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        la, lo = pair
        ele = H[i] if i < len(H) else None
        tm  = iso(start_epoch, T[i]) if (start_epoch is not None and i < len(T)) else None
        pts.append({"lat": la, "lon": lo, "ele": ele, "time": tm})

    if not pts:
        print("Ingen gyldige GPS-punkter generert.")
        sys.exit(3)

    write_gpx(out_path, pts)
    print(f"Wrote {out_path} with {len(pts)} points.")

if __name__ == "__main__":
    main()
