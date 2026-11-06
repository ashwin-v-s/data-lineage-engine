import json
from pathlib import Path

s = json.loads(Path('research/results/summary.json').read_text())

print('=== Proposed vs Baselines at MCAR level=0 ===')
for method in ['proposed','B1','B2','B3','B4','B5']:
    key = f'mcar|0|{method}'
    c = s['per_cell'].get(key, {})
    fr  = c.get('false_refutation_avg')
    fo  = c.get('false_observation_avg')
    ca  = c.get('committed_accuracy_avg')
    rec = c.get('recall_strict_avg')
    ur  = c.get('unknown_rate_avg')
    print(f'{method:10s} fr={fr} fo={fo} ca={ca} rec={rec} ur={ur}')

print()
print('=== MCAR recall erosion (proposed) ===')
for lvl in [0,10,30,50,70,90]:
    key = f'mcar|{lvl}|proposed'
    c = s['per_cell'].get(key, {})
    print(f'level={lvl:2d}%  rec={c.get("recall_strict_avg")}  fr={c.get("false_refutation_avg")}  ca={c.get("committed_accuracy_avg")}')

print()
print('=== K1-K8 verdicts ===')
for k, v in s['k1_k8_verdicts'].items():
    print(f'{k}: {v}')
