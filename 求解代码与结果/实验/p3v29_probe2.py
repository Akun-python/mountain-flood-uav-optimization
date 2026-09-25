# -*- coding: utf-8 -*-
"""快速对比：原/新位置往返时间 + E/N/W 合并且检查（B2 侦察第二步）。"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '代码'))
from core import Data, relay_link_ok, relay_mission_time, direct_ok
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant
from p3_gaps import flight_trajectory

data = Data()
ORIG = {'W': (109.2103, 23.047134, 676.5), 'E': (109.268918, 23.012732, 650.0),
        'N': (109.234314, 23.059248, 600.0)}
NEW = {'W': (109.206749, 23.044585, 710.8), 'E': (109.268187, 23.003900, 675.5),
       'N': (109.245951, 23.059755, 565.8)}
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
for g, p in ORIG.items():
    to, tb, tt = relay_mission_time(p[0], p[1], p[2], data)
    print('原 %s: 往返 %.0f s' % (g, tt))
for g, p in NEW.items():
    to, tb, tt = relay_mission_time(p[0], p[1], p[2], data)
    print('新 %s: 往返 %.0f s' % (g, tt))

d = json.load(open(os.path.join(OUTD, 'p2v28_compliant_makespan.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in d['solution']]
sch, _ = dispatch_compliant(data, fls)
base = {fid: sch[fid]['start'] for fid in sch}
by_area = {}
for f in fls:
    pts, _ = flight_trajectory(f, base[f.fid])
    for pt in pts:
        if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
            continue
        best = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                          data.areas[s]['lon'], data.areas[s]['lat']))
        by_area.setdefault(best, []).append((pt['lon'], pt['lat'], pt['z']))
W = [p for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']
     for p in by_area.get(s, [])]
E = [p for s in ['S010', 'S012', 'S013', 'S014'] for p in by_area.get(s, [])]
N = by_area.get('S004', [])
for g, pos in [('E', NEW['E']), ('N', NEW['N'])]:
    print('位置 %s: E覆盖 %d/%d, N覆盖 %d/%d' % (
        g, sum(1 for p in E if relay_link_ok(*p, pos, data)), len(E),
        sum(1 for p in N if relay_link_ok(*p, pos, data)), len(N)))
for g, pos in [('W', NEW['W']), ('E', NEW['E'])]:
    print('位置 %s: W覆盖 %d/%d, E覆盖 %d/%d' % (
        g, sum(1 for p in W if relay_link_ok(*p, pos, data)), len(W),
        sum(1 for p in E if relay_link_ok(*p, pos, data)), len(E)))
# 三位置全集并成 2 个位置的可行性：找一对 (p1,p2) 使 W/E/N 全覆盖
for g1, p1 in NEW.items():
    for g2, p2 in NEW.items():
        if g1 >= g2:
            continue
        cW = max(sum(1 for p in W if relay_link_ok(*p, p1, data)),
                 sum(1 for p in W if relay_link_ok(*p, p2, data)))
        cE = max(sum(1 for p in E if relay_link_ok(*p, p1, data)),
                 sum(1 for p in E if relay_link_ok(*p, p2, data)))
        cN = max(sum(1 for p in N if relay_link_ok(*p, p1, data)),
                 sum(1 for p in N if relay_link_ok(*p, p2, data)))
        print('2位置 %s+%s: W %d/%d, E %d/%d, N %d/%d' % (g1, g2, cW, len(W), cE, len(E), cN, len(N)))
