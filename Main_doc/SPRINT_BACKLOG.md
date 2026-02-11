# CycleGraph – Sprint Backlog (Feb 11 - Mar 1, 2026)
**Sprint Goal:** Launch Pioneer Beta with stable profile system and power analytics  
**Duration:** 18 days  
**End Date:** March 1, 2026

---

## 🎯 Sprint Objectives

**Must-Have (March 1):**
- ✅ Users can signup with complete profile (gender, country, city, age)
- ✅ Onboarding is clean and understandable
- ✅ Users can view and edit profile in Dashboard
- ✅ Profile versioning works (weight changes don't affect old rides)
- ✅ **Users can import 10 or 50 rides (50 is default/recommended)**
- ✅ **Power Profile shows FTP + peak efforts (1, 5, 20, 60min)**
- ✅ **FTP Progression shows trend and future projection**

**Success Metrics:**
- 10-20 pioneer users can test
- System is stable and deterministic
- No critical bugs
- Presentable for job applications
- **WOW factor: Users see their form + progression immediately after import**

---

## 📥 Import Strategy (Pioneer Beta)

**CRITICAL DECISION: Keep it simple**

For Pioneer Beta, users can import ONLY:
- **50 rides** (default/recommended) - Full Power Profile + meaningful FTP Progression
- **10 rides** (quick test) - Basic Power Profile, limited progression data

**Why not more options (25, 100, date ranges)?**
- Simpler UX (less decisions = faster onboarding)
- 50 rides is sweet spot: Enough data for trends, not overwhelming
- 10 rides lets users "test drive" before committing
- Can add more options in April if users request it

**Implementation in Day 8:**
- Simple dropdown: "Import 10 rides" or "Import 50 rides"
- Default selection: 50 rides
- Help text: "50 rides recommended for full analytics"

---

## 📅 Week 1: Foundation (Feb 11-17)

### **Day 1 - Tuesday, Feb 11** 🔴
**Focus:** Signup form enhancement

**Tasks:**
1. Add fields to signup form UI:
   - Gender (dropdown: male/female)
   - Country (text input or dropdown)
   - City (text input)
   - Age (number input, min 13, max 100)
2. Update frontend validation
3. Update `POST /api/auth/signup` to accept new fields
4. Store in `auth.json`
5. Test: Create new user, verify fields saved

**Deliverable:** New users have complete demographic profile  
**Time estimate:** 4-5 hours  
**Blockers:** None

**Validation:**
- [ ] Signup form has 4 new fields
- [ ] Fields are required (can't skip)
- [ ] Data saves to `auth.json`
- [ ] Old users still work (backward compatible)

---

### **Day 2 - Wednesday, Feb 12** 🔴
**Focus:** Profile in Dashboard - Part 1 (Display)

**Tasks:**
1. Create Profile section in Dashboard UI
2. Add "Profile" tab/link in navigation
3. Read profile data via `GET /api/profile/get`
4. Display current values:
   - Rider weight, bike weight
   - CdA, Crr, crank efficiency
   - Bike type, tire specs
   - FTP (if exists)
5. Show profile version number
6. Style it cleanly (match Dashboard aesthetic)

**Deliverable:** Users can VIEW their profile  
**Time estimate:** 5-6 hours  
**Blockers:** None (API already exists)

**Validation:**
- [ ] Profile section visible in Dashboard
- [ ] All profile fields display correctly
- [ ] Shows "No profile yet" if user hasn't done onboarding
- [ ] Looks professional

---

### **Day 3 - Thursday, Feb 13** 🔴
**Focus:** Profile in Dashboard - Part 2 (Edit)

**Tasks:**
1. Make profile fields editable (form mode)
2. Add "Edit Profile" button
3. Validation for inputs (weight > 0, etc.)
4. Save via `PUT /api/profile/save`
5. Show success message after save
6. Update display with new values
7. Test profile versioning:
   - Change weight from 80 → 75
   - Verify `profile_versions.jsonl` appended
   - Verify `profile.json` updated

**Deliverable:** Users can EDIT their profile  
**Time estimate:** 5-6 hours  
**Blockers:** None

**Validation:**
- [ ] Can edit all profile fields
- [ ] Changes save successfully
- [ ] Profile version increments
- [ ] `profile_versions.jsonl` contains history
- [ ] No errors in console

---

### **Day 4 - Friday, Feb 14** 🔴
**Focus:** Onboarding UI cleanup

**Tasks:**
1. Improve layout (more spacing, cleaner design)
2. Add tooltips/help text for technical fields:
   - CdA: "Aerodynamic drag (0.250-0.350, lower = faster)"
   - Crr: "Rolling resistance (0.0030-0.0050, lower = faster)"
   - Crank efficiency: "Power transfer efficiency (typically 96%)"
3. Set smart defaults:
   - CdA: 0.300
   - Crr: 0.0040
   - Crank efficiency: 0.96
   - Tire width: 28mm
4. Mark required vs optional fields clearly
5. Consider: Hide advanced fields behind toggle?
6. Test with fresh eyes (pretend you're new user)

**Deliverable:** Onboarding is clear and professional  
**Time estimate:** 5-6 hours  
**Blockers:** None

**Validation:**
- [ ] UI looks clean (not messy)
- [ ] Help text explains technical terms
- [ ] Defaults make sense
- [ ] New user can complete without confusion
- [ ] No overwhelming fields

---

### **Day 5 - Saturday, Feb 15** 🟡
**Focus:** Remove duplicate API routes

**Tasks:**
1. Confirm which `strava_import_router` is current:
   - Check git history
   - Check which is imported in main app
   - Ask yourself: which was last modified?
2. Delete the duplicate file entirely
3. Remove `/api/sessions/list` from `sessions.py`
4. Update imports in main app if needed
5. Test all affected endpoints:
   - `/api/strava/sync`
   - `/api/strava/import/{rid}`
   - `/api/sessions/list/all`
6. Verify no regressions

**Deliverable:** Clean API, no duplicates  
**Time estimate:** 3-4 hours  
**Blockers:** Need to identify which file is current

**Validation:**
- [ ] Only one `strava_import_router` file exists
- [ ] `/api/sessions/list` only in `sessions_list_router.py`
- [ ] All imports work
- [ ] Strava sync still works
- [ ] No 404s or 500s

---

### **Day 6 - Sunday, Feb 16** 🟡
**Focus:** Consolidate meta generation + Buffer day

**Tasks:**
1. Create `server/utils/meta_generator.py`
2. Single function: `generate_sessions_meta(uid)`
3. Move meta logic from:
   - `sessions_list_router.py`
   - `sessions.py`
   - `strava_import_router.py`
4. Call explicitly after:
   - Analysis completes
   - Batch import finishes
5. Document: "Meta is cache, not SSOT"
6. Test: Delete meta file, regenerate, verify correct

**If done early:** Use buffer time for:
- Catch up on any incomplete tasks from Week 1
- Test end-to-end flow (signup → onboarding → profile)
- Fix bugs discovered

**Deliverable:** Clean meta generation logic  
**Time estimate:** 3-4 hours + buffer  
**Blockers:** None

**Validation:**
- [ ] Single source of meta generation
- [ ] Meta regenerates correctly
- [ ] No duplicate logic in routers
- [ ] Documentation updated

---

### **Week 1 Review (Sunday evening)**

**Checklist:**
- [ ] Signup form has demographic fields
- [ ] Profile Dashboard displays
- [ ] Profile Dashboard allows editing
- [ ] Onboarding UI is clean
- [ ] Duplicate routes removed
- [ ] Meta generation consolidated

**If ANY task incomplete:** Carry over to Week 2 Day 1

---

## 📅 Week 2: Analytics Features (Feb 18-24)

### **Day 7 - Tuesday, Feb 18** 🟡
**Focus:** Profile versioning verification

**Tasks:**
1. End-to-end test scenario:
   - Create test user
   - Set weight: 80kg
   - Import 1 ride
   - Verify ride in `result_<sid>.json` has weight: 80kg
2. Change weight to 75kg via Dashboard
3. Import another ride
4. Verify:
   - Old ride still has weight: 80kg
   - New ride has weight: 75kg
   - `profile_versions.jsonl` has both versions
5. Document test results
6. Fix any issues discovered

**Deliverable:** Profile versioning proven to work  
**Time estimate:** 3-4 hours  
**Blockers:** Profile Dashboard must work (Day 2-3)

**Validation:**
- [ ] Old rides unchanged after profile update
- [ ] New rides use new profile
- [ ] Version history exists in jsonl file
- [ ] Determinism maintained

---

### **Day 8 - Wednesday, Feb 19** 🟢
**Focus:** Import rides UX improvements

**Context:**
For Pioneer Beta, keep import simple: ONLY 10 or 50 rides.
- 50 rides: Recommended (needed for meaningful Power Profile + FTP Progression)
- 10 rides: Quick test option (for users who want to try before committing to full import)

**Tasks:**
1. ~~Add date range picker to import UI~~ (SKIP for Pioneer Beta - too complex)
2. Add "last N rides" option:
   - **Simple dropdown: 10 rides OR 50 rides ONLY**
   - Default: 50 rides (recommended for Power Profile)
   - 10 rides: Quick test option
   - Note: 50 rides needed for meaningful FTP Progression analysis
3. Show progress during import:
   - "Importing ride 5 of 50..."
   - Progress bar?
4. Better error handling:
   - Show which rides failed
   - Allow retry for failed rides
5. Test with both options (10 and 50 rides)

**Deliverable:** Import UX is simple and clear (10 or 50 rides only)  
**Time estimate:** 3-4 hours (simpler than original - no date picker)  
**Blockers:** None

**Validation:**
- [ ] Dropdown shows ONLY 10 or 50 rides (no other options)
- [ ] 50 rides is default/recommended
- [ ] Progress visible during import
- [ ] Errors handled gracefully
- [ ] Both 10 and 50 ride imports work
- [ ] UI explains: "50 rides recommended for full Power Profile"

---

### **Day 9-10 - Thursday-Friday, Feb 20-21** 🔴
**Focus:** Power Profile Analysis (BACKEND) - NEW FEATURE

**Context:** 
This is the #1 WOW feature - shows users their concrete form (FTP + peak efforts).
Must work regardless if user has 50 rides from 1 month or 2 years.

**Day 9 Tasks (Backend - Rust + Python):**
1. **Peak efforts calculation (Rust):**
   - Add function to find best watt for durations: 1min, 5min, 20min, 45min, 60min
   - Use sliding window algorithm over watt streams
   - Return: `{duration: watts}` for each ride
   
2. **Smart FTP calculation (Python):**
   - Collect peak efforts from all rides
   - Calculate FTP estimates:
     - From 5min: `best_5min * 0.85`
     - From 20min: `best_20min * 0.95`
     - From 45min: `best_45min * 0.98`
     - From 60min: `best_60min * 1.00`
   - Take highest estimate as FTP
   
3. **W/kg calculation:**
   - Get rider weight from `profile.json`
   - Calculate all metrics in W/kg as well
   
4. **Store in result files:**
   - Add to `result_<sid>.json`:
     - `ftp_watts`, `ftp_watts_per_kg`
     - `peak_1min`, `peak_5min`, `peak_20min`, `peak_60min` (both W and W/kg)

**Day 10 Tasks (API endpoint):**
5. Create `/api/analytics/power-profile` endpoint:
   - Input: user_id
   - Load all `result_<sid>.json` files
   - Extract peak efforts from each ride
   - Find overall bests (max across all rides)
   - Calculate FTP (current best)
   - Calculate progression (first ride FTP vs current)
   - Return JSON:
     ```json
     {
       "current_ftp_watts": 265,
       "current_ftp_wkg": 2.7,
       "first_ftp_watts": 250,
       "first_ftp_wkg": 2.5,
       "progression_watts": 15,
       "progression_percent": 6,
       "peak_efforts": {
         "1min": {"watts": 420, "wkg": 4.2},
         "5min": {"watts": 340, "wkg": 3.4},
         "20min": {"watts": 280, "wkg": 2.8},
         "60min": {"watts": 260, "wkg": 2.6}
       }
     }
     ```

6. Test with multiple user scenarios:
   - User with 50 rides from 2 months
   - User with 50 rides from 1 year
   - User with only 10 rides

**Deliverable:** Backend can calculate Power Profile  
**Time estimate:** 12 hours (2 days)  
**Blockers:** Need precision watt streams available

**Validation:**
- [ ] Peak efforts calculated correctly from watt streams
- [ ] FTP estimate is accurate (uses best of multiple durations)
- [ ] W/kg calculated correctly
- [ ] API returns consistent data
- [ ] Works with different ride count/timespan scenarios

---

### **Day 11-12 - Saturday-Sunday, Feb 22-23** 🔴
**Focus:** Power Analytics - Dashboard + Trends Page (FRONTEND) - NEW FEATURE

**Context:**
Analytics must be DYNAMIC and live in TWO places:
1. **Dashboard:** Key metrics (snapshot/summary)
2. **Trends Page:** Full Power Profile + FTP Progression (detailed view)

Both must update automatically when user imports new rides.

**ARCHITECTURE DECISION:**
- Analytics are computed ON-DEMAND (not cached)
- Every time user views Dashboard or Trends: fetch from `/api/analytics/*`
- Backend reads ALL `result_<sid>.json` files and calculates current metrics
- This ensures data is always fresh after new imports

**Day 11 Tasks (Dashboard Key Metrics):**
1. Create "Key Metrics" widget in Dashboard (top of page)
2. Fetch data from `/api/analytics/power-profile`
3. Display SUMMARY only:
   ```
   💪 CURRENT FTP: 265W (2.7 W/kg)
   📈 Progress: +15W (+6%) since start
   🔥 Best 5min: 340W (3.4 W/kg)
   
   [View Full Analysis →] (links to Trends page)
   ```
4. Keep it minimal - just enough to show progress

**Day 11 Tasks (Trends Page - Power Profile):**
5. Create NEW PAGE: `/trends` (add to navigation)
6. Section 1: "Power Profile"
7. Fetch data from `/api/analytics/power-profile`
8. Display FULL layout:
   ```
   🎯 YOUR POWER PROFILE
   
   💪 FTP: 265W (2.7 W/kg)
      First ride: 250W (2.5 W/kg)
      Improvement: +15W (+6%) 🔥
   
   📈 PEAK EFFORTS:
      1min:  420W (4.2 W/kg) - Sprint power
      5min:  340W (3.4 W/kg) - VO2max
      20min: 280W (2.8 W/kg) - Threshold
      60min: 260W (2.6 W/kg) - Endurance
   ```
9. Add tooltips:
   - FTP: "Functional Threshold Power - max watt you can sustain for ~1 hour"
   - W/kg: "Watts per kilogram - accounts for body weight"
   - Peak efforts: "Your best performances at different durations"

**Day 12 Tasks (Trends Page - FTP Progression):**
10. Section 2 on Trends page: "FTP Progression" (below Power Profile)
11. Create `/api/analytics/ftp-progression` endpoint:
   - Load all rides sorted by date
   - Calculate timespan (first to last ride)
   - Group FTP by week (not by ride number!)
   - Calculate rides per week
   - If timespan > 6 months: use only last 6 months data
   - Linear regression: watts per week trend
   - Project future: +4w, +8w, +12w
   - Return:
     ```json
     {
       "ftp_by_week": [
         {"week": "2025-W40", "ftp_watts": 250, "ftp_wkg": 2.5},
         {"week": "2025-W44", "ftp_watts": 258, "ftp_wkg": 2.6},
         {"week": "2026-W05", "ftp_watts": 265, "ftp_wkg": 2.7}
       ],
       "trend_watts_per_week": 1.9,
       "rides_per_week": 6.2,
       "weeks_analyzed": 12,
       "projections": {
         "4_weeks": {"watts": 273, "wkg": 2.73},
         "8_weeks": {"watts": 281, "wkg": 2.81},
         "12_weeks": {"watts": 289, "wkg": 2.89}
       },
       "confidence": "high"
     }
     ```

12. Display FTP progression on Trends page:
   - Line chart: FTP over time (weeks on x-axis, not ride numbers)
   - Show activity level: "6.2 rides/week ✅ Great consistency!"
   - Show trend: "+1.9W per week"
   - Show projections:
     ```
     🔮 IF YOU CONTINUE:
        4 weeks:  273W (2.73 W/kg)
        8 weeks:  281W (2.81 W/kg)
        12 weeks: 289W (2.89 W/kg)
     ```
   - Add messaging based on activity:
     - High activity (3+ rides/week): "Great consistency! 💪"
     - Medium (1-3 rides/week): "For faster gains: 3-4x per week"
     - Low (<1 ride/week): "⚠️ Low activity - projection uncertain"

13. Add tip box:
   ```
   💡 TO IMPROVE FTP FASTER:
      • Train 3-4x per week minimum
      • Include 2-3 sessions above 90% FTP (threshold/intervals)
      • Keep 1-2 sessions easy (recovery)
   ```

**CRITICAL - Dynamic Updates:**
14. Ensure both Dashboard and Trends page RE-FETCH data on every view:
    - Dashboard key metrics: fetch on page load
    - Trends page: fetch on page load
    - After import completes: show message "Analytics updated! Refresh to see latest."
    - Or: Auto-refresh Dashboard/Trends after import completes
15. Test: Import 1 new ride → verify FTP/peaks update immediately

**Deliverable:** Power Analytics live in Dashboard + Trends page, updates dynamically  
**Time estimate:** 8 hours (2 days)  
**Blockers:** Backend API must work (Day 9-10)

**Validation:**
- [ ] **Dashboard has key metrics widget** (FTP, progress, best 5min)
- [ ] **Trends page exists** (new navigation item)
- [ ] **Trends page has 2 sections:** Power Profile + FTP Progression
- [ ] Power Profile displays correctly
- [ ] FTP progression chart shows time-based data (weeks, not rides)
- [ ] Projections make sense
- [ ] Works for users with 50 rides from 1 month AND 2 years
- [ ] Activity level messaging is appropriate
- [ ] Tooltips explain terms clearly
- [ ] **Data updates dynamically:** Import new ride → analytics refresh
- [ ] Mobile responsive
- [ ] WOW factor achieved - users excited to see their data!

---

### **Week 2 Review (Sunday evening)**

**Checklist:**
- [ ] Profile versioning verified
- [ ] Import UX improved
- [ ] Power Profile backend working
- [ ] **Dashboard has key metrics**
- [ ] **Trends page exists with full analytics**
- [ ] **Analytics update dynamically after imports**

**If ANY task incomplete:** Prioritize for Week 3

---

## 📅 Week 3: Polish & Testing (Feb 25 - Mar 1)

### **Day 13-14 - Tuesday-Wednesday, Feb 25-26** 🟢
**Focus:** End-to-end testing & bug fixes

**Tasks:**
1. Full user journey test:
   - Signup with new fields
   - Complete onboarding
   - Connect Strava
   - Import 50 rides
   - **View Dashboard → Check key metrics appear**
   - **View Trends page → Check full Power Profile + FTP Progression**
   - View rides list
   - View session detail
   - Edit profile
   - **Import 1 more ride → Verify analytics update**
   - **Refresh Dashboard → Verify new FTP/peaks if better**
   - **Refresh Trends → Verify new data point in progression chart**
   - Verify profile versioning
2. Document bugs found
3. Fix critical bugs
4. Test on different browsers (Chrome, Firefox, Safari)
5. Test on mobile (responsive design)
6. **Special test scenarios:**
   - User with 50 rides from 1 month (very active)
   - User with 50 rides from 1 year (sporadic)
   - User with only 10 rides
   - User who changes weight mid-way
   - **User imports 50 rides, then 10 more → verify analytics update correctly**

**Deliverable:** System is stable  
**Time estimate:** 8 hours (2 days)  
**Blockers:** All features must be done

**Validation:**
- [ ] No critical bugs
- [ ] Works on multiple browsers
- [ ] Mobile-friendly
- [ ] Fast enough (no major slowdowns)
- [ ] Power analytics work for different activity patterns
- [ ] **Dashboard key metrics update after new imports**
- [ ] **Trends page updates after new imports**
- [ ] Can demo confidently

---

### **Day 15 - Thursday, Feb 27** 🟢
**Focus:** Documentation & cleanup

**Tasks:**
1. Update README.md:
   - Feature list (add Power Profile + FTP Progression)
   - Setup instructions
   - Tech stack
2. Add inline code comments where needed
3. Clean up console.logs
4. Remove commented-out code
5. Update API_REFERENCE.md with new endpoints:
   - `/api/analytics/power-profile`
   - `/api/analytics/ftp-progression`
6. Take screenshots for job applications:
   - **Dashboard with key metrics widget**
   - **Trends page (full view)**
   - Rides list
   - Profile

**Deliverable:** Presentable codebase  
**Time estimate:** 4-5 hours  
**Blockers:** None

**Validation:**
- [ ] README is current
- [ ] Code is clean
- [ ] Screenshots taken
- [ ] Documentation matches reality
- [ ] API reference updated

---

### **Day 16 - Friday, Feb 28** 🟢
**Focus:** Pioneer user preparation

**Tasks:**
1. Create onboarding guide for pioneer users:
   - "Welcome to CycleGraph Beta"
   - Step-by-step instructions
   - What to test
   - How to report bugs
   - **Highlight: "Import 50 rides (recommended) to unlock full Power Profile and FTP Progression!"**
   - **Note: "10 rides available for quick testing, but analytics limited"**
2. Set up feedback mechanism:
   - Simple form or email
   - Discord/Slack channel?
3. Prepare demo script (for yourself):
   - Show signup → import → **Power Profile** → **FTP Progression**
   - Highlight deterministic watt calculation
   - **Show WOW moment: "This is your form, this is your progress"**
   - Practice explaining value prop
4. Deploy to production:
   - Verify Vercel + Fly.io are updated
   - Test production environment
   - Check no API keys exposed

**Deliverable:** Ready for pioneers  
**Time estimate:** 4-5 hours  
**Blockers:** System must be stable

**Validation:**
- [ ] Onboarding guide exists
- [ ] Feedback mechanism ready
- [ ] Production deployed
- [ ] Can demo smoothly
- [ ] Demo emphasizes WOW factor

---

### **Day 17 - Saturday, Feb 29** 🟢
**Focus:** Invite pioneers & monitor

**Tasks:**
1. Invite 5-10 pioneer users:
   - Send personal invites
   - Include onboarding guide
   - Set expectations (beta, bugs expected)
   - **Emphasize: Import 50 rides to unlock full value**
2. Monitor for issues:
   - Check logs for errors
   - Be ready to fix critical bugs
3. Respond to feedback quickly
4. Document issues found
5. Make quick fixes if possible
6. **Gather feedback specifically on:**
   - Was Power Profile impressive?
   - Was FTP Progression motivating?
   - Did they understand W/kg?
   - Did projections make sense?

**Deliverable:** Pioneers are testing  
**Time estimate:** Variable (monitoring day)  
**Blockers:** Must have users willing to test

**Validation:**
- [ ] At least 5 users signed up
- [ ] Users can complete onboarding
- [ ] Users can import 50 rides
- [ ] No showstopper bugs
- [ ] Getting positive feedback on analytics
- [ ] WOW factor confirmed by users

---

### **Day 18 - Sunday, Mar 1** 🎯
**Focus:** Final polish & retrospective

**Tasks:**
1. Fix any critical bugs from Day 17
2. Update documentation based on pioneer feedback
3. Prepare for April sprint:
   - What worked?
   - What didn't?
   - What to prioritize next?
4. Update SPRINT_LOG.md with accomplishments
5. Celebrate launch! 🎉

**Deliverable:** Pioneer Beta is live  
**Time estimate:** 4-5 hours + reflection  
**Blockers:** None

**Validation:**
- [ ] All critical bugs fixed
- [ ] Documentation updated
- [ ] Pioneer Beta is stable
- [ ] Ready for next phase
- [ ] Analytics are delivering WOW factor

---

## 📊 Sprint Metrics

**Track daily:**
- Hours worked
- Tasks completed
- Bugs found
- Bugs fixed
- Blockers encountered

**Track weekly:**
- Features completed
- Technical debt paid
- User feedback received

---

## 🚧 Risk Management

### **High-Risk Areas**

**1. Profile versioning might not work first try**
- Mitigation: Test early (Day 7)
- Fallback: Simpler approach (embed snapshot in result)

**2. Peak effort calculation might be computationally expensive**
- Mitigation: Cache results in `result_<sid>.json` (calculate once)
- Fallback: Limit to finding just FTP-relevant durations (20, 60min)

**3. Users with variable activity patterns (1 month vs 2 years)**
- Mitigation: Time-based grouping (weeks), not ride-based
- Fallback: Show warning if low activity (<1 ride/week)

**4. Strava API rate limits during batch import**
- Mitigation: Add delay between imports
- Fallback: Import in smaller batches

**5. FTP calculation might not match user expectations**
- Mitigation: Use multiple duration estimates, take best
- Fallback: Add "manual FTP override" in profile settings (future)

**6. Pioneer users might not have 50 rides available**
- Mitigation: Provide 10-ride option as alternative (though analytics less meaningful)
- Expectation setting: Onboarding guide emphasizes "50 rides recommended"
- Fallback: Analytics still work with fewer rides, but show warning about limited data

---

## 🎯 Definition of Done (Per Task)

**For each task to be "done":**
1. ✅ Code written and tested locally
2. ✅ No console errors
3. ✅ Works on Chrome + Firefox
4. ✅ Committed to git
5. ✅ Deployed to production (if applicable)
6. ✅ Validated against checklist

**For sprint to be "done":**
1. ✅ All critical tasks complete
2. ✅ All high tasks complete (or documented why skipped)
3. ✅ System is stable
4. ✅ Can demo to job interviewer
5. ✅ Pioneer users can test
6. ✅ **Power analytics deliver WOW factor**

---

## 📝 Daily Log Template

**Use this format each day:**

```
## Day X - [Date]
**Planned:**
- Task 1
- Task 2

**Actual:**
- Completed Task 1 (3 hours)
- Started Task 2 (1.5 hours)
- Discovered bug in X, fixed (0.5 hours)

**Blockers:**
- None / [Describe blocker]

**Tomorrow:**
- Finish Task 2
- Start Task 3
```

---

## 🔄 Adjustment Rules

**If falling behind:**
1. Re-prioritize: Cut 🟢 tasks first, then 🟡, never 🔴
2. Simplify: Reduce scope of features
   - Skip peak 1min/45min, just show 5/20/60
   - Skip projections, just show trend
3. Ask for help: Reach out if truly stuck
4. Extend deadline: Only if unavoidable (March 1 is soft deadline)

**If ahead of schedule:**
1. Add polish: Better UX, animations, styling on Power Profile
2. Add benchmarking: "Your FTP is in 'Good' category (2.5-3.5 W/kg)"
3. Pay more debt: Remove legacy routes, add tests
4. Prepare for April: Start thinking about goal-tracking feature

---

## 🎓 Learning Opportunities

**Job application talking points from this sprint:**

1. **Product management:** Balancing features vs technical debt
2. **Prioritization:** Critical vs nice-to-have (chose simple, impactful analytics over complex goals)
3. **User-centric:** Onboarding UX focus + WOW factor design
4. **Data integrity:** Profile versioning for determinism
5. **Full-stack:** Backend API + Frontend React + Rust computation
6. **System design:** SSOT architecture
7. **Agile:** 18-day sprint with clear deliverables
8. **Analytics:** Time-based progression tracking, smart FTP calculation
9. **Performance:** Efficient peak effort calculation with sliding windows

**Demo this sprint when interviewing!**

---

## ✅ Final Checklist (March 1)

**Must be done:**
- [ ] Signup has demographic fields
- [ ] Onboarding UI is clean
- [ ] Profile Dashboard (view + edit)
- [ ] Profile versioning works
- [ ] Can import 10 or 50 rides
- [ ] **Dashboard has key metrics widget (FTP, progress)**
- [ ] **Trends page exists with full Power Profile + FTP Progression**
- [ ] **Analytics update dynamically after each import**
- [ ] System is stable
- [ ] 5+ pioneer users testing
- [ ] **WOW factor achieved**

**Nice to have:**
- [ ] All duplicate routes removed
- [ ] Meta generation consolidated
- [ ] Import UX improved
- [ ] Mobile responsive
- [ ] Documentation complete
- [ ] Benchmarking ("Good" vs "Very Good" categories)

---

## 🚀 Post-Sprint (After March 1)

**Immediate next steps:**
1. Gather pioneer feedback on Power Profile + FTP Progression
2. Fix bugs reported
3. Plan April sprint (MVP launch)

**April sprint will add:**
- **Goal tracking** (build on FTP Progression - let users "lock" projections as goals)
- Intensity distribution (time in zones)
- Better trends (power curves, training load)
- Foundation for leaderboards (segment detection)
- Payment integration?

**Note:** Power Profile + FTP Progression are perfect foundation for goal tracking.
In April, just add: "Click projection to set as goal" → activate tracking.

---

## 💡 Key Changes from Original Plan

**REPLACED:**
- ❌ "Simple Trend Analysis" (generic watts/distance/elevation over time)
- ❌ "Simple Goals Feature" (manual goal setting + tracking)

**WITH:**
- ✅ **Power Profile** (FTP + peak efforts in W and W/kg)
- ✅ **FTP Progression** (time-based trend + future projections)

**Why this is better:**
1. **Higher ROI:** Concrete metrics (FTP, peaks) vs generic trends
2. **More motivating:** "You can reach 280W in 8 weeks" vs manual goal setting
3. **Simpler to implement:** No goal state management, no tracking UI
4. **Better foundation:** Can add goal tracking in April by building on progression
5. **WOW factor:** Users immediately see form + progress after importing 50 rides
6. **Works for all users:** FTP-chasers AND long-distance riders (like Jotunheimen case)

**Time estimate:**
- Original: 16-20 hours (8-10h trends + 8-10h goals)
- New: 20 hours (12h backend + 8h frontend)
- Same total effort, better outcome ✅

---

**Sprint starts:** Tuesday, Feb 11, 2026  
**Sprint ends:** Sunday, Mar 1, 2026  
**Let's build! 🚀**
