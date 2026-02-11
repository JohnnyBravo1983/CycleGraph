# CycleGraph – Technical Debt
**Last updated:** 2026-02-11  
**Purpose:** Prioritized list of what needs fixing before and after MVP

---

## 🎯 Debt Categories

**Priority Levels:**
- 🔴 **CRITICAL** - Must fix before March 1 (blocks MVP)
- 🟡 **HIGH** - Should fix before March 1 (quality issue)
- 🟢 **MEDIUM** - Fix after MVP (technical cleanup)
- ⚪ **LOW** - Nice to have (future improvement)

---

## 🔴 CRITICAL (Must Fix Before March 1)

### **1. Profile in Dashboard - Not Implemented**
**Priority:** 🔴 CRITICAL  
**Impact:** Users can't view or edit their profile after onboarding  
**Blocks:** Goals feature, proper user experience

**Current state:**
- Profile data exists in `profile.json`
- No way to display it in Dashboard
- No way to edit (weight changes, new bike, etc.)

**What needs to happen:**
1. Create Profile section in Dashboard
2. Read from `profile.json`
3. Display current values (weight, bike specs, FTP)
4. Allow editing
5. Save with versioning (via `/api/profile/save`)
6. Test: change weight → verify new rides use new weight

**Estimated effort:** 2-3 days  
**Blockers:** None (API already exists)

---

### **2. Signup Form - Missing Leaderboard Fields**
**Priority:** 🔴 CRITICAL  
**Impact:** Can't build leaderboards without demographic data  
**Blocks:** April leaderboard feature

**Current state:**
- Signup form has: username, email, password, full_name, bike_name
- Missing: gender, country, city, age

**What needs to happen:**
1. Add fields to signup form UI
2. Update `/api/auth/signup` to accept new fields
3. Store in `auth.json`
4. Validate inputs (age > 0, gender enum, etc.)

**Estimated effort:** 0.5 days  
**Blockers:** None

---

### **3. Onboarding UI Cleanup**
**Priority:** 🔴 CRITICAL  
**Impact:** Confusing for new users, looks unprofessional  
**Blocks:** User experience, Pioneer Beta launch

**Current state:**
- UI is messy (screenshot evidence)
- No explanations for technical fields (CdA? Crr?)
- Some fields should have better defaults
- Unclear which fields are critical vs optional

**What needs to happen:**
1. Improve layout (cleaner, more spacious)
2. Add tooltips/help text:
   - "CdA: Aerodynamic drag coefficient (lower = more aero)"
   - "Crr: Rolling resistance (0.004 is standard road tire)"
3. Set smart defaults:
   - CdA: 0.300 (typical road position)
   - Crr: 0.0040 (performance road tire)
   - Crank efficiency: 0.96
4. Mark required fields clearly
5. Hide advanced fields behind "Advanced settings" toggle?

**Estimated effort:** 1-2 days  
**Blockers:** None

---

## 🟡 HIGH (Should Fix Before March 1)

### **4. Duplicate API Routes**
**Priority:** 🟡 HIGH  
**Impact:** Confusion, risk of divergent behavior  
**Blocks:** Clean codebase for job applications

**Duplicates identified:**

#### **A) `/api/sessions/list`**
- **File 1:** `sessions.py` (L1121)
- **File 2:** `sessions_list_router.py` (L1075)
- **Decision:** Keep `sessions_list_router.py` (SSOT-based)
- **Action:** Remove from `sessions.py`

#### **B) `/api/strava/sync`**
- **File 1:** `strava_import_router.py` (L761)
- **File 2:** `strava_import_router_for_commit.py` (L629)
- **Decision:** Determine which is current
- **Action:** Remove one file entirely

#### **C) `/api/strava/import/{rid}`**
- **File 1:** `strava_import_router.py` (L1090)
- **File 2:** `strava_import_router_for_commit.py` (L925)
- **Decision:** Same as above
- **Action:** Remove one file entirely

**Estimated effort:** 1 day (includes testing)  
**Blockers:** Need to confirm which strava_import_router is current

