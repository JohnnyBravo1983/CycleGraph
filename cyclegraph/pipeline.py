# cyclegraph/pipeline.py
from __future__ import annotations
from typing import Dict, Any, Optional

from .session_storage import save_session
from .settings import get_settings
from .publish import maybe_publish_to_strava

def persist_and_maybe_publish(
    session_id: str,
    session: Dict[str, Any],
    *,
    token: Optional[str] = None,
    publish_toggle: Optional[bool] = None,
) -> None:
    """
    Én inngang for persist + (valgfri) Strava-publisering.
    - Lagrer alltid økten (atomisk).
    - Publiserer hvis toggle/token er sann/tilgjengelig.
    - No-op safe (mangler activity_id/pw → ingen publisering).
    """
    # 1) Persist
    save_session(session_id, session)

    # 2) Publisering (miljø som default)
    settings = get_settings()
    tok = token if token is not None else settings.strava_access_token
    toggle = publish_toggle if publish_toggle is not None else settings.publish_to_strava

    maybe_publish_to_strava(session_id=session_id, token=tok, publish_toggle=toggle)
