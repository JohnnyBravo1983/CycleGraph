# Sprint Workflow Guide - Claude vs ChatGPT
**Sprint:** Pioneer Beta (Feb 11 - Mar 1, 2026)

---

## 🎯 Two-Track System

### **Track 1: Claude (Roadmap & Quality)**
**Chat name:** "CycleGraph - Sprint Oversight"  
**Purpose:** Strategic decisions, architecture, documentation  
**Frequency:** 2-3 times per week + when blocked

### **Track 2: ChatGPT (Daily Execution)**
**Chat name:** "Day [X] - [Task Name]"  
**Purpose:** Coding, debugging, implementation  
**Frequency:** Daily (new chat each day)

---

## 📋 Daily Workflow

### **Morning Routine (with ChatGPT)**

1. **Create new chat:** "Day [X] - [Task Name]"

2. **Paste context package:**
   ```
   [Copy DAILY_SPRINT_TEMPLATE.md]
   [Fill in Day X details from SPRINT_BACKLOG.md]
   [Add yesterday's handover notes]
   ```

3. **Start work:**
   - ChatGPT helps you code
   - ChatGPT helps debug
   - ChatGPT suggests solutions

4. **Throughout day:**
   - Fill in Work Log section
   - Document blockers
   - Update progress

---

### **Evening Routine (with ChatGPT)**

1. **Complete End of Day Report** in chat

2. **Export report:**
   - Copy final report from chat
   - Save as: `logs/day_[X]_report.md`

3. **Prepare handover:**
   - What's done
   - What's incomplete
   - What to start tomorrow

4. **Commit work:**
   ```bash
   git add .
   git commit -m "Day [X]: [Brief summary]"
   git push
   ```

---

## 🔄 When to Switch to Claude

### **Use Claude when:**

1. **Architecture decisions needed:**
   - "Should I use Option A or Option B?"
   - "How should this feature integrate with existing system?"
   - "Is this approach aligned with SSOT principles?"

2. **Major blockers:**
   - "Task seems harder than estimated - should we simplify?"
   - "Found a fundamental issue with current design"
   - "Need to change sprint plan"

3. **Weekly reviews:**
   - End of Week 1 (Day 6)
   - End of Week 2 (Day 12)
   - End of Week 3 (Day 18)

4. **Documentation updates:**
   - Update CURRENT_STATE.md
   - Update SPRINT_BACKLOG.md
   - Update TECHNICAL_DEBT.md

5. **Quality checks:**
   - "Does this code follow best practices?"
   - "Is this implementation deterministic?"
   - "Should I refactor before continuing?"

---

## 💬 Context Transfer to Claude

**When asking Claude for help, provide:**

1. **Current day:** "Day [X] of 18"

2. **Task:** "Working on [task name from SPRINT_BACKLOG.md]"

3. **Problem:** "[Specific issue]"

4. **What you've tried:** "[Approaches attempted]"

5. **Relevant code/files:** "[Paste snippet or describe]"

6. **Question:** "[Clear question]"

**Example:**
```
I'm on Day 3 of Pioneer Beta sprint, working on "Profile in Dashboard - Edit".

I'm implementing the profile edit form, but I'm unsure:
Should profile versioning happen on every save, or only when critical fields (weight, CdA) change?

From ARCHITECTURE.md, I see profile_versions.jsonl is append-only, 
but I don't want to spam it with minor edits (e.g., user fixes typo in bike name).

What's the right approach that respects determinism?
```

---

## 📊 Weekly Review with Claude

**Every Sunday evening:**

1. **Open Claude chat:** "CycleGraph - Sprint Oversight"

2. **Provide week summary:**
   ```
   Week [1/2/3] of Pioneer Beta Sprint
   
   Completed:
   - Day 1: ✅
   - Day 2: ✅
   - Day 3: ⚠️ (partial)
   - Day 4: ✅
   - Day 5: ✅
   - Day 6: ✅
   
   Blockers encountered:
   - [Blocker 1 - resolved]
   - [Blocker 2 - still open]
   
   Behind schedule?: [Yes/No - by X days]
   
   What needs adjustment?: [Your thoughts]
   ```

3. **Get Claude's assessment:**
   - Should sprint plan be adjusted?
   - Any red flags in approach?
   - Priorities correct?

4. **Update documents:**
   - CURRENT_STATE.md (if major progress)
   - SPRINT_BACKLOG.md (mark completed tasks)
   - TECHNICAL_DEBT.md (if new debt created/paid)

---

## 🎯 Context Packages for Each Day

**For ChatGPT, each day needs:**

### **Minimal Context (Fast Start):**
```
Day [X] Template + Yesterday's handover notes
```

### **Medium Context (Most Days):**
```
Day [X] Template
+ Yesterday's handover notes
+ Relevant section from ARCHITECTURE.md
+ Relevant endpoints from API_REFERENCE.md
```

