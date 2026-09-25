# -*- coding: utf-8 -*-
"""v28d 从25架严格合规基线(7790.5/78.88)做能耗merge -> 目标24架/77级/零迟到。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, evaluate, normalize_flight, clone_flights
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
    return m, sch, check_battery(data, sch, fl)


def main():
    cur = load('p2v25i_merge.json')
    m, s, v = eval_c(data, cur)
    print('起点: %d架 mk=%.1f en=%.2f 违规=%d tardy=%.2f' % (len(cur), m['makespan'], m['energy'], len(v), m['tardy_w']))
    for rnd in range(30):
        m, s, v = eval_c(data, cur)
        if m is None:
            break
        improved = False
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
                if m2['energy'] < m['energy'] - 1e-6 and m2['makespan'] <= m['makespan'] + 600.0:
                    print('  rnd%d merge f%d+f%d -> %d架 mk=%.1f en=%.2f' % (
                        rnd + 1, a.fid, b.fid, len(fl), m2['makespan'], m2['energy']), flush=True)
                    cur = fl
                    m = m2
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    m, s, v = eval_c(data, cur)
    print('\n结果: %d架 mk=%.1f (%.1fmin) en=%.2f 违规=%d tardy=%.2f hard=%s' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], len(v), m['tardy_w'], m['hard_ok']))
    json.dump({'metrics': {k: v for k, v in m.items() if k != 'box_time'}, 'battery_violations': len(v),
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(x, list(bs)) for x, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v28d_compliant_energy.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p2v28d_compliant_energy.json')


if __name__ == '__main__':
    main()