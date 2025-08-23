
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
- **M7.5 – Backend forfining (CGS v1.1, explain, flere tester) (Planlagt)
- **M8** – Webdemo & visualisering (**Ikke startet**)  
- **M9** – MVP-forberedelse & testing (**Ikke startet**)  
- **M10** – Feedback-innsamling & justeringer (**Ikke startet**)  
- **M11** – Demo-lansering & markedsføring (**Ikke startet**)  
- **M12** – Kommersialisering & skalering (**Ikke startet**)  

---



## Statusoversikt

| Dato       | M    | Milepæl                                           | Status      | Beskrivelse |
|------------|------|----------------------------------------------------|-------------|-------------|
| 2025-08-07 | M1   | Opprette prosjektstruktur                          | Ferdig      | Mappeoppsett (core, cli, data, docs, shapes), initialisert GitHub-repo med README, lisens og .gitignore. |
| 2025-08-08 | M2   | Sette opp Rust-core med pyo3                       | Ferdig      | Cargo.toml konfigurert med pyo3, første testfunksjon lagt inn og bekreftet bygging. |
| 2025-08-09 | M2   | Installere maturin og teste kobling til Python     | Ferdig      | Maturin-build testet, Python-import av Rust-modul bekreftet. |
| 2025-08-09 | M2   | Lage analysefunksjon for effektivitet (Rust)       | Ferdig      | Beregning av snitteffektivitet, øktstatus og per-punkt-data implementert. |
| 2025-08-10 | M3   | Sette opp Python CLI (analyze.py)                  | Ferdig      | CLI med argparse, integrert Rust-funksjon, testet full CSV → Rust → output-flyt. |
| 2025-08-11 | M4   | Lage første dummydata (CSV + RDF)                  | Ferdig      | Opprettet sample_data med testfiler for CLI og validering. |
| 2025-08-12 | M3   | Kjøre CLI → Rust → output-flyt                     | Ferdig      | Verifisert analyse med dummydata, konsistent output. |
| 2025-08-15 | M5   | Implementere SHACL-validering                      | Ferdig      | Lagt til SHACL-shapes og Python-script for RDF-validering, testet med dummydata. |
| 2025-08-16 | M5   | Integrere validering i CLI                         | Ferdig      | CLI-utvidelse med valideringsopsjon og terminaloutput. |
| 2025-08-18 | M6   | Opprette Strava API-tilgang og testimport          | Ferdig      | OAuth/scopes ok, token lagres sikkert; første testimport verifisert. |
| 2025-08-19 | M6   | Lese Strava-data og konvertere til CSV/RDF         | Ferdig      | Streams→CSV per aktivitet + CSV→TTL, robust feilhåndtering. |
| 2025-08-20 | M6   | Kjøre CLI-analyse på Strava-økter                  | Ferdig      | Analyze kjørt på ≥3 ekte økter med HR+watts; output skrevet til rapporter. |
| 2025-08-20 | M7   | Analysefunksjoner                                  | Ferdig      | CLI/analyze støtter --publish-to-strava (--dry-run, --lang). Formatter håndterer trimming, språk og fallbacks. Strava-klient med auto-refresh og kommentar→description-fallback. Baseline, badges og trend ferdig. Live publisering bekreftet. |
| 2025-08-21 | M7.5 | Kickoff backend forfining (CGS v1.1, explain)      | Påbegynt    | Sanert DoD i repo, sample-konfig, plan for tuning/baseline/degrade, flere golden/sanity-tester. |


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
- ⚠️ Kjent: enkelte data/streams/*.csv mangler gyldige samples (påvirker ikke publisering, ryddes senere).  

---

## Oppdateringsrutine
Når en milepæl er ferdig:  
1. Oppdater statusoversikten.  
2. Marker milepælstatus i planen (M1–M12).  
3. Legg til kort milepælsrapport (✅/⚠️).  
4. Legg sanert DoD i docs/milestones for hver milepæl (ingen sensitive tall).
5. Bruk sample-konfig i repo; hold ekte konfig privat og .gitignore den.
6. Commit i repoet.  