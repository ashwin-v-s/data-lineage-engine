from backend.app.main import app

routes = []
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        routes.append({'path': route.path, 'methods': list(route.methods)})

# Print lineage routes
print("Lineage routes:")
lineage_routes = [r for r in routes if 'lineage' in r['path']]
for r in lineage_routes:
    print(f"  {r['methods']} {r['path']}")

# Print assets routes
print("\nAssets routes:")
assets_routes = [r for r in routes if 'assets' in r['path']]
for r in assets_routes:
    print(f"  {r['methods']} {r['path']}")

print(f"\nTotal routes: {len(routes)}")
