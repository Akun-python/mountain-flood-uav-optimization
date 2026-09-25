# -*- coding: utf-8 -*-
"""v28b 严格合规口径能耗合并增强：从 28 架 compliant 基线(7666.1/83.12)出发，
用 dispatch_compliant + 宽接受（en降 & mk<=cur+500）做多轮 merge/换型，目标合规能耗冠军（零迟到）。"""
import sys, os, json, copy
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data, charge_time
from p2_solve import (Flight, flight_critical_time, make_resources, evaluate,
                      normalize_flight, clone_flights, dispatch)
from p2v28_compliant import dispatch_compliant, check_battery

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def load(src):
    d = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d['solution']]


def eval_c(data, fl):
    sch, _ = dispatch_compliant(data, fl)
    if sch is None:
        return None, None, None
    m = evaluate(data, fl, sch)
    viol = check_battery(data, sch, fl)
    return m, sch, viol


def main():
    cur = load('p2v28_compliant_makespan.json')
    # 找所有可合并候选（同型且区不重叠、容量足），按能耗收益降序
    m, s, v = eval_c(data, cur)
    print('起点: %d架 mk=%.1f en=%.2f 违规=%d tardy=%.2f' % (len(cur), m['makespan'], m['energy'], len(v), m['tardy_w']))
    for rnd in range(25):
        m, s, v = eval_c(data, cur)
        if m is None:
            break
        improved = False
        # merge：同型、区不重叠、合并后可行且能耗下降、完工 <= cur+500
        fls_sorted = sorted(cur, key=lambda f: s[f.fid]['return'])
        for i in range(len(fls_sorted)):
            for j in range(len(fls_sorted)):
                if i == j:
                    continue
                a, b = fls_sorted[i], fls_sorted[j]
                if a.model != b.model or set(x for x, _ in a.route) & set(x for x, _ in b.route):
                    continue
                gap = s[b.fid]['start'] - s[a.fid]['return']
                if not (0 <= gap <= 1500):
                    continue
                fl = clone_flights(cur)
                fa = next(x for x in fl if x.fid == a.fid)
                fb = next(x for x in fl if x.fid == b.fid)
                fa.route = [(x, list(bs)) for x, bs in a.route] + [(x, list(bs)) for x, bs in b.route]
                normalize_flight(fa, data)
                if not fa.is_feasible():
                    continue
                fl = [x for x in fl if x.fid != b.fid]
                m2, s2, v2 = eval_c(data, fl)
                if m2 is None or not (m2['hard_ok'] and m2['tardy_w'] < 1e-6):
                    continue
                if m2['energy'] < m['energy'] - 1e-6 and m2['makespan'] <= m['makespan'] + 500.0:
                    print('  rnd%d merge f%d+f%d -> %d架 mk=%.1f en=%.2f' % (
                        rnd + 1, a.fid, b.fid, len(fl), m2['makespan'], m2['energy']), flush=True)
                    cur = fl
                    m = m2
                    improved = True
                    break
            if improved:
                break
        # 换型：单区架次换更小型号（C->B->A）若能耗降
        if not improved:
            for f in cur:
                if len(f.route) != 1:
                    continue
                for to in {'C': 'B', 'B': 'A'}.get(f.model, []):
                    fl = clone_flights(cur)
                    fa = next(x for x in fl if x.fid == f.fid)
                    fa.model = to
                    normalize_flight(fa, data)
                    if not fa.is_feasible():
                        continue
                    m2, s2, v2 = eval_c(data, fl)
                    if m2 is None or not (m2['hard_ok'] and m2['tardy_w'] < 1e-6):
                        continue
                    if m2['energy'] < m['energy'] - 1e-6 and m2['makespan'] <= m['makespan'] + 500.0:
                        print('  rnd%d retype f%d %s->%s mk=%.1f en=%.2f' % (
                            rnd + 1, f.fid, f.model, to, m2['makespan'], m2['energy']), flush=True)
                        cur = fl
                        m = m2
                        improved = True
                        break
                if improved:
                    break
        if not improved:
            break
    m, s, v = eval_c(data, cur)
    print('\n合规能耗冠军: %d架 mk=%.1f (%.1fmin) en=%.2f 违规=%d tardy=%.2f' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], len(v), m['tardy_w']))
    json.dump({'metrics': {k: v for k, v in m.items() if k != 'box_time'}, 'battery_violations': len(v),
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(x, list(bs)) for x, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v28b_compliant_energy.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p2v28b_compliant_energy.json')


if __name__ == '__main__':
    main()