import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
print(f"Connecting to Supabase...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()
    print(f"✅ Connected! PostgreSQL version: {version[0][:50]}")
    cur.execute("SELECT current_database();")
    db = cur.fetchone()
    print(f"✅ Database: {db[0]}")
    cur.close()
    conn.close()
    print("✅ Connection test PASSED!")
except Exception as e:
    print(f"❌ Connection failed: {e}")
