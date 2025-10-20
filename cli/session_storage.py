# cli/session_storage.py
from __future__ import annotations
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import json

# 📦 Schema-versjon (må samsvare med frontend/schemas/session_metrics.schema.json)
SCHEMA_VERSION = "0.7.3"

# 📁 Data-katalog (opprettes automatisk)
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get(d: Dict[str, Any], key: str, default=None):
    """Trygg get med fallback til default"""
    return d.get(key, default)


def _iso(ts: Optional[str]) -> Optional[str]:
    """Returner ISO-streng hvis tilgjengelig"""
    if ts is None:
        return None
    try:
        # aksepter ISO-streng, eventuelt datetime-objekt
        if isinstance(ts, datetime):
            return ts.isoformat(timespec="seconds") + "Z"
        if isinstance(ts, str) and "T" in ts:
            return ts
    except Exception:
        pass
    return None


def persist_session_metrics(session_id: str, metrics: Dict[str, Any], profile: Dict[str, Any]) -> None:
    """
    Persister resultater fra analyze_session() til data/session_metrics.jsonl (append-only).
    Alle Sprint 14-felter inkluderes. Manglende verdier → null/default.
    """
    record = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "metrics": {
            # eksisterende
            "np": _get(metrics, "np"),
            "if_factor": _get(metrics, "if_factor"),
            "vi": _get(metrics, "vi"),

            # Sprint 14 – nye
            "precision_watt": _get(metrics, "precision_watt"),
            "precision_watt_ci": _get(metrics, "precision_watt_ci"),
            "crr_used": _get(metrics, "crr_used"),
            "CdA": _get(metrics, "CdA") or _get(metrics, "cda"),
            "reason": _get(metrics, "reason"),

            "rider_weight": _get(metrics, "rider_weight"),
            "bike_weight": _get(metrics, "bike_weight"),
            "bike_type": _get(metrics, "bike_type"),
            "tire_width": _get(metrics, "tire_width"),
            "tire_quality": _get(metrics, "tire_quality"),

            "publish_state": _get(metrics, "publish_state", "draft"),
            "publish_hash": _get(metrics, "publish_hash"),
            "published_to_strava": _get(metrics, "published_to_strava", False),
            "publish_time": _iso(_get(metrics, "publish_time")),
        },
        "profile": {
            "consent_accepted": _get(profile, "consent_accepted"),
            "consent_version": _get(profile, "consent_version"),
            "consent_time": _iso(_get(profile, "consent_time")),
            "bike_name": _get(profile, "bike_name"),
        },
    }

    path = DATA_DIR / "session_metrics.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_last_sessions(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Leser de siste N øktene fra data/session_metrics.jsonl.
    Returnerer listen i omvendt rekkefølge (nyeste først).
    """
    path = DATA_DIR / "session_metrics.jsonl"
    if not path.exists():
        return []

    rows = path.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in rows[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue

    return out[::-1]
