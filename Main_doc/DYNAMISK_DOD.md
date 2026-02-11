# CycleGraph – Dynamisk Definition of Done
**Periode:** August 2025 - Mars 2026  
**Sist oppdatert:** 11. februar 2026

---

## 📜 Oversikt

Dette dokumentet viser **kronologisk progresjon** av CycleGraph fra prosjektstart til Pioneer Beta launch.

**Formål:** Spore hva som er ferdig, hva som pågår, og hva som er planlagt.

---

## ✅ FASE 1: Foundation (August 2025)

### M1 — Prosjektstruktur & repo
- [x] Standard repo-oppsett: core/, cli/, docs/, data/, shapes/, tests/
- [x] Init GitHub-repo (README, lisens, .gitignore)
- [x] Bygg/kjørbare grunnkommandoer dokumentert i README (Rust/Python)
- [x] CI eller lokal "quick check": cargo check og enkel Python-kall fungerer

### M2 — Rust-core med PyO3
- [x] Cargo.toml satt opp med PyO3
- [x] Minst én eksponert Rust-funksjon bundet til Python (importerbar)
- [x] cargo test (grunnleggende) og "import i Python" fungerer lokalt
- [x] Kodekommentarer: hvor core-API lever og hvordan bygge

### M3 — CLI-oppsett & dataflyt
- [x] cli/analyze.py kjører ende-til-ende mot core (Rust) med argparse-flagg
- [x] I/O-kontrakt: leser CSV/streams, skriver rapport/JSON til output/
- [x] Grunnleggende feilhåndtering (fil mangler, feil format) med tydelige feilmeldinger
- [x] "Happy path" demonstrert på sample data

### M4 — Dummydata & testkjøring
- [x] Dummy/samples tilgjengelig i repo (ikke sensitive)
- [x] Kjøreeksempel dokumentert: python -m cli.analyze produserer forutsigbar rapport
- [x] Sanity-sjekk: verdier i rapport er konsistente og uten exceptions
- [x] Enkle tester/skript verifiserer flyten

### M5 — SHACL-validering
- [x] SHACL-shapes for RDF definert i shapes/
- [x] Valideringsscript i Python: kjørbar via CLI-flag eller separat kommando
- [x] Eksempelfiler validerer OK; feil rapporteres forståelig
- [x] Kort bruksdokumentasjon i docs/

**Status:** ✅ Ferdig (August 2025)

---

## ✅ FASE 2: Strava Integration (September 2025)

### M6 — Strava-integrasjon (API & import)
- [x] OAuth-flyt verifisert; tokens lagres sikkert lokalt
- [x] Henting av aktiviteter med paging og tidsfilter (--since) fungerer
- [x] Streams → CSV (minst time, hr, watts), robust håndtering av 401/403/429/5xx
- [x] Inkrementell state (ingen duplikater), og grunnlogg over kjøringer
- [x] End-to-end "import → analyze" fungerer på ≥3 reelle økter

**Status:** ✅ Ferdig (September 2025)

---

## ✅ FASE 3: Analyse-engine (Oktober 2025)

### M7 — Analysefunksjoner (effektivitet, treningsscore)
- [x] CGS v1 etablert: IF/NP/VI/Pa:Hr/WpB + 28d baseline (±25%), tydelige fallbacks
- [x] Badges: Big Engine (+6%, ≥30min) og Metronome (VI≤1.05, Pa:Hr≤1.05)
- [x] Python: Strava publish-formatter m/ språk, trimming og fallbacks + tester grønne
- [x] Rust: unit + golden + perf-guard (2h@1Hz ≤200ms) grønne
- [x] Strava-klient: auto-refresh, header-fix, comment→description-fallback, verifisert live
- [x] Docs: CGS_v1, CLI usage, Strava publish oppdatert

