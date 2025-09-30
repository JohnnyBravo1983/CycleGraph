CycleGraph er et analyseverktøy for syklister som henter treningsdata fra Strava og gir innsikt i watt/puls-effektivitet, utvikling over tid og prestasjonsanalyse.  
Løsningen bygges med en Rust-basert kjerne (via pyo3) for høy ytelse, og et Python-grensesnitt for fleksibilitet.  
Prosjektet utvikles modulært for skalerbarhet og fremtidig drift i skyen (Azure/Kubernetes).  
Denne masterplanen beskriver milepæler, tidslinje og leveranser frem mot første demo-lansering 1. september 2025.

---

## Milepæl-plan (M1–M12)

- **M1** – Prosjektstruktur & repo (**Ferdig**)  
- **M2** – Rust-core med pyo3 (**Ferdig**)  
- **M3** – CLI-oppsett & dataflyt (**Ferdig**)  
- **M4** – Dummydata & testkjøring (**Ferdig**)  
- **M5** – SHACL-validering (**Ferdig**)  
- **M6** – Strava-integrasjon (API & import) (**Ferdig**)  
- **M7** – Analysefunksjoner (effektivitet, treningsscore) (**Ferdig**)  
- **M7.5** – Backend-forfining (CGS v1.1, explain, tester) (**Ferdig**)  
- **M7.6** – Watt-engine v1 (værdata, sykkeltype, perf-tests) (**Påbegynt**) 
- **M8** – Demo/MVP med verdi (**Planlagt**)  
- **M9** – MVP-forberedelse & skyoppsett (Azure/Kubernetes, CI/CD) (**Ikke startet**)  
- **M10** – Feedback-innsamling & justeringer (**Ikke startet**)  
- **M11** – Markedsdemo & kommunikasjon (**Ikke startet**)  
- **M12** – Kommersialisering & skalering (**Ikke startet**)  

---

## Statusoversikt

