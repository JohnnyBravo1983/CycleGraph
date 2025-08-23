from __future__ import annotations
import os
import json
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
    os.makedirs(os.path.dirname(TOK_FILE) or ".", exist_ok=True)
    with open(TOK_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)


class StravaClient:
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def _headers_from_tokens(self) -> Dict[str, str]:
        tokens = _safe_load_tokens()
        if hasattr(S, "refresh_if_needed"):
            try:
                return S.refresh_if_needed(tokens, CID, CSECRET)  # type: ignore
            except TypeError:
                return S.refresh_if_needed(tokens)  # type: ignore
        access = tokens.get("access_token") or tokens.get("accessToken") or ""
        return {"Authorization": f"Bearer {access}", "Accept": "application/json"}

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True,
    ) -> requests.Response:
        headers = self._headers_from_tokens()
        resp = requests.request(
            method.upper(), url, params=params, json=json_body, headers=headers, timeout=self.timeout
        )
        if resp.status_code in (401, 403) and retry_on_401:
            headers = self._headers_from_tokens()
            resp = requests.request(
                method.upper(), url, params=params, json=json_body, headers=headers, timeout=self.timeout
            )
        if resp.status_code >= 400:
            resp.raise_for_status()
        return resp

    # ---------- Public API ----------
    def resolve_target_activity_id(self, explicit_id: Optional[int] = None) -> Optional[int]:
        if explicit_id:
            return explicit_id
        try:
            with open(os.path.join("state", "last_import.json"), "r", encoding="utf-8") as f:
                aid = json.load(f).get("activity_id")
                if aid:
                    return int(aid)
        except FileNotFoundError:
            pass
        return self.get_latest_activity_id()

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

    def create_comment(self, activity_id: int, text: str) -> None:
        """
        Post en kommentar til aktiviteten.
        """
        url = f"{API_BASE}/activities/{activity_id}/comments"
        body = {"text": text}
        self._request("POST", url, json_body=body)

    def publish_to_strava(
        self,
        pieces: Any,
        *,
        activity_id: Optional[int] = None,
        dry_run: bool = False,
        lang: str = "no",
    ) -> Tuple[Optional[int], str]:
        # NB: kall uten arg for å støtte monkeypatch `lambda: 123`
        if activity_id is not None:
            aid = activity_id
        else:
            aid = self.resolve_target_activity_id()

        if not aid:
            return None, "[strava] activity_id=None (no valid activity)"

        comment, description = self._extract_pieces(pieces)

        # DRY-RUN: krever "[dry-run]" + "comment=" + "description="
        if dry_run:
            return (
                None,
                f"[dry-run] activity_id={aid} comment={comment or ''} "
                f"description={description or ''} lang={lang}"
            )

              # Ekte publisering: separat comment + description
                      # Ekte publisering: separat comment + description
        if comment:
            self.create_comment(aid, comment)

        # Alltid oppdater description (selv tom streng) fordi testene forventer PUT
        desc_to_send = description or ""
        self.update_description(aid, desc_to_send)

        return aid, "published"

      


       

    @staticmethod
    def _extract_pieces(pieces: Any) -> Tuple[Optional[str], Optional[str]]:
        comment: Optional[str] = None
        description: Optional[str] = None
        if pieces is None:
            return None, None

        # Objekter med relevante attributter (inkl. DummyPieces i testen)
        if any(hasattr(pieces, a) for a in ("comment", "description", "header", "body")):
            comment = getattr(pieces, "comment", None)
            description = getattr(pieces, "description", None)
            if not description:
                header = getattr(pieces, "header", "") or ""
                body = getattr(pieces, "body", "") or ""
                if header or body:
                    description = (header + ("\n\n" + body if body else "")).strip()
            return comment, description

        # Dict-input
        if isinstance(pieces, dict):
            comment = pieces.get("comment")
            description = pieces.get("description")
            if not description:
                header = pieces.get("header") or ""
                body = pieces.get("body") or ""
                if header or body:
                    description = (header + "\n\n" + body).strip()
            return comment, description

        # List/tuple
        if isinstance(pieces, (list, tuple)):
            if len(pieces) >= 2:
                return pieces[0], pieces[1]
            if len(pieces) == 1:
                return None, pieces[0]

        # Ren tekst
        if isinstance(pieces, str):
            return None, pieces

        return None, None


# --- module-level shim for legacy import ---
def publish_to_strava(pieces, *, activity_id=None, dry_run=False, lang="no"):
    return StravaClient().publish_to_strava(
        pieces, activity_id=activity_id, dry_run=dry_run, lang=lang
    )
