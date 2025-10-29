import json, sys, datetime, pathlib

def load_json(p, enc="utf-8-sig"):
    with open(p, "r", encoding=enc) as f:
        return json.load(f)

def to_iso(epoch, t):
    if epoch is None or t is None: return None
    return datetime.datetime.fromtimestamp(\1, datetime.UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")

def build_inline(activity_json, streams_json, out_json):
    A = load_json(activity_json)
    S = load_json(streams_json)

    start_epoch = None
    sd = A.get("start_date")
    if isinstance(sd, str) and sd.endswith("Z"):
        dt = datetime.datetime.strptime(sd, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        start_epoch = int(dt.timestamp())

    LL = (S.get("latlng") or {}).get("data", [])
    TT = (S.get("time") or {}).get("data", [])
    EE = (S.get("altitude") or {}).get("data", [])
    VV = (S.get("velocity_smooth") or {}).get("data", [])
    HH = (S.get("heartrate") or {}).get("data", [])
    CC = (S.get("cadence") or {}).get("data", [])
    WW = (S.get("watts") or {}).get("data", [])
    TTEMP = (S.get("temp") or {}).get("data", [])

    samples = []
    for i, (la, lo) in enumerate(LL):
        row = {
            "time":  to_iso(start_epoch, TT[i]) if i < len(TT) else None,
            "lat":   la,
            "lon":   lo,
            "elev":  EE[i] if i < len(EE) else None,
            "speed": VV[i] if i < len(VV) else None,
            "hr":    HH[i] if i < len(HH) else None,
            "cadence": CC[i] if i < len(CC) else None,
            "watts":   WW[i] if i < len(WW) else None,
            "temp":    TTEMP[i] if i < len(TTEMP) else None,
        }
        samples.append(row)

    pathlib.Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"samples": samples}, f, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: build_inline_samples.py <activity.json> <streams.json> <out.json>")
        sys.exit(1)
    build_inline(sys.argv[1], sys.argv[2], sys.argv[3])

