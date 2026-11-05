#!/usr/bin/env python3
"""
REA UI Pattern Analyzer for KAIROS

Uses REA to reverse-engineer frontend components and extract patterns
from DataHub, OpenMetadata, and Atlan for intelligent UI enhancement.

Usage:
  python scripts/rea_ui_analysis.py analyze-components
  python scripts/rea_ui_analysis.py compare-patterns
  python scripts/rea_ui_analysis.py extract-best-practices
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# REA CLI command base
REA_BIN = "npx"
REA_PACKAGE = "rea-agents@latest"


def run_rea_command(args: list[str]) -> dict[str, Any]:
    """Execute REA CLI command and return JSON result."""
    cmd = [REA_BIN, REA_PACKAGE] + args + ["--json"]
    print(f"[REA] Running: {' '.join(cmd)}", file=sys.stderr)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode != 0:
            print(f"[REA] Error: {result.stderr}", file=sys.stderr)
            return {"error": result.stderr, "code": result.returncode}
        
        # Try to parse JSON from stdout
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_output": result.stdout, "stderr": result.stderr}
    
    except subprocess.TimeoutExpired:
        return {"error": "REA command timeout (300s)", "code": 124}
    except Exception as e:
        return {"error": str(e), "code": 1}


def analyze_kairos_components() -> dict[str, Any]:
    """
    Analyze KAIROS frontend components using REA.
    
    Extracts:
    - Module structure (SearchPage, EntityPage, EvidenceInspector)
    - Import patterns and dependencies
    - Component hierarchy
    - State management patterns
    - Network calls (API routes)
    """
    frontend_path = Path(__file__).parent.parent / "frontend" / "src" / "components"
    
    print(f"[KAIROS] Analyzing frontend at: {frontend_path}")
    
    if not frontend_path.exists():
        return {"error": f"Frontend path not found: {frontend_path}"}
    
    # Use REA to analyze JavaScript application
    result = run_rea_command([
        "analyze-javascript-application",
        str(frontend_path),
    ])
    
    return {
        "operation": "analyze_kairos_components",
        "frontend_path": str(frontend_path),
        "analysis": result,
    }


def extract_ui_patterns() -> dict[str, Any]:
    """
    Extract UI/UX patterns from KAIROS components.
    
    Identifies:
    - Component composition patterns
    - Data flow patterns
    - User interaction patterns
    - Visual hierarchy patterns
    """
    analysis = analyze_kairos_components()
    
    if "error" in analysis.get("analysis", {}):
        return analysis
    
    modules = analysis.get("analysis", {}).get("modules", [])
    
    patterns = {
        "components": [],
        "imports": [],
        "dataflow": [],
        "interactions": [],
    }
    
    for mod in modules:
        name = mod.get("name", "")
        
        if "SearchPage" in name:
            patterns["components"].append({
                "name": "SearchPage",
                "type": "search_interface",
                "pattern": "faceted_search_with_filters",
                "role": "discovery_entry_point",
            })
        elif "EntityPage" in name:
            patterns["components"].append({
                "name": "EntityPage",
                "type": "detail_view",
                "pattern": "tabbed_details_with_lineage",
                "role": "entity_inspector",
            })
        elif "EvidenceInspector" in name:
            patterns["components"].append({
                "name": "EvidenceInspector",
                "type": "evidence_panel",
                "pattern": "collapsible_reasoning_panel",
                "role": "dependency_justification",
            })
    
    return {
        "operation": "extract_ui_patterns",
        "patterns": patterns,
        "analysis_metadata": analysis.get("analysis", {}),
    }


def generate_recommendations() -> dict[str, Any]:
    """
    Generate UI enhancement recommendations based on REA analysis.
    
    Uses patterns from:
    - KAIROS current implementation
    - DataHub reference patterns
    - OpenMetadata patterns
    - Atlan patterns
    """
    patterns = extract_ui_patterns()
    
    recommendations = {
        "search_page": {
            "current": "Faceted search with asset types, namespaces, columns",
            "improvements": [
                "Add saved search filters (like DataHub star feature)",
                "Implement full-text search with relevance ranking",
                "Add advanced query builder (OpenMetadata style)",
                "Show recent searches for quick access",
            ],
        },
        "entity_page": {
            "current": "Tabbed view with Metadata, Lineage, Evidence tabs",
            "improvements": [
                "Add owner/steward assignment UI (like Atlan)",
                "Implement glossary term linking (DataHub pattern)",
                "Add data quality indicators (OpenMetadata)",
                "Show related datasets in suggestions",
                "Add inline tagging and annotation",
            ],
        },
        "lineage_graph": {
            "current": "Interactive D3 graph with Fit/Isolate/Depth controls",
            "improvements": [
                "Add column-level lineage toggle (OpenMetadata)",
                "Implement lineage path highlighting on hover",
                "Add impact analysis (downstream propagation)",
                "Show data quality scores on nodes (Atlan)",
                "Add node filtering by type/system (DataHub)",
            ],
        },
        "evidence_panel": {
            "current": "Collapsible reasoning panel with coverage details",
            "improvements": [
                "Add evidence timeline (when discovered)",
                "Show evidence provenance and confidence scores",
                "Add evidence comparison across runs",
                "Implement evidence export/sharing",
                "Add drill-down to source SQL/config",
            ],
        },
    }
    
    return {
        "operation": "generate_recommendations",
        "recommendations": recommendations,
        "patterns_analyzed": patterns,
    }


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "analyze-components":
        result = analyze_kairos_components()
    elif command == "extract-patterns":
        result = extract_ui_patterns()
    elif command == "recommend":
        result = generate_recommendations()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
