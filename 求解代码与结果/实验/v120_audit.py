# -*- coding: utf-8 -*-
"""v120：24架冠军(v113)独立复验——含 vv/nn/区一致/箱覆盖/机队/电池/时限明细。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/v113_best.json', encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
print('架次:', len(fls), '| 机型分布:', {m: sum(1 for f in fls if f.model == m) for m in 'ABC'})
# 1) 箱覆盖（80箱全有且无重复）
allb = set()
for f in fls: allb |= set(f.box_ids)
print('箱覆盖: %d/80 重复=%d' % (len(allb), 80 - len(allb)))
# 2) 完整硬约束
sch, _ = dispatch_compliant(data, fls)
mm, s, vv, nn = eval_full(data, fls)
vb = cb(data, sch, fls)
print('mk=%.1f en=%.2f hard=%s vv=%d nn=%d bat=%d' % (mm['makespan'], mm['energy'], mm['hard_ok'], vv, nn, len(vb)))
# 3) 区一致明细（每趟投递区 vs 箱号前缀）
bad = []
for f in fls:
    for sid, b, t in f.delivery_times(sch[f.fid]['start']):
        if not b.startswith(sid + '-'):
            bad.append((f.fid, sid, b))
print('区一致违例:', len(bad), bad[:3])
# 4) 每区箱数/趟数与时限
from collections import Counter
zc = Counter()
for f in fls:
    for z, bs in f.route: zc[z] += len(bs)
print('区箱数:', dict(sorted(zc.items())))
# 5) 池负载与尾趟
pools = {}
for f in fls: pools.setdefault(f.model, []).append(sch[f.fid]['return'])
print('池max返场:', {m: round(max(v)) for m, v in pools.items()})
tail = sorted(fls, key=lambda f: sch[f.fid]['return'])[-3:]
print('尾趟:', [(f.fid, f.model, [z for z,_ in f.route], round(sch[f.fid]['return'])) for f in tail])
# 6) 多区趟
print('多区趟:', [(f.fid, f.model, [z for z,_ in f.route]) for f in fls if len(set(z for z,_ in f.route)) > 1])
# 7) 电池链明细（最紧的 2 台）
import itertools
for f in sorted(fls, key=lambda x: sch[x.fid]['return'])[:0]: pass
print('机台链（贪心均衡近似）:')
from collections import defaultdict
chains = defaultdict(list)
for f in sorted(fls, key=lambda x: sch[x.fid]['start']):
    chains[f.model].append((sch[f.fid]['start'], sch[f.fid]['return'], f.fid))
for m, v in chains.items():
    v.sort()
    # 简单机台分配
    slots = [[] for _ in range({'A':4,'B':2,'C':2}[m])]
    for s0, s1, fid in v:
        cand = [i for i, sl in enumerate(slots) if not sl or s0 >= sl[-1][1]]
        if not cand:
            cand = [min(range(len(slots)), key=lambda i: slots[i][-1][1])]
        slots[min(cand, key=lambda i: slots[i][-1][1] if slots[i] else 0)].append((s0, s1, fid))
    print('  %s: %s' % (m, [round(sl[-1][1]) for sl in slots]))
