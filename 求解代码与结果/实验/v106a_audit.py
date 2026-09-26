# -*- coding: utf-8 -*-
"""v106a（修复）：多区架次 × 中继覆盖归属 → 问题四分区硬约束判定。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
import p3_co2
from p2_solve import Flight
from dqn23_enhanced import OUTD
data = p3_co2.data
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
print('== 多区架次（硬约束：同趟区同组）==')
for f in fls:
    zones = [z for z, _ in f.route]
    if len(zones) > 1:
        print('  f%02d %s: %s' % (f.fid, f.model, zones))
from collections import Counter
zn = Counter()
for f in fls:
    for z, bs in f.route: zn[z] += len(bs)
print('== 每区直连/中继归属（悬停点静态判定）==')
for z in sorted(zn):
    a = data.areas[z]
    pos = (a['lon'], a['lat'], a['alt'] + 30.0)
    d_ok = p3_co2.direct_ok(pos[0], pos[1], pos[2], data)
    which = []
    for g in ['W', 'E', 'N']:
        rp = p3_co2.POS_OF[g]
        if p3_co2.relay_link_ok(pos[0], pos[1], pos[2], rp, data) and p3_co2.relay_backhaul_ok(rp, data):
            which.append(g)
    print('  %s: 直连=%s 中继=%s 箱=%d' % (z, 'Y' if d_ok else 'N', which, zn[z]))

