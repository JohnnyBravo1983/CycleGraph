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

S2 — Vær & profiler (🌤️) ✅
Sprint [ID 2]
Start: 12.09.2025
Ferdig: 13.09.2025
Estimat: 8–12 timer
Faktisk tid: 9 timer

Endringer:
Implementert værklient med støtte for vind, temperatur og trykk.
Caching per (lat, lon, timestamp) med lokal kv-store.
Profilsettings lagt til: total vekt, sykkeltype, dekk/underlag (Crr-preset).
Validering av profil med fallback til default og estimat=True-flagg.
Metrics lagt til: weather_cache_hit_total, weather_cache_miss_total.

Tester:
Lokale tester på cache-hit og profilvalidering.
CI kjørt med selektiv teststrategi (sanity-test hoppet over – publiseringsflyt ikke berørt).
pytest -v grønn på relevante moduler.
Status: Ferdig

Observasjoner:
✅ Cache-rate over 95 % ved rekjøring av samme økt.
✅ Profilvalidering fungerer med default og flagging.
🧠 CI-oppsett justert for høy ROI: sanity-test kjøres kun ved endringer i publiseringsflyt.
🚫 Ingen endringer i publish_to_strava() → ingen behov for full systemtest.
Neste: Sprint S3 — Fysikkmotor (🚴) med golden test og fysisk modell. Klar for å koble vær + profil inn i beregningene.
