# -*- coding: utf-8 -*-
"""按 26 架冠军口径重建 p3_final.json（schedule/flights/sorties + 任务段数），
供 p3_figures.py 与 advanced_figures fig3_relay_tl/fig3_comm_tl 使用。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data, direct_ok
from p2_solve import Flight
from p3_gaps import flight_trajectory

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
data = Data()

AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S006', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'

# 26 架冠军中继时段（论文口径）
SORTIES = [
    {'relay': 'R01', 'pos': 'W', 't0': 1078, 't1': 6802, 'energy': 1.979},
    {'relay': 'R02', 'pos': 'E', 't0': 1406, 't1': 4074, 'energy': 1.046},
    {'relay': 'R02', 'pos': 'N', 't0': 5894, 't1': 6446, 'energy': 0.521},
]

r = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
r3 = json.load(open(os.path.join(RES, 'p3_co2.json'), encoding='utf-8'))
off = {int(k): float(v) for k, v in r3.get('offsets', {}).items()}
base = {fj['fid']: float(fj['start']) for fj in r['flights']}

# 统计各布设点任务段数（架次 x 服务区组的非直连段）
seg_count = {'W': 0, 'E': 0, 'N': 0}
for fj in r['flights']:
    f = Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
    pts, _ = flight_trajectory(f, base[f.fid] + off.get(f.fid, 0.0))
    groups = {}
    for pt in pts:
        if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
            continue
        sid = min(data.areas, key=lambda s: data.dist_ll(
            pt['lon'], pt['lat'], data.areas[s]['lon'], data.areas[s]['lat']))
        groups.setdefault(sid, 1)
    for sid in groups:
        g = AREA_POS.get(sid)
        if g:
            seg_count[g] += 1

schedule = {str(fj['fid']): {'start': fj['start'], 'return': fj['return'],
                             'uav': fj['uav']} for fj in r['flights']}
sorties = []
n1 = n2 = 0
for sg in SORTIES:
    if sg['relay'] == 'R01':
        n1 += 1
        rid = 'R1-0%d' % n1
    else:
        n2 += 1
        rid = 'R2-0%d' % n2
    sorties.append({'relay': rid, 'pos': sg['pos'], 't0': sg['t0'], 't1': sg['t1'],
                    'energy': sg['energy'],
                    'missions': ['seg_%s_%d' % (sg['pos'], i)
                                 for i in range(seg_count[sg['pos']])]})

out = {'schedule': schedule, 'flights': r['flights'], 'sorties': sorties}
json.dump(out, open(os.path.join(RES, 'p3_final.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('任务段数:', seg_count, ' 总架次:', len(r['flights']))
print('saved p3_final.json (26 架冠军口径)')