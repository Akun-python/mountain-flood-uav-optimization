# -*- coding: utf-8 -*-
"""v79：电池选择策略回放——earliest-ready/latest-ready/socmax/max-ready-priority，零装箱改动压调度开销。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data, flight_critical_time, make_resources
from dqn23_enhanced import eval_full, OUTD
from core import charge_time
from audit_results import check_battery as cb
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v75_champion.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]

def dispatch_pick(data, flights, pick):
    order = sorted(enumerate(flights), key=lambda x: (flight_critical_time(data, x[1]),
                                                      -sum(data.boxes[b]['priority'] for b in x[1].box_ids), x[1].fid))
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
        if pick == 'latest':  # 最迟就绪优先（把早就绪的留给后续，减少总体等待）
            avail.sort(key=lambda b: -b['ready'])
        elif pick == 'socmax':
            avail.sort(key=lambda b: -b.get('_soc', 1.0))
        elif pick == 'earliest':
            avail.sort(key=lambda b: b['ready'])
        elif pick == 'roundrobin':
            # 轮转：选使用次数最少的电池
            avail.sort(key=lambda b: b.get('_cnt', 0))
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

print('策略    完工s     能耗     硬   违规 临界 电池 迟到')
for pick in ['earliest', 'latest', 'socmax', 'roundrobin']:
    sch, _ = dispatch_pick(data, fls, pick)
    if sch is None:
        print('%-10s 调度失败' % pick); continue
    m, s2, v, nc = eval_full(data, fls, sch)
    vb = cb(data, sch, fls)
    print('%-10s %8.1f %8.2f %5s %4d %4d %4d %5.1f' % (pick, m['makespan'], m['energy'], m['hard_ok'], v, nc, len(vb), m.get('tardy_w', 0)))
