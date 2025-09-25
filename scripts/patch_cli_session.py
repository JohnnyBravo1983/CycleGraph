# scripts/patch_cli_session.py
import re
import sys
from pathlib import Path

SESSION_PATH = Path("cli/session.py")

HELPER_FN = r'''
def _ensure_cli_fields(d: dict) -> dict:
    """Garanter at watts/wind_rel finnes, map calibrated til Ja/Nei, og sett status."""
    if not isinstance(d, dict):
        return d
    r = dict(d)

    # watts / wind_rel (hent fra samples hvis mulig)
    if "watts" not in r:
        if isinstance(r.get("samples"), list):
            r["watts"] = [s.get("watts") for s in r["samples"]]
        else:
            r["watts"] = []
    if "wind_rel" not in r:
        if isinstance(r.get("samples"), list):
            r["wind_rel"] = [s.get("wind_rel") for s in r["samples"]]
        else:
            r["wind_rel"] = []

    # v_rel (valgfritt)
    if "v_rel" not in r and isinstance(r.get("samples"), list):
        r["v_rel"] = [s.get("v_rel") for s in r["samples"]]

    # calibrated: bool -> "Ja"/"Nei"
    if isinstance(r.get("calibrated"), bool):
        r["calibrated"] = "Ja" if r["calibrated"] else "Nei"

    # status fra puls
    if "status" not in r:
        hr = r.get("avg_hr", r.get("avg_pulse"))
        if isinstance(hr, (int, float)):
            r["status"] = "OK" if hr < 160 else ("Høy puls" if hr > 180 else "Lav")
    return r
'''.lstrip("\n")

# Regex som fanger første argumentet i json.dumps(
# Eksempler: print(json.dumps(result, ensure_ascii=False))
#            return json.dumps(report)
DUMPS_ARG_RE = re.compile(r'(json\.dumps\()\s*([A-Za-z_][A-Za-z0-9_]*)')

def main():
    if not SESSION_PATH.exists():
        print(f"[!] Fant ikke {SESSION_PATH}. Kjør skriptet fra repo-roten.")
        sys.exit(1)

    src = SESSION_PATH.read_text(encoding="utf-8")

    inserted_helper = False
    if "_ensure_cli_fields(" not in src:
        # Sett helper etter imports (etter første tomlinje etter import-blokk)
        lines = src.splitlines(keepends=True)
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                insert_idx = i + 1
                continue
            # første ikke-import etter en import-blokk + tomlinje
            if insert_idx and line.strip() == "":
                insert_idx = i + 1
                break
        if insert_idx == 0:
            insert_idx = 0
        lines.insert(insert_idx, "\n" + HELPER_FN + "\n")
        src = "".join(lines)
        inserted_helper = True

    # Wrap første argument i json.dumps(...) med _ensure_cli_fields(...)
    def _wrap_arg(m: re.Match) -> str:
        prefix = m.group(1)  # 'json.dumps('
        var = m.group(2)     # f.eks. result / report
        return f"{prefix}_ensure_cli_fields({var}"

    new_src, nsubs = DUMPS_ARG_RE.subn(_wrap_arg, src)

    if inserted_helper or nsubs > 0:
        SESSION_PATH.write_text(new_src, encoding="utf-8")
        print(f"[OK] Patchet {SESSION_PATH}")
        if inserted_helper:
            print("     + la til _ensure_cli_fields(...)")
        print(f"     + wrappet {nsubs} kall til json.dumps(...)")
    else:
        print("[i] Ingen endringer nødvendig (allerede patchet).")

if __name__ == "__main__":
    main()