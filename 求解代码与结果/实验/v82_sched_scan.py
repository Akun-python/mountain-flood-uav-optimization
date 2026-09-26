# -*- coding: utf-8 -*-
"""v82：调度策略空间扫描——架次排序(EDF/时长/机型/池轮转) × 电池选择(early/late/socmax/socmin/rr)。
权威验证链：dispatch_pick → evaluate.hard_ok(硬时限+区一致+覆盖) + check_battery(电池0违规) 双过才算数。
关键：完工 6571.4 是 dispatch_compliant(固定策略)下的值——策略空间从未被系统探索！"""
import sys, os, json, itertools
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data, flight_critical_time, make_resources, evaluate
from dqn23_enhanced import OUTD
from core import charge_time
from audit_results import check_battery as cb
data = Data()

def load(p):
    d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]

def dispatch_strategy(data, flights, sortk, pick):
    """sortk: 'edf'/'dur_desc'/'dur_asc'/'grp'/'pool_rotate'；pick: 电池选择。"""
    order = list(enumerate(flights))
    if sortk == 'edf':
        order.sort(key=lambda x: (flight_critical_time(data, x[1]),
                                  -sum(data.boxes[b]['priority'] for b in x[1].box_ids), x[1].fid))
    elif sortk == 'dur_desc':
        order.sort(key=lambda x: (-x[1].duration(), x[1].fid))
    elif sortk == 'dur_asc':
        order.sort(key=lambda x: (x[1].duration(), x[1].fid))
    elif sortk == 'grp':
        order.sort(key=lambda x: (x[1].model, flight_critical_time(data, x[1]), x[1].fid))
    elif sortk == 'pool_rotate':
        # 池内轮转：每个机型内部按池负载贡献排序（尽量均分充电压力）
        pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}
        for f in flights: pt[f.model] += f.duration()
        order.sort(key=lambda x: (x[1].model, -x[1].duration(), x[1].fid))
    uavs, bats = make_resources(data, None)
    schedule = {}
    for _, f in order:
        model = f.model
        cu = sorted([(u['ready'], u) for u in uavs.values() if u['model'] == model])
        if not cu: return None, None
        uav = cu[0][1]
        cbats = [b for b in bats.values() if b['model'] == model]
        start = max(0.0, uav['ready'])
        for _ in range(8):
            avail = [b for b in cbats if b['ready'] <= start + 1e-6]
            if not avail:
                start = max(start, min(b['ready'] for b in cbats)); continue
            if uav['ready'] > start + 1e-6:
                start = uav['ready']; continue
            break
        avail = [b for b in cbats if b['ready'] <= start + 1e-6]
        if not avail: return None, None
        if pick == 'early': avail.sort(key=lambda b: b['ready'])
        elif pick == 'late': avail.sort(key=lambda b: -b['ready'])
        elif pick == 'socmax': avail.sort(key=lambda b: -b.get('_soc', 1.0))
        elif pick == 'socmin': avail.sort(key=lambda b: b.get('_soc', 1.0))
        elif pick == 'rr': avail.sort(key=lambda b: b.get('_cnt', 0))
        bat = avail[0]
        bat['_cnt'] = bat.get('_cnt', 0) + 1
        uav['ready'] = start + f.duration()
        soc_end = 1.0 - f.energy() / data.uav_types[model]['E_use']
        bat['ready'] = start + f.duration() + charge_time(soc_end, data.batteries[model]['T_full'])
        bat['_soc'] = soc_end
        schedule[f.fid] = {'uav': [u for u, d in uavs.items() if d is uav][0],
                           'battery': [b for b, d in bats.items() if d is bat][0],
                           'start': start, 'return': start + f.duration(),
                           'energy': f.energy(), 'deliveries': f.delivery_times(start),
                           'route': [(s, b) for s, b in f.route]}
    return schedule, uavs

fls = load('p2v75_champion.json')
sorts = ['edf', 'dur_desc', 'dur_asc', 'grp', 'pool_rotate']
picks = ['early', 'late', 'socmax', 'socmin', 'rr']
res = []
for sk, pk in itertools.product(sorts, picks):
    sch, _ = dispatch_strategy(data, fls, sk, pk)
    if sch is None: continue
    m = evaluate(data, fls, sch)
    vb = cb(data, sch, fls)
    if not m['hard_ok'] or len(vb) > 0:
        res.append((sk, pk, m['makespan'], None, None, len(vb)))
        continue
    res.append((sk, pk, m['makespan'], m['energy'], m['hard_ok'], len(vb)))
print('排序×电池   完工s     能耗    硬    电池')
res.sort(key=lambda r: (r[2] if r[3] is not None else 1e18))
for sk, pk, mk, en, hard, nvb in res:
    print('%-10s×%-6s %8.1f %8.2f %5s %4d' % (sk, pk, mk, en if en is not None else -1, hard if hard is not None else 'X', nvb))
