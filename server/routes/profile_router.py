from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import Any, Dict
from server.utils.versioning import get_profile_export, save_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])

@router.get("/get")
def get_profile() -> Dict[str, Any]:
    return get_profile_export()

@router.put("/save")
def save_profile_route(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        saved = save_profile(body or {})
        return {
            "profile": {k: saved.get(k) for k in ("rider_weight_kg","bike_type","bike_weight_kg","tire_width_mm","tire_quality","device")},
            "profile_version": saved.get("profile_version"),
            "version_hash": saved.get("version_hash"),
            "version_at": saved.get("version_at"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"save error: {e}")
