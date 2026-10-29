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
├── docs/                     # Architectural specs, research pack, guides, and pattern analysis
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
```

---

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Linux/macOS
# or: .venv\Scripts\Activate.ps1 # On Windows PowerShell

# Install dependencies
pip install -r backend/requirements.txt
pip install pytest sqlglot
```

### 2. Verify Import Boundaries & Tests
```bash
# Check architectural isolation rules (checked in CI)
python scripts/check_import_boundaries.py

# Run test suite
python -m pytest -q
```

### 3. Database & Migrations
```bash
# Copy and configure environment variables
cp .env.example .env

# Test database connection
python scripts/test_connection.py

# Run migrations
python scripts/run_migration.py
```

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
