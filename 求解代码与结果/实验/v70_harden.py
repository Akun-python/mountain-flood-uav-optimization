# -*- coding: utf-8 -*-
"""v70：从 6799.9/28架 出发硬化（完工窄带收尾 + 宽带再扫一轮）+ 独立审计。"""
import sys, os, json, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v69c_d28_n28.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m, sch, v, nc = eval_full(data, fls)
print('v69c 28架: mk=%.1f en=%.2f hard=%s 违规%d 临界%d 趟%d' % (m['makespan'], m['energy'], m['hard_ok'], v, nc, len(fls)))
bat = cb(data, sch, fls)
allb = set(data.boxes); used = set()
for f in fls:
    for b in f.box_ids: used.add(b)
print('电池%d 覆盖缺%d重%d' % (len(bat), len(allb-used), len(used)-len(allb)))
pt = {'A':0.0,'B':0.0,'C':0.0}
for f in fls: pt[f.model] += f.duration()
print('池T/台:', {g: round(pt[g]/{'A':4,'B':2,'C':2}[g],0) for g in 'ABC'})
print('机型:', {g: sum(1 for f in fls if f.model==g) for g in 'ABC'})
# 硬化：窄带完工降贪婪（v46 式）直到收敛
def evalf(x):
    mm, ss, vv, nn = eval_full(data, x)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']
cur = fls
t0 = time.time()
for rnd in range(40):
    m0c = evalf(cur)[0]
    best_ls = None
    c, fa, sc, si, di = build_candidates_x(cur)
    for i in range(min(len(c), 40)):
        imp = apply_cand_x(cur, c[i])
        if imp is None: continue
        r = evalf(imp)
        if r is None: continue
        mk2, en2 = r
        if mk2 < m0c - 0.5 and (best_ls is None or (mk2, en2) < (best_ls[0], best_ls[1])):
            best_ls = (mk2, en2, imp)
    if best_ls is None: break
    cur = best_ls[2]
    print(f'  硬化r{rnd}: mk={best_ls[0]:.1f} en={best_ls[1]:.2f}')
m2, s2, v2, n2 = eval_full(data, cur)
print('硬化后: mk=%.1f (%.1fmin) en=%.2f 趟%d' % (m2['makespan'], m2['makespan']/60, m2['energy'], len(cur)))
bat2 = cb(data, s2, cur)
print('电池%d 违规%d 临界%d' % (len(bat2), v2, n2))
json.dump({'best': {'makespan': m2['makespan'], 'energy': m2['energy'], 'flights': len(cur)},
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
          open(os.path.join(OUTD, 'p2v70_champion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p2v70_champion.json', round(time.time()-t0), 's')
