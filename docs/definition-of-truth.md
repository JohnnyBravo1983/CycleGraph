# Definition of Truth

## Formål
Dette dokumentet definerer hvordan sannhet etableres i systemet – fra rådata til aggregerte trender – og hvilke konvensjoner som gjelder for versjonering, tidssoner og datakontrakter.

## Datakjede
`sessions → session_metrics → daily_user_metrics → trends_response`

## Begreper
- **sessions**: Rådata fra brukerens økt (tid, watt, puls, etc.).
- **session_metrics**: Aggregerte målinger per økt (snittwatt, varighet, etc.).
- **daily_user_metrics**: Daglig summering per bruker (f.eks. total watt, antall økter).
- **trends_response**: Strukturert API-respons for frontendens TrendsChart.

## Versjonering
Alle schemaer følger `v0.7.x`-konvensjon. Nye kontrakter legges til som `*.v1.json`, uten å endre eksisterende.

## Tidssone
All tid lagres og vises i **UTC**. Frontend er ansvarlig for eventuell lokal visning/formattering.

## Roll-up-logikk
- `session_metrics` genereres fra `sessions` ved analyse (`analyze_session()`).
- `daily_user_metrics` summerer `session_metrics` per bruker per dag.
- `trends_response` henter data fra `daily_user_metrics` og grupperer etter bucket (dag, uke, måned).

## Eksempel
```json
// sessions
{ "user_id": "abc", "start": "2025-10-14T08:00:00Z", "watts": [120, 130, 125] }

// session_metrics
{ "user_id": "abc", "date": "2025-10-14", "avg_watt": 125, "duration_min": 45 }

// daily_user_metrics
{ "user_id": "abc", "date": "2025-10-14", "total_watt": 125, "sessions": 1 }

// trends_response
{
  "from": "2025-10-14",
  "to": "2025-10-14",
  "bucket": "day",
  "data": [
    { "date": "2025-10-14", "avg_watt": 125 }
  ]
}