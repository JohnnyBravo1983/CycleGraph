Sprint 1 – Auth & Security Documentation (Revidert og formatert)

Task 1.1 - Auth Implementation
Implementation

Auth-strategi: Session-based authentication med HttpOnly cookie (cg_auth)
Password hashing: PBKDF2-SHA256
User ID: cg_uid (konsistent mellom local auth og Strava)
Storage: state/users/<uid>/auth.json
Endpoints:

POST /api/auth/signup
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me



Technical

Session cookie (cg_auth) settes som HttpOnly (XSS-beskyttelse)
Backend setter request.state.user_id via middleware
Auth-data lagres idiomatisk per bruker i state/users/<uid>/auth.json

Verified scenarios

✅ Gyldig session → /api/auth/me returnerer user_id
✅ Manglende/ugyldig session → 401 Unauthorized
✅ Password hashing fungerer korrekt (PBKDF2-SHA256)


Task 1.2 - API Security
Implementation

Auth pattern: Depends(require_auth) på alle user-beskyttede endepunkter
Ownership SSOT: sessions_index.json per user
HTTP semantics:

401 – Ikke autentisert
404 – Ressurs finnes ikke eller eies ikke av user (forhindrer information disclosure)
410 – Deaktiverte/debug-endepunkter


Debug endpoints: Alle deaktivert (410 Gone)

Protected Endpoints

