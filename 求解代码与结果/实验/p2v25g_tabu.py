# -*- coding: utf-8 -*-
"""v25g 从 v25b 解出发的 tabu 继续搜索（严格口径，完工优先权重，600s）。
solvers.tabu_optimize 接受任意起点；期望在 7394.9 附近找到更优结构。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate
from common import TimeBudget, set_weights
from solvers import tabu_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

d = json.load(open(os.path.join(OUTD, 'p2v25b_compress26.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in d['solution']]
sch0, _ = dispatch(data, fls)
m0 = evaluate(data, fls, sch0)
print('起点: %d 架 / mk %.1f / %.2f kWh' % (len(fls), m0['makespan'], m0['energy']), flush=True)

set_weights(10.0, 0.5, 0.5, 10.0)
fl, met = tabu_optimize(data, fls, TimeBudget(600), seed=7)
if fl is None:
    print('tabu 失败', flush=True)
    sys.exit(1)
sch, _ = dispatch(data, fl)
m = evaluate(data, fl, sch)
bad = sum(1 for scd in sch.values() for sid, bid, t in scd['deliveries']
          if bid.split('-')[0] != sid)
print('tabu 后: %d 架 / mk %.1f (%.1f min) / %.2f kWh / hard %s / 区不符 %d' % (
    len(fl), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], bad))
if m['makespan'] < m0['makespan'] - 1e-6 and bad == 0 and m['hard_ok']:
    json.dump({'best': {k: v for k, v in m.items() if k != 'box_time'},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in fl]},
              open(os.path.join(OUTD, 'p2v25g_tabu.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p2v25g_tabu.json')
else:
    print('未改善或不可行，不保存')