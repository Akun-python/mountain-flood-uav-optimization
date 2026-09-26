# -*- coding: utf-8 -*-
"""v95c：多区优先构造器——从零装箱（80箱→趟），多区省段最大优先，检验总飞行下界。
如果构造器总飞行 >= 45312 → 25架冠军总飞行是下界 → 完工<6000 数学上不可行。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from core import segment_geometry
data = Data()
# 80 箱按区聚类
by_zone = {}
for bid, bx in data.boxes.items():
    z = bid.split('-')[0]
    by_zone.setdefault(z, []).append(bid)
print('各区箱数:', {z: len(v) for z, v in sorted(by_zone.items())})
# 单区趟参考时长（该区所有箱装 C 一趟的时长）——用于估省段
def zone_roundtrip(z):
    # C 型单区往返 O01->z->O01 带全部箱
    nf = Flight(999, [(z, by_zone[z])], 'C', data)
    return nf.duration() if nf.is_feasible() else None
# 多区构造：贪心从最大省段对开始
fid = 1
fls = []
boxes_pool = dict(by_zone)
t0 = time.time()
# 策略1：同机型多区对（C 容量大——先做 C 多区对，再做 B/A）
# 先枚举所有可行的"两区合一趟C"（容量≤80）
cands = []
zones = sorted(by_zone)
for za, zb in itertools.combinations(zones, 2):
    if len(za) != 3 or len(zb) != 3: continue
    bsa = by_zone[za]; bsb = by_zone[zb]
    mass = sum(data.boxes[b]['mass'] for b in bsa + bsb)
    vol = sum(data.boxes[b]['vol'] for b in bsa + bsb)
    if mass <= 80 and vol <= 0.25:
        fa = Flight(fid, [(za, bsa)], 'C', data)
        fb = Flight(fid+1, [(zb, bsb)], 'C', data)
        nf = Flight(fid+2, [(za, bsa), (zb, bsb)], 'C', data)
        if fa.is_feasible() and fb.is_feasible() and nf.is_feasible():
            save = (fa.duration() + fb.duration()) - nf.duration()
            cands.append((save, za, zb))
cands.sort(key=lambda x: -x[0])
print('可行C多区对: %d 最大省段: %.0fs (%s+%s)' % (len(cands), cands[0][0] if cands else 0, cands[0][1] if cands else '', cands[0][2] if cands else ''))
# 贪心使用不重叠的多区对
used_z = set(); merged = []
for save, za, zb in cands:
    if za in used_z or zb in used_z: continue
    used_z.add(za); used_z.add(zb)
    merged.append((za, zb))
print('贪心合并对: %s 总省段 %.0fs' % (merged, sum(c[0] for c in cands if (c[1], c[2]) in merged or (c[2], c[1]) in merged)))
