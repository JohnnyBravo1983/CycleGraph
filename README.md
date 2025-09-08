# 🚴‍♂️ CycleGraph

🚴 CycleGraph – et treningsverktøy bygget av en mosjonistsyklist, for å spore fremgang og nå nye mål – fra topp 40 % i 2025 til topp 10 % i 2028.

![CycleGraph Logo](docs/CycleGraph_Logo.png)

---

## ✨ Nøkkelfunksjoner (Beta)
- 📊 **CGS-score** (CycleGraph Score) med tre delskårer:
  - **Hvor hardt?** (Intensity)
  - **Hvor lenge?** (Duration)
  - **Hvor jevnt & effektivt?** (Quality)
- ⚡ **CGS-Watt** (kalibrert effektmåling basert på NP).
- 🌤️ **Værdata** (temperatur, vind og forhold koblet til økt).
- 🏅 **Badges** som fremhever prestasjoner og særpreg i økten.
- 📈 **Nøkkelmetrikker** som IF, NP, VI, Pa:Hr, W/slag – presentert med fargekoder og trendarrows.
- 🔁 **Smart caching** (statisk + dynamisk) for rask gjenbruk og spørring.
- 🔌 **Strava-integrasjon** (import av dine økter, automatisk publisering av kommentarer).
- 📉 **Mini-trend** – se forbedring over siste 3 økter.
- 🔒 **Personvernklar** – lokal behandling, samtykke før publisering.

---

## 🛠️ Struktur

- `core/` – Rust-kjerne, eksponert som Python-modul via `pyo3`
- `cli/` – Python-skript for lokal analyse
- `data/` – Treningsdata i CSV eller RDF-format
- `shapes/` – SHACL-regler for treningsvalidering
- `docs/` – Logo, illustrasjoner og demoer
- `tests/` – Golden files og systemtester (Rust + Pytest)

---

## 📅 Status & Planer

- ✅ **MVP-funksjonalitet** implementert (CGS, badges, caching, Strava import/publish).
- ✅ **Systemtester** (Rust golden + Pytest for CLI).
- ✅ **Golden testing** stabilisert (env-styrt oppdatering).
- 🚧 **Beta-lansering**: første demo med CGS-Watt + værdata koblet inn.
- 🎯 **Videre**: enklere frontend, brukerpilot, feedback, og Basic/Pro-abonnement.

---

## 📫 Vil du teste eller bidra?

Er du syklist og nysgjerrig på hvor effektivt du trener?  
Kontakt: **jstromo83@gmail.com** eller legg igjen en issue i repoet.

---

## 🖥️ Eksempel: CLI-kjøring

### Alternativ A – vanlig kjøring
```bash
$ python cli/analyze.py --file data/2025-08-01.csv
🚴‍♂️ CycleGraph v0.1

⏱️ Varighet: 2t 05m
📊 CGS: 88  (Hvor hardt: 93 | Hvor lenge: 82 | Hvor jevnt & effektivt: 88)
⚡ CGS-Watt: 196 W (Normalized Power)
🌤️ Vær: 18°C, lett bris, opphold
🏅 Badges: Iron Lungs

🔧 Nøkkelmetrikker
• IF 0.92   • VI 1.11   • Pa:Hr 2.4%   • W/slag 1.59 (+10% vs baseline)
🔁 Mini-trend: siste 3 økter snitt 85  (↑ +3%)

🔗 Strava-kommentar:
«CycleGraph · CGS 88 · CGS-Watt 196 W · IF 0.92 · VI 1.11 · Pa:Hr 2.4% · W/slag 1.59 (+10%) · Trend ↑+3% · 🌤️18°C»
```

### Alternativ B – dry-run
For å teste publisering til Strava **uten** å poste, kjør med `--dry-run`.  
Da simuleres output lokalt, men ingenting legges ut på Strava.

---

## 🧪 Testing & Golden Files

CycleGraph bruker *golden testing* for å sikre at beregningene holder seg stabile over tid.

**Vanlig kjøring:**
```powershell
cargo test
```

Alt kjører grønt under normale forhold. Golden-testen (`golden_sessions_match_with_tolerance`) sammenligner beregnede verdier mot lagrede fasitfiler i `tests/golden/expected`.

**Oppdatere golden (kun ved bevisste endringer i algoritmer):**
```powershell
cd core
$env:CG_UPDATE_GOLDEN="1"
cargo test -q golden_sessions_match_with_tolerance
Remove-Item Env:\CG_UPDATE_GOLDEN
```

Dette regenererer fasitfilene (`*_expected.json`).  
👉 Husk å committe både `lib.rs` og de oppdaterte JSON-filene.

---

## 🔒 Om lisens og bruk

CycleGraph er delt i to:

### 🔓 Åpen kjerne
All treningsanalyse og datamodellering som ligger i `/core`, `/cli`, `/data` og `/shapes` er fritt tilgjengelig for læring og ikke-kommersiell bruk.  
**Lisens:** CycleGraph Non-Commercial License v0.1

### 🔒 Prototype og kommersiell del
Webapp-frontend, Premium-funksjoner og enkelte API-endepunkter utvikles som en lukket Beta og er ikke inkludert i dette repoet. Disse delene vurderes for fremtidig kommersiell bruk.
