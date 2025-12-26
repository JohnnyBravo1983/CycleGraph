# server/routes/auth_strava.py
from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter()

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


# ----------------------------
# Storage (multi-user-ready)
# ----------------------------
def _repo_root() -> Path:
    # .../server/routes/auth_strava.py -> repo root
    return Path(__file__).resolve().parents[2]


def _users_dir() -> Path:
    # tokens per user inside repo (can be swapped later to DB)
    return _repo_root() / "state" / "users"


def _get_or_set_uid(req: Request, resp: Optional[Response] = None) -> str:
    uid = req.cookies.get("cg_uid")
    if uid and isinstance(uid, str) and len(uid) >= 10:
        return uid

    # generate new anon uid (strip urlsafe chars that can be annoying in paths/logs)
    uid = "u_" + secrets.token_urlsafe(16).replace("-", "").replace("_", "")

    # If a response object is provided, prime the cookie immediately.
    if resp is not None:
        resp.set_cookie(
            key="cg_uid",
            value=uid,
            httponly=True,
            samesite="lax",
            path="/",
        )

    return uid


def _token_path_for_uid(uid: str) -> Path:
    return _users_dir() / uid / "strava_tokens.json"


def _save_tokens(uid: str, tokens: Dict[str, Any]) -> Path:
    p = _token_path_for_uid(uid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _load_tokens(uid: str) -> Optional[Dict[str, Any]]:
    p = _token_path_for_uid(uid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ----------------------------
# Helpers
# ----------------------------
def _effective_redirect_uri(req: Request) -> str:
    # Prefer explicit env var; else build from request base URL
    # Example: http://localhost:5175/api/auth/strava/callback
    env = (os.getenv("STRAVA_REDIRECT_URI") or "").strip()
    if env:
        return env
    base = str(req.base_url).rstrip("/")
    return f"{base}/api/auth/strava/callback"


def _require_env() -> tuple[str, str]:
    cid = (os.getenv("STRAVA_CLIENT_ID") or "").strip()
    csec = (os.getenv("STRAVA_CLIENT_SECRET") or "").strip()
    if not cid or not csec:
        raise HTTPException(
            status_code=500,
            detail="Missing STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET in environment (.env)",
        )
    return cid, csec


def _exchange_code_for_tokens(code: str, redirect_uri: str) -> Dict[str, Any]:
    cid, csec = _require_env()
    payload = {
        "client_id": cid,
        "client_secret": csec,
        "code": code,
        "grant_type": "authorization_code",
        # Strava does not require redirect_uri for token exchange in all cases,
        # but including it makes debugging clearer if you later enforce it.
        "redirect_uri": redirect_uri,
    }

    r = requests.post(STRAVA_TOKEN_URL, data=payload, timeout=30)
    if r.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Strava token exchange failed: HTTP {r.status_code}: {r.text[:400]}",
        )
    data = r.json()
    # Expect: access_token, refresh_token, expires_at
    for k in ("access_token", "refresh_token", "expires_at"):
        if k not in data:
            raise HTTPException(status_code=502, detail=f"Strava response missing {k}")
    return data


# ----------------------------
# Routes
# ----------------------------
@router.get("/status")
def status(
    req: Request,
    response: Response,
    cg_uid: str | None = Cookie(default=None),
):
    """
    Status endpoint for local dev + onboarding.

    RULE (Patch 4.3):
    - If cookie is missing -> generate new uid -> set cookie -> done.
    - Never "pick" another uid from disk.
    """
    # 1) Use cookie uid if present, else create & PRIME cookie via response
    uid = cg_uid or _get_or_set_uid(req, response)

    # 2) Load tokens for this uid only (no disk-scanning fallback)
    tokens = _load_tokens(uid)

    ok = bool(tokens and tokens.get("access_token"))
    exp = int(tokens.get("expires_at", 0)) if tokens else 0
    now = int(time.time())

    # 🔒 Always set cookie explicitly (PowerShell + onboarding)
    response.set_cookie(
        key="cg_uid",
        value=uid,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return {
        "ok": ok,
        "uid": uid,
        "has_tokens": ok,
        "expires_at": exp,
        "expires_in_sec": (exp - now) if exp else None,
        "token_path": str(_token_path_for_uid(uid)),
        "redirect_uri_effective": _effective_redirect_uri(req),
    }


@router.get("/login")
def login(req: Request):
    uid = _get_or_set_uid(req)
    redirect_uri = _effective_redirect_uri(req)

    cid, _csec = _require_env()

    # state binds callback to this browser session/user
    state = "st_" + secrets.token_urlsafe(16)

    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "auto",
        # Choose minimum needed scopes for ingest:
        # read + activity:read_all is typical for fetching activities/streams
        "scope": "read,activity:read_all",
        "state": state,
    }

    url = f"{STRAVA_AUTH_URL}?{urlencode(params)}"
    resp = RedirectResponse(url=url, status_code=302)

    # cookie-based anon user id (multi-user baseline)
    # store uid + state in cookies for later verification
    resp.set_cookie("cg_uid", uid, httponly=True, samesite="lax", path="/")
    resp.set_cookie("cg_oauth_state", state, httponly=True, samesite="lax", path="/")

    # stash return URL for callback redirect (from /login?next=...)
    next_url = req.query_params.get("next")
    if next_url and isinstance(next_url, str) and next_url.startswith(("http://", "https://")):
        resp.set_cookie("cg_next", next_url, httponly=True, samesite="lax", path="/")

    return resp


@router.get("/callback")
def callback(
    req: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    uid = _get_or_set_uid(req)

    if error:
        raise HTTPException(status_code=400, detail=f"Strava OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing ?code from Strava")

    expected_state = req.cookies.get("cg_oauth_state")
    if expected_state and state and state != expected_state:
        raise HTTPException(status_code=400, detail="OAuth state mismatch")

    redirect_uri = _effective_redirect_uri(req)
    data = _exchange_code_for_tokens(code=code, redirect_uri=redirect_uri)

    # Persist only what we need + some metadata for debugging
    tokens = {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_at": int(data.get("expires_at") or 0),
        "token_type": data.get("token_type"),
        "scope": data.get("scope"),
        "athlete": data.get("athlete"),
        "received_at": int(time.time()),
    }
    p = _save_tokens(uid, tokens)

    # If frontend provided a return URL via /login?next=..., send user back there.
    next_url = req.cookies.get("cg_next")
    if next_url and isinstance(next_url, str) and next_url.startswith(("http://", "https://")):
        resp = RedirectResponse(url=next_url, status_code=302)
        resp.set_cookie("cg_uid", uid, httponly=True, samesite="lax", path="/")
        resp.set_cookie("cg_oauth_state", "", httponly=True, samesite="lax", max_age=0, path="/")
        resp.set_cookie("cg_next", "", httponly=True, samesite="lax", max_age=0, path="/")
        return resp

    # fallback: keep JSON response (useful for debugging / manual testing)
    resp = JSONResponse(
        {
            "ok": True,
            "uid": uid,
            "saved_to": str(p),
            "expires_at": tokens["expires_at"],
            "scope": tokens.get("scope"),
            "next": "Now you can call server-side import using this user's tokens.",
        }
    )
    resp.set_cookie("cg_uid", uid, httponly=True, samesite="lax", path="/")
    # clear state cookie (one-time)
    resp.set_cookie("cg_oauth_state", "", httponly=True, samesite="lax", max_age=0, path="/")
    return resp


# --- ALIASES for legacy Strava redirect paths ---
# Some Strava apps are configured with /api/auth/strava/callback.
# We keep /login + /callback as the canonical routes, but add these
# aliases to avoid 404 and reduce UX confusion.

@router.get("/api/auth/strava/login")
def login_alias(req: Request):
    # forward to canonical /login (preserve querystring if any)
    qs = dict(req.query_params)
    url = "/login"
    if qs:
        url = f"{url}?{urlencode(qs)}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/api/auth/strava/callback")
def callback_alias(request: Request):
    # forward querystring to canonical /callback
    qs = dict(request.query_params)
    url = "/callback"
    if qs:
        url = f"{url}?{urlencode(qs)}"
    return RedirectResponse(url=url, status_code=302)