### M7.5 — Backend-forfining (CGS v1.1, explain)
- [x] Systemtest grønn på steg 0–7: PyO3-import, CLI-hjelp, E2E med sample, idempotens, feilhåndtering
- [x] Fikser: ryddet cmd_session, fikset continue-feil, lagt til mod metrics i lib.rs
- [x] Output verifisert deterministisk

### M7.5 — Forebyggende tester
- [x] Pytest: _analyze_session_bridge() kaster ValueError ved tomme arrays
- [x] Rust golden-test for w_per_beat() med edge-case input (NaN/null/mismatch)
- [x] Tester grønne: pytest + cargo test (inkl. golden)

### M7.5 — GitHub Actions (basic CI)
- [x] Minimal workflow: kjører pytest -q og cargo test --tests -q på push/PR
- [x] Workflow verifisert OK på GitHub

### M7.6 — Strava Fetch & Modusdeteksjon
- [x] Auto-modus basert på trainer, sport_type og device_watts
- [x] CLI-flag --mode roller|outdoor som overstyrer auto
- [x] JSON-output rutes til riktig pipeline (indoor/outdoor)
- [x] Tester: pytest + cargo test grønne

### M7.6B — No-watt policy & fallback
- [x] Backend: rute økter uten watt eller device_watts=False til hr_only pipeline
- [x] Frontend (senere): vise varsel "Ingen effekt-data registrert"
- [x] Logging: structured WARN med no_power_reason
- [x] Observability: metrics sessions_no_power_total, sessions_device_watts_false_total

**Status:** ✅ Ferdig (Oktober 2025)

---

## ✅ FASE 4: Physics Engine (November 2025)

### S2 — Vær & profiler
- [x] Værklient (vind/temp/trykk) med caching per (lat,lon,timestamp)
- [x] Profilsettings (total vekt, sykkeltype, Crr-preset) + validering/defaults
- [x] CLI integrasjon: justert effektivitet basert på værkontekst
- [x] DoD: ≥95% cache-hit ved rekjøring; sanity-test hoppes over når publiseringsflyt ikke berøres
- [x] Status: pytest + cargo grønne, stabile tall ±1–2W

### S3 — Fysikkmotor
- [x] Kraftmodell: gravitasjon, rulling (Crr), aero (CdA), akselerasjon + drivverkstap
- [x] Høyde-smoothing i egen modul + outlier-kutt (stopp/sving)
- [x] Sample-watt + 5s glatting + NP/avg i CLI
- [x] Golden test i CI (±1–2W; NP/avg ±1W) oppnådd
- [x] Deterministisk output

### S4 — Kalibrering (CdA/Crr-fit)
- [x] Kalibreringsprosedyre (5–8 min, 3–6% bakke)
- [x] Fit CdA/Crr fra data (uten powermeter)
- [x] Lagre pr sykkel/profil; bruk globalt i beregninger
- [x] Reproducible fit på testdata
- [x] MAE ≤10% mot powermeter på kalibreringssegment
- [x] Flagg "Kalibrert: Ja/Nei"

### S5 — Indoor pipeline + GPS/Wind integrasjon
- [x] Indoor/outdoor-pipeline koblet til fysikkmotor m/ vindkorrigering
- [x] CLI-output: watts, wind_rel, v_rel, calibrated, status
- [x] Eksponert backend-API for frontend: cli/session_api.py: analyze_session()
- [x] Golden test med syntetisk GPS+vindfelt etablert
- [x] Unicode-bug i CLI løst
- [x] Tester: cargo/pytest grønne, output stabil ±1–2W

**Status:** ✅ Ferdig (November 2025)

---

## ✅ FASE 5: Web Application Foundation (Desember 2025)

### S8 — Scaffold & dataadapter
- [x] React/Tailwind scaffold, routing, state
- [x] Bruk eksisterende Python-API analyze_session() som backend-adapter
- [x] Frontend forventer schema_version i output
- [x] Håndterer HR-only fallback
- [x] Viser én økt (mock) i UI
- [x] Bytte mock→live via .env
- [x] JSON-output fra backend valideres mot schema_version

