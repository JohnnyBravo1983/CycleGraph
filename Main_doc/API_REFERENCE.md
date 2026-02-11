# CycleGraph – API Reference
**Last updated:** 2026-02-11  
**Purpose:** Complete overview of all API endpoints with status and usage

---

## 📋 Endpoint Overview

**Total endpoints:** 24  
**Active files:** 7  
**Duplicates identified:** 4  
**Status:** Needs cleanup (remove duplicates)

---

## 🔐 Authentication Endpoints

### **Local Auth** (`server/routes/auth_local.py`)

#### `POST /api/auth/signup`
**Purpose:** Create new user account  
**Status:** ✅ Active  

**Request:**
```json
{
  "username": "johnny",
  "email": "deg@epost.no",
  "password": "securepass123",
  "full_name": "Johnny Strømøe",
  "bike_name": "Tarmac SL7",
  "gender": "male",
  "country": "Norway",
  "city": "Trondheim",
  "age": 32
}
```

**Response:**
```json
{
  "success": true,
  "uid": "u_WkE6Gs812BbAVGm3AEaiX4",
  "message": "User created"
}
```

**Side effects:**
- Creates `/app/state/users/<uid>/` directory
- Creates `auth.json` with user data
- Initializes `sessions_index.json` as empty array

---

#### `POST /api/auth/login`
**Purpose:** Authenticate user and create session  
**Status:** ✅ Active  

**Request:**
```json
{
  "username": "johnny",
  "password": "securepass123"
}
```

**Response:**
```json
{
  "success": true,
  "uid": "u_WkE6Gs812BbAVGm3AEaiX4"
}
```

**Side effects:**
- Sets `cg_auth` cookie (session token)

---

#### `POST /api/auth/logout`
**Purpose:** End user session  
**Status:** ✅ Active  

**Request:** None (cookie-based)

**Response:**
```json
{
  "success": true,
  "message": "Logged out"
}
```

**Side effects:**
- Clears `cg_auth` cookie

---

#### `GET /api/auth/me`
**Purpose:** Get current user info  
**Status:** ✅ Active  

**Request:** None (cookie-based)

**Response:**
```json
{
  "uid": "u_WkE6Gs812BbAVGm3AEaiX4",
  "username": "johnny",
  "email": "deg@epost.no",
  "full_name": "Johnny Strømøe",
  "strava_connected": true
}
```

---

### **Strava OAuth** (`server/routes/auth_strava.py`)

#### `GET /api/auth/strava/login`
**Purpose:** Initiate Strava OAuth flow  
**Status:** ✅ Active  

**Request:** None

**Response:** Redirect to Strava authorization page

---

#### `GET /api/auth/strava/callback`
**Purpose:** Handle OAuth callback from Strava  
**Status:** ✅ Active  

**Request:** Query params from Strava (code, scope)

**Response:** Redirect to dashboard

**Side effects:**
- Exchanges code for access token
- Saves tokens in `auth.json`
- Updates `strava_tokens` field

---

#### `GET /login` ⚠️
**Purpose:** Legacy Strava login endpoint  
**Status:** ⚠️ Unclear if still used  
**Location:** Line 275 in auth_strava.py

**Note:** May be duplicate of `/api/auth/strava/login`

---

#### `GET /callback` ⚠️
**Purpose:** Legacy Strava callback  
**Status:** ⚠️ Unclear if still used  
**Location:** Line 315 in auth_strava.py

**Note:** May be duplicate of `/api/auth/strava/callback`

---

#### `GET /status` 
**Purpose:** Check Strava connection status  
**Status:** ✅ Active  
**Location:** Line 244 in auth_strava.py

**Response:**
```json
{
  "connected": true,
  "athlete_id": "12345678"
}
```

---

## 👤 Profile Endpoints

### **Profile Management** (`server/routes/profile_router.py`)

#### `GET /api/profile/get`
**Purpose:** Retrieve user profile data  
**Status:** ✅ Active  

**Request:** None (cookie-based)

