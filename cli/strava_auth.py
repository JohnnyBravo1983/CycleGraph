# cli/strava_auth.py
from __future__ import annotations

import os
import json
import time
from typing import Dict, Any
from pathlib import Path
import requests
from dotenv import load_dotenv

# Last .env fra repo-roten (en mappe opp fra denne filen)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=str(ENV_PATH), override=True)

CID = os.getenv("STRAVA_CLIENT_ID", "")
CSECRET = os.getenv("STRAVA_CLIENT_SECRET", "")

TOKEN_URL = "https://www.strava.com/oauth/token"
TOK_FILE = "data/strava_tokens.json"


def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Bytt authorization code -> tokens og lagre til data/strava_tokens.json"""
    redirect_uri = "http://localhost/exchange_token"  # MÅ matche authorize-URL
    payload = {
        "client_id": CID,
        "client_secret": CSECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=15)
    if not r.ok:
        # vis Stravas feilmelding (svært nyttig ved 401/400)
        try:
            print("Token exchange failed:", r.status_code, r.json(), flush=True)
        except Exception:
            print("Token exchange failed:", r.status_code, r.text, flush=True)
        r.raise_for_status()
    data = r.json()
    Path("data").mkdir(parents=True, exist_ok=True)
    with open(TOK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def load_tokens(tok_file: str = TOK_FILE) -> Dict[str, Any]:
    """Les tokens og tåle BOM hvis filen ble skrevet med PowerShell."""
    with open(tok_file, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_tokens(tokens: Dict[str, Any], tok_file: str = TOK_FILE) -> None:
    p = Path(tok_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")


def token_expired(tokens: Dict[str, Any], leeway_secs: int = 3600) -> bool:
    """Sjekk om token er (snart) utløpt gitt 'expires_at' (Unix-sekunder)."""
    exp = tokens.get("expires_at")
    try:
        exp = float(exp)
    except (TypeError, ValueError):
        return True  # konservativt: hvis vi ikke kan lese den, anta utløpt
    return (exp - time.time()) <= leeway_secs

def refresh_if_needed(tokens: Dict[str, Any],
                      client_id: str | None = None,
                      client_secret: str | None = None,
                      leeway_secs: int = 3600) -> Dict[str, str]:
    """
    Returner gyldige headers. Refresher Strava-token hvis utløpt.
    Leser .env først *hvis* refresh trengs. Lagrer nye tokens ved refresh.
    """
    access  = tokens.get("access_token")
    refresh = tokens.get("refresh_token")

    need_refresh = (not access) or token_expired(tokens, leeway_secs=leeway_secs)
    if not need_refresh:
        # Vi har gyldig access_token – ingen grunn til å kreve CID/SECRET nå
        return {"Authorization": f"Bearer {access or ''}"}

    # Refresh trengs → sørg for CID/SECRET
    if not client_id or not client_secret:
        load_dotenv(dotenv_path=str(ENV_PATH), override=True)
        client_id = client_id or os.getenv("STRAVA_CLIENT_ID") or CID
        client_secret = client_secret or os.getenv("STRAVA_CLIENT_SECRET") or CSECRET

    missing = []
    if not refresh:      missing.append("refresh_token (i data/strava_tokens.json)")
    if not client_id:    missing.append("STRAVA_CLIENT_ID (.env)")
    if not client_secret:missing.append("STRAVA_CLIENT_SECRET (.env)")
    if missing:
        raise RuntimeError("Mangler: " + ", ".join(missing))

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh,
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=15)
    r.raise_for_status()
    new = r.json()
    save_tokens(new)  # Strava kan rotere refresh_token – lagre alltid
    access = new.get("access_token")
    return {"Authorization": f"Bearer {access or ''}"}

