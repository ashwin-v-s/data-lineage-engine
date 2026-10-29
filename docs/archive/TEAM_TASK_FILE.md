# KAIROS — Team Task File
> Who does what, in what order, with what files
> **You (M1 = Jatin) + M5 person**
> Last updated: Week 2

---

## HOW TO USE THIS FILE

- Do tasks IN ORDER — each step depends on the previous
- Mark ✅ when done
- Share this file in your group chat
- I (Kiro) will write the code for each step — just tell me when you're ready

---

## PHASE 1 — DATABASE SETUP
> **Do this first. Everything else depends on it.**
> Time: 1 hour total

---

### TASK 1 — Create Supabase Project
**Who:** Jatin (M1)
**Time:** 10 minutes
**Status:** [ ] Not done

**Steps:**
1. Go to https://supabase.com
2. Sign up with your email
3. Click "New Project"
   - Name: `kairos`
   - Password: `kairos123`
   - Region: Southeast Asia (Singapore) or South Asia (Mumbai)
4. Wait 2 minutes for project to start
5. Go to: Settings → Database → Connection String → URI
6. Copy the URL — looks like:
   ```
   postgresql://postgres:kairos123@db.XXXX.supabase.co:5432/postgres
   ```
7. Share this URL in your team group chat

**Done when:** You have the Supabase URL

---

### TASK 2 — Run Database Migration
**Who:** Jatin (M1)
**Time:** 5 minutes
**Status:** [ ] Not done
**Depends on:** Task 1

**Steps:**
1. Install psql if not installed:
   - Download from: https://www.postgresql.org/download/windows/
   - OR use: https://supabase.com/dashboard → SQL Editor (easier!)

2. Using Supabase SQL Editor (recommended — no install needed):
   - Go to your Supabase project
   - Click "SQL Editor" in left sidebar
   - Click "New Query"
   - Copy ALL contents of `E:\EDI-Metadata_Lineage\backend\migrations\0001_core.sql`
   - Paste into SQL editor
   - Click "Run"
   - Should see: "Success. No rows returned"

3. Verify tables created:
   - In SQL Editor run: `SELECT tablename FROM pg_tables WHERE schemaname = 'public';`
   - Should see: dataset, column_record, job, execution_run, raw_event, evidence, lineage_edge, edge_temporal_version, execution_state, projection_outbox

**Done when:** 10 tables visible in Supabase Table Editor

---

### TASK 3 — Create .env Files (BOTH OF YOU)
**Who:** Jatin (M1) AND M5 person — BOTH need to do this
**Time:** 2 minutes each
**Status:** [ ] Not done
**Depends on:** Task 1

**Jatin — create this file:**
`E:\EDI-Metadata_Lineage\.env`

```
DATABASE_URL=postgresql://postgres:kairos123@db.XXXX.supabase.co:5432/postgres
KAIROS_ENV=development
KAIROS_LOG_LEVEL=INFO
```

**M5 person — create same file in their repo folder**

**IMPORTANT:** Never commit .env to GitHub — it's already in .gitignore

**Done when:** Both of you have .env file with Supabase URL

---

## PHASE 2 — BACKEND WIRING
> **Connect API routes to real database**
> Time: 3-4 hours

---

### TASK 4 — Add Database Connection Module
**Who:** Jatin (M1)
**Time:** 30 minutes
**Status:** [ ] Not done
**Depends on:** Task 3
**File to create:** `E:\EDI-Metadata_Lineage\backend\app\db.py`

**What it does:** Creates the database connection that all routes will use

**Tell Kiro:** "Write db.py for Supabase connection"
→ Kiro will write the complete file for you

---

### TASK 5 — Fix CORS in main.py
**Who:** M5 person
**Time:** 15 minutes
**Status:** [ ] Not done
**Depends on:** Task 4
**File to modify:** `E:\EDI-Metadata_Lineage\backend\app\main.py`

**Problem:** Frontend at localhost:3000 gets blocked when calling backend at localhost:8000
**Fix:** Add CORS middleware

**Tell Kiro:** "Fix CORS in backend main.py"
→ Kiro will write the fix

---

### TASK 6 — Wire Lineage Route to Database
**Who:** M5 person
**Time:** 2 hours
**Status:** [ ] Not done
**Depends on:** Task 4 and Task 5
**File to modify:** `E:\EDI-Metadata_Lineage\backend\app\api\routes\lineage.py`

**Problem right now:**
```python
# Currently returns EMPTY every time:
return {"asset_id": asset_id, "nodes": [], "edges": []}
```

**What it should do:**
- Query Supabase `lineage_edge` and `edge_temporal_version` tables
- Return real nodes and edges
- Support `as_of` and `recorded_as_of` parameters

**Tell Kiro:** "Write the real lineage route that queries Supabase"
→ Kiro will write the complete implementation

---

### TASK 7 — Wire Search Route to Database
**Who:** M5 person
**Time:** 1 hour
**Status:** [ ] Not done
**Depends on:** Task 4
**File to modify:** `E:\EDI-Metadata_Lineage\backend\app\api\routes\search.py`

**Problem right now:**
```python
# Currently returns EMPTY every time:
return {"results": [], "total": 0}
```

