import httpx
import json

try:
    response = httpx.get('http://localhost:8000/api/v1/assets/orders_fact/lineage')
    if response.status_code == 200:
        data = response.json()
        print('First 3 nodes:')
        for node in data['nodes'][:3]:
            print(f'  ID: {node.get("id")}')
            print(f'  Name: {node.get("name")}')
            print(f'  Display Name: {node.get("display_name")}')
            print(f'  Namespace: {node.get("namespace")}')
            print()
        print(f'Total nodes: {len(data["nodes"])}')
        print(f'Total edges: {len(data["edges"])}')
    else:
        print(f'Error: {response.status_code}')
        print(response.text)
except Exception as e:
    print(f'Connection error: {e}')
    print('Backend might not be running on localhost:8000')
