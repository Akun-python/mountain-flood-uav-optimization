# -*- coding: utf-8 -*-
"""v109f：验证对方组批机制——S004 拆 B 2趟(3+3箱) + S002 改 C 型 → 严格口径完工/能耗。"""
import sys, os, json, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
def show(fls, tag):
    sch, _ = dispatch_compliant(data, fls)
    mm, s, vv, nn = eval_full(data, fls)
    vb = cb(data, sch, fls)
    pools = {}
    for f in fls:
        pools.setdefault(f.model, []).append(sch[f.fid]['return'])
    pl = {m: 'max %.0f (n=%d)' % (max(v), len(v)) for m, v in pools.items()}
    print('%s: %d架 mk=%.1f en=%.2f hard=%s bat=%d 池=%s' % (tag, len(fls), mm['makespan'], mm['energy'], mm['hard_ok'], len(vb), pl), flush=True)
show(fls, '基线25架')
# 找 S004 C 趟与 S002 B 趟
f7 = next(f for f in fls if f.fid == 7)   # C S004 6箱
f4 = next(f for f in fls if f.fid == 4)   # B S002 8箱?
print('f7:', [(z, len(bs)) for z, bs in f7.route], f7.model, 'f4:', [(z, len(bs)) for z, bs in f4.route], f4.model)
s004 = [b for z, bs in f7.route if z == 'S004' for b in bs]
s002 = [b for z, bs in f4.route if z == 'S002' for b in bs]
print('S004 箱:%d 重%.0f | S002 箱:%d 重%.0f' % (len(s004), sum(data.boxes[b]['mass'] for b in s004), len(s002), sum(data.boxes[b]['mass'] for b in s002)))
# 方案A: S004 拆 B 2趟(3+3), S002 改 C 1趟
half = s004[:3]; half2 = s004[3:]
nf1 = Flight(90, [('S004', list(half))], 'B', data)
nf2 = Flight(91, [('S004', list(half2))], 'B', data)
nf3 = Flight(92, [('S002', list(s002))], 'C', data)
new = [f for f in fls if f.fid not in (7, 4)] + [nf1, nf2, nf3]
print('A: f7(S004 B1) fea=%s dur=%.0f; B2 fea=%s dur=%.0f; S002-C fea=%s dur=%.0f' % (
    nf1.is_feasible(), nf1.duration(), nf2.is_feasible(), nf2.duration(), nf3.is_feasible(), nf3.duration()))
show(new, '方案A(26架)')
