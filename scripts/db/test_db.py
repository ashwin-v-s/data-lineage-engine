import os
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
import sys

load_dotenv()
db_url = os.getenv('DATABASE_URL')
print(f"Testing connection to: {db_url[:50]}...")

try:
    conn = psycopg2.connect(db_url, connect_timeout=5)
    print("✓ Connected successfully!")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dataset")
    count = cur.fetchone()[0]
    print(f"✓ Dataset table has {count} rows")
    cur.close()
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f"✗ Connection failed: {e}")
    sys.exit(1)
