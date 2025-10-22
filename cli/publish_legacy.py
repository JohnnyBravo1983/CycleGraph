# cli/publish.py
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, Any, Dict

import requests
from dotenv import load_dotenv
from cli.strava_client import StravaClient
from cli import strava_auth

# ── Paths / state ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "last_publish.json"
PIECES_FILE = STATE_DIR / "publish_pieces.json"
LAST_IMPORT = STATE_DIR / "last_import.json"

# Last .env robust (uten å avhenge av at miljøet allerede er lastet)
load_dotenv(dotenv_path=str(REPO_ROOT / ".env"), override=True)

# ── Idempotens ────────────────────────────────────────────────────────────────
HASH_LEN = 10
TAG_FMT = "[CG:{h}]"

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publish CycleGraph output til Strava (description + evt. comment)")
    p.add_argument("--activity", default="latest", help="Activity id eller 'latest' (default)")
    p.add_argument("--dry-run", action="store_true", help="Simuler uten å poste til Strava")
    p.add_argument("--confirm", action="store_true", help="Påkrevd for LIVE publisering")
    p.add_argument("--no-comment", action="store_true", help="Ikke post kommentar (kun description)")
    p.add_argument("--force", action="store_true", help="Ignorer idempotens-sjekk og post uansett")
    return p.parse_args()

# ── Preflight ─────────────────────────────────────────────────────────────────
def preflight(headers: dict, activity_id: Optional[str], dry_run: bool, confirm: bool) -> tuple[bool, str, int]:
    if not headers or "Authorization" not in headers:
        return False, "mangler Authorization-header (auth/token).", 2
    if not activity_id:
        return False, "fant ingen activity-id (bruk --activity <ID> eller 'latest').", 2
    if not dry_run and not confirm:
        return False, "live publisering krever --confirm. Kjør først --dry-run for å sjekke.", 3
    return True, "ok", 0

# ── State helpers ─────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def sha(text: Optional[str]) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:HASH_LEN]

def ensure_tagged(text: Optional[str], h: Optional[str]) -> Optional[str]:
    if text is None or not h:
        return text
    tag = TAG_FMT.format(h=h)
    if tag in text:
        return text
    sep = "" if text.endswith((" ", "\n")) else " "
    return f"{text}{sep}{tag}"

# ── Extractors (parser client-msg til comment/description) ────────────────────
COMMENT_RE = re.compile(r"comment\s*=\s*(?P<val>.+?)(?:,|\n|$)", re.IGNORECASE | re.DOTALL)
DESC_RE    = re.compile(r"description\s*=\s*(?P<val>.+?)(?:,|\n|$)", re.IGNORECASE | re.DOTALL)
QUOTED_RE  = re.compile(r"""^(?P<q>['"])(?P<body>.*?)(?P=q)$""", re.DOTALL)

def _strip_quotes(s: str) -> str:
    m = QUOTED_RE.match(s.strip())
    return m.group("body") if m else s.strip()

def extract_comment_description(msg: str) -> tuple[Optional[str], Optional[str]]:
    comment = None
    description = None
    mc = COMMENT_RE.search(msg)
    if mc:
        comment = _strip_quotes(mc.group("val"))
    md = DESC_RE.search(msg)
    if md:
        description = _strip_quotes(md.group("val"))
    return comment, description

# ── Helpers for ID og pieces ──────────────────────────────────────────────────
def get_latest_activity_id(candidate: str) -> str:
    """Returner konkret ID hvis mulig. Leser state/last_import.json om 'latest'."""
    if str(candidate).lower() != "latest":
        return str(candidate)
    if LAST_IMPORT.exists():
        try:
            data = json.loads(LAST_IMPORT.read_text(encoding="utf-8-sig"))
            for key in ("activity_id", "id", "aid", "target_activity_id", "latest"):
                v = data.get(key)
                if v:
                    return str(v)
        except Exception:
            pass
    return "latest"

