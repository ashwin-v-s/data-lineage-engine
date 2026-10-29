import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='dataset' ORDER BY ordinal_position")
print("Dataset table columns:")
for row in cur.fetchall():
    print(f"  {row[0]:<25} {row[1]}")
cur.close()
conn.close()
