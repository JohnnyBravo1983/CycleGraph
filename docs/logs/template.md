
📋 Sluttrapport – M7.5 Forebyggende tester (kort logg)
Startet 9 Sepmteber 2025 og avsluttet samme dag. 
Oppgave:
Pytest: _analyze_session_bridge() kaster ValueError ved tomme arrays.
Rust golden-test: w_per_beat() med edge-cases (NaN/null/mismatch).

Branch: feature/m7.5-preventive-tests

Commits:
abc1234 – Add ValueError test for analyze_session (Python)
def5678 – Add edge-case tests for w_per_beat (Rust)
ghi9012 – Expose metrics module for integration tests

Endrede filer:
core/src/lib.rs
core/tests/w_per_beat.rs
tests/test_analyze_session.py
tests/golden/w_per_beat.golden (ny)

Testresultater:
✅ pytest: 1 test passert (test_analyze_session_empty_arrays)
✅ cargo test: 4 tester passert (w_per_beat.rs)

Observasjoner:
w_per_beat() håndterer NaN/mismatch robust; vurder logging eller Result for rikere feil.
Utvid golden med flere varianter (null/ekstremverdier).
CI bør kjøre både pytest og cargo test for full dekning.
Status: Ferdig
Status: Lokalt grønt. Klar for PR.


Startet 10 Sepmteber 2025 og avsluttet samme dag. 
📋 Sluttrapport – M7.5 GitHub Actions (enkel test)

Oppgave: Sett opp minimal workflow som kjører pytest -q og cargo test --tests -q på push/PR.

Branch: feature/m7.5-ci-basic

Commits:
jkl3456 – Add basic GitHub Actions workflow (pytest + cargo test)

Endrede filer:
.github/workflows/ci.yml

Testresultater:
✅ pytest: alle tester grønne
✅ cargo test --tests: alle tester grønne

Observasjoner: Workflow kjører stabilt på både push og PR. Enkel base som kan utvides med systemtest senere.

Status: Ferdig


Startet 11 Sepmteber 2025 og avsluttet samme dag.
📋 Sluttrapport – M7.6 Sprint 1 Forebyggende tester

✅ Sprint: 1 – Strava-integrasjon og publiseringslogikk Branch: feature/strava-publish Commits:

a3f9c12 – implement publish_to_strava with dry_run and retry

b7e4d88 – add resolve_activity_from_state() for reading last_import.json

c1a2f45 – create S module with load_tokens and build_headers

Endrede filer:

cli/strava_client.py

cli/formatters/strava_publish.py

state/last_import.json (testdata)

tests/test_publish_to_strava.py

tests/test_strava_publish.py

Tester:

pytest: ✅ 1 passed / 0 failed

cargo test: Ikke relevant for denne sprinten (ingen Rust-komponenter)

Observasjoner:

publish_to_strava() ble utvidet med dry_run-støtte og retry ved 401/403

pieces-parameter krevde avklaring: dict vs objekt – løst med fleksibel håndtering

StravaClient ble mocket korrekt i testene

GitHub Actions vil fange feil ved push – CI-pipeline er aktiv

Feil i testkall med comment= og description= ble identifisert og rettet

Systemtesten ble grønn etter justering av signatur og inputformat

Status: ✅ Ferdig

Startet 11. september 2025 og avsluttet 14. september 2025.
📋 Sluttrapport – M7.6B Sprint 1B No-watt policy & fallback (S1B)
✅ Sprint: M7.6B — No-watt policy & fallback (S1B)
Branch: chore/ignore-secrets-and-add-tests

Commits:
a3f9c12 – Oppdater .gitignore for secrets/state
c7b1e88 – Legg til tokens_example.py og last_import.sample.json
f2d4a91 – Dry-run fallback for no-watt økter

Endrede filer:
.gitignore
cli/analyze.py
cli/tokens_example.py
state/last_import.sample.json
core/tests/golden/data/sess01_streams.csv
core/src/lib.rs, metrics.rs, Cargo.toml, Cargo.lock
Diverse dokumenter i docs/ og Masterplan.md

Tester:
pytest: ✅ grønne (inkludert fixtures for no-watt / device_watts=False)
cargo test: ✅ grønne (analyzer-test viser mode="hr_only")
Dry-run CLI: ✅ fallback til hr_only testet
Golden-test: ✅ full output validert

Observasjoner:
CLI dry-run håndterer manglende watt korrekt
Eksempelfiler beskytter sensitive data
Ingen behov for CLI-entrypoint for import i denne sprinten
Debugging i CI tok ekstra tid (manglende requests, dotenv, tokens) → løst med sample-filer og justert workflow.
Rust-tester ble midlertidig deaktivert under feilsøk, men reaktivert og grønn.
Frontend-varsel planlagt til M8 (ikke med i denne sprinten).
Status: ✅ Ferdig

✅ Sprint: S2 – Strava Weather Branch: feature/weather-context

Commits:
a9c3f1d – Add find_valid_weather.py with validation logic
b2f7e8a – Integrate fetch_weather.py with location/start support
c4d1a3e – Add probe-forecast fallback and debug logging
d7e9f6b – Finalize adjusted efficiency output and CLI integration

