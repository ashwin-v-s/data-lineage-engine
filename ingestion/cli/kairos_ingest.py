import os
import sys
import json
import csv
import argparse
from datetime import datetime

try:
    import yaml
    import requests
except ImportError:
    print("[ERROR] Missing required packages. Run: pip install pyyaml requests psycopg2-binary")
    sys.exit(1)

class KairosCSVExtractor:
    def __init__(self, config):
        self.directory = config.get("directory", ".")

    def extract(self):
        print(f"[INFO] Scanning directory '{self.directory}' for CSV files...")
        assets = []
        if not os.path.exists(self.directory):
            print(f"[WARN] Directory {self.directory} does not exist.")
            return assets

        for filename in os.listdir(self.directory):
            if filename.endswith(".csv"):
                filepath = os.path.join(self.directory, filename)
                print(f"[INFO] Extracting schema for file '{filename}'...")
                
                columns = []
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        headers = next(reader)
                        for col in headers:
                            columns.append({"name": col.strip(), "type": "string"})
                except Exception as e:
                    print(f"[WARN] Could not read {filename}: {e}")
                
                table_name = filename.replace('.csv', '')
                asset_id = f"csv.local.{table_name}"
                
                assets.append({
                    "id": asset_id,
                    "name": table_name,
                    "namespace": "local_filesystem",
                    "kind": "source",
                    "type": "dataset",
                    "column_count": len(columns),
                    "columns": columns,
                    "description": f"Local CSV file: {filename}"
                })
        return assets

class KairosPostgresExtractor:
    def __init__(self, config):
        self.config = config

    def extract(self):
        try:
            import psycopg2
        except ImportError:
            print("[ERROR] psycopg2 is not installed. Run: pip install psycopg2-binary")
            sys.exit(1)
            
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 5432)
        dbname = self.config.get("database", "postgres")
        user = self.config.get("username", "postgres")
        password = self.config.get("password", "")
        
        print(f"[INFO] Connecting to local Postgres at {host}:{port} / {dbname}...")
        
        try:
            conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT table_name, column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position;
            """)
            rows = cur.fetchall()
            
            tables = {}
            for table_name, column_name, data_type in rows:
                if table_name not in tables:
                    tables[table_name] = []
                tables[table_name].append({"name": column_name, "type": data_type})
                
            assets = []
            for table_name, columns in tables.items():
                print(f"[INFO] Extracting schema for table '{table_name}'... Found {len(columns)} columns.")
                assets.append({
                    "id": f"postgres.{dbname}.public.{table_name}",
                    "name": table_name,
                    "namespace": f"{dbname}.public",
                    "kind": "source",
                    "type": "table",
                    "column_count": len(columns),
                    "columns": columns,
                    "description": f"PostgreSQL table extracted from {dbname}"
                })
            return assets
            
        except Exception as e:
            print(f"[ERROR] Failed to extract from Postgres: {e}")
            return []

def push_to_kairos(assets, dest_config):
    endpoint = dest_config.get("endpoint")
    token = dest_config.get("token", "default_token")
    
    if not endpoint:
        print("[ERROR] Missing destination endpoint in config.")
        sys.exit(1)
        
    print(f"[INFO] Pushing {len(assets)} assets to Kairos API ({endpoint})...")
    
    payload = {
        "kind": "metadata_graph",
        "payload": {
            "source_system": "kairos_python_sdk",
            "assets": assets,
            "relationships": [] # Later, we'll populate this with lineage edges!
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        if response.status_code == 200:
            print("[INFO] Success: 200 OK. Metadata securely ingested into Kairos.")
            data = response.json()
            print(f"[INFO] Details: {data.get('assets_upserted', 0)} assets processed.")
        else:
            print(f"[ERROR] API rejected payload: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] Failed to connect to Kairos API: {e}")

def main():
    parser = argparse.ArgumentParser(description="Kairos Metadata Ingestion SDK")
    parser.add_argument("--run", metavar="CONFIG_FILE", required=True, help="Path to the kairos.yaml recipe file")
    args = parser.parse_args()
        
    config_path = args.run
    print(f"=========================================")
    print(f"[INFO] Starting Kairos Ingestion Client")
    print(f"[INFO] Loading Recipe: {config_path}")
    print(f"=========================================\n")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"[ERROR] Could not read {config_path}: {e}")
        sys.exit(1)
        
    source = config.get("source", {})
    source_type = source.get("type")
    source_config = source.get("config", {})
    dest_config = config.get("destination", {}).get("config", {})
    
    if source_type == "csv":
        extractor = KairosCSVExtractor(source_config)
    elif source_type == "postgres":
        extractor = KairosPostgresExtractor(source_config)
    else:
        print(f"[ERROR] Unsupported source type: {source_type}. Try 'csv' or 'postgres'.")
        sys.exit(1)
        
    assets = extractor.extract()
    
    print("")
    if assets:
        push_to_kairos(assets, dest_config)
    else:
        print("[INFO] No assets found. Nothing to push.")
        
    print(f"=========================================")
    print(f"[INFO] Ingestion Run Complete.")

if __name__ == "__main__":
    main()