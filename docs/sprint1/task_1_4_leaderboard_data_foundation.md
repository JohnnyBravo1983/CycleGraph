# Task 1.4 — Verify Leaderboard Data Foundation

Dato: 2026-01-16  
Scope: Read-only audit av lagrede resultfiler + SSOT `sessions_index.json` (ingen ingest/UI/migrasjon)

## 1) Datakilder (SSOT + result)
- SSOT (eierskap): `state/users/<uid>/sessions_index.json`
  - Format observert: `{ "rides": [ "<ride_id>", ... ] }`
  - For uid `u_VXyRxSj8x4kdkCqu9M3Hvw`: `rides` = 40
- Result: `logs/results/result_<ride_id>.json`
- Eierskap: indirekte via SSOT (`rides[]`). Aggregeringer skal baseres på SSOT + filoppslag (ikke filnavn alene).

## 2) Metric-inventar (top-level fields i result_<ride>.json)

## 2.1) Metric-inventar (metrics.* subfelter)
Basert på audit (SampleN=50). Disse subfeltene er observert under metrics:

- metrics.calibrated
- metrics.calibration_mae
- metrics.calibration_status
- metrics.cg_build
- metrics.core_n_device_samples
- metrics.core_watts_source
- metrics.drag_watt
- metrics.eff_used
- metrics.estimated_error_pct_range
- metrics.gravity_watt
- metrics.gravity_watt_pedal
- metrics.gravity_watt_signed
- metrics.model_watt_crank
- metrics.model_watt_wheel
- metrics.model_watt_wheel_pedal
- metrics.model_watt_wheel_pedal_elapsed
- metrics.model_watt_wheel_pedal_moving
- metrics.model_watt_wheel_signed
- metrics.pedal_ratio_elapsed_over_moving
- metrics.precision_quality_hint
- metrics.precision_watt
- metrics.precision_watt_avg
- metrics.precision_watt_crank
- metrics.precision_watt_pedal
- metrics.precision_watt_signed
- metrics.profile_used
- metrics.rolling_watt
- metrics.total_watt
- metrics.total_watt_pedal
- metrics.total_watt_signed
- metrics.weather_applied
- metrics.weather_fp
- metrics.weather_meta
- metrics.weather_source
- metrics.weather_used
- metrics.wind_effect

Datatype-status:
- Ingen multi-type røde flagg observert for metrics.* i sample (OK).
Basert på audit (SampleN=50, results dir=`logs/results`).

Top-level keys observert:
- calibrated
- cg_build
- debug
- metrics
- precision_watt_avg
- profile_used
- profile_version
- repr_kind
- source
- start_time
- v_rel
- watts
- weather_applied
- weather_source
- wind_rel

Store arrays (ikke direkte egnet for leaderboards uten videre aggregering):
- watts (array, Len ~1187 i eksempel)
- v_rel (array, Len ~1187 i eksempel)
- wind_rel (array, Len ~1187 i eksempel)

## 3) Datatype- og konsistenssjekk
### 3.1 Multi-type røde flagg
- Ingen top-level keys med blandede datatyper observert i sample (OK).

### 3.2 Manglende resultfiler for SSOT rides (røde flagg)
Følgende ride IDs finnes i SSOT, men mangler `result_<ride>.json`:
- PUTT_INN_NY_RID_HER (placeholder)
- DITT_EKTE_RID_HER (placeholder)
- 167439016198 (mistenkelig ID / mulig typo)
- 5908409437 (mangler resultfil)

Konsekvens: disse rides kan ikke inngå i leaderboards før SSOT ryddes eller ingest produserer resultfiler (Sprint 2+).

## 4) Tids- og ID-stabilitet
### 4.1 ID
- Primær ID for aggregering: `<ride_id>` fra SSOT (`rides[]`)
- Resultfil: `logs/results/result_<ride_id>.json`
- Stabilitet: OK så lenge SSOT er autoritativ og placeholders/typos fjernes senere.

### 4.2 Tid
- Primært tidsfelt observert: `start_time`
- Format: ISO 8601 med `Z` (UTC) observert (eks: `2024-05-18T14:05:19Z`)
- Egnet for: “siste 30 dager”, år-for-år, trendqueries.

## 5) Manuell aggregeringsverifikasjon (3 stk)
Utført via PowerShell, basert på SSOT rides[] og logs/results/result_<ride_id>.json.

1. **Top 10 rides etter precision_watt_avg**
   - Resultat (top 10):
     - 12188367759 (2024-08-19): 293.52
     - 12709078268 (2024-10-21): 291.13
     - 14942774174 (2025-06-28): 269.80
     - 12172270701 (2024-08-17): 264.98
     - 16053034149 (2025-10-06): 255.88
     - 16231049823 (2025-10-23): 254.01
     - 16007374633 (2025-10-02): 253.39
     - 15908409437 (2025-09-23): 252.53
     - 16192415203 (2025-10-19): 248.17
     - 16127771071 (2025-10-13): 247.62
   - Verifisert at start_time kan brukes for sortering/filtering.

2. **Sum 	ss siste 30 dager**
   - Resultat: 0
   - Tolkning: enten ingen rides innen cutoff, eller 	ss ikke brukes/er null i disse resultatene (må bekreftes ved metrics-subkey audit).

3. **Snitt precision_watt_avg per år**
   - 2022: 162.05 (n=5)
   - 2023: 206.75 (n=3)
   - 2024: 243.57 (n=8)
   - 2025: 231.16 (n=20)

## 6) Leveranse
### A) Leaderboard-ready felt (direkte aggregerbare)
- start_time (tidsfiltering og grouping)
- precision_watt_avg (top-N / snitt / trend)  *(forutsatt at feltet er numerisk på tvers av rides)*
- weather_applied (bool/flag filter)
- weather_source (kategori/filter)
- profile_version (kategori/filter)

### B) Ikke-klare felt
- tss: aggregering ga 0 siste 30 dager; enten ingen rides i perioden eller tss lagres ikke/er null i resultatene (Sprint 2+ hvis leaderboards trenger TSS).
- watts / v_rel / wind_rel: store arrays (må aggregeres før leaderboardbruk)
- debug: diagnostikk, ikke leaderboard
- metrics: krever egen inventar av subfelter (må audites separat hvis leaderboards skal bruke noe inni)
- SSOT entries uten resultfil (se liste)

### C) Anbefalinger (kun notert)
- Fjern placeholders fra `sessions_index.json` (PUTT_INN_NY_RID_HER / DITT_EKTE_RID_HER)
- Valider ride IDs (167439016198 ser feil ut) og sikre at alle SSOT rides har resultfil
- Hvis leaderboards senere skal bruke felter inne i `metrics`, må `metrics.*` inventeres og type-sjekkes tilsvarende





