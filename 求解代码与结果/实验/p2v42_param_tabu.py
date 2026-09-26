# -*- coding: utf-8 -*-
"""v42-π2：GA 帕累托点（23-25 架）tabu 精化。
读 param_pareto.json → 每点 build → tabu（完工/能耗权重 × 3 种子 × 90s）→
输出 param_refined.json（精化后 23-25 架合规点 + 官方指标）。"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate
from common import set_weights, clone_flights, TimeBudget
from solvers import tabu_optimize
import p2v42_param_ga as P

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
pareto = json.load(open(os.path.join(EVO, 'param_pareto.json'), encoding='utf-8'))['pareto']

CONFIGS = {
    'mk': (10.0, 0.5, 0.5, 10.0),
    'en': (1.0, 0.02, 2.0, 20.0),
}
rows = []
for i, pt in enumerate(pareto):
    fl0 = P.build(**pt['gene'])
    data = Data()
    sch, _ = dispatch(data, fl0)
    m0 = P.evaluate_sol(fl0)
    if m0['nbox'] != 80 or m0['uniq'] != 80:
        continue
    print('点%d: 初始 %d架 mk=%.1f e=%.3f' % (i, m0['flights'], m0['makespan'], m0['energy']), flush=True)
    for name, w in CONFIGS.items():
        set_weights(*w)
        for seed in (3, 7, 11):
            data2 = Data()
            fl, met = tabu_optimize(data2, clone_flights(fl0), TimeBudget(90), seed)
            if fl is None or met is None:
                continue
            nf = len(fl)
            if not (23 <= nf <= 25):
                continue
            rows.append({'gene': pt['gene'], 'config': name, 'seed': seed,
                         'flights': nf, 'makespan': met['makespan'], 'energy': met['energy'],
                         'hard_ok': met['hard_ok'], 'tardy_w': met['tardy_w'],
                         'bad': len(met['bad_zones'])})
            print('   %-3s s%-2d %d架 mk=%7.1f e=%6.3f hard=%s' % (
                name, seed, nf, met['makespan'], met['energy'], met['hard_ok']), flush=True)

ok = [r for r in rows if r['hard_ok'] and r['tardy_w'] < 1e-6 and r['bad'] == 0]
# 非支配筛选
non_dom = []
for r in ok:
    dominated = False
    for q in ok:
        if q is r:
            continue
        if q['flights'] <= r['flights'] and q['makespan'] <= r['makespan'] + 1e-6 \
           and q['energy'] <= r['energy'] + 1e-6 and (
                q['flights'] < r['flights'] or q['makespan'] < r['makespan'] - 1e-6 or q['energy'] < r['energy'] - 1e-6):
            dominated = True
            break
    if not dominated:
        non_dom.append(r)
non_dom.sort(key=lambda r: (r['makespan'], r['energy']))
print('\n合规 %d/%d  非支配 %d 点:' % (len(ok), len(rows), len(non_dom)))
for r in non_dom:
    print('  %d架 mk=%7.1f e=%6.3f (%s s%d)' % (r['flights'], r['makespan'], r['energy'], r['config'], r['seed']))
json.dump({'solver': 'v42-param-ga+tabu', 'points': ok, 'pareto': non_dom},
          open(os.path.join(EVO, 'param_refined.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved param_refined.json')