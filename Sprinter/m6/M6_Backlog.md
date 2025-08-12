# 📌 Backlog – Milepæl 6 (CycleGraph)

## 1. Funksjonsønsker (Features)
For idéer om nye funksjoner som kan gi merverdi, men ikke er kritiske for nåværende milepæl.

| ID  | Tittel | Beskrivelse | Prioritet (H/M/L) | Status |
|-----|--------|-------------|-------------------|--------|
| F-001 | Automatisk dataanalyse | Etter import, automatisk generere en kort rapport med snittpuls, snittwatt og varighet | M | ⬜ |
| F-002 | CLI flag for "since" | Mulighet til å spesifisere startdato for import i CLI, konverteres til epoch | M | ⬜ |

## 2. Tekniske forbedringer (Tech debt / optimisering)
For forslag til teknisk opprydding, optimalisering eller bedre struktur.

| ID  | Tittel | Beskrivelse | Prioritet (H/M/L) | Status |
|-----|--------|-------------|-------------------|--------|
| T-001 | Paginering og after-state | Fullføre paginering med state.json for inkrementell sync | H | ⬜ |
| T-002 | Bedre feilhåndtering | Legge inn spesifikke meldinger for 401/403/429 + rate limit backoff | H | ⬜ |

## 3. Bugs / kjente problemer
For feil som ikke stopper fremdriften nå, men må rettes senere.

| ID  | Tittel | Beskrivelse | Prioritet (H/M/L) | Status |
|-----|--------|-------------|-------------------|--------|
| B-001 | Manglende watts-data | Noen Strava-økter mangler watt i streams, krever fallback til NaN i CSV | M | ⬜ |
| B-002 | Redirect mismatch | Strava token exchange feiler hvis redirect_uri ikke matcher autorisasjonssteget | H | ⬜ |

## 4. Notater / idéparkering
Frie notater, tanker eller "kanskje senere"-ting.

- Mulighet for eksport til JSON-LD
- SHACL-validering mot eget cg: namespace
- Støtte for Garmin API i fremtidig milepæl