### S8.5 — Mini-sprint: Precision Watt stubs + short-session guard
- [x] Utvidet SessionReport med: precision_watt, precision_watt_ci, sources, cda, crr, reason
- [x] Oppdatert mockSession med dummy-serier (40 samples)
- [x] Dev-sanity i SessionView (kun DEV): teller PW/CI samples
- [x] Short-session guard (<30 samples): kontrollert melding, ingen crash
- [x] App bygger grønt med nye felter

### S9 — Økt-kort & nøkkelmetrikker
- [x] SessionCard viser NP, IF, VI, Pa:Hr, W/slag, CGS og PrecisionWatt-verdi
- [x] Indoor/Outdoor-chip og Kalibrert-status i UI
- [x] Short-session guard med kontrollert melding
- [x] HR-only fallback støttes uten crash
- [x] MockSession oppdatert (outdoor/indoor-varianter)
- [x] Konsistent rendering

**Status:** ✅ Ferdig (Desember 2025)

---

## ✅ FASE 6: File-based State & SSOT Model (Januar 2026)

### Backend Architecture Shift
- [x] Migrert fra database-forslag til file-based state
- [x] Per-user directory structure: `/app/state/users/<uid>/`
- [x] SSOT-modell etablert:
  - `sessions_index.json` → Which sessions exist
  - `result_<sid>.json` → Metrics for each session (SSOT)
  - `sessions_meta.json` → Derived cache only
- [x] Cookie-based auth (`cg_auth`)
- [x] FastAPI backend deployed on Fly.io
- [x] React frontend deployed on Vercel

### Authentication System
- [x] Local auth (username/password)
- [x] Strava OAuth integration
- [x] Token refresh handling
- [x] Session management via cookies

### Strava Import & Analysis Pipeline
- [x] `/api/strava/sync` - Fetch rides from Strava
- [x] `/api/strava/import/{rid}` - Import single ride + analyze
- [x] Weather data integration (Open-Meteo API)
- [x] Deterministic analysis (Rust engine via PyO3)
- [x] Results stored in `result_<sid>.json`

**Status:** ✅ Ferdig (Januar 2026)

---

## ✅ FASE 7: SSOT Stabilization & Onboarding (Januar - Februar 2026)

### Weather Integration Fixes
- [x] Weather fetching during onboarding fixed
- [x] Weather cached in `result_<sid>.json`
- [x] Fallback to standard atmosphere if API fails
- [x] Error handling for missing coordinates
- [x] `weather_source` field always present in results

### Rides List - Full SSOT
- [x] Rides list ONLY reads from `result_<sid>.json`
- [x] Removed all fallbacks to Strava API
- [x] Removed "hydrations" and duplicate data storage
- [x] Standardized field names:
  - `distance_km` (not distance_m)
  - `precision_watt_avg` (not avg_power)
  - `weather_source` (always present)
- [x] `/api/sessions/list/all` endpoint stable
- [x] Frontend Rides.tsx reads from SSOT only

### Onboarding Stabilization
- [x] New user signup flow works end-to-end
- [x] Onboarding form captures:
  - Rider weight, bike weight
  - CdA, Crr, crank efficiency
  - Bike type, tire specs
- [x] Profile data saved to `profile.json`
- [x] First ride import triggers weather fetch
- [x] Analysis runs without errors
- [x] Rides appear in list with correct metrics

### Profile System (Designed)
- [x] `profile.json` stores user physical parameters
- [x] `profile_versions.jsonl` designed for audit log
- [x] `server/utils/versioning.py` exists
- [x] `/api/profile/get` endpoint works
- [x] `/api/profile/save` endpoint works

**Status:** ✅ Ferdig (Februar 2026)

---

## 🚧 FASE 8: Pioneer Beta Sprint (11. februar - 1. mars 2026)