def load_pieces_from_file() -> Optional[dict]:
    """Les tekstbiter fra state/publish_pieces.json hvis finnes."""
    if PIECES_FILE.exists():
        try:
            d = json.loads(PIECES_FILE.read_text(encoding="utf-8-sig"))
            return {
                "comment": (d.get("comment") or "").strip(),
                "description": (d.get("description") or "").strip(),
            }
        except Exception:
            return None
    return None

# ── Preview-tekster (støtter både pieces-fil og StravaClient preview) ─────────
def preview_texts(client: StravaClient, activity_id: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Rekkefølge:
      0) Hvis state/publish_pieces.json finnes → bruk den (ingen Strava-kall).
      1) publish_to_strava(dry_run=True, activity_id=...)
      2) publish_to_strava(pieces=..., dry_run=True, activity_id=...)
      3) publish_to_strava({...}, True)  # posisjonelle args (eldre stil)
      4) Fallback: tom preview.
    """
    pieces = load_pieces_from_file()
    if pieces is not None:
        cmt = pieces.get("comment") or None
        desc = pieces.get("description") or ""
        raw = f"[dry-run] pieces from {PIECES_FILE.name}: comment={'<nonempty>' if cmt else ''} description={'<nonempty>' if desc else ''}"
        return cmt, desc, raw

    try:
        _, msg = client.publish_to_strava(dry_run=True, activity_id=activity_id)  # type: ignore
        cmt, desc = extract_comment_description(str(msg))
        return cmt, desc, str(msg)
    except Exception:
        pass

    try:
        _, msg = client.publish_to_strava(
            pieces={"description": "", "comment": ""},
            dry_run=True,
            activity_id=activity_id,  # type: ignore[arg-type]
        )
        cmt, desc = extract_comment_description(str(msg))
        return cmt, desc, str(msg)
    except Exception:
        pass

    try:
        _, msg = client.publish_to_strava({"description": "", "comment": ""}, True)  # type: ignore
        cmt, desc = extract_comment_description(str(msg))
        return cmt, desc, str(msg)
    except Exception:
        pass

    return None, "", "[dry-run] (fallback) comment='' , description=''"

# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()

    # 1) Tokens (fra data/strava_tokens.json)
    try:
        tokens_in = strava_auth.load_tokens()
    except FileNotFoundError:
        print("SAFE-ABORT: fant ikke data/strava_tokens.json. Kjør oauth-koden eller legg inn tokens.")
        sys.exit(2)

    # 2) Bygg headers uten å refreshe her (refresh håndteres i klienten ved 401)
    headers = {"Authorization": f"Bearer {tokens_in.get('access_token','')}"}

    # 3) Resolve activity-id
    client = StravaClient()
    client.use_headers(headers)  # injiser header i alle kall
    aid = client.resolve_target_activity_id(args.activity)
    aid = get_latest_activity_id(aid)

    # 4) Preflight
    ok, reason, code = preflight(headers, aid, args.dry_run, args.confirm)
    if not ok:
        print(f"SAFE-ABORT: {reason}")
        sys.exit(code)

    # 5) Hent tekster via dry-run path
    comment, description, raw_msg = preview_texts(client, str(aid))

    # Guard: ikke post tomme tekster
    if comment is not None and not comment.strip():
        comment = None
    if description is None or not description.strip():
        description = ""
    if args.no_comment:
        comment = None

    # 6) Idempotens + “inline kommentar”-modus etter første fallback
    state = load_state()
    per_a = state.get(str(aid), {})
    force_inline = per_a.get("comment_mode") == "inline"

    def merge(desc: str, cmt: Optional[str]) -> str:
        if not cmt:
            return desc
        return (desc.rstrip() + "\n\n" if desc.strip() else "") + cmt

    effective_description = description
    if force_inline and comment:
        effective_description = merge(description, comment)

    desc_hash = sha(effective_description)
    description_tagged = ensure_tagged(effective_description, desc_hash) or ""
    cmt_hash = sha(comment) if comment else None
    comment_tagged = ensure_tagged(comment, cmt_hash)

    # 7) Preview/logging
    print("== CycleGraph publish preview ==")
    print(f"activity_id: {aid}")
    if args.dry_run:
        print("[dry-run] update_description(...)")
        if comment_tagged:
            print("[dry-run] create_comment(...)")
        if raw_msg:
            print("\n[dry-run] raw preview from client.publish_to_strava():")
            print(str(raw_msg).strip())
        if str(aid).lower() == "latest":
            print("HINT: Fyll state/last_import.json med {'activity_id': <id>} eller kjør med --activity <id>.")
        if not description and not comment:
            print(f"HINT: Legg tekster i {PIECES_FILE} ({{'description': '...', 'comment': '...'}}) for å se full preview.")
        sys.exit(0)
    else:
        print("[LIVE] update_description(...)")
        if comment_tagged:
            print("[LIVE] create_comment(...)")

    # 8) Idempotens (state/last_publish.json)
    desc_unchanged = per_a.get("desc_hash") == desc_hash
    cmt_unchanged  = (cmt_hash is not None) and (per_a.get("comment_hash") == cmt_hash)

    # 9) Live-kall (try/except for tydelige feilmeldinger)
    try:
        if description_tagged.strip() and (not desc_unchanged or args.force):
            _ = client.update_description(aid, description_tagged)
            print("OK: description oppdatert.")
        elif not description_tagged.strip():
            print("SKIP: tom description – ingenting å poste.")
        else:
            print("SKIP: description uendret (idempotent). Bruk --force for å overskrive.")
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", "?")
        body = ""
        try:
            body = e.response.text[:400]
        except Exception:
            pass
        print(f"ERROR: update_description failed (HTTP {status}). Body: {body}")
        sys.exit(5)
    except Exception as e:
        print(f"ERROR: update_description failed: {e}")
        sys.exit(5)

    # Kommentar: forsøk først “kommentar”; hvis ikke støttet → fallback inn i description
    if comment_tagged and comment:
        if not cmt_unchanged or args.force:
            try:
                res = client.create_comment(aid, comment_tagged)

                # Fallback hvis API ikke støtter kommentar-posting (klienten signaliserer dette)
                if isinstance(res, dict) and res.get("_unsupported"):
                    base_desc = description or ""
                    merged = merge(base_desc, comment)  # bruk u-tagget comment
                    new_hash = sha(merged)
                    merged_tagged = ensure_tagged(merged, new_hash) or ""

                    _ = client.update_description(aid, merged_tagged)
                    print("FALLBACK: Strava støtter ikke kommentar via API → la kommentaren inn i description.")

                    # marker inline-modus og lagre konsistent state
                    state[str(aid)] = {"desc_hash": new_hash, "comment_hash": cmt_hash, "comment_mode": "inline"}
                    save_state(state)
                    print("Done.")
                    return
                else:
                    print("OK: kommentar postet.")
            except requests.HTTPError as e:
                status = getattr(e.response, "status_code", "?")
                body = ""
                try:
                    body = e.response.text[:400]
                except Exception:
                    pass
                print(f"ERROR: create_comment failed (HTTP {status}). Body: {body}")
                print("TIP: Strava API tillater sannsynligvis ikke kommentar-post. Faller tilbake til description neste gang.")
                sys.exit(6)
            except Exception as e:
                print(f"ERROR: create_comment failed: {e}")
                sys.exit(6)
        else:
            print("SKIP: kommentar uendret (idempotent). Bruk --force for å poste på nytt.")
    elif comment is None:
        print("SKIP: tom kommentar – ingenting å poste.")

    # 10) Lagre state (viderefør comment_mode hvis satt fra før)
    per_a["desc_hash"] = desc_hash
    per_a["comment_hash"] = cmt_hash
    state[str(aid)] = per_a
    save_state(state)
    print("Done.")

if __name__ == "__main__":
    main()
