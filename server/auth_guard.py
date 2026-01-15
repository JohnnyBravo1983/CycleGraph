# server/auth_guard.py
from __future__ import annotations

from fastapi import Request, HTTPException, status

# Public endpoints som alltid skal slippe gjennom (healthcheck + docs + auth)
PUBLIC_PREFIXES = (
    "/status",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
    "/api/auth",
)

def require_auth(request: Request) -> str:
    """
    Auth-guard dependency.
    Returnerer user_id (cg_uid) hvis authenticated, ellers 401.
    """
    path = request.url.path

    # ✅ Always allow public paths (health/docs/auth)
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        # Returner tom streng for å matche returtype str uten å påvirke callers.
        # Callers som faktisk trenger user_id skal uansett være på beskyttede paths.
        return ""

    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return str(user_id)
