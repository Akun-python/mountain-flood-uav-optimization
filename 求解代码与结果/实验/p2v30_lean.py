# -*- coding: utf-8 -*-
"""v30 28架合规完工解的定向瘦身：把轻载单区趟（单箱<=8kg 或 mass<=10）并入访问同区的趟。
接受：架次↓ 或 (能耗↓ 且 完工<=cur+60) 且 零迟到 + 电池 0 违规 + hard。
全程 dispatch_compliant + check_battery + 严格 evaluate。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, evaluate, normalize_flight, clone_flights
from p2v28_compliant import dispatch_compliant, check_battery

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def eval_full(data, fl):
    sch, _ = dispatch_compliant(data, fl)
    if sch is None:
        return None, None, 999
    viol = check_battery(data, sch, fl)
    m = evaluate(data, fl, sch)
    return m, sch, len(viol)


def add_box_to_zone(fl, tgt_fid, sid, bid):
    fl = clone_flights(fl)
    t = next(x for x in fl if x.fid == tgt_fid)
    route = list(t.route)
    done = False
    for i, (s2, bs2) in enumerate(route):
        if s2 == sid:
            route[i] = (s2, bs2 + [bid])
            done = True
            break
    if not done:
        route.append((sid, [bid]))
    t.route = route
    normalize_flight(t, data)
    if not t.is_feasible():
        return None
    return fl


def main():
    start = json.load(open(os.path.join(OUTD, 'p2v28_compliant_makespan.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in start['solution']]
    m0, s0, v0 = eval_full(data, fls)
    print('起点: %d 架 / mk %.1f / %.2f kWh / 电池违规=%d / 迟到 %.2f' % (
        len(fls), m0['makespan'], m0['energy'], v0, m0['tardy_w']))
    cur, cur_met, cur_v = fls, m0, v0
    for rnd in range(12):
        # 找轻载单区单箱趟
        light = [f for f in cur if len(f.route) == 1 and len(f.box_ids) == 1
                 and f.total_mass <= 10 and f.model in ('A', 'B')]
        if not light:
            print('round %d: 无轻载单箱趟，停止' % (rnd + 1))
            break
        improved = False
        for f in light:
            sid, bs = f.route[0]
            bid = bs[0]
            # 找访问该区的其它趟（同区可并入）
            tgt = [g for g in cur if g.fid != f.fid and any(s == sid for s, _ in g.route)
                   and g.model in ('B', 'C')]
            tgt.sort(key=lambda g: g.duration())
            for g in tgt:
                cand = add_box_to_zone(cur, g.fid, sid, bid)
                if cand is None:
                    continue
                cand = [x for x in cand if x.fid != f.fid]
                m, s, v = eval_full(data, cand)
                if m is None or v > 0 or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                    continue
                better = (m['makespan'] <= cur_met['makespan'] + 60.0
                          and m['energy'] < cur_met['energy'] - 1e-6)
                if better:
                    print('  round%d: 并入 f%d(箱%s %s区->f%d) -> %d 架 / mk %.1f / %.2f kWh' % (
                        rnd + 1, f.fid, bid, sid, g.fid, len(cand), m['makespan'], m['energy']))
                    cur, cur_met, cur_v = cand, m, v
                    improved = True
                    break
            if improved:
                break
        if not improved:
            print('round %d: 无可接受合并，停止' % (rnd + 1))
            break
    print('\n结果: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard %s / 电池违规=%d / 迟到 %.2f' % (
        cur_met['flights'], cur_met['makespan'], cur_met['makespan'] / 60, cur_met['energy'],
        cur_met['hard_ok'], cur_v, cur_met['tardy_w']))
    if cur_met['energy'] < m0['energy'] - 1e-6:
        json.dump({'best': {k: v for k, v in cur_met.items() if k != 'box_time'},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
                  open(os.path.join(OUTD, 'p2v30_lean.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v30_lean.json')


if __name__ == '__main__':
    main()