# CycleGraph – System Architecture
**Last updated:** 2026-02-11  
**Purpose:** Explain how the system actually works - data flow, storage, SSOT rules

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  React + Vite + TypeScript (Vercel)                         │
│  - Signup/Login                                              │
│  - Onboarding (profile setup)                                │
│  - Dashboard (profile display)                               │
│  - Rides List                                                │
│  - Session View                                              │
│  - Trend Analysis (planned: March 2026)                      │
│  - Set Goals (planned: March 2026)                           │
│  - Leaderboards (planned: April 2026)                        │
│  - Forum (planned: May 2026)                                 │
└────────────────┬────────────────────────────────────────────┘
                 │ HTTP/REST
                 │
┌────────────────▼────────────────────────────────────────────┐
│                      BACKEND API                             │
│  Python FastAPI (Fly.io)                                     │
│  - Auth (local + Strava OAuth)                               │
│  - Profile management                                        │
│  - Strava import                                             │
│  - Analysis orchestration                                    │
│  - Session list/detail                                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ├──────────────────┬─────────────────────────┐
                 │                  │                         │
         ┌───────▼──────┐   ┌──────▼──────┐   ┌─────────▼──────┐
         │  File State  │   │ Rust Engine │   │  Strava API    │
         │  (per user)  │   │   (PyO3)    │   │   (OAuth)      │
         │              │   │             │   │                │
         │ auth.json    │   │ Physics     │   │ GET /athlete/  │
         │ sessions/    │   │ Watt calc   │   │     activities │
         │ results/     │   │ Deterministic│   │                │
         └──────────────┘   └─────────────┘   └────────────────┘
```

---

## 📂 File System Structure (SSOT Model)

### **Per-User State Directory**

```
/app/state/users/<uid>/
    auth.json                     # User credentials + OAuth tokens
    profile.json                  # ← NEW (to be implemented)
    sessions_index.json           # ✅ SSOT: Which sessions exist
    sessions_meta.json            # ⚠️ Derived cache (regenerate-able)
    sessions/
        session_<sid>.json        # Raw Strava data + GPS samples
        result_<sid>.json         # ✅ SSOT: Analysis results
```

### **File Ownership & SSOT Rules**

| File | Role | Can Regenerate? | SSOT? |
|---|---|---|---|
| `auth.json` | User credentials, Strava tokens | ❌ No | ✅ Yes |
| `profile.json` | User profile (weight, bike, FTP) | ❌ No | ✅ Yes |
| `sessions_index.json` | List of session IDs | ❌ No | ✅ Yes |
| `session_<sid>.json` | Raw ride data from Strava | ❌ No | ✅ Yes |
| `result_<sid>.json` | Analysis output (watt, weather) | ✅ Yes* | ✅ Yes |
| `sessions_meta.json` | Display metadata cache | ✅ Yes | ❌ No |

*Can regenerate by re-running analysis on `session_<sid>.json`

---

## 👤 Profile System Architecture

### **Current State (as of Feb 2026)**

Profile data is split across **3 stages:**

#### **Stage 1: Signup (`auth.json`)**
```json
{
  "uid": "u_WkE6Gs812BbAVGm3AEaiX4",
  "username": "johnny",
  "email": "deg@epost.no",
  "full_name": "Johnny Strømøe",
  "bike_name": "Tarmac SL7",
  "gender": "male",
  "country": "Norway",
  "city": "Trondheim",
  "age": 32,
  "created_at": "2026-02-11T10:00:00Z",
  "strava_tokens": { ... }
}
```

**What's stored here:**
- Identity (username, email)
- Basic info (full name, bike name, gender, location, age)
- Auth tokens

**New fields for leaderboards/profile:**
- `gender` - "male" | "female" 
- `country` - For leaderboard filtering
- `city` - For local leaderboards
- `age` - For age-group categories

**What's missing:**
- Weight
- Bike specs
- Physical parameters

---

#### **Stage 2: Onboarding (`profile.json` via `/api/profile/save`)**

**CONFIRMED:** Onboarding data is stored in `state/users/<uid>/profile.json`

```json
{
  "rider_weight_kg": 75,
  "bike_weight_kg": 8,
  "cda": 0.300,
  "crr": 0.0040,
  "crank_efficiency": 0.96,
  "bike_type": "road",
  "tire_width_mm": 28,
  "tire_quality": "performance",
  "device": "strava",
  "ftp_watts": null,
  "profile_version": 1,
  "updated_at": "2026-02-11T11:00:00Z"
}
```

**Versioning:** Handled by `server/utils/versioning.py`
- Current profile: `profile.json`
- Version history: `profile_versions.jsonl` (append-only audit log)

**Critical fields for analysis:**
- `rider_weight_kg` - Used in watt calculation
- `bike_weight_kg` - Used in watt calculation
- `cda` - Aerodynamic drag coefficient
- `crr` - Rolling resistance coefficient

**Separation of concerns:**
- `auth.json` → Authentication + identity
- `profile.json` → Physical parameters for analysis

---

#### **Stage 3: Dashboard Profile (NOT IMPLEMENTED)**

**Current problem:** Dashboard doesn't show or allow editing profile data.

**What should happen:**
1. Dashboard reads `profile.json`
2. User can edit weight, bike specs, etc.
3. On save → new `profile_version` created
4. Old rides keep old profile version
5. New rides use new profile version

---

### **Profile Versioning (Critical for Determinism)**

**Why needed:**
- User changes weight from 80kg → 75kg
- Old rides should NOT retroactively change
- New rides should use new weight

**CONFIRMED APPROACH: Option A - Profile Snapshots**

**Implementation:**
```
/app/state/users/<uid>/
    profile.json              # Current active profile
    profile_versions.jsonl    # Append-only audit log of all changes
