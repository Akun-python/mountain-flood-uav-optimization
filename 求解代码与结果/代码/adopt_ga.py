# -*- coding: utf-8 -*-
"""集成：把 v2 遗传算法方案（种子7，已独立实证）采纳为问题二主结果。

- p2_results.json        ← GA 24架次方案（驱动 p3_construct 系列）
- p2_pareto.json['balanced'] ← GA 方案（驱动 Q2 Excel 与问题二图件）
SA 四权重方案保留在 p2_pareto.json['sa_*'] 作为对照。
"""
import sys, os, json, io
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'code'))
sys.stdout.reconfigure(encoding='utf-8')

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
GA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'versions', 'v2', 'results.json')

r_ga = json.load(io.open(GA, encoding='utf-8'))
flights = r_ga['flights']
deliveries = r_ga['deliveries']
metrics = {k: (float(v) if hasattr(v, 'item') else v) for k, v in r_ga['metrics'].items()}
metrics['makespan'] = round(metrics['makespan'], 2)
metrics['energy'] = round(metrics['energy'], 2)

# 1) p2_results.json
out = {'metrics': metrics, 'box_time': {},
       'flights': flights, 'deliveries': deliveries}
box_time = {}
for d in deliveries:
    box_time[d['box']] = d['t']
out['box_time'] = box_time
with io.open(os.path.join(RES, 'p2_results.json'), 'w', encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print('p2_results.json ← GA (%d flights, makespan %.1f, energy %.2f, tardy %.1f)'
      % (len(flights), metrics['makespan'], metrics['energy'], metrics['tardy_w']))

# 2) p2_pareto.json
pareto = json.load(io.open(os.path.join(RES, 'p2_pareto.json'), encoding='utf-8'))
sa_balanced = dict(pareto['balanced'])
for k in list(pareto.keys()):
    if k.startswith('sa_'):
        del pareto[k]
pareto['sa_balanced'] = sa_balanced
pareto['sa_min_flights'] = pareto.pop('min_flights')
pareto['sa_min_makespan'] = pareto.pop('min_makespan')
pareto['sa_min_energy'] = pareto.pop('min_energy')
pareto['balanced'] = {'metrics': metrics, 'flights': flights, 'deliveries': deliveries,
                      'method': 'v2-ga-seed7', 'note': 'GA 24架/8342.1s/77.31kWh/零迟到'}
with io.open(os.path.join(RES, 'p2_pareto.json'), 'w', encoding='utf-8') as fh:
    json.dump(pareto, fh, ensure_ascii=False, indent=1)
print('p2_pareto.json ← balanced=GA; SA 对照存为 sa_* 键')
print('adopted GA plan OK')