| Dato       | M    | Milepæl                               | Status   | Beskrivelse                                                                 |
|------------|------|---------------------------------------|----------|-----------------------------------------------------------------------------|
| 2025-08-07 | M1   | Opprette prosjektstruktur              | Ferdig   | Mappeoppsett (core, cli, data, docs, shapes), initialisert GitHub-repo.     |
| 2025-08-08 | M2   | Rust-core med pyo3                     | Ferdig   | Cargo.toml konfigurert med pyo3, første funksjon lagt inn, bygget OK.       |
| 2025-08-09 | M2   | Maturin + Python-import                | Ferdig   | Bygget wheel, testet import i Python.                                       |
| 2025-08-10 | M3   | Python CLI (analyze.py)                | Ferdig   | CLI med argparse, Rust-funksjon, full CSV → Rust → output-flyt.             |
| 2025-08-11 | M4   | Dummydata (CSV + RDF)                  | Ferdig   | Sample_data med testfiler for CLI og validering.                            |
| 2025-08-12 | M3   | CLI → Rust → output-flyt               | Ferdig   | Verifisert analyse med dummydata, konsistent output.                        |
| 2025-08-15 | M5   | SHACL-validering                       | Ferdig   | SHACL-shapes lagt til, Python-script testet OK med dummydata.               |
| 2025-08-16 | M5   | Integrere validering i CLI             | Ferdig   | CLI-utvidelse med valideringsopsjon og terminaloutput.                      |
| 2025-08-18 | M6   | Strava API-tilgang + testimport        | Ferdig   | OAuth/scopes OK, tokens lagres sikkert, første testimport.                  |
| 2025-08-19 | M6   | Strava-data til CSV/RDF                | Ferdig   | Streams→CSV + CSV→TTL, robust feilhåndtering.                               |
| 2025-08-20 | M6   | CLI-analyse på Strava-økter            | Ferdig   | ≥3 ekte økter analysert, rapporter skrevet.                                 |
| 2025-08-20 | M7   | Analysefunksjoner                      | Ferdig   | CGS v1, badges, baseline, Strava publish (dry-run/lang), live publisering.  |
| 2025-09-09 | M7.5 | Backend-forfining (CGS v1.1, explain)  | Ferdig   | CI satt opp, systemtest grønn, perf ~0.73s, fixes gjort, forebyggende tester planlagt. |
| 2025-09-09 | M7.5 | Forebyggende tester                    | Ferdig   | Pytest ValueError for `_analyze_session_bridge`, Rust golden-test for `w_per_beat` (NaN/null/mismatch). Alle tester grønne. |
| 2025-09-09 | M7.5 | GitHub Actions (basic CI)              | Ferdig   | Minimal workflow: `pytest -q` og `cargo test --tests -q` kjøres på push/PR. |---
| 2025-09-10 | S1   | Strava Fetch & modusdeteksjon (S1)     | Ferdig   | Auto-modus med trainer/sport_type/device_watts, CLI-flag --mode, JSON-ruting. |
| 2025-09-12 | S1B  | No-watt fallback & policy (S1B)        | Ferdig   | Fallback til hr_only implementert, structured WARN, metrics lagt inn, tester grønne.
| 2025-09-16 | S2   | Vær & profiler                         | Ferdig   | Værklient med caching/validering (vind, temp, trykk), profilsettings og CLI-integrasjon med justert effektivitet. Tester grønne, fallback og debug-modus sikrer robusthet.
| 2025-09-19 | S3   | Fysikkmotor                            | Ferdig   | Kraftmodell (gravitasjon, rulling, aero, akselerasjon, drivverkstap), smoothing/outlier-kutt, NP/avg/glatting i CLI. Golden test integrert i CI (±1–2W stabilt). Alle tester grønne. |
| 2025-09-23 | S4   | Kalibrering                            | Ferdig   | CdA/Crr-fit med MAE ≤10 %, lagring av profil (profile.json), CLI-integrasjon med flagg --calibrate. Tester grønne i cargo/pytest. |
| 2025-09-25 | S5   | Indoor pipeline + GPS/Wind integrasjon | Ferdig   | Vindkorrigert fysikkmotor koblet på indoor/outdoor-pipeline. CLI-output viser watts, wind_rel, v_rel, calibrated, status. Bonus: backend-API `analyze_session()` for frontend (M8). Tester grønne i cargo/pytest. |
| 2025-09-26 | S6   | CLI/Reports & observabilitet	     | Ferdig 	| Rapportfelt (NP, Avg, VI, Pa:Hr, W/beat, PrecisionWatt ± usikkerhet), strukturert JSON-logging, metrics for no-watt, docs. Tester grønne i cargo/pytest. Små inkonsistenser ryddet manuelt, golden stabil ±1–2 W.
| 2025-09-29 | S7   | QA & Hardening                         | Ferdig   | Schema-versionering (v0.7.0) og avg_hr lagt til i CLI/API-output, falsy-felter beholdes. Golden-datasett utvidet til ≥30 samples. Edge-case-tester (vær, GPS-drift, null HR, korte økter) implementert, HR-only plausibilitet med fallback. Robust JSON-uttrekk i tester håndterer stdout-støy. CGS konsumerer nye felter uten regressjoner. Pytest 55 passert / 4 skipped (akseptert), cargo test alle grønne. |
| 2025-09-30 | S8   | Scaffold & dataadapter                 | Ferdig   | React/Tailwind scaffold med routing og state-management. Backend-adapter (mock↔live) med ENV-switch. Schema-version validering og HR-only fallback lagt inn. CLI-flagg-tabell dokumentert i docs. Prod-build testet via `npx serve -s dist`. Tester grønne (pytest 55 passert/4 skipped, cargo 17/17). Innsikt: Mini-sprint 8.5 (stubs + short-session guard) planlagt før S9 for å redusere total tid. |
| 2025-10-01 | S8.5 | Mini-sprint: Precision Watt stubs + short-session guard | Ferdig | Utvidet `SessionReport` med PW/CI/stubs, oppdatert `mockSession`, lagt til DEV-sanity (PW/CI counts) og short-session guard. Prod-serve verifisert med `npx serve -s dist`. Besparelse 3–7h i kommende S9–S12. |

## Milepælsrapporter Status Pr 23.09.2025

### M6 – Strava-integrasjon (API & import) – status per 2025-08-12 Ferdig
- ✅ OAuth & tokens på plass (redirect/scopes, .env).  
- ✅ Refresh + lagring av rotert refresh_token.  
- ✅ Aktiviteter med paging + --since + inkrementell state.  
- ✅ Streams→CSV (time,hr,watts,moving,altitude) og CSV→TTL.  
- ✅ Robust feilhåndtering (401/403/429/5xx).  
- ✅ Analyze kjørt på ≥3 ekte Ride-økter; rapporter skrevet.  

