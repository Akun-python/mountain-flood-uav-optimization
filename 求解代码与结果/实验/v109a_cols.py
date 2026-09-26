# -*- coding: utf-8 -*-
"""v109a：可行多区顺访列探查——15区2区对(105)/3区组 的可行性与总飞行节省潜力。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
data = Data()
# 当前冠军的箱分布
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
zbox = {}
for f in fls:
    for z, bs in f.route:
        zbox.setdefault(z, []).extend(bs)
total_flight = sum(f.duration() for f in fls)
single = [f for f in fls if len(set(z for z, _ in f.route)) == 1]
print('25架: 总飞行 %.0f s, 单区趟 %d/%d' % (total_flight, len(single), len(fls)))
# 每个区的当前趟时长（单区部分）
zt = {}
for f in single:
    z = [z for z, _ in f.route][0]
    zt.setdefault(z, []).append(f.duration())
# 枚举2区对：同机型可行的顺访列（含所有箱 → 若容量超限则部分拆分考察）
t0 = time.time(); n_ok = 0; n_ok_all = 0
savings = []
zones = sorted(zbox)
for z1, z2 in itertools.combinations(zones, 2):
    b1, b2 = zbox[z1], zbox[z2]
    for m in 'ABC':
        cap = {'A': 25, 'B': 30, 'C': 80}[m]
        # 全部箱装入（若超限则跳过——只统计能全装的组合）
        tot = sum(data.boxes[b]['mass'] for b in b1 + b2)
        if tot > cap: continue
        nf = Flight(900, [(z1, list(b1)), (z2, list(b2))], m, data)
        if nf.is_feasible():
            n_ok_all += 1
            single_t = sum(sum(zt.get(z, []) or [1000]) for z in (z1, z2)) if zt.get(z1) and zt.get(z2) else 99999
            savings.append((single_t - nf.duration(), z1, z2, m, round(nf.duration())))
print('2区全装可行列: %d 个 (%.0fs)' % (n_ok_all, time.time()-t0))
savings.sort(reverse=True)
print('top 节省（单区趟时长和 - 顺访时长）:')
for s, z1, z2, m, d2 in savings[:12]:
    print('  %s|%s %s: -%.0fs' % (z1, z2, m, s))
# 3区组容量检查（粗略：C 型大容量 + A/B 近区）
n3 = 0
for tup in itertools.combinations(zones, 3):
    for m in ('B', 'C'):
        cap = {'B': 30, 'C': 80}[m]
        if sum(data.boxes[b]['mass'] for z in tup for b in zbox[z]) > cap: continue
        nf = Flight(901, [(z, list(zbox[z])) for z in tup], m, data)
        if nf.is_feasible():
            n3 += 1
print('3区可行列(B/C全装): %d' % n3)
