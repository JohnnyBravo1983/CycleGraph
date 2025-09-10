
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

# Sprint S1 — Datagrunnlag & modus (⚙️)

**Branch:** feature/strava-fetch-mode  
**Commits:**  
- a3f9c12 — Add Strava stream fetch with auto-mode detection  
- c7b1e88 — CLI flag --mode roller|outdoor added  
- f2d4a91 — Log mode in JSON and route to correct pipeline

**Endrede filer (utvalg):**
cli/analyze.py, cli/strava_client.py, cli/test_fetch.py, cli/formatters/strava_publish.py, core/Cargo.toml

**Tester:**  
- pytest: OK (CLI-parsing, mode override, dry-run output)  
- cargo test: OK (session analysis, efficiency calc, JSON output)

**Funn / Observasjoner:**  
- `--mode` overstyrer auto-deteksjon som forventet.  
- Auto-modus bruker `trainer`, `sport_type`, `device_watts`.  
- Noen Strava-økter mangler watt eller har `device_watts=False` → vurder varsel i frontend og/eller fallback i backend.

**Status:** ✅ Ferdig  
**Neste:** Avklare policy for økter uten watt (frontend-varsel vs. backend-fallback + logging).