**What it should do:**
- Search `dataset` and `column_record` tables in Supabase
- Return matching assets

**Tell Kiro:** "Write the real search route that queries Supabase"

---

### TASK 8 — Add Dependency State Route
**Who:** M5 person
**Time:** 1.5 hours
**Status:** [ ] Not done
**Depends on:** Task 6
**File to modify:** `E:\EDI-Metadata_Lineage\backend\app\api\routes\lineage.py`

**What it should do:**
- Accept run_id, source column, target column
- Pull evidence from Supabase
- Run FourStateEngine on that evidence
- Return the reasoning state (OBSERVED / POSSIBLE / REFUTED / UNKNOWN)

**Tell Kiro:** "Write the dependency state route that runs the reasoning engine"

---

## PHASE 3 — DATA LOADING
> **Put real data into Supabase**
> Time: 2 hours

---

### TASK 9 — Wire M1 SQLGlot Output to Supabase
**Who:** Jatin (M1)
**Time:** 2 hours
**Status:** [ ] Not done
**Depends on:** Task 4
**File to create:** `E:\EDI-Metadata_Lineage\ingestion\sql\ingest.py`

**What it does:**
- Takes your SQLGlot StaticEvidence objects
- Stores them in Supabase `evidence` table
- This is the MISSING LINK between your SQL parsing and the database

**Tell Kiro:** "Write ingestion/sql/ingest.py to store StaticEvidence in Supabase"
→ Kiro will write the complete file

---

### TASK 10 — Load Sample Datasets into Supabase
**Who:** Jatin (M1)
**Time:** 30 minutes
**Status:** [ ] Not done
**Depends on:** Task 2 and Task 9
**File to use:** `E:\EDI-Metadata_Lineage\ingestion\openlineage\load_datasets.py`

**What it does:**
- Creates sample datasets (employees, orders, customers tables) in Supabase
- These become the nodes visible in the UI

**Steps:**
1. Make sure .env is set up (Task 3)
2. Run:
   ```powershell
   cd E:\EDI-Metadata_Lineage
   python ingestion/openlineage/load_datasets.py
   ```
3. Check Supabase Table Editor → dataset table should have rows

**Done when:** dataset table in Supabase has at least 3-4 rows

---

### TASK 11 — Run M1 SQLGlot Corpus Through Supabase
**Who:** Jatin (M1)
**Time:** 30 minutes
**Status:** [ ] Not done
**Depends on:** Task 9 and Task 10
**What it does:** Runs all 11 SQL corpus cases through SQLGlot → stores evidence in Supabase

**Steps:**
1. Run the ingest script you created in Task 9:
   ```powershell
   cd E:\EDI-Metadata_Lineage
   python ingestion/sql/ingest.py
   ```
2. Check Supabase → evidence table should have rows
3. Check Supabase → lineage_edge table should have rows

**Done when:** evidence table has rows from corpus SQL cases

---

### TASK 12 — Load Synthetic Runtime Events
**Who:** Jatin (M1)
**Time:** 30 minutes
**Status:** [ ] Not done
**Depends on:** Task 10
**File:** `E:\EDI-Metadata_Lineage\ingestion\openlineage\generate_synthetic_events.py`

**Steps:**
```powershell
cd E:\EDI-Metadata_Lineage
python ingestion/openlineage/generate_synthetic_events.py
python ingestion/openlineage/load_raw_events.py
python ingestion/openlineage/process_runtime_events.py
```

**Done when:** raw_event and evidence tables have runtime event rows

---

## PHASE 4 — FRONTEND FIX
> **Connect UI to real backend**
> Time: 1.5 hours

---

### TASK 13 — Fix Frontend API URL Mismatch
**Who:** M5 person
**Time:** 1 hour
**Status:** [ ] Not done
**Depends on:** Task 6
**File:** `E:\EDI-Metadata_Lineage\frontend\src\api\client.ts`

**Problem:**
- Frontend calls `/api/v1/lineage/{entity}`
- Backend has route at `/api/v1/assets/{asset_id}/lineage`
- These don't match → 404 error

**Tell Kiro:** "Fix the frontend API client URL mismatch"
→ Kiro will align frontend calls to backend routes

---

### TASK 14 — Test Full Frontend Flow
**Who:** M5 person + Jatin
**Time:** 30 minutes
**Status:** [ ] Not done
**Depends on:** All previous tasks

**Steps:**
1. Start backend:
   ```powershell
   cd E:\EDI-Metadata_Lineage
   uvicorn backend.app.main:app --reload --port 8000
   ```
2. Start frontend:
   ```powershell
   cd E:\EDI-Metadata_Lineage\frontend
   npm run dev
   ```
3. Open http://localhost:3000
4. Should see real nodes from Supabase
5. Click a node → should see real lineage

**Done when:** Frontend shows real data from Supabase (not mock)

---

## PHASE 5 — RESEARCH COMPLETION
> **Complete the research experiment parts**
> Time: 2 hours

---

