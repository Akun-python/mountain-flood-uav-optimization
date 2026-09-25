# -*- coding: utf-8 -*-
"""v25 修正版冠军导出：balanced 权重 + seed 7（固定种子复现完整搜索中的冠军），
导出零跨区+零迟到的 p2_results.json（28 架 / 8153.2 s / 80.31 kWh）。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Data, TimeBudget, make_initial, clone_flights, set_weights, safe_eval
from solvers import tabu_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_P2 = os.path.join(HERE, '..', 'results', 'p2_results.json')
p1 = json.load(open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8'))
data = Data()
fl0 = make_initial(data, p1['grouping'])
# 冠军配置：balanced (5.0, 0.3, 1.0, 20.0) seed 7；预算 600/(4*3*2)=25s
set_weights(5.0, 0.3, 1.0, 20.0)
budget = TimeBudget(25.0)
fl, met = tabu_optimize(data, clone_flights(fl0), budget, 7)
assert fl is not None and met is not None
assert met['hard_ok'] and met['tardy_w'] < 1e-6 and not met.get('bad_zones'), (met['hard_ok'], met['tardy_w'], met.get('bad_zones'))
print('冠军复核: fl=%d mk=%.2f e=%.3f tardy=%.2f bad_zones=%d'
      % (met['flights'], met['makespan'], met['energy'], met['tardy_w'], len(met.get('bad_zones', []))))

from p2_solve import dispatch
schedule, _ = dispatch(data, fl)
result = {'solver': 'v25 zone-fix tabu', 'config': 'balanced s7 (零跨区修正)',
          'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                      for k, v in met.items() if k != 'box_time'},
          'flights': [], 'deliveries': []}
for f in fl:
    sch = schedule[f.fid]
    result['flights'].append({
        'fid': f.fid, 'uav': sch['uav'], 'model': f.model, 'battery': sch['battery'],
        'start': round(sch['start'], 1), 'return': round(sch['return'], 1),
        'route': [(s, list(bs)) for s, bs in f.route],
        'energy': round(f.energy(), 4), 'nbox': f.nbox, 'mass': round(f.total_mass, 2)})
    for sid, bid, t in sch['deliveries']:
        result['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
json.dump(result, open(OUT_P2, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('p2_results.json 已导出（28 架零跨区）')
# 逐架确认零跨区
n = 0
for f in fl:
    for s, bs in f.route:
        for b in bs:
            if b.split('-')[0] != s:
                n += 1
print('route 级零跨区复核: %d 处跨区' % n)