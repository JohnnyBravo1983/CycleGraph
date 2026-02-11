# Day 1 - Tirsdag 11. Februar 2026
**Sprint:** Pioneer Beta (11. feb - 1. mars 2026)  
**Oppgave:** Signup-forbedring - Demografiske felt  
**Prioritet:** 🔴 Kritisk

---

## 📋 DEL 1: OPPSTART (Paste dette i ChatGPT når du starter dagen)

### **Prosjektkontekst:**
Jeg jobber på Day 1 av en 18-dagers sprint for CycleGraph Pioneer Beta.

**Om CycleGraph:**
- Sykkelanalyseplattform som estimerer watt uten fysisk wattmåler
- Backend: Python FastAPI + Rust fysikkmotor (PyO3)
- Frontend: React + TypeScript + Vite
- Data: Filbasert lagring (ingen database), SSOT-modell
- Deploy: Fly.io (backend) + Vercel (frontend)

**Viktige SSOT-regler:**
- `auth.json` → Brukeridentitet + demografisk data
- `profile.json` → Fysiske parametere (vekt, sykkel, CdA, Crr)
- `result_<sid>.json` → Analyseresultater (SSOT for metrics)
- `sessions_index.json` → Hvilke økter som finnes
- `sessions_meta.json` → Avledet cache (kan regenereres)

---

### **Dagens oppgave (Day 1):**

**Mål:** Brukere kan registrere seg med komplett profil (kjønn, land, by, alder)

**Oppgaver:**
1. Legg til 4 nye felt i signup-skjema:
   - Kjønn (dropdown: male/female)
   - Land (tekst-input)
   - By (tekst-input)
   - Alder (tall-input, min 13, max 100)
2. Oppdater frontend-validering
3. Oppdater `POST /api/auth/signup` backend-endpoint
4. Lagre data i `auth.json`
5. Test: Opprett ny bruker, verifiser at feltene lagres

**Leveranse:** Nye brukere har komplett demografisk profil  
**Tidsestimat:** 4-5 timer  
**Blokkere:** Ingen

---

### **Filer som skal endres:**
- `server/routes/auth_local.py` - Backend signup-endpoint
- `client/src/pages/Signup.tsx` - Signup-skjema UI
- `client/src/types/User.ts` - Type-definisjoner for bruker
- `server/state/users/<uid>/auth.json` - Hvor data lagres

---

### **Suksesskriterier:**
- [ ] Signup-skjema har 4 nye felt
- [ ] Feltene er påkrevd (kan ikke hoppes over)
- [ ] Data lagres i `auth.json`
- [ ] Gamle brukere fungerer fortsatt (bakoverkompatibelt)

**Testing:**
- [ ] Koden kjører uten feil
- [ ] Fungerer i Chrome + Firefox
- [ ] Ingen console errors
- [ ] Committet til git

---

### **Hva ble gjort i går (Day 0):**
- Dokumentasjon gjennomgått og organisert
- Sprint backlog ferdigstilt
- Utviklingsmiljø verifisert
- Main_Document mappe opprettet med alle dokumenter
- Klar til å starte koding

**Hva dette bygger på:**
Eksisterende signup-skjema har username, email, password. Vi legger til demografiske felt som trengs for leaderboards i April.

---

**Jeg starter nå med signup-skjemaet. Klar til å jobbe gjennom dette sammen?**

---

## 📝 DEL 2: ARBEIDSLOGG (Fyll ut underveis i løpet av dagen)

### **Startet:** 09:00

**Første tanker:**
- Signup.tsx ligger i client/src/pages/
- Må finne riktig plass å legge til feltene
- Trenger å oppdatere TypeScript-typer først

---

### **09:15 - Startet med TypeScript-typer**

**Hva jeg gjør:**
Oppdaterer `client/src/types/User.ts` med nye felt

**Kode endret:**
```typescript
export interface User {
  uid: string;
  username: string;
  email: string;
  full_name: string;
  bike_name: string;
  // NYE FELT:
  gender: 'male' | 'female';
  country: string;
  city: string;
  age: number;
  created_at: string;
}
```

**Status:** ✅ Typer oppdatert, TypeScript compiler fornøyd

