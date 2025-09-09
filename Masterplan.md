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
- **M7.6** – Watt-engine v1 (værdata, sykkeltype, perf-tests) (**Planlagt**)  
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
---

## Milepælsrapporter

### M6 – Strava-integrasjon (API & import) – status per 2025-08-12
- ✅ OAuth & tokens på plass (redirect/scopes, .env).  
- ✅ Refresh + lagring av rotert refresh_token.  
- ✅ Aktiviteter med paging + --since + inkrementell state.  
- ✅ Streams→CSV (time,hr,watts,moving,altitude) og CSV→TTL.  
- ✅ Robust feilhåndtering (401/403/429/5xx).  
- ✅ Analyze kjørt på ≥3 ekte Ride-økter; rapporter skrevet.  

### M7 – Analysefunksjoner – status per 2025-08-21
- ✅ Formatter (strava_publish.py) med språkvalg, trimming, fallbacks.  
- ✅ CLI-integrasjon (--publish-to-strava, --dry-run, --lang).  
- ✅ Baseline (28d, ±25 % varighet) + badges.  
- ✅ Strava-klient (auto refresh, headers fix, fallback for kommentarer).  
- ✅ Live publisering bekreftet.  
- ✅ Tester (pytest) grønne.  
- ⚠️ Kjent: enkelte data/streams/*.csv mangler gyldige samples (påvirker ikke publisering).  

### M7.5 – Backend-forfining (CGS v1.1, explain) – status per 2025-09-09
- ✅ CI (GitHub Actions) kjører: build PyO3, cargo test (inkl. golden), system_test.sh.  
- ✅ Systemtest grønn (0–7), perf (kald start) ~0.73s.  
- ⏭️ SHACL/Strava-mock hoppet (ingen .ttl / ingen Pulled:).  
- 🔧 Fikser: ryddet cmd_session, continue-fix, lagt til `mod metrics;` (løste E0432), verifisert deterministisk output.  
- 🧪 Plan: pytest for `_analyze_session_bridge()` (tomme arrays → ValueError), Rust golden for `w_per_beat()` (NaN/null/mismatch).  

---

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