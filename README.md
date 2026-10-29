# Kairos: Data Lineage & Metadata Engine

Bitemporal data lineage infrastructure and execution-conditioned reasoning engine over static lineage graphs and runtime evidence.

---

## 📁 Repository Structure

```text
├── backend/                  # FastAPI service, routers, database pool, migrations, and tests
│   ├── app/                  # Application code (API routers, schemas, services, identity, auth)
│   ├── migrations/           # Numbered SQL database migration files (PostgreSQL / Supabase)
│   ├── tests/                # Backend API integration and unit tests
│   └── requirements.txt      # Backend Python dependencies
├── configs/                  # Project and environment configuration files
├── contracts/                # Shared domain types, interfaces, fixtures, and test mocks
├── data/olist/               # Tracked Olist sample dataset used by research/demo workflows
├── docs/                     # Current architecture, setup, research, and team documentation
│   ├── archive/               # Historical notes and superseded setup/task documents
│   └── workstreams/           # M1–M5 independent work assignments
├── frontend/                 # React/Vite app, existing CSS, and dashboard compatibility runtime
│   ├── src/                  # React app shell and dashboard view bridge
│   └── *.css                 # Existing Kairos design system and page styles
├── ingestion/                # Lineage & metadata extractors
│   ├── cli/                  # CLI ingestion utilities and configuration templates
│   ├── dbt/                  # dbt manifest/catalog ingestion adapter
│   ├── openlineage/          # OpenLineage event parsing and normalizers
│   └── sql/                  # SQLGlot static lineage parser & test corpus
├── research/                 # Reasoning engine, baselines, and benchmark suite
│   ├── baselines/            # Baseline models B1 through B5
│   ├── experiments/          # Protocol execution runner
│   ├── ground_truth/         # Ground truth providers & reference interpreters
│   ├── metrics/              # Lineage evaluation metrics
│   ├── missingness/          # MCAR loss simulator
│   └── reasoning/            # FourStateEngine and rules R1–R5
├── scripts/                  # Operational, diagnostic, and CI verification scripts
│   ├── db/                   # Database inspection and diagnostics utilities
│   ├── check_import_boundaries.py  # CI rule verification
│   ├── run_migration.py      # Database migration execution script
│   └── test_connection.py    # Database connectivity test
└── tests/                    # Core pytest test suite (engine, baselines, contracts, leakage)

Local source snapshots (such as Hatchable exports and Stitch ZIPs) belong in
`references/snapshots/`. ZIP files are ignored by Git; they remain local
reference material and are not included in a clone.
```

---

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Linux/macOS
# or: .venv\Scripts\Activate.ps1 # On Windows PowerShell

# Install the application and test dependencies from the project manifest
python -m pip install -e ".[dev]"
```

### 1.1 Frontend Setup

```bash
cd frontend
npm ci
npm run build
cd ..
```

The React/Vite build keeps the existing Kairos CSS, palette, and Stitch sign-in
page. Dashboard views still use the existing `frontend/app.js` renderer while
they are migrated into React components. `scripts/run_ui.py` rebuilds the
frontend before starting FastAPI.

### 2. Verify Import Boundaries & Tests
```bash
# Check architectural isolation rules (checked in CI)
python scripts/check_import_boundaries.py

# Run test suite
python -m pytest -q
```

### 3. Database & Migrations

Kairos uses the team's **shared Supabase project** for Auth and hosted Postgres.
You do not need to install PostgreSQL locally for the product demo. Get the
database pooler URI and API keys from the project's Supabase dashboard and
follow [`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md). Local PostgreSQL is
optional for isolated research experiments and offline development.

```bash
# Use the existing ignored .env; if it is missing, create it from .env.example
# and fill it with the team's Supabase project settings. Do not overwrite an existing .env.

# Test database connection
python scripts/test_connection.py

# Apply migrations once as described in docs/SUPABASE_SETUP.md
```

The legacy `scripts/run_migration.py` applies only migration 0001. Follow the
numbered migration guide instead of using that script as a complete setup.

### 4. Run Backend Server
```bash
python scripts/run_ui.py
# API documentation available at: http://127.0.0.1:8000/docs
```

---

## 🔒 Architectural Boundaries (CI Enforced)

- `research/reasoning` and `research/baselines` never import `contracts.truth`, `research.ground_truth`, `contracts.interfaces`, `contracts.mocks` or `ingestion`.
- `research/ground_truth` never imports `ingestion`, `sqlglot`, `research.reasoning` or `research.baselines`.
- `research/` never imports `backend` or `frontend`.
- Leakage guards raise `LeakageError` if ground-truth objects or labels leak into reasoning or baselines.
