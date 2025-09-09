# Workflow – CycleGraph utviklingsflyt

## Roller
- **Du**: Starter oppgaver, velger DoD-punkt, kjører samtaler.
- **ChatGPT**: Dirigent, lager oppgave-spesifikke manus til Copilot, oppdaterer Masterplan og DoD.
- **Copilot**: Utfører kodeendringer, tester og feilsøking steg for steg.
- **Du LAgrer Manus til Copilot og Rapport tilbake etter hver komunikasjonsflyt

---

## Standard arbeidsflyt

1. **Du → ChatGPT**  
   - Start en ny chat for hver oppgave.  
   - Lim inn siste versjon av **Masterplan** og **Dynamisk DoD & Backlog**.  
   - Si hvilken oppgave du skal gjøre (fra DoD).  
   - Lim inn *standard arbeidsflyt-manus*.

Instruksjon til Chat
Hei, jeg skal i gang med [TASK NAVN].
Her er siste Masterplan og DoD.
Oppgave fra DoD: [sett inn punkt]

Din oppgave (ChatGPT):

Lag et kort manus til Copilot basert på DoD-punktet.

Manus skal være presist og bare inneholde det Copilot trenger for å sette opp en detaljert kjøreplan steg for steg.

Copilot er ansvarlig for å utføre selve jobben: kodeendringer, tester, feilsøking og rapportering.

Du (ChatGPT) skal ikke gjøre koding, kun levere manus.

Copilot sin plan skal alltid inkludere:

Hvilke filer som skal endres

Hvilke tester som skal skrives/kjøres

Forventet output/resultat etter hvert steg

Når Copilot har fulgt planen og er ferdig, rapporterer den tilbake i fast format (branch, commits, endrede filer, testresultater, observasjoner). Da oppdaterer du (ChatGPT) Masterplan og DoD.

2. **ChatGPT → Copilot**  (Send Manus fra Chat til Copilot)
   - Setter opp et **oppgave-spesifikt manus** tilpasset DoD-punktet.  
   - Gir Copilot konkrete instruksjoner og tester å kjøre.

3. **Du via Copilot → ChatGPT**  (send Rapport fra Copilot til Chatgpt)
   - Når ferdig, rapporterer i dette formatet:


Gi en kort og tydelig oppsummering i dette formatet:

✅ Oppgave: [navn fra DoD]
Endringer: [kort liste over hva som ble gjort, maks 3–4 punkter]
Tester: [hvilke tester som ble kjørt og at de er grønne]
Status: [Ferdig / Delvis ferdig / Feil som gjenstår]


Ikke lim inn hele koden på nytt – bare vis hvilke filer som ble endret og bekreft at alt er committed/kjørt.

Hvis noe fortsatt er rødt: skriv kort hva som feilet og hva neste minste fix bør være.


4. **ChatGPT → Oppdatering**  
   - Lager en **sluttrapport** (kort logg for oppgaven).  
   - Oppdaterer **Dynamisk DoD & Backlog** (flytter oppgaven til Ferdig).  
   - Synkroniserer **Masterplan** med statusoversikt og milepælsrapport.  
   - Sørger for at roadmap og backlog alltid er i takt.  