**Sprint Goal:** Launch Pioneer Beta with stable profile system and power analytics

### Week 1: Foundation (Feb 11-17)

#### Day 1 - Signup Enhancement
- [ ] Add demographic fields to signup form:
  - Gender (male/female)
  - Country (text input)
  - City (text input)
  - Age (number, 13-100)
- [ ] Update `POST /api/auth/signup` backend
- [ ] Store in `auth.json`
- [ ] Test backward compatibility

#### Day 2-3 - Profile in Dashboard
- [ ] Create Profile section in Dashboard UI
- [ ] Display current profile values (weight, bike specs, FTP)
- [ ] Make fields editable
- [ ] Save via `PUT /api/profile/save`
- [ ] Test profile versioning (weight change → verify old rides unchanged)

#### Day 4 - Onboarding UI Cleanup
- [ ] Improve layout (cleaner, more spacious)
- [ ] Add tooltips for technical fields (CdA, Crr, crank efficiency)
- [ ] Set smart defaults (CdA: 0.300, Crr: 0.0040)
- [ ] Mark required vs optional fields
- [ ] Test with fresh eyes (pretend new user)

#### Day 5 - Remove Duplicate Routes
- [ ] Identify current `strava_import_router` file
- [ ] Delete duplicate file
- [ ] Remove `/api/sessions/list` from `sessions.py`
- [ ] Test all affected endpoints
- [ ] Verify no regressions

#### Day 6 - Consolidate Meta Generation
- [ ] Create `server/utils/meta_generator.py`
- [ ] Single function: `generate_sessions_meta(uid)`
- [ ] Move logic from sessions_list_router.py, sessions.py, strava_import_router.py
- [ ] Call explicitly after analysis/batch import
- [ ] Test: delete meta, regenerate, verify correct

### Week 2: Analytics Features (Feb 18-24)

#### Day 7 - Profile Versioning Verification
- [ ] End-to-end test: weight change → old rides unchanged, new rides use new weight
- [ ] Verify `profile_versions.jsonl` contains history
- [ ] Document test results
- [ ] Fix any issues discovered

#### Day 8 - Import UX Improvements
- [ ] Simple dropdown: "Import 10 rides" or "Import 50 rides" (default: 50)
- [ ] Working progress bar (real-time updates)
- [ ] Error handling: show which rides failed
- [ ] "Retry failed rides" button
- [ ] Test with 50 ride import

#### Day 9-10 - Power Profile (Backend + Frontend)
- [ ] Backend: Calculate FTP estimate (95% of 20min peak)
- [ ] Backend: Calculate peak efforts (1min, 5min, 20min, 45min, 60min)
- [ ] Backend: Calculate W/kg for all values
- [ ] Cache results in `result_<sid>.json`
- [ ] Frontend: Display Power Profile card
- [ ] Frontend: Show FTP + peaks in table format
- [ ] Frontend: Show both W and W/kg

#### Day 11-12 - FTP Progression (Backend + Frontend)
- [ ] Backend: Time-based grouping (weekly/monthly)
- [ ] Backend: Calculate FTP trend over time
- [ ] Backend: Polynomial fit + future projection (4-8 weeks)
- [ ] Backend: Confidence intervals for projection
- [ ] Frontend: Line chart showing FTP over time
- [ ] Frontend: Show projection with shaded confidence area
- [ ] Frontend: Display "Reach XW in Y weeks"

### Week 3: Polish & Testing (Feb 25 - Mar 1)

#### Day 13-14 - End-to-end Testing
- [ ] Full user journey test (signup → onboarding → import 50 rides → view trends)
- [ ] Test on multiple browsers (Chrome, Firefox, Safari)
- [ ] Test on mobile (responsive design)
- [ ] Document bugs found
- [ ] Fix critical bugs

#### Day 15 - Documentation & Cleanup
- [ ] Update README.md (feature list, setup instructions, tech stack)
- [ ] Add inline code comments where needed
- [ ] Clean up console.logs
- [ ] Remove commented-out code
- [ ] Update API_REFERENCE.md if endpoints changed
- [ ] Take screenshots for job applications