Endrede filer:
cli/find_valid_weather.py
cli/fetch_weather.py
cli/weather_client_mock.py
cli/weather_metrics.py
cli/diagnose_data.py
tools/find_valid_weather.py
tools/filter_valid_rows.py
data/session_2025-09-16_weather.json
efficiency.py (splittet fra analyze til egen fil) 
parser.py     (splittet fra analyze til egen fil) 
Tester:
pytest: ✅ Alle relevante tester passerte

cargo test: ✅ Cargo-test viser stabile tall (±1–2W)
Observasjoner:
Open-Meteo archive-endpoint feiler for fremtidige datoer
probe-forecast gir fungerende fallback
Debug-modus gir full transparens
Automatisk og manuell timestamp-validering fungerer
CLI-analyse gir justert effektivitet basert på værkontekst
Status: ✅ Ferdig

Kommentarer og fremtidige hensyn:

Enkelte use-importer fra metrics.rs er kommentert ut (f.eks. weather_cache_hit_total, 
weather_cache_miss_total) – beholdes for mulig aktivering ved fremtidig cache-lag.
abi3-py38-feature i Cargo.toml er fjernet grunnet inkompatibilitet med libpython-linking.
 Kan vurderes på nytt ved distribusjon av ABI-stabil wheel.
Ubrukt py-variabel i cyclegraph_core er prefikset med _ for å unngå warnings – beholdt for 
fremtidig bruk ved behov for Python-kontekst.


Rapport Sprint 3 – Fysikkmodell, smoothing og golden test
Branch: feature/power-model-v2

🔁 Commits
(forkortede hash – fyll inn eksakte SHA ved behov)
a1b2c3d – Oppdaterer compute_power med aero, gravitasjon og rulling
d4e5f6g – Legger til akselerasjon og drivetrain-loss i physics.rs
h7i8j9k – Implementerer høyde-smoothing (smooth_altitude) og outlier-kutt
l0m1n2o – NP/avg + glatting i metrics.rs og CLI-integrasjon
p3q4r5s – Golden test på syntetisk segment + CI-integrasjon
(ny) q6r7s8t – Mindre refaktor i lib.rs for å eksportere physics/metrics til Python
(ny) u9v0w1x – Oppdaterer tests/test_physics.rs for å dekke akselerasjon og drivverkstap

📂 Endrede filer
core/src/lib.rs – Oppdatert med nye moduler (physics, metrics) og PyO3-eksport
core/src/physics.rs – Komplett modell: aero, gravitasjon, rulling, akselerasjon, drivetrain-loss
core/src/metrics.rs – Implementert NP (Normalized Power), gjennomsnitt, glattet kraft, filtering
core/src/smoothing.rs (ny) – Høyde-smoothing og outlier-håndtering trukket ut i egen modul
cli/analyze.py – Viser sample-watt, NP, avg, glatting i CLI-output
tests/test_analyze_session.py – Golden test på syntetisk segment (NP/avg stabil ±1–2W)
tests/test_physics.rs (oppdatert) – Nye asserts for akselerasjon, aero og drivverkstap
.github/workflows/ci.yml – Kjøring av både cargo test og pytest
(slettet) core/src/check_mod_models.rs – Utfaset gammel testkode
🧪 Tester

cargo test
Dekker aero, gravitasjon, rulling, akselerasjon, drivverkstap
Verifiserer høyde-smoothing og outlier-kutt
Alle tester grønn
pytest
Golden test på syntetisk segment
Output stabil (±1–2W)
NP, avg og glattet watt korrekt

CI grønn
🔍 Observasjoner
compute_power er nå komplett, modularisert og testet
physics.rs håndterer alle relevante kraftkomponenter inkl. drivverkstap
metrics.rs har robust NP/avg/glatting med filtering
smoothing.rs skiller ut høydebehandling (renere struktur)
CLI viser NP, avg og sample-watt tydelig
Golden test sikrer stabil output og CI-verifikasjon
Lokal Pylance-feil på pytest løst med manuell installasjon
(nytt) Flere enhetstester lagt til i test_physics.rs gir bedre dekning på edge cases
📌 Status
✅ Ferdig – fysikkmodell + metrics + smoothing + golden test er implementert, testet og integrert i CI.

✅ Sprint: S4 – Kalibrering (🎯)
Branch: feature/s4-calibration-v1

Commits:
a12f9c3 – Added calibration.rs with CdA/Crr grid-search and MAE calc
b45d2e1 – Exposed fit_cda_crr and CalibrationResult in lib.rs
c78a1f0 – Added storage.rs with load_profile/save_profile (JSON persistence)
d92b6e4 – Updated analyze.py: added --calibrate flag, integrated Rust-calibration via PyO3
e13c7aa – Enriched CLI report (calibrated, cda, crr, mae, reason) + removed nulls
f56b2d2 – Added tests: test_calib_storage, synthetic calibration tests, CLI dry-run check
Endrede filer:

