# CycleGraph – Masterplan

**Formål:**  
CycleGraph er et verktøy for analyse av treningsdata (watt, puls, varighet) med Strava-integrasjon og Rust-kjerne via pyo3.  
Målet er å gi syklister innsikt i puls/watt-effektivitet og utvikling over tid, med MVP-demo 1. september 2025.  
Arkitekturen skal være modulær og skalerbar for fremtidig Azure-drift.

---CycleGraph – Masterplan
Formål:
CycleGraph er et verktøy for analyse av treningsdata (watt, puls, varighet) med Strava-integrasjon og Rust-kjerne via pyo3.
Målet er å gi syklister innsikt i puls/watt-effektivitet og utvikling over tid, med MVP-demo 1. september 2025.
Arkitekturen skal være modulær og skalerbar for fremtidig Azure-drift.

Statusoversikt (oppdatert etter hver milepæl)
Dato	Milepæl	Status	Beskrivelse
2025-08-07	Opprette prosjektstruktur	Ferdig	Opprettet mappeoppsett (core, cli, data, docs, shapes), initialisert GitHub-repo (public) med README, lisens og .gitignore.
2025-08-08	Sette opp Rust-core med pyo3 (enkel funksjon)	Ferdig	Konfigurert Cargo.toml med pyo3, lagt inn første testfunksjon og bekreftet bygging.
2025-08-09	Installere maturin og teste kobling til Python	Ferdig	Installert og testet Maturin-build, bekreftet Python-import av Rust-modul.
2025-08-09	Lage analysefunksjon for effektivitet (Rust)	Ferdig	Implementert beregning av snitteffektivitet, øktstatus og per-punkt-data, testet via Python.
2025-08-10	Sette opp Python CLI (analyze.py)	Ferdig	Laget CLI med argparse, integrert Rust-funksjon, testet full CSV → Rust → output-flyt.
2025-08-11	Lage første dummydata (CSV + RDF)	Ferdig	Opprettet sample_data med testfiler for CLI og validering.
2025-08-12	Kjøre CLI → Rust → output-flyt	Ferdig	Verifisert analyse med dummydata, konsistent output.
2025-08-12	Finne masse testere (lokalt og bredt / LinkedIn)	Påbegynt	Strategi definert for lokal og online outreach, avventer Strava-integrasjon.
2025-08-13	Legge inn webanalyse (Plausible eller lignende)	Ikke startet	
2025-08-14	Lage anonym logging fra CLI (analysebruk)	Ikke startet	
2025-08-14	Utvide analysefunksjon til flere økter	Ikke startet	
2025-08-15	Implementere SHACL-validering	Ferdig	Lagt til SHACL-shapes og Python-script for RDF-validering, testet med dummydata.
2025-08-16	Integrere validering i CLI	Ferdig	CLI-utvidelse med valideringsopsjon og terminaloutput.
2025-08-17	Utvikle treningsscore-logikk	Ikke startet	
2025-08-18	Opprette Strava API-tilgang og testimport	Påbegynt	Løst .env-feil og redirect_uri-krav, hentet gyldig authorization code, lagret tokens lokalt.
2025-08-11	M6 – Strava OAuth autorisasjon	Ferdig	Fikset .env (UTF-8 uten BOM), lastet CID/secret korrekt, kjørte authorize → code → token (200 OK), lagret data/strava_tokens.json. Callback via http://127.0.0.1:5001/callback.
2025-08-11	M6 – Tokenhåndtering & lagring	Ferdig	Preemptiv refresh før utløp, håndtering av rotert refresh_token, vennlige feilmeldinger når tokenfil mangler/er korrupt. Første testimport gjennomført.
2025-08-19	Lese Strava-data og konvertere til CSV/RDF	Påbegynt	Opprettet importskript for CSV-konvertering, test avhenger av fullført API-autentisering.
2025-08-20	Kjøre CLI-analyse på Strava-økter	Ikke startet	
2025-08-22	Lage enkel webdemo med output	Ikke startet	
2025-08-23	Visualisere grafer og fremgang (JS)	Ikke startet	
2025-08-24	Forberede MVP for testsyklister	Ikke startet	
2025-08-27	Samle feedback fra testere	Ikke startet	
2025-08-29	Justere analyse ut fra feedback	Ikke startet	
2025-09-01	🚀 Demo-lansering til testere og offentlig	Ikke startet	
2025-09-01	Planlegge kommersialisering (beta / abonnement)	Påbegynt	Fastlagt Open Core-modell og trinnvis lanseringsplan.
2025-09-02	Poste 'nå kommer den'-innlegg på LinkedIn	Ikke startet	
2025-09-03	Etablere ny kanal / lenke for feedback	Ikke startet	

Milepæl-plan (M1–M12)
M1 – Prosjektstruktur & repo (Ferdig)

M2 – Rust-core med pyo3 (Ferdig)

M3 – CLI-oppsett & dataflyt (Ferdig)

M4 – Dummydata & testkjøring (Ferdig)

M5 – SHACL-validering (Ferdig)

M6 – Strava-integrasjon (API & import) (Delvis ferdig – punkt 1–2 OK, 3–5 gjenstår)

M7 – Analysefunksjoner (effektivitet, treningsscore) (Ikke startet)

M8 – Webdemo & visualisering (Ikke startet)

M9 – MVP-forberedelse & testing (Ikke startet)

M10 – Feedback-innsamling & justeringer (Ikke startet)

M11 – Demo-lansering & markedsføring (Ikke startet)

M12 – Kommersialisering & skalering (Ikke startet)

M6 – Strava-integrasjon (API & import) – status per 2025-08-11
✅ Punkt 1: Fiks authorize-bug (redirect/URL, scopes, token-exchange uten redirect_uri, lokal callback-server på port 5001).
✅ Punkt 2: Sikre .env og tokensti (UTF-8 uten BOM), robust lasting, preemptiv refresh og rotasjon av refresh_token, vennlige feilmeldinger.
⏭️ Neste: Punkt 3–5 (rate-limit & trygg polling, paging + --since/inkrementell sync, streams→CSV med time,hr,watts (+ ev. moving,altitude)).

Oppdateringsrutine
Når en milepæl er ferdig:

Oppdater status i tabellen over.

Endre milepælstatus i planen nederst.

Når du starter en ny milepæl-chat:

Kopier hele Masterplan.md inn i chatten.

Legg til milepæl-spesifikke “MÅL FOR MILEPÆLEN” og “NESTE OPPGAVE”-seksjoner.

Lag commit i repoet:


