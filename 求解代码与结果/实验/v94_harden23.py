# -*- coding: utf-8 -*-
"""v94：23架/6598.8 窄带硬化（15轮）+ 8项审计。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
from dqn23_gat import build_candidates_x, apply_cand_x
from collections import Counter
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v93_best23.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']
mk0, en0 = evalf(fls)
best_mk, best_en = mk0, en0
for rnd in range(15):
    c, fa, sc, si, di = build_candidates_x(fls)
    imp_prog = None
    for i in range(len(c)):
        cc = c[i]
        if cc[0] == 'stop': continue
        try: imp = apply_cand_x(fls, cc)
        except Exception: continue
        if imp is None: continue
        r = evalf(imp)
        if r is None: continue
        if r[0] <= best_mk + 120 and (r[0], -r[1]) < (best_mk, -best_en):
            imp_prog = (r[0], r[1], imp)
    if imp_prog is None: continue
    m2, e2, imp = imp_prog
    if m2 < best_mk - 0.5 or (abs(m2 - best_mk) < 0.5 and e2 < best_en - 0.01):
        print('r%d: ★mk=%.1f en=%.2f' % (rnd, m2, e2), flush=True)
        best_mk, best_en = m2, e2; fls = imp
print('硬化后: mk=%.1f en=%.2f → %s' % (best_mk, best_en, '不动点' if best_mk >= mk0 - 0.5 else '新纪录'))
# 8项审计
m, sch, v, nc = eval_full(data, fls)
allb = set(data.boxes); used = set()
for f in fls: used.update(f.box_ids)
zb = [f.fid for f in fls for s2, bs in f.route for b in bs if b.split('-')[0] != s2]
bat = cb(data, sch, fls)
low = [f.fid for f in fls if f.energy() > 0.8*{'A':4.5,'B':4.0,'C':8.0}[f.model]]
empty = [f.fid for f in fls if not f.box_ids]
ok = (v==0 and nc==0 and not bat and not zb and not low and not empty and not allb-used and not used-allb and m['hard_ok'])
pt = {'A':0.0,'B':0.0,'C':0.0}; N = {'A':4,'B':2,'C':2}
for f in fls: pt[f.model] += f.duration()
rows = []
for fid, s2 in sch.items():
    for sid, bid, t in s2['deliveries']:
        bx = data.boxes[bid]
        mm_ = min(bx['deadline_first'], bx['deadline_exp'])
        if mm_ < 1e15: rows.append((mm_ - t, bid))
rows.sort()
print('机型%s mk=%.1f(%.2fmin) en=%.2f 硬=%s 违%d 临界%d 池(A%.0f/B%.0f/C%.0f) 电池%d 覆盖缺%d 区违%d 返航%d 空趟%d → %s' % (
    dict(Counter(f.model for f in fls)), m['makespan'], m['makespan']/60, m['energy'], m['hard_ok'], v, nc,
    pt['A']/N['A'], pt['B']/N['B'], pt['C']/N['C'], len(bat),
    len(allb-used)+len(used-allb), len(zb), len(low), len(empty), 'ALL PASS' if ok else 'HAS ISSUE'))
print('最紧裕度:', (round(rows[0][0]), rows[0][1]))
if ok:
    json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy'], 'flights': len(fls)},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]},
              open(os.path.join(OUTD, 'p2v94_champion23.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v94_champion23.json')