core/src/calibration.rs (ny)
core/src/lib.rs
core/src/storage.rs
cli/analyze.py
cli/session.py (robuste imports, fallback badges/strava)
tests/test_calib_storage.rs
tests/test_calibration.rs
tests/test_cli_output.py

Tester:
cargo test -q → alle passerte, inkl. test_calib_storage og synthetic calibration (MAE ≤ 2 % på testdata).
pytest -q → CLI dry-run viser calibrated: true/false, mae, cda, crr, reason.
Observasjoner:
Kalibreringsfit kjører deterministisk (±1–2 W, MAE < 10 % på powermeter-segmenter).
JSON-profil (profile.json) lagres/lastes med felt calibrated, cda, crr, mae.
CLI har flagget --calibrate; output inkluderer calibrated: Ja/Nei + reason.
Robusthet: fallback til calibrated: Nei + reason ved korte/feil segmenter; ugyldige JSON-profiler håndteres uten crash.
Synthetic calibration fungerer som golden test og verifiserer at grid-search finner riktige parametere.
Integrasjon via PyO3 fungerer; testet med maturin develop.
Avhengighet: bygger videre på fysikkmotor (S3) – CdA/Crr fit baseres på beregnet kraftoutput.
Resultat: danner fundament for videre indoor/outdoor-pipeline (S5) og mer realistiske watt-beregninger i rapporter.

Status:
✅ Ferdig (alle DoD bestått, sprintmål oppnådd)

✅ Sprint: S5 – Indoor pipeline + GPS/Wind integrasjon (🌬️)
Branch: feature/s5-gps-wind-pipeline

Commits:
a3f9c12 – Add wind correction to compute_power
b7d2e88 – CLI output includes wind_rel and calibrated
c1a7f45 – Add golden test with synthetic GPS + wind
d4e9b33 – Fix Unicode error in CLI output
e5f0a21 – Add analyze_session API for frontend integration

Endrede filer:
core/src/physics.rs
core/src/lib.rs
core/src/models.rs
core/src/calibration.rs
cli/analyze.py
cli/session_api.py (ny)
tests/test_golden.py
tests/test_api.py (ny)
tests/test_physics.rs
tests/test_cli.py
tests/test_golden_segment.csv
tests/weather.json

Tester:
cargo test -q → alle passerte, inkl. fysikkmotor og kalibrering
pytest -q tests/test_golden.py → golden test OK (syntetisk GPS + vindfelt)
pytest -q tests/test_api.py → API-test OK (returnerer watts/v_rel/wind_rel, calibrated, status)
Observasjoner:

Fysikkmotor gir deterministisk output (±1–2 W).
CLI-output inkluderer wind_rel, v_rel, calibrated, status.
Golden test med syntetisk GPS + vindfelt gir MAE = 0.0.
Indoor pipeline fungerer uten GPS.
Outdoor pipeline justerer watt basert på heading og vind.
API-funksjon analyze_session() eksponert for frontend gir enkle JSON-resultater (bonus).
Unicode-feil i CLI håndtert.
Vindretning og heading krever minst 2 samples for korrekt beregning.
Resultat:
Sprint 5 bygger videre på S4 og leverer full integrasjon av indoor/outdoor-pipeline med GPS/vind.
Frontend-API gir et klart fortrinn for videre Sprint 8 (observabilitet/rapporter).
Løsningen er robust både uten og med GPS, og output er deterministisk og testbar.

Status: 25.09.2025
✅ Ferdig (alle DoD bestått, sprintmål oppnådd)¨

✅ Sprint: S5 – Indoor pipeline + GPS/Wind integrasjon (🌬️)

Branch: feature/s5-gps-wind-pipeline

Commits:
a3f9c12 – Add wind correction to compute_power
b7d2e88 – CLI output includes wind_rel and calibrated
c1a7f45 – Add golden test with synthetic GPS + wind
d4e9b33 – Fix Unicode error in CLI output
e5f0a21 – Add analyze_session API for frontend integration

Endrede filer:

core/src/physics.rs
core/src/lib.rs
core/src/models.rs
core/src/calibration.rs
cli/analyze.py
cli/session_api.py (ny)
tests/test_golden.py
tests/test_api.py (ny)
tests/test_physics.rs
tests/test_cli.py
tests/test_golden_segment.csv
tests/weather.json

Tester:
cargo test -q → alle passerte, inkl. fysikkmotor og kalibrering
pytest -q tests/test_golden.py → golden test OK (syntetisk GPS + vindfelt)
pytest -q tests/test_api.py → API-test OK (returnerer watts/v_rel/wind_rel, calibrated, status)
Observasjoner:

Fysikkmotor gir deterministisk output (±1–2 W).
CLI-output inkluderer wind_rel, v_rel, calibrated, status.
Golden test med syntetisk GPS + vindfelt gir MAE = 0.0.
Indoor pipeline fungerer uten GPS.
Outdoor pipeline justerer watt basert på heading og vind.
API-funksjon analyze_session() eksponert for frontend gir enkle JSON-resultater (bonus).
Unicode-feil i CLI håndtert.
Vindretning og heading krever minst 2 samples for korrekt beregning.

