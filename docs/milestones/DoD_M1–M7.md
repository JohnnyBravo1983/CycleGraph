# Definition of Done — M1–M6 (sanert)
*Oppsummering av hva som måtte være oppfylt for å kalle hver milepæl ferdig. Ikke-sensitive, høynivå punkter.*

Sist oppdatert: 2025-08-21

---

## M1 — Prosjektstruktur & repo (Ferdig)
- Standard repo-oppsett: `core/`, `cli/`, `docs/`, `data/`, `shapes/`, `tests/`.
- Init GitHub-repo (README, lisens, .gitignore).
- Bygg/kjørbare grunnkommandoer dokumentert i README (Rust/Python).
- CI eller lokal “quick check”: `cargo check` og enkel Python-kall fungerer.

## M2 — Rust-core med PyO3 (Ferdig)
- Cargo.toml satt opp med PyO3 av riktig versjon.
- Minst én eksponert Rust-funksjon bundet til Python (importerbar i Python).
- `cargo test` (grunnleggende) og “import i Python” fungerer lokalt.
- Kodekommentarer: hvor core-API lever og hvordan bygge.

## M3 — CLI-oppsett & dataflyt (Ferdig)
- `cli/analyze.py` kjører ende-til-ende mot core (Rust) med argparse-flagg.
- I/O-kontrakt: leser CSV/streams, skriver rapport/JSON til `output/`.
- Grunnleggende feilhåndtering (fil mangler, feil format) med tydelige feilmeldinger.
- “Happy path” demonstrert på sample data.

## M4 — Dummydata & testkjøring (Ferdig)
- Dummy/samples tilgjengelig i repo (ikke sensitive).
- Kjøreeksempel dokumentert: `python -m cli.analyze ...` produserer forutsigbar rapport.
- Sanity-sjekk: verdier i rapport er konsistente og uten exceptions.
- Enkle tester/skript verifiserer flyten.

## M5 — SHACL-validering (Ferdig)
- SHACL-shapes for RDF definert i `shapes/`.
- Valideringsscript i Python: kjørbar via CLI-flag eller separat kommando.
- Eksempelfiler validerer OK; feil rapporteres forståelig.
- Kort bruksdokumentasjon i `docs/` (hva, hvordan, hvor output havner).

## M6 — Strava-integrasjon (API & import) (Ferdig)
- OAuth-flyt verifisert; tokens lagres sikkert lokalt (ingen hemmeligheter i repo).
- Henting av aktiviteter med paging og tidsfilter (`--since`) fungerer.
- Streams → CSV (minst `time,hr,watts`), robust håndtering av 401/403/429/5xx.
- Inkrementell state (ingen duplikater), og grunnlogg over kjøringer.
- End-to-end “import → analyze” fungerer på ≥3 reelle økter (lokalt verifisert).

## M7 — Analysefunksjoner (effektivitet, treningsscore) (Ferdig)
- CGS v1 etablert: IF/NP/VI/Pa:Hr/WpB + 28d baseline (±25 %), tydelige fallbacks.
- Badges: Big Engine (+6 %, ≥30 min) og Metronome (VI≤1.05, Pa:Hr≤1.05).
- Python: Strava publish-formatter m/ språk, trimming og fallbacks + tester grønne.
- Rust: unit + golden + perf-guard (2h@1Hz ≤200 ms) grønne.
- Strava-klient: auto-refresh, header-fix, comment→description-fallback, verifisert live.
- Docs: CGS_v1, CLI usage, Strava publish oppdatert.



---

### Notater
- Sensitive nøkler, ekte tokens og personlige data holdes utenfor repoet.
- Denne DoD-filen er bevisst sanert og høynivå for offentlig deling.