### M7 – Analysefunksjoner – status per 2025-08-21 Ferdig
- ✅ Formatter (strava_publish.py) med språkvalg, trimming, fallbacks.  
- ✅ CLI-integrasjon (--publish-to-strava, --dry-run, --lang).  
- ✅ Baseline (28d, ±25 % varighet) + badges.  
- ✅ Strava-klient (auto refresh, headers fix, fallback for kommentarer).  
- ✅ Live publisering bekreftet.  
- ✅ Tester (pytest) grønne.  
- ⚠️ Kjent: enkelte data/streams/*.csv mangler gyldige samples (påvirker ikke publisering).  

 ### M7.5 – Backend-forfining (CGS v1.1, explain) – status per 2025-09-09 Ferdig
- ✅ Systemtest grønn (0–7), perf (kald start) ~0.73s.  
- ⏭️ SHACL/Strava-mock hoppet (ingen .ttl / ingen Pulled:).  
- ✅ Forebyggende tester:  
  - Pytest for `_analyze_session_bridge()` (tomme arrays → ValueError).  
  - Rust golden for `w_per_beat()` (NaN/null/mismatch).  
  - Alle tester grønne (pytest + cargo test).  

### M7.5 – GitHub Actions (basic CI) – status per 2025-09-09 Ferdig
- ✅ Minimal workflow konfigurert i `.github/workflows/ci.yml`.  
- ✅ Kjører `pytest -q` og `cargo test --tests -q` på push/PR.  
- ✅ Første kjøring verifisert grønn på GitHub.  
- ⏭️ Kan utvides senere med systemtest og golden-sjekker.

### M7.6 – Watt-engine v1 & Precision Watt – status per 2025-09-10 Ferdig
- ✅ Sprint S1 – Strava Fetch & modusdeteksjon ferdig:
  - Auto-modus basert på `trainer`, `sport_type`, `device_watts`.
  - CLI-flag `--mode roller|outdoor` overstyrer auto.
  - JSON-output rutes til korrekt pipeline (indoor/outdoor).
  - Tester: pytest + cargo test grønne.
- ⚠️ Funn: Enkelte Strava-økter mangler watt (`device_watts=False`) → policy nødvendig.
- 🔜 Sprint S1B – No-watt fallback & policy planlagt:
  - Backend: rute til `hr_only` pipeline, structured WARN-logg.
  - Frontend (senere): varsel “Ingen effekt-data registrert”.
  - Metrics: `sessions_no_power_total`, `sessions_device_watts_false_total`.
- ✅ Backend: ruter økter uten watt eller device_watts=False til hr_only pipeline.
- ✅ Logging: structured WARN med no_power_reason.
- ✅ Metrics: sessions_no_power_total og sessions_device_watts_false_total.
- ✅ Tester: pytest + cargo grønne, golden validert.
- ✅ Git hygiene: eksempelfiler lagt til, secrets/state ignorert.
- ⏭️ Frontend-varsel kommer i M8.

“CI-lærdom: abi3 fjernet libpython-avhengighet; korrigert core/ wd; la til debug-step for linker.”

M7.6 – Sprint 2 – Vær & profiler – status per 2025-09-16 Ferdig
✅ Værklient: vind, temp, trykk med validering og caching per (lat,lon,timestamp). Fallback via probe-forecast aktivert.
✅ Profilsettings: total vekt, sykkeltype og Crr-preset med defaults og estimat=true. Persist i enkel JSON/kv-store.
✅ CLI-integrasjon: justert effektivitetsanalyse basert på værkontekst. Moduler splittet til efficiency.py og parser.py.
✅ Tester: pytest grønne. cargo test stabile tall (±1–2 W). DoD oppfylt: ≥95 % cache-hit ved rekjøring av samme økt.
🔎 Observasjoner: Open-Meteo archive feiler for fremtidige datoer; fallback + debug-modus gir robusthet og transparens.
🧩 CI: sanity-test (test_strava_client.py) hoppes over når publiseringsflyt ikke er berørt.
📝 Endringer: cli/find_valid_weather.py, cli/fetch_weather.py, cli/weather_client_mock.py, cli/weather_metrics.py, cli/diagnose_data.py,
 tools/find_valid_weather.py, tools/filter_valid_rows.py, data/session_2025-09-16_weather.json, samt modul-splitt.
ℹ️ Notater: cache-metrics i metrics.rs foreløpig kommentert. abi3-py38 fjernet pga linking; vurderes ved wheel-distribusjon.

S3 – Fysikkmotor – status per 2025-09-19 Ferdig
✅ Kraftmodell implementert: gravitasjon, rulling (Crr), aero (CdA), akselerasjon og drivverkstap.
✅ Høyde-smoothing flyttet til egen modul (smoothing.rs) med outlier-kutt for stopp/sving.
✅ Metrics: sample-watt, 5 s glatting, NP og avg beregnes og vises i CLI.
✅ Golden test på syntetisk segment (flat, bakke, varierende vind) inkludert i CI, stabil output ±1–2 W, NP/avg ±1 W.
✅ Tester: cargo test dekker alle kraftkomponenter, pytest verifiserer CLI-integrasjon; begge grønne.
🔎 Observasjoner: struktur ryddigere med egen smoothing-modul; edge-case tester gir bedre dekning; lokal Pylance-feil måtte fikses manuelt.
📝 Endringer: core/src/physics.rs, core/src/lib.rs, core/src/metrics.rs, core/src/smoothing.rs, cli/analyze.py, tests/test_analyze_session.py, tests/test_physics.rs, .github/workflows/ci.yml.
ℹ️ Notater: deterministisk output etablert som baseline; golden-toleranser (±1–2 W) nå en del av dynamisk DoD.


S4 – Kalibrering – status per 2025-09-23 Ferdig
✅ Kalibreringsprosedyre etablert: segment 5–8 min, stigning 3–6 %.  
✅ Algoritme: fit_cda_crr med grid-search på Crr, CdA foreløpig konstant (0.30).  
✅ Output: MAE ≤10 % mot powermeter på testsegmenter, flagg “calibrated: Ja/Nei” i CLI.  
✅ Persistens: profile.json oppdateres med cda, crr, calibrated, calibration_mae.  
✅ CLI-integrasjon: nytt flagg `--calibrate`, kjøring returnerer kalibreringsresultat og oppdatert profil.  
✅ Tester: cargo test (syntetiske segmenter, profilpersistens) og pytest (CLI dry-run) grønne.  
🔎 Observasjoner: CdA foreløpig statisk, planlagt dynamisk fit senere. Input-validering gir robuste feilmeldinger ved mismatch.  
📝 Endringer: core/src/calibration.rs (ny), core/src/storage.rs, core/src/lib.rs, cli/analyze.py, tests/test_calibration.rs, tests/test_calib_storage.rs.  
ℹ️ Notater: smoothing aktivert for reproduserbarhet; golden-tester viser stabil output. CLI håndterer mislykket fit uten crash (reason=“fit_failed”).  


5 – Indoor pipeline + GPS/Wind integrasjon – status per 2025-09-25 Ferdig
✅ Vindkorrigert fysikkmotor koblet til indoor/outdoor-pipeline (CLI ruter automatisk).
✅ CLI-output utvidet med `watts`, `wind_rel`, `v_rel`, `calibrated`, `status`.
✅ Indoor-modus: bruker `device_watts` direkte når tilgjengelig.
✅ Outdoor-modus: bruker GPS-posisjon + heading og værdata for vindkorrigering.
✅ Robust fallback: CSV-lesing normaliserer samples hvis input er ufullstendig.
✅ Tester: `cargo test` og `pytest` grønne (inkl. golden-test med syntetisk GPS+vind).
✅ Bonus: Nytt Python-API `analyze_session()` (cli/session_api.py) eksponert for frontend (M8).
🔎 Observasjoner: små inkonsistenser (reason vs calibrated, status=LIMITED) ryddet opp i CLI etter kalibrering.
📝 Endringer: core/src/physics.rs, core/src/lib.rs, core/src/models.rs, core/src/calibration.rs, cli/session.py, cli/analyze.py, cli/session_api.py, tests/test_api.py, tests/test_golden.py, tests/test_cli.py.
ℹ️ Notater: API gjør frontend-integrasjon enklere i Sprint 8 (UI scaffolding), da backend kan kalles direkte.

S6 – CLI/Reports & observabilitet – status per 2025-09-26 Ferdig
✅ Rapportfelt: NP, Avg, VI, Pa:Hr, W/beat, PrecisionWatt ± usikkerhet i CLI/JSON.
✅ Strukturert JSON-logging (level, step, duration_ms, cache_hit) med --log-level + LOG_LEVEL.
✅ Observability-metrikk: sessions_no_power_total.
✅ Docs: “How it works” + “Known limits” oppdatert for nye felter/flows.
✅ Tester: cargo test -q (fysikk + golden syntetisk GPS/vind) grønne; pytest -q (CLI dry-run + API) grønne.
🔎 Observasjoner: mindre inkonsistenser (reason vs calibrated, status=LIMITED) ryddet i CLI; golden deterministisk ±1–2 W; logging gir god sporbarhet.

S7 – QA & Hardening – status per 2025-09-29 Ferdig
✅ Schema-versionering (schema_version = "0.7.0") lagt til i CLI/API-output.
✅ avg_hr normaliseres og beholdes i både filer og CLI-stdout.
✅ Falsy-felter (f.eks. calibrated=False) beholdes i output.
✅ Golden-datasett (indoor, outdoor, hr-only) utvidet til ≥30 samples med plausibel variasjon.
✅ Edge-case-tester lagt til (manglende vær, GPS-drift, null HR, korte økter) – håndteres kontrollert uten crash.
✅ HR-only plausibilitet sikret via fallback-logikk.
✅ Robust JSON-uttrekk i tester håndterer stdout-støy (debug-linjer).
✅ Tester: cargo test -q alle grønne; pytest -q 55 passert / 4 skipped (akseptert).

S8 – Scaffold & dataadapter – status per 2025-09-30 Ferdig
✅ React/Tailwind scaffold opprettet med routing og state-management.
✅ Backend-adapter implementert: mock ↔ live via .env.local (VITE_BACKEND_MODE, VITE_BACKEND_URL).
✅ Schema-version validering lagt til i frontend (schema.ts), med kontrollert feilkort ved ugyldig/manglende versjon.
✅ HR-only fallback støttet i SessionView (watts=null → infoboks, ingen crash).
✅ CLI-flagg-tabell opprettet i docs/cli_flags.md (navn, type, default, eksempel, beskrivelse).
✅ Prod-build verifisert: npm run build grønn (vite v7.1.7, ~327 kB JS gzip ~102 kB).
✅ Tester: cargo test 17/17 grønne; pytest 55 passert / 4 skipped (akseptert).

S8.5 – Mini-sprint: Precision Watt stubs + short-session guard – status per 2025-10-01 Ferdig
✅ SessionReport utvidet med nye felter: precision_watt, precision_watt_ci, sources, cda, crr, reason.
✅ mockSession oppdatert med 40 samples (PW og CI-stubs) for å validere DEV-sanity og unngå kort-økt.
✅ DEV-sanity lagt inn i SessionView: viser “PW samples: N, CI: M” kun når import.meta.env.DEV === true.
✅ Kort-økt guard implementert (<30 samples): viser kontrollert melding (“Kort økt – viser begrenset visning”), ingen crash.
✅ Prod-build verifisert (npx serve -s dist): debug-info skjules, kort-økt vises korrekt, ingen feil.
✅ Tester: npm run type-check og npm run build grønne; npm run dev og npx serve -s dist testet OK. Eksisterende tester (cargo/pytest) fortsatt grønne.
✅ Effekt: Ca. 2–2.25h brukt, men gir 3–7h besparelse i S9–S12 ved at PW-stubs og kort-økt-håndtering er etablert tidlig.



## Oppdateringsrutine
Når en milepæl eller oppgave er ferdig:  
1. Oppdater **Dynamisk DoD & Backlog** først (flytt fra Planlagt → Påbegynt → Ferdig).  
2. Synkroniser **Masterplanen**:  
   - Oppdater statusoversikten.  
   - Marker milepælstatus i planen (M1–M12).  
   - Legg til kort milepælsrapport (✅/⚠️).  
3. Lagre en sanert kopi av DoD-detaljene i `docs/milestones/` (ingen sensitive tall).  
4. Bruk sample-konfig i repo; hold ekte konfig privat og `.gitignore`-den.  
5. Commit og push endringene.  