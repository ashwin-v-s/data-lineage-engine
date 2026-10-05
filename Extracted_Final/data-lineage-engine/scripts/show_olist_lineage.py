#!/usr/bin/env python3
"""
Display Olist lineage graph that's already in Supabase.
This shows what the UI will display when you search for 'olist' datasets.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db import get_cursor

print("=" * 70)
print("OLIST LINEAGE GRAPH — KAIROS UI")
print("=" * 70)

with get_cursor() as cur:
    # Get all Olist datasets
    print("\n[DATASETS]")
    cur.execute("""
        SELECT id, name, schema_name, asset_type, source_system
        FROM dataset
        WHERE name ILIKE '%olist%'
        ORDER BY name
    """)
    datasets = cur.fetchall()
    dataset_map = {str(r["id"]): r["name"] for r in datasets}
    
    print(f"Found {len(datasets)} Olist datasets:")
    for r in datasets:
        print(f"  - {r['name']:30} ({r['asset_type']:6}) [{r['source_system']}]")
    
    # Get all Olist lineage edges
    print("\n[LINEAGE EDGES]")
    cur.execute("""
        SELECT le.id, le.source_id, le.target_id, le.granularity,
               src.name as src_name, tgt.name as tgt_name
        FROM lineage_edge le
        LEFT JOIN dataset src ON src.id = le.source_id
        LEFT JOIN dataset tgt ON tgt.id = le.target_id
        WHERE (src.name ILIKE '%olist%' OR tgt.name ILIKE '%olist%')
        ORDER BY src.name, tgt.name
    """)
    edges = cur.fetchall()
    print(f"Found {len(edges)} Olist lineage relationships:")
    
    # Group by source
    edge_groups = {}
    for edge in edges:
        src = edge["src_name"] or str(edge["source_id"])
        if src not in edge_groups:
            edge_groups[src] = []
        edge_groups[src].append({
            "target": edge["tgt_name"] or str(edge["target_id"]),
            "granularity": edge["granularity"],
        })
    
    for src in sorted(edge_groups.keys()):
        for target_info in edge_groups[src]:
            gran = f"[{target_info['granularity']}]" if target_info['granularity'] != 'DATASET' else ""
            print(f"  {src:30} → {target_info['target']:30} {gran}")
    
    # Compute graph structure for display
    print("\n[GRAPH STRUCTURE]")
    nodes = set(dataset_map.values())
    print(f"Nodes: {len(nodes)}")
    print(f"Edges: {len(edges)}")
    
    # Find root nodes (sources with no incoming edges)
    all_targets = {edge["tgt_name"] or str(edge["target_id"]) for edge in edges}
    all_sources = {edge["src_name"] or str(edge["source_id"]) for edge in edges}
    roots = all_sources - all_targets
    
    print(f"\nRoot datasets (no incoming edges):")
    for root in sorted(roots):
        print(f"  • {root}")
    
    # Find leaf nodes (targets with no outgoing edges)
    leaves = all_targets - all_sources
    print(f"\nLeaf datasets (no outgoing edges):")
    for leaf in sorted(leaves):
        print(f"  ◆ {leaf}")

print("\n" + "=" * 70)
print("HOW TO VIEW IN UI:")
print("=" * 70)
print("""
1. Open http://localhost:3000
2. Click search box at top
3. Type "olist_orders" or any dataset name above
4. Click on dataset name to view its lineage
5. Click "Column Lineage" toggle to see column-level deps (if available)
6. Use BitemporalBar date pickers for historical time-travel
""")
print("=" * 70)
