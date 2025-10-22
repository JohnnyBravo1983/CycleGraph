from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# --- Paths -------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _REPO_ROOT / "data"
_SESSIONS_DIR = _DATA_DIR / "sessions"
_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def _sessions_dir() -> str:
    return str(_SESSIONS_DIR)

def _session_path(session_id: str) -> str:
    return str(_SESSIONS_DIR / f"{session_id}.json")

# --- Low-level IO ------------------------------------------------------
def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=str(_SESSIONS_DIR))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

# --- Defaults / Mutators -----------------------------------------------
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _ensure_defaults(s: Dict[str, Any], *, session_id: Optional[str] = None) -> None:
    defaults: Dict[str, Any] = {
        "session_id": session_id,
        "precision_watt": None,
        "precision_watt_ci": None,
        "strava_activity_id": None,
        "publish_state": None,
        "publish_time": None,
        "publish_hash": "",
        "publish_error": None,
    }
    for k, v in defaults.items():
        if k == "session_id" and session_id is None:
            continue
        if k not in s:
            s[k] = v

def set_publish_pending(s: Dict[str, Any]) -> None:
    s["publish_state"] = "pending"
    s["publish_time"] = _utc_now_iso()
    if "publish_hash" not in s or s.get("publish_hash") is None:
        s["publish_hash"] = ""
    s["publish_error"] = None

def set_publish_done(s: Dict[str, Any], new_hash: str) -> None:
    s["publish_state"] = "done"
    s["publish_time"] = _utc_now_iso()
    s["publish_hash"] = new_hash or ""
    s["publish_error"] = None

def set_publish_failed(s: Dict[str, Any], message: str) -> None:
    s["publish_state"] = "failed"
    s["publish_time"] = _utc_now_iso()
    s["publish_error"] = str(message or "Unknown error")

# --- Public API ---------------------------------------------------------
def load_session(session_id: str) -> Dict[str, Any]:
    path = _session_path(session_id)
    if not os.path.exists(path):
        data: Dict[str, Any] = {"session_id": session_id}
        _ensure_defaults(data, session_id=session_id)
        _atomic_write_json(path, data)
        return data
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        data = {"session_id": session_id}
    _ensure_defaults(data, session_id=session_id)
    return data

def save_session(session_id: str, data: Dict[str, Any]) -> None:
    data["session_id"] = session_id
    _ensure_defaults(data, session_id=session_id)
    _atomic_write_json(_session_path(session_id), data)

