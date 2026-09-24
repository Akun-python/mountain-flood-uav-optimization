# -*- coding: utf-8 -*-
"""v9v C 链与 A 链实际槽位。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'code'))
sys.stdout.reconfigure(encoding='utf-8')
import v9v_q3_final as v9v
from v9v_q3_final import Flight, dispatch, data, OUT

r = json.load(open(os.path.join(OUT, 'p2_results.json'), encoding='utf-8'))
base = {fj['fid']: fj['start'] for fj in r['flights']}
flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
           for fj in r['flights']]
flights = v9v.build(flights)
rel_all = {f.fid: max(0.0, base.get(f.fid, 0.0) + v9v.FLOORS.get(f.fid, 0.0)) for f in flights}
sch, _ = dispatch(data, flights, rel_all)
for f in sorted(flights, key=lambda x: sch[x.fid]['start']):
    if f.model in ('A', 'B', 'C'):
        print('f%-3d %s start=%6.0f ret=%6.0f uav=%s bat=%-4s %s' %
              (f.fid, f.model, sch[f.fid]['start'], sch[f.fid]['return'],
               sch[f.fid]['uav'], sch[f.fid]['battery'],
               [(s, len(bs)) for s, bs in f.route]))
for fid in (6, 10, 7, 8, 9):
    for sid, bid, t in sch[fid]['deliveries']:
        if sid in ('S003', 'S008', 'S015', 'S011', 'S005', 'S006'):
            print('f%-3d %s t=%.1f' % (fid, bid, t))