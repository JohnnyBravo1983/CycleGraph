# How it works

CLI-analyse bygger rapporter basert på samples (tid, HR, watt, GPS/vind), profil og værdata.

## Rapportfelter
- **NP**: Normalized Power – 30s glidende snitt, 4. potens, gjennomsnitt, 4. rot.
- **Avg**: Gjennomsnittlig effekt.
- **VI**: Variability Index = NP / Avg.
- **Pa:Hr**: Ratio mellom gjennomsnittlig watt og HR.
- **W/beat**: Total watt dividert på totale hjerteslag.
- **PrecisionWatt**: ± estimert usikkerhet basert på input-spredning og smoothing.

## Modus og fallback
- `hr_only`: fallback når wattdata mangler eller ikke kan kobles til HR.
- `LIMITED`: status når rapporten mangler nøkkeldata.

## CLI-bruk
- `--dry-run`: simulerer analyse uten å skrive til disk.
- `--log-level`: styrer loggnivå (`info`, `debug`, `warning`).
- `--format json`: gir strukturert rapportoutput.

## Eksempel på dry-run output
```json
{
  "np": 441.53,
  "avg_power": 384.52,
  "vi": 1.15,
  "pa_hr": 0.0,
  "w_per_beat": 0.0,
  "PrecisionWatt": "±35.1 W"
}

Kode
[DRY-RUN] METRICS: NP=441.53 Avg=384.52 VI=1.15 Pa:Hr=0.0 W/beat=0.0 ±35.1 W
Kode
{"metric": "sessions_no_power_total", "value": 1, "session_id": "test_golden_segment"}
Kode
{"level": "INFO", "step": "compute_power_with_wind", "cache_hit": false}
Kode
{"level": "INFO", "step": "done", "rc": 0}