---

### **09:45 - Frontend signup-skjema**

**Hva jeg gjør:**
Legger til 4 nye felt i Signup.tsx

**Endringer:**
- Lagt til gender dropdown (male/female)
- Lagt til country text input
- Lagt til city text input  
- Lagt til age number input (min=13, max=100)
- Oppdatert form state
- Lagt til validering

**Kode snippet:**
```tsx
<select name="gender" required>
  <option value="">Velg kjønn</option>
  <option value="male">Mann</option>
  <option value="female">Kvinne</option>
</select>

<input 
  type="number" 
  name="age" 
  min="13" 
  max="100" 
  required 
  placeholder="Alder"
/>
```

**Status:** ✅ Frontend-skjema ferdig, ser bra ut

---

### **10:30 - Backend endpoint-oppdatering**

**Hva jeg gjør:**
Oppdaterer `POST /api/auth/signup` i `server/routes/auth_local.py`

**Endringer:**
- Endpoint aksepterer nå gender, country, city, age
- Validering: age må være 13-100
- Validering: gender må være 'male' eller 'female'
- Data lagres i auth.json

**Kode snippet:**
```python
@router.post("/api/auth/signup")
async def signup(
    username: str,
    email: str,
    password: str,
    full_name: str,
    bike_name: str,
    gender: str,      # NYT
    country: str,     # NYT
    city: str,        # NYT
    age: int          # NYT
):
    # Validering
    if age < 13 or age > 100:
        raise HTTPException(400, "Age must be 13-100")
    if gender not in ['male', 'female']:
        raise HTTPException(400, "Invalid gender")
    
    # Lagre i auth.json
    user_data = {
        "uid": uid,
        "username": username,
        "email": email,
        "full_name": full_name,
        "bike_name": bike_name,
        "gender": gender,
        "country": country,
        "city": city,
        "age": age,
        "created_at": datetime.now().isoformat()
    }
    
    save_auth(uid, user_data)
```

**Status:** ✅ Backend ferdig

---

### **11:30 - Testing**

**Test 1: Opprett ny bruker**
- ✅ Skjema viser alle felt
- ✅ Validering fungerer (kan ikke sende uten å fylle ut)
- ✅ Data sendes til backend

**Test 2: Verifiser lagring**
- ✅ Sjekket `state/users/<uid>/auth.json`
- ✅ Alle nye felt er lagret
- ✅ Riktig format

**Test 3: Bakoverkompatibilitet**
- ✅ Gamle brukere kan fortsatt logge inn
- ✅ Ingen feil i console
- ✅ Systemet håndterer brukere uten nye felt

**Test 4: Cross-browser**
- ✅ Chrome: Fungerer perfekt
- ✅ Firefox: Fungerer perfekt

---

### **12:15 - Blokkere oppdaget**

**Problem:** Ingen (alt gikk smooth!)

---

### **12:30 - Commit og push**

**Commits:**
```bash
git add .
git commit -m "Add demographic fields to signup (gender, country, city, age)"
git push origin main
```

**Endrede filer:**
- `client/src/types/User.ts`
- `client/src/pages/Signup.tsx`
- `server/routes/auth_local.py`

---

### **Fullført:** 12:30

**Total tid brukt:** 3.5 timer (bedre enn estimert 4-5 timer!)

---

## 📊 DEL 3: AVSLUTNINGSRAPPORT (Paste dette til ChatGPT når dagen er ferdig)

### **Hva ble fullført:**
- [x] Lagt til 4 nye felt i signup-skjema (gender, country, city, age)
- [x] Oppdatert TypeScript-typer
- [x] Oppdatert frontend-validering
- [x] Oppdatert backend endpoint
- [x] Data lagres korrekt i auth.json
- [x] Testet med ny bruker
- [x] Verifisert bakoverkompatibilitet
- [x] Cross-browser testing (Chrome + Firefox)
- [x] Committet til git

---

### **Hva fungerer:**
- Signup-skjema viser 4 nye felt
- Frontend-validering: alder 13-100, kjønn påkrevd
- Backend validerer input korrekt
- Data lagres i `auth.json` med riktig struktur
- Gamle brukere kan fortsatt logge inn
- Ingen console errors
- Fungerer i Chrome og Firefox

