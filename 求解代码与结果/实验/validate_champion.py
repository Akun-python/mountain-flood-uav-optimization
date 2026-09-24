# -*- coding: utf-8 -*-
"""稳健性复现验证：用 champion 相同的参数（balanced 权重 / seed 11 族）多次重跑
Tabu，检查是否稳定复现 26 架次 / 6959.8s / 70.71kWh 冠军；只输出指标，不写文件。"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Data, TimeBudget, make_initial, summarize, clone_flights, set_weights
from solvers import tabu_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
p1 = json.load(open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8'))
data = Data()
flights0 = make_initial(data, p1['grouping'])
set_weights(5.0, 0.3, 1.0, 20.0)   # balanced

print('== 冠军参数复现（balanced, seed 11 族, 240s x 5 次）==')
for rep in range(5):
    budget = TimeBudget(240.0)
    t0 = time.time()
    fl, met = tabu_optimize(data, clone_flights(flights0), budget, 11 + 17 * rep)
    m = summarize(met)
    print('rep%d  %d 架  mk=%.1f s  e=%.2f kWh  tardy=%.2f  hard=%s  (%.0fs)'
          % (rep, m['flights'], m['makespan'], m['energy'], m['tardy_w'],
             m['hard_ok'], time.time() - t0))
print('对照冠军：26 架 / 6959.8 s / 70.71 kWh / tardy 0 / hard True')