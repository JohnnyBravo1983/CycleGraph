from __future__ import annotations
import os, json
from typing import Any, Dict, Optional, Tuple
import requests
from . import strava_auth as S  # type: ignore

API_BASE = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"

CID = getattr(S, "CID", None) or os.getenv("STRAVA_CLIENT_ID") or ""
CSECRET = getattr(S, "CSECRET", None) or os.getenv("STRAVA_CLIENT_SECRET") or ""
TOK_FILE = getattr(S, "TOK_FILE", None) or "data/strava_tokens.json"

def _safe_load_tokens() -> Dict[str, Any]:
    if hasattr(S, "load_tokens"):
        try:
            return S.load_tokens(TOK_FILE)  # type: ignore
        except TypeError:
            return S.load_tokens()  # type: ignore
    with open(TOK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_tokens(tokens: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(TOK_FILE), exist_ok=True)
    with open(TOK_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)

class StravaClient:
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        tokens = _safe_load_tokens()
        access = tokens.get("access_token") or tokens.get("accessToken") or ""
        return {"Authorization": f"Bearer {access}", "Accept": "application/json"}

    def _refresh_access_token(self) -> None:
        tokens = _safe_load_tokens()
        rtoken = tokens.get("refresh_token")
        if not rtoken:
            raise RuntimeError("Missing refresh_token")
        cid = CID or os.getenv("STRAVA_CLIENT_ID") or ""
        csec = CSECRET or os.getenv("STRAVA_CLIENT_SECRET") or ""
        if not cid or not csec:
            raise RuntimeError("Missing client id/secret for refresh")
        payload = {
            "client_id": cid,
            "client_secret": csec,
            "grant_type": "refresh_token",
            "refresh_token": rtoken,
        }
        resp = requests.post(TOKEN_URL, data=payload, timeout=self.timeout)
        if resp.status_code != 200:
            resp.raise_for_status()
        _save_tokens(resp.json())

    def _request(self, method: str, url: str, *, params=None, json_body=None, retry_on_401: bool = True) -> requests.Response:
        headers = self._headers()
        resp = requests.request(method.upper(), url, params=params, json=json_body, headers=headers, timeout=self.timeout)
        if resp.status_code == 401 and retry_on_401:
            self._refresh_access_token()
            headers = self._headers()
            resp = requests.request(method.upper(), url, params=params, json=json_body, headers=headers, timeout=self.timeout)
        if resp.status_code >= 400:
            resp.raise_for_status()
        return resp

    # ---------- Public API ----------
    def get_latest_activity_id(self) -> Optional[int]:
        url = f"{API_BASE}/athlete/activities"
        resp = self._request("GET", url, params={"per_page": 1})
        data = resp.json()
        if isinstance(data, list) and data:
            aid = data[0].get("id")
            return int(aid) if aid is not None else None
        return None

    def update_description(self, activity_id: int, description: str) -> None:
        url = f"{API_BASE}/activities/{activity_id}"
        body = {"description": description}
        self._request("PUT", url, json_body=body)

    def publish_to_strava(self, pieces: Any, *, activity_id: Optional[int] = None, dry_run: bool = False, lang: str = "no") -> Tuple[Optional[int], str]:
        aid = activity_id
        if aid is None:
            try:
                with open(os.path.join("state","last_import.json"), "r", encoding="utf-8") as f:
                    aid = json.load(f).get("activity_id")
            except FileNotFoundError:
                aid = None
        if aid is None:
            aid = self.get_latest_activity_id()
        if not aid:
            return None, "[strava] activity_id=None (no valid activity)"

        comment, description = self._extract_pieces(pieces)
        if dry_run:
            return aid, f"[strava] activity_id={aid} status=dry-run comment_len={len(comment or '')} description_len={len(description or '')} lang={lang}"

        final_desc = description or ""
        if comment:
            # prepend comment into description (since public comment endpoint is not available)
            final_desc = (comment + ("\n\n" + final_desc if final_desc else "")).strip()

        if final_desc:
            self.update_description(aid, final_desc)

        return aid, f"[strava] activity_id={aid} status=published"

    @staticmethod
    def _extract_pieces(pieces: Any) -> Tuple[Optional[str], Optional[str]]:
        comment = None; description = None
        if pieces is None:
            return None, None
        if hasattr(pieces, "comment") or hasattr(pieces, "description"):
            return getattr(pieces, "comment", None), getattr(pieces, "description", None)
        if isinstance(pieces, dict):
            comment = pieces.get("comment")
            description = pieces.get("description")
            if not description:
                header = pieces.get("header") or ""
                body = pieces.get("body") or ""
                description = (header + "\n\n" + body).strip() if (header or body) else None
            return comment, description
        if isinstance(pieces, (list, tuple)):
            if len(pieces) >= 2: return pieces[0], pieces[1]
            if len(pieces) == 1: return None, pieces[0]
        if isinstance(pieces, str):
            return None, pieces
        return None, None
# --- module-level shim for legacy import ---
def publish_to_strava(pieces, *, activity_id=None, dry_run=False, lang="no"):
    """
    Back-compat wrapper used by analyze.py:
    returns (activity_id, status_str)
    """
    return StravaClient().publish_to_strava(
        pieces, activity_id=activity_id, dry_run=dry_run, lang=lang
    )
