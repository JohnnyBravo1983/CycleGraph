# cli/strava_client.py
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

# Bruker eksisterende M6-byggesteiner
# - S.TOK_FILE -> data/strava_tokens.json
# - S.refresh_if_needed(tokens, cid, csec, leeway_secs) -> dict med {"Authorization": "Bearer ..."}
# - S.load_tokens(path) -> dict (kan være definert i strava_import; legg til hvis mangler)
from cli import strava_import as S

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STATE_LAST_IMPORT = Path("state/last_import.json")


class StravaClient:
    """
    Tynn klient som alltid henter ferske Authorization-headers via S.refresh_if_needed
    og gjenbruker M6 sin robuste token/refresh-logikk.
    """

    def __init__(self, timeout: int = 10, max_retries_5xx: int = 3):
        self.timeout = timeout
        self.max_retries_5xx = max_retries_5xx

    # ---------- Internals ----------
    def _headers(self) -> dict:
        """
        Hent ferske Authorization-headers via refresh_if_needed.
        Forventer ENV: STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET i .env,
        og en gyldig token-fil på S.TOK_FILE (data/strava_tokens.json).
        """
        # 1) last tokens fra fil (roterer automatisk ved refresh i refresh_if_needed)
        tokens = S.load_tokens(S.TOK_FILE)

        # 2) klient-credentials fra env
        cid = os.getenv("STRAVA_CLIENT_ID")
        csec = os.getenv("STRAVA_CLIENT_SECRET")
        if not cid or not csec:
            raise RuntimeError(
                "STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET mangler i miljøvariabler (.env)."
            )

        # 3) få ferske headers (refresh hvis nær utløp; leeway 1 time)
        headers = S.refresh_if_needed(tokens, cid, csec, leeway_secs=3600)
        # legg på Accept for JSON
        headers["Accept"] = "application/json"
        return headers

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Wrapper:
        - legger på headers (inkl. automatisk refresh via _headers())
        - håndterer 5xx med retry/backoff
        - håndterer 429 (rate limit) med ryddig feilmelding
        - håndterer 401/403 ved å prøve en gang til (nye headers)
        """
        headers = kwargs.pop("headers", {})
        merged_headers = {**self._headers(), **headers}

        last_exc = None
        for attempt in range(self.max_retries_5xx + 1):
            try:
                resp = requests.request(
                    method, url, headers=merged_headers, timeout=self.timeout, **kwargs
                )

                # 401/403: prøv én gang til med ferske headers
                if resp.status_code in (401, 403):
                    merged_headers = {**self._headers(), **headers}
                    resp = requests.request(
                        method, url, headers=merged_headers, timeout=self.timeout, **kwargs
                    )

                # 429: Strava rate limit
                if resp.status_code == 429:
                    detail = resp.text[:500]
                    raise RuntimeError(f"Strava rate limited (429). Response: {detail}")

                # 5xx: retry med liten backoff
                if 500 <= resp.status_code < 600 and attempt < self.max_retries_5xx:
                    time.sleep(2.0)
                    continue

                return resp

            except requests.RequestException as e:
                last_exc = e
                if attempt < self.max_retries_5xx:
                    time.sleep(2.0)
                    continue
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError("Unknown request failure")

    # ---------- Public API ----------
    def get_latest_activity_id(self) -> int:
        """
        GET /athlete/activities?per_page=1  -> returnerer siste aktivitetens id
        """
        url = f"{STRAVA_API_BASE}/athlete/activities"
        resp = self._request("GET", url, params={"per_page": 1})
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch latest activities: {resp.status_code} {resp.text[:500]}"
            )
        data = resp.json()
        if not data or "id" not in data[0]:
            raise RuntimeError(
                f"No recent activities found or unexpected payload: {json.dumps(data)[:500]}"
            )
        return int(data[0]["id"])

    def create_comment(self, activity_id: int, text: str) -> None:
        """
        POST /activities/{id}/comments
        Payload: {'text': <comment>}
        """
        url = f"{STRAVA_API_BASE}/activities/{activity_id}/comments"
        resp = self._request("POST", url, data={"text": text})
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create comment: {resp.status_code} {resp.text[:500]}"
            )

    def update_description(self, activity_id: int, description: str) -> None:
        """
        PUT /activities/{id}
        Payload: {'description': <full description>}
        NB: Denne setter HELE description.
        """
        url = f"{STRAVA_API_BASE}/activities/{activity_id}"
        resp = self._request("PUT", url, data={"description": description})
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to update description: {resp.status_code} {resp.text[:500]}"
            )

    # ---------- Fallbacks / Helpers ----------
    @staticmethod
    def load_last_import_activity_id() -> Optional[int]:
        if STATE_LAST_IMPORT.exists():
            try:
                obj = json.loads(STATE_LAST_IMPORT.read_text(encoding="utf-8"))
                aid = obj.get("activity_id")
                return int(aid) if aid is not None else None
            except Exception:
                return None
        return None

    def resolve_target_activity_id(self) -> int:
        """
        1) Bruk state/last_import.json hvis finnes
        2) Ellers hent siste aktivitet
        """
        aid = self.load_last_import_activity_id()
        if aid is not None:
            return aid
        return self.get_latest_activity_id()


def publish_to_strava(
    pieces,
    lang: str = "no",
    dry_run: bool = False,
) -> Tuple[Optional[int], str]:
    """
    pieces: PublishPieces fra formatteren (comment, desc_header, desc_body?)
    Return: (activity_id, status-str)
    """
    client = StravaClient()

    # Bygg description av header + ev. body (unngå doble mellomrom/linjeskift)
    header = (getattr(pieces, "desc_header", "") or "").strip()
    body = (getattr(pieces, "desc_body", "") or "").strip()
    if header and body:
        description = f"{header}\n\n{body}".strip()
    else:
        description = header or body

    comment = (getattr(pieces, "comment", "") or "").strip()

    if dry_run:
        return (
            None,
            f"[dry-run] Would publish to Strava: comment={len(comment)} chars, "
            f"description={len(description)} chars, lang={lang}",
        )

    # Resolving target activity
    aid = client.resolve_target_activity_id()

    # Publiser i rekkefølge: kommentar → beskrivelse
    if comment:
        client.create_comment(aid, comment)
    if description:
        client.update_description(aid, description)

    return aid, "published"
