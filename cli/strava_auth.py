import os
import json
import requests
from dotenv import load_dotenv

# Finn absolutt sti til .env (én mappe opp fra denne filen)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
env_path = os.path.abspath(env_path)
print(f"📂 Laster .env fra: {env_path}")

# Last .env eksplisitt
load_dotenv(dotenv_path=env_path)

# Hent verdier
CID = os.getenv("STRAVA_CLIENT_ID")
CSECRET = os.getenv("STRAVA_CLIENT_SECRET")

print("🔑 CID =", CID)
print("🔑 Secret length =", len(CSECRET or ""))

TOKEN_URL = "https://www.strava.com/oauth/token"
TOK_FILE = "data/strava_tokens.json"

def exchange_code_for_token(code: str):
    payload = {
        "client_id": CID,
        "client_secret": CSECRET,
        "code": code,
        "grant_type": "authorization_code",
}
    print("📤 Sender payload:", payload)
    r = requests.post(TOKEN_URL, data=payload)
    print("📥 Status:", r.status_code)
    print("📥 Body:", r.text)
    r.raise_for_status()

    data = r.json()
    os.makedirs("data", exist_ok=True)
    with open(TOK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Tokens lagret i: {TOK_FILE}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Bruk: python cli/strava_auth.py <authorization_code>")
        raise SystemExit(1)
    exchange_code_for_token(sys.argv[1])