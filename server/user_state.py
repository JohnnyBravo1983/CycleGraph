import os
import json
from pathlib import Path
from typing import Any, Dict, List


def state_root() -> Path:
    """
    Source of truth for persistent state.
    - Fly: /app/state (via volume mount)
    - Local/dev: <repo>/state
    """
    env = (os.getenv("CG_STATE_DIR") or "").strip()
    if env:
        return Path(env)
    
    # ✅ FIX: Default to /app/state if in Fly container
    if Path("/app/state").exists():
        return Path("/app/state")
    
    # Fallback: local dev repo-root/state
    return Path(__file__).resolve().parents[1] / "state"


def user_dir(base_dir: str, uid: str) -> str:
    # PATCH: use state_root() as SSOT for where "state" lives.
    # base_dir is kept for compatibility with existing call sites.
    return str(state_root() / "users" / uid)


def user_sessions_index_path(base_dir: str, uid: str) -> str:
    return os.path.join(user_dir(base_dir, uid), "sessions_index.json")


def ensure_user_dir(base_dir: str, uid: str) -> str:
    p = user_dir(base_dir, uid)
    os.makedirs(p, exist_ok=True)
    return p


def load_user_sessions_index(base_dir: str, user_id: str) -> Dict[str, Any]:
    """
    Leser state/users/<uid>/sessions_index.json.
    Tåler UTF-8 BOM (utf-8-sig) og returnerer alltid en dict med "sessions": list.
    """
    path = os.path.join(user_dir(base_dir, str(user_id)), "sessions_index.json")
    if not os.path.exists(path):
        return {"sessions": []}

    try:
        # FIX: tåler JSON-filer med UTF-8 BOM
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f) or {}
    except Exception:
        return {"sessions": []}

    if not isinstance(data, dict):
        return {"sessions": []}

    sessions = data.get("sessions")
    if not isinstance(sessions, list):
        data["sessions"] = []

    return data


def save_user_sessions_index(base_dir: str, uid: str, data: Dict[str, Any]) -> None:
    ensure_user_dir(base_dir, uid)
    p = user_sessions_index_path(base_dir, uid)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def maybe_bootstrap_demo_sessions(base_dir: str, uid: str) -> None:
    """
    DEV/DEMO ONLY:
    Hvis CG_DEMO_BOOTSTRAP=1 og user mangler sessions_index.json,
    kopier global state/sessions_index.json -> state/users/<uid>/sessions_index.json
    og stamp uid på alle items slik at eiersjekk fungerer.

    Viktig (Task 1.3 / cascading delete):
    - Denne funksjonen skal ALDRI "resurrecte" en slettet bruker ved å opprette state/users/<uid>/.
    - Vi bootstrapper kun hvis user_dir allerede finnes (dvs. brukeren eksisterer i state).
    """
    if os.getenv("CG_DEMO_BOOTSTRAP", "").strip() != "1":
        return

    # FAIL-CLOSED: ikke opprett user-dir på read-endpoints
    u_dir = user_dir(base_dir, uid)
    if not os.path.isdir(u_dir):
        return

    u_path = user_sessions_index_path(base_dir, uid)
    if os.path.exists(u_path):
        return

    # global sessions index under state_root()
    g_path = str(state_root() / "sessions_index.json")
    if not os.path.exists(g_path):
        # Ingen global index å bootstrappe fra (og vi skal ikke skrive en tom index her)
        return

    try:
        with open(g_path, "r", encoding="utf-8-sig") as f:
            g = json.load(f)
    except Exception:
        return

    sessions: List[Dict[str, Any]] = []
    if isinstance(g, dict) and isinstance(g.get("sessions"), list):
        sessions = [x for x in g["sessions"] if isinstance(x, dict)]
    elif isinstance(g, list):
        sessions = [x for x in g if isinstance(x, dict)]

    # stamp uid
    for it in sessions:
        it["uid"] = uid

    # OK å skrive nå, siden user_dir allerede eksisterer
    save_user_sessions_index(base_dir, uid, {"sessions": sessions})
