# Sprint 1 – Auth & Security Documentation

## Task 1.1 – Auth Implementation

- **Auth-strategi**: Session-based authentication med HttpOnly cookie (`cg_auth`)
- **Password hashing**: PBKDF2-SHA256
- **User ID**: `cg_uid` (konsistent mellom local auth og Strava)
- **Storage**: `state/users/<uid>/auth.json`
- **Endpoints**:
  - `/api/auth/signup`
  - `/api/auth/login`
  - `/api/auth/logout`
  - `/api/auth/me`

---

## Task 1.2 – API Security

- **Auth pattern**: `Depends(require_auth)` på alle user-beskyttede endepunkter
- **Ownership SSOT**: `sessions_index.json` per user
- **HTTP semantics**:
  - `401` – ikke autentisert
  - `404` – ressurs finnes ikke eller eies ikke av user
  - `410` – deaktiverte/debug-endepunkter
- **Debug endpoints**: Alle deaktivert (`410 Gone`)

### Protected Endpoints

- `/api/auth/*` (login/logout/me)
- `/api/profile/*` (get/save)
- `/api/sessions/*` (list/detail/analyze)
- `/api/strava/*` (auth/import)

### Owner Protection Pattern

```python
# Load user's index (SSOT)
index = load_user_sessions_index(user_id)

# Check ownership
if session_id not in index:
    return 404  # Not found (do not reveal existence)

# Proceed with operation
Data Structure (Oversikt)
text
Kopier kode
state/
  users/
    <uid>/
      auth.json
      profile.json
      strava_tokens.json
      sessions_index.json

logs/
  results/
    result_<sid>.json
Known Limitations (Identified in Task 1.2)
Filbasert state fungerer for <100 brukere

Concurrent writes ikke håndtert (single-process assumption)

Migrering til database anbefales før public launch

Testing Evidence
Multi-user isolation verifisert via PowerShell

Cross-user access blokkert (404)

Debug endpoints deaktivert (410)

Task 1.3 – Data Structure & GDPR Readiness
Data Structure (Filbasert)
text
Kopier kode
state/
  users/
    <uid>/
      auth.json            # Password hash, session metadata
      profile.json         # FTP, weight, name, Strava device
      strava_tokens.json   # OAuth access/refresh tokens
      sessions_index.json  # SSOT for owned sessions (list of session IDs)

logs/
  results/
    result_<sid>.json      # Analysis results (referenced via sessions_index)

_debug/
  result_<sid>.json        # Debug results (same SSOT pattern)
User Data Ownership (SSOT Pattern)
Direct ownership
Alle filer under state/users/<uid>/ eies eksklusivt av brukeren

Indirect ownership
result_<sid>.json eies indirekte via sessions_index.json

Single Source of Truth (SSOT)
sessions_index.json er autoritativ eierliste for alle sessions

No shared state
Hver bruker har isolert state-katalog

Fail-closed design
Slettede brukere kan ikke gjenopprettes av read-operasjoner

GDPR Deletion Pattern
Verifisert cascading delete:

Slett state/users/<uid>/ (hele katalogen)

Sessions referert i sessions_index.json blir utilgjengelige

Read-operasjoner returnerer tomme svar (200 []), ikke feil

Ingen auto-opprettelse av mapper ved read/list

Testing evidence:

bash
Kopier kode
# Etter sletting av state/users/test_delete_a39b/
GET /api/sessions/list → 200 []
state/users/test_delete_a39b/ eksisterer ikke etter API-kall
Identified Technical Debt
Item	Severity	Impact	Resolution
_email_index.json (global)	🟡 Moderate	Må ryddes ved GDPR delete	Task 3.4
Filbasert state (no locking)	🟡 Moderate	Concurrent writes ikke trygt	DB-migrasjon (post-launch)
logs/results/ flat struktur	🟢 Low	Kun ytelse/skala	DB-migrasjon (post-launch)

Known Limitations
Filbasert state er egnet for <100 brukere

Concurrent writes er ikke håndtert (single-process assumption)

_email_index.json må håndteres separat ved GDPR deletion

Migrering til database anbefales før public launch

Data Isolation Verification
✅ User A kan ikke aksessere User B sine sessions (404)

✅ User A kan ikke aksessere User B sin profile

✅ Slettede brukere forblir slettet (fail-closed)

✅ SSOT-pattern forhindrer cross-user data leakage

markdown
Kopier kode

---

### Kort vurdering
Dette dokumentet er nå:

- 📘 **Lesbart for andre utviklere**
- 🔍 **Revisjons- og GDPR-klart**
- 🧩 **Konsistent med Task 1.1–1.3**
- 🚀 Klart som grunnlag for **Task 1.4** og **Task 3**

Si ifra hvis du vil at vi:
- forkorter teksten ytterligere
- tilpasser språket til ekstern revisjon
- eller går rett videre til neste task