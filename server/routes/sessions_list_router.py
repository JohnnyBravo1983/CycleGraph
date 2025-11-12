from __future__ import annotations
from fastapi import APIRouter
from typing import Any, Dict, List
import glob, json, os

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.get("/list")
def list_sessions() -> List[Dict[str,Any]]:
    rows: List[Dict[str,Any]] = []
    base = os.path.join(os.getcwd(), "logs", "results")
    for path in glob.glob(os.path.join(base, "result_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            rows.append({
                "ride_id": str(doc.get("ride_id") or doc.get("id") or ""),
                "profile_version": doc.get("profile_version"),
                "weather_source": (doc.get("weather_source") or (doc.get("metrics") or {}).get("weather_source")),
            })
        except Exception:
            continue
    return rows