```

**How it works:**
1. User updates profile (e.g., changes weight)
2. New entry appended to `profile_versions.jsonl`:
   ```json
   {"version": 2, "timestamp": "2026-02-11T12:00:00Z", "rider_weight_kg": 75, "bike_weight_kg": 8, ...}
   ```
3. `profile.json` updated with new values
4. New rides reference `profile_version: 2`
5. Old rides keep `profile_version: 1`

**Versioning handled by:** `server/utils/versioning.py`

Each `result_<sid>.json` stores which version was used:
```json
{
  "session_id": "s_123",
  "profile_version": 2,
  "profile_snapshot": {
    "rider_weight_kg": 75,
    "bike_weight_kg": 8,
    "cda": 0.300,
    "crr": 0.0040
  },
  "precision_watt_avg": 245,
  ...
}
```

**Key principle:** Profile snapshot embedded in result ensures determinism even if `profile_versions.jsonl` is lost.

---

## 🔄 Data Flow Diagrams

### **1. User Signup Flow**

```
User fills signup form
    ↓
POST /api/auth/signup
    ↓
Create user directory: /app/state/users/<uid>/
    ↓
Save auth.json (username, email, full_name, bike_name)
    ↓
Initialize sessions_index.json = []
    ↓
Redirect to /onboarding
```

---

### **2. Onboarding Flow**

```
User fills onboarding form (weight, bike specs, etc.)
    ↓
POST /api/profile/save (or similar)
    ↓
Save profile.json (or merge into auth.json?)
    ↓
Redirect to /dashboard
    ↓
Show "Connect to Strava" button
```

**Current issue:** Onboarding data storage location is unclear.

---

### **3. Strava Import Flow**

```
User clicks "Connect to Strava"
    ↓
GET /api/auth/strava/login
    ↓
Redirect to Strava OAuth
    ↓
User authorizes
    ↓
GET /api/auth/strava/callback
    ↓
Save Strava tokens in auth.json
    ↓
POST /api/strava/sync
    ↓
Fetch rides from Strava API
    ↓
For each ride:
    POST /api/strava/import/{rid}
        ↓
        Save session_<sid>.json (raw data)
        ↓
        Trigger analysis
        ↓
        Save result_<sid>.json (watt + weather)
        ↓
        Update sessions_index.json
```

---

### **4. Analysis Flow (Core Value)**

```
Input: session_<sid>.json + profile.json
    ↓
Read GPS samples (lat, lon, elevation, speed)
    ↓
Fetch weather data (if not cached)
    ↓
Call Rust engine via PyO3:
    - rider_weight_kg
    - bike_weight_kg
    - cda, crr, crank_efficiency
    - GPS samples
    - Weather (temp, pressure, humidity, wind)
    ↓
Rust calculates power (watts) for each sample
    ↓
Aggregate metrics:
    - precision_watt_avg
    - precision_watt_max
    - distance_km
    - elevation_gain_m
    - duration_seconds
    ↓
Save result_<sid>.json
    ↓
Update sessions_meta.json (cache)
```

**Determinism guarantee:**
- Same inputs → same outputs
- No randomness
- Pure physics model

---

### **5. Rides List Display Flow**

```
Frontend: GET /api/sessions/list/all
    ↓
Backend reads sessions_index.json
    ↓
