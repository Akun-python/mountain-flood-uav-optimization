# -*- coding: utf-8 -*-
"""v42-ε：25 架冠军小幅参数搜索——tabu 续搜多权重多种子。
从 results/p2_results.json（网络口径 25 架 7112.8/70.28）出发，以多种权重+种子续搜，
收集全部严格合规且 (makespan,energy) 任一优于基线的 Pareto 点，导出 best 路由。
输出 结果/进化_v42/mk25_micro.json / mk25_best.json。"""
import sys, os, json, time, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from common import Data, TimeBudget, set_weights, summarize
from solvers import tabu_optimize
from p2_solve import Flight, dispatch, evaluate
from core import Data as CoreData

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
EVO = os.path.join(HERE, '..', '结果', '进化_v42')

data = CoreData()
sol = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
fl0 = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in sol['flights']]
sch0, _ = dispatch(data, fl0)
met0 = evaluate(data, fl0, sch0)
print('基线: mk=%.1f e=%.2f fl=%d' % (met0['makespan'], met0['energy'], met0['flights']))

WEIGHTS = {
    'mk_strong':  (10.0, 0.5, 0.5, 10.0),
    'balanced':   (5.0, 0.3, 1.0, 20.0),
    'mk_plus_en': (8.0, 0.35, 0.8, 15.0),
    'en_strong':  (1.5, 0.15, 2.5, 20.0),
}
rows = []
best = None  # (mk, energy) 字典序最小、且不劣于基线的不超过基线拷贝
best_key = None
for name, w in WEIGHTS.items():
    set_weights(*w)
    for seed in (7, 11, 13):
        t0 = time.time()
        fl, met = tabu_optimize(data, [copy.deepcopy(f) for f in fl0], TimeBudget(180.0), seed)
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
        # best：完工不劣于基线 7113，且能耗更小；或完工更小（能耗先放宽）
        if ok:
            k = (m['makespan'], m['energy'])
            if (m['makespan'] <= met0['makespan'] + 0.5 and m['energy'] < met0['energy'] - 0.05) or \
               (m['makespan'] < met0['makespan'] - 0.5 and m['energy'] <= met0['energy']):
                if best is None or k < best_key:
                    best = (fl, m)
                    best_key = k

print('\n== 帕累托改进候选 ==')
cand = [r for r in rows if r.get('m') and r['m']['hard_ok'] and r['m']['tardy_w'] < 1e-6
        and ((r['m']['makespan'] <= met0['makespan'] + 0.5 and r['m']['energy'] < met0['energy']) or
             (r['m']['makespan'] < met0['makespan'] and r['m']['energy'] <= met0['energy']))]
cand.sort(key=lambda r: (r['m']['makespan'], r['m']['energy']))
for r in cand[:5]:
    print('  %s s%-3d fl=%d mk=%.1f e=%.3f' % (r['cfg'], r['seed'], r['m']['flights'],
                                               r['m']['makespan'], r['m']['energy']))
print('改进候选 %d/%d' % (len(cand), len(rows)))

out = {'baseline': {'flights': met0['flights'], 'makespan': round(met0['makespan'], 1),
                    'energy': round(met0['energy'], 3)},
       'rows': []}
for r in rows:
    rec = {'cfg': r['cfg'], 'seed': r['seed'], 'time_s': r.get('time_s'), 'status': r.get('status', 'ok')}
    if r.get('m'):
        m = r['m']
        rec['m'] = {'flights': m['flights'], 'makespan': round(m['makespan'], 1),
                    'energy': round(m['energy'], 3), 'hard_ok': m['hard_ok'],
                    'tardy_w': round(m['tardy_w'], 3), 'bad_zones': m['bad_zones']}
    out['rows'].append(rec)
json.dump(out, open(os.path.join(EVO, 'mk25_micro.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

if best is not None:
    fl, m = best
    json.dump({'flights': [{'fid': f.fid, 'model': f.model,
                            'route': [[s, bs] for s, bs in f.route]} for f in fl],
               'met': {'flights': m['flights'], 'makespan': round(m['makespan'], 1),
                       'energy': round(m['energy'], 3), 'tardy_w': m['tardy_w'],
                       'bad_zones': m['bad_zones']},
               'source': 'mk25_micro'},
              open(os.path.join(EVO, 'mk25_best.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved mk25_best.json fl=%d mk=%.1f e=%.2f'
          % (m['flights'], m['makespan'], m['energy']))
print('saved mk25_micro.json')