#### Day 16 - Pioneer User Preparation
- [ ] Create onboarding guide for pioneers
- [ ] Set up feedback mechanism (form or email)
- [ ] Prepare demo script
- [ ] Deploy to production (verify Vercel + Fly.io)
- [ ] Test production environment

#### Day 17 - Invite Pioneers & Monitor
- [ ] Invite 5-10 pioneer users
- [ ] Monitor for issues
- [ ] Respond to feedback quickly
- [ ] Document issues found
- [ ] Make quick fixes if possible

#### Day 18 - Final Polish & Retrospective
- [ ] Fix any critical bugs from Day 17
- [ ] Update documentation based on feedback
- [ ] Prepare for April sprint
- [ ] Update SPRINT_LOG.md with accomplishments
- [ ] Celebrate launch! 🎉

**Status:** 🚧 In Progress (Starting Feb 11, 2026)

---

## 📋 FASE 9: MVP Launch (April 2026) - PLANNED

### Goals Feature
- [ ] Build on FTP Progression
- [ ] "Click projection to set as goal" functionality
- [ ] Goal tracking UI
- [ ] Progress notifications

### Enhanced Analytics
- [ ] Intensity distribution (time in zones)
- [ ] Power curves
- [ ] Training load tracking

### Leaderboards Foundation
- [ ] Segment detection algorithm
- [ ] Segment matching across rides
- [ ] Basic leaderboard UI

### Payment Integration
- [ ] 30-day free trial
- [ ] Subscription management
- [ ] Payment gateway integration

**Status:** 📋 Planned (April 2026)

---

## 📋 FASE 10: Mature Launch (Mai 2026) - PLANNED

### Forum Feature
- [ ] User forum/community
- [ ] Discussion threads
- [ ] User profiles
- [ ] Moderation tools

### Advanced Features
- [ ] Benchmarking ("Good" vs "Very Good" categories)
- [ ] Social features (follow riders, kudos)
- [ ] Mobile app considerations
- [ ] Performance optimization at scale

**Status:** 📋 Planned (Mai 2026)

---

## 🎯 Critical Success Factors (Always Maintained)

### Determinisme
- Same input → same output
- No randomness in analysis
- Reproducible results
- ±1-2W tolerance acceptable

### SSOT (Single Source of Truth)
- `sessions_index.json` → Which sessions exist
- `result_<sid>.json` → Metrics (SSOT)
- `profile.json` → Current user profile
- `sessions_meta.json` → Cache only (regenerate-able)

### No Double Storage
- Data exists in one place only
- Cache is derived, not canonical
- Profile versioning preserves history

### Physics Engine First
- Rust watt calculation is core value
- Everything else is wrapper/UI
- PyO3 integration must be stable

---

## 📊 Progress Summary

**Completed Phases:** 7 (August 2025 - February 2026)  
**Current Phase:** 8 (Pioneer Beta Sprint)  
**Planned Phases:** 2 (April - May 2026)

**Total Development Time:** ~7 months (August 2025 - Mars 2026)  
**Lines of Code:** ~15,000+ (Rust + Python + TypeScript)  
**Key Technologies:** Rust, Python, FastAPI, React, PyO3, Strava API

---

## ✅ Definition of Done (Per Phase)

**For each phase to be "done":**
1. All checkboxes completed
2. Tests passing (cargo + pytest)
3. No critical bugs
4. Deployed to production (if applicable)
5. Documented in code and/or docs/

**For entire project to be "done" (May 2026):**
1. All 10 phases complete
2. Pioneer feedback incorporated
3. MVP launched with paying users
4. Forum and community active
5. System is stable and scalable

---

**Last updated:** 11. februar 2026  
**Next update:** 1. mars 2026 (after Pioneer Beta launch)
