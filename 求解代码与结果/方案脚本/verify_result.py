# -*- coding: utf-8 -*-
"""对版本结果 JSON 做独立实证校验（不信任求解器自报指标）。"""
import sys, os, json, io
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'code'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate, flight_critical_time

data = Data()
ver = sys.argv[1] if len(sys.argv) > 1 else 'v2'
with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ver, 'results.json'),
             encoding='utf-8') as fh:
    r = json.load(fh)

flights = []
for fj in r['flights']:
    f = Flight(fj['fid'], [(s, b) for s, b in fj['route']], fj['model'], data)
    flights.append(f)

# 1) 全箱覆盖唯一性
allb = [b for f in flights for b in f.box_ids]
dup = len(allb) - len(set(allb))
missing = [b for b in data.boxes if b not in set(allb)]
print('boxes: total=%d dup=%d missing=%d' % (len(allb), dup, len(missing)))

# 2) 架次可行
bad = [f.fid for f in flights if not f.is_feasible()]
print('infeasible flights:', bad if bad else '无')

# 3) 时限：重算交付时刻并核对
schedule, _ = dispatch(data, flights)
met = evaluate(data, flights, schedule)
print('metrics(重算): flights=%d makespan=%.1f energy=%.2f tardy_w=%.2f hard_ok=%s'
      % (met['flights'], met['makespan'], met['energy'], met['tardy_w'], met['hard_ok']))
rpt = {k: (round(v, 4) if isinstance(v, float) else v)
       for k, v in met.items() if k != 'box_time'}
print('report(原):', rpt)
# 独立时限核查
bad_ddl = []
for fid, sch in schedule.items():
    for sid, bid, t in sch['deliveries']:
        bx = data.boxes[bid]
        if bx['first_batch'] and t > bx['deadline_first'] + 1e-6:
            bad_ddl.append((bid, 'first', t, bx['deadline_first']))
        if bx['type'] == '医疗物资' and t > bx['deadline_exp'] + 1e-6:
            bad_ddl.append((bid, 'med', t, bx['deadline_exp']))
print('硬时限违反:', bad_ddl if bad_ddl else '无')
# 资源核查：电池数量与无人机数量
used_uav = {sch['uav'] for sch in schedule.values()}
used_bat = {sch['battery'] for sch in schedule.values()}
print('used uav: %d / 8 | used batteries: %d (A%d B%d C%d)'
      % (len(used_uav), len(used_bat),
         sum(1 for b in used_bat if b.startswith('A')),
         sum(1 for b in used_bat if b.startswith('B')),
         sum(1 for b in used_bat if b.startswith('C'))))