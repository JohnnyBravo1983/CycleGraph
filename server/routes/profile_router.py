from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from server.auth_guard import require_auth
from server.utils.versioning import get_profile_export, save_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("/get")
def get_profile(
    req: Request,
    response: Response,
    user_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    uid = user_id
    print("[PROFILE_GET] uid =", uid)
    return get_profile_export(uid)


@router.put("/save")
def save_profile_route(
    body: Dict[str, Any],
    req: Request,
    response: Response,
    user_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    uid = user_id

    try:
        incoming = body or {}
        print("[PROFILE_SAVE] uid =", uid)
        print("[PROFILE_SAVE] raw incoming body =", incoming)

        # ------------------------------------------------------------
        # NORMALISER INPUT (ENDELIG MVP-SIKKER)
        # ------------------------------------------------------------
        profile: Dict[str, Any] = {}

        # 1) Nested profile fra frontend (hvis finnes)
        nested = incoming.get("profile")
        if isinstance(nested, dict):
            profile.update(nested)

        # 2) Flat fields override ALT (eksplisitt vinner)
        for key in (
            "rider_weight_kg",
            "weight_kg",  # kan komme fra enkelte UI-flyter
            "bike_weight_kg",
            "bike_type",
            "tire_width_mm",
            "tire_quality",
            "device",
            "cda",
            "crr",
            "crank_efficiency",
            "crank_eff_pct",
        ):
            if key in incoming and incoming[key] is not None:
                profile[key] = incoming[key]

        # 3) KRITISK: weight_kg → rider_weight_kg
        if "rider_weight_kg" not in profile and "weight_kg" in profile:
            profile["rider_weight_kg"] = profile["weight_kg"]

        # Fjern weight_kg så den ikke skaper tvetydighet videre
        profile.pop("weight_kg", None)

        print("[PROFILE_SAVE] normalized profile =", profile)

        # ------------------------------------------------------------
        # LAGRE (SSOT)
        # ------------------------------------------------------------
        saved = save_profile(uid, profile)

        print(
            "[PROFILE_SAVE] saved rider_weight_kg =",
            saved.get("rider_weight_kg"),
            "profile_version =",
            saved.get("profile_version"),
        )

        return {
            "profile": {
                k: saved.get(k)
                for k in (
                    "rider_weight_kg",
                    "bike_type",
                    "bike_weight_kg",
                    "tire_width_mm",
                    "tire_quality",
                    "device",
                )
            },
            "profile_version": saved.get("profile_version"),
            "version_hash": saved.get("version_hash"),
            "version_at": saved.get("version_at"),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"save error: {e}")