---

### **Hva fungerer ikke ennå:**
- Ingenting! Alt fungerer som forventet ✅

---

### **Filer endret:**
```
client/src/types/User.ts
client/src/pages/Signup.tsx
server/routes/auth_local.py
```

---

### **Commits:**
```
abc1234 - Add demographic fields to signup (gender, country, city, age)
```

---

### **Testresultater:**
- [x] Unit tests: N/A (ingen tests skrevet ennå)
- [x] Manual testing: ✅ Alt fungerer
- [x] Browser compatibility: ✅ Chrome + Firefox OK
- [x] Committed to git: ✅

---

### **Validering mot suksesskriterier:**
- [x] Signup-skjema har 4 nye felt ✅
- [x] Feltene er påkrevd ✅
- [x] Data lagres i auth.json ✅
- [x] Gamle brukere fungerer fortsatt ✅

**Status: Day 1 fullført! 🎉**

---

## 🔄 HANDOVER TIL DAY 2 (Denne teksten brukes i morgendagens oppstart)

### **Hva som skal fortsette i morgen:**
Ingenting - Day 1 er 100% ferdig.

---

### **Hva som starter i morgen (Day 2):**

**Oppgave:** Profile i Dashboard - Del 1 (Visning)

**Mål:** Brukere kan SE sin profil i Dashboard

**Oppgaver:**
1. Lag Profile-seksjon i Dashboard UI
2. Legg til "Profile"-fane i navigasjon
3. Les profildata via `GET /api/profile/get`
4. Vis nåværende verdier:
   - Ryttervekt, sykkelvekt
   - CdA, Crr, crank efficiency
   - Sykkeltype, dekk-specs
   - FTP (hvis eksisterer)
5. Vis profile version number
6. Style det pent (matcher Dashboard-estetikk)

**Filer som skal endres:**
- `client/src/pages/Dashboard.tsx`
- `client/src/components/ProfileCard.tsx` (ny fil)
- `server/routes/profile_router.py` (verifiser at GET fungerer)

---

### **Notater for morgendagens sesjon:**

**Viktig å huske:**
- `auth.json` inneholder nå demografiske felt (gender, country, city, age)
- `profile.json` inneholder fysiske parametere (weight, bike, CdA, Crr) - DETTE skal vises i Dashboard
- Hvis bruker ikke har gjort onboarding ennå → vis "No profile yet"
- Endpoint `GET /api/profile/get` eksisterer allerede (fra tidligere sprint)

**Hva dette bygger på:**
Day 1 la til demografiske felt i signup. Day 2 viser fysiske parametere fra profile.json. Dette er to forskjellige filer og formål.

**Potensielle utfordringer:**
- Profile kan være tom hvis bruker ikke har gjort onboarding
- Må håndtere dette gracefully i UI
- Vise tydelig "Complete your profile" melding

---

### **Bugs funnet:**
Ingen bugs funnet i dag! ✅

---

### **Lærdommer:**

**Hva gikk bra:**
- TypeScript-typer først gjorde resten enklere
- Frontend + backend samtidig fungerte fint
- Estimert 4-5 timer, faktisk 3.5 timer

**Hva var vanskeligere enn forventet:**
- Ingenting - alt gikk smooth!

**Bedre tilnærming neste gang:**
- Fortsett med samme approach (typer først, deretter UI, deretter backend)

**Teknisk gjeld skapt:**
- Ingen! Clean implementation ✅

---

**Status:** ✅ Ferdig  
**Klar for QA:** Ja  
**Merge til main:** Ja (allerede pushet)

---

## 🎯 Trenger Claude-review?

**Trenger dette Claude-review før vi fortsetter?**
- [ ] Ja - Arkitekturbeslutning tatt
- [ ] Ja - Stor refaktorering gjort
- [ ] Ja - Blokkere møtt
- [x] Nei - Rett fram implementasjon

**Hvis ja, spørsmål til Claude:**
N/A

---

**Day 1 fullført! Klar for Day 2 i morgen. 🚀**
