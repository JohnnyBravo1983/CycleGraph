# server/auth/local_auth.py
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

from fastapi import Request, Response

# -----------------------------------------------------------------------------
# Repo-root + state/users (samme idiom som auth_strava.py)
# -----------------------------------------------------------------------------

def _repo_root() -> Path:
    # .../server/auth/local_auth.py -> repo root
    return Path(__file__).resolve().parents[2]

def _users_dir() -> Path:
    return _repo_root() / "state" / "users"

def _get_or_set_uid(req: Request, resp: Optional[Response] = None) -> str:
    uid = req.cookies.get("cg_uid")
    if uid and isinstance(uid, str) and len(uid) >= 10:
        return uid

    uid = "u_" + secrets.token_urlsafe(16).replace("-", "").replace("_", "")

    if resp is not None:
        resp.set_cookie(
            key="cg_uid",
            value=uid,
            httponly=True,
            samesite="lax",
            path="/",
        )
    return uid

# -----------------------------------------------------------------------------
# User storage (per-uid): state/users/<uid>/auth.json
# -----------------------------------------------------------------------------

def _auth_path(uid: str) -> Path:
    return _users_dir() / uid / "auth.json"

def load_auth(uid: str) -> Optional[Dict[str, Any]]:
    p = _auth_path(uid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def save_auth(uid: str, doc: Dict[str, Any]) -> None:
    p = _auth_path(uid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


# -----------------------------------------------------------------------------
# Password hashing (PBKDF2-SHA256) – ingen eksterne deps
# Format: pbkdf2_sha256$<iters>$<salt_b64>$<hash_b64>
# -----------------------------------------------------------------------------

_PBKDF2_ITERS = int(os.getenv("CG_PBKDF2_ITERS", "200000"))

def _pad_b64(s: str) -> str:
    return s + "=" * ((4 - (len(s) % 4)) % 4)

def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ITERS,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(dk).decode("ascii").rstrip("="),
    )

def verify_password(password: str, stored: str) -> bool:
    try:
        kind, iters_s, salt_b64, hash_b64 = stored.split("$", 3)
        if kind != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = base64.urlsafe_b64decode(_pad_b64(salt_b64))
        expected = base64.urlsafe_b64decode(_pad_b64(hash_b64))
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Signed session cookie (HMAC) – cg_auth
# Cookie value: base64url(payload_json).base64url(sig)
# payload: {"uid": "...", "exp": 1234567890}
# -----------------------------------------------------------------------------

COOKIE_NAME = os.getenv("CG_AUTH_COOKIE", "cg_auth")

def _auth_secret() -> bytes:
    sec = os.getenv("CG_AUTH_SECRET", "").strip()
    if not sec:
        # dev fallback; sett i .env for stabilitet
        sec = "dev-insecure-secret-change-me"
    return sec.encode("utf-8")

def sign_session(uid: str, ttl_seconds: int) -> str:
    exp = int(time.time()) + int(ttl_seconds)
    payload = {"uid": uid, "exp": exp}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(_auth_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_b64}.{sig_b64}"

def verify_session(value: str) -> Optional[Dict[str, Any]]:
    try:
        if not value or "." not in value:
            return None
        payload_b64, sig_b64 = value.split(".", 1)
        sig = base64.urlsafe_b64decode(_pad_b64(sig_b64))
        expected = hmac.new(_auth_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        raw = base64.urlsafe_b64decode(_pad_b64(payload_b64))
        payload = json.loads(raw.decode("utf-8"))
        exp = int(payload.get("exp") or 0)
        if exp <= int(time.time()):
            return None
        uid = payload.get("uid")
        if not uid or not isinstance(uid, str):
            return None
        return payload
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Public helpers used by routes/middleware
# -----------------------------------------------------------------------------

def ensure_uid(req: Request, resp: Optional[Response] = None) -> str:
    return _get_or_set_uid(req, resp)

def signup_for_uid(uid: str, email: str, password: str) -> Dict[str, Any]:
    existing = load_auth(uid)
    if existing and existing.get("password_hash"):
        raise ValueError("User already has local auth.")
    doc = {
        "uid": uid,
        "email": (email or "").strip().lower(),
        "password_hash": hash_password(password),
        "created_at": int(time.time()),
    }
    save_auth(uid, doc)
    return {"uid": uid, "email": doc["email"]}

def login_for_uid(uid: str, email: str, password: str) -> Dict[str, Any]:
    doc = load_auth(uid)
    if not doc:
        raise ValueError("No local user for this uid. Signup first.")
    if (doc.get("email") or "").strip().lower() != (email or "").strip().lower():
        raise ValueError("Email mismatch for this uid.")
    if not verify_password(password, doc.get("password_hash") or ""):
        raise ValueError("Invalid credentials.")
    return {"uid": uid, "email": doc.get("email")}

def me_from_request(req: Request) -> Optional[Dict[str, Any]]:
    uid = req.cookies.get("cg_uid")
    if not uid:
        return None
    doc = load_auth(uid)
    if not doc:
        return None
    return {"uid": uid, "email": doc.get("email")}
