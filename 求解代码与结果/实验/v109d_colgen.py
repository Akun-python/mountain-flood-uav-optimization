# -*- coding: utf-8 -*-
"""v109d：列生成探查——从零枚举可行列(单区+2区顺访×机型+部分装箱)，贪心覆盖80箱，估计总飞行下界。"""
import sys, os, json, itertools, time, math
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
data = Data()
CAP = {'A': 25, 'B': 30, 'C': 80}
zones = sorted(data.areas)
zbox = {}
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
for f in [Flight(x['fid'], [(s, list(bs)) for s, bs in x['route']], x['model'], data) for x in d['solution']]:
    for z, bs in f.route:
        zbox.setdefault(z, []).extend(bs)
def angle_key(z, ref):
    a = data.areas[z]
    return math.atan2(a['lat'] - ref[1], (a['lon'] - ref[0]) * math.cos(ref[1] * math.pi / 180))
def gen_cols():
    cols = []
    fid = 500
    o = data.centers['O01']; ref = (o['lon'], o['lat'])
    # 单区列（整区箱装入各机型，若超载则拆子集）
    for z in zones:
        bs = zbox[z]
        for m in 'ABC':
            cap = CAP[m]
            # 最大载箱子集（贪心按重）
            sub = []
            w = 0.0
            for b in sorted(bs, key=lambda b: -data.boxes[b]['mass']):
                if w + data.boxes[b]['mass'] <= cap:
                    sub.append(b); w += data.boxes[b]['mass']
            for k in range(1, len(sub) + 1):
                for combo in itertools.combinations(sub, k):
                    if sum(data.boxes[b]['mass'] for b in combo) > cap: continue
                    nf = Flight(fid, [(z, list(combo))], m, data)
                    if nf.is_feasible():
                        cols.append((fid, nf.duration(), nf.energy(), {z: frozenset(combo)}, nf))
                        fid += 1
    # 2区顺访列
    for z1, z2 in itertools.combinations(zones, 2):
        b1, b2 = zbox[z1], zbox[z2]
        for m in 'ABC':
            cap = CAP[m]
            for k1 in range(1, min(len(b1), 4) + 1):
                for k2 in range(1, min(len(b2), 4) + 1):
                    for c1 in itertools.combinations(b1, k1):
                        w1 = sum(data.boxes[b]['mass'] for b in c1)
                        if w1 > cap: continue
                        for c2 in itertools.combinations(b2, k2):
                            if w1 + sum(data.boxes[b]['mass'] for b in c2) > cap: continue
                            zs = sorted([z1, z2], key=lambda z: angle_key(z, ref))
                            r1, r2 = (z1, z2) if zs[0] == z1 else (z2, z1)
                            nf = Flight(fid, [(r1, list(c1)), (r2, list(c2))], m, data)
                            if nf.is_feasible():
                                cols.append((fid, nf.duration(), nf.energy(), {z1: frozenset(c1), z2: frozenset(c2)}, nf))
                                fid += 1
    return cols
t0 = time.time()
cols = gen_cols()
print('候选列: %d (%.0fs)' % (len(cols), time.time()-t0))
# 贪心覆盖：选每箱省时最少的列？——简化：按"覆盖新箱数/时长"比贪心
import heapq
covered = set()
sel = []
allboxes = set(b for bs in zbox.values() for b in bs)
by_box = {}
for fid, dur, en, cov, nf in cols:
    for z, s in cov.items():
        for b in s: by_box.setdefault(b, []).append((dur, fid, z, s))
# 贪心：每次选未覆盖箱最多的省时列
pool = sorted(cols, key=lambda c: (-sum(1 for z, s in c[3].items() for b in s if b not in covered), c[1]))
while covered != allboxes and pool:
    best_i = None; best_gain = -1
    for i, c in enumerate(pool[:2000]):
        fid, dur, en, cov, nf = c
        nb = sum(1 for z, s in cov.items() for b in s if b not in covered)
        if nb == 0: continue
        gain = nb / (dur / 1000.0)
        if gain > best_gain: best_gain, best_i = gain, i
    if best_i is None: break
    fid, dur, en, cov, nf = pool.pop(best_i)
    sel.append((dur, en, nf))
    for z, s in cov.items(): covered |= set(s)
print('贪心覆盖: %d 趟 覆盖%d/80 总飞%.0f 能耗%.2f' % (
    len(sel), len(covered), sum(d for d, _, _ in sel), sum(e for _, e, _ in sel)))
