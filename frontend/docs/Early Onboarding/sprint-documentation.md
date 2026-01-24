 CYCLEGRAPH - KOMPLETT DEPLOYMENT & SPRINT DOKUMENTASJON

🎯 PROSJEKTOVERSIKT
CycleGraph er en webapp for syklister som beregner "Precision Watt" basert på Strava-data, vær og fysikkmodellering.
Tech Stack:

Frontend: React + Vite (TypeScript)
Backend: FastAPI (Python)
Deploy: Vercel (frontend) + Fly.io (backend)
Storage: Filbasert state (/app/state/ på Fly volume)


📋 INNHOLDSFORTEGNELSE

Sprint 1 - Auth & Security
Sprint 2 - Onboarding & Strava
Sprint 3 - Data Enrichment (PÅGÅENDE)
Deployment Guide
Troubleshooting
Known Issues & Technical Debt


🔐 SPRINT 1 - AUTH & SECURITY
Task 1.1 - Auth Implementation
Implementation:

Auth-strategi: Session-based authentication med HttpOnly cookie (cg_auth)
Password hashing: PBKDF2-SHA256
User ID: cg_uid (konsistent mellom local auth og Strava)
Storage: state/users/<uid>/auth.json

Endpoints:

POST /api/auth/signup
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me

Technical:

Session cookie (cg_auth) settes som HttpOnly (XSS-beskyttelse)
Backend setter request.state.user_id via middleware
Auth-data lagres idiomatisk per bruker i state/users/<uid>/auth.json

Verified scenarios:

✅ Gyldig session → /api/auth/me returnerer user_id
✅ Manglende/ugyldig session → 401 Unauthorized
✅ Password hashing fungerer korrekt (PBKDF2-SHA256)


Task 1.2 - API Security
Implementation:

Auth pattern: Depends(require_auth) på alle user-beskyttede endepunkter
Ownership SSOT: sessions_index.json per user
HTTP semantics:

401 – Ikke autentisert
404 – Ressurs finnes ikke eller eies ikke av user (forhindrer information disclosure)
410 – Deaktiverte/debug-endepunkter



Protected Endpoints:

