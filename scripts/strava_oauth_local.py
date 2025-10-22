# -*- coding: utf-8 -*-
# scripts/strava_oauth_local.py
import json, os, random, string, threading, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
import requests
from pathlib import Path
import sys

CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "").strip()
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "activity:write,activity:read"  # Strava aksepterer komma-separert

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TOKENS_FILE = DATA_DIR / "strava_tokens.json"

def _rand(n=24):
    import secrets, string
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))

class Handler(BaseHTTPRequestHandler):
    code = None
    received_state = None
    expected_state = None
    err = None

    def do_GET(self):
        u = urlparse(self.path)
        if u.path != "/callback":
            self.send_response(404); self.end_headers(); self.wfile.write(b"Not found"); return
        q = parse_qs(u.query)
        code  = q.get("code",  [None])[0]
        state = q.get("state", [None])[0]
        error = q.get("error", [None])[0]

        Handler.received_state = state
        if error:
            Handler.err = f"Auth error from Strava: {error}"
        if not code:
            self.send_response(400); self.end_headers(); self.wfile.write(b"Missing code"); return

        # Dev-toleranse: logg mismatch, men aksepter code hvis gitt
        if state != Handler.expected_state:
            sys.stderr.write(f"[WARN] state mismatch: expected={Handler.expected_state} got={state}\n")

        Handler.code = code
        self.send_response(200); self.end_headers()
        self.wfile.write(b"You can close this window. Token exchange will continue in the console...")

def main():
    assert CLIENT_ID and CLIENT_SECRET, "Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET env vars first."

    state = _rand()
    Handler.expected_state = state

    auth_url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={quote(CLIENT_ID)}"
        f"&redirect_uri={quote(REDIRECT_URI, safe=':/')}"
        f"&response_type=code"
        f"&approval_prompt=auto"
        f"&scope={quote(SCOPES)}"
        f"&state={quote(state)}"
    )
    print("Open/authorize:", auth_url)

    server = HTTPServer(("localhost", 8000), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass
    print("Waiting for callback on", REDIRECT_URI, "...")
    while Handler.code is None and Handler.err is None:
        pass
    server.shutdown()

    if Handler.err:
        raise SystemExit(Handler.err)
    print("Received code; state(expected/actual):", Handler.expected_state, "/", Handler.received_state)

    # Exchange code -> tokens
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": Handler.code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    out = {
        "access_token":  data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_at":    data.get("expires_at"),
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    TOKENS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {TOKENS_FILE}")
    print("Access token head:", (out["access_token"] or "")[:10])

if __name__ == "__main__":
    main()
