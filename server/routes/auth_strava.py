# server/routes/auth_strava.py
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode, unquote, urlparse

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from server.auth.local_auth import COOKIE_NAME, verify_session

router = APIRouter()


# ----------------------------
# Local auth dependency (SSOT cookie -> uid)
# ----------------------------
def require_auth(req: Request) -> str:
    raw = req.cookies.get(COOKIE_NAME)
    payload = verify_session(raw or "")
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return payload["uid"]


STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


# ----------------------------
# OAuth state: signed + TTL (PATCH 2.2.1)
# ----------------------------
def _oauth_secret() -> bytes:
    """
    Secret for signing OAuth state.
    Prefer dedicated env var, fallback to STRAVA_CLIENT_SECRET.
    """
    sec = (os.getenv("CG_OAUTH_STATE_SECRET") or "").strip()
    if not sec:
        sec = (os.getenv("STRAVA_CLIENT_SECRET") or "").strip()
    if not sec:
        raise HTTPException(
            status_code=500,
            detail="Missing CG_OAUTH_STATE_SECRET (or STRAVA_CLIENT_SECRET) for signing OAuth state",
        )
    return sec.encode("utf-8")


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _sign_state(payload_b64: str) -> str:
    mac = hmac.new(_oauth_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(mac)


def _make_state(uid: str, ttl_sec: int = 600) -> str:
    """
    Create signed state token binding to uid + expiry.
    TTL default: 10 minutes (600s).
    Format: v1.<payload_b64>.<sig_b64>
    """
    now = int(time.time())
    payload = {
        "uid": uid,
        "iat": now,
        "exp": now + int(ttl_sec),
        "nonce": secrets.token_urlsafe(12),
    }
    payload_b = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_b64 = _b64url_encode(payload_b)
    sig_b64 = _sign_state(payload_b64)
    return f"v1.{payload_b64}.{sig_b64}"


def _verify_state(state: str) -> str:
    """
    Verify signed state + TTL. Returns uid if OK, else raises HTTPException.
    Fail-closed.
    """
    if not state or not isinstance(state, str):
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    parts = state.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        raise HTTPException(status_code=400, detail="Invalid OAuth state format")

    _ver, payload_b64, sig_b64 = parts

    expected_sig = _sign_state(payload_b64)
    if not hmac.compare_digest(expected_sig, sig_b64):
        raise HTTPException(status_code=400, detail="OAuth state signature mismatch")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="OAuth state decode failed")

    uid = payload.get("uid")
    exp = payload.get("exp")
    if not uid or not isinstance(uid, str):
        raise HTTPException(status_code=400, detail="OAuth state missing uid")
    if not isinstance(exp, int):
        raise HTTPException(status_code=400, detail="OAuth state missing exp")

    now = int(time.time())
    if exp < now:
        raise HTTPException(status_code=400, detail="OAuth state expired")

    return uid


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
# Protected endpoints må bruke require_auth (session cookie SSOT).
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
    """
    Dev-safe redirect_uri that avoids localhost vs 127.0.0.1 cookie loss.
    Priority:
      1) Explicit env override if set
      2) Derive hostname from Origin header (frontend host)
      3) Fallback to request hostname
    """
    explicit = os.getenv("STRAVA_REDIRECT_URI") or os.getenv("CG_STRAVA_REDIRECT_URI")
    if explicit:
        return explicit

    origin = req.headers.get("origin") or ""
    host = ""
    if origin:
        try:
            host = urlparse(origin).hostname or ""
        except Exception:
            host = ""

    if not host:
        host = req.url.hostname or "localhost"

    # In dev we always run backend on 5175; keep it explicit to be safe.
    return f"http://{host}:5175/api/auth/strava/callback"


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
# Routes (protected => use require_auth SSOT)
# ----------------------------
@router.get("/status")
def strava_status(req: Request, user_id: str = Depends(require_auth)):
    uid = user_id  # SSOT

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

    Patch 2.2.1:
    - signed state + TTL, fail-closed (state er SSOT)
    """
    uid = user_id
    redirect_uri = _effective_redirect_uri(req)
    cid, _csec = _require_env()

    state = _make_state(uid)

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

    Patch 2.2.1:
    - state må finnes
    - verify signed state + TTL
    - fail-closed hvis state-uid != user_id
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Strava OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing ?code from Strava")

    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    uid_from_state = _verify_state(state)
    if uid_from_state != user_id:
        raise HTTPException(status_code=401, detail="OAuth state does not match authenticated user")

    uid = user_id

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
        resp.set_cookie("cg_next", "", httponly=True, samesite="lax", max_age=0, path="/")
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

    resp.set_cookie("cg_uid", uid, httponly=True, samesite="lax", path="/")

    # clear legacy cookies (if any)
    resp.set_cookie("cg_next", "", httponly=True, samesite="lax", max_age=0, path="/")
    resp.set_cookie("cg_oauth_state", "", httponly=True, samesite="lax", max_age=0, path="/")
    return resp


# --- ALIASES for legacy Strava redirect paths ---
@router.get("/api/auth/strava/login")
def login_alias(req: Request):
    """
    Legacy alias: frontend (eller gammel kode) kan sende brukeren hit.
    Vi videresender til den "riktige" /login-endepunktet, men sørger for at
    next ikke er dobbelt-encodet.
    """
    next_q = req.query_params.get("next") or ""

    try:
        next_q = unquote(next_q)
        if "%2F" in next_q or "%3A" in next_q:
            next_q = unquote(next_q)
    except Exception:
        pass

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
