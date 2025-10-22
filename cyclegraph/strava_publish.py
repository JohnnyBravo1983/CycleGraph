# cyclegraph/strava_publish.py
from __future__ import annotations
import hashlib, time
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any, Protocol

class Transport(Protocol):
    def patch_activity(self, activity_id: int, payload: Dict[str, Any], token: str) -> "HttpResponse": ...

@dataclass
class HttpResponse:
    status: int
    body: Optional[Dict[str, Any]] = None

class RequestsTransport:
    def __init__(self, base_url: str = "https://www.strava.com/api/v3"):
        import requests
        self._requests = requests
        self._base = base_url

    def patch_activity(self, activity_id: int, payload: Dict[str, Any], token: str) -> HttpResponse:
        url = f"{self._base}/activities/{activity_id}"
        r = self._requests.patch(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=10,
        )
        try:
            body = r.json()
        except Exception:
            body = None
        return HttpResponse(status=r.status_code, body=body)

@dataclass
class PublishResult:
    state: str   # "pending" | "done" | "failed"
    hash: Optional[str]
    message: Optional[str]
    attempts: int

def make_publish_hash(activity_id: int, precision_watt: float, ci: Optional[float]) -> str:
    s = f"{activity_id}:{precision_watt:.6f}:{ci if ci is not None else 'na'}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _format_note(pw: float, ci: Optional[float]) -> str:
    return f"Precision Watt: {pw:.0f}W" if ci is None else f"Precision Watt: {pw:.0f}W (±{ci:.0f}W)"

def publish_precision_watt(
    *,
    activity_id: int,
    precision_watt: float,
    precision_watt_ci: Optional[float],
    token: str,
    previous_publish_hash: Optional[str],
    transport: Transport,
    sleep: Callable[[float], None] = time.sleep,
    max_attempts: int = 3,
    base_backoff: float = 1.0,
) -> PublishResult:
    new_hash = make_publish_hash(activity_id, precision_watt, precision_watt_ci)
    if previous_publish_hash and new_hash == previous_publish_hash:
        return PublishResult(state="done", hash=new_hash, message="Idempotent skip (unchanged).", attempts=0)

    payload = {"description": _format_note(precision_watt, precision_watt_ci)}
    attempts = 0
    backoff = base_backoff

    while attempts < max_attempts:
        attempts += 1
        resp = transport.patch_activity(activity_id, payload, token)

        if resp.status == 200:
            return PublishResult(state="done", hash=new_hash, message="Published to Strava.", attempts=attempts)

        if resp.status == 429:
            if attempts >= max_attempts:
                return PublishResult(state="failed", hash=None, message="Rate limited (429) after retries.", attempts=attempts)
            sleep(backoff); backoff *= 2; continue

        if resp.status in (401, 403):
            return PublishResult(state="failed", hash=None, message=f"Auth/permission error ({resp.status}).", attempts=attempts)

        if attempts >= max_attempts:
            return PublishResult(state="failed", hash=None, message=f"HTTP {resp.status}.", attempts=attempts)
        sleep(backoff); backoff *= 2

    return PublishResult(state="failed", hash=None, message="Unexpected termination.", attempts=attempts)
