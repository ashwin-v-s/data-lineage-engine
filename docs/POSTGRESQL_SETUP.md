# PostgreSQL Setup Guide (M3)

Quick setup guide for installing PostgreSQL and creating the Kairos database.

---

## Option 1: Native Windows Installation (Recommended for Development)

### Install PostgreSQL

**Using winget:**
```powershell
winget install PostgreSQL.PostgreSQL
```

**Or download installer:**
- Go to: https://www.postgresql.org/download/windows/
- Download and run the installer
- Default port: 5432
- Set a password for `postgres` user (remember this!)

### Add to PATH

Add PostgreSQL bin directory to your PATH:
```
C:\Program Files\PostgreSQL\16\bin
```

Or via PowerShell:
```powershell
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"
```

### Verify Installation

```powershell
psql --version
# Should show: psql (PostgreSQL) 16.x
```

### Create Database

```powershell
# Connect as postgres user
psql -U postgres

# In psql:
CREATE DATABASE kairos;
\q
```

### Apply Migration

```powershell
cd d:\Meta_Data\data-lineage-engine
psql -U postgres kairos < backend\migrations\0001_core.sql
```

### Verify Tables

```powershell
psql -U postgres kairos -c "\dt"
```

Should show:
```
 Schema |         Name          | Type  |  Owner   
--------+-----------------------+-------+----------
 public | column_record         | table | postgres
 public | dataset               | table | postgres
 public | edge_temporal_version | table | postgres
 public | evidence              | table | postgres
 public | execution_run         | table | postgres
 public | execution_state       | table | postgres
 public | job                   | table | postgres
 public | lineage_edge          | table | postgres
 public | projection_outbox     | table | postgres
 public | raw_event             | table | postgres
```

---

## Option 2: WSL2 Installation (For ProvSQL Compatibility)

WSL2 may be needed if M2's ProvSQL spike requires Linux.

### Install WSL2

```powershell
wsl --install
```

Restart your computer if prompted.

### Install PostgreSQL in WSL2

```bash
# Open WSL2 terminal
wsl

# Update packages
sudo apt update

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL service
sudo service postgresql start

# Verify
sudo -u postgres psql --version
```

### Create Database in WSL2

```bash
# Switch to postgres user
sudo -u postgres psql

# In psql:
CREATE DATABASE kairos;
\q
```

### Apply Migration

```bash
cd /mnt/d/Meta_Data/data-lineage-engine
sudo -u postgres psql kairos < backend/migrations/0001_core.sql
```

---

## Option 3: Docker (Last Resort)

Only use if native and WSL2 fail.

### Create docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: kairos_password
      POSTGRES_DB: kairos
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/migrations:/migrations

volumes:
  postgres_data:
```

### Start PostgreSQL

```powershell
docker-compose up -d
```

### Apply Migration

```powershell
docker exec -i $(docker-compose ps -q postgres) psql -U postgres kairos < backend\migrations\0001_core.sql
```

---

## Connection String

### For Python (psycopg2)

```python
import psycopg2

conn = psycopg2.connect(
    "dbname=kairos user=postgres password=your_password host=localhost"
)
```

### Environment Variable (.env)

```
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/kairos
```

**Important:** Never commit `.env` file!

---

## Testing Connection

### From Command Line

```powershell
psql -U postgres -d kairos -c "SELECT version();"
```

### From Python

```python
# tests/test_database_connection.py
import psycopg2

def test_connection():
    conn = psycopg2.connect(
        "dbname=kairos user=postgres password=your_password host=localhost"
    )
    cur = conn.cursor()
    cur.execute("SELECT 1")
    assert cur.fetchone() == (1,)
    conn.close()
```

---

## Troubleshooting

### "psql: command not found"
- Add PostgreSQL bin to PATH
- Restart terminal

### "connection refused"
- Check if PostgreSQL is running:
  - Windows: Services → PostgreSQL
  - WSL2: `sudo service postgresql status`
  - Docker: `docker-compose ps`

### "authentication failed"
- Check password
- Edit `pg_hba.conf` if needed (native install)

### "database does not exist"
- Create it first: `createdb kairos` or `CREATE DATABASE kairos;`

---

## Next Steps

After PostgreSQL is set up:

1. ✅ Apply migration 0001
2. ✅ Verify tables exist
3. ✅ Run temporal oracle tests: `python -m pytest tests/test_temporal_oracle.py`
4. ✅ Create `.env` file with connection string
5. ✅ Test connection from Python

---

## References

- Official docs: https://www.postgresql.org/docs/
- psycopg2 docs: https://www.psycopg.org/docs/
- Migration files: `backend/migrations/`