---

### **5. Meta Generation - Consolidate Logic**
**Priority:** 🟡 HIGH  
**Impact:** Hard to maintain, risk of stale cache  
**Blocks:** Clean architecture

**Current state:**
- Meta generation logic spread across:
  - `sessions_list_router.py`
  - `sessions.py`
  - `strava_import_router.py`

**What needs to happen:**
1. Create single utility function: `generate_sessions_meta(uid)`
2. Call it explicitly when results change:
   - After analysis completes
   - After batch import
3. Remove duplicate logic from routers
4. Document: "Meta is cache, not SSOT"

**Estimated effort:** 1 day  
**Blockers:** None

---

### **6. Profile Versioning - Verify Implementation**
**Priority:** 🟡 HIGH  
**Impact:** Determinism breaks if not working correctly  
**Blocks:** Data integrity

**Current state:**
- Architecture designed (profile_versions.jsonl)
- `server/utils/versioning.py` exists
- Not verified to work end-to-end

**What needs to happen:**
1. Test profile update flow:
   - User changes weight: 80kg → 75kg
   - Verify `profile_versions.jsonl` appended
   - Verify `profile.json` updated
2. Test analysis uses correct version:
   - Import ride before weight change
   - Change weight
   - Import ride after weight change
   - Verify old ride has old weight, new ride has new weight
3. Verify `result_<sid>.json` stores profile snapshot

**Estimated effort:** 0.5 days (mostly testing)  
**Blockers:** Profile in Dashboard must exist first

---

## 🟢 MEDIUM (Fix After March 1)

### **7. Legacy/Unclear Routes - Clarify or Remove**
**Priority:** 🟢 MEDIUM  
**Impact:** Code confusion, not user-facing  

**Routes to investigate:**

| Route | Location | Question |
|---|---|---|
| `/login` | auth_strava.py (L275) | Still used? Remove? |
| `/callback` | auth_strava.py (L315) | Still used? Remove? |
| `/api/sessions/{sid}/analyze_sessionspy` | sessions.py (L3504) | Debug only? Remove? |

**Estimated effort:** 0.5 days  
**Blockers:** None

---

