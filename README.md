<p align="center">
  <img src="docs/logo/CycleGraph_Logo.png" alt="CycleGraph Logo" width="200"/>
</p>

# 🚴‍♂️ CycleGraph

Analyseverktøy for syklister som kombinerer **smart caching**, **Strava-integrasjon** og **avanserte treningsmetrikker** for å gi deg en enkel, rettferdig og inspirerende score på hver økt.

---

## ✨ Nøkkelfunksjoner (MVP)
- 📊 **CGS-score** (CycleGraph Score) med tre delskårer:
  - **Hvor hardt?** (Intensity)
  - **Hvor lenge?** (Duration)
  - **Hvor jevnt & effektivt?** (Quality)
- 🏅 **Badges** som fremhever prestasjoner og særpreg i økten.
- 📈 **Nøkkelmetrikker** som IF, NP, VI, Pa:Hr, W/slag – presentert med fargekoder og trendarrows.
- 🔁 **Smart caching** for rask gjenbruk og spørring.
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

---

## 🔒 Om lisens og bruk

CycleGraph er delt i to:

### 🔓 Åpen kjerne
All treningsanalyse og datamodellering som ligger i `/core`, `/cli`, `/data` og `/shapes` er fritt tilgjengelig for læring og ikke-kommersiell bruk.  
**Lisens:** CycleGraph Non-Commercial License v0.1

### 🔒 Prototype og kommersiell del
Webapp-frontend, Premium-funksjoner og enkelte API-endepunkter utvikles som en lukket MVP og er ikke inkludert i dette repoet. Disse delene vurderes for fremtidig kommersiell bruk.

---

## 📫 Vil du teste eller bidra?

Er du syklist og nysgjerrig på hvor effektivt du trener?  
Kontakt: **jstromo83@gmail.com** eller legg igjen en issue i repoet.

---

## 🖥️ Eksempel: CLI-kjøring

```bash
$ python cli/analyze.py --file data/2025-08-01.csv
🚴‍♂️ CycleGraph v0.1

⏱️ Varighet: 2t 05m
📊 CGS: 88  (Hvor hardt: 93 | Hvor lenge: 82 | Hvor jevnt & effektivt: 88)
🏅 Badges: Iron Lungs

🔧 Nøkkelmetrikker
• IF 0.92   • VI 1.11   • Pa:Hr 2.4%   • W/slag 1.59 (+10% vs baseline)
🔁 Mini-trend: siste 3 økter snitt 85  (↑ +3%)

🔗 Strava: «CycleGraph CGS 88 · IF 0.92 · VI 1.11 · Pa:Hr 2.4% · W/slag 1.59 (↑+10%) · Trend ↑+3%»