### **Full Context (Complex Days):**
```
Day [X] Template
+ Yesterday's handover notes
+ Full ARCHITECTURE.md
+ Full API_REFERENCE.md
+ Relevant TECHNICAL_DEBT.md section
+ Code snippets from previous days
```

**Rule of thumb:** Start minimal, add context as needed

---

## 🔧 ChatGPT Prompt Optimization

### **Good Opening Prompt (Day 1):**
```
I'm starting Day 1 of an 18-day sprint to build Pioneer Beta for CycleGraph.

Context:
- CycleGraph is a cycling analytics platform
- Backend: Python FastAPI + Rust physics engine
- Frontend: React + TypeScript
- File-based state (no database)
- SSOT model (result_<sid>.json is truth)

Today's task: Add demographic fields to signup form
- Gender, country, city, age
- Update backend endpoint
- Store in auth.json

I'll work through this with you today and fill in the daily template as we go.

Ready to start?
```

### **Good Daily Continuation (Day 2+):**
```
Day [X] of Pioneer Beta Sprint.

Yesterday we completed: [Brief summary]

Today's task: [Task name]

Here's my filled template:
[Paste DAILY_SPRINT_TEMPLATE with Day X details]

Let's start with [first subtask].
```

---

## 📁 File Organization

### **Your Local Structure:**
```
CycleGraph/
├── Main_Document/
│   ├── 0_DYNAMISK_DOD.md
│   ├── 1_CURRENT_STATE.md
│   ├── 2_ARCHITECTURE.md
│   ├── 3_PROJECT_HISTORY.md
│   ├── 4_API_REFERENCE.md
│   ├── 5_TECHNICAL_DEBT.md
│   └── 6_SPRINT_BACKLOG.md
├── Sprint_Logs/
│   ├── day_01_report.md
│   ├── day_02_report.md
│   ├── ...
│   ├── week_1_review.md
│   └── week_2_review.md
└── [code repos: server/, client/, core/]
```

---

## ✅ Daily Checklist

**Before starting work:**
- [ ] New ChatGPT chat created (Day X name)
- [ ] Template filled with today's task
- [ ] Yesterday's handover read
- [ ] Coffee ready ☕

**During work:**
- [ ] Work log updated regularly
- [ ] Commits made incrementally
- [ ] Tests run after each change
- [ ] Blockers documented immediately

**End of day:**
- [ ] End of Day Report completed
- [ ] Report saved to Sprint_Logs/
- [ ] Handover notes written
- [ ] Code committed and pushed
- [ ] Tomorrow's template prepared

**Weekly (Sunday):**
- [ ] Week review with Claude
- [ ] SPRINT_BACKLOG.md updated
- [ ] CURRENT_STATE.md updated (if needed)
- [ ] Plan for next week clear

---

## 🚨 Emergency Protocol

**If seriously blocked (>2 hours stuck):**

1. **Stop coding**
2. **Document blocker** in daily template
3. **Switch to Claude** immediately:
   ```
   BLOCKER on Day [X]
   
   Task: [Task name]
   Problem: [Clear description]
   Tried: [What you attempted]
   Impact: [How this affects sprint]
   
   Need architecture decision / guidance
   ```
4. **Get Claude's input**
5. **Return to ChatGPT** with solution

**Don't waste time being stuck - Claude is there for this!**

---

## 💡 Pro Tips

### **For ChatGPT:**
- Start specific: "Help me implement X" not "What should I do?"
- Share code early: Paste what you have, ask for improvements
- Test frequently: Don't code for 2 hours then test
- Document as you go: Fill template throughout day

### **For Claude:**
- Ask big questions: Architecture, strategy, priorities
- Provide context: Don't assume Claude remembers everything
- Request document updates: "Can you update TECHNICAL_DEBT.md?"
- Use for reviews: "Does this approach make sense?"

### **General:**
- Commit small, commit often
- Write clear commit messages
- Keep both chats open (tab switching)
- Save daily reports religiously

---

## 🎓 Context Continuity Rules

**ChatGPT loses context daily:**
- ✅ Use template to restore context
- ✅ Paste yesterday's handover
- ✅ Reference files explicitly ("See ARCHITECTURE.md section on profiles")
- ❌ Don't assume it remembers yesterday

**Claude maintains sprint context:**
- ✅ Can reference earlier conversations in same chat
- ✅ Knows the full documentation
- ✅ Tracks sprint progress
- ⚠️ Still remind it which day you're on

---

## 📊 Success Metrics

**Daily:**
- [ ] Task from SPRINT_BACKLOG completed
- [ ] Tests passing
- [ ] Code committed
- [ ] Report saved

**Weekly:**
- [ ] 6 days completed
- [ ] On track with sprint plan
- [ ] No critical blockers
- [ ] Documentation updated

**Sprint:**
- [ ] All 18 days completed
- [ ] Pioneer Beta launches March 1
- [ ] Can demo to job interviewer
- [ ] 5+ pioneer users testing

---

**Remember:** ChatGPT is your daily partner, Claude is your senior architect.

Use both strategically! 🚀
