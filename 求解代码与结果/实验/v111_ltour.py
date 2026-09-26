# -*- coding: utf-8 -*-
"""v111：A/B池轻区多区顺访合并（部分箱，2-3区）——枚举可行顺访列 + beam 选择 → 能耗降验证。"""
import sys, os, json, itertools, time, math
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
base = {f['fid']: Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']}
CAP = {'A': 25, 'B': 30, 'C': 80}
def W(B): return sum(data.boxes[b]['mass'] for b in B)
def angle_key(z, ref):
    a = data.areas[z]
    return math.atan2(a['lat'] - ref[1], (a['lon'] - ref[0]) * math.cos(ref[1] * math.pi / 180))
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
# A池轻区：S006/S011/S014 的 A 趟箱
o = data.centers['O01']; ref = (o['lon'], o['lat'])
fidn = 700
cols = []  # (gain, src_fids, new_flight)
# 构造 2-3 区顺访列（A/B 型，部分箱——从单区趟拿 1-2 箱）
singleA = [f for f in base.values() if f.model == 'A' and len(set(z for z,_ in f.route)) == 1]
print('A池单区趟:', [(f.fid, [z for z,_ in f.route], [len(bs) for _, bs in f.route]) for f in singleA], flush=True)
# 对每趟尝试：把该趟所有箱移入"顺访组合"由另一趟承担？——不——直接枚举"轻区对顺访"：
# 从 A 池找 S006/S011/S014/S002 单区趟，尝试两两合成（箱重和 ≤25 且顺访可行）
byzone = {}
for f in singleA:
    z = [z for z, _ in f.route][0]
    byzone.setdefault(z, []).append(f)
for z1, fs1 in byzone.items():
    for z2, fs2 in byzone.items():
        if z1 >= z2: continue
        for f1 in fs1:
            for f2 in fs2:
                B = f1.box_ids + f2.box_ids
                if W(B) > CAP['A']: continue
                zs = sorted([z1, z2], key=lambda z: angle_key(z, ref))
                r1, r2 = (z1, z2) if zs[0] == z1 else (z2, z1)
                nf = Flight(fidn, [(r1, list(f1.box_ids)), (r2, list(f2.box_ids))], 'A', data)
                fidn += 1
                if not nf.is_feasible(): continue
                gain = f1.duration() + f2.duration() - nf.duration()
                if gain > 50:
                    cols.append((gain, [f1.fid, f2.fid], nf))
cols.sort(key=lambda c: -c[0])
print('A池2区顺访候选: %d 个' % len(cols), flush=True)
for g, sids, nf in cols[:10]:
    print('  省%.0fs: f%s -> %s dur=%.0f' % (g, '+'.join(map(str, sids)), [(z, len(bs)) for z, bs in nf.route], nf.duration()), flush=True)
# 选最大不相交组合
used = set(); sel = []
for g, sids, nf in cols:
    if used & set(sids): continue
    used |= set(sids); sel.append(nf)
if sel:
    new = [base[f] for f in base if f not in used] + sel
    evalv(sorted(new, key=lambda x: x.fid), 'A池2区顺访(%d合)' % len(sel))
