CycleGraph Score (CGS) v2.2

Mål
CGS summerer hvor hardt, hvor lenge og hvor jevnt/effektivt en økt ble gjennomført – nå også med en eksplisitt datakvalitetskomponent som reflekterer presisjon, kalibrering og prøvestørrelse.

Kjerne-metrikker

NP (Normalized Power): 30 s glidende snitt av effekt, 4. potens, middel, så fjerderot.

IF (Intensity Factor): NP / FTP.

VI (Variability Index): NP / avg_power (1.00 er helt jevnt).

Pa:Hr: relativ drift mellom effekt og puls (≈1.00 ved stabil intensitet).

W/beat (WpB): avg_power / avg_heart_rate (krever både HR og effekt).

PrecisionWatt: estimert usikkerhet i wattberegning; brukes i datakvalitetsvekting (lavere usikkerhet → høyere kvalitet).

Varighet: duration_s.

Prøvestørrelse: samples (krav ≥30 for “full verdi”).

Status/kalibrering: status (f.eks. LIMITED) og calibrated (true/false).

28-d baseline (WpB)
Velg økter siste 28 dager med effekt & HR, innen ±25 % varighet og samme modus (indoor/outdoor).
Baseline = median(WpB) av matchene. Fallbacks: trimmed mean (10 %) → global 28d (uten varighetsfilter) → None.
Minimum antall matcher: 3 (ellers settes WpB-komponenten nøytral).

CGS vektning (v2.2)

Hvor hardt? 0.35 → IF, NP (skalert)

Hvor lenge? 0.30 → varighet (log-skalert)

Hvor jevnt/effektivt? 0.25 → VI (jevnhet), Pa:Hr (stabilitet), WpB vs baseline (effektivitet)

Datakvalitet 0.10 → kombinasjon av:

PrecisionWatt (invers normalisert; lav usikkerhet gir høyere score)

samples (≥30 gir full uttelling; <30 lineær nedvekting)

calibrated (true gir lite kvalitetspåslag; false gir nøytral, ikke straff)

Merk: Datakvalitet påvirker score-konfidens og legger lett vekt på økter med dokumentert presisjon/tilstrekkelig data, uten å “straffe” ikke-kalibrert utstyr hardt.

Badges (v2.2)

Big Engine: WpB ≥ baseline × 1.06 og varighet ≥ 30 min.

Metronome: VI ≤ 1.05 og Pa:Hr ≤ 1.05.

Dialed In (ny): calibrated == true og PrecisionWatt ≤ ±3 W og samples ≥ 30.

Fallbacks & degrade (v2.2)

Mangler HR: hopp over Pa:Hr og WpB; bruk effektbaserte indikatorer (IF/NP/VI/varighet) + datakvalitet.

Mangler watts (hr_only): hopp over NP/IF/VI/WpB; bruk varighet + Pa:Hr (der mulig) + datakvalitet; sett status="LIMITED".

Kort økt (<10 samples): score beregnes, men datakvalitet nedvektes kraftig; sett status="LIMITED".

Ingen baseline: WpB-komponenten nøytraliseres; legg varsel i warnings.

Observabilitet (Sprint 6–7)

Strukturert logging (level, step, component, cache_hit) med justerbart loggnivå.

Metrikk sessions_no_power_total logges for økter uten wattdata.

JSON-rapport er deterministisk ved --dry-run.

Testene tåler ikke-JSON stdout-støy; anbefalt praksis er ren JSON på stdout og logging på stderr.

Rapport (S7)

schema_version: "0.7.0" (bruker CGS v2.2).

Felter (utdrag): cgs, badges, warnings, duration_s, samples, avg_power, avg_hr, NP, IF, VI, Pa:Hr, w_per_beat, w_per_beat_baseline, w_per_beat_baseline_source, precision_watt, calibrated, status, schema_version.

Ytelse (perf-guard)
Mål: ≤ 200 ms for 2h @ 1 Hz for beregning av NP/IF/VI/Pa:Hr/WpB + CGS.

Versjonsmapping

schema_version "0.7.0" → CGS v2.2

Changelog

v2.2 (2025-09-29) – La til datakvalitetsvekting (PrecisionWatt, samples, calibrated). Klargjorde regler for hr_only og kort økt (LIMITED). Innførte badge Dialed In. Baseline matcher nå modus (indoor/outdoor).

v2.1 (2025-09-28) – Presiserte at WpB-baseline krever effekt+HR; tydeliggjorde nøytralisering ved manglende baseline.

v2.0 (2025-09-26) – Forberedelse til schema-versionert rapport; rebalanserte vekter (0.35/0.30/0.25) og reserverte 0.10 til datakvalitet.

v1 (2025-08-20) – Første stabile definisjon. WpB-baseline (28d, ±25 %), badges Big Engine/Metronome, vekter 0.40/0.30/0.30, perf-guard 2h@1Hz ≤200 ms; observabilitet/PrecisionWatt introdusert.