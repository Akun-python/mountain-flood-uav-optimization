# -*- coding: utf-8 -*-
"""v25d 严格口径 P2 搜索：tabu 600s，完工优先权重，严格 evaluate（区一致硬约束）。
起点：28 架基线（并行线）或 26 架 v24（捎带）——tabu 邻域在严格 evaluate 下会拒绝混乱解。
输出：结果/进化_v25/p2v25d_search.json（best 解 + 指标）。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from common import Data, TimeBudget, make_initial, clone_flights, set_weights, summarize
from solvers import tabu_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

p1 = json.load(open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8'))
init = make_initial(data, p1['grouping'])

# 完工优先权重（makespan 权重最大）
set_weights(10.0, 0.5, 0.5, 10.0)
fl, met = tabu_optimize(data, clone_flights(init), TimeBudget(600), seed=13)
if fl is None:
    print('ERROR: tabu 失败', flush=True)
    sys.exit(1)
print('严格搜索: %d 架 / mk %.1f / %.2f kWh / hard %s / tardy %.3f' % (
    met['flights'], met['makespan'], met['energy'], met['hard_ok'], met['tardy_w']))

# 区一致复核
from p2_solve import dispatch, evaluate
sch, _ = dispatch(data, fl)
m2 = evaluate(data, fl, sch)
bad = sum(1 for scd in sch.values() for sid, bid, t in scd['deliveries']
          if bid.split('-')[0] != sid)
print('复核: hard %s  区不符箱 %d' % (m2['hard_ok'], bad))

json.dump({'metrics': {k: v for k, v in m2.items() if k != 'box_time'}, 'zone_mismatch': bad,
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in fl]},
          open(os.path.join(OUTD, 'p2v25d_search.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved -> 结果/进化_v25/p2v25d_search.json')