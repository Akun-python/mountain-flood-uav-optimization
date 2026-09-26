# -*- coding: utf-8 -*-
"""v84：多区合并算子验证——同机型不同区的两趟 → 合并多区趟（省 O01 往返重复段）。
目标：C池 6→5 趟（或 B 池），池负载下降 → 完工突破 6571.4。"""
import sys, os, json, itertools
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v75_champion.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m0 = eval_full(data, fls)[0]
print('起点: %d架 mk=%.1f en=%.2f' % (len(fls), m0['makespan'], m0['energy']))
print('趟结构:', [(f.fid, f.model, [s for s, _ in f.route]) for f in fls])
# 多区合并候选：同机型、单区、不同区 的两趟合并
from p2_solve import clone_flights
best = None
for fa, fb in itertools.combinations(fls, 2):
    if fa.model != fb.model: continue
    if len(fa.route) != 1 or len(fb.route) != 1: continue
    za, zb = fa.route[0][0], fb.route[0][0]
    if za == zb: continue
    # 合并为多区趟：O01->za->zb->O01（按两趟箱合并）
    boxes_a = list(fa.route[0][1]); boxes_b = list(fb.route[0][1])
    # 尝试两种段序
    merged = []
    for seq in [(za, zb), (zb, za)]:
        s1, s2 = seq
        zset = set()
        for b in boxes_a + boxes_b:
            zset.add(b.split('-')[0])
        if not (zset <= {s1, s2}):
            continue
        route = [(s1, [b for b in boxes_a + boxes_b if b.split('-')[0] == s1]),
                 (s2, [b for b in boxes_a + boxes_b if b.split('-')[0] == s2])]
        route = [(s, bs) for s, bs in route if bs]
        nf = Flight(max(x.fid for x in fls) + 1, route, fa.model, data)
        if not nf.is_feasible():
            continue
        merged.append(nf)
        break
    if not merged:
        continue
    nfl = [f for f in fls if f.fid not in (fa.fid, fb.fid)] + merged
    mm, ss, vv, nn = eval_full(data, nfl)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']:
        continue
    gain = m0['makespan'] - mm['makespan']
    print('合并 %d(%s)+%d(%s) → %d架 mk=%.1f en=%.2f Δmk=%+.1f' % (
        fa.fid, za, fb.fid, zb, len(nfl), mm['makespan'], mm['energy'], -gain))
    if best is None or mm['makespan'] < best[0]:
        best = (mm['makespan'], mm['energy'], nfl, (fa.fid, za, fb.fid, zb))
if best:
    print('★最佳: 合并%s → %d架 mk=%.1f en=%.2f' % (best[3], len(best[2]), best[0], best[1]))
    json.dump({'best': {'makespan': best[0], 'energy': best[1], 'flights': len(best[2])},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in best[2]]},
              open(os.path.join(OUTD, 'p2v84_multizone.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
else:
    print('无可行的多区合并')
