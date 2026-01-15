

markdownCopy# Sprint 1 - Auth & Security Documentation

## Task 1.1 - Auth Implementation
- **Auth-strategi**: Session-based, HttpOnly cookie (cg_auth)
- **Password hashing**: PBKDF2-SHA256
- **User ID**: Gjenbruker cg_uid (konsistent med Strava)
- **Storage**: state/users/<uid>/auth.json
- **Endpoints**: /api/auth/signup, /login, /logout, /me

## Task 1.2 - API Security
- **Auth pattern**: Depends(require_auth) på alle user endpoints
- **SSOT**: sessions_index.json per user for ownership
- **HTTP semantics**: 401 (unauth), 404 (not owned), 410 (deprecated)
- **Debug endpoints**: Alle deaktivert (410)

### Protected Endpoints
- /api/auth/* (login/logout/me)
- /api/profile/* (get/save)
- /api/sessions/* (list/detail/analyze)
- /api/strava/* (import)

### Owner Protection Pattern
```python
# Load user's index
index = load_user_sessions_index(user_id)

# Check ownership
if session_id not in index:
    return 404  # Not found (don't reveal existence)

# Proceed with operation
Data Structure (Filbasert)
Copystate/
  users/
    <uid>/
      auth.json           # Password hash, metadata
      sessions_index.json # List of owned sessions (SSOT)
      profile.json        # User profile (FTP, weight, etc)
      strava_tokens.json  # OAuth tokens
logs/
  results/
    result_*.json        # Analysis results (referenced by sessions_index)
Known Limitations (for later)

Filbasert state fungerer for <100 brukere
Concurrent writes ikke håndtert (single-process assumption)
Migrering til database anbefales før public launch

Testing Evidence

Multi-user isolation verifisert via PowerShell
Cross-user access blocked (404)
Debug endpoints deactivated (410)

