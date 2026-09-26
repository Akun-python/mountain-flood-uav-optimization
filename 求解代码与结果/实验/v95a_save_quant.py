# -*- coding: utf-8 -*-
"""v95a：多区合并省段潜力量化——分析25架冠军每趟往返段，枚举两趟→多区一趟的省段量。"""
import sys, os, json, itertools
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m0 = eval_full(data, fls)[0]
pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}; N = {'A': 4, 'B': 2, 'C': 2}
for f in fls: pt[f.model] += f.duration()
tot = sum(pt.values())
print('总飞行 %.0fs 池(A%.0f/B%.0f/C%.0f) 平均/台 %.0f 完工%.1f' % (tot, pt['A'], pt['B'], pt['C'], tot/8, m0['makespan']))
# 每趟时长 + 区
rows = [(f.fid, f.model, f.duration(), f.route[0][0] if len(f.route)==1 else '+'.join(z for z,_ in f.route)) for f in fls]
for r in sorted(rows): print('  f%02d %s %6.0fs %s' % r)
print()
# 省段量化：同机型两趟（不同区）→ 多区一趟的预计时长
print('=== 两趟→多区 省段枚举（按省段量降序） ===')
fid_new = max(f.fid for f in fls) + 1
cands = []
for fa, fb in itertools.combinations(fls, 2):
    if fa.model != fb.model: continue
    za = [z for z, _ in fa.route]; zb = [z for z, _ in fb.route]
    union = set(za) | set(zb)
    if len(union) < 2 or len(union) > 4: continue
    boxes_all = [b for s2, bs2 in fa.route for b in bs2] + [b for s2, bs2 in fb.route for b in bs2]
    route = []
    for z in sorted(union):
        bs = [b for b in boxes_all if b.split('-')[0] == z]
        if bs: route.append((z, bs))
    nf = Flight(fid_new, route, fa.model, data)
    if not nf.is_feasible(): continue
    save = (fa.duration() + fb.duration()) - nf.duration()
    cands.append((save, fa.fid, fb.fid, fa.model, '+'.join(sorted(union)), fa.duration(), fb.duration(), nf.duration()))
cands.sort(key=lambda x: -x[0])
for c in cands[:18]:
    print('  省%5.0fs | f%02d+f%02d %s → %s : %5.0f+%5.0f → %5.0f' % (c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7]))
print('可行合并数: %d 总省段潜力(全用): %.0fs → 总飞行约 %.0fs → 平均/台 %.0f' % (
    len(cands), sum(c[0] for c in cands), tot - sum(c[0] for c in cands), (tot - sum(c[0] for c in cands))/8))