For each session_id:
    Read result_<sid>.json (SSOT)
    ↓
    Extract display fields:
        - distance_km
        - precision_watt_avg
        - duration_seconds
        - elevation_gain_m
        - weather_source
        - start_date
    ↓
Return array of rides
    ↓
Frontend displays in table
```

**Key principle:** Always read from `result_<sid>.json`, never from cache.

---

### **6. Profile Update Flow (TO BE IMPLEMENTED)**

```
User opens Dashboard → Profile section
    ↓
Frontend: GET /api/profile/get
    ↓
Backend reads profile.json
    ↓
Display current values (weight, bike specs, etc.)
    ↓
User changes weight: 80kg → 75kg
    ↓
Frontend: PUT /api/profile/save
    ↓
Backend:
    1. Read current profile.json
    2. Create snapshot: profile_v2.json (if using Option A)
    3. Update profile.json with new values
    4. Increment profile_version
    ↓
New rides will use profile_v2
Old rides still reference profile_v1 (embedded or snapshot)
```

---

## 🔐 Authentication Architecture

### **Two Auth Methods**

#### **1. Local Auth (username/password)**
- Endpoint: `POST /api/auth/signup`, `POST /api/auth/login`
- Cookie: `cg_auth` (JWT or session ID)
- Storage: `auth.json` with hashed password

#### **2. Strava OAuth**
- Endpoint: `GET /api/auth/strava/login` → `GET /api/auth/strava/callback`
- Flow: Standard OAuth 2.0
- Storage: `auth.json` with `strava_tokens`

```json
{
  "strava_tokens": {
    "access_token": "abc123...",
    "refresh_token": "def456...",
    "expires_at": 1234567890
  }
}
```

### **Cookie-based Session Management**
- Cookie name: `cg_auth`
- Sent with every API request
- Backend validates and extracts `uid`
- Used to load user state from `/app/state/users/<uid>/`

---

## 🧮 Rust Physics Engine (Core IP)

### **What it does:**
- Calculates instantaneous power (watts) for each GPS sample
- Pure physics: no ML, no guessing

### **Inputs:**
```python
calculate_power(
    speed_ms: float,
    gradient: float,           # From elevation delta
    rider_weight_kg: float,
    bike_weight_kg: float,
    cda: float,                # Aerodynamic drag
    crr: float,                # Rolling resistance
    air_density: float,        # From weather
    wind_speed_ms: float,      # From weather
    wind_direction_deg: float, # From weather
    crank_efficiency: float
) -> float  # Returns watts
```

### **Integration:**
- Rust compiled as Python extension via PyO3
- Called from Python backend
- Zero overhead (direct function call)

### **Why Rust:**
- Performance: process 1000s of GPS samples quickly
- Determinism: no floating-point drift
- Type safety: catch bugs at compile time

---

## 🌦️ Weather Data Integration

### **Why needed:**
- Air density affects drag (hot air = less drag)
- Wind affects effective speed
- Critical for accurate watt calculation

### **Data sources:**
- Primary: Open-Meteo API (free, historical weather)
- Fallback: Standard atmosphere model

### **Caching strategy:**
- Weather fetched once per ride
- Stored in `result_<sid>.json` under `weather` key
- Never re-fetch (historical data doesn't change)

```json
{
  "weather": {
    "source": "open-meteo",
    "temperature_c": 15,
    "pressure_hpa": 1013,
    "humidity_percent": 60,
    "wind_speed_ms": 5.2,
    "wind_direction_deg": 180
  }
}
```

---

## 🔄 Meta Generation (Cache Layer)

### **What is `sessions_meta.json`?**
- Derived cache for UI display
- Aggregates data from multiple `result_<sid>.json` files
- Can be regenerated at any time

### **DECISION: Keep `sessions_meta.json` as derived cache**

**Why keep it:**
- Already in active use across multiple routers
- Reduces IO when listing rides
- Prevents need for Strava API fallback on every list operation
- Removing it now increases regression risk

**Rules for using meta:**
1. ✅ Use for list views (performance optimization)
2. ❌ Never use as SSOT (always defer to `result_<sid>.json`)
3. ✅ Regenerate when results change
4. ❌ Never store data that isn't in result files

**SSOT hierarchy:**
- `sessions_index.json` → Which sessions exist
- `result_<sid>.json` → Metrics for each session
- `sessions_meta.json` → Cache (aggregated view of results)

**Consolidation task:**
- Meta generation logic is currently spread across files
- Need to centralize into single utility function
- Call explicitly when results are updated

---

## 🚨 SSOT Principles (Sacred Rules)

### **Rule 1: One source of truth per data type**
- `sessions_index.json` → Which sessions exist
- `result_<sid>.json` → Metrics for session `sid`
- `profile.json` → Current user profile

### **Rule 2: Never duplicate data**
- If data exists in result file, don't copy to meta
- If data exists in profile, don't copy to session

### **Rule 3: Cache must be regenerate-able**
- If you delete `sessions_meta.json`, system still works
- Cache is for performance, not correctness

### **Rule 4: Analysis is deterministic**
- Same input → same output
- Re-running analysis produces identical `result_<sid>.json`

---

## 📊 API Structure Overview

### **Auth Routes** (`auth_local.py`, `auth_strava.py`)
```
POST   /api/auth/signup
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/me
GET    /api/auth/strava/login
GET    /api/auth/strava/callback
```

### **Profile Routes** (`profile_router.py`)
```
GET    /api/profile/get
PUT    /api/profile/save
```

### **Session Routes** (`sessions_list_router.py`)
```
GET    /api/sessions/list/all          # List all rides (SSOT)
GET    /api/sessions/{session_id}      # Get single ride detail
POST   /api/sessions/{sid}/analyze     # Re-run analysis
```

### **Strava Import Routes** (`strava_import_router.py`)
```
POST   /api/strava/sync                # Fetch rides from Strava
POST   /api/strava/import/{rid}        # Import single ride + analyze
```

### **Duplicate Routes (TO BE RESOLVED)**
```
⚠️ /api/sessions/list exists in:
   - sessions.py (legacy?)
   - sessions_list_router.py (current?)

