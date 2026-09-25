# -*- coding: utf-8 -*-
"""按 26 架冠军口径重建 p3_final.json（schedule/flights/sorties + 任务段数），
供 p3_figures.py 与 advanced_figures fig3_relay_tl/fig3_comm_tl 使用。
v23：以修正模型 + 最小偏移 {f4:3300, f22:1000} 的实际派单为准重建。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data, direct_ok
from p2_solve import Flight, dispatch
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

# 26 架冠军中继时段（v23 最小偏移解，能耗为两阶段等效模型计算值）
SORTIES = [
    {'relay': 'R01', 'pos': 'W', 't0': 778, 't1': 6502, 'energy': 1.979},
    {'relay': 'R02', 'pos': 'E', 't0': 800, 't1': 3774, 'energy': 1.102},
    {'relay': 'R02', 'pos': 'N', 't0': 5594, 't1': 6212, 'energy': 0.450},
]

r = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
r3 = json.load(open(os.path.join(RES, 'p3_co2.json'), encoding='utf-8'))
off = {int(k): float(v) for k, v in r3.get('offsets', {}).items()}
base = {fj['fid']: float(fj['start']) for fj in r['flights']}

flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
           for fj in r['flights']]
releases = {fid: base[fid] + off.get(fid, 0.0) for fid in base}
schedule, _ = dispatch(data, flights, releases)

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

sched_out = {}
for fj in r['flights']:
    s = schedule[fj['fid']]
    sched_out[str(fj['fid'])] = {'start': s['start'], 'return': s['return'],
                                 'uav': s['uav'], 'energy': float(s['energy'])}
sorties = []
for sg in SORTIES:
    sorties.append({'relay': sg['relay'], 'pos': sg['pos'], 't0': sg['t0'], 't1': sg['t1'],
                    'energy': sg['energy'],
                    'missions': ['seg_%s_%d' % (sg['pos'], i)
                                 for i in range(seg_count[sg['pos']])]})

out = {'schedule': sched_out, 'flights': r['flights'], 'sorties': sorties,
       'makespan': max(s['return'] for s in sched_out.values())}
json.dump(out, open(os.path.join(RES, 'p3_final.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('任务段数:', seg_count, ' 总架次:', len(r['flights']))
print('makespan=%.1f saved p3_final.json (26 架冠军 v23 口径)' % out['makespan'])