# server/routes/auth_local.py
from __future__ import annotations

import os
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from server.auth.local_auth import (
    COOKIE_NAME,
    ensure_uid,
    login_for_uid,
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
    # Ensure cg_uid exists (prime cookie if missing)
    resp = Response(media_type="application/json")
    uid = ensure_uid(req, resp)

    try:
        u = signup_for_uid(uid, payload.email, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = sign_session(uid, ttl_seconds=COOKIE_TTL)
    _set_auth_cookie(resp, token)
    resp.body = bytes(f'{{"ok":true,"uid":"{u["uid"]}","email":"{u["email"]}"}}', "utf-8")
    return resp


@router.post("/login")
def login(req: Request, payload: LoginIn):
    resp = Response(media_type="application/json")
    uid = ensure_uid(req, resp)

    try:
        u = login_for_uid(uid, payload.email, payload.password)
    except ValueError as e:
        # feil credentials -> 401, andre -> 400
        msg = str(e)
        code = 401 if "Invalid credentials" in msg else 400
        raise HTTPException(status_code=code, detail=msg)

    token = sign_session(uid, ttl_seconds=COOKIE_TTL)
    _set_auth_cookie(resp, token)
    resp.body = bytes(f'{{"ok":true,"uid":"{u["uid"]}","email":"{u["email"]}"}}', "utf-8")
    return resp


@router.post("/logout")
def logout():
    resp = Response(content='{"ok":true}', media_type="application/json")
    _clear_auth_cookie(resp)
    return resp


@router.get("/me")
def me(req: Request):
    raw = req.cookies.get(COOKIE_NAME)
    payload = verify_session(raw or "")
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Return uid from session, and email from user store if present
    uid = payload["uid"]
    u = me_from_request(req)
    # If cg_uid cookie missing or mismatch, still return uid from session (source of truth)
    email = (u or {}).get("email")
    return {"ok": True, "uid": uid, "email": email}

