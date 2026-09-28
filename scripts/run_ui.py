"""CLI script to start the Kairos backend server and serve the frontend."""
import argparse
import sys
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uvicorn

def main():
    parser = argparse.ArgumentParser(description="Run Kairos Backend & Frontend server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--open-browser", action="store_true", help="Automatically open browser")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"\nStarting Kairos Lineage Engine at {url}")
    print(f"API Documentation available at: {url}/docs")
    print(f"Investigator Cockpit available at: {url}/")

    if args.open_browser:
        webbrowser.open(url)

    uvicorn.run("backend.app.main:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
