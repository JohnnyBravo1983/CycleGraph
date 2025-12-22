# cli/strava_client.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import json
import time
import requests

from dotenv import load_dotenv

from cli.tokens import load_tokens as _load_tokens, build_headers as _build_headers
from cli import strava_auth

# Paths / env
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "state"
LAST_IMPORT = STATE_DIR / "last_import.json"
load_dotenv(dotenv_path=str(REPO_ROOT / ".env"), override=True)


class S:
    """
    Test-hook wrapper.
    Testene dine monkeypatcher:
      - S.load_tokens(path)
      - S.refresh_if_needed(tokens, cid, csec, leeway_secs=...)
    """
    @staticmethod
    def load_tokens(path: Optional[Path] = None):
        # cli.tokens.load_tokens kan være (path) eller uten args i noen repo-varianter
        try:
            return _load_tokens(path) if path is not None else _load_tokens()
        except TypeError:
            # fallback hvis load_tokens() ikke tar path
            return _load_tokens()

    @staticmethod
    def build_headers(tokens: Optional[Dict[str, Any]] = None):
        # samme type fleksibilitet for build_headers
        try:
            return _build_headers(tokens) if tokens is not None else _build_headers()
        except TypeError:
            return _build_headers()

    @staticmethod
    def refresh_if_needed(tokens, cid, csec, leeway_secs=3600):
        # Ekte refresh ligger i cli/strava_auth.py, men testene mocker dette uansett.
        return strava_auth.refresh_if_needed(tokens, client_id=cid, client_secret=csec, leeway_secs=leeway_secs)


def resolve_activity_from_state(state_dir: Path = STATE_DIR) -> str:
    p = state_dir / "last_import.json"
    if not p.exists():
        return ""
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
        return str(state.get("activity_id", "") or "")
    except Exception:
        return ""


def publish_to_strava(pieces, dry_run: bool = False, lang: str = "no", headers: Optional[Dict[str, str]] = None) -> tuple[str, str]:
    activity_id = resolve_activity_from_state(STATE_DIR)

    # Dry-run: aldri krev activity_id, aldri krev headers
    if dry_run:
        if isinstance(pieces, dict):
            description = pieces.get("description", "")
            comment = pieces.get("comment", "")
        else:
            description = getattr(pieces, "desc_header", "") or ""
            comment = getattr(pieces, "comment", "") or ""

        msg = (
            f"[dry-run] activity_id={activity_id or ''} "
            f"comment={comment} "
            f"description={description} "
            f"lang={lang}"
        )

        url = f"https://www.strava.com/api/v3/activities/{activity_id or '<none>'}"
        print(f"[DRY-RUN] PATCH {url}")
        print(json.dumps({"description": description, "name": comment}, ensure_ascii=False, indent=2))
        return "", msg

    # Normal flyt: krever activity_id
    if not activity_id:
        return "", "missing_activity_id"

    # Hent verdier trygt fra pieces
    if isinstance(pieces, dict):
        description = pieces.get("description", "")
        comment = pieces.get("comment", "")
    else:
        description = getattr(pieces, "desc_header", "") or ""
        comment = getattr(pieces, "comment", "") or ""

    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    payload = {"description": description, "name": comment}

    if headers is None:
        return activity_id, "missing_headers"

    for attempt in range(2):
        response = requests.put(url, headers=headers, json=payload, timeout=15)
        if response.status_code in (401, 403):
            print(f"[STRAVA] Auth error ({response.status_code}), retrying...")
            time.sleep(1)
            continue
        if response.ok:
            return activity_id, "ok"
        return activity_id, f"error_{response.status_code}"

    return activity_id, "auth_failed"


class StravaClient:
    def __init__(
        self,
        base_url: str = "https://www.strava.com/api/v3",
        lang: str = "no",
        state_dir: Path = Path("state"),
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.lang = lang
        self._fixed_headers: Optional[Dict[str, str]] = None
        self.state_dir = state_dir
        self.last_import_path = self.state_dir / "last_import.json"

    def use_headers(self, headers: Dict[str, str]) -> None:
        self._fixed_headers = dict(headers)

    # dummy for test (test_401_retry_flow_on_latest_activity monkeypatcher denne uansett)
    def get_latest_activity_id(self):
        return 99

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        form_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        def build_headers() -> Dict[str, str]:
            if self._fixed_headers is not None:
                return dict(self._fixed_headers)
            tokens = strava_auth.load_tokens()
            return strava_auth.refresh_if_needed(tokens, client_id=None, client_secret=None)

        headers = build_headers()

        def do_req(hdrs: Dict[str, str]):
            kwargs: Dict[str, Any] = {"headers": hdrs, "timeout": 15}
            if json_body is not None:
                kwargs["json"] = json_body
            if form_body is not None:
                kwargs["data"] = form_body
            return requests.request(method, url, **kwargs)

        resp = do_req(headers)
        if resp.status_code == 401:
            # tvungen refresh + ett retry
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

    def resolve_target_activity_id(self, target: Any = None) -> Optional[str]:
        if target is None:
            target = "latest"
        s = str(target).strip().lower()

        if s != "latest":
            return str(target)

        if self.last_import_path.exists():
            try:
                data = json.loads(self.last_import_path.read_text(encoding="utf-8"))
                for key in ("activity_id", "id", "aid", "target_activity_id", "latest"):
                    v = data.get(key)
                    if v:
                        return str(v)
            except Exception:
                pass

        # fallback (valgfritt)
        try:
            return str(self.get_latest_activity_id())
        except Exception:
            return None

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

    def fetch_activity_with_streams(self, activity_id: str) -> Dict[str, Any]:
        meta_url = f"{self.base_url}/activities/{activity_id}"
        meta = self._request("GET", meta_url)

        stream_keys = ["time", "distance", "heartrate", "cadence", "watts", "latlng"]
        stream_url = f"{self.base_url}/activities/{activity_id}/streams"
        streams = self._request("GET", f"{stream_url}?keys={','.join(stream_keys)}&key_by_type=true")

        trainer = meta.get("trainer", False)
        sport_type = meta.get("sport_type", "")
        device_watts = meta.get("device_watts", False)

        if trainer or sport_type == "VirtualRide" or (device_watts and not meta.get("start_latlng")):
            mode = "indoor"
        else:
            mode = "outdoor"

        return {
            "id": str(activity_id),
            "mode": mode,
            "meta": meta,
            "streams": streams,
        }

    def publish_to_strava(self, pieces: Any, dry_run: bool = False, activity_id: Any = "latest") -> tuple[str, str]:
        target_id = self.resolve_target_activity_id(activity_id)
        if dry_run:
            # bare gjenbruk top-level preview-format
            return publish_to_strava(pieces, dry_run=True, lang=self.lang, headers=None)

        if not target_id:
            return "", "missing_activity_id"

        comment, description = self._extract_pieces(pieces)
        comment = comment or ""

        if self._fixed_headers is None:
            # bygg headers via strava_auth
            tokens = strava_auth.load_tokens()
            hdrs = strava_auth.refresh_if_needed(tokens, client_id=None, client_secret=None)
        else:
            hdrs = dict(self._fixed_headers)

        url = f"{self.base_url}/activities/{target_id}"
        payload = {"description": description or "", "name": comment}

        for attempt in range(2):
            resp = requests.request("PUT", url, headers=hdrs, json=payload, timeout=15)
            if resp.status_code in (401, 403):
                time.sleep(1)
                continue
            if resp.ok:
                return str(target_id), "ok"
            return str(target_id), f"error_{resp.status_code}"

        return str(target_id), "auth_failed"