**Response:**
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
  "ftp_watts": null,
  "profile_version": 1
}
```

**Data source:** `profile.json`

---

#### `PUT /api/profile/save`
**Purpose:** Update user profile  
**Status:** ✅ Active  

**Request:**
```json
{
  "rider_weight_kg": 73,
  "bike_weight_kg": 7.8,
  "cda": 0.290
}
```

**Response:**
```json
{
  "success": true,
  "profile_version": 2
}
```

**Side effects:**
- Updates `profile.json`
- Appends to `profile_versions.jsonl`
- Increments `profile_version`

---

## 🚴 Session Endpoints

### **Session List** (`server/routes/sessions_list_router.py`)

#### `GET /api/sessions/list/all`
**Purpose:** Get all user sessions with metrics  
**Status:** ✅ Active (SSOT-based)  

**Request:** None (cookie-based)

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "s_123",
      "start_date": "2026-02-10T08:00:00Z",
      "distance_km": 45.2,
      "precision_watt_avg": 245,
      "precision_watt_max": 480,
      "duration_seconds": 5400,
      "elevation_gain_m": 650,
      "weather_source": "open-meteo"
    }
  ],
  "count": 1
}
```

**Data source:** `result_<sid>.json` (SSOT)  
**Note:** Does NOT use `sessions_meta.json` as SSOT

---

#### `GET /api/sessions/list/_debug_paths`
**Purpose:** Debug endpoint to inspect file paths  
**Status:** 🔧 Debug only  

**Request:** None

**Response:**
```json
{
  "sessions_index": "/app/state/users/<uid>/sessions_index.json",
  "sessions_meta": "/app/state/users/<uid>/sessions_meta.json",
  "sessions_dir": "/app/state/users/<uid>/sessions/"
}
```

---

### **Session List (DUPLICATE)** (`server/routes/sessions.py`)

#### `GET /api/sessions/list` ⚠️
**Purpose:** List sessions (older implementation?)  
**Status:** ⚠️ DUPLICATE - conflicts with sessions_list_router.py  
**Location:** Line 1121 in sessions.py

**Action needed:** Determine which is current, remove the other

---

### **Session Detail**

#### `GET /api/sessions/{session_id}`
**Purpose:** Get detailed data for single session  
**Status:** ✅ Active  
**Location:** Line 3540 in sessions.py

**Request:** Path param `session_id`

**Response:**
```json
{
  "session_id": "s_123",
  "start_date": "2026-02-10T08:00:00Z",
  "distance_km": 45.2,
  "precision_watt_avg": 245,
  "precision_watt_max": 480,
  "samples": [
    {
      "lat": 63.4305,
      "lon": 10.3951,
      "elevation_m": 50,
      "speed_ms": 8.5,
      "watt": 250
    }
  ],
  "weather": {
    "source": "open-meteo",
    "temperature_c": 15,
    "wind_speed_ms": 5.2
  }
}
```

**Data source:** `result_<sid>.json`

---

### **Session Analysis**

#### `POST /api/sessions/{sid}/analyze`
**Purpose:** Re-run analysis on existing session  
**Status:** ✅ Active  
**Location:** Line 2016 in sessions.py

**Request:** Path param `sid`

**Response:**
```json
{
  "success": true,
  "session_id": "s_123",
  "precision_watt_avg": 245,
  "analysis_timestamp": "2026-02-11T12:00:00Z"
}
```

**Side effects:**
- Reads `session_<sid>.json`
- Re-runs Rust engine
- Updates `result_<sid>.json`
- Updates `sessions_meta.json`

---

#### `POST /api/sessions/{sid}/analyze_sessionspy` 🔧
**Purpose:** Debug/alternate analysis endpoint  
**Status:** 🔧 Debug or legacy?  
**Location:** Line 3504 in sessions.py

**Action needed:** Clarify if this is debug-only or production

---

#### `POST /api/sessions/debug/rb` 🔧
**Purpose:** Debug endpoint for rebuild/reanalysis  
**Status:** 🔧 Debug only  
**Location:** Line 1722 in sessions.py

---

## 🔄 Strava Import Endpoints

### **Import (Current)** (`server/routes/strava_import_router.py`)

#### `POST /api/strava/sync`
**Purpose:** Fetch list of activities from Strava  
**Status:** ✅ Active  

**Request:**
```json
{
  "limit": 50,
  "after": "2026-01-01T00:00:00Z"
}
```

**Response:**
```json
{
  "activities": [
    {
      "id": "10876543210",
      "name": "Morning Ride",
      "distance": 45231.2,
      "start_date": "2026-02-10T08:00:00Z"
    }
  ],
  "count": 1
}
```

