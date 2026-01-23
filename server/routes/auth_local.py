from __future__ import annotations

import os
import secrets
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

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_SECURE = os.getenv("CG_COOKIE_SECURE", "0").strip() == "1"
COOKIE_SAMESITE = os.getenv("CG_COOKIE_SAMESITE", "lax")  # lax|strict|none
COOKIE_TTL = int(os.getenv("CG_AUTH_TTL_SECONDS", str(60 * 60 * 24 * 7)))  # 7d


class SignupIn(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


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
    """

    # 🔒 HARD RESET AUTH CONTEXT (signup er alltid identitetsskapende)
    # NB: Slett først, så setter vi ny state etterpå.
    resp = JSONResponse({"ok": False})  # midlertidig; overskrives før return
    resp.delete_cookie(COOKIE_NAME, path="/")
    resp.delete_cookie("cg_uid", path="/")
    resp.delete_cookie("cg_next", path="/")
    resp.delete_cookie("cg_oauth_state", path="/")

    # Generér ny uid (alltid fresh)
    uid = "u_" + secrets.token_urlsafe(16).replace("-", "").replace("_", "")

    try:
        u = signup_for_uid(uid, payload.email, payload.password)
    except ValueError as e:
        # Returner med cookies allerede slettet for å unngå halv-state
        raise HTTPException(status_code=400, detail=str(e))

    token = sign_session(uid, ttl_seconds=COOKIE_TTL)

    # ✅ bruk JSONResponse (unngå Content-Length/body crash)
    resp = JSONResponse({"ok": True, "uid": u["uid"], "email": u["email"]})

    # 🔥 OVERSKRIV ALL TIDLIGERE AUTH STATE
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

    # ✅ PATCH: bruk JSONResponse (unngå Content-Length/body crash)
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
    # ✅ PATCH: bruk JSONResponse + clear cg_auth og legacy helper cookies
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
