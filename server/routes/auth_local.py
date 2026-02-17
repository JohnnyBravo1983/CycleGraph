from __future__ import annotations

import os
import secrets
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from server.auth.local_auth import (
    COOKIE_NAME,
    login_by_email,
    me_from_request,
    sign_session,
    signup_for_uid,
    verify_session,
)

# NEW: admin alert helper (fail-safe)
from server.utils.admin_alerts import send_admin_alert_new_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_SECURE = os.getenv("CG_COOKIE_SECURE", "0").strip() == "1"
COOKIE_SAMESITE = os.getenv("CG_COOKIE_SAMESITE", "lax")  # lax|strict|none
COOKIE_TTL = int(os.getenv("CG_AUTH_TTL_SECONDS", str(60 * 60 * 24 * 7)))  # 7d

# Optional feature flag (safe rollout)
NEW_USER_ALERTS_ENABLED = os.getenv("NEW_USER_ALERTS_ENABLED", "1").strip() == "1"


class SignupIn(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)

    # NEW: identity fields wanted in auth.json + email alert
    full_name: str = Field(..., min_length=2)

    # existing demographic fields
    gender: Literal["male", "female"]
    country: str = Field(..., min_length=2)
    city: str = Field(..., min_length=2)
    age: int = Field(..., ge=13, le=100)

    # OPTIONAL: include if you want it in the admin mail (and stored in auth.json)
    bike_name: Optional[str] = Field(None, min_length=1)


class LoginIn(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


def _set_auth_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
        max_age=COOKIE_TTL,
    )


def _clear_auth_cookie(resp: Response) -> None:
    resp.set_cookie(
        key=COOKIE_NAME,
        value="",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
        max_age=0,
    )


@router.post("/signup")
def signup(req: Request, payload: SignupIn):
    """
    PATCH 1 – Backend: gjør signup alltid “fresh”
    - Ignorer eksisterende cookies
    - Slett eksisterende auth-cookies eksplisitt
    - Deretter opprett ny identitet (uid)

    NEW (Sprint: New User Alerts v0)
    - Persist full_name -> auth.json (display_name)
    - Optional: persist bike_name
    - Send admin email alert (fail-safe)
    """

    # 🔒 HARD RESET AUTH CONTEXT (signup er alltid identitetsskapende)
    resp = JSONResponse({"ok": False})  # midlertidig; overskrives før return
    resp.delete_cookie(COOKIE_NAME, path="/")
    resp.delete_cookie("cg_uid", path="/")
    resp.delete_cookie("cg_next", path="/")
    resp.delete_cookie("cg_oauth_state", path="/")

    # Generér ny uid (alltid fresh)
    uid = "u_" + secrets.token_urlsafe(16).replace("-", "").replace("_", "")

    try:
        # NOTE: signup_for_uid MUST be updated to accept display_name/bike_name
        u = signup_for_uid(
            uid,
            payload.email,
            payload.password,
            payload.gender,
            payload.country,
            payload.city,
            payload.age,
            display_name=payload.full_name,
            bike_name=payload.bike_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fire-and-forget style: do NOT block signup on SMTP issues
    if NEW_USER_ALERTS_ENABLED:
        try:
            ok = send_admin_alert_new_user(u)
            if ok:
                print(f"NEW_USER_ALERT sent uid={u.get('uid')} email={u.get('email')}")
        except Exception as e:
            print(
                f"NEW_USER_ALERT crashed uid={u.get('uid')} email={u.get('email')} "
                f"err={type(e).__name__}: {e}"
            )

    token = sign_session(uid, ttl_seconds=COOKIE_TTL)

    resp = JSONResponse(
        {
            "ok": True,
            "uid": u["uid"],
            "email": u["email"],
            # optional to return (handy for UI)
            "display_name": u.get("display_name"),
        }
    )

    _set_auth_cookie(resp, token)

    # legacy helper cookie (ikke autoritativ identitet)
    resp.set_cookie(
        key="cg_uid",
        value=uid,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=COOKIE_TTL,
    )

    # 🔥 EKSTRA: slett evt gamle helpers
    resp.delete_cookie("cg_next", path="/")
    resp.delete_cookie("cg_oauth_state", path="/")

    return resp


@router.post("/login")
def login(req: Request, payload: LoginIn):
    """
    PATCH 2:
    - Login via login_by_email(email, password) (email->uid index)
    - Signér cg_auth (COOKIE_NAME)
    - (valgfritt) sett cg_uid=uid som legacy helper cookie
    """
    try:
        u = login_by_email(payload.email, payload.password)
    except ValueError as e:
        msg = str(e)
        code = 401 if "Invalid credentials" in msg else 400
        raise HTTPException(status_code=code, detail=msg)

    uid = str(u["uid"])
    token = sign_session(uid, ttl_seconds=COOKIE_TTL)

    resp = JSONResponse({"ok": True, "uid": uid, "email": u["email"]})
    _set_auth_cookie(resp, token)

    # legacy helper cookie (ikke autoritativ identitet)
    resp.set_cookie(
        key="cg_uid",
        value=uid,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )

    return resp


@router.post("/logout")
def logout():
    resp = JSONResponse({"ok": True})

    _clear_auth_cookie(resp)

    # clear legacy helper cookies as well
    resp.set_cookie(
        key="cg_uid",
        value="",
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
        max_age=0,
    )
    resp.set_cookie(
        key="cg_next",
        value="",
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
        max_age=0,
    )
    resp.set_cookie(
        key="cg_oauth_state",
        value="",
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
        max_age=0,
    )

    return resp


@router.get("/me")
def me(req: Request):
    """
    Patch 3E:
    - /me bruker kun cg_auth (COOKIE_NAME) som source of truth.
    - cg_uid kan eksistere, men ignoreres som identitet.
    """
    raw = req.cookies.get(COOKIE_NAME)
    payload = verify_session(raw or "")
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")

    uid = payload["uid"]
    u = me_from_request(req)
    email = (u or {}).get("email")
    return {"ok": True, "uid": uid, "email": email}

