from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, Response, Cookie

from server.utils.versioning import get_profile_export, save_profile
from server.routes.auth_strava import _get_or_set_uid  # gjenbruk samme uid-cookie-logikk

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _uid(req: Request, resp: Response, cg_uid: str | None) -> str:
    # Bruk cookie hvis finnes, ellers generer og sett cookie
    return cg_uid or _get_or_set_uid(req, resp)


@router.get("/get")
def get_profile(req: Request, response: Response, cg_uid: str | None = Cookie(default=None)) -> Dict[str, Any]:
    uid = _uid(req, response, cg_uid)
    return get_profile_export(uid)


@router.put("/save")
def save_profile_route(
    body: Dict[str, Any],
    req: Request,
    response: Response,
    cg_uid: str | None = Cookie(default=None),
) -> Dict[str, Any]:
    uid = _uid(req, response, cg_uid)
    try:
        saved = save_profile(uid, body or {})
        return {
            "profile": {k: saved.get(k) for k in ("rider_weight_kg","bike_type","bike_weight_kg","tire_width_mm","tire_quality","device")},
            "profile_version": saved.get("profile_version"),
            "version_hash": saved.get("version_hash"),
            "version_at": saved.get("version_at"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"save error: {e}")
