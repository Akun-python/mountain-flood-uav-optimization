# -*- coding: utf-8 -*-
"""v102：S005 f31 B 拆分——1箱给A（新建A趟），验证完工。+ C池最后返场下界精确核算。"""
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
    last = sorted([(s2['return'], f.fid, f.model) for f in fls for s2 in [sch[f.fid]]])
    print('%s: mk=%.1f en=%.2f 最后4: %s' % (tag, m['makespan'], m['energy'], [(round(t), fid) for t, fid, _ in last[-4:]]))
    return m['makespan'], m['energy']
show(fls, '0 基准')
f31 = [f for f in fls if f.fid == 31][0]
bxs = sorted(f31.box_ids, key=lambda b: data.boxes[b]['mass'], reverse=True)
print('f31箱: %s 总%dkg' % ([(b, data.boxes[b]['mass']) for b in bxs], sum(data.boxes[b]['mass'] for b in bxs)))
# 方案A：拆最重1箱给A新建
for take in range(1, 3):
    moved = bxs[:take]
    remain = bxs[take:]
    nf_b = Flight(31, [('S005', remain)], 'B', data)
    nf_a = Flight(max(f.fid for f in fls) + 100 + take, [('S005', moved)], 'A', data)
    ok = nf_b.is_feasible() and nf_a.is_feasible() and sum(data.boxes[b]['mass'] for b in moved) <= 25
    if ok:
        fls2 = [nf_b if f.fid == 31 else f for f in fls] + [nf_a]
        r = show(fls2, '方案%d: A取%d箱(%dkg) B剩%d箱' % (take, take, sum(data.boxes[b]['mass'] for b in moved), len(remain)))
    else:
        print('方案%d 不可行: B=%s A=%s mv=%dkg' % (take, nf_b.is_feasible(), nf_a.is_feasible(), sum(data.boxes[b]['mass'] for b in moved)))
# C池最后返场下界核算：6趟时长
cfl = [(f.fid, f.duration()) for f in fls if f.model == 'C']
print('C池6趟: %s 总%ds/2台=%ds' % ([d2 for _, d2 in cfl], sum(d2 for _, d2 in cfl), sum(d2 for _, d2 in cfl)/2))
