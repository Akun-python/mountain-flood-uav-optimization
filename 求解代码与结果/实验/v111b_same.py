# -*- coding: utf-8 -*-
"""v111b：A池同区部分箱合并（S006 f27+f28→23kg一趟）——省一趟飞行，能耗降验证。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
base = {f['fid']: Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']}
def W(B): return sum(data.boxes[b]['mass'] for b in B)
def evalv(fls, tag):
    sch, _ = dispatch_compliant(data, fls)
    mm, s, vv, nn = eval_full(data, fls)
    vb = cb(data, sch, fls)
    ok = mm is not None and vv == 0 and nn == 0 and mm['hard_ok'] and len(vb) == 0
    pools = {}
    for f in fls:
        pools.setdefault(f.model, []).append(sch[f.fid]['return'])
    pl = {m: round(max(v)) for m, v in pools.items()}
    print('%s: %d架 mk=%s en=%s OK=%s 池%s' % (tag, len(fls),
        '%.1f' % mm['makespan'] if mm else '-', '%.2f' % mm['energy'] if mm else '-', ok, pl), flush=True)
    return (mm['makespan'], mm['energy']) if mm and ok else None
# 同区部分合并：对每个区，若有多趟且可重组为更少趟（箱重 ≤ 容量）则试
zfl = {}
for f in base.values():
    for z, bs in f.route:
        if len(set(zz for zz,_ in f.route)) == 1:
            zfl.setdefault(z, []).append(f)
for z, fs in sorted(zfl.items()):
    B = [b for f in fs for _, bs in f.route for b in bs]
    n = len(fs)
    if n < 2: continue
    cap = 25 if fs[0].model == 'A' else (30 if fs[0].model == 'B' else 80)
    tot = W(B)
    # 最小趟数 k 满足 k*cap >= tot
    import math
    kmin = math.ceil(tot / cap)
    if kmin >= n: continue
    # 找 kmin 趟的拆法（贪心近似：按重量贪心装箱）
    best = None
    for comb in itertools.combinations(B, n - 1):
        # 简化：只试 1 趟并 2 趟（n-1 趟删 1 趟）
        break
    # 简单法：两趟合并（每趟删减至可合并）
    for i in range(n):
        for j in range(i + 1, n):
            Bc = fs[i].box_ids + fs[j].box_ids
            if W(Bc) > cap: continue
            z1 = [zz for zz,_ in fs[i].route][0]
            nf = Flight(800, [(z1, list(Bc))], fs[i].model, data)
            if nf.is_feasible():
                gain = fs[i].duration() + fs[j].duration() - nf.duration()
                if gain > 100:
                    print('★%s: f%d+f%d 合并 %.0fkg dur=%.0f (省%.0fs)' % (z, fs[i].fid, fs[j].fid, W(Bc), nf.duration(), gain), flush=True)
                    new = [base[f] for f in base if f not in (fs[i].fid, fs[j].fid)] + [nf]
                    evalv(sorted(new, key=lambda x: x.fid), 'v111b %s合趟' % z)
