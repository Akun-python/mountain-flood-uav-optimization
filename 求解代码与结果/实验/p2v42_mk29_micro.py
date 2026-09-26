# -*- coding: utf-8 -*-
"""v42-α：29 架冠军小幅参数搜索（tabu 续搜多权重多种子）。
从 p2v41_mk_tol6_0.json 出发，以不同权重+种子续搜，寻找严格合规且
(makespan,energy) 更优的 29 架解。输出 结果/进化_v42/mk29_micro.json。"""
import sys, os, json, time, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from common import Data, TimeBudget, set_weights, total_obj, summarize
from solvers import tabu_optimize
from p2_solve import Flight, dispatch, evaluate
from core import Data as CoreData

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
SRC = os.path.join(HERE, '..', '结果', '进化_v25', 'p2v41_mk_tol6_0.json')

data = CoreData()
sol = json.load(open(SRC, encoding='utf-8'))['solution']
fl0 = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in sol]
# 基线度量
sch0, _ = dispatch(data, fl0)
met0 = evaluate(data, fl0, sch0)
print('基线: mk=%.1f e=%.2f fl=%d hard=%s tardy=%.2f'
      % (met0['makespan'], met0['energy'], met0['flights'], met0['hard_ok'],
         met0['tardy_w']))

WEIGHTS = {
    'mk_strong':  (10.0, 0.5, 0.5, 10.0),
    'balanced':   (5.0, 0.3, 1.0, 20.0),
    'mk_plus_en': (8.0, 0.35, 0.8, 15.0),
    'mk_tight':   (12.0, 0.45, 0.6, 8.0),
}
rows = []
for name, w in WEIGHTS.items():
    set_weights(*w)
    for seed in (7, 11, 13):
        t0 = time.time()
        fl, met = tabu_optimize(data, [copy.deepcopy(f) for f in fl0], TimeBudget(150.0), seed)
        dt = time.time() - t0
        if fl is None or met is None:
            rows.append({'cfg': name, 'seed': seed, 'status': 'fail'})
            continue
        m = summarize(met)
        rows.append({'cfg': name, 'seed': seed, 'm': m, 'time_s': round(dt, 1), 'fl': fl})
        print('%s s%-3d fl=%d mk=%.1f e=%.3f hard=%s tardy=%.2f  (%.0f s)'
              % (name, seed, m['flights'], m['makespan'], m['energy'],
                 m['hard_ok'], m['tardy_w'], dt))

ok = [r for r in rows if r.get('m') and r['m']['hard_ok'] and r['m']['tardy_w'] < 1e-6]
ok.sort(key=lambda r: (r['m']['makespan'], r['m']['energy']))
print('\n== 零迟到最好 3 个 ==')
for r in ok[:3]:
    print('  %s s%-3d mk=%.1f e=%.3f fl=%d' % (r['cfg'], r['seed'], r['m']['makespan'],
                                               r['m']['energy'], r['m']['flights']))
improved = [r for r in ok
            if (r['m']['makespan'] < met0['makespan'] - 0.5)
            or (r['m']['energy'] < met0['energy'] - 0.05)]
print('较基线改进候选: %d/%d' % (len(improved), len(ok)))

# 保存（fl 不可序列化，存摘要）
out = {'baseline': {'flights': met0['flights'], 'makespan': round(met0['makespan'], 1),
                    'energy': round(met0['energy'], 2)},
       'rows': []}
best_route = None
for r in rows:
    rec = {'cfg': r['cfg'], 'seed': r['seed'], 'time_s': r.get('time_s'), 'status': r.get('status', 'ok')}
    if r.get('m'):
        m = r['m']
        rec['m'] = {'flights': m['flights'], 'makespan': round(m['makespan'], 1),
                    'energy': round(m['energy'], 3), 'hard_ok': m['hard_ok'],
                    'tardy_w': round(m['tardy_w'], 3)}
        # 保存完工优先口径最优解的路由（可复现 + 复核算）
        key = (m['makespan'], m['energy'])
        if best_route is None or key < best_route[0]:
            best_route = (key, r.get('fl'), m)
    out['rows'].append(rec)

if best_route:
    _, best_route = None, best_route
    key, fl, m = best_route
    json.dump({'flights': [{'fid': f.fid, 'model': f.model,
                            'route': [[s, bs] for s, bs in f.route]}
                           for f in fl], 'met': {
                   'flights': m['flights'], 'makespan': round(m['makespan'], 1),
                   'energy': round(m['energy'], 3), 'hard_ok': m['hard_ok'],
                   'tardy_w': round(m['tardy_w'], 3)},
               'source': 'mk29_micro'},
              open(os.path.join(EVO, 'mk29_best.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved mk29_best.json (fl=%d mk=%.1f e=%.3f)'
          % (m['flights'], m['makespan'], m['energy']))
json.dump(out, open(os.path.join(EVO, 'mk29_micro.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved mk29_micro.json')