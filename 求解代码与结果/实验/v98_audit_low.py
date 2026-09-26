# -*- coding: utf-8 -*-
"""v98：审计 22架/6993.3 与 20架/7778.7 新点（8项）。"""
import sys, os, json
from collections import Counter
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v97_lowfleet.json'), encoding='utf-8'))
for n in ('22', '20'):
    s = d[n]
    fls = [Flight(f['fid'], [(s2, list(bs)) for s2, bs in f['route']], f['model'], data) for f in s['solution']]
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
    print('%s架: mk=%.1f(%.2fmin) en=%.2f 机型%s 硬=%s 违%d 池(A%.0f/B%.0f/C%.0f) 电池%d 覆盖缺%d 区违%d 返航%d 空趟%d 裕度%d → %s' % (
        n, m['makespan'], m['makespan']/60, m['energy'], dict(Counter(f.model for f in fls)), m['hard_ok'], v,
        pt['A']/N['A'], pt['B']/N['B'], pt['C']/N['C'], len(bat),
        len(allb-used)+len(used-allb), len(zb), len(low), len(empty), round(rows[0][0]), 'PASS' if ok else 'ISSUE'))
