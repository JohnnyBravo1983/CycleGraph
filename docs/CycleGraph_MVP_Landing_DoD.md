🚀 CycleGraph — MVP Landing & Final DoD
S14 Summary + Plan for S14.5 – S15
🎯 Overordnet mål

Sprint 14 markerer ferdigstilling av backend- og Strava-integrasjon, samt at hele kjeden fra analyse → persistens → publisering nå fungerer helhetlig.
Dette danner grunnlaget for kommende Minisprint 14.5 (manuell Precision Watt-testing) og Sprint 15 (innholdsmigrering og MVP-lansering).

🧩 Teknisk helhet – “CycleGraph-hjernen”
Lag	Rolle	Status (S14)
🧠 Core (Rust via PyO3)	Beregning av NP, IF, VI, Precision Watt, CGS m.m.	✅ stabil
🧰 CLI (Python)	Parser, analyse, caching, persistens, Strava-publisering	✅ ferdig
🌐 Frontend (React/Tailwind)	Presentasjon og brukeropplevelse	⚙️ aktiv (flyttes i S15)

CycleGraph-hjernen (CLI-laget) fungerer nå som styrings- og sannhetslag mellom Rust-kjernen og frontend-laget.

🔑 Strava-autorisering (Sprint 14 kjerneleveranse)

Status: ✅ Fullført

Beskrivelse:

Miljøvariabler satt og testet (STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_AUTH_CODE).

Tokenutveksling mot https://www.strava.com/oauth/token verifisert.

data/strava_tokens.json genereres og holdes utenfor Git.

CLI-publisering testet med fem økter (ride1–5) → alle returnerte state = done.

publish_hash og publish_time settes automatisk.

Feilhåndtering for 401/403 og fallback til pending ✅

🔒 Sikkerhet & Git-hygiene

.gitignore oppdatert for å skjerme bruker- og token-data:

.tmp_*.py
data/sessions/*.json
data/strava_tokens.json
data/activities.json
data/streams/
data/compat/
data/*.ttl
data/*.parquet
output/
.env


→ ingen sensitive filer i repo.
→ repro-sikker lokal utvikling.

🧪 Testing og validering

pytest-suite ✅ grønn.

Validerte CLI-kommandoer:

cyclegraph analyze session --input data/imports/csv/*.csv

cyclegraph sessions list

cyclegraph publish run <ride>

Strava-publisering ✅ 5/5 suksess.
session_storage.py refaktorert for atomisk I/O og dataintegritet.

⚙️ Strategisk designvalg

Full reproduksjon fra rådata → ingen manuell patching

CLI fungerer som “truth layer” mellom backend og UI

Fokus på enkel redeploy og minimal konfig

Arkitektur klargjort for fremtidig deploy i Azure / Kubernetes

Frontend-visning (SessionView, SessionCard og TrendsChart) fullført og testet med mock-data → backend-integrasjon kommer i S15

🏁 Definition of Done – Sprint 14

Rust + Python-core integrert og testet

CLI-analyse, caching og persistens stabil

Strava-autorisering og publisering fullført

DoD-logging i data/sessions/*.json

.gitignore / .env-policy ferdig

Auto-publish-hook i analyze_session() → S14.5

Frontend-visning ferdig og testet med mock-data (SessionView → S15 backend-kobling)

Dokumentert “Launch Playbook” (README + MVP brief) → S15

🧠 Plan fremover
⚡ S14.5 — Precision Watt Testing (Manuell validering)

Mål: Felt- og lab-test av Precision Watt-algoritmen under reelle sykkeløkter.
Oppgaver:

Importere egne økter fra Strava (manuelt eller via API)

Sammenligne precision_watt vs Strava “avg power”

Finjustere CI-intervall og algoritmeparametere

✅ DoD: Sammenligningsrapport (JSON + graf) med avvik < ± 5 %

🌐 S15 — Minisprint: Full innholdsmigrering → cyclegraph.app

Mål: Flytte alt innhold og statiske ressurser fra eksisterende cycle-graph-landing (Vercel) til hovedprosjektet, og klargjøre for offisiell MVP-lansering.

Oppgaver:

Migrer alt innhold fra landing/ → frontend/public eller app/landing

Samle språk-tekstene (NO/EN) i felles i18n-struktur

Re-konfigurer Vercel deploy slik at cyclegraph.app bygger fra main

Test DNS, favicon, meta-tags (Open Graph)

Valider mobil/desktop-layout (Chrome, Safari, Edge)

Kjør Lighthouse > 90 (SEO / Accessibility)

Opprett docs/deployment-log.md (migreringsrapport)

✅ DoD:

cyclegraph.app og www.cyclegraph.app viser ny side

Deploy via git push → Vercel (main)

Språk-toggle og layout fungerer

Ingen 404-feil

Lighthouse SEO > 90

💾 Status: Trinn 6 (frontend-integrasjon og tests) ✅ Fullført.
Neste steg: Trinn 7 → backend-tilkobling og end-to-end verifisering før Precision Watt field-testing.
