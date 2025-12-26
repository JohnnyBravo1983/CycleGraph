from __future__ import annotations

from fastapi import APIRouter, HTTPException, Cookie, Request, Response
from typing import Any, Dict

from server.utils.versioning import get_profile_export, save_profile
from server.routes.auth_strava import _get_or_set_uid

router = APIRouter(prefix="/api/profile", tags=["profile"])

@router.get("/get")
def get_profile_route(
    req: Request,
    response: Response,
    cg_uid: str | None = Cookie(default=None),
) -> Dict[str, Any]:
    uid = cg_uid or _get_or_set_uid(req, response)
    return get_profile_export(uid)

@router.put("/save")
def save_profile_route(
    body: Dict[str, Any],
    req: Request,
    response: Response,
    cg_uid: str | None = Cookie(default=None),
) -> Dict[str, Any]:
    try:
        uid = cg_uid or _get_or_set_uid(req, response)
        saved = save_profile(uid, body or {})
        return {
            "profile": {k: saved.get(k) for k in ("rider_weight_kg","bike_type","bike_weight_kg","tire_width_mm","tire_quality","device")},
            "profile_version": saved.get("profile_version"),
            "version_hash": saved.get("version_hash"),
            "version_at": saved.get("version_at"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"save error: {e}")
