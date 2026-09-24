# -*- coding: utf-8 -*-
"""P3 位置选择：在“覆盖本组所有区域锚点”的候选中，按样本覆盖数选最佳悬停点。"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import Data, relay_link_ok, direct_ok
from p3_gaps import flight_trajectory
from p2_solve import Flight, dispatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = Data()
cov = json.load(open(os.path.join(OUT, 'p3_cov.json'), encoding='utf-8'))
area_cov = {k: [tuple(c) for c in v] for k, v in cov['area_cov'].items()}

W9 = ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']
E4 = ['S010', 'S012', 'S013', 'S014']
N1 = ['S004']

with open(os.path.join(OUT, 'p2_results.json'), encoding='utf-8') as fh:
    r = json.load(fh)
flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
           for fj in r['flights']]
base = {fj['fid']: fj['start'] for fj in r['flights']}
schedule, _ = dispatch(data, flights)
starts = {f.fid: schedule[f.fid]['start'] for f in flights}

# 每架次每区：样本清单（相对时间 -> 绝对时间）
samples_by_area = {}
for f in flights:
    pts, _ = flight_trajectory(f, starts[f.fid])
    groups = {}
    for pt in pts:
        if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
            continue
        best = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                          data.areas[s]['lon'], data.areas[s]['lat']))
        groups.setdefault(best, []).append((pt['lon'], pt['lat'], pt['z']))
    for sid, sgs in groups.items():
        samples_by_area.setdefault(sid, []).extend(sgs)


def common_cands(areas):
    inter = set(area_cov[areas[0]])
    for s in areas[1:]:
        inter &= set(area_cov[s])
    return list(inter)


def best_pos(areas, samples_map, topn=400):
    """在共同候选中选样本覆盖最多者。"""
    cands = common_cands(areas)
    # 距离排序剪枝
    def dist_c(c):
        d = 0.0
        for s in areas:
            a = data.areas[s]
            d += data.dist_ll(c[0], c[1], a['lon'], a['lat'])
        return d
    cands.sort(key=dist_c)
    cands = cands[:topn]
    total_samples = sum(len(samples_map.get(s, [])) for s in areas)
    best = None
    best_n = -1
    for c in cands:
        n = 0
        for s in areas:
            for (lon, lat, z) in samples_map.get(s, []):
                if relay_link_ok(lon, lat, z, c, data):
                    n += 1
        if n > best_n:
            best_n = n
            best = c
    print('best for %s: %s  covers %d/%d samples (%.1f%%)'
          % (areas, best, best_n, total_samples, 100.0 * best_n / max(1, total_samples)))
    return best, best_n, total_samples


for name, areas in [('W9', W9), ('E4', E4), ('N1', N1)]:
    best_pos(areas, samples_by_area)