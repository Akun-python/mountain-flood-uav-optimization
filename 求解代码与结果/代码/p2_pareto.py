# -*- coding: utf-8 -*-
"""P2 权重扫描：产生多组权衡解，存 p2_pareto.json。"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import core
import p2_solve
from p2_solve import (initial_flights, dispatch, evaluate, objective, sa_optimize,
                      clone_flights, Flight, MODELS)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = core.Data()
with open(os.path.join(OUT, 'p1_results.json'), encoding='utf-8') as fh:
    p1 = json.load(fh)
fl0 = initial_flights(data, p1['grouping'])

weights = {
    'balanced':  (1.0, 0.05, 0.8, 30.0),
    'min_flights': (1.0, 0.02, 0.3, 80.0),
    'min_makespan': (1.0, 0.6, 0.6, 15.0),
    'min_energy': (1.0, 0.03, 4.0, 10.0),
}
res = {}
for name, (w1, w2, w3, w4) in weights.items():
    p2_solve.W_TARDY, p2_solve.W_MAKESPAN = w1, w2
    p2_solve.W_ENERGY, p2_solve.W_FLIGHTS = w3, w4
    best = None
    for seed in [3, 7, 11, 21]:
        fl, met = sa_optimize(data, fl0, iters=5000, seed=seed)
        if fl is None:
            continue
        key = (met['flights'], round(met['makespan']), round(met['energy'], 2), round(met['tardy_w'], 1))
        if best is None or key[0] < best[0][0] or (key[0] == best[0][0] and met['hard_ok'] and not best[1]['hard_ok']):
            best = (key, met, fl, seed)
    if best is None:
        continue
    (k, met, fl, seed) = best
    res[name] = {
        'params': {'w_tardy': w1, 'w_makespan': w2, 'w_energy': w3, 'w_flights': w4, 'seed': seed},
        'metrics': {kk: (round(v, 3) if isinstance(v, float) else v)
                    for kk, v in met.items() if kk != 'box_time'},
    }
    print('%-12s flights=%d makespan=%.0f energy=%.2f tardy=%.1f hard=%s'
          % (name, met['flights'], met['makespan'], met['energy'], met['tardy_w'], met['hard_ok']))
    # 保存该配置的最优架次安排
    schedule, _ = dispatch(data, fl)
    flights_json = []
    deliveries = []
    for f in fl:
        s = schedule[f.fid]
        flights_json.append({'fid': f.fid, 'uav': s['uav'], 'model': f.model,
                             'battery': s['battery'], 'start': round(s['start'], 1),
                             'return': round(s['return'], 1),
                             'route': [(a, b) for a, b in f.route],
                             'energy': round(f.energy(), 4), 'nbox': f.nbox,
                             'mass': round(f.total_mass, 2)})
        for sid, bid, t in s['deliveries']:
            deliveries.append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
    res[name]['flights'] = flights_json
    res[name]['deliveries'] = deliveries

with open(os.path.join(OUT, 'p2_pareto.json'), 'w', encoding='utf-8') as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1)
print('saved p2_pareto.json')