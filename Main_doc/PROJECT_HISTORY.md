# CycleGraph – Project History
**Archive created:** 2026-02-11  
**Purpose:** Historical record of how the project evolved from concept to current state

---

## 📜 Project Overview

**Start date:** ~October 2025  
**Current phase:** MVP preparation (18 days to Pioneer Beta launch)  
**Total development time:** ~4 months

---

## 🎯 Project Vision

Build a cycling analysis platform that estimates precision watt without a physical power meter, by combining:
- Strava GPS data
- Physics-based modeling
- Weather data integration
- Deterministic calculation engine (Rust)

**Dual purpose:**
1. Real product for cyclists
2. Technical showcase for job applications

---

## 📊 Development Phases (from Dynamisk DoD)

### **Phase 1: Foundation & Setup**
**Timeline:** October 2025  
**Status:** ✅ Complete

**Achievements:**
- Project structure established
- Basic FastAPI backend
- React frontend with Vite
- Local authentication system
- File-based state management

**Key decisions:**
- File-based storage (not database)
- Cookie-based auth (`cg_auth`)
- Per-user directory structure

---

### **Phase 2: Strava Integration**
**Timeline:** November 2025  
**Status:** ✅ Complete

**Achievements:**
- Strava OAuth flow implemented
- Token management (access + refresh)
- Activity import from Strava API
- Raw data storage in `session_<sid>.json`

**Challenges:**
- Token expiry handling
- Rate limiting from Strava API
- Large activity payloads

**Key files created:**
- `auth_strava.py` - OAuth flow
- `strava_import_router.py` - Import logic

---

### **Phase 3: Analysis Engine (Rust)**
**Timeline:** December 2025  
**Status:** ✅ Complete

**Achievements:**
- Rust physics engine via PyO3
- Watt calculation from GPS + elevation + speed
- Aerodynamic modeling (CdA)
- Rolling resistance (Crr)
- Crank efficiency integration

**Physics model inputs:**
- Rider weight
- Bike weight
- Speed, gradient, elevation
- Air density (from weather)
- Wind speed/direction

**Key principle:** Deterministic - same input always produces same output

---

### **Phase 4: Weather Integration & Stabilization**
**Timeline:** Late December 2025 - January 2026  
**Status:** ✅ Complete

**From Backend Analyzer Stability Log:**

**Major milestones:**
1. Weather data fetching from Open-Meteo API
2. Caching weather in `result_<sid>.json`
3. Fallback to standard atmosphere if API fails
4. Error handling for missing coordinates
5. Deterministic weather application to analysis

**Critical fixes:**
- Weather not fetching during onboarding (FIXED)
- Missing weather source field in results (FIXED)
- Inconsistent weather data across sessions (FIXED)

**Outcome:** Weather now correctly fetched and stored for all new rides

---

### **Phase 5: SSOT Model & Data Consistency**
**Timeline:** January 2026  
**Status:** ✅ Complete

**Problem identified:**
- Data scattered across multiple files
- Unclear which file was "source of truth"
- Rides list showing inconsistent data
- Meta generation logic spread everywhere

**Solution implemented:**
```
SSOT hierarchy:
1. sessions_index.json → Which sessions exist
2. result_<sid>.json → Metrics for each session (SSOT)
3. sessions_meta.json → Derived cache only
```

**Key changes:**
- Rides list now ONLY reads from `result_<sid>.json`
- Removed fallback to Strava API in list endpoints
- Standardized field names:
  - `distance_km` (not distance_m)
  - `precision_watt_avg` (not avg_power)
  - `weather_source` (always present)

**Files affected:**
- `sessions_list_router.py` - Major refactor
- `sessions.py` - Deprecated some endpoints
- Rides.tsx - Now reads from SSOT only

---

### **Phase 6: Onboarding Stabilization**
**Timeline:** Late January - Early February 2026  
**Status:** ✅ Complete

