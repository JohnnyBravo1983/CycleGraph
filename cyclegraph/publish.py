from __future__ import annotations
from typing import Optional, Dict, Any
from .session_storage import (
    load_session, save_session,
    set_publish_pending, set_publish_done, set_publish_failed,
)
from .strava_publish import publish_precision_watt, RequestsTransport


def maybe_publish_to_strava(session_id: str, token: Optional[str], publish_toggle: bool) -> Dict[str, Any]:
    """
    Forsøk å publisere Precision Watt til Strava for gitt session.

    Returnerer alltid et dict:
      - Ved suksess: {"ok": True,  "state": "...", "hash": "...", "message": "...", "raw": "<repr>"}
      - Ved feil:    {"ok": False, "error": "...",  "state": "...", "hash": "...", "message": "...", "raw": "<repr>"}

    NB: Oppdaterer også session-state via set_publish_pending / set_publish_done / set_publish_failed.
    """

    # 1) Tidlige exits med tydelig grunn
    if not publish_toggle:
        return {"ok": False, "error": "disabled"}
    if not token:
        return {"ok": False, "error": "missing token"}

    session = load_session(session_id)
    activity_id = session.get("strava_activity_id")
    pw = session.get("precision_watt")
    ci = session.get("precision_watt_ci")

    if activity_id in (None, "", 0) or pw is None:
        return {"ok": False, "error": "missing activity_id or precision_watt"}

    # 2) Marker pending før kall
    set_publish_pending(session)
    save_session(session_id, session)

    previous_hash = session.get("publish_hash")

    # 3) Kall Strava-transport
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
        err = f"exception: {e}"
        set_publish_failed(session, err)
        save_session(session_id, session)
        return {"ok": False, "error": err}

    # 4) Normaliser respons/state
    state  = (getattr(result, "state", "") or "").lower()
    new_hash = getattr(result, "hash", None) or previous_hash or ""
    message = getattr(result, "message", None) or None
    raw_repr = repr(result)

    # 5) Oppdater session på grunnlag av state + bygg svar
    if state in ("done", "success", "skip", "idempotent"):
        set_publish_done(session, new_hash)
        save_session(session_id, session)
        return {
            "ok": True,
            "state": state,
            "hash": new_hash,
            "message": message,
            "raw": raw_repr,
        }
    elif state in ("failed", "error"):
        set_publish_failed(session, message or "Unknown error")
        save_session(session_id, session)
        return {
            "ok": False,
            "error": message or "Unknown error",
            "state": state,
            "hash": new_hash,
            "message": message,
            "raw": raw_repr,
        }
    else:
        # Uventet state
        unknown = f"Unknown state: {state}" if state else "Unknown state (empty)"
        set_publish_failed(session, message or unknown)
        save_session(session_id, session)
        return {
            "ok": False,
            "error": message or unknown,
            "state": state or "unknown",
            "hash": new_hash,
            "message": message,
            "raw": raw_repr,
        }
