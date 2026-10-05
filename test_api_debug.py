import httpx
import json

response = httpx.get('http://localhost:8000/api/v1/assets/orders_fact/lineage')
data = response.json()

# Print raw first node JSON
print("Raw JSON for first node:")
print(json.dumps(data['nodes'][0], indent=2))

print("\nAll keys in first node:")
print(list(data['nodes'][0].keys()))