/api/auth/* (login/logout/me)
/api/profile/* (get/save)
/api/sessions/* (list/detail/analyze)
/api/strava/* (auth/import)

Owner Protection Pattern
pythonCopy# Load user's index (SSOT)
index = load_user_sessions_index(user_id)

# Check ownership
if session_id not in index:
    return 404  # Not found (do not reveal existence)

# Proceed with operation
Technical

Middleware setter request.state.user_id for alle autentiserte requests
SSOT-pattern sikrer at data kun er tilgjengelig via brukerens index
Fail-closed: Ingen auto-mkdir på read operations

Verified scenarios

✅ User A kan ikke access User B's sessions (404)
✅ User A kan ikke access User B's profile
✅ Uautentiserte requests → 401
✅ Debug endpoints → 410


Task 1.3 - Data Structure & GDPR Readiness
Data Structure (Filbasert)
Copystate/
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
      result_<sid>.json    # Debug results (same SSOT pattern)
User Data Ownership (SSOT Pattern)

Direct ownership: Alle filer under state/users/<uid>/ eies eksklusivt av brukeren
Indirect ownership: result_<sid>.json eies indirekte via sessions_index.json
Single Source of Truth: sessions_index.json er autoritativ eierliste for alle sessions
No shared state: Hver bruker har isolert state-katalog
Fail-closed design: Slettede brukere kan ikke gjenopprettes av read-operasjoner

GDPR Deletion Pattern
Verifisert cascading delete:

Slett state/users/<uid>/ (hele katalogen)
Sessions referert i sessions_index.json blir utilgjengelige
Read-operasjoner returnerer tomme svar (200 []), ikke feil
Ingen auto-opprettelse av mapper ved read/list

Testing evidence:
bashCopy# Etter sletting av state/users/test_delete_a39b/
GET /api/sessions/list → 200 []
state/users/test_delete_a39b/ eksisterer ikke etter API-kall
Identified Technical Debt
ItemSeverityImpactResolution_email_index.json (global)🟡 MODERATEMå ryddes ved GDPR deleteTask 3.4Filbasert state (no locking)🟡 MODERATEConcurrent writes ikke trygtDB-migrasjon (post-launch)logs/results/ flat struktur🟢 LOWKun ytelse/skalaDB-migrasjon (post-launch)
Known Limitations

Filbasert state er egnet for <100 brukere
Concurrent writes er ikke håndtert (single-process assumption)
_email_index.json må håndteres separat ved GDPR deletion
Migrering til database anbefales før public launch

Verified scenarios

✅ User A kan ikke aksessere User B sine sessions (404)
✅ User A kan ikke aksessere User B sin profile
✅ Slettede brukere forblir slettet (fail-closed)
✅ SSOT-pattern forhindrer cross-user data leakage


Task 1.4 - Leaderboard Data Foundation
Implementation
Formål: Verifisere at eksisterende lagrede data er egnet for fremtidige leaderboards og aggregeringer. Utført som read-only audit uten endringer i ingest, backend eller frontend.
Technical

sessions_index.json fungerer som SSOT for session-eierskap per bruker
Resultatdata (result_<ride_id>.json) er strukturelt og typemessig konsistente
start_time er stabilt tidsfelt (ISO-8601 UTC) for tidsfiltrering og gruppering
precision_watt_avg er verifisert som aggregerbar metric

Leaderboard-Ready Data

✅ start_time (dato-filtrering, år-for-år)
✅ precision_watt_avg (power-baserte leaderboards)
✅ weather_applied, weather_source (context)
✅ profile_version (profil-tracking)

Identified Limitations

⚠️ Enkelte entries i sessions_index.json mangler tilhørende resultatfil (placeholders / mistenkelig ride_id)
⚠️ Store arrays (watts, v_rel, wind_rel) er ikke direkte leaderboard-egnet
⚠️ tss ga 0 ved aggregering (enten ikke brukt eller ikke lagret)
❌ distance, elevation, duration ikke observert i resultatfiler

Verified scenarios

✅ Top-10 etter precision_watt_avg fungerer korrekt
✅ År-for-år aggregering fungerer
✅ Datatyper er konsistente (ingen string/int/float-mix)
⚠️ TSS-baserte leaderboards ikke mulig (data ikke pålitelig)

Notes for Future Sprints

sessions_index.json er kontrakt og eneste autoritative kilde for session-eierskap
Fremtidig kode må tåle rides uten tilhørende result_<ride_id>.json
Arrays (watts, v_rel, wind_rel) må aggregeres eksplisitt før leaderboard-bruk
Løsningen forutsetter single-process filbasert state frem til eventuell database-migrasjon

Detaljert audit: docs/sprint1/task_1_4_leaderboard_data_foundation.md

Task 1.5 - Frontend Login
Implementation

Login flow: POST /api/auth/login → GET /api/auth/me → redirect
Session: HttpOnly cookie (cg_auth), persistent across refresh
Error handling: 401 (wrong password), network errors
UX: Disabled button, "Logger inn..." feedback, spam prevention

Technical

credentials: "include" brukes konsekvent for cookie-håndtering
Session-verifisering via GET /api/auth/me etter login
Backend-logger verifisert (uid logges korrekt)

Verified scenarios

✅ Valid login → redirect to dashboard
✅ Invalid password → error message
✅ Session persists on refresh
✅ Protected endpoints accessible after login

Known limitations

No "Remember me" (optional, not needed for early onboarding)
Empty field validation relies on HTML5 required attribute


Task 1.6 - Frontend Signup
Implementation

Signup flow: POST /api/auth/signup → GET /api/auth/me → redirect to /onboarding
Validation: Min 8 chars password, required fields, consent checkbox
Error handling: 409 (duplicate email), 400/401 (invalid), network errors
Auto-login: Verified via cgApi.authMe()
UX: Loading state, disabled submit button

Technical

Introduced ApiError in cgApi for status code access
Introduced cgApi.authMe() for robust session verification
Typecheck + build verified

Verified scenarios

✅ Valid signup → auto-login → redirect to /onboarding
✅ Duplicate email → 409 → "E-post er allerede i bruk"
✅ Invalid input → 400/401 → "Ugyldige felt"
✅ Network error → user-friendly message


Task 1.7 - Route Guards
Implementation

AuthGate: Global provider wrapping entire app in main.tsx
Auth check: GET /api/auth/me (SSOT)
Onboarding check: GET /api/profile/get (non-empty = onboarded)
Guard components: RequireAuth, RequireOnboarding

Routes
Public: /, /login, /signup, /how-it-works
Protected: /dashboard, /rides, /trends, /goals, /profile, /session/:id, /calibration
Guard states

checking → Loading screen
guest → Redirect to /login
authed + !onboarded → Redirect to /onboarding (except on /onboarding itself)
authed + onboarded → Access granted

Technical

RequireOnboarding allowUnonboarded on /onboarding prevents redirect loop
Onboarding status based on actual profile data (not localStorage flag)
Session-based auth (token expiry handled by backend)

Testing

Playwright smoke tests: route-guards.smoke.mjs
Verified: [T1] guest redirect, [T2] new user redirect, [T3] refresh stable, [T4] onboarded access

Verified scenarios

✅ Guest → protected route → redirect to /login
✅ Authed + not onboarded → redirect to /onboarding
✅ Refresh preserves auth/onboarding state (no re-login needed)
✅ No redirect loops (allowUnonboarded pattern)


## Task 1.8 - Multi-User Auth Validation

### Implementation
**Formål:** Sluttvalidering av Sprint 1 – bevise at auth, guards og data isolation fungerer korrekt for multiple brukere.

### Test Setup
- **Miljø**: Frontend (localhost:5173), Backend (127.0.0.1:5175)
- **Testbrukere**: 5 unike brukere (U1-U5) opprettet via API
- **Testing**: PowerShell (API-nivå), normal browser, incognito

### Test Matrix & Results

#### A) Basic Auth (per bruker)
- ✅ Signup → redirect /onboarding
- ✅ Refresh på /onboarding (stable)
- ✅ Logout → forsøk /dashboard → redirect /login
- ✅ Login → korrekt redirect (onboarding hvis ikke onboardet)
- ✅ Logout → cookie slettes (Set-Cookie Max-Age=0)

#### B) Guard Correctness
- ✅ Guest → /rides direkte → redirect /login
- ✅ Authed, ikke onboardet → /dashboard → redirect /onboarding
- ✅ Authed + onboardet → /dashboard → OK
- ✅ allowUnonboarded på /onboarding → ingen redirect-loop

#### C) Multi-User Isolation (KRITISK)
- ✅ /api/sessions/list per bruker → kun egne data / tom liste
- ✅ U2 forsøker å åpne U1 sin session_id → HTTP 404
- ✅ Cross-access gir ALDRI 500

**Kritisk funn:** Cross-user tilgang blokkeres med 404 (Not Found), ikke 403, og uten å lekke informasjon. Dette bekrefter full datasilo-isolasjon (SSOT-pattern fra Task 1.2-1.3).

#### D) Session & Persistence
- ✅ Login → F5 refresh → fortsatt authed
- ✅ Lukk tab → reopen → fortsatt authed (cookie lever)
- ✅ Incognito → alltid guest
- ✅ Ingen auth-flapping observert

#### E) Negative / Edge Cases
- ✅ Ugyldig passord → HTTP 401 + korrekt feilmelding
- ✅ Duplikat signup → HTTP 409
- ✅ /api/auth/me uten cookie → HTTP 401
- ✅ Protected endpoints uten auth → HTTP 401
- ✅ Ugyldig cross-session → HTTP 404 (ikke 500)

### Verified Showstoppers (None Found)
| Potensiell showstopper | Status |
|------------------------|--------|
| Cross-user data leakage | ❌ Ikke funnet |
| Redirect-loops | ❌ Ikke funnet |
| 500-feil i normal flyt | ❌ Ikke funnet |
| Auth flapping | ❌ Ikke funnet |

### Out of Scope (Sprint 2)
- Strava OAuth-integrasjon for nye brukere (eksplisitt Sprint 2)
- Testbrukere kan ikke fullføre Strava OAuth (fiktive brukere)
- "Connect Strava" kan sende bruker tilbake til /login (forventet for fiktive brukere)

### Conclusion
- ✅ Multi-user auth er korrekt implementert
- ✅ Datasilo-isolasjon er bevist
- ✅ Guards fungerer i hele brukerreisen
- ✅ Edge cases håndteres korrekt
- ✅ Ingen showstoppers funnet
- ✅ Sprint 1 kan lukkes formelt
- ▶️ Sprint 2 kan startes uten datarisiko

Sprint 1 – FULLSTENDIG KONKLUSJON
✅ Alle tasks fullført
TaskStatusQualityTask 1.1: Auth Implementation✅⭐⭐⭐⭐⭐Task 1.2: API Security✅⭐⭐⭐⭐⭐Task 1.3: Data Structure & GDPR✅⭐⭐⭐⭐⭐Task 1.4: Leaderboard Data Foundation✅⭐⭐⭐⭐⭐Task 1.5: Frontend Login✅⭐⭐⭐⭐⭐Task 1.6: Frontend Signup✅⭐⭐⭐⭐⭐Task 1.7: Route Guards✅⭐⭐⭐⭐⭐Task 1.8: Multi-User Validation✅⭐⭐⭐⭐⭐
Sprint 1 Total: 8/8 tasks fullført med høy kvalitet ✅

Hva er oppnådd i Sprint 1
✅ Autentisering

Session-based auth med HttpOnly cookie
Password hashing (PBKDF2-SHA256)
Login/signup/logout fungerer

✅ Sikkerhet

Alle API-endepunkter beskyttet
SSOT-pattern for data ownership
Datasilo-isolasjon bevist (User A kan ikke se User B's data)
HTTP-semantikk korrekt (401, 404, 410 – aldri 500)

✅ Datastruktur

Filbasert state dokumentert
GDPR deletion-pattern verifisert
Leaderboard-datafundament kartlagt

✅ Frontend

Login-skjerm koblet til backend
Signup-skjerm med auto-login
Route guards (AuthGate)
Onboarding-redirect fungerer

✅ Testing

Multi-user isolation verifisert
Playwright smoke tests
Comprehensive testmatrise
Ingen showstoppers funnet
FaseUkerSluttdato (ca.)Hva er klart✅ Sprint 1-1Ferdig nåAuth, data, frontend login/signup
Sprint 2+1Uke 2Onboarding fungerer
Sprint 3+1Uke 3GDPR-compliant
Sprint 4+1Uke 4Dashboard polert
Sprint 5+1Uke 5Early onboarding live 🎉
Sprint 6+2-3Uke 8Leaderboards live
print 7+2-3Uke 11Trends live
Sprint 8+2Uke 13Goals live
Sprint 9+1-2Uke 15Public launch 1. april 🚀


Sprint 1 er klar for produksjon 🚀
Systemet kan nå:

✅ Nye brukere kan sign up
✅ Brukere kan logge inn
✅ Session persisterer ved refresh
✅ Protected routes er beskyttet
✅ Data er isolert per bruker
✅ GDPR deletion er mulig

Systemet kan IKKE enda:

❌ Onboarding-flyt for nye brukere (Sprint 2)
❌ Strava OAuth for nye brukere (Sprint 2)
❌ Automatisk import av rides (Sprint 2)
❌ GDPR UI (Sprint 3)
❌ Production-ready dashboard (Sprint 4)


## Sprint 2 – Onboarding & Strava Integration

---

## Task 2.1 - Onboarding Flow Verification

### Implementation
**Formål:** Verifisere at onboarding fungerer for nye brukere (ikke bare eier), og at ingen hardkodet owner-logikk eksisterer.

### Technical
- Onboarding-flyt bruker `req.user.id` fra auth middleware (Task 1.1)
- Profile lagres i `state/users/<uid>/profile.json`
- `onboarded: true` settes via `POST /api/profile/save` med `markOnboarded: true`
- Hard reload etter onboarding for å refresh `AuthGate` state
- Redirect til `/dashboard` ved fullført onboarding

### Onboarding Flow
1. User signs up → auto-login (Task 1.6)
2. Redirect to `/onboarding` (Task 1.7 guard)
3. Fill profile form:
   - Rider weight (kg)
   - Bike type (road/gravel/mtb)
   - Bike weight (kg)
   - Tire width (mm)
   - Tire quality (performance/standard/comfort)
   - Optional: bike name
4. Submit → `POST /api/profile/save` with `markOnboarded: true`
5. Backend calculates derived values (e.g., `crank_efficiency`)
6. Hard reload → redirect to `/dashboard`

### Data Structure
**Profile stored at:** `state/users/<uid>/profile.json`

**Example:**
```json
{
  "rider_weight_kg": 75,
  "bike_type": "road",
  "bike_weight_kg": 8.0,
  "tire_width_mm": 28,
  "tire_quality": "performance",
  "device": "strava",
  "bike_name": "My Bike",
  "crank_efficiency": 96.0,
  "onboarded": true,
  "profile_version": "v1-766f4722-20260118",
  "version_at": "20260118T00:00:00Z",
  "version_hash": "766f4722"
}
Code Audit

Searched for hardcoded cg_uid, owner, default, admin in backend
Result: No hardcoded owner-logic found
All onboarding writes use req.user.id from Depends(require_auth)
Profile save endpoint: PUT /api/profile/save (protected, Task 1.2)

Testing Evidence
Test setup:

Environment: Incognito browser (clean state)
Test user: test_onboarding_2026_01_18@example.com
UID generated: u_E4vABnNHFk2JJ48EkbUjJA

Test flow:

Signup via /signup → auto-login
Redirect to /onboarding
Fill profile form with test data
Submit → redirect to /dashboard
Verify: state/users/u_E4vABnNHFk2JJ48EkbUjJA/profile.json created
Verify: All fields match input data
Verify: onboarded: true set correctly

Verified Scenarios

✅ New user (not owner) can complete onboarding
✅ Profile data stored with correct user_id
✅ onboarded: true persisted correctly
✅ No hardcoded owner-logic found in code audit
✅ File path uses correct UID: state/users/<uid>/profile.json
✅ Derived values calculated correctly (e.g., crank_efficiency)
✅ AuthGate respects onboarded status (Task 1.7 integration)

Out of Scope (Later Tasks)

Strava OAuth redirect verification (Task 2.2)
Strava token storage verification (Task 2.2)
Rides import (Task 2.3)
Automatic ride sync after onboarding (Task 2.4)

Known Behavior

Hard reload required after onboarding to refresh AuthGate state
device: "strava" is default (manual device selection not implemented)
Profile version is auto-generated (hash-based versioning)

Conclusion
Onboarding flow is fully generalized and user-agnostic. No hardcoded owner-logic exists. 
New users can complete onboarding independently and are correctly tracked in the system.


Task 2.2 – Strava OAuth Integration Verification
Implementation

Formål: Verifisere at Strava OAuth fungerer korrekt for innloggede brukere, at tokens lagres per bruker (ikke globalt), og at ingen legacy- eller hardkodet cg_uid brukes som autoritativ identitet.
Technical
Strava OAuth-endepunkter er beskyttet med require_auth
Autentisert brukeridentitet hentes fra cg_auth (SSOT)
OAuth state er:
Signert
Bundet til uid
Tidsbegrenset (TTL)
Tokens lagres per bruker i:
state/users/<uid>/strava_tokens.json
cg_uid settes kun som legacy helper cookie, aldri brukt som identitet
Redirect URI beregnes dynamisk via _effective_redirect_uri(req) for å unngå localhost vs 127.0.0.1 cookie-tap
Status sjekkes via GET /api/auth/strava/status
Strava OAuth Flow
User er innlogget (cg_auth cookie valid)
User klikker Connect to Strava

Frontend kaller:
GET /api/auth/strava/login?next=http://localhost:5173/onboarding

Backend:
Verifiserer auth (require_auth)
Genererer signert OAuth state (uid + TTL)
Redirecter til Strava authorize endpoint
Strava redirecter tilbake til:
/api/auth/strava/callback?code=...&state=...

Backend:
Verifiserer state (signatur + TTL + uid-match)
Exchange code → access/refresh tokens
Lagrer tokens per bruker
Redirecter tilbake til next (onboarding)

Data Structure
Tokens stored at:
state/users/<uid>/strava_tokens.json
Example:

{
  "access_token": "…",
  "refresh_token": "…",
  "expires_at": 1768853046,
  "token_type": "Bearer",
  "athlete": {
    "id": 55313385,
    "firstname": "Johnny",
    "lastname": "Stroemoe",
    "premium": true
  },
  "received_at": 1768831461
}

Status Endpoint
Endpoint:
GET /api/auth/strava/status (protected)
Behavior:
Krever gyldig cg_auth
Leser tokens fra state/users/<uid>/strava_tokens.json
Returnerer tilkoblingsstatus
Example response (connected):

{
  "ok": true,
  "uid": "u_ZYqxGIOatRFvf4i5s8oGTQ",
  "has_tokens": true,
  "expires_at": 1768853046,
  "expires_in_sec": 21258,
  "redirect_uri_effective": "http://localhost:5175/api/auth/strava/callback"
}

Code Audit
Søkt etter:
cg_uid brukt som identitet
hardkodet owner / admin / default logic
global token-lagring
Resultat:
Alle protected Strava-endepunkter bruker require_auth
uid kommer alltid fra cg_auth
Tokens lagres kun under state/users/<uid>/
cg_uid brukes kun som legacy helper cookie (ikke autoritativ)

Testing Evidence
Test setup:
Environment: Local dev
Frontend: localhost:5173
Backend: 127.0.0.1:5175

Test user UID: u_ZYqxGIOatRFvf4i5s8oGTQ
Real Strava account (non-mock)

Test flow:
Logget inn bruker (/api/auth/me → 200 OK)
Trigger OAuth via /api/auth/strava/login
Fullfør Strava consent
Callback mottatt og validert
Verifiser:
state/users/<uid>/strava_tokens.json eksisterer
Tokens inneholder athlete-data
Kall /api/auth/strava/status
has_tokens: true
Verified Scenarios

✅ OAuth kan kun startes av autentisert bruker
✅ state er bundet til riktig uid (fail-closed)
✅ Tokens lagres per bruker (ikke globalt)
✅ Status-endepunkt reflekterer korrekt tilkoblingsstatus
✅ Ingen avhengighet til legacy cg_uid for identitet
✅ Redirect tilbake til korrekt frontend-URL etter OAuth

Out of Scope (Later Tasks)
Ride import (Task 2.3)
Automatic ride sync (Task 2.4)
UI-polish for “Connected” status (indikatortekst)

Known Behavior
cg_uid cookie settes fortsatt for kompatibilitet/debug
UI “Connected”-indikator oppdateres først etter status-refetch
Redirect host kan variere (localhost / 127.0.0.1) i dev, men håndteres av _effective_redirect_uri
Conclusion
Strava OAuth-integrasjonen er korrekt implementert, brukerspesifikk og sikker.
Tokens bindes entydig til autentisert bruker via signert state og lagres isolert per UID.
Task 2.2 er fullført og godkjent med ekte Strava OAuth-flow.

Task 2.3 – Dokumentasjon (copy-paste klar)
Legg til i docs/sprint-documentation.md (etter Task 2.2):

markdownCopy## Task 2.3 - Rides Import & Precision Watt SSOT

### Implementation
**Formål:** Verifisere at Strava rides importeres korrekt til riktig bruker, og etablere SSOT for watt-visning i UI.

### Task 2.3a - Import Functionality

**Technical:**
- `POST /api/strava/import/{rid}` imports ride from Strava API
- Session file written to `logs/actual10/latest/session_{rid}.json`
- SSOT updated: `state/users/<uid>/sessions_index.json` (rider ownership)
- Auth/ownership verified via `require_auth` + SSOT check

**Verified Scenarios:**
- ✅ Import works end-to-end (200 OK)
- ✅ Session file created in correct location
- ✅ SSOT updated with new ride ID
- ✅ Auth enforced (401 without cookie, 200 with correct user)

---

### Task 2.3b - Fix Analysepipeline Vekt-bug & Precision Watt SSOT

**Problem Identified:**

**Issue 1: Input Source Bug**
- `_debug/session_<RID>.json` was used as input source
- Contained incorrect profile/weight data
- Result: Catastrophically wrong watt calculations (158W instead of 230W)

**Issue 2: SSOT Inconsistency**
- Multiple `precision_watt*` variants in result files (wheel/crank/pedal + top-level)
- UI used `precision_watt_avg` (top-level), but nested `metrics.*` had different values
- Caused mismatch between dashboard list view and ride detail view

**Root Cause:**
_debug/ (legacy): 111kg weight → precision_watt_signed: 230W ✅
logs/results/ (new): 83kg weight → precision_watt_signed: 158W ❌ (37% error)
Copy
Analysepipeline used hardcoded default weight (83kg) instead of user profile (111.9kg).

---

**Fix 1: Input Source**
- Gate debug inputs behind `CG_ALLOW_DEBUG_INPUTS` env variable
- Deleted legacy `_debug/session_*.json` and `logs/results/result_*.json`
- Re-imported all test rides with correct profile data (111.9kg total weight)

**Fix 2: Canonical Watt Metric (SSOT)**

**Decision:** `metrics.precision_watt_pedal` is canonical UI metric

**Why:**
- Rider-facing (accounts for pedal efficiency)
- Most sanity-tested metric (team invested significant effort previously)
- Matches expected power values (~230-250W for test rides)

**Implementation** (in `server/routes/sessions.py`):

```python
# 1) Determine UI watt (prioritized fallback):
ui_avg = metrics.precision_watt_pedal
      OR metrics.total_watt_pedal
      OR wheel/eff fallback

# 2) Enforce top-level SSOT for frontend:
resp["precision_watt_avg"] = ui_avg

# 3) Sync nested metrics (defensive – prevents legacy mismatch):
m["precision_watt"] = ui_avg
m["total_watt"] = ui_avg
m["precision_watt_avg"] = ui_avg

# 4) Preserve physics truth (not overwritten):
model_watt_wheel
Defensive Sync:

Top-level and nested metrics always consistent
Retroactively fixes legacy files with inconsistent data
UI cannot get mismatch between list/view
Physics truth (model_watt_wheel) preserved for debugging


Testing Evidence
Profile Weight Verification:

Rider weight: ~103.9 kg
Total weight (rider + bike): 111.9 kg
All new analyses use correct weight from user profile ✅

Test Rides (5 rides verified):

16712572748
16396031026
15890366129
16262232459
15635293008

Verification per ride:

✅ metrics.precision_watt_pedal == resp.precision_watt_avg (SSOT enforced)
✅ UI shows consistent watt in list + view (no mismatch)
✅ Correct profile weight used (111.9 kg total, not 83 kg)
✅ Sanity-tested watt values (~230-250W range)


Effect
UI:

One SSOT for watt (precision_watt_pedal) across entire app
Consistent display in dashboard list, ride detail view
No mismatch between different UI components

Physics/Debug:

No regression: model_watt_wheel truth still available separately
Debug data preserved for analysis and verification

Legacy Data:

Old files with inconsistent metrics defensively synced at response-time
No manual migration needed


Known Limitations

SSOT enforcement happens at response-time (not stored in JSON files)
Legacy _debug/ files deleted (clean slate approach)
Requires CG_ALLOW_DEBUG_INPUTS=false in production (debug inputs disabled)

Out of Scope (Later)

Automatic re-analysis on profile change (Sprint 5)
Historical data migration for old rides (Sprint 6-7 if needed)
A/B testing of pedal vs. signed watt (post-launch)

Conclusion
Precision watt is now consistent, sanity-tested, and has clear SSOT (metrics.precision_watt_pedal). UI displays correct, rider-facing power values across all views. Vekt-bug fixed (correct profile weight used). No regression in debug/physics data.




---
Gi meg først powershell comands på alt du ikke vet som du trenger å vite for å løse tasken. Deretter setter du treffsikre patcher
 hvem hva og vhor så går du gjennom meg etter hver patch eller task og validerer at den er gjennomført slik den skal.
åp Pass på å ikke starte på ptacher før du har tenkt grundig gjennom å er sikker på beste patch.Pass også på å spisse søkene 
der det er mulig så vi ikke får så vanvittig mye treff. MEn det må ikke gå på bekostning av 
kvalitet.  
 Du har regien i denne arhbeidschatten

