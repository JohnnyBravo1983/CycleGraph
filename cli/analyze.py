import argparse
import csv
import json
from cyclegraph_core import calculate_efficiency_series

# --- SHACL-validering (RDF) ---
def validate_rdf(shape_path="shapes/session_shape.ttl", data_path="data/sample.ttl"):
    """
    Validerer RDF-data mot SHACL-shapes.
    Returnerer (conforms: bool, report: str).
    """
    try:
        from pyshacl import validate
        from rdflib import Graph
    except ImportError:
        return False, "pyshacl/rdflib er ikke installert. Kjør: pip install pyshacl rdflib"

    sg = Graph().parse(shape_path, format="turtle")
    dg = Graph().parse(data_path, format="turtle")
    conforms, _vgraph, vtext = validate(
        dg,
        shacl_graph=sg,
        inference="rdfs",
        abort_on_first=False,
    )
    return bool(conforms), str(vtext)


# --- CSV-lesing ---
def read_csv(file_path):
    watts, pulses = [], []
    with open(file_path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            watts.append(float(row["watt"]))
            pulses.append(float(row["puls"]))
    return watts, pulses


def main():
    parser = argparse.ArgumentParser(description="Analyze cycling session efficiency.")
    parser.add_argument("--file", required=True, help="Path to CSV file with 'watt' and 'puls' columns.")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate RDF (data/sample.ttl) against shapes (shapes/session_shape.ttl) before analysis.",
    )
    parser.add_argument(
        "--json",
        help="Path to save analysis report as JSON (e.g., output/report.json).",
    )
    args = parser.parse_args()

    # Valider RDF først hvis flagget er satt
    if args.validate:
        conforms, report = validate_rdf()
        print("SHACL validation:", "OK ✅" if conforms else "FAILED ❌")
        if not conforms:
            print(report)
            return

    # Les CSV og kjør analyse
    watts, pulses = read_csv(args.file)
    avg_eff, session_status, per_point_eff, per_point_status = calculate_efficiency_series(watts, pulses)

    # Tekstrapport
    print("\n📊 CycleGraph Report")
    print("====================")
    print(f"Snitteffektivitet: {avg_eff:.2f} watt/puls")
    print(f"Øktstatus: {session_status}\n")

    print("Per datapunkt:")
    for i, (eff, status) in enumerate(zip(per_point_eff, per_point_status), start=1):
        print(f"  Punkt {i}: {eff:.2f} watt/puls – {status}")

    # JSON-eksport
    if args.json:
        report_data = {
            "average_efficiency": round(avg_eff, 2),
            "session_status": session_status,
            "points": [
                {"point": i + 1, "efficiency": round(eff, 2), "status": status}
                for i, (eff, status) in enumerate(zip(per_point_eff, per_point_status))
            ],
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Rapport lagret som JSON: {args.json}")


if __name__ == "__main__":
    main()