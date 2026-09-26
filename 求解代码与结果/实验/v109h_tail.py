# -*- coding: utf-8 -*-
"""v109h：削除B池尾趟 f31 —— S005 1箱(14kg)并入 f28(A S006 6kg→20kg)，重调度验证。"""
import sys, os, json
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
    pl = {m: 'max %.0f' % max(v) for m, v in pools.items()}
    print('%s: %d架 mk=%.1f en=%.2f hard=%s bat=%d %s' % (tag, len(fls), mm['makespan'], mm['energy'], mm['hard_ok'], len(vb), pl), flush=True)
show(fls, '基线25架')
f31 = next(f for f in fls if f.fid == 31)
f28 = next(f for f in fls if f.fid == 28)
print('f31:', [(z, bs) for z, bs in f31.route], 'f28:', [(z, bs) for z, bs in f28.route])
s005_wat2 = [b for z, bs in f31.route for b in bs if b == 'S005-WAT-02']
s005_wat3 = [b for z, bs in f31.route for b in bs if b == 'S005-WAT-03']
# 试：WAT-03 并入 f28
for bid in ('S005-WAT-02', 'S005-WAT-03'):
    b2 = [b for z, bs in f31.route for b in bs if b == bid]
    if not b2: continue
    route28 = [('S006', list(f28.route[0][1]) + b2)]
    nf28 = Flight(93, route28, 'A', data)
    route31 = [('S005', [b for z, bs in f31.route for b in bs if b != bid])]
    nf31 = Flight(94, route31, 'B', data)
    print('%s: f28_new fea=%s dur=%.0f (old %.0f); f31_new fea=%s dur=%.0f (old %.0f)' % (
        bid, nf28.is_feasible(), nf28.duration(), f28.duration(), nf31.is_feasible(), nf31.duration(), f31.duration()))
    new = [f for f in fls if f.fid not in (28, 31)] + [nf28, nf31]
    show(new, '削f31(%s→f28)' % bid)
