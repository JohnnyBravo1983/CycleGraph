from cli.efficiency import cmd_efficiency
from cli.session import cmd_session
import argparse

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CycleGraph CLI (efficiency | session)")
    sub = p.add_subparsers(dest="command", required=True)

    pe = sub.add_parser("efficiency", help="Analyser watt/puls-effektivitet fra CSV (kolonner: watt,puls).")
    pe.add_argument("--file", help="Path til CSV med kolonner 'watt' og 'puls'. (påkrevd uten --dry-run)")
    # pe.add_argument("--validate", action="store_true", help="Valider RDF mot SHACL før analyse.")
    pe.add_argument("--json", help="Lagre efficiency-rapport som JSON.")
    pe.add_argument("--dry-run", action="store_true", help="Run without making changes")
    pe.set_defaults(func=cmd_efficiency)
    
    ps = sub.add_parser("session", help="Analyser treningsøkter (NP/IF/VI/Pa:Hr/WpB/CGS) fra CSV.")
    ps.add_argument("--mode", choices=["roller", "outdoor"], help="Overstyr auto-modus (roller|outdoor)")
    ps.add_argument("--input", required=True, help="Glob for CSV, f.eks. data/*.csv")
    ps.add_argument("--out", default="output", help="Output-mappe (default: output/)")
    ps.add_argument("--cfg", default="", help="Path til config.json")
    ps.add_argument("--format", choices=["json", "csv", "both"], default="json", help="Rapportformat")
    ps.add_argument("--batch", action="store_true", help="Analyser alle filer i én batch")
    ps.add_argument("--with-trend", action="store_true", help="Legg til minitrend (siste 3) i batch")
    ps.add_argument("--set-ftp", type=float, default=None, help="Overstyr FTP for alle sessions")
    ps.add_argument("--auto-ftp", action="store_true", help="Estimer FTP (20min*0.95) hvis mulig")
    ps.add_argument("--publish-to-strava", action="store_true", help="(Stub) Publiser kort/tekst til Strava")
    ps.add_argument("--dry-run", action="store_true", help="Skriv kun til stdout (ingen filer)")
    ps.add_argument("--debug", action="store_true", help="Print diagnostikk om CSV-parsing pr. fil")
    ps.add_argument("--lang", choices=["no", "en"], default="no", help="Språk for publiseringstekster (no/en)")
    ps.set_defaults(func=cmd_session)

    return p