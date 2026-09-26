# -*- coding: utf-8 -*-
"""v42-δ：25 架方案（s23_search.final）落地为权威 results/p2_results.json。
含 flights(全字段)/metrics/deliveries，供 P3/P4/图件/导出模板使用。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
EVO = os.path.join(HERE, '..', '结果', '进化_v42')

data = Data()
obj = json.load(open(os.path.join(EVO, 's23_search.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in obj['final']['routes']]
sch, _ = dispatch(data, fls)
met = evaluate(data, fls, sch)
assert met['hard_ok'] and met['tardy_w'] < 1e-6 and not met['bad_zones'], '25架口径校验失败'

fids = {f.fid for f in fls}
# 重编号：按 (model 权重, start) 排序后赋 1..N（合并索引消失，使命名与表/导出一致）
ORDER_W = {'C': 0, 'B': 1, 'A': 2}
sch_f = [(f, sch[f.fid]) for f in fls]
sch_f.sort(key=lambda t: (ORDER_W[t[0].model], t[1]['start'], t[0].fid))
renum = {f.fid: k + 1 for k, (f, _) in enumerate(sch_f)}
flights = []
for f, s in sch_f:
    nid = renum[f.fid]
    flights.append({'fid': nid, 'uav': s['uav'], 'model': f.model,
                    'battery': s['battery'], 'start': round(s['start'], 1),
                    'return': round(s['return'], 1),
                    'route': [[ss, bs] for ss, bs in f.route],
                    'energy': round(f.energy(), 3), 'nbox': f.nbox,
                    'mass': round(f.total_mass, 3)})

deliveries = []
for f, s in sch_f:
    nid = renum[f.fid]
    for sname, bid, t in f.delivery_times(s['start']):
        deliveries.append({'box': bid, 'fid': nid, 'area': sname, 't': round(t, 1)})

out = {'solver': 'v42-25merge', 'config': {'source': 's23_search.json',
                                           'fid_map': {str(o): n for o, n in renum.items()}},
       'metrics': {'makespan': met['makespan'], 'energy': met['energy'],
                   'flights': met['flights'], 'tardy_w': 0.0, 'hard_ok': True},
       'flights': sorted(flights, key=lambda x: x['fid']), 'deliveries': deliveries}
json.dump(out, open(os.path.join(RES, 'p2_results.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved results/p2_results.json: fl=%d mk=%.1f e=%.2f deliveries=%d'
      % (len(flights), met['makespan'], met['energy'], len(deliveries)))
print('机型:', {m: sum(1 for f in flights if f['model'] == m) for m in 'ABC'})