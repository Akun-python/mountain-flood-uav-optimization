# -*- coding: utf-8 -*-
"""重算三个中继布设点的接入链路余量统计（基于最新 p3_final.json）。

采样与分组约定与 p3_construct.py 完全一致：对每个架次按轨迹展开采样，
直连点跳过，非直连点归入最近服务区；若该服务区有固定中继位置（AREA_POS），
该任务段即由该位置保障。统计口径：接入链路余量 = 116 - L(uav, 中继)。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data, direct_ok, path_loss
from p2_solve import Flight
from p3_gaps import flight_trajectory

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
POS = {'W': (109.2103, 23.047134, 676.5),
       'E': (109.276017, 23.019401, 542.3),
       'N': (109.238171, 23.077841, 496.1)}
AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'

data = Data()
r = json.load(open(os.path.join(OUT, 'p3_final.json'), encoding='utf-8'))
sch = r['schedule']

stats = {g: [] for g in POS}
n_grouped = 0
for fj in r['flights']:
    f = Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
    pts, _ = flight_trajectory(f, sch[str(fj['fid'])]['start'])
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
        lo, la, zz = POS[g]
        for pt in sgs:
            stats[g].append(116.0 - path_loss(pt['lon'], pt['lat'], pt['z'], lo, la, zz, data))
        n_grouped += len(sgs)

res = {}
for g in 'WEN':
    ms = stats[g]
    if ms:
        res[g] = {'n': len(ms), 'min': round(min(ms), 1), 'avg': round(sum(ms) / len(ms), 1),
                  'samples': [round(m, 2) for m in ms]}
    else:
        res[g] = {'n': 0, 'min': None, 'avg': None, 'samples': []}
for g in 'WEN':
    s = res[g]
    print('%s: n=%d min=%s avg=%s' % (g, s['n'], s['min'], s['avg']))
with open(os.path.join(OUT, 'p3_margins.json'), 'w', encoding='utf-8') as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1)
print('saved p3_margins.json')