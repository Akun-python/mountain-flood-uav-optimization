# -*- coding: utf-8 -*-
"""v25 偏移后派单的接入链路余量统计（p3_margins 互斥归属口径）。
输入：p2_results.json（route）+ p3v25_final.json（偏移后 start）。
输出：results/p3_margins.json（覆盖 sampling 数/最紧/平均余量）+ 打印。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data, direct_ok, path_loss
from p2_solve import Flight
from p3_gaps import flight_trajectory

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
EVO = os.path.join(HERE, '..', '结果', '进化_v25')
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
p2 = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
fin = json.load(open(os.path.join(EVO, 'p3v25_final.json'), encoding='utf-8'))
starts = {r['fid']: r['start'] for r in fin['rows']}
fls = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
       for fj in p2['flights']]
print('flights=%d starts=%d' % (len(fls), len(starts)))

stats = {g: [] for g in POS}
n_grouped = 0
for f in fls:
    if f.fid not in starts:
        continue
    pts, _ = flight_trajectory(f, starts[f.fid])
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
    res[g] = {'n': len(ms),
              'min': round(min(ms), 1) if ms else None,
              'avg': round(sum(ms) / len(ms), 1) if ms else None,
              'samples': [round(m, 2) for m in ms]}
    print('%s: n=%d min=%s avg=%s' % (g, res[g]['n'], res[g]['min'], res[g]['avg']))
print('需中继采样合计(互斥归属) = %d' % n_grouped)
json.dump(res, open(os.path.join(RES, 'p3_margins.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved p3_margins.json')