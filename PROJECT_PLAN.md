2025-08-07	Opprette prosjektstruktur	1
2025-08-08	Sette opp Rust-core med pyo3 (enkel funksjon)	4 Ferdig
2025-08-09	Installere maturin og teste kobling til Python	2 Ferdig
2025-08-09	Lage analysefunksjon for effektivitet (Rust)	3 Ferdig
2025-08-10	Sette opp Python CLI (analyze.py)	4         Ferdig
2025-08-11	Lage første dummydata (CSV + RDF)	2         Ferdig
2025-08-12	Kjøre CLI → Rust → output-flyt	3             Ferdig
2025-08-12	Finne masse testere (lokalt og bredt / LinkedIn)	2
2025-08-13	Legge inn webanalyse (Plausible eller lignende)	2
2025-08-14	Lage anonym logging fra CLI (analysebruk)	2
2025-08-14	Utvide analysefunksjon til flere økter	3
2025-08-15	Implementere SHACL-validering	5
2025-08-16	Integrere validering i CLI	2
2025-08-17	Utvikle treningsscore-logikk	3
2025-08-18	Opprette Strava API-tilgang og testimport	4
2025-08-19	Lese Strava-data og konvertere til CSV/RDF	4
2025-08-20	Kjøre CLI-analyse på Strava-økter	3
2025-08-22	Lage enkel webdemo med output	5
2025-08-23	Visualisere grafer og fremgang (JS)	5
2025-08-24	Forberede MVP for testsyklister	3
2025-08-27	Samle feedback fra testere	4
2025-08-29	Justere analyse ut fra feedback	3
2025-09-01	🚀 Demo-lansering til testere og offentlig	0
2025-09-01	Planlegge kommersialisering (beta / abonnement)	3
2025-09-02	Poste 'nå kommer den'-innlegg på LinkedIn	2
2025-09-03	Etablere ny kanal / lenke for feedback	2


✅ Konklusjon
Del	Åpen?	Notat
Rust-core	✅ Ja	Open source (MIT anbefalt)
Python CLI	✅ Ja	Kan være åpen, men uten nøkler
Strava-integrasjon	❌ Nei	Lag eget privat repo eller hold utenfor
Brukeranalyse / logging	🔒	Hold kode + endpoints privat hvis data samles inn
Del	Synlig på GitHub?	Lisens?	Kommentar
Rust-core (core/)	✅ Ja	MIT	Viser Datalog/SHACL/effektivitetsanalyse
Python CLI (cli/)	✅ Ja	MIT	Viser bruken av pyo3, CSV/RDF osv
Dummydata (data/)	✅ Ja	MIT	Viser hvordan det fungerer uten sensitivt
Web-demo (web_demo/)	✅ Ja	MIT	Enkel visualisering (uten innlogging)
Strava-integrasjon (strava/)	❌ Nei	Privat	Holdes unna repo – inneholder API-nøkkel og strukturell edge
Brukerlogging / abonnement / score-logikk	❌ Nei	Privat	Din "moat" – behold det for deg selv eller kommersiell versjon