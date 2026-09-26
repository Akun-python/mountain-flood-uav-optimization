# -*- coding: utf-8 -*-
"""v89：审计 25架/6571.4/69.77 新候选（8项 + 机型结构 + 池负载）。"""
import sys, os, json
from collections import Counter
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v88_fleet23.json'), encoding='utf-8'))
sol25 = None
for s in d['solutions']:
    if s['flights'] == 25:
        sol25 = s; break
print('25架解: mk=%.1f en=%.2f' % (sol25['makespan'], sol25['energy']))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in sol25['solution']]
print('机型:', dict(Counter(f.model for f in fls)))
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
print('mk=%.1f(%.2fmin) en=%.2f 硬=%s 违规%d 临界%d 池(A%.0f/B%.0f/C%.0f) 电池%d 覆盖缺%d 区违%d 返航%d 空趟%d → %s' % (
    m['makespan'], m['makespan']/60, m['energy'], m['hard_ok'], v, nc,
    pt['A']/N['A'], pt['B']/N['B'], pt['C']/N['C'], len(bat),
    len(allb-used)+len(used-allb), len(zb), len(low), len(empty), 'ALL PASS' if ok else 'HAS ISSUE'))
# 最紧裕度
rows = []
for fid, s2 in sch.items():
    for sid, bid, t in s2['deliveries']:
        bx = data.boxes[bid]
        dl_f, dl_e = bx['deadline_first'], bx['deadline_exp']
        mm_ = min(dl_f, dl_e)
        if mm_ < 1e15:
            rows.append((mm_ - t, bid, t))
rows.sort()
print('最紧裕度Top3:', [(round(r[0]), r[1]) for r in rows[:3]])
if ok:
    json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy'], 'flights': len(fls)},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]},
              open(os.path.join(OUTD, 'p2v89_champion25.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v89_champion25.json (新正冠军候选)')
