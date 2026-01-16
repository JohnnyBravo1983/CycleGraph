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

---

## Task 1.4 – Leaderboard Data Foundation (Summary)

Formål:  
Verifisere at eksisterende lagrede data er egnet for fremtidige leaderboards
og aggregeringer. Tasken er utført som read-only audit uten endringer i ingest,
backend eller frontend.

Status:
- `sessions_index.json` fungerer som Single Source of Truth (SSOT) for
  session-eierskap per bruker
- Resultatdata (`result_<ride_id>.json`) er strukturelt og typemessig konsistente
- `start_time` er stabilt tidsfelt (ISO-8601 UTC) og kan brukes til
  tidsfiltrering og gruppering
- `precision_watt_avg` er verifisert som aggregerbar metric
  (Top-N, år-for-år, trend)

Identifiserte begrensninger (ikke løst her):
- Enkelte entries i `sessions_index.json` mangler tilhørende resultatfil
  (placeholders / mistenkelig ride_id)
- Store arrays (`watts`, `v_rel`, `wind_rel`) er ikke direkte leaderboard-egnet
- `tss` ga 0 ved aggregering (enten ikke brukt eller ikke lagret i resultatene)

Detaljert audit og full metric-inventar er dokumentert i:
`docs/sprint1/task_1_4_leaderboard_data_foundation.md`

---

## Notes for Future Sprints (Important)

- `sessions_index.json` er kontrakt og eneste autoritative kilde for
  session-eierskap
- Fremtidig kode må tåle rides uten tilhørende `result_<ride_id>.json`
- Arrays (`watts`, `v_rel`, `wind_rel`) må aggregeres eksplisitt før
  leaderboard-bruk
- Løsningen forutsetter single-process filbasert state frem til eventuell
  database-migrasjon
Task 1.5 – Frontend Login Integration (Auth)

Formål:
Koble frontend login-skjerm til eksisterende session-baserte auth-endepunkter
i backend. Erstatte mock-login med ekte autentisering og verifisere
session-cookie-basert innlogging fra browser.

Status:
Login-skjerm kaller ekte backend (/api/auth/login)
Session etableres via HttpOnly cookie (cg_auth)
Innlogging verifiseres eksplisitt via /api/auth/me
Bruker navigeres først etter bekreftet session
Implementasjon (Frontend):
Login utføres via:
POST /api/auth/login
credentials: "include" for cookie-basert auth
Etter vellykket login:
GET /api/auth/me brukes som autoritativ verifikasjon
200 OK indikerer gyldig session
Ingen tokens lagres i localStorage eller JS-state
All auth-state styres server-side via cookie
Feilhåndtering:
Feil passord:
Backend returnerer 401 Unauthorized

Frontend viser feilmelding (“invalid credentials”)
Ingen navigasjon eller session-opprettelse

Nettverksfeil:
Exceptions fanges
Bruker får tydelig feiltilstand
Dobbelt-submit forhindres via loading state
UX / Brukerflyt:
Login-knapp deaktiveres under pågående request
Loading state vises under autentisering
Navigasjon skjer først etter bekreftet session
Refresh av siden bevarer innlogging (cookie-basert)

Testing Evidence:
Verifisert via:
Browser (Network-tab + cookies)
Backend-logger (Uvicorn)
Manuell feil-/suksesstest
Testede scenarier:
Feil passord → 401 Unauthorized
Riktig passord → 200 OK + session-cookie
GET /api/auth/me → 200 OK etter login
Refresh side → session persisterer
Beskyttede endepunkter tilgjengelige etter login
Avgrensning (Bevisst ikke inkludert):
Signup-flow (Task 1.6)
Route guards i frontend (Task 1.7)
Token refresh (ikke relevant for session-auth)
OAuth (Strava) login-flow
Design/UX-polish utover nødvendig feedback

Konklusjon:
Task 1.5 bekrefter at frontend er korrekt integrert med backend sin
session-baserte autentiseringsmodell. Løsningen er konsistent med
Task 1.1–1.2, følger HttpOnly cookie-prinsippet og gir et sikkert og
forutsigbart grunnlag for videre onboarding- og signup-arbeid.


---
Gi meg først powershell comands på alt du ikke vet som du trenger å vite for å løse tasken. Deretter setter du treffsikre patcher
 hvem hva og vhor så går du gjennom meg etter hver patch eller task og validerer at den er gjennomført slik den skal.
 Pass på å ikke starte på ptacher før du har tenkt grundig gjennom å er sikker på beste patch. 
 Du har regien i denne arhbeidschatten
