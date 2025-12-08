1. Foreslått rutestruktur (informasjon / IA)

Jeg normaliserer navnene litt så de blir ryddige og “prod-vennlige”, men alt er basert på det du skrev.

Public routes

/ – LandingPage (inngangsrouter)
Innhold:

Logo (CycleGraphLogo)

Språkvelger med flagg (LanguageToggle – norsk/engelsk)

Kort forklaring av:

Precision Watt-beregning

Formålet med CycleGraph

To hovedknapper:

“Logg inn / Log In” → /login

“Registrer ny bruker / Sign up” → /signup

/login – LoginPage

Skjema med:

E-post

Passord

“Logg inn”-knapp

Ved suksess → redirect til /dashboard (DynamicDashboardPage)

/signup – SignupPage

Skjema med:

Fullt navn

Bike name

E-post

Passord

GDPR/consent-seksjon:

Tekst om bruk av Strava-aktiviteter

3 mnd gratis CycleGraph Basic

Checkbox: “I agree …”

Knapp “Proceed to calibration”

Ved klikk → /calibration

Semi-public / onboarding

/calibration – CalibrationPage
Her fyller nye brukere inn profilen sin første gang.

Innhold:

Skjema med alle profilfelter (det vi har i profile-modellen):

Vekt, høyde, CdA, Crr, FTP, crank efficiency, osv.

Default-verdier:

Hvis noe ikke er satt, vises default i grå tekst (placeholder)

To dynamiske rundinger (donut-/gauge-komponenter):

“Calibration completeness”

Starter på f.eks. 75 %

Går mot 100 % når brukeren fyller inn alle felter som ikke er default

“Estimated Precision Watt Accuracy”

Starter på f.eks. 90 %

Maks 96–98 %

Tekstforklaring: forutsetter normale forhold (vind < 3–4 m/s, tørr asfalt, etc.)

Knapp “Proceed to Dashboard”

Ved klikk → /dashboard

Auth-beskyttede sider (krever innlogget bruker)

/dashboard – DynamicDashboardPage
Dette er “hjemmesiden” etter login.

Innhold:

De to rundingene fra Calibration:

Calibration %

Estimated watt accuracy

Kort tekst: “Du kan forbedre nøyaktigheten ved å oppdatere profilen/kalibreringen”

Snarveier / knapper:

“Rides / Økter” → /rides

“Trends / Trender” → /trends

“Goals / Mål” → /goals

“Profile / Profil” → /profile

/rides – RidesPage (tidligere SessionsPage)

Liste over alle økter (nyeste først)

Hver økt (RideCard):

Dato

Navn

Varighet

Distance

Snittwatt (Precision Watt avg)

Tags / markering:

“FTP / High intensity”

“Other”

Aksjoner:

Klikk på kort → /rides/:rideId

Slett-knapp for økter av lav kvalitet (ikke med i trender)

/rides/:rideId – RideDetailPage (nåværende SessionView)
Her gjenbruker vi mye av det du allerede har.

Innhold:

Header med nøkkeldata:

Dato, navn, varighet, snittwatt, snittpuls, etc.

AnalysisPanel:

Watt pr puls (“W per beat”)

Snitt / maks / zoner

TrendsChart for økta:

Hover for å se utvikling i watt og W/HR over tid

Mulighet til å merke økta:

“Er dette en FTP-økt?” [ja/nei / type-tag]

/trends – TrendsPage

Filterseksjon:

Periode (f.eks. siste 4 uker, 3 måneder, 6 måneder, 12 måneder, custom)

Trend 1: FTP avg watt

Bruker kun økter merket “FTP”

Viser utvikling over tid

Trend 2: HR per watt (W/HR)

Bruker alle økter i Rides

Viser effektivitet (lavere W/HR = bedre) el.l.

/goals – GoalsPage

Set FTP goal:

Default = nåværende FTP + 5 % (hvis data)

Hvis ikke data: default basert på alder, vekt, enkle estimater

Set HR/Watt goal:

Liknende logikk: bedre effektivitet

Set deadline(s):

En eller flere datoer

Visualisering:

Kurve i Trends (gjerne gjenbruk av komponent) som viser om brukeren er “on track” mot målet

/profile – ProfilePage

Vise og endre alle profilfelter:

Vekt, høyde, CdA, Crr, FTP, crank efficiency, etc.

Info om hvordan dette påvirker:

Calibration %

Estimated watt accuracy

På sikt: Strava connection / API-key-handtering

2. Komponent-lag (hvilke ting går igjen)

For å gjøre dette ryddig, kan vi dele opp noen “familier” av komponenter:

Layout & språk

AppLayout (header, språkvelger, evt. bruker-meny)

LanguageToggle (NO/EN – styrer en LanguageContext eller lignende)

Auth

LoginForm

SignupForm

Profil / kalibrering

ProfileForm

CalibrationProgressDonut

PrecisionAccuracyDonut

Rides

RidesList

RideCard

RideFilterBar

Analyser

AnalysisPanel

SessionMetricsHeader

TrendsChart (for én økt)

Trender & mål

TrendFilters

TrendChart (for globale trender)

GoalsForm

GoalProgressWidget

Vi trenger ikke lage alle samtidig, men det gir oss en mappe-struktur å styre etter når vi skal “vaske”.

3. Språk (NO/EN)

Alle routes/pages skal være tospråklige.

En enkel strategi:

Egen i18n.ts med:

const messages = {
  no: { login: "Logg inn", ... },
  en: { login: "Log in", ... },
};


LanguageContext som sier lang = "no" | "en".

LanguageToggle (flag-knapper) som bytter lang.

En liten t("login")-helper.

Vi trenger ikke implementere dette nå, men det ligger som designkrav.

4. Hvordan vi bruker dette videre (planen din)

Jeg ville gjort det sånn:

Fase 1 – “Frontend Skeleton & Routes”

Opprette routes i kode etter denne strukturen (med VERY simple content).

Ikke stress med backend ennå – bare knapper, overskrifter, “TODO”-tekst.

Sørge for at navigasjon fungerer mellom:

/, /login, /signup, /calibration, /dashboard, /rides, /rides/:id, /trends, /goals, /profile

Fase 2 – “Koble opp eksisterende sannhet”

Plugg inn det du allerede har:

Nåværende SessionsPage → /rides

Nåværende SessionView + AnalysisPanel + TrendsChart → /rides/:rideId

Da har vi FØRSTE sanne flyt:

Login (fake i starten) → Dashboard → Rides → RideDetail med ekte backend-data

Fase 3 – “Profile + Calibration UI”

Bygg ProfilePage og CalibrationPage

Legg inn de to rundingene og logikk for 75–100 % + 90–98 %

Fase 4 – “Trends & Goals”

Koble eksisterende trend-CSV/backend-data inn i /trends

Legge på goals + visualisering

Alt dette kan vi bryte videre ned i minisprinter som du sier: login først, Rides, Profile/Calibration, Trends, Goals.