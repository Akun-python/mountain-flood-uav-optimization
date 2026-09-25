# -*- coding: utf-8 -*-
"""接入链路余量统计（兼容进化管线）：读 p2_results.json + p3_co2.json 偏移，
对全部需中继采样点统计各布设点的接入余量（116 - path_loss）。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data, direct_ok, path_loss
from p2_solve import Flight
from p3_gaps import flight_trajectory

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
POS = {'W': (109.2103, 23.047134, 676.5),
       'E': (109.268918, 23.012732, 650.0),
       'N': (109.234314, 23.059248, 600.0)}
AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'

data = Data()
r = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
r3 = json.load(open(os.path.join(RES, 'p3_co2.json'), encoding='utf-8'))
off = {int(k): float(v) for k, v in r3.get('offsets', {}).items()}
base = {fj['fid']: float(fj['start']) for fj in r['flights']}

stats = {g: [] for g in POS}
seg_count = {'W': 0, 'E': 0, 'N': 0}
n_relay = 0
for fj in r['flights']:
    f = Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
    pts, _ = flight_trajectory(f, base[f.fid] + off.get(f.fid, 0.0))
    groups = {}
    for pt in pts:
        if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
            continue
        sid = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                          data.areas[s]['lon'], data.areas[s]['lat']))
        groups.setdefault(sid, []).append(pt)
    for sid, sgs in groups.items():
        g = AREA_POS.get(sid)
        if g is None:
            continue
        seg_count[g] += 1
        lo, la, zz = POS[g]
        for pt in sgs:
            stats[g].append(116.0 - path_loss(pt['lon'], pt['lat'], pt['z'], lo, la, zz, data))
            n_relay += 1

res = {}
for g in 'WEN':
    ms = stats[g]
    res[g] = {'n': len(ms), 'min': round(min(ms), 2) if ms else None,
              'avg': round(sum(ms) / len(ms), 2) if ms else None,
              'below1': sum(1 for m in ms if m < 1.0) if ms else 0,
              'below2': sum(1 for m in ms if m < 2.0) if ms else 0,
              'segments': seg_count[g],
              'samples': [round(m, 2) for m in ms]}
for g in 'WEN':
    s = res[g]
    print('%s: n=%d min=%.2f avg=%.2f below1=%d below2=%d'
          % (g, s['n'], s['min'] or 0, s['avg'] or 0, s['below1'], s['below2']))
print('total relay samples:', n_relay)
with open(os.path.join(RES, 'p3_margins.json'), 'w', encoding='utf-8') as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1)
print('saved p3_margins.json')