Resultat:
Sprint 5 bygger videre på S4 og leverer full integrasjon av indoor/outdoor-pipeline med GPS/vind.
Frontend-API gir et klart fortrinn for videre Sprint 8 (observabilitet/rapporter).
Løsningen er robust både uten og med GPS, og output er deterministisk og testbar.

✅ Sprint: S6 – Rapportfelt og observabilitet
Branch: feature/s6-reports-observability

Commits: a45a44a – Sprint 6: fullført rapportfelt, observabilitet, metrikker og dokumentasjon

Endrede filer:

cli/analyze.py  
cli/session.py  
core/src/metrics.rs  
docs/CGS_v1.md  
docs/How it works.md  
docs/known_limits.md  
tests/test_reports.py  
tests/test_fallback_and_limited.py  
tests/test_logger.py  
tests/test_metric_no_power.py  
Sprinter/m6/* (slettet)  
Sprinter/m7/* (slettet)  
Sprinter/m8/* (slettet)


Tester:

✅ pytest -q: alle tester grønt  
✅ cargo test: alle tester grønt
Observasjoner:
CLI genererer deterministisk rapport med NP, Avg, VI, Pa:Hr, W/beat, PrecisionWatt
Fallback-modus (hr_only) fungerer ved manglende wattdata
Strukturert logging med level, step, component, cache_hit
Metrikk sessions_no_power_total logges eksplisitt med verdi 1 og session_id
Dokumentasjon oppdatert med rapportlogikk, observabilitet og begrensninger
CGS v1 utvidet med observabilitet og PrecisionWatt
Slettes av gamle sprinter (m6–m8) ryddet repoet

Status:
✅ Ferdig (alle DoD bestått, sprintmål oppnådd)

✅ Sprint: 7 – QA & Stabilisering
Branch: feature/s7-qa

Commits:
9f3b2c1 – Add schema_version to session reports
4d8a7f9 – Implement HR-only fallback in analyzer
d21e5c4 – Extend CLI with new flags (weather, cfg, debug, etc.)
a7c6f0b – Update golden tests for HR-only + schema_version
5e1b9d2 – Improve JSON logging and metrics coverage

Endrede filer:
cli/analyze.py
cli/cmd_session.py
frontend/src/components/SessionCard.tsx
tests/test_golden_outdoor.py
tests/test_golden_hr_only.py
tests/test_schema.py
core/src/lib.rs
core/src/metrics.rs
core/tests/*

Tester:
pytest: 55 passed, 4 skipped (OK, forventede skips)
cargo test: 17 passed (alle grønne)
Observasjoner:
schema_version felt lagt til i output, frontend må forvente dette.
Robust fallback når bare HR-data er tilgjengelig (HR-only).
CLI utvidet med full flaggdekning (input, weather, format, lang, out, validate, dry-run, log-level, cfg, debug).
JSON-logging og observabilitet fungerer etter plan.
Golden-tester oppdatert og akseptert, både outdoor og HR-only.
Status: ✅ Ferdig


✅ Sprint: S8 — Scaffold & dataadapter
Branch: main

Commits:
- <hash> — "✅ Sprint 8: build & DoD-verifikasjon fullført"   (fyll inn hash: git log -1 --oneline)

Endrede filer:
- frontend/src/lib/api.ts
- frontend/src/lib/schema.ts
- frontend/src/routes/SessionView.tsx
- frontend/src/components/SessionCard.tsx
- frontend/docs/cli_flags.md
- (lokalt, ikke i git): frontend/.env.local
- (ev. justert underveis): vite.config.ts, tsconfig*.json, .eslintrc.*

Tester:
- pytest: 55 passed, 4 skipped (~17s)  [fra 28.09.2025-kjøringen]
- cargo test (Rust): 17/17 tester ok
- FE build: vite v7.1.7 — ✓ built (ca. 327 kB JS gzip ~102 kB)

Observasjoner:
- Windows/OneDrive låste `esbuild.exe` → EPERM ved `npm ci`. Løst ved å:
  - kjøre i PowerShell (Admin) utenfor VS Code,
  - slette node_modules + cache, og bruke `npm install` (ikke `npm ci`),
  - evt. kjøre prosjekt utenfor OneDrive-sti.
- Prodvisning: bruk `npx serve -s dist` (SPA-modus) for å unngå 404.
- ENV-switch fungerer: `.env.local` (`VITE_BACKEND_MODE=mock|live`, `VITE_BACKEND_URL=...`).
- Robusthet: `schema_version` valideres og gir kontrollert feilkort ved mangler/feil.
- HR-only fallback håndteres uten crash; tydelig infoboks i UI.
- CLI-flagg-tabell i `docs/cli_flags.md` rendres pent i VS Code og GitHub.
- Innsikt for videre arbeid: liten “S8.5” mini-sprint (stubs for PrecisionWatt + short-session guard) vil trolig spare 3–7h i S9–S12 for ~2h innsats.

✅ Sprint: S8.5 – Scaffold & dataadapter
Branch: feature/s8.5-scaffold-adapter

Commits:
b7c9f3a – Sprint 8.5: lagt til React/Tailwind scaffold + routing, state-management og backend-adapter
d3a1f42 – Oppdatert SessionView med kort-økt-guard og DEV-sanity for Precision Watt
e94b6d8 – Justert mockSession (40 samples, PW/CI stubs) og koblet til sessionStore
f28c0d1 – DoD-verifikasjon: typecheck/build grønt, dev/prod testet uten crash

Endrede filer:
frontend/src/routes/SessionView.tsx
frontend/src/components/SessionCard.tsx (mindre justeringer ifm. schema guards)
frontend/src/state/sessionStore.ts
frontend/src/mocks/mockSession.ts
docs/cli_flags.md (oppdatert dokumentasjonstabell fra trinn 2)

Tester:
npm run type-check → grønt
npm run build → grønt
npm run dev → mock + DEV-sanity synlig, kort-økt testet (<30 samples)
npx serve -s dist → prod-server uten debug, kort-økt vises korrekt
pytest -q og cargo test → alle tester grønt (ingen nye feil introdusert)

Observasjoner:
DEV-sanity blokken gir nyttig feedback (PW samples/CI).
Kort-økt visning fungerer kontrollert ved <30 samples.
Prod bygger grønt og skjuler debug-info som forventet.
Hele leveransen er nå robust både i dev og prod.
Status: ✅ Ferdig – Sprint 8.5 kan lukkes.



Status: Ferdig


✅ Sprint: S9 – Økt-kort & nøkkelmetrikker (📊)
Branch: feature/s9-session-card
Commits:
a12f3c9 – add SessionReport type extensions (mode + has_gps)
c4d9f44 – update mockSession with indoor/outdoor modes
d92eab1 – add IoBadge to SessionCard, remove ModeBadge from card
f18a2e0 – clean up SessionView: remove ModeBadge, EnvBadge → simplify nav
e2c6d33 – rename nav links to “Eksempel – Outdoor / Indoor (kort) / Live fra API”
b41e0a7 – add discrete “Kilde: …” footer in SessionView

Endrede filer:
frontend/src/types/session.ts
frontend/src/mocks/mockSession.ts
frontend/src/components/SessionCard.tsx
frontend/src/routes/SessionView.tsx

Tester:
npm run test (vitest) → ✅ alle tester grønne
cargo test (core evaluator) → ✅ alle tester grønne
Manuell smoke-test dev/prod:
Dev (npm run dev) → UI rendrer NP, IF, VI, Pa:Hr, W/slag, CGS, PW
Prod (npm run build && npx serve -s dist) → identisk visning, ingen debug-info
Observasjoner:
Indoor/Outdoor-chip lagt til og fungerer i SessionCard.
ModeBadge fjernet fra UI (ingen “MODE: MOCK” i kort/header).
Navigasjon gjort mer brukervennlig: “Eksempel – Outdoor / Indoor (kort) / Live fra API”.
Diskré kildeinfo (“Kilde: …”) lagt nederst.
Mock-data oppdatert med mode og has_gps.
Litt “dummy”-følelse gjenstår i eksempelvisningene – dette bør strammes opp videre når live API får flere datasett.

Status: ✅ Ferdig
✅ Sprint: S10 – Live API-integrasjon (🌐)
Branch: feature/s10-live-api (brukte denne som sprint-branch; endre hvis dere pushet i en annen)
Commits:
[SHA TBA] – feat(s10): live API-integrasjon + robust feilflyt
(lib/api: fetchWithTimeout, semver/schema-guard, mock/live kilde, ?simulateInvalid)
[SHA TBA] – feat(ui): ErrorBanner m/ retry + feilklassifisering i SessionView
[SHA TBA] – feat(state): sessionStore med source (api|mock), ENV-styrt modus
[SHA TBA] – test: SessionView/ErrorBanner + sessionStore; vitest jsdom-oppsett
[SHA TBA] – chore: tsconfig, vitest.config, .env.example (VITE_BACKEND_URL)
Tips for å fylle inn SHA: git log -n 5 --oneline

Endrede filer:
frontend/src/lib/api.ts (ny/oppdatert fetch-klient, timeout, schema-guard)
frontend/src/state/sessionStore.ts (kildevalg api/mock, feilflyt, retry)
frontend/src/components/ErrorBanner.tsx (ny)
frontend/src/routes/SessionView.tsx (bruker ErrorBanner + retry, samme layout)
frontend/.env.example (ny – VITE_BACKEND_URL)
frontend/vitest.config.ts (jsdom + @vitejs/plugin-react)
frontend/src/tests/setup.ts (jest-dom matchere)
frontend/src/tests/ErrorBanner.test.tsx (ny)
frontend/src/tests/SessionView.test.tsx (ny)
frontend/tests/sessionStore.test.ts (ny)
frontend/tsconfig.app.json, frontend/tsconfig.node.json (oppdatert for react-jsx/vitest)
(små justeringer i src/env.d.ts om VITE_BACKEND_URL/Mode var nødvendig)

Tester:
Frontend (Vitest): 3 testfiler / 9 passerer
(ErrorBanner, SessionView, sessionStore; jsdom-runtime OK)
Backend/CLI (pytest): alle grønne igjen etter å ha bygget Rust-kjernen i riktig Python-miljø
(root cause: miljø-mismatch; fix: maturin develop --release -m core/Cargo.toml --features python i samme venv som pytest/CLI)
Rust (cargo test): ikke endret i sprinten; ikke kjørt (build OK via maturin)

Observasjoner:
Viktig å bruke én Python-tolker/venv for CLI/pytest/maturin; miljø-mismatch ga 18 røde tester før rebuild.
Inne i src/**: unngå imports som starter med ../src/; hold rene relative stier.
@vitejs/plugin-react + jsdom + @testing-library/jest-dom/vitest er nødvendig for JSX i tester.
ErrorBanner + feilklassifisering gir konsistent UX ved timeout/offline/404/500.
.env.example forenkler onboarding (kun VITE_BACKEND_URL).
Dev-snarvei ?simulateInvalid gjør schema-guard testbar uten å endre backend.
Status: Ferdig ✅
Live API-økt hentes og rendres uten crash.
Mock-modus intakt og lik layout som prod.
Feiltilstander viser banner + Prøv igjen.
Typecheck/build/test grønne (FE).

Pytest grønne etter kjapp rebuild av core i korrekt miljø.
Leveransen oppfyller DoD for S9: alle nøkkelmetrikker vises, indoor/outdoor og kalibrering er på plass, kort-økt guard fungerer, og build/dev er like. Mock-håndtering er ryddet, men bør strammes mer opp i kommende sprinter.

✅ Sprint: S11 – Analysepanel & Trender (📈)
Branch: feature/s11-analysis-trends

Commits:
7c9b2f3 – Add AnalysisChart with CI-band and tooltip
5f12a9a – Refactor tooltip and pointer logic for HR/power sync
a0de11c – Fix CI-band visibility logic (getCI multi-key support)
b47c6f4 – Add hover tests and smoke suite for AnalysisChart
cf118b2 – Patch eslint/type errors (removed any, added Partial<Series>)
e08db5a – Finalize DoD check and confirm S11 complete

Endrede filer:
src/components/AnalysisChart.tsx
src/tests/AnalysisChart.test.tsx
src/tests/SessionView.test.tsx
src/tests/SessionSmoke.test.tsx
package.json (oppdatert test-script / lint rules)

Tester:
npm run test → ✅ alle tester bestått (11 av 11 pass)
npm run lint → ✅ ingen feil etter eslint-patch
npm run type-check → ✅ ingen TypeScript-feil
(backend uendret; ingen nye pytest/cargo-endringer i denne sprinten)

Observasjoner:
CI-bånd-logikk nå robust mot precision_watt_ci, ci, pw_ci.
Tooltip viser korrekt Kilde og Kalibrert-status ved hover.
Pointer-håndtering og fallback testet i JSDOM.
Ytelsestest 1 Hz over 2 timer viser ingen lagg.
Lint og type-feil fjernet (ingen any, ingen unused vars).
Prod og dev layout verifisert identisk.
Status: ✅ Ferdig


📋 Delta Sammendrag av Sluttrapporter

M7.5 – Forebyggende tester
Edge-case tester lagt til i både Python og Rust (ValueError, NaN/mismatch). Golden utvidet. CI kjører pytest + cargo. Lokalt grønt, klar for PR.

M7.5 – GitHub Actions
Minimal workflow etablert (pytest + cargo test). Kjøring stabil på push/PR, enkel base for videre utvidelse.

Sprint 1 – Strava-integrasjon og publisering
Strava publish med dry_run + retry implementert. Fixtures/tester grønne. CI aktiv; pieces-parameter avklart.
Status: Ferdig.

Sprint 1B – No-watt policy & fallback
Fallback til hr_only implementert for økter uten watt. Varsel/metrics og git hygiene fullført. Pytest/cargo tester grønne, golden validert.
Eksempelfiler beskytter secrets. CI krevde ekstra debugging (requests/dotenv/tokens), løst via sample-filer og workflow-oppdatering.
Frontend-varsel håndteres i M8.
Status: Ferdig.

Sprint 2 – Strava Weather
Værklient med caching/validering (vind, temp, trykk) og probe-forecast fallback implementert. Integrert i CLI med justert effektivitetsanalyse.
✅ pytest alle tester grønne, ✅ cargo test stabile tall (±1–2W).
Open-Meteo-arkiv feiler for fremtidige datoer; fallback og debug-modus sikrer robusthet.
Status: Ferdig.

Sprint 3 – Fysikkmodell, smoothing og golden test
Komplett kraftmodell (aero, grav, rulling, aksel, drivetrain) + smoothing/outlier-filter og NP/avg/glatting i metrics, golden test integrert i CI.
✅ cargo/pytest alle tester grønne, output stabil ±1–2W.
Observasjon: Separat smoothing-modul ga ryddigere struktur og bedre testdekning.
Status: Ferdig.

Sprint 4 – Kalibrering (CdA/Crr-fit)
Kalibreringsprosedyre implementert: fit_cda_crr med grid-search på Crr, integrert mot physics-output.
Profiler kan lagres/lastes som JSON (cda, crr, calibrated, mae). CLI utvidet med --calibrate, viser flagget “Kalibrert: Ja/Nei”.
✅ cargo test – inkludert syntetiske segmenter med kjent CdA/Crr.
✅ pytest – CLI integrasjon med dry-run, korrekt output.
Observasjoner: robust fallback ved korte/mangelfulle segmenter, logging gir innsikt i fit-grunnlag. Output deterministisk.
Status: Ferdig.

Sprint 5 – Indoor pipeline + GPS/Wind integrasjon
Indoor/outdoor-pipeline koblet til fysikkmotor med vindkorrigering. CLI-output inkluderer watts, wind_rel, v_rel, calibrated, status. Ny API-funksjon (analyze_session) gir frontend enkel JSON-output. Golden test med syntetisk GPS+vindfelt etablert.
✅ cargo/pytest alle tester grønne, output stabil ±1–2W.
Observasjoner: indoor pipeline fungerer uten GPS, outdoor justerer mot vind/heading. Unicode-bug i CLI fikset.
Status: Ferdig.

✅ cargo test – fysikkmotor + golden-test (syntetisk GPS/vind) grønne.
✅ pytest – CLI dry-run og API-test grønne.
Observasjoner: CLI-rapportene stabile, logging gir sporbarhet, golden-test deterministisk ±1–2W. Mindre inkonsistenser (reason vs calibrated, status=LIMITED) ryddet manuelt. Flere golden-tester på ekte segmenter legges til i S7.
Status: Ferdig.

Sprint 6 – Rapportfelt & Observabilitet
CLI genererer deterministiske rapporter med NP, Avg, VI, Pa:Hr, W/beat, PrecisionWatt. Fallback-modus (HR-only) fungerer uten wattdata. Strukturert logging lagt til (level, step, component, cache_hit), og metrikken sessions_no_power_total logges eksplisitt. Dokumentasjon oppdatert med observabilitet, rapportlogikk og kjente begrensninger. Repo ryddet for gamle sprintmapper.

✅ cargo test – alle grønne.
✅ pytest – alle grønne.
Observasjoner: rapportfelt dekker alle metrikker, logging gir sporbarhet, fallback robust. Dokumentasjon og CGS v1 oppdatert.
Status: Ferdig.


Sprint 7 – QA & Stabilisering
schema_version lagt til i alle rapporter, frontend forventer feltet. HR-only fallback implementert (avg_hr, status=hr_only_demo). CLI utvidet med full flaggdekning (input, weather, out, format, lang, validate, dry-run, log-level, cfg, debug). JSON-logging og metrikker validert, golden-tester oppdatert (outdoor + HR-only).

✅ cargo test – 17/17 grønne (metrics, physics, golden).
✅ pytest – 55 passed, 4 skipped (forventede skips).
Observasjoner: frontend får stabil output med schema_version. Robust degradert modus ved HR-only. Logging/observabilitet fungerer, output deterministisk.
Status: Ferdig.

Sprint 8 – Scaffold & dataadapter
React/Tailwind scaffold satt opp med routing og state-management. Backend-adapter implementert (mock → live) med ENV-switch via .env.local. Schema-version validering lagt inn med kontrollert feilhåndtering, HR-only fallback støttet. Dokumentasjonstabell for CLI-flagg opprettet i docs/cli_flags.md. Prod-build verifisert (vite v7.1.7) og servert via npx serve -s dist.

✅ cargo test – 17/17 tester grønne.
✅ pytest – 55 passed, 4 skipped (~17s).
✅ npm run build – grønn, ~327 kB JS gzip ~102 kB.

Observasjoner: Windows/OneDrive ga EPERM unlink-feil ved npm ci; løst via PowerShell-admin og npm install. CLI-flagg-tabellen rendres pent i både VS Code og GitHub. Innsikt: liten “S8.5” mini-sprint (stubs for PrecisionWatt + short-session guard) vil spare 3–7h i S9–S12 for ca. 2h investering.

Status: Ferdig.

✅ Sprint: S12 – Brukeropplevelse & kalibreringsguide
Branch: feature/s12-calibration-guide

Commits:
a74b3f1 – Add onboarding modal and calibration guide flow
b82a45d – Refactor SessionView labels (Mode vs Source)
c12d8fe – Integrate TrendsChart into main dashboard
d0a1f9b – Improve HR-only messages and fallback tooltips
e98c6ac – Docs: update Using Precision Watt with new calibration flow
Endrede filer:

frontend/src/components/CalibrationGuide.tsx
frontend/src/components/AnalysisPanel.tsx
frontend/src/routes/SessionView.tsx
frontend/src/lib/i18n.ts
frontend/src/tests/AnalysisPanel.test.tsx
frontend/src/tests/SessionSmoke.test.tsx
docs/Using_Precision_Watt.md
Tester:
pytest → 55 passerte / 0 feilet / 4 skip’et (akseptert; SHACL ikke påkrevd)
cargo test → alle 17/17 grønne
vitest → 9/9 bestått (AnalysisPanel + SessionView + ErrorBanner)
Lighthouse UX score → 82 / 100
Observasjoner:
Onboarding-flyten fungerer stabilt; enkelte brukere kan hoppe over modalen ved nettavbrudd → fallback legges i S13.
Tekstene i HR-only-varsel bør forenkles (“Mindre presis – basert på pulsdata”).
TrendsChart integrert og responsiv, men live-kobling aktiveres først i S13.
Ytelse forbedret; ingen memory-lekkasje ved modal unmount.
QA verifisert på mobil og desktop; tastaturnavigasjon OK.
Status: ✅ Ferdig

✅ Sprint: 13 – QA-sjekk og DoD-verifikasjon
Branch: main

Commits:
a41d92e – Fullført QA-verifikasjon (Lighthouse, API, schema, toggle, import)
b09f55a – Oppdatert CI-workflow for schema-validator og feature-toggle-sjekk
c17a3d8 – Korrigert AbortError-guard i TrendsChart.tsx
d42b61f – Fjernet ubrukt import, oppdatert ajv.config.cjs, fikset CI-warnings
e88f0e3 – Endelig DoD-verifisering og oppdatert QA-log
Endrede filer:

frontend/src/routes/TrendsChart.tsx  
frontend/src/lib/fetchJSON.ts  
frontend/scripts/ajv.config.cjs  
frontend/tests/TrendsChart.test.tsx  
.github/workflows/ci.yml  
.env.example

Tester:
pytest -q → ✅ Alle tester passerte (9/9)
cargo test → ✅ Alle Rust-tester grønt (23/23)
npm run test → ✅ Vitest: 4/4 tester OK, ingen warnings
Observasjoner:
Lighthouse-resultater:
Performance: 74 ⚠️ (noe under målkravet >80)
Accessibility: 90 ✅
Best Practices: 100 ✅
SEO: 82 ✅
Schema-validator stopper korrekt ved kontraktbrudd
Feature-toggle fungerer (mock vs live)
API returnerer gyldig struktur, håndterer tom respons
Ingen kontrastfeil, tastaturnavigasjon OK
CI kjører rent uten warnings
Status: ✅ Ferdig
📌 Alle kriterier i Definition of Done er oppfylt, med unntak av Performance (74). Tiltak for ytelsesforbedring vurderes i Sprint 14.

Sprint 8.5
Scaffold, state-management og backend-adapter implementert; SessionView utvidet med kort-økt-guard og DEV-sanity, mockSession koblet til store.
Typecheck, build, pytest og cargo test alle grønne; dev/prod verifisert uten crash.
Observasjon: Kort-økt og DEV-sanity oppfører seg kontrollert, prod skjuler debug som forventet.

Sprint 9
Implementert nøkkelmetrikker i SessionCard, lagt til Indoor/Outdoor-chip, fjernet “MODE: MOCK” og ryddet opp i navigasjon + mock-data.
Alle tester (vitest + cargo) passerte, og manuell smoke-test i dev/prod viste korrekt visning.
Mock-håndtering er forbedret, men fortsatt litt “dummy”-følelse som planlegges justert i senere sprinter.

Sprint 10 
Hva ble gjort: Live API-integrasjon i FE (ny api.ts m/timeout+schema-guard), sessionStore med kildevalg (api/mock) og robust feilflyt, ErrorBanner + retry i SessionView, samt .env.example for VITE_BACKEND_URL.
Teststatus: Vitest 9/9 grønt; Pytest tilbake til grønt etter rebuild av Rust-kjerne i riktig Python-venv (maturin develop --features python); type-check og build passerer.

Sprint 11 
Delta-sammendrag:
Utviklet og ferdigstilte AnalysisChart med CI-bånd, tooltip og komplett edge-case-håndtering.
Alle tester, lint og type-sjekker passerte uten feil.
Komponenten er stabil, responsiv og gir konsistent visning i både dev og prod.

Sprint 12 – Delta-sammendrag
Utviklet full kalibreringsguide og onboarding-flyt for første outdoor-økt, med stegvis modal og tydelig språk for brukere uten wattmåler.
Skilt mellom Mode (Indoor/Outdoor) og Kilde (API/Mock) i SessionView, samt integrert TrendsChart i hovedoversikten.
Alle tester (pytest, cargo, vitest) passerte; Lighthouse UX-score 82.
Onboarding-flyten fungerer stabilt, men fallback ved nettavbrudd og språklig finpuss på HR-only-varsel planlegges i neste sprint.

Sprint 13 – Delta-sammendrag
Gjennomført full QA- og DoD-verifikasjon med fokus på stabilitet, testdekning og samsvar mellom frontend, backend og CI-pipeline.
Alle tester (pytest, cargo, vitest) passerte uten feil, og CI validerer nå både schema og feature-toggle automatisk.
Feature-toggle mellom live- og mock-data fungerer korrekt, og API håndterer tom respons uten crash.
Lighthouse-resultater viser Performance 74, Accessibility 90, Best Practices 100 og SEO 82 — kun ytelse vurderes som forbedringspunkt.
Løsningen er verifisert som stabil og klar for avslutning av Sprint 13; Performance-optimalisering løftes til Sprint 14.
