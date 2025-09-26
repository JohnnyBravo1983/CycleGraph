# Session JSON Schema

- **Versjon:** `0.7.0`
- **Fil:** `docs/schema/session_v0.7.0.json`
- **Semver-policy:**  
  - **PATCH (X.Y.Z → X.Y.Z+1):** Feltbeskrivelser/docs presisering uten å endre semantikk.  
  - **MINOR (X.Y.Z → X.Y+1.0):** Nye *opsjonelle* felt som ikke bryter eksisterende konsumenter.  
  - **MAJOR (X.Y.Z → X+1.0.0):** Endring i felt-semantikk, fjerning/renaming av felt, eller strengere validering.

## Påkrevde felt
`session_id, duration_s, samples, avg_power, np, if_, vi, pa_hr, w_per_beat, precision_watt, calibrated, status, wind_rel, v_rel, schema_version`

## Opsjonelle blokker
- `weather` (finnes kun når --weather er brukt eller data er tilgjengelig)
- `gps` (kun outdoor)
- `notes`

## Endringslogg
- **0.7.0 (Sprint 7):** Første formelle schema med `schema_version` felt i CLI/API-output. Ingen beregningsendringer.