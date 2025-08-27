# cli/strava_client.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from pathlib import Path
import json
import requests
from dotenv import load_dotenv

from cli import strava_auth

# Paths / env
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "state"
LAST_IMPORT = STATE_DIR / "last_import.json"
load_dotenv(dotenv_path=str(REPO_ROOT / ".env"), override=True)


class StravaClient:
    def __init__(self, base_url: str = "https://www.strava.com/api/v3", lang: str = "no") -> None:
        self.base_url = base_url.rstrip("/")
        self.lang = lang
        self._fixed_headers: Optional[Dict[str, str]] = None  # settes av publish.py

    # ── injiser forhåndsbygde headers fra publish.py ──────────────────────────
    def use_headers(self, headers: Dict[str, str]) -> None:
        self._fixed_headers = headers

    # ── intern request-helper (med 401→refresh→retry) ─────────────────────────
    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        form_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # 1) Bygg headers (bruk injisert om de finnes, ellers last/refresh)
        def build_headers() -> Dict[str, str]:
            if self._fixed_headers is not None:
                return dict(self._fixed_headers)
            tokens = strava_auth.load_tokens()
            return strava_auth.refresh_if_needed(tokens, client_id=None, client_secret=None)

        headers = build_headers()

        def do_req(hdrs: Dict[str, str]):
            kwargs: Dict[str, Any] = {"headers": hdrs, "timeout": 15}
            if json_body is not None:
                kwargs["json"] = json_body               # application/json
            if form_body is not None:
                kwargs["data"] = form_body               # application/x-www-form-urlencoded
            return requests.request(method, url, **kwargs)

        # 2) Første forsøk
        resp = do_req(headers)
        if resp.status_code == 401:
            # 3) Tvungen refresh + ett retry
            try:
                tokens = strava_auth.load_tokens()
                new_hdrs = strava_auth.refresh_if_needed(
                    tokens, client_id=None, client_secret=None, leeway_secs=10**9
                )
                if self._fixed_headers is not None:
                    self._fixed_headers.update(new_hdrs)
                headers = new_hdrs
                resp = do_req(headers)
            except Exception:
                pass

        resp.raise_for_status()
        if resp.content:
            try:
                return resp.json()
            except Exception:
                return {}
        return {}

    # ── hjelpefunksjon: finn target activity id ───────────────────────────────
    def resolve_target_activity_id(self, target: Any) -> str:
        s = str(target).strip().lower()
        if s != "latest":
            return str(target)
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

    # ── robust utpakking av tekstbiter ────────────────────────────────────────
    def _extract_pieces(self, x: Any) -> Tuple[Optional[str], Optional[str]]:
        if x is None:
            return (None, "")
        if isinstance(x, dict):
            comment = x.get("comment")
            header = x.get("header")
            body = x.get("body")
            description = x.get("description")
            if description is None:
                parts = []
                if header:
                    parts.append(str(header))
                if body:
                    parts.append(str(body))
                description = "\n".join(p for p in parts if p)
            return (str(comment) if comment else None, str(description) if description else "")
        if isinstance(x, (list, tuple)):
            try:
                description = "\n".join(str(t) for t in x if t is not None)
            except Exception:
                description = ""
            return (None, description)
        if isinstance(x, str):
            return (None, x)
        c = getattr(x, "comment", None)
        h = getattr(x, "header", None)
        b = getattr(x, "body", None)
        d = getattr(x, "description", None)
        if d is None:
            parts = []
            if h:
                parts.append(str(h))
            if b:
                parts.append(str(b))
            d = "\n".join(p for p in parts if p)
        return (str(c) if c else None, str(d) if d else "")

    # ── dry-run preview ───────────────────────────────────────────────────────
    def publish_to_strava(
        self,
        pieces: Any = None,
        dry_run: bool = False,
        activity_id: Optional[str] = None,
    ) -> Tuple[None, str]:
        comment, description = self._extract_pieces(pieces)
        msg = (
            f"[dry-run] activity_id={activity_id or 'latest'} "
            f"comment={'' if not comment else comment} "
            f"description={'' if not description else description} "
            f"lang={self.lang}"
        )
        return (None, msg)

    # ── kommentarer via API er ikke støttet → signaliser 'unsupported' ────────
    def create_comment(self, activity_id: str | int, text: str) -> Dict[str, Any]:
        """
        Strava V3 API støtter ikke å opprette kommentarer via offentlig API.
        Kalleren (publish.py) sjekker _unsupported og faller tilbake til å
        flette kommentaren inn i description.
        """
        return {"_unsupported": True, "reason": "Strava API does not expose a comment-create endpoint."}

    # ── oppdater beskrivelse (form-encoded) ───────────────────────────────────
    def update_description(self, activity_id: str | int, desc: str) -> Dict[str, Any]:
        url = f"{self.base_url}/activities/{activity_id}"
        return self._request("PUT", url, form_body={"description": desc})
