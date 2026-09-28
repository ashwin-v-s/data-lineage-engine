"""Export OpenAPI 3.1 JSON schema from the Kairos FastAPI application."""
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.main import app

OUT_PATH = ROOT_DIR / "docs" / "openapi.json"

def export():
    schema = app.openapi()
    OUT_PATH.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"OpenAPI schema successfully written to {OUT_PATH}")

if __name__ == "__main__":
    export()
