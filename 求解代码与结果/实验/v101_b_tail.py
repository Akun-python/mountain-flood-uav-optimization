# -*- coding: utf-8 -*-
"""v101：B池尾趟消除——S005 2箱 B→A（A池有空闲），释放B池链 → 完工向C池6233靠拢？"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']
def show(fls, tag):
    m, sch, v, nc = eval_full(data, fls)
    if m is None: print('%s: 不可行' % tag); return None
    last = sorted([(s2['return'], f.fid, f.model, [z for z,_ in f.route]) for f, s2 in ((f, sch[f.fid]) for f in fls)])
    print('%s: mk=%.1f en=%.2f 最后5趟: %s' % (tag, m['makespan'], m['energy'], [(round(t), fid) for t, fid, _, _ in last[-5:]]))
    return m['makespan'], m['energy']
r0 = show(fls, '0 基准25架')
# 找到 B 池 S005 趟（f31）
for f in fls:
    if f.model == 'B' and any(z == 'S005' for z, _ in f.route):
        print('  f%02d B S005 %d箱 %dkg %ds' % (f.fid, len(f.box_ids), sum(data.boxes[b]['mass'] for b in f.box_ids), f.duration()))
        target = f
# 构造 A 趟承接：新建 A S005 趟（把 target 的箱移出，新建 A 趟）
boxes = list(target.box_ids)
newf = Flight(max(f.fid for f in fls) + 100, [('S005', boxes)], 'A', data)
print('  新建A趟: 可行=%s 时长=%ds' % (newf.is_feasible(), newf.duration() if newf.is_feasible() else -1))
fls2 = [f for f in fls if f.fid != target.fid] + [newf]
nv = show(fls2, '1 S005 B→A新建')
# 收编进已有 A S005 趟（f35 A S005 或 f38 A S005|S011）
for f in fls:
    if f.model == 'A' and any(z == 'S005' for z, _ in f.route):
        nb = list(f.box_ids) + boxes
        nf = Flight(f.fid, [(z, list(bs)) for z, bs in f.route], 'A', data)
        nf2 = Flight(f.fid, [(z, (list(bs) + (boxes if z == 'S005' else []))) for z, bs in f.route], 'A', data)
        print('  并入A f%02d %s: 可行=%s 箱%dkg=%d' % (f.fid, [z for z,_ in f.route], nf2.is_feasible(),
            len(nf2.box_ids), sum(data.boxes[b]['mass'] for b in nf2.box_ids)))
        if nf2.is_feasible():
            fls3 = [nf2 if x.fid == f.fid else x for x in fls if x.fid != target.fid]
            show(fls3, '2 S005并入A f%02d' % f.fid)