**Side effects:** None (just fetches list, doesn't import)

---

#### `POST /api/strava/import/{rid}`
**Purpose:** Import single activity and analyze  
**Status:** ✅ Active  

**Request:** Path param `rid` (Strava activity ID)

**Response:**
```json
{
  "success": true,
  "session_id": "s_123",
  "precision_watt_avg": 245
}
```

**Side effects:**
1. Fetch full activity data from Strava
2. Save to `session_<sid>.json`
3. Fetch weather data
4. Run analysis (Rust engine)
5. Save to `result_<sid>.json`
6. Update `sessions_index.json`
7. Update `sessions_meta.json`

---

### **Import (Duplicate?)** (`server/routes/strava_import_router_for_commit.py`)

#### `POST /api/strava/sync` ⚠️
**Purpose:** Same as above  
**Status:** ⚠️ DUPLICATE  
**Location:** Line 629 in strava_import_router_for_commit.py

**Action needed:** Determine which file is current

---

#### `POST /api/strava/import/{rid}` ⚠️
**Purpose:** Same as above  
**Status:** ⚠️ DUPLICATE  
**Location:** Line 925 in strava_import_router_for_commit.py

**Action needed:** Determine which file is current

---

## 📊 Summary of Issues

### **Duplicate Routes (High Priority)**

| Route | File 1 | File 2 | Action |
|---|---|---|---|
| `/api/sessions/list` | sessions.py (L1121) | sessions_list_router.py (L1075) | ⚠️ Keep sessions_list_router.py (SSOT-based) |
| `/api/strava/sync` | strava_import_router.py (L761) | strava_import_router_for_commit.py (L629) | ⚠️ Determine current |
| `/api/strava/import/{rid}` | strava_import_router.py (L1090) | strava_import_router_for_commit.py (L925) | ⚠️ Determine current |

---

### **Legacy/Unclear Routes**

| Route | Location | Status |
|---|---|---|
| `/login` | auth_strava.py (L275) | ⚠️ Legacy? Use `/api/auth/strava/login` instead? |
| `/callback` | auth_strava.py (L315) | ⚠️ Legacy? Use `/api/auth/strava/callback` instead? |
| `/api/sessions/{sid}/analyze_sessionspy` | sessions.py (L3504) | 🔧 Debug only? |
| `/api/sessions/debug/rb` | sessions.py (L1722) | 🔧 Debug only |
| `/api/sessions/list/_debug_paths` | sessions_list_router.py (L1170) | 🔧 Debug only |

---

## 🔧 Recommended Actions

### **1. Remove duplicate routes**
**Priority:** HIGH  
**Timeline:** Before March 1

**Steps:**
1. Confirm which `strava_import_router` file is current
2. Delete the other file
3. Remove `/api/sessions/list` from `sessions.py`
4. Keep only `sessions_list_router.py` version

---

### **2. Clarify legacy routes**
**Priority:** MEDIUM  
**Timeline:** Can be done after MVP

**Steps:**
1. Check if `/login` and `/callback` are still used
2. If not, remove them
3. If yes, document why they exist alongside `/api/auth/strava/*`

---

### **3. Mark debug endpoints**
**Priority:** LOW  
**Timeline:** Documentation only

**Steps:**
1. Add `_debug` prefix to debug endpoints
2. Document in code comments
3. Optionally: disable in production

---

## 🎯 Production API Contract (Post-Cleanup)

After cleanup, this should be the final API:

### **Auth**
```
POST   /api/auth/signup
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/me
GET    /api/auth/strava/login
GET    /api/auth/strava/callback
GET    /api/auth/strava/status
```

### **Profile**
```
GET    /api/profile/get
PUT    /api/profile/save
```

### **Sessions**
```
GET    /api/sessions/list/all
GET    /api/sessions/{session_id}
POST   /api/sessions/{sid}/analyze
```

### **Strava**
```
POST   /api/strava/sync
POST   /api/strava/import/{rid}
```

**Total:** 14 production endpoints (clean)

---

## 📝 Notes

- This document reflects actual endpoints found in codebase
- Duplicates marked with ⚠️ need resolution
- Debug endpoints marked with 🔧 should be documented or removed
- After cleanup, update this document

**Next review:** After duplicate removal (before March 1)
