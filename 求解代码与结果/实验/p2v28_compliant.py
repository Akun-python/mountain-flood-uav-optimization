# -*- coding: utf-8 -*-
"""v28 合规电池口径重求解（P2，严格合规）：
权威 dispatch_compliant()：电池最早就绪 = 架次返回(start+duration, 含handover) + charge_time(1-e/E_use)。
独立 check_battery() 逐电池串验证 next.start >= return + charge。
1) 用 compliant dispatch 重调度 v25b(28架) / v25j(24架) 报告合规指标；
2) 合规口径下重做完工压缩(28架起点)与能耗合并(24架起点) -> 保存 p2v28_compliant_*.json(含solution)。
"""
import sys, os, json, copy, math
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data, charge_time
from p2_solve import Flight, flight_critical_time, make_resources, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def dispatch_compliant(data, flights, limit=None, releases=None):
    """正确电池口径的 EDF 调度（严格：电池须在架次"开始时刻 start"前就绪，即 ready<=start）。
    约束：start 同时满足 (a) 无人机 ready(上一架次+duration) (b) 所分配电池该趟就绪
    (上一趟 return+充电 <= start)。电池最早就绪 = return+charge_time(soc)。
    """
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
        rel = releases.get(f.fid, 0.0) if releases else 0.0
        start = max(rel, uav['ready'])
        for _ in range(8):  # 电池-无人机联合等待迭代
            avail = [b for b in cand_bats if b['ready'] <= start + 1e-6]
            if not avail:
                earliest = min(b['ready'] for b in cand_bats)
                start = max(start, earliest)
                continue
            if uav['ready'] > start + 1e-6:
                start = uav['ready']
                continue
            break
        else:
            return None, None
        avail = [b for b in cand_bats if b['ready'] <= start + 1e-6]
        if not avail:
            return None, None
        bat = avail[0]
        uav['ready'] = start + f.duration()
        soc_end = 1.0 - f.energy() / data.uav_types[model]['E_use']
        bat['ready'] = start + f.duration() + charge_time(soc_end, data.batteries[model]['T_full'])
        deliveries = f.delivery_times(start)
        schedule[f.fid] = {'uav': [u for u, d in uavs.items() if d is uav][0],
                           'battery': [b for b, d in bats.items() if d is bat][0],
                           'start': start, 'return': start + f.duration(),
                           'energy': f.energy(), 'deliveries': deliveries,
                           'route': [(s, b) for s, b in f.route]}
    return schedule, uavs


def check_battery(data, schedule, flights):
    """独立逐电池串验证：同一电池串内 next.start >= return + charge_time(1-e/E_use)。
    return 必须是 start+duration（含handover）。返回违规列表。"""
    viol = []
    per = defaultdict(list)
    for fid, s in schedule.items():
        per[s['battery']].append((s['start'], s['return'], s['energy'], fid))
    for bat, rl in per.items():
        model = bat.split('-')[0]
        rl.sort(key=lambda x: x[0])
        for i in range(len(rl) - 1):
            st, ret, e, fid = rl[i]
            soc = max(0.0, 1.0 - e / data.uav_types[model]['E_use'])
            ch = charge_time(soc, data.batteries[model]['T_full'])
            need = ret + ch
            nxt = rl[i + 1][0]
            if nxt < need - 1e-6:
                viol.append((bat, fid, rl[i + 1][3], round(ret), round(ch), round(need), round(nxt)))
    return viol


def load(src):
    d = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d['solution']]


def report(name, fls, verbose=False):
    sch, _ = dispatch_compliant(data, fls)
    if sch is None:
        print('%-26s | compliant 调度失败(不可行)' % name)
        return None, None
    m = evaluate(data, fls, sch)
    viol = check_battery(data, sch, fls)
    print('%-26s | compliant: %2d架 mk=%7.1f en=%6.2f hard=%s tardy=%.2f 电池违规=%d' % (
        name, len(fls), m['makespan'], m['energy'], m['hard_ok'], m['tardy_w'], len(viol)))
    if verbose and viol:
        for v in viol[:6]:
            print('       违规:', v)
    return m, sch


