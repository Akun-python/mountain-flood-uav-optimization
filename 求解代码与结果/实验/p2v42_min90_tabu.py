# -*- coding: utf-8 -*-
"""v42-ο：min90 初始解（24 趟满载）的长程 tabu 精化——完工/能耗双口径 × 多种子 × 300s。
输出 结果/进化_v42/min90_best.json（最优合规解路由）。"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate
from common import set_weights, clone_flights, TimeBudget
from solvers import tabu_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
data = Data()
init = json.load(open(os.path.join(EVO, 'min90_init.json'), encoding='utf-8'))
fl0 = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in init['flights']]

CONFIGS = {
    'hard': (100.0, 0.5, 0.5, 100.0),
    'mk': (10.0, 0.5, 0.5, 10.0),
    'bal': (5.0, 0.3, 1.0, 20.0),
    'en': (1.0, 0.02, 2.0, 20.0),
}
rows = []
for name, w in CONFIGS.items():
    set_weights(*w)
    for seed in (3, 7, 11, 13, 17, 19):
        t0 = time.time()
        fl, met = tabu_optimize(data, clone_flights(fl0), TimeBudget(300), seed)
        if fl is None or met is None:
            continue
        m = {'flights': len(fl), 'makespan': met['makespan'], 'energy': met['energy'],
             'hard_ok': met['hard_ok'], 'tardy_w': met['tardy_w'], 'bad': len(met['bad_zones'])}
        rows.append((name, seed, m, time.time() - t0))
        print('%-4s s%-3d fl=%d mk=%7.1f e=%6.3f hard=%s t=%.0fs' % (
            name, seed, m['flights'], m['makespan'], m['energy'], m['hard_ok'], time.time() - t0))

ok = [r for r in rows if r[2]['hard_ok'] and r[2]['tardy_w'] < 1e-6 and r[2]['bad'] == 0]
print('\n合规 %d/%d' % (len(ok), len(rows)))
by_mk = sorted(ok, key=lambda r: (r[2]['makespan'], r[2]['energy']))
by_en = sorted(ok, key=lambda r: (r[2]['energy'], r[2]['makespan']))
for tag, lst in (('完工', by_mk), ('能耗', by_en)):
    r = lst[0]
    print('%s 最优: %s s%-3d fl=%d mk=%.1f e=%.3f' % (tag, r[0], r[1], r[2]['flights'],
                                                       r[2]['makespan'], r[2]['energy']))

# 保存完工最优
best = by_mk[0]
set_weights(*CONFIGS[best[0]])
flb, metb = tabu_optimize(data, clone_flights(fl0), TimeBudget(300), best[1])
sch, _ = dispatch(data, flb)
out = {'solver': 'v42-min90-tabu', 'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                                                for k, v in metb.items() if k != 'box_time'},
       'flights': [], 'deliveries': []}
for f in flb:
    s = sch[f.fid]
    out['flights'].append({'fid': f.fid, 'uav': s['uav'], 'model': f.model,
                           'battery': s['battery'], 'start': round(s['start'], 1),
                           'return': round(s['return'], 1),
                           'route': [(sid, list(bs)) for sid, bs in f.route],
                           'energy': round(f.energy(), 4), 'nbox': f.nbox,
                           'mass': round(f.total_mass, 2)})
    for sid, bid, t in s['deliveries']:
        out['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
json.dump(out, open(os.path.join(EVO, 'min90_best.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved min90_best.json')