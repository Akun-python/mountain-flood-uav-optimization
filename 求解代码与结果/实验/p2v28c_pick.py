# -*- coding: utf-8 -*-
"""v28c 24架解在严格口径下电池选择策略试验：soc最高优先 vs 最早就绪，看迟到是否可消。"""
import sys, os, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data, charge_time
from p2_solve import Flight, flight_critical_time, make_resources, evaluate
from p2v28_compliant import check_battery

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def load(src):
    d = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d['solution']]


def dispatch_pick(data, flights, pick='earliest'):
    """pick='earliest'=最早就绪先选; 'socmax'=SOC最高先选。电池须 start 时就绪。"""
    order = sorted(enumerate(flights), key=lambda x: (flight_critical_time(data, x[1]),
                                                      -sum(data.boxes[b]['priority'] for b in x[1].box_ids),
                                                      x[1].fid))
    uavs, bats = make_resources(data, None)
    schedule = {}
    for _, f in order:
        model = f.model
        cu = sorted([(u['ready'], u) for u in uavs.values() if u['model'] == model])
        uav = cu[0][1]
        cb = [b for b in bats.values() if b['model'] == model]
        start = max(0.0, uav['ready'])
        for _ in range(8):
            avail = [b for b in cb if b['ready'] <= start + 1e-6]
            if not avail:
                start = max(start, min(b['ready'] for b in cb))
                continue
            if uav['ready'] > start + 1e-6:
                start = uav['ready']
                continue
            break
        avail = [b for b in cb if b['ready'] <= start + 1e-6]
        if not avail:
            return None, None
        if pick == 'socmax':
            def soc_of(b):
                return b.get('_soc', 1.0)
            avail.sort(key=lambda b: (-soc_of(b), b['ready']))
        bat = avail[0]
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


def main():
    fls = load('p2v25j_dual.json')
    for pick in ('earliest', 'socmax'):
        sch, _ = dispatch_pick(data, fls, pick)
        if sch is None:
            print('%-10s | 失败' % pick); continue
        m = evaluate(data, fls, sch)
        v = check_battery(data, sch, fls)
        print('%-10s | mk=%.1f en=%.2f hard=%s tardy=%.2f 电池违规=%d' % (
            pick, m['makespan'], m['energy'], m['hard_ok'], m['tardy_w'], len(v)))


if __name__ == '__main__':
    main()