⚠️ /api/strava/sync and /api/strava/import/{rid} exist in:
   - strava_import_router.py
   - strava_import_router_for_commit.py
```

**Action needed:** Decide which to keep, remove duplicates.

---

## 🎯 Key Design Decisions

### **1. File-based state (not database)**
**Why:**
- Simplicity: no DB migrations
- Transparency: can inspect files directly
- Portability: easy to backup/restore
- Per-user isolation: natural sharding

**Trade-off:**
- Slower for large user counts
- Manual index management

**Future:** Can migrate to DB without changing API contracts.

---

### **2. Deterministic physics model (not ML)**
**Why:**
- Reproducible results
- No training data needed
- Explainable (users can see why watt is X)
- No drift over time

**Trade-off:**
- Less accurate than calibrated power meter
- Assumes ideal conditions (rider position, etc.)

**Value prop:** "Good enough" watt estimate without buying hardware.

---

### **3. Cookie-based auth (not JWT in header)**
**Why:**
- Simpler frontend (no token management)
- Secure (HttpOnly cookie)
- Works with browser auto-login

**Trade-off:**
- CSRF protection needed
- Not ideal for mobile app (would need token auth)

---

## 🔮 Planned Architecture Changes

### **Short-term (for MVP):**
1. **Profile in Dashboard** - implement display + edit
2. **Profile versioning** - decide on Option A or B
3. **Remove duplicate routes** - clean up API
4. **Consolidate meta generation** - or remove entirely

### **Medium-term (post-MVP):**
1. **Auto-sync from Strava** - webhook integration
2. **Segment detection** - for leaderboards
3. **Trend analysis** - time-series queries on results

### **Long-term (scale):**
1. **Migrate to database** - PostgreSQL or SQLite
2. **Caching layer** - Redis for meta/aggregates
3. **Background workers** - Celery for async analysis

---

## 📝 Resolved Questions

1. ✅ **Where does onboarding data go?**
   - ANSWER: `profile.json` via `/api/profile/save`
   - `auth.json` is for authentication only

2. ✅ **Profile versioning approach?**
   - ANSWER: Option A - Snapshots in `profile_versions.jsonl`
   - Handled by `server/utils/versioning.py`

3. ✅ **Meta generation - keep or remove?**
   - ANSWER: Keep as derived cache
   - Consolidate generation logic to single utility
   - Never use as SSOT

## 📝 Remaining Open Questions

1. **Auto-sync architecture?**
   - Webhook from Strava?
   - Polling?
   - Background worker?
   - Timeline: After MVP (manual import is OK for March 1)

2. **Segment detection for leaderboards?**
   - How to identify matching segments across rides?
   - GPS-based matching? Strava segment IDs?
   - Timeline: April 2026

---

## ✍️ Notes

- This document reflects the *intended* architecture
- Some parts may not match current implementation
- Use this as guide for refactoring
- Update as system evolves

**Next steps:**
1. Audit current code to confirm profile storage location
2. Decide on profile versioning approach
3. Implement Dashboard profile display/edit
4. Remove duplicate API routes
