# -*- coding: utf-8 -*-
"""v25 诊断：复现 23 架能耗口径解（mk_hyper 权重）并解剖其完工瓶颈。
目标：理解"我们 23 架 7722 s vs 对方 23 架 5694 s"的差距来源——
B/C 机链长、LB2 拆解、最晚架次、能否通过定向修复压缩完工。"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from common import Data, TimeBudget, make_initial, clone_flights, set_weights, summarize
from solvers import tabu_optimize
from p2_solve import dispatch

N_UAVS = {'A': 4, 'B': 2, 'C': 2}

HERE = os.path.dirname(os.path.abspath(__file__))
data = Data()
p1 = json.load(open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8'))
init = make_initial(data, p1['grouping'])

# mk_hyper: 完工权重 200, 架次 0.1, 能耗 0.1, 迟到 5
set_weights(200.0, 0.1, 0.1, 5.0)
budget = TimeBudget(600)
t0 = time.time()
fl, met = tabu_optimize(data, clone_flights(init), budget, seed=13)
dt = time.time() - t0
m = summarize(met)
print('tabu mk_hyper s13: %d 架 / makespan %.1f s / %.3f kWh / tardy %.3f / hard %s / %.0fs' % (
    m['flights'], m['makespan'], m['energy'], m['tardy_w'], m['hard_ok'], dt))

schedule, _ = dispatch(data, fl)
fls = sorted(fl, key=lambda f: schedule[f.fid]['start'])
rows = []
for f in fls:
    sch = schedule[f.fid]
    rows.append({'fid': f.fid, 'uav': sch['uav'], 'model': f.model,
                 'route': [(s, len(bs)) for s, bs in f.route],
                 'nbox': f.nbox, 'start': round(sch['start'], 1), 'return': round(sch['return'], 1),
                 'dur': round(sch['return'] - sch['start'], 1), 'energy': round(f.energy(), 3)})
rows.sort(key=lambda r: r['return'])

print('\n== 架次明细（按返场排序）==')
for r in rows:
    print('f%-3d %s  %-10s n%-2d [%7.0f -> %7.0f] dur=%6.0f  %.2f kWh' % (
        r['fid'], r['model'], str(r['route']), r['nbox'], r['start'], r['return'], r['dur'], r['energy']))

# LB2 拆解（含交接 duration）
dur = {'A': 0.0, 'B': 0.0, 'C': 0.0}
for r in rows:
    dur[r['model']] += r['dur']
lb2 = {g: dur[g] / N_UAVS[g] for g in 'ABC'}
print('\n== LB2 拆解（含交接的任务时长）==')
for g in 'ABC':
    print('  %s: 累计 %.0f s / %d 架 = %.1f s' % (g, dur[g], N_UAVS[g], lb2[g]))
print('  LB2 = %.1f s (%.1f min)；完工 %.1f s 与 LB2 差距 %.0f s (%.1f%%)' % (
    max(lb2.values()), max(lb2.values()) / 60, m['makespan'],
    m['makespan'] - max(lb2.values()), (m['makespan'] - max(lb2.values())) / max(lb2.values()) * 100))

# 每机链：无人机视角
print('\n== 每架无人机的任务链 ==')
chains = {}
for r in rows:
    chains.setdefault(r['uav'], []).append(r)
for uid in sorted(chains):
    ch = chains[uid]
    last = max(c['return'] for c in ch)
    gap = sum(ch[i + 1]['start'] - ch[i]['return'] for i in range(len(ch) - 1))
    print('  %s (%s): %d 架次 -> 最后返场 %7.0f s, 链内空档合计 %5.0f s' % (
        uid, ch[0]['model'], len(ch), last, gap))

print('\n最晚 5 架次 (fid, model, return):', [(r['fid'], r['model'], r['return']) for r in rows[-5:]])

out = os.path.join(HERE, '..', '结果', '进化_v25')
os.makedirs(out, exist_ok=True)
# 存完整可重建解（route 含 box id）
full = [{'fid': f.fid, 'model': f.model, 'route': [(s, list(bs)) for s, bs in f.route]} for f in fl]
json.dump({'flights': rows, 'solution': full, 'lb2': {'duration_s': dur, 'lb2_g': lb2},
           'makespan': m['makespan'], 'energy': m['energy'], 'flights_n': m['flights'],
           'meta': {'weights': 'mk_hyper(200,0.1,0.1,5)', 'seed': 13, 'budget_s': 600}},
          open(os.path.join(out, 'p2v25_diag.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\nsaved -> 结果/进化_v25/p2v25_diag.json（含可重建 solution）')