"""Run database migration on Supabase."""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATION_FILE = "backend/migrations/0001_core.sql"

print("Running migration on Supabase...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    with open(MIGRATION_FILE, "r") as f:
        sql = f.read()

    cur.execute(sql)
    print("✅ Migration executed successfully!")

    # Verify tables
    cur.execute("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY tablename;
    """)
    tables = cur.fetchall()
    print(f"\n✅ Tables created ({len(tables)} total):")
    for t in tables:
        print(f"   - {t[0]}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Migration failed: {e}")
