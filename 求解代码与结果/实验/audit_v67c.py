# -*- coding: utf-8 -*-
"""v67c 冠军解独立复核（audit_results.check_battery 复用）。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
OUTD = '求解代码与结果/结果/进化_v25'
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v61_gatv67c_greedy.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m, sch, v, nc = eval_full(data, fls)
print('eval_full:', round(m['makespan'],1), round(m['energy'],2), 'hard', m['hard_ok'], '违规', v, '临界', nc)
bat = cb(data, sch, fls)
print('电池复核: %d 条违规（0=PASS）' % len(bat))
allb = set(data.boxes)
used = set()
for f in fls:
    for b in f.box_ids: used.add(b)
print('覆盖: 缺 %d 重 %d 越界 %d' % (len(allb-used), len(used)-len(allb), sum(1 for f in fls for b in f.box_ids if b.split('-')[0] != f.route[0][0])))
urg = [(f.fid, f.route[0][0]) for f in fls for b in f.box_ids if data.boxes[b]['deadline_exp'] <= 3600.0]
print('紧急箱所在趟:', urg)
print('审计完成 PASS' if (v==0 and nc==0 and len(bat)==0) else '审计 FAIL')
