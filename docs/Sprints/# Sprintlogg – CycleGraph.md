# Sprintlogg – CycleGraph


M7.6 Watt-engine v1 & Precision Watt v1.0 (Backend)
### Sprint [ID 1]
- **Dato start:*10.09.2025*  
- **Dato ferdig:*10.09.2025*  
- **Estimat:** 8-12 timer  
- **Faktisk tid:** 8 timer  
- **Endringer:**  
  - Implementert auto-modus basert på trainer, sport_type, device_watts.
  - Lagt til CLI-flag --mode roller|outdoor for å overstyre auto.
  - JSON-output rutet til korrekt pipeline (indoor/outdoor). 
  - **Tester:**  
  - pytest -q grønn (CLI-parsing, mode override, dry-run).
  - cargo test --tests -q grønn (session analysis, efficiency calc, JSON-output). 
- **Status:** Ferdig  
- **Observasjoner:**  
  - Hva gikk bra  Auto-modus og CLI-override fungerte stabilt; alle tester grønne både lokalt og i CI.
  - Hva kan forbedres Enkelte Strava-økter manglet watt (device_watts=False) → krever policy og fallback (lagt inn som oppfølging i Sprint S1B). 


Sprint [S1B] – No-watt fallback & policy
Dato start: 13.09.2025
Dato ferdig: 14.09.2025
Estimat: 8–10 timer
Faktisk tid: ca. 14 timer (mye debugging CI/pytest/cargo)

Endringer:
Implementert fallback til hr_only for økter uten watt eller device_watts=False.
Structured WARN-logg med no_power_reason.
Metrics: sessions_no_power_total og sessions_device_watts_false_total.
Varsel lagt til i publish dry-run.
Git hygiene: .gitignore oppdatert, eksempelfiler (tokens_example.py, last_import.sample.json) lagt til.

Tester:
pytest -q grønn (fixtures for no-watt).
cargo test --tests -q grønn (analyzer-test med mode="hr_only").
Golden-test validert output.
Status: Ferdig
Observasjoner:
Hva gikk bra: Fallback-løsningen fungerte, metrics og logging på plass; både pytest og cargo grønn lokalt og i CI.
Hva kan forbedres: CI-debugging tok tid (requests, dotenv, tokens); bør rydde opp i workflow (planlagt S2B – CI hardening). Frontend-varsel håndteres i M8.