/api/auth/* (login/logout/me)
/api/profile/* (get/save)
/api/sessions/* (list/detail/analyze)
/api/strava/* (auth/import)

Owner Protection Pattern:
pythonCopy# Load user's index (SSOT)
index = load_user_sessions_index(user_id)

# Check ownership
if session_id not in index:
    return 404  # Not found (do not reveal existence)
Verified scenarios:

✅ User A kan ikke access User B's sessions (404)
✅ User A kan ikke access User B's profile
✅ Uautentiserte requests → 401
✅ Debug endpoints → 410


Task 1.3 - Data Structure & GDPR Readiness
Data Structure (Filbasert):
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
User Data Ownership (SSOT Pattern):

Direct ownership: Alle filer under state/users/<uid>/ eies eksklusivt av brukeren
Indirect ownership: result_<sid>.json eies indirekte via sessions_index.json
Single Source of Truth: sessions_index.json er autoritativ eierliste for alle sessions
No shared state: Hver bruker har isolert state-katalog
Fail-closed design: Slettede brukere kan ikke gjenopprettes av read-operasjoner

GDPR Deletion Pattern:

Slett state/users/<uid>/ (hele katalogen)
Sessions referert i sessions_index.json blir utilgjengelige
Read-operasjoner returnerer tomme svar (200 []), ikke feil
Ingen auto-opprettelse av mapper ved read/list


Task 1.4-1.8 (Sammendrag)
Task 1.4: Leaderboard Data Foundation - verifiserte at data er aggregerbar
Task 1.5: Frontend Login - implementert login-skjerm
Task 1.6: Frontend Signup - implementert signup med auto-login
Task 1.7: Route Guards - AuthGate og RequireOnboarding guards
Task 1.8: Multi-User Validation - bevist datasilo-isolasjon
Sprint 1 Status: ✅ 8/8 tasks fullført med høy kvalitet

🚀 SPRINT 2 - ONBOARDING & STRAVA INTEGRATION
Task 2.1 - Onboarding Flow
Flow:

User signs up → auto-login
Redirect to /onboarding
Fill profile form (weight, bike type, tire, etc.)
Submit → POST /api/profile/save with markOnboarded: true
Hard reload → redirect to /dashboard

Data stored:
jsonCopy{
  "rider_weight_kg": 75,
  "bike_type": "road",
  "bike_weight_kg": 8.0,
  "tire_width_mm": 28,
  "onboarded": true,
  "profile_version": "v1-766f4722-20260118"
}
Verified: ✅ Ingen hardkodet owner-logic, fungerer for alle brukere

Task 2.2 - Strava OAuth
Flow:

User klikker "Connect to Strava"
Backend redirecter til Strava authorize
Strava redirecter tilbake med code
Backend exchange code → tokens
Tokens lagres i state/users/<uid>/strava_tokens.json

Security:

OAuth state er signert + bundet til uid + tidsbegrenset
Tokens lagres per bruker (ikke globalt)
Status sjekkes via GET /api/auth/strava/status

Verified: ✅ Tokens isolert per bruker, ingen cg_uid-avhengighet

Task 2.3 - Rides Import & Precision Watt SSOT
Import:

POST /api/strava/import/{rid} imports ride from Strava
Session file: logs/actual10/latest/session_{rid}.json
SSOT updated: state/users/<uid>/sessions_index.json

Critical Bug Fixed (Vekt-bug):

Problem: Analysepipeline brukte hardcoded 83kg i stedet for user profile (111.9kg)
Effect: 37% feil i watt-beregninger (158W i stedet for 230W)
Fix: Slettet legacy _debug/ filer, re-importerte med korrekt profil

Precision Watt SSOT:

Canonical metric: metrics.precision_watt_pedal
Enforcement: Top-level precision_watt_avg synkroniseres med precision_watt_pedal
Effect: Konsistent watt-visning i list + detail views

Sprint 2 Status: ✅ Fullført, klar for produksjon

🔧 SPRINT 3 - DATA ENRICHMENT (PÅGÅENDE)
Status: Sprint 3 startet 2026-01-24
Gjennombrudd oppnådd:

✅ /api/sessions/list/all returnerer data (12 rides synlige)
✅ precision_watt_avg vises korrekt (f.eks. 256.07W)
✅ Result-filer funnet i /app/_debug_WithWeather/

Problemer identifisert:

❌ distance_km, start_time, weather_source, profile_label er null
❌ 55 av 67 rides mangler result-filer (12/67 synlige)
❌ Metadata parsing feil i _row_from_doc()


Neste Tasks (Sprint 3):
FASE 1: Fix metadata parsing (2-4 timer)
Problem: Result-filer HAR dataen, men _row_from_doc() henter fra feil JSON-nøkler.
Løsning:
pythonCopydef _row_from_doc(doc: Dict[str, Any], ...) -> Dict[str, Any]:
    metrics = doc.get("metrics", {})
    weather_meta = doc.get("weather_meta", {})
    
    # Hent fra riktige steder:
    precision_watt = metrics.get("precision_watt") or metrics.get("precision_watt_avg")
    distance_km = metrics.get("distance_km") or doc.get("distance_km")
    weather_source = weather_meta.get("provider") or doc.get("weather_source")
    
    return {
        "session_id": doc.get("session_id") or fallback_sid,
        "precision_watt_avg": precision_watt,
        "distance_km": distance_km,
        "weather_source": weather_source,
        ...
    }
FASE 2: Fix manglende result-filer (3-6 timer)
Diagnostiser:
bashCopy# SSH til Fly:
fly ssh console -a cyclegraph-api

# Finn manglende rides:
NEW_UID="u_Dp1h92XJY30w1vE7hmgyw"
cat /app/state/users/$NEW_UID/sessions_index.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for rid in data.get('sessions', []):
    print(rid)
" > /tmp/all_ride_ids.txt

for rid in $(cat /tmp/all_ride_ids.txt); do
  if ! ls /app/_debug_*/result_$rid.json 2>/dev/null | grep -q .; then
    echo "MISSING: $rid"
  fi
done
Re-analyze manglende rides via API eller Python script i container.
FASE 3: UI polish (2-3 timer)

