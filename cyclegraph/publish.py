from __future__ import annotations
from typing import Optional
from .session_storage import (
    load_session, save_session,
    set_publish_pending, set_publish_done, set_publish_failed,
)
from .strava_publish import publish_precision_watt, RequestsTransport

def maybe_publish_to_strava(session_id: str, token: Optional[str], publish_toggle: bool) -> None:
    if not publish_toggle or not token:
        return

    session = load_session(session_id)
    activity_id = session.get("strava_activity_id")
    pw = session.get("precision_watt")
    ci = session.get("precision_watt_ci")

    if activity_id in (None, "", 0) or pw is None:
        return

    set_publish_pending(session)
    save_session(session_id, session)

    previous_hash = session.get("publish_hash")

    try:
        result = publish_precision_watt(
            activity_id=int(activity_id),
            precision_watt=float(pw),
            precision_watt_ci=(None if ci is None else float(ci)),
            token=token,
            previous_publish_hash=previous_hash,
            transport=RequestsTransport(),
        )
    except Exception as e:
        set_publish_failed(session, f"exception: {e}")
        save_session(session_id, session)
        return

    state = (getattr(result, "state", "") or "").lower()
    new_hash = getattr(result, "hash", None) or previous_hash or ""
    message = getattr(result, "message", None) or None

    if state in ("done", "success", "skip", "idempotent"):
        set_publish_done(session, new_hash)
    elif state in ("failed", "error"):
        set_publish_failed(session, message or "Unknown error")
    else:
        set_publish_failed(session, message or f"Unknown state: {state}")

    save_session(session_id, session)