**Problem:**
- New users had broken onboarding
- Weather not fetching on first import
- Analysis failing silently
- Rides not appearing in list

**Solution:**
- Fixed weather fetching in import flow
- Ensured `result_<sid>.json` always created
- Added proper error handling
- Verified deterministic analysis on first run

**Test scenario that now works:**
1. New user signs up
2. Fills onboarding form (weight, bike specs)
3. Imports rides from Strava
4. Weather fetched correctly
5. Analysis runs without errors
6. Rides appear in list with metrics

---

### **Phase 7: Rides List - Full SSOT (Current)**
**Timeline:** Last 14 days (late Jan - Feb 11, 2026)  
**Status:** ✅ Complete

**Major work done:**
- Locked rides list to pure SSOT model
- Removed all "hydrations" and fallbacks
- Ensured consistency across:
  - `/api/sessions/list/all`
  - Rides page (frontend)
  - SessionView detail page
- Standardized metrics display

**Outcome:** Rides list is now deterministic and reliable foundation for future features

**Not documented in sprint-documentation.md because work happened in last 14 days**

---

## 🔧 Technical Debt Accumulated

### **Duplicate API Routes (identified in api_endpoints.md)**

| Route | Duplicate Files | Issue |
|---|---|---|
| `/api/sessions/list` | sessions.py + sessions_list_router.py | Unclear which is current |
| `/api/strava/sync` | strava_import_router.py + strava_import_router_for_commit.py | Both active |
| `/api/strava/import/{rid}` | strava_import_router.py + strava_import_router_for_commit.py | Both active |

**Impact:** Confusing for maintenance, risk of divergent behavior

---

### **Meta Generation Spread Across Files**

**Problem:** Logic for generating `sessions_meta.json` exists in:
- `sessions_list_router.py`
- `sessions.py`
- `strava_import_router.py`

**Impact:** Hard to ensure consistency, risk of stale cache

**Solution needed:** Consolidate to single utility function

---

### **Documentation Lag**

**Last update:** ~January 28, 2026 (14 days ago)  
**Missing:** Work on rides-list SSOT stabilization

**Impact:** Hard to track what was actually accomplished

---

## 📈 Sprint Work (from Sprintplan.txt)

**Sprint started:** ~4 weeks after initial DoD  
**Original plan had 8 areas:**

1. ✅ Profile enrichment (partially done)
2. ✅ Onboarding cleanup (started, needs completion)
3. ❌ Trend analysis (not started)
4. ❌ Set goals (not started)
5. ❌ Leaderboards (not started)
6. ✅ Rides list SSOT (done, but not in plan!)
7. ❌ Forum (planned for May)
8. ⚠️ Tech debt (identified but not resolved)

**Reality vs Plan:**
- More time spent on SSOT stabilization than planned
- Less time on new features
- Prioritized data integrity over feature velocity

**Lesson:** Foundation had to be solid before building features

---

## 🎯 Key Milestones Achieved

### **Technical Milestones**
- ✅ Deterministic analysis engine (Rust)
- ✅ Strava integration stable
- ✅ Weather data integration working
- ✅ SSOT model implemented
- ✅ Rides list fully reliable
- ✅ Onboarding for new users functional

### **Architectural Milestones**
- ✅ File-based state management proven viable
- ✅ Profile versioning architecture designed
- ✅ Cookie-based auth working in production
- ✅ Frontend deployed on Vercel
- ✅ Backend deployed on Fly.io

### **Product Milestones**
- ✅ Users can sign up
- ✅ Users can connect Strava
- ✅ Users can import rides
- ✅ Users can see ride list with watt estimates
- ✅ Analysis is deterministic and reproducible

---

## 📊 Current State (as of Feb 11, 2026)

**What works:**
- Signup + Login
- Strava OAuth
- Onboarding (but UI messy)
- Import rides (manual)
- Analysis (deterministic)
- Rides list (SSOT-based)

