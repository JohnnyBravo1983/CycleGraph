# CLI-flagg — `python -m cli.analyze session`

> Dette er dokumentasjon for `session`-kommandoen. (Linjene under er eksempler – ikke kjør dem nøyaktig som de står.)

## Bruk

```bash
python -m cli.analyze session --input <glob> [flagg...]
```

## Flaggoversikt

| Navn          | Type                           | Default  | Eksempel                                | Beskrivelse                                                        |
| ------------- | ------------------------------ | -------- | --------------------------------------- | ------------------------------------------------------------------ |
| `--input`     | str (glob) **påkrevd**         | –        | `--input tests/data/golden_outdoor.csv` | Angi én fil eller glob-mønster for øktdata (CSV).                  |
| `--weather`   | str (fil/URL)                  | –        | `--weather tests/data/golden_wx.json`   | Valgfri værkilde. Brukes i beregninger når tilgjengelig.           |
| `--format`    | `json` \| `csv` \| `both`      | `json`   | `--format both`                         | Output-format: skriv JSON, CSV eller begge.                        |
| `--out`       | str (katalog)                  | `output` | `--out artifacts/session_001`           | Katalog for filer ved skriving. Ignorert ved `--dry-run`.          |
| `--lang`      | `no` \| `en`                   | `no`     | `--lang en`                             | Språk/locale for tekstlige felt i rapport.                         |
| `--calibrate` | flagg (bool)                   | `false`  | `--calibrate`                           | Aktiverer kalibrering; setter `calibrated` i rapporten.            |
| `--dry-run`   | flagg (bool)                   | `false`  | `--dry-run`                             | Skriver rapport til **stdout** i stedet for til filer.             |
| `--log-level` | `info` \| `debug` \| `warning` | `info`   | `--log-level debug`                     | Styrer detaljnivå på strukturerte logger (JSON) til stderr/stdout. |
| `--cfg`       | str (fil)                      | –        | `--cfg configs/local.json`              | Valgfri konfig-fil. Kan bl.a. sette `history_dir`, m.m.            |
| `--debug`     | flagg (bool)                   | `false`  | `--debug`                               | Skriver ekstra debug-info (f.eks. normaliseringssteg) til stderr.  |

