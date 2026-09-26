# -*- coding: utf-8 -*-
"""v87：双冠军审计——27架/6571.4/70.68（完工最优，能耗更低）与 26架/6571.4/70.70（架次最少）8项全审。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
data = Data()

def audit(name, p):
    d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
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
    print('%s: %d架 mk=%.1f(%.2fmin) en=%.2f 硬=%s 违规%d 临界%d 池(A%.0f/B%.0f/C%.0f) 电池%d 覆盖缺%d 区违%d 返航%d 空趟%d → %s' % (
        name, len(fls), m['makespan'], m['makespan']/60, m['energy'], m['hard_ok'], v, nc,
        pt['A']/N['A'], pt['B']/N['B'], pt['C']/N['C'], len(bat),
        len(allb-used)+len(used-allb), len(zb), len(low), len(empty), 'ALL PASS' if ok else 'HAS ISSUE'))
    return ok, fls

ok1, f1 = audit('27架冠军', 'p2v75_champion.json')
ok2, f2 = audit('26架新方案', 'p2v85_best.json')
# 26架方案结构
from collections import Counter
print('26架机型:', dict(Counter(f.model for f in f2)))
print('27架机型:', dict(Counter(f.model for f in f1)))
