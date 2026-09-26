# -*- coding: utf-8 -*-
"""v42-η：28 架完工方向能耗收敛——从 mk29_best(7058.3/76.58) 续搜。
完工通道已探明（7058.3 为纪录），此处补足"完工≤7075 下能耗更低"的搜索火力：
5 权重 × 4 种子 × 150 s，收集严格合规且 mk≤7075 的解，best 保存路由。
输出 结果/进化_v42/mk28_micro.json / mk28_best.json。"""
import sys, os, json, time, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from common import Data, TimeBudget, set_weights, summarize
from solvers import tabu_optimize
from p2_solve import Flight
from core import Data as CoreData

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')

data = CoreData()
obj = json.load(open(os.path.join(EVO, 'mk29_best.json'), encoding='utf-8'))
fl0 = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in obj['flights']]

WEIGHTS = {
    'mk_en_a': (4.0, 0.2, 1.5, 12.0),
    'mk_en_b': (2.0, 0.15, 2.5, 15.0),
    'mk_en_c': (6.0, 0.3, 1.2, 10.0),
    'en_soft': (1.0, 0.1, 3.0, 10.0),
    'en_onmk': (2.5, 0.2, 2.0, 8.0),
}
rows = []
best = None
best_key = None
for name, w in WEIGHTS.items():
    set_weights(*w)
    for seed in (7, 11, 13, 17):
        t0 = time.time()
        fl, met = tabu_optimize(data, [copy.deepcopy(f) for f in fl0], TimeBudget(150.0), seed)
        dt = time.time() - t0
        if fl is None or met is None:
            rows.append({'cfg': name, 'seed': seed, 'status': 'fail'})
            continue
        m = summarize(met)
        rows.append({'cfg': name, 'seed': seed, 'm': m, 'time_s': round(dt, 1), 'fl': fl})
        ok = m['hard_ok'] and m['tardy_w'] < 1e-6 and not m['bad_zones']
        print('%s s%-3d fl=%d mk=%.1f e=%.3f hard=%s tardy=%.2f bad=%d (%.0fs)'
              % (name, seed, m['flights'], m['makespan'], m['energy'],
                 m['hard_ok'], m['tardy_w'], len(m['bad_zones']), dt))
        if ok and m['makespan'] <= 7075.0 and m['energy'] < 76.58:
            k = (m['makespan'], m['energy'])
            if best is None or k < best_key:
                best = (fl, m)
                best_key = k

print('\n== 完工≤7075 且能耗<76.58 的解（完工方向收敛）==')
cand = [r for r in rows if r.get('m') and r['m']['hard_ok'] and r['m']['tardy_w'] < 1e-6
        and r['m']['makespan'] <= 7075.0 and r['m']['energy'] < 76.58]
cand.sort(key=lambda r: (r['m']['makespan'], r['m']['energy']))
for r in cand[:8]:
    print('  %s s%-3d fl=%d mk=%.1f e=%.3f' % (r['cfg'], r['seed'], r['m']['flights'],
                                               r['m']['makespan'], r['m']['energy']))
print('候选 %d/%d' % (len(cand), len(rows)))

out = {'baseline': {'flights': 28, 'makespan': 7058.3, 'energy': 76.58}, 'rows': []}
for r in rows:
    rec = {'cfg': r['cfg'], 'seed': r['seed'], 'time_s': r.get('time_s'), 'status': r.get('status', 'ok')}
    if r.get('m'):
        m = r['m']
        rec['m'] = {'flights': m['flights'], 'makespan': round(m['makespan'], 1),
                    'energy': round(m['energy'], 3), 'hard_ok': m['hard_ok'],
                    'tardy_w': round(m['tardy_w'], 3), 'bad_zones': m['bad_zones']}
    out['rows'].append(rec)
json.dump(out, open(os.path.join(EVO, 'mk28_micro.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
if best is not None:
    fl, m = best
    json.dump({'flights': [{'fid': f.fid, 'model': f.model,
                            'route': [[s, bs] for s, bs in f.route]} for f in fl],
               'met': {'flights': m['flights'], 'makespan': round(m['makespan'], 1),
                       'energy': round(m['energy'], 3), 'tardy_w': m['tardy_w'],
                       'bad_zones': m['bad_zones']},
               'source': 'mk28_micro'},
              open(os.path.join(EVO, 'mk28_best.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved mk28_best.json fl=%d mk=%.1f e=%.2f'
          % (m['flights'], m['makespan'], m['energy']))
print('saved mk28_micro.json')