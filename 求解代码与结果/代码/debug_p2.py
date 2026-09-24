# -*- coding: utf-8 -*-
"""P2 调试：打印种子调度的箱级时限违反详情。"""
import sys, os, json, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import (initial_flights, greedy_merge, dispatch, evaluate, Flight,
                      MODELS)

data = Data()
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', 'p1_results.json'), encoding='utf-8') as fh:
    p1 = json.load(fh)
flights0 = initial_flights(data, p1['grouping'])
flights0 = greedy_merge(data, flights0)
print('flights after merge:', len(flights0))
schedule, _ = dispatch(data, flights0)
for f in flights0:
    sch = schedule[f.fid]
    ct = min(data.boxes[b]['deadline_first'] for b in f.box_ids) if any(
        data.boxes[b]['first_batch'] for b in f.box_ids) else None
    print('f%02d model=%s start=%8.0f return=%8.0f dur=%7.0f nbox=%2d mass=%6.1f route=%s ct=%s'
          % (f.fid, f.model, sch['start'], sch['return'], f.duration(), f.nbox,
             f.total_mass, [(s, len(b)) for s, b in f.route], ct))
print()
viol = []
for fid, sch in schedule.items():
    for sid, bid, t in sch['deliveries']:
        bx = data.boxes[bid]
        if bx['first_batch'] and t > bx['deadline_first'] + 1e-6:
            viol.append((bid, 'first', t, bx['deadline_first'], fid, sid))
        if bx['type'] == '医疗物资' and t > bx['deadline_exp'] + 1e-6:
            viol.append((bid, 'med', t, bx['deadline_exp'], fid, sid))
for v in viol:
    print('VIOL', v)
print('n violations:', len(viol))
# 每个架次各交付箱的交付时刻（取最晚）
for f in flights0:
    sch = schedule[f.fid]
    dts = {sid: max((t for s, b, t in sch['deliveries'] if s == sid), default=-1) for sid, _ in f.route}
    print('f%02d 交付时刻(区:时刻) %s' % (f.fid, {k: round(v) for k, v in dts.items()}))