Format dates (toLocaleDateString)
Vis distance + weather i UI
Loading/error states


🚀 DEPLOYMENT GUIDE
🎯 Arkitektur
CopyUser Browser
    ↓
Vercel (www.cyclegraph.app)
    ↓ /api/* → proxy
Fly.io (api.cyclegraph.app)
    ↓
Volume (/app/state/)

📦 Backend Deployment (Fly.io)
Initial Setup (én gang):
bashCopy# 1. Install Fly CLI:
# https://fly.io/docs/hands-on/install-flyctl/

# 2. Login:
fly auth login

# 3. Fra backend-mappen:
cd backend

# 4. Opprett app (om ikke eksisterer):
fly apps create cyclegraph-api --region ams

# 5. Opprett volume (persistent storage):
fly volumes create cg_state --region ams --size 1 -a cyclegraph-api

# 6. Sett secrets (environment variables):
fly secrets set \
  CG_STATE_DIR=/app/state \
  CG_STRAVA_CLIENT_ID=your_client_id \
  CG_STRAVA_CLIENT_SECRET=your_secret \
  CG_OAUTH_STATE_SECRET=$(openssl rand -hex 32) \
  CG_COOKIE_SECURE=1 \
  CG_COOKIE_SAMESITE=none \
  -a cyclegraph-api
fly.toml Config:
tomlCopyapp = "cyclegraph-api"
primary_region = "ams"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[[mounts]]
  source = "cg_state"
  destination = "/app/state"
Deploy Backend:
bashCopy# Fra backend root:
fly deploy

# Sjekk status:
fly status -a cyclegraph-api

# Sjekk logs:
fly logs -a cyclegraph-api
Custom Domain:
bashCopy# Legg til custom domain:
fly certs add api.cyclegraph.app -a cyclegraph-api

# Sjekk sertifikat:
fly certs show api.cyclegraph.app -a cyclegraph-api

🌐 Frontend Deployment (Vercel)
Vercel Project Settings:
CopyFramework Preset: Vite
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
Install Command: npm install
frontend/vercel.json:
jsonCopy{
  "rewrites": [
    { 
      "source": "/api/(.*)", 
      "destination": "https://api.cyclegraph.app/api/$1" 
    },
    { 
      "source": "/(.*)", 
      "destination": "/index.html" 
    }
  ]
}
Viktig: vercel.json MÅ ligge i frontend/ mappen (ikke repo root) fordi Root Directory er satt til frontend.
Deploy Frontend:
bashCopy# Auto-deploy ved push til main:
git add .
git commit -m "your message"
git push origin main

# Vercel deployer automatisk via GitHub integration

🔍 Critical Path Fixes (Læring fra Sprint 1-3)
Problem 1: /data/state vs /app/state
Symptom: index_path: "/data/state/..." men volume mounted til /app/state/
Root cause: CG_STATE_DIR env var satt til /data/state
Fix:
bashCopyfly secrets set CG_STATE_DIR=/app/state -a cyclegraph-api
Verify:
bashCopyfly ssh console -a cyclegraph-api
echo $CG_STATE_DIR  # Skal vise /app/state
df -h | grep state  # Skal vise /dev/vdc mounted til /app/state

Problem 2: Result-filer ikke funnet
Symptom: rows_returned: 0 selv om sessions_index.json har data
Root cause: _pick_result_path() søkte i feil mapper (/app/out/ i stedet for /app/_debug_WithWeather/)
Fix i server/routes/sessions_list_router.py:
pythonCopydef _pick_result_path(sid: str) -> Path | None:
    root = Path("/app")
    
    # PRIORITY: Where files ACTUALLY are
    candidates = [
        root / "_debug_WithWeather" / f"result_{sid}.json",
        root / "_debug_NoWeather" / f"result_{sid}.json",
        root / "scripts" / "_debug" / f"result_{sid}.json",
    ]
    
    for path in candidates:
        if path.exists():
            return path
    
    # Fallback
    fallback = [
        root / "out" / f"result_{sid}.json",
        root / "src" / "cyclegraph" / f"result_{sid}.json",
    ]
    
    for path in fallback:
        if path.exists():
            return path
    
    return None

Problem 3: Vercel SPA routing 404
Symptom: /onboarding ga 404 i prod (virket lokalt)
Root cause: Vercel Root Directory var satt feil / manglende rewrite
Fix:

Vercel Settings → Root Directory: frontend
Build Command: npm run build (ikke cd frontend && ...)
Output Directory: dist (ikke frontend/dist)
Legg vercel.json i frontend/ mappen


🧪 Testing & Verification
Backend Health Check:
bashCopy# Status:
curl https://api.cyclegraph.app/status

# Auth check (krever login):
curl https://api.cyclegraph.app/api/auth/me \
  -H "Cookie: cg_auth=your_token"

# Sessions list (krever login):
curl "https://api.cyclegraph.app/api/sessions/list/all?debug=1" \
  -H "Cookie: cg_auth=your_token"
Frontend Health Check:
bashCopy# SPA routing:
curl -I https://www.cyclegraph.app/onboarding
# Skal returnere 200 OK (ikke 404)

# API proxy:
curl https://www.cyclegraph.app/api/status
# Skal redirecte til api.cyclegraph.app
SSH Debugging:
bashCopy# Start machine (hvis stopped):
fly machine start -a cyclegraph-api

# SSH inn:
fly ssh console -a cyclegraph-api

# Sjekk volume:
df -h | grep state
ls -la /app/state/users/

# Sjekk env vars:
echo $CG_STATE_DIR
env | grep CG_

# Sjekk result-filer:
find /app -name "result_*.json" | wc -l
ls /app/_debug_WithWeather/*.json | head -5

# Sjekk user data:
NEW_UID="u_xxx"
cat /app/state/users/$NEW_UID/sessions_index.json
ls -la /app/state/users/$NEW_UID/

🐛 TROUBLESHOOTING
Problem: "Not authenticated" ved API-kall
Symptom:
jsonCopy{"detail": "Not authenticated"}
Årsaker:

Cookie (cg_auth) mangler eller utløpt
CORS issue (cookie sendes ikke cross-origin)
Backend ser ikke cookie pga. domain mismatch

Debug:
bashCopy# Sjekk at cookie settes:
# DevTools → Application → Cookies → cyclegraph.app
# Skal vise: cg_auth, cg_uid

# Test med curl:
curl https://api.cyclegraph.app/api/auth/me \
  -H "Cookie: cg_auth=your_actual_token" \
  -v
Fix:

Verifiser credentials: "include" i frontend fetch-calls
Sjekk at backend CORS tillater credentials
Verifiser cookie domain er .cyclegraph.app (ikke subdomain-spesifikk)


Problem: Rides vises ikke i UI
Symptom: /rides page tom eller viser "Ingen økter"
Debug steg:

Sjekk API direkte:

bashCopycurl "https://api.cyclegraph.app/api/sessions/list/all?debug=1" \
  -H "Cookie: cg_auth=..."

Verifiser sessions_index.json:

bashCopyfly ssh console -a cyclegraph-api
cat /app/state/users/u_YOUR_UID/sessions_index.json

Sjekk result-filer:

bashCopy# Finn første ride ID fra index
RIDE_ID="16127771071"  # Eksempel

# Sjekk om result-fil finnes:
find /app -name "result_$RIDE_ID.json"

# Åpne result-fil:
cat /app/_debug_WithWeather/result_$RIDE_ID.json | python3 -m json.tool | head -100

Sjekk logs under list/all:

bashCopyfly logs -a cyclegraph-api | grep "list/all"
Vanlige årsaker:

sessions_index.json tom (ingen import kjørt)
Result-filer mangler (analyze ikke kjørt)
_pick_result_path() søker i feil mapper
Metadata parsing feil (felter er null)


Problem: Import feiler / ingen result-filer genereres
Symptom: Import returnerer 200 OK men result-filer skrives ikke
Debug:
bashCopy# Sjekk Strava tokens:
fly ssh console -a cyclegraph-api
cat /app/state/users/u_YOUR_UID/strava_tokens.json

# Sjekk import logs:
fly logs -a cyclegraph-api | grep -i "import\|analyz"

# Sjekk Strava rate limit:
fly logs -a cyclegraph-api | grep "429"
Vanlige årsaker:

Strava 429 rate limit (100 requests per 15 min)
Analyze krasjer stille (mangler error logging)
analyze=1 parameter ignoreres
Ride type ikke støttet (f.eks. VirtualRide, EBikeRide)


Problem: Frontend build feiler
Symptom: Vercel deployment failed
Debug:
bashCopy# Sjekk build lokalt:
cd frontend
npm run build

# Sjekk TypeScript errors:
npm run typecheck

# Sjekk Vite config:
cat vite.config.ts
Vanlige årsaker:

TypeScript errors
Missing dependencies
Env vars ikke satt i Vercel
Vite base path feil konfigurert


📊 KNOWN ISSUES & TECHNICAL DEBT
🔴 Critical (Må fikses før launch)
IssueSeverityImpactStatus55 av 67 rides mangler result-filer🔴 HIGHBrukere ser ikke alle ridesSprint 3Metadata (distance, date, weather) vises som null🔴 HIGHDårlig UXSprint 3

🟡 Important (Før public beta)
IssueSeverityImpactPlanResult-filer spredt over 4 lokasjoner🟡 MEDIUMKompleks debuggingKonsolider til /app/state/results/UTF-8 BOM i result-filer🟡 MEDIUMParsing issuesSkriv uten BOM i analyze_email_index.json global (GDPR)🟡 MEDIUMMå ryddes ved deleteSprint 4Filbasert state (no locking)🟡 MEDIUMConcurrent writes unsafeDB-migrasjon (post-launch)

🟢 Nice-to-have (Post-launch)
IssueSeverityImpactPriorityAutomatic re-analyze on profile change🟢 LOWManual re-import nødvendigSprint 5+Historical data migration🟢 LOWOld rides inconsistentSprint 6+Redis cache for leaderboards🟢 LOWPerformanceSprint 7+

🎓 LESSONS LEARNED
Hva tok mest tid:

Multi-platform debugging (Vercel + Fly) → 70% av tiden
Path mismatches (/data vs /app, result-file locations) → 20%
Multiple API-wrapper systemer (cgApi + api.ts) → 10%

Hva fungerte bra:

SSH debugging i Fly container (umiddelbar tilgang til filsystem)
?debug=1 parameter i API (return internals)
Systematisk eliminering av hypoteser (ikke spekulere!)

Best practices framover:

Start med SSH + logs før kode-endringer
Test lokalt først når mulig (raskere iterasjon)
Én endring om gangen → deploy → test
Dokumenter env vars og path-avhengigheter tidlig
Bruk SSOT-pattern konsekvent (unngå multiple sources of truth)


📞 KONTAKT & SUPPORT
Utvikler: Johnny Strømoe
Email: easy2johnny@gmail.com
Repo: github.com/JohnnyBravo1983/CycleGraph
Vercel Project: cyclegraph
Fly.io App: cyclegraph-api

📈 ROADMAP
SprintStatusETADeliverableSprint 1✅ FullførtJan 2026Auth & SecuritySprint 2✅ FullførtJan 2026Onboarding & StravaSprint 3🔄 PågåendeFeb 2026Data EnrichmentSprint 4📋 PlanlagtFeb 2026Dashboard PolishSprint 5📋 PlanlagtMar 2026Early Beta LaunchSprint 6-7📋 PlanlagtMar-Apr 2026Leaderboards & TrendsSprint 8-9📋 PlanlagtApr 2026Public Launch 🚀

🎯 CURRENT STATUS (2026-01-24)
Production Status:

✅ Frontend live: www.cyclegraph.app
✅ Backend live: api.cyclegraph.app
✅ Auth & signup fungerer
✅ Strava OAuth fungerer
✅ Rides importeres
⚠️ 12 av 67 rides synlige (metadata mangler)
⚠️ Sprint 3 pågår (data enrichment)

Next Steps:

Fix _row_from_doc() metadata parsing
Re-analyze 55 manglende rides
UI polish (dates, distance, weather)
Deploy Sprint 3 → production-ready MVP


Sist oppdatert: 2026-01-24
Versjon: Sprint 3 (pågående)