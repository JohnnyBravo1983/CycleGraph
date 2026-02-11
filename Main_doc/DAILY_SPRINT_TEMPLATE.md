# Day [1] - [11.02] - [Focus Area]
**Sprint:** Pioneer Beta (Feb 11 - Mar 1, 2026)  
**Task:** [Task name from SPRINT_BACKLOG.md]  
**Priority:** 🔴/🟡/🟢

---

## 📋 Today's Mission

**Goal:** [Signup form enhancement]

**Tasks from SPRINT_BACKLOG.md:**
1. [Task 1] Add fields to signup form UI:
   - Gender (dropdown: male/female)
   - Country (text input or dropdown)
   - City (text input)
   - Age (number input, min 13, max 100)
2. [Task 2]Update frontend validation
3. [Task 3] Update `POST /api/auth/signup` to accept new fields 
4. [Task4] Store in `auth.json`
   [Task5]

**Deliverable:** [Create new user, verify fields saved]

**Time estimate:** [4-5 Hours]

---

## 🏗️ Architecture Context

### **File Structure (Relevant for Today):**
```
[Paste relevant file paths from project]
```

### **Key Files to Touch:**
### **Key Files to Touch:**
- `server/routes/auth_local.py` - Signup endpoint
- `client/src/pages/Signup.tsx` - Signup form UI
- `client/src/types/User.ts` - User type definition

### **SSOT Rules (Always Respect):**
- `sessions_index.json` → Which sessions exist
- `result_<sid>.json` → Metrics (SSOT)
- `profile.json` → Current user profile
- `sessions_meta.json` → Cache only

---

## 🔗 Dependencies

**What was done yesterday (Day [X-1]):**
- [Item 1]
- [Item 2]
- [Item 3]

**Blockers resolved:**
- [If any]

**What this builds on:**
- [Which previous work this depends on]

---

## 🎯 Success Criteria (from SPRINT_BACKLOG.md)

**Validation checklist:**
- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]
- [ ] [Criterion 4]

**Testing requirements:**
- [ ] Code runs without errors
- [ ] Works in Chrome + Firefox
- [ ] No console errors
- [ ] Committed to git

---

## 🧪 Testing Strategy

**Unit tests needed:**
- [Test 1]

**Integration tests needed:**
- [Test 2]

**Manual tests:**
1. [Scenario 1]
2. [Scenario 2]

**Edge cases to verify:**
- [Edge case 1]
- [Edge case 2]

---

## 📚 Reference Documents

**Read before starting:**
- ARCHITECTURE.md (sections: [relevant sections])
- API_REFERENCE.md (endpoints: [relevant endpoints])
- TECHNICAL_DEBT.md (item #[X] if touching that area)

**Quick refs:**
- Profile storage: `state/users/<uid>/profile.json`
- Profile versioning: `profile_versions.jsonl`
- Analysis results: `result_<sid>.json`

---

## 🚨 Known Issues / Watch Out For

**Common pitfalls:**
- [Issue 1 to avoid]
- [Issue 2 to avoid]

**Technical constraints:**
- [Constraint 1]
- [Constraint 2]

---

## 🔧 Development Environment

**Backend:**
```bash
cd server
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -m uvicorn main:app --reload
```

**Frontend:**
```bash
cd client
npm run dev
```

**Rust (if needed):**
```bash
cd core
cargo build --release
maturin develop --features python
```

---

## 💬 Work Log (Fill in as you go)

### **Started:** [Time]

**Initial thoughts:**
- [First impressions of task]

### **Progress Updates:**

**[Time] - Started [subtask]**
- [What you're doing]

**[Time] - Completed [subtask]**
- [What worked]
- [What didn't work]
- [Changes made]

**[Time] - Blocker encountered**
- [Description]
- [How resolved]

### **Completed:** [Time]

---

## 📊 End of Day Report

### **What was completed:**
- [x] [Task 1]
- [x] [Task 2]
- [ ] [Task 3] (if incomplete)

### **What works:**
- [Feature 1] - tested and verified
- [Feature 2] - committed to git

### **What doesn't work yet:**
- [Issue 1] - needs fixing tomorrow
- [Issue 2] - blocked by [X]

### **Files changed:**
```
server/routes/profile_router.py
client/src/pages/Dashboard.tsx
client/src/components/ProfileCard.tsx
```

### **Commits made:**
```
git log --oneline -5
```

### **Testing results:**
- [ ] Unit tests: X passed / Y failed
- [ ] Integration tests: X passed / Y failed
- [ ] Manual smoke test: ✅/❌
- [ ] Browser compatibility: ✅/❌

### **Validation against checklist:**
- [x] [Criterion 1] ✅
- [x] [Criterion 2] ✅
- [ ] [Criterion 3] ⚠️ (partial)
- [ ] [Criterion 4] ❌ (blocked)

---

## 🔄 Handover to Tomorrow

### **What needs to continue:**
- [Task that's 50% done]
- [Blocker that needs resolution]

### **What to start tomorrow (Day [X+1]):**
- [Next task from SPRINT_BACKLOG.md]

### **Notes for tomorrow's session:**
- [Important thing to remember]
- [Gotcha discovered today]
- [Better approach to try]

---

## 🐛 Bugs Found

### **Bug #1: [Title]**
- **Severity:** Critical/High/Medium/Low
- **Description:** [What's broken]
- **Steps to reproduce:** [1, 2, 3]
- **Expected:** [What should happen]
- **Actual:** [What actually happens]
- **Fix:** [How it was fixed / needs fixing]

---

## 💡 Learnings & Observations

**What went well:**
- [Thing 1]

**What was harder than expected:**
- [Thing 2]

**Better approach for next time:**
- [Idea 1]

**Technical debt created:**
- [Shortcuts taken that need cleanup later]

---

## 📎 Attachments

**Screenshots:**
- [Link to screenshot 1]
- [Link to screenshot 2]

**Code snippets (if needed for tomorrow):**
```python
# Important snippet from today
def example():
    pass
```

---

**Status:** ✅ Done / 🚧 In Progress / ❌ Blocked  
**Ready for QA:** Yes/No  
**Merge to main:** Yes/No/Wait

---

## 🎯 Claude Review Required?

**Does this need Claude review before continuing?**
- [ ] Yes - Architecture decision made
- [ ] Yes - Major refactor done
- [ ] Yes - Blocker encountered
- [ ] No - Straightforward implementation

**If yes, questions for Claude:**
1. [Question 1]
2. [Question 2]
