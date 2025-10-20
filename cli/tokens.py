from pathlib import Path
import json
from typing import Dict, Any

TOKENS_PATH = Path("data/strava_tokens.json")

def load_tokens() -> Dict[str, Any]:
    if TOKENS_PATH.exists():
        return json.loads(TOKENS_PATH.read_text(encoding="utf-8-sig"))
    return {
        "access_token": "",
        "refresh_token": "",
        "expires_at": 0,
        "client_id": "",
        "client_secret": "",
    }

def build_headers(tokens: Dict[str, Any] | None = None) -> Dict[str, str]:
    if tokens is None:
        tokens = load_tokens()
    return {"Authorization": f"Bearer {tokens.get('access_token','')}"}
