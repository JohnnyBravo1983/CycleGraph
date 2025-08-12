# cli/csv_to_rdf.py
import csv
import os
import argparse
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal, XSD

CG = Namespace("https://cyclegraph.dev/ns#")
ACT = Namespace("https://cyclegraph.dev/activity/")
SMP = Namespace("https://cyclegraph.dev/sample/")

def add_row(g: Graph, activity_id: str, row: dict):
    # Lag URIs
    act = URIRef(ACT[str(activity_id)])
    idx = row.get("index", "").strip()
    sample = URIRef(SMP[f"{activity_id}/{idx}"]) if idx != "" else URIRef(SMP[f"{activity_id}/unknown"])

    # Relasjon sample→activity
    g.add((sample, CG.activity, act))

    # time_s (int)
    t = row.get("time_s", "").strip()
    if t != "":
        try:
            g.add((sample, CG.timeS, Literal(int(float(t)), datatype=XSD.integer)))
        except ValueError:
            pass

    # hr (int)
    hr = row.get("hr", "").strip()
    if hr != "":
        try:
            g.add((sample, CG.heartRate, Literal(int(float(hr)), datatype=XSD.integer)))
        except ValueError:
            pass

    # watts (int)
    w = row.get("watts", "").strip()
    if w != "":
        try:
            g.add((sample, CG.power, Literal(int(float(w)), datatype=XSD.integer)))
        except ValueError:
            pass

    # moving (bool)
    mv = row.get("moving", "").strip()
    if mv != "":
        # Strava streams gir True/False (case sensitive). Tolerer “true/false/1/0”
        val = mv
        if mv.lower() in ("true", "1"):
            val = True
        elif mv.lower() in ("false", "0"):
            val = False
        g.add((sample, CG.moving, Literal(val, datatype=XSD.boolean)))

    # altitude (float, meter)
    alt = row.get("altitude", "").strip()
    if alt != "":
        try:
            g.add((sample, CG.altitude, Literal(float(alt), datatype=XSD.float)))
        except ValueError:
            pass

def convert_csv(g: Graph, csv_path: Path):
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        # Forventer header: activity_id,index,time_s,hr,watts,moving,altitude
        for row in r:
            add_row(g, row.get("activity_id", "").strip(), row)

def main():
    ap = argparse.ArgumentParser(description="CSV → RDF (TTL) for CycleGraph streams")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", help="Sti til én CSV-fil")
    group.add_argument("--csv-dir", help="Sti til mappe med CSV-filer (default: data/streams)", nargs="?")
    ap.add_argument("--out", default="data/sample_strava.ttl", help="Utfil (TTL)")
    args = ap.parse_args()

    g = Graph()
    g.bind("cg", CG)

    if args.csv:
        convert_csv(g, Path(args.csv))
    else:
        base = Path(args.csv_dir or "data/streams")
        for p in sorted(base.glob("*.csv")):
            convert_csv(g, p)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out), format="turtle")
    print(f"✅ Skrev TTL: {out}  (tripler: {len(g)})")

if __name__ == "__main__":
    main()
