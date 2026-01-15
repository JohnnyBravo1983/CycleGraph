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
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from server.auth_guard import require_auth

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


# NOTE (Patch 3E):
# cg_uid kan eksistere som legacy helper cookie, men skal aldri være autoritativ identitet.
# Protected endpoints må bruke request.state.user_id / require_auth.
def _get_or_set_uid_legacy(req: Request) -> str:
    """
    Legacy helper: beholdes kun for kompatibilitet / debugging.
    Skal ikke brukes som autoritativ identitet for protected endpoints.
    """
    uid = req.cookies.get("cg_uid")
    if uid and isinstance(uid, str) and len(uid) >= 10:
        return uid
    uid = "u_" + secrets.token_urlsafe(16).replace("-", "").replace("_", "")
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
        "redirect_uri": redirect_uri,
    }

    r = requests.post(STRAVA_TOKEN_URL, data=payload, timeout=30)
    if r.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Strava token exchange failed: HTTP {r.status_code}: {r.text[:400]}",
        )
    data = r.json()
    for k in ("access_token", "refresh_token", "expires_at"):
        if k not in data:
            raise HTTPException(status_code=502, detail=f"Strava response missing {k}")
    return data


# ----------------------------
# Routes (Patch 3E: protected => use request.state.user_id)
# ----------------------------
@router.get("/status")
def strava_status(
    req: Request,
    user_id: str = Depends(require_auth),
):
    """
    Status endpoint for onboarding/dev.

    Patch 3E:
    - Identitet = request.state.user_id (via require_auth)
    - cg_uid kan settes som legacy helper cookie, men er aldri autoritativ.
    """
    uid = user_id

    tokens = _load_tokens(uid)

    ok = bool(tokens and tokens.get("access_token"))
    exp = int(tokens.get("expires_at", 0)) if tokens else 0
    now = int(time.time())

    resp = JSONResponse(
        {
            "ok": ok,
            "uid": uid,
            "has_tokens": ok,
            "expires_at": exp,
            "expires_in_sec": (exp - now) if exp else None,
            "token_path": str(_token_path_for_uid(uid)),
            "redirect_uri_effective": _effective_redirect_uri(req),
        }
    )

    # legacy helper cookie (ikke autoritativ identitet)
    resp.set_cookie(
        key="cg_uid",
        value=uid,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return resp


@router.get("/login")
def login(
    req: Request,
    user_id: str = Depends(require_auth),
):
    """
    Starter Strava OAuth for INNLOGGET bruker.

    Patch 3E:
    - bruker_id = request.state.user_id (via require_auth)
    - cg_uid brukes ikke som identitet (kun evt legacy helper cookie)
    """
    uid = user_id
    redirect_uri = _effective_redirect_uri(req)
    cid, _csec = _require_env()

    state = "st_" + secrets.token_urlsafe(16)

    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "auto",
        "scope": "read,activity:read_all",
        "state": state,
    }

    url = f"{STRAVA_AUTH_URL}?{urlencode(params)}"
    resp = RedirectResponse(url=url, status_code=302)

    # bind callback til denne browser-sessionen
    resp.set_cookie("cg_oauth_state", state, httponly=True, samesite="lax", path="/")

    # stash return URL for callback redirect (from /login?next=...)
    next_url = req.query_params.get("next")
    if next_url and isinstance(next_url, str) and next_url.startswith(("http://", "https://")):
        resp.set_cookie("cg_next", next_url, httponly=True, samesite="lax", path="/")

    # legacy helper cookie (ikke autoritativ identitet)
    resp.set_cookie("cg_uid", uid, httponly=True, samesite="lax", path="/")

    return resp


@router.get("/callback")
def callback(
    req: Request,
    user_id: str = Depends(require_auth),
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    Strava redirect callback.

    Patch 3E:
    - lagrer tokens under request.state.user_id
    - ignorerer cg_uid for identitet
    """
    uid = user_id

    if error:
        raise HTTPException(status_code=400, detail=f"Strava OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing ?code from Strava")

    expected_state = req.cookies.get("cg_oauth_state")
    if expected_state and state and state != expected_state:
        raise HTTPException(status_code=400, detail="OAuth state mismatch")

    redirect_uri = _effective_redirect_uri(req)
    data = _exchange_code_for_tokens(code=code, redirect_uri=redirect_uri)

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

    next_url = req.cookies.get("cg_next")
    if next_url and isinstance(next_url, str) and next_url.startswith(("http://", "https://")):
        resp = RedirectResponse(url=next_url, status_code=302)
        resp.set_cookie("cg_oauth_state", "", httponly=True, samesite="lax", max_age=0, path="/")
        resp.set_cookie("cg_next", "", httponly=True, samesite="lax", max_age=0, path="/")
        # legacy helper cookie (ikke autoritativ identitet)
        resp.set_cookie("cg_uid", uid, httponly=True, samesite="lax", path="/")
        return resp

    resp = JSONResponse(
        {
            "ok": True,
            "uid": uid,
            "saved_to": str(p),
            "expires_at": tokens["expires_at"],
            "scope": tokens.get("scope"),
            "next": "Strava tokens saved for this authenticated user.",
        }
    )

    # legacy helper cookie (ikke autoritativ identitet)
    resp.set_cookie("cg_uid", uid, httponly=True, samesite="lax", path="/")

    # clear state cookie (one-time)
    resp.set_cookie("cg_oauth_state", "", httponly=True, samesite="lax", max_age=0, path="/")
    resp.set_cookie("cg_next", "", httponly=True, samesite="lax", max_age=0, path="/")
    return resp


# --- ALIASES for legacy Strava redirect paths ---
# --- ALIASES for legacy Strava redirect paths ---
@router.get("/api/auth/strava/login")
def login_alias(req: Request):
    """
    Legacy alias: frontend (eller gammel kode) kan sende brukeren hit.
    Vi videresender til den "riktige" /login-endepunktet, men sørger for at
    next ikke er dobbelt-encodet.
    """
    next_q = req.query_params.get("next") or ""

    # Unquote 1-2 ganger for å håndtere typisk "http%253A%252F..." (dobbel encoding)
    try:
        next_q = unquote(next_q)
        # Hvis det fortsatt ser encodet ut (inneholder %2F etc), unquote en gang til
        if "%2F" in next_q or "%3A" in next_q:
            next_q = unquote(next_q)
    except Exception:
        pass

    # Forward til /login (samme host) med next som query param.
    # Viktig: bruker urlencode for korrekt encoding av hele URL-en.
    qs = urlencode({"next": next_q}) if next_q else ""
    url = f"/login?{qs}" if qs else "/login"
    return RedirectResponse(url=url, status_code=302)


@router.get("/api/auth/strava/callback")
def callback_alias(request: Request):
    qs = dict(request.query_params)
    url = "/callback"
    if qs:
        url = f"{url}?{urlencode(qs)}"
    return RedirectResponse(url=url, status_code=302)
