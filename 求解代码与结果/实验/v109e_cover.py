# -*- coding: utf-8 -*-
"""v109e：列覆盖完整求解——by_box 索引贪心 + 未覆盖单区补齐 → 严格调度验证完工/能耗。"""
import sys, os, json, itertools, time, math
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
data = Data()
CAP = {'A': 25, 'B': 30, 'C': 80}
zbox = {}
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
for f in [Flight(x['fid'], [(s, list(bs)) for s, bs in x['route']], x['model'], data) for x in d['solution']]:
    for z, bs in f.route:
        zbox.setdefault(z, []).extend(bs)
def angle_key(z, ref):
    a = data.areas[z]
    return math.atan2(a['lat'] - ref[1], (a['lon'] - ref[0]) * math.cos(ref[1] * math.pi / 180))
# 受限列池：单区全装 + 2区全装 + C型3区全装（避免 80 万超集）
cols = []
fid = 500
o = data.centers['O01']; ref = (o['lon'], o['lat'])
def add(zs_order, combo_map, m):
    global fid
    nf = Flight(fid, [(z, list(combo_map[z])) for z in zs_order], m, data)
    if nf.is_feasible():
        cols.append((fid, nf.duration(), nf.energy(), {z: frozenset(combo_map[z]) for z in zs_order}, nf))
        fid += 1
zones = sorted(zbox)
# 单区全装
for z in zones:
    bs = zbox[z]
    for m in 'ABC':
        if sum(data.boxes[b]['mass'] for b in bs) <= CAP[m]:
            add([z], {z: bs}, m)
# 2区全装
for z1, z2 in itertools.combinations(zones, 2):
    if sum(data.boxes[b]['mass'] for b in zbox[z1] + zbox[z2]) > CAP['C']: continue
    for m in 'ABC':
        if sum(data.boxes[b]['mass'] for b in zbox[z1] + zbox[z2]) > CAP[m]: continue
        zs = sorted([z1, z2], key=lambda z: angle_key(z, ref))
        add(zs, {z1: zbox[z1], z2: zbox[z2]}, m)
# C 型 3区全装
for z1, z2, z3 in itertools.combinations(zones, 3):
    if sum(data.boxes[b]['mass'] for z in (z1,z2,z3) for b in zbox[z]) > CAP['C']: continue
    zs = sorted([z1,z2,z3], key=lambda z: angle_key(z, ref))
    add(zs, {z: zbox[z] for z in (z1,z2,z3)}, 'C')
print('列池: %d' % len(cols), flush=True)
by_box = {}
for cid, dur, en, cov, nf in cols:
    for z, s in cov.items():
        for b in s: by_box.setdefault(b, []).append(cid)
cidx = {c[0]: c for c in cols}
allboxes = set(b for bs in zbox.values() for b in bs)
# 贪心：最大化新箱覆盖数，次优 min dur/total——完整到覆盖 80
covered = set(); sel = []
while covered != allboxes:
    best = None
    for b in allboxes - covered:
        for cid in by_box.get(b, []):
            cidn, dur, en, cov, nf = cidx[cid]
            nb = len(set(bx for z, s in cov.items() for bx in s) - covered)
            gain = nb / (dur / 1000.0)
            if best is None or gain > best[0]:
                best = (gain, cid)
    if best is None: break
    cidn, dur, en, cov, nf = cidx[best[1]]
    sel.append(nf); covered |= set(bx for z, s in cov.items() for bx in s)
    if len(sel) > 40: break
print('覆盖: %d 趟 %d/80 总飞%.0f' % (len(sel), len(covered), sum(f.duration() for f in sel)), flush=True)
if covered == allboxes:
    fls = sorted(sel, key=lambda f: f.fid)
    # 分配新 fid 连续（Flight.fid 需唯一）
    fls = [Flight(i + 1, [(z, list(bs)) for z, bs in f.route], f.model, data) for i, f in enumerate(fls)]
    sch, _ = dispatch_compliant(data, fls)
    mm, s, vv, nn = eval_full(data, fls)
    print('★%d架 mk=%.1f(%.2fmin) en=%.2f 总飞%.0f hard=%s' % (
        len(fls), mm['makespan'], mm['makespan']/60, mm['energy'], sum(f.duration() for f in fls), mm['hard_ok']), flush=True)
