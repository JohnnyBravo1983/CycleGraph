
# ChatGPT Daily Start Script
**Use this EXACT text every morning. Just fill in the [BRACKETED] parts.**

---

```
I'm starting Day [X] of an 18-day sprint for CycleGraph Pioneer Beta.

CONTEXT:
- CycleGraph: Cycling analytics platform (power estimates without power meter)
- Backend: Python FastAPI + Rust physics engine
- Frontend: React + TypeScript + Vite
- Data: File-based (no database), SSOT model
- Deployed: Fly.io (backend) + Vercel (frontend)

ARCHITECTURE QUICK REF:
- Profile storage: state/users/<uid>/profile.json
- Profile versioning: profile_versions.jsonl
- Analysis results: result_<sid>.json (SSOT)
- Sessions index: sessions_index.json (SSOT)
- Meta cache: sessions_meta.json (derived, not SSOT)

---

TODAY'S WORK - DAY [X]:

TASK: [Copy task name from SPRINT_BACKLOG Day X]

GOAL: [Copy goal from SPRINT_BACKLOG Day X]

TASKS TO COMPLETE:
[Paste numbered list from SPRINT_BACKLOG Day X]

DELIVERABLE: [Copy deliverable from SPRINT_BACKLOG Day X]

TIME ESTIMATE: [Copy from SPRINT_BACKLOG Day X]

---

KEY FILES TO TOUCH:
- [file1.py] - [brief purpose]
- [file2.tsx] - [brief purpose]
- [file3.json] - [brief purpose]

---

SUCCESS CRITERIA:
[Paste validation checklist from SPRINT_BACKLOG Day X]

---

WHAT WAS DONE YESTERDAY (Day [X-1]):
[Paste from yesterday's "Handover to Tomorrow" section]

---

WHAT THIS BUILDS ON:
[1-2 sentences about dependencies]

---

I'll work through this with you today. We'll log progress in Work Log format as we go.

Ready to start with [first subtask]?
```

---

## 📋 HOW TO USE THIS EVERY MORNING

### **STEP 1: Copy template above**

### **STEP 2: Fill in [BRACKETED] parts:**

**Example for Day 1:**

```
I'm starting Day 1 of an 18-day sprint for CycleGraph Pioneer Beta.

CONTEXT:
- CycleGraph: Cycling analytics platform (power estimates without power meter)
- Backend: Python FastAPI + Rust physics engine
- Frontend: React + TypeScript + Vite
- Data: File-based (no database), SSOT model
- Deployed: Fly.io (backend) + Vercel (frontend)

ARCHITECTURE QUICK REF:
- Profile storage: state/users/<uid>/profile.json
- Profile versioning: profile_versions.jsonl
- Analysis results: result_<sid>.json (SSOT)
- Sessions index: sessions_index.json (SSOT)
- Meta cache: sessions_meta.json (derived, not SSOT)

---

TODAY'S WORK - DAY 1:

TASK: Signup form enhancement

GOAL: Users can signup with complete profile (gender, country, city, age)

TASKS TO COMPLETE:
1. Add fields to signup form UI:
   - Gender (dropdown: male/female)
   - Country (text input)
   - City (text input)
   - Age (number input, min 13, max 100)
2. Update frontend validation
3. Update `POST /api/auth/signup` to accept new fields
4. Store in `auth.json`
5. Test: Create new user, verify fields saved

DELIVERABLE: New users have complete demographic profile

TIME ESTIMATE: 4-5 hours

---

KEY FILES TO TOUCH:
- server/routes/auth_local.py - Backend signup endpoint
- client/src/pages/Signup.tsx - Signup form UI
- client/src/types/User.ts - User type definitions

---

SUCCESS CRITERIA:
- [ ] Signup form has 4 new fields
- [ ] Fields are required (can't skip)
- [ ] Data saves to auth.json
- [ ] Old users still work (backward compatible)

---

WHAT WAS DONE YESTERDAY (Day 0):
- Documentation reviewed and organized
- Sprint backlog finalized
- Development environment verified
- Ready to start coding

---

WHAT THIS BUILDS ON:
Existing signup form has username, email, password. We're adding demographic fields for leaderboards in April.

---

I'll work through this with you today. We'll log progress in Work Log format as we go.

Ready to start with the signup form UI?
```

### **STEP 3: Paste into new ChatGPT chat**

### **STEP 4: Start working**

---

## 📋 SIMPLIFIED FILL-IN CHECKLIST

**Every morning, you fill in:**

1. ⬜ Day number (Day [X])
2. ⬜ Task name (from SPRINT_BACKLOG)
3. ⬜ Goal (from SPRINT_BACKLOG)
4. ⬜ Tasks to complete (copy list from SPRINT_BACKLOG)
5. ⬜ Deliverable (from SPRINT_BACKLOG)
6. ⬜ Time estimate (from SPRINT_BACKLOG)
7. ⬜ Key files (3-5 files you'll touch)
8. ⬜ Success criteria (from SPRINT_BACKLOG)
9. ⬜ Yesterday's handover (from yesterday's report)
10. ⬜ What this builds on (1-2 sentences)
11. ⬜ First subtask (what to start with)

**Total time: 5-10 minutes**

---

## 💾 SAVE THIS AS

Save the template above as:
```
ChatGPT_Daily_Start_Script.md
```

**Then every morning:**
1. Open `ChatGPT_Daily_Start_Script.md`
2. Copy everything
3. Fill in [BRACKETED] parts
4. Paste into new ChatGPT chat
5. Start coding

---

## 🎯 IS THIS WHAT YOU WANTED?

- ✅ Fixed template (identical every day)
- ✅ You just fill in the variables
- ✅ Paste → Start working
- ✅ No thinking about structure

**Correct?**