### TASK 15 — Fill Protocol v1.yaml
**Who:** Jatin (M1)
**Time:** 1 hour
**Status:** [ ] Not done
**File:** `E:\EDI-Metadata_Lineage\research\protocol\v1.yaml`
**Problem:** Has 26 TBD values — experiment runner can't execute

**Tell Kiro:** "Fill in research/protocol/v1.yaml with proper values"
→ Kiro will fill all TBD values based on what's implemented

---

### TASK 16 — Run Experiment with Real Data
**Who:** Jatin (M1)
**Time:** 1 hour
**Status:** [ ] Not done
**Depends on:** Task 11, Task 12, Task 15
**Command:**
```powershell
cd E:\EDI-Metadata_Lineage
python research/experiments/run.py --protocol research/protocol/v1.yaml
```

**Done when:** New result files appear in `research/results/` that are NOT named `plumbing`

---

### TASK 17 — Wire Ground Truth (ReferenceInterpreter)
**Who:** Jatin (M1)
**Time:** 1 hour
**Status:** [ ] Not done
**File:** `E:\EDI-Metadata_Lineage\research\ground_truth\reference_interpreter.py`

**What it does:** Replaces ProvSQL — computes PROPAGATED/NOT_PROPAGATED for simple SQL in pure Python

**Tell Kiro:** "Wire the ReferenceInterpreter to the experiment runner"

---

## PHASE 6 — PUSH AND PR
> **Commit everything and create PRs**
> Time: 30 minutes

---

### TASK 18 — Commit M1 Work
**Who:** Jatin (M1)
**Time:** 15 minutes
**Status:** [ ] Not done

```powershell
cd E:\EDI-Metadata_Lineage
git checkout -b feature/member-1-db-integration
git add ingestion/sql/ingest.py
git add backend/app/db.py
git add research/protocol/v1.yaml
git commit -m "M1: Wire SQLGlot to Supabase, fill protocol, add DB module"
git push -u origin feature/member-1-db-integration
```

---

### TASK 19 — Commit M5 Work
**Who:** M5 person
**Time:** 15 minutes
**Status:** [ ] Not done

```powershell
git checkout -b feature/backend-ui-db-integration
git add backend/app/api/routes/
git add backend/app/main.py
git add frontend/src/api/client.ts
git commit -m "M5: Wire all API routes to Supabase, fix CORS, fix frontend URLs"
git push -u origin feature/backend-ui-db-integration
```

---

## SUMMARY TABLE

| Task | Who | Time | Priority | Status |
|------|-----|------|----------|--------|
| 1. Create Supabase | Jatin | 10 min | 🔴 FIRST | [ ] |
| 2. Run migration | Jatin | 5 min | 🔴 FIRST | [ ] |
| 3. Create .env | BOTH | 2 min | 🔴 FIRST | [ ] |
| 4. DB connection module | Jatin | 30 min | 🔴 | [ ] |
| 5. Fix CORS | M5 | 15 min | 🔴 | [ ] |
| 6. Wire lineage route | M5 | 2 hrs | 🔴 | [ ] |
| 7. Wire search route | M5 | 1 hr | 🔴 | [ ] |
| 8. Add dependency route | M5 | 1.5 hrs | 🔴 | [ ] |
| 9. SQLGlot → Supabase | Jatin | 2 hrs | 🟡 | [ ] |
| 10. Load sample datasets | Jatin | 30 min | 🟡 | [ ] |
| 11. Run corpus through DB | Jatin | 30 min | 🟡 | [ ] |
| 12. Load runtime events | Jatin | 30 min | 🟡 | [ ] |
| 13. Fix frontend URLs | M5 | 1 hr | 🟡 | [ ] |
| 14. Test full flow | BOTH | 30 min | 🟡 | [ ] |
| 15. Fill protocol.yaml | Jatin | 1 hr | 🟢 | [ ] |
| 16. Run experiment | Jatin | 1 hr | 🟢 | [ ] |
| 17. Wire ReferenceInterpreter | Jatin | 1 hr | 🟢 | [ ] |
| 18. Commit M1 work | Jatin | 15 min | 🟢 | [ ] |
| 19. Commit M5 work | M5 | 15 min | 🟢 | [ ] |

**Total Jatin:** ~9 hours
**Total M5:** ~7 hours
**Total together:** ~2 days

---

## WHAT YOU'LL HAVE WHEN DONE

```
35% complete NOW
        ↓
85% complete AFTER ALL TASKS
        ↓
Real SQL → SQLGlot ✅ → Supabase → FourStateEngine ✅ → API → UI
```

---

## HOW TO USE KIRO FOR EACH TASK

For every coding task, just tell Kiro:

- "Write Task 4 — db.py for Supabase"
- "Write Task 6 — wire lineage route to DB"
- "Write Task 9 — SQLGlot to Supabase ingest.py"
- etc.

Kiro will write the complete code for each task.

---

## NOTES

- Do NOT commit `.env` file to GitHub
- If Supabase pauses (after 1 week inactivity), just go to Supabase dashboard and click "Resume"
- If a task fails, tell Kiro what error you got — will fix immediately
- Tasks 1-3 MUST be done before anything else
- Jatin and M5 can work on Phase 2 and Phase 3 IN PARALLEL after Task 4 is done
