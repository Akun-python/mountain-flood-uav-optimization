# -*- coding: utf-8 -*-
"""v27 电池周转合规审计/修复：dispatch 的电池起充时刻应为架次"返回 O01"（含交接）。
原 dispatch 用 bat_end = start+prep+flight_time（漏 handover）——电池过早可用（宽松）。
本脚本以正确口径（bat_end = start+duration）重放现有解，报告每解电池违规与完工变化。
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data, charge_time
from p2_solve import Flight, flight_critical_time, make_resources

data = Data()


def dispatch_correct(data, flights, limit=None):
    """同 p2_solve.dispatch，但电池返场起充时刻 = start + duration（含 handover）。"""
    order = sorted(enumerate(flights), key=lambda x: (flight_critical_time(data, x[1]),
                                                      -sum(data.boxes[b]['priority'] for b in x[1].box_ids),
                                                      x[1].fid))
    uavs, bats = make_resources(data, limit)
    schedule = {}
    for _, f in order:
        model = f.model
        cand_uavs = [(u['ready'], u) for u in uavs.values() if u['model'] == model]
        if not cand_uavs:
            return None, None
        cand_uavs.sort()
        uav = cand_uavs[0][1]
        cand_bats = [b for b in bats.values() if b['model'] == model]
        start = max(0.0, uav['ready'])
        avail = [b for b in cand_bats if b['ready'] <= start + f.prep]
        if not avail:
            earliest = min(b['ready'] for b in cand_bats)
            start = max(start, earliest - f.prep)
            avail = [b for b in cand_bats if b['ready'] <= start + f.prep]
            if not avail:
                return None, None
        while uav['ready'] > start + 1e-9:
            start = uav['ready']
            avail = [b for b in cand_bats if b['ready'] <= start + f.prep]
            if not avail:
                earliest = min(b['ready'] for b in cand_bats)
                start = max(start, earliest - f.prep)
                avail = [b for b in cand_bats if b['ready'] <= start + f.prep]
                if not avail:
                    return None, None
        bat = avail[0]
        # 无人机：整个架次(duration)后 ready
        uav['ready'] = start + f.duration()
        # 电池：返场(含handover)+充电 后 ready
        bat['ready'] = start + f.duration() + charge_time(
            1.0 - f.energy() / data.uav_types[model]['E_use'], data.batteries[model]['T_full'])
        deliveries = f.delivery_times(start)
        schedule[f.fid] = {'uav': [u for u, d in uavs.items() if d is uav][0],
                           'battery': [b for b, d in bats.items() if d is bat][0],
                           'start': start, 'return': start + f.duration(),
                           'energy': f.energy(), 'deliveries': deliveries,
                           'route': [(s, b) for s, b in f.route]}
    return schedule, uavs


def load(src):
    d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '结果',
                                    '进化_v25', src), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d['solution']]


def audit(name, src):
    fls = load(src)
    sch, _ = dispatch_correct(data, fls)
    if sch is None:
        print('%-28s| 正确口径: 调度失败（无可行电池时序）' % name)
        return
    makespan = max(s['return'] for s in sch.values())
    # 电池违规检测
    from collections import defaultdict
    per = defaultdict(list)
    for fid, s in sch.items():
        per[s['battery']].append((s['start'], s['return'], s['energy'], fid))
    viol = 0
    for bat, rl in per.items():
        model = bat.split('-')[0]
        rl.sort()
        for i in range(len(rl) - 1):
            st, ret, e, fid = rl[i]
            soc = max(0.0, 1.0 - e / data.uav_types[model]['E_use'])
            ch = charge_time(soc, data.batteries[model]['T_full'])
            if rl[i+1][0] < ret + ch - 1e-6:
                viol += 1
    print('%-28s| 正确口径: %d 架 makespan=%.1f 电池违规=%d' % (name, len(fls), makespan, viol))


def main():
    for name, src in [('v25j(24架能耗)', 'p2v25j_dual.json'),
                      ('v25b(28架完工)', 'p2v25b_compress26.json'),
                      ('v25i(25架)', 'p2v25i_merge.json'),
                      ('tabu续搜', 'p2v25g_tabu.json')]:
        try:
            audit(name, src)
        except FileNotFoundError:
            print('%-28s| (无此文件)' % name)


if __name__ == '__main__':
    main()