def merge_improve(data, fls, cap_relax, max_rnd):
    """合规口径下的合并搜索：merges（同型相邻可merge）接受 (mk降)或(en降且mk<=cur+cap_relax)。"""
    cur = clone_flights(fls)
    cur_met, cur_sch = None, None
    for rnd in range(max_rnd):
        sch, _ = dispatch_compliant(data, cur)
        if sch is None:
            break
        cur_met = evaluate(data, cur, sch)
        cur_sch = sch
        improved = False
        fls_sorted = sorted(cur, key=lambda f: cur_sch[f.fid]['return'])
        for i in range(len(fls_sorted)):
            for j in range(len(fls_sorted)):
                if i == j:
                    continue
                a, b = fls_sorted[i], fls_sorted[j]
                if a.model != b.model or set(s for s, _ in a.route) & set(s for s, _ in b.route):
                    continue
                gap = cur_sch[b.fid]['start'] - cur_sch[a.fid]['return']
                if not (0 <= gap <= 1500):
                    continue
                fl = clone_flights(cur)
                fa = next(x for x in fl if x.fid == a.fid)
                fb = next(x for x in fl if x.fid == b.fid)
                fa.route = [(s, list(bs)) for s, bs in a.route] + [(s, list(bs)) for s, bs in b.route]
                normalize_flight(fa, data)
                if not fa.is_feasible():
                    continue
                fl = [x for x in fl if x.fid != b.fid]
                sch2, _ = dispatch_compliant(data, fl)
                if sch2 is None:
                    continue
                m2 = evaluate(data, fl, sch2)
                if not (m2['hard_ok'] and m2['tardy_w'] < 1e-6):
                    continue
                better = (m2['makespan'] < cur_met['makespan'] - 1e-6
                          and m2['energy'] <= cur_met['energy'] + 0.5) \
                    or (m2['energy'] < cur_met['energy'] - 1e-6
                        and m2['makespan'] <= cur_met['makespan'] + cap_relax)
                if better:
                    cur = fl
                    cur_met = m2
                    improved = True
                    break
            if improved:
                break
        print('  merge rnd %d: mk=%.1f en=%.2f n=%d improved=%s' % (
            rnd + 1, cur_met['makespan'], cur_met['energy'], len(cur), improved), flush=True)
        if not improved:
            break
    return cur, cur_met


def main():
    # 1) 合规重调度现有解
    print('== 合规口径重调度现有解 ==', flush=True)
    m28, s28 = report('v25b(28架完工优先)', load('p2v25b_compress26.json'))
    m24, s24 = report('v25j(24架能耗优先)', load('p2v25j_dual.json'))
    m25, s25 = report('v25i(25架)', load('p2v25i_merge.json'))
    print()
    # 2) 合规口径重做合并搜索
    print('== 合规口径完工压缩（28架起点） ==', flush=True)
    c28, m28c = merge_improve(data, load('p2v25b_compress26.json'), 250, 20)
    print('== 合规口径能耗合并（24架起点） ==', flush=True)
    c24, m24c = merge_improve(data, load('p2v25j_dual.json'), 400, 20)
    # 3) 保存（含 solution）
    for tag, fls, met in [('makespan', c28, m28c), ('energy', c24, m24c)]:
        sch, _ = dispatch_compliant(data, fls)
        viol = check_battery(data, sch, fls)
        out = {'metrics': {k: v for k, v in met.items() if k != 'box_time'},
               'battery_violations': len(viol),
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]}
        p = os.path.join(OUTD, 'p2v28_compliant_%s.json' % tag)
        json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v28_compliant_%s.json (电池违规=%d)' % (tag, len(viol)))


if __name__ == '__main__':
    main()