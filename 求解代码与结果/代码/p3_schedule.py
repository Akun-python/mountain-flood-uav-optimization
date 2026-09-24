# -*- coding: utf-8 -*-
"""问题三：中继架次调度——任务聚类、悬停点选择、时间线并发分析"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import Data, relay_mission_time, relay_mission_energy, charge_time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = Data()

with open(os.path.join(OUT, 'p3_missions.json'), encoding='utf-8') as fh:
    missions = json.load(fh)

# 1) 聚类：共享候选悬停点的任务连边
pos_sets = [set(tuple(c) for c in m['pos_cands']) for m in missions]
n = len(missions)
parent = list(range(n))

def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb

# 稠密图太大（57x57 集合交集可接受）
for i in range(n):
    for j in range(i + 1, n):
        if pos_sets[i] & pos_sets[j]:
            union(i, j)

clusters = {}
for i in range(n):
    clusters.setdefault(find(i), []).append(i)
print('clusters:', len(clusters))
for cid, idx in clusters.items():
    areas = sorted(set(missions[i]['area'] for i in idx))
    t0 = min(missions[i]['t0'] for i in idx)
    t1 = max(missions[i]['t1'] for i in idx)
    print('  cluster %s areas=%s t=[%.0f, %.0f] n=%d' % (cid, areas, t0, t1, len(idx)))

# 2) 每簇选择一个共同悬停点（各任务候选的交集）
cluster_plan = []
for cid, idx in clusters.items():
    inter = pos_sets[idx[0]].copy()
    for i in idx[1:]:
        inter &= pos_sets[i]
        if not inter:
            break
    # 若无交集，按出现次数选点
    if not inter:
        from collections import Counter
        cnt = Counter()
        for i in idx:
            for c in pos_sets[i]:
                cnt[c] += 1
        inter = {c for c, k in cnt.most_common(5)}
    # 选与簇内任务位置最近的点
    best = None
    best_d = 1e18
    for c in inter:
        d = 0.0
        for i in idx:
            a = data.areas[missions[i]['area']]
            d += data.dist_ll(c[0], c[1], a['lon'], a['lat'])
        if d < best_d:
            best_d = d
            best = c
    cluster_plan.append({'cluster': cid, 'idx': idx, 'pos': list(best),
                         'areas': sorted(set(missions[i]['area'] for i in idx)),
                         't0': min(missions[i]['t0'] for i in idx),
                         't1': max(missions[i]['t1'] for i in idx)})
    print('plan cluster %s pos=(%.5f,%.5f,z=%.0f) t=[%.0f,%.0f]'
          % (cid, best[0], best[1], best[2], cluster_plan[-1]['t0'], cluster_plan[-1]['t1']))

# 3) 时间线并发：把每簇的“服务需求”展开为（簇内任务窗口并集）
#    简化：每簇一个连续窗口 [t0, t1]（含往返转场）
intervals = [(p['t0'], p['t1'], p['cluster'], p['pos']) for p in cluster_plan]
events = []
for (t0, t1, cid, pos) in intervals:
    events.append((t0, 1, cid))
    events.append((t1, -1, cid))
events.sort()
active = set()
maxconc = 0
for t, dt, cid in events:
    if dt == 1:
        active.add(cid)
    else:
        active.discard(cid)
    maxconc = max(maxconc, len(active))
print('\nmax concurrent cluster windows:', maxconc, '(需中继无人机数)')

json.dump(cluster_plan, open(os.path.join(OUT, 'p3_clusters.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)