**What's in progress:**
- Profile in Dashboard (not implemented)
- Profile versioning (designed but not coded)

**What's planned:**
- Trend analysis (March 2026)
- Set goals (March 2026)
- Leaderboards (April 2026)
- Forum (May 2026)

---

## 🚀 Next Phase: MVP Sprint

**Timeline:** Feb 11 - Mar 1, 2026 (18 days)  
**Goal:** Pioneer Beta launch

**Must-have features:**
- Signup with leaderboard fields (gender, country, city, age)
- Onboarding UI cleanup
- Profile in Dashboard (view + edit)
- Profile versioning working
- Import 50+ rides per user
- Simple trend analysis
- Simple goals feature

**Success criteria:**
- 10-20 pioneer users can test
- System is stable and deterministic
- Provides value (watt estimates + trends)
- Foundation for April MVP launch

---

## 📝 Lessons Learned

### **1. Determinism is hard**
- Many iterations to get consistent results
- Weather integration took longer than expected
- SSOT model required discipline

### **2. Foundation before features**
- Time spent on SSOT was worth it
- Can't build trends on unstable data
- Refactoring early is cheaper than later

### **3. Documentation matters**
- Gaps in documentation slowed progress
- Hard to remember decisions from weeks ago
- This archive prevents future confusion

### **4. Scope management**
- Original sprint plan was ambitious
- Reality: data integrity took priority
- Better to have stable foundation than rushed features

---

## 🗂️ File Structure Evolution

### **Initial Structure (Phase 1-2)**
```
/app/state/users/<uid>/
    auth.json
    sessions/
        session_<sid>.json
```

### **After SSOT Model (Phase 5)**
```
/app/state/users/<uid>/
    auth.json
    sessions_index.json       # NEW - SSOT for session list
    sessions/
        session_<sid>.json
        result_<sid>.json     # NEW - SSOT for metrics
```

### **Current + Planned (Phase 7+)**
```
/app/state/users/<uid>/
    auth.json
    profile.json              # NEW - for onboarding data
    profile_versions.jsonl    # NEW - audit log
    sessions_index.json
    sessions_meta.json        # Cache only
    sessions/
        session_<sid>.json
        result_<sid>.json
```

---

## 🎓 Technical Achievements

### **Backend (Python FastAPI)**
- File-based state management at scale
- OAuth 2.0 flow implementation
- Efficient session management
- Error handling & logging
- Deployed on Fly.io

### **Frontend (React + Vite)**
- TypeScript throughout
- Component-based architecture
- Strava OAuth integration
- Responsive design
- Deployed on Vercel

### **Core Engine (Rust + PyO3)**
- Physics-based power calculation
- Zero-copy data transfer to Python
- Deterministic floating-point math
- Performance: 1000s of samples processed in milliseconds

### **Infrastructure**
- CI/CD pipeline (implied from Vercel/Fly.io)
- Cookie-based auth
- File system as database
- Versioned profile management

---

## 📚 Key Documents Generated

1. **Dynamisk DoD** - Original development plan (6 phases)
2. **api_endpoints.md** - API inventory (24 endpoints)
3. **Backend Analyzer Stability Log** - Weather integration journey
4. **Sprintplan.txt** - 8-area sprint plan (partially completed)
5. **sprint-documentation.md** - Daily log (stopped 14 days ago)
6. **CURRENT_STATE.md** - Snapshot as of Feb 11, 2026
7. **ARCHITECTURE.md** - System design and data flow
8. **PROJECT_HISTORY.md** - This document

---

## ✍️ Notes

- This is a historical archive, not a living document
- For current status, see CURRENT_STATE.md
- For technical design, see ARCHITECTURE.md
- For next steps, see SPRINT_BACKLOG.md (when created)

**Last updated:** 2026-02-11  
**Covers:** October 2025 - February 11, 2026 (~4 months)
