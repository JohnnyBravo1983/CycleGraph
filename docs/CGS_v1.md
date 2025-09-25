CycleGraph Score (CGS) v1
Mål
CGS summerer hvor hardt, hvor lenge, og hvor jevnt/effektivt en økt ble gjennomført.

Kjerne-metrikker
NP (Normalized Power): 30 s glidende snitt av effekt, 4. potens, middel, så fjerderot.

IF (Intensity Factor): NP / FTP.

VI (Variability Index): NP / avg_power (1.00 er helt jevnt).

Pa:Hr: relativ drift mellom effekt og puls (≈1.00 ved stabil intensitet).

W/beat (WpB): avg_power / avg_heart_rate (krever både HR og effekt).

PrecisionWatt: estimert usikkerhet i wattberegning, typisk ±1–2 W, avhengig av input-spredning og smoothing.

28-d baseline (WpB)
Velg økter siste 28 dager innen ±25 % varighet.

Baseline = median(WpB) av matchene. Fallbacks: trimmed mean (10 %) → global 28d (uten varighetsfilter) → None.

Min. antall matcher: 3.

CGS vektning
Hvor hardt? 0.40 (IF, NP)

Hvor lenge? 0.30 (varighet)

Hvor jevnt/effektivt? 0.30 (VI, Pa:Hr, WpB vs baseline)

Badges (v1)
Big Engine: WpB ≥ baseline * 1.06 og varighet ≥ 30 min.

Metronome: VI ≤ 1.05 og Pa:Hr ≤ 1.05.

Fallbacks & degrade
Mangler HR → hopp over Pa:Hr og WpB; bruk effektbaserte indikatorer.

Mangler watts → hopp over NP/IF/VI; bruk HR-basert intensitet (nøytraliser score).

Ingen baseline → nøytral referanse; legg varsel i warnings.

Begrenset input → fallback-modus (hr_only) med status LIMITED.

Observabilitet (Sprint 6)
CLI genererer strukturerte logger (level, step, component, cache_hit) med styrbart loggnivå via flagg/env.

Metrikk sessions_no_power_total logges eksplisitt ved økter uten wattdata.

Rapportfelt er deterministiske og testbare via dry-run.

PrecisionWatt gir frontend innsikt i beregningspresisjon.

Rapport (M7)
schema_version: "m7.1.0" (benytter CGS v1)

Felter: badges, warnings, w_per_beat, w_per_beat_baseline, w_per_beat_baseline_source, duration_s, cgs, precision_watt, m.m.

Ytelse (perf-guard)
Mål: ≤ 200 ms for 2h @ 1 Hz (NP/IF/VI/Pa:Hr/WpB).

Versjonsmapping
schema_version: "m7.1.0" → CGS: v1

Changelog
v1 (2025-08-20) – Første stabile definisjon. – WpB-baseline: 28d, ±25 % varighet, median → trimmed mean (10 %) → global 28d → None. – Badges: Big Engine (+6 %, ≥30 min), Metronome (VI ≤1.05 & Pa:Hr ≤1.05). – Vekter: Hardhet 0.40, Varighet 0.30, Jevnhet/effektivitet 0.30. – Perf-guard: 2h@1Hz ≤200 ms. – Sprint 6: PrecisionWatt, fallback-modus (hr_only), observabilitet (logger, metrikker), deterministisk rapport.