### **8. Debug Endpoints - Mark or Remove**
**Priority:** 🟢 MEDIUM  
**Impact:** Code clarity, security (don't expose debug in prod)

**Debug endpoints:**
- `/api/sessions/debug/rb` (sessions.py L1722)
- `/api/sessions/list/_debug_paths` (sessions_list_router.py L1170)

**What needs to happen:**
1. Add `_debug` prefix consistently
2. Document as debug-only in code
3. Optionally: disable in production environment

**Estimated effort:** 0.5 days  
**Blockers:** None

---

### **9. Import Rides UX - Better Controls**
**Priority:** 🟢 MEDIUM  
**Impact:** User experience (not blocking)

**Current state:**
- Manual import button in Dashboard
- No control over which rides to import

**What needs to happen:**
1. Add date range picker (import rides from Jan 1 - Feb 11)
2. Add "last N rides" option (import last 50)
3. Show progress during import (X of Y rides)
4. Error handling for failed imports

**Estimated effort:** 1-2 days  
**Blockers:** None

---

## ⚪ LOW (Future Improvements)

### **10. Auto-Sync from Strava**
**Priority:** ⚪ LOW  
**Impact:** User convenience (manual is OK for MVP)

**Current state:** Manual import only

**What needs to happen:**
1. Implement Strava webhook subscription
2. Listen for new activities
3. Auto-fetch and analyze
4. Notify user of new ride

**Estimated effort:** 3-5 days  
**Blockers:** Strava webhook setup, background worker architecture  
**Timeline:** After April MVP

---

### **11. Migrate to Database**
**Priority:** ⚪ LOW  
**Impact:** Scalability (file-based is fine for MVP)

**Current state:** File-based storage per user

**What needs to happen:**
1. Design schema (users, profiles, sessions, results)
2. Choose DB (PostgreSQL? SQLite?)
3. Migrate data
4. Update all routers to use DB queries
5. Keep API contracts unchanged

**Estimated effort:** 1-2 weeks  
**Blockers:** Need significant user base first  
**Timeline:** Post-MVP (only if scaling issues)

---

### **12. Test Coverage**
**Priority:** ⚪ LOW  
**Impact:** Code quality, confidence in refactoring

**Current state:** Unknown/minimal test coverage

**What needs to happen:**
1. Unit tests for core logic:
   - Profile versioning
   - Meta generation
   - Analysis orchestration
2. Integration tests for API:
   - Signup → onboarding → import → analyze flow
3. End-to-end tests:
   - Full user journey

**Estimated effort:** Ongoing (add tests as you code)  
**Blockers:** None

---

## 📊 Debt by Component

### **Backend (Python)**
- 🔴 Profile in Dashboard API (if missing)
- 🟡 Duplicate routes removal
- 🟡 Meta generation consolidation
- 🟢 Legacy route cleanup
- 🟢 Debug endpoint marking

### **Frontend (React)**
- 🔴 Profile Dashboard component
- 🔴 Signup form fields
- 🔴 Onboarding UI cleanup
- 🟢 Import rides UX improvements

### **Data/State**
- 🟡 Profile versioning verification
- ⚪ Database migration (far future)

### **Infrastructure**
- ⚪ Auto-sync webhooks
- ⚪ Background workers
- ⚪ Test coverage

---

## 🗓️ Suggested Fix Timeline

### **Week 1 (Feb 11-17): Critical Foundation**
- Day 1-2: Profile in Dashboard
- Day 3: Signup form fields
- Day 4-5: Onboarding UI cleanup
- Day 6: Buffer/testing

### **Week 2 (Feb 18-24): Quality & Features**
- Day 7: Remove duplicate routes
- Day 8: Consolidate meta generation
- Day 9-10: Trend analysis (new feature)
- Day 11-12: Goals feature (new feature)
- Day 13: Buffer/testing

### **Week 3 (Feb 25 - Mar 1): Polish & Testing**
- Day 14-15: Profile versioning verification
- Day 16: Import rides UX
- Day 17: End-to-end testing with pioneer users
- Day 18: Bug fixes, final polish

**Post-MVP (After March 1):**
- Remove legacy routes
- Mark debug endpoints
- Consider auto-sync (if time permits)

---

## 💰 Cost of Ignoring Debt

### **If we skip duplicate route cleanup:**
- Risk: Devs (or you in 2 months) won't know which to use
- Risk: Divergent behavior between routes
- Impact: Debugging nightmares

### **If we skip profile in Dashboard:**
- Risk: Users can't update weight/bike
- Impact: Can't build goals or trends properly
- Impact: Poor user experience

### **If we skip onboarding cleanup:**
- Risk: Users confused, abandon app
- Impact: No Pioneer Beta success
- Impact: Unprofessional for job applications

### **If we skip profile versioning:**
- Risk: Determinism breaks
- Impact: Old rides change when profile updates
- Impact: Core value prop (deterministic watt) fails

---

## ✅ Definition of "Debt Paid"

**For each item:**
1. Code implemented and tested
2. Documentation updated (if needed)
3. No regressions in existing features
4. Can demo to job interviewer without embarrassment

**Overall:**
- Clean, understandable codebase
- No confusing duplicates
- Clear separation of concerns
- Professional quality

---

## 📝 Notes

- This list will grow as we discover more debt
- Prioritize ruthlessly: MVP first, perfection later
- Some debt is OK if it doesn't block users
- Pay high-interest debt first (blocks features, confuses users)

**Next review:** After each sprint week, re-prioritize based on progress

---

## 🎯 Quick Reference: Must-Fix Before March 1

1. 🔴 Profile in Dashboard
2. 🔴 Signup form fields
3. 🔴 Onboarding UI cleanup
4. 🟡 Remove duplicate routes
5. 🟡 Consolidate meta generation
6. 🟡 Verify profile versioning

**Everything else can wait until after Pioneer Beta launch.**
