# tools/patch_analyze_strava_publish.py
import re
from pathlib import Path

ANALYZE = Path("cli/analyze.py")
if not ANALYZE.exists():
    raise SystemExit("Fant ikke cli/analyze.py – kjør fra repo-roten.")

src = ANALYZE.read_text(encoding="utf-8")

changes = 0

def ensure_import(line: str) -> None:
    global src, changes
    if line not in src:
        # Legg inn etter første import-blokk
        m = re.search(r"(^import .+?$|^from .+? import .+?$)(\r?\n(import .+?|from .+? import .+?))*", src, flags=re.M)
        if m:
            insert_at = m.end()
            src = src[:insert_at] + f"\n{line}" + src[insert_at:]
        else:
            src = f"{line}\n" + src
        changes += 1

# 1) Sørg for imports
ensure_import("from cli.strava_client import publish_to_strava")
ensure_import("from cli.formatters.strava_publish import PublishPieces, build_publish_texts")

# 2) Erstatt publish_to_strava_stub med ekte implementasjon.
#    Vi beholder navnet for å slippe å endre alle kall.
stub_pattern = re.compile(
    r"def\s+publish_to_strava_stub\s*\(\s*report\s*:\s*Dict\[str,\s*Any\]\s*,\s*dry_run\s*:\s*bool\s*\)\s*:\s*\n"
    r"(?:\s*.*\n)+?", flags=re.M
)

if not stub_pattern.search(src):
    # fallback: mindre strikt matcher signatur uten type hints
    stub_pattern = re.compile(
        r"def\s+publish_to_strava_stub\s*\([^)]*\)\s*:\s*\n(?:\s*.*\n)+?", flags=re.M
    )

new_impl = '''def publish_to_strava_stub(report, dry_run: bool):
    """
    Ekte Strava-publish (navnet beholdes for bakoverkompabilitet).
    Bruker build_publish_texts -> PublishPieces -> publish_to_strava.
    """
    # finn språk fra args i report hvis satt, ellers default "no"
    lang = (report.get("args", {}) or {}).get("lang", "no")
    try:
        comment_text, desc_header_text, desc_body_text = build_publish_texts(report, lang=lang)
    except Exception as e:
        print(f"[strava] build_publish_texts feilet: {e}")
        return None

    pieces = PublishPieces(
        comment=comment_text,
        desc_header=desc_header_text,
        desc_body=desc_body_text
    )

    try:
        aid, status = publish_to_strava(pieces, lang=lang, dry_run=dry_run)
        print(f"[strava] activity_id={aid} status={status}")
        return aid, status
    except Exception as e:
        print(f"[strava] publisering feilet: {e}")
        return None
'''

m = stub_pattern.search(src)
if m:
    # finn neste top-level def/EOF for å begrense erstatning
    start = m.start()
    # finn hvor stub-funksjonen slutter (neste "def " på kolonne 0 eller EOF)
    rest = src[m.start():]
    n = re.search(r"\ndef\s+\w+\s*\(", rest)
    if n:
        end = m.start() + n.start() + 1  # hold med newline
    else:
        end = len(src)

    src = src[:start] + new_impl + src[end:]
    changes += 1
else:
    print("Advarsel: Fant ikke publish_to_strava_stub. Hopper over funkerstatning.")

# 3) Oppdater help-tekst for flagget (valgfritt)
src_new = re.sub(
    r'--publish-to-strava",\s*action="store_true",\s*help="[^"]*"',
    '--publish-to-strava", action="store_true", help="Publiser kort/tekst til Strava"',
    src
)
if src_new != src:
    src = src_new
    changes += 1

if changes:
    ANALYZE.write_text(src, encoding="utf-8")
    print(f"Patched cli/analyze.py ({changes} endringer).")
else:
    print("Ingen endringer nødvendig – ser allerede patchet ut.")
