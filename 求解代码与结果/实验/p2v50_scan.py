# -*- coding: utf-8 -*-
"""p2v50_scan.py —— 架次作为优化变量的多目标扫描。
从 29 架（完工 7168.5）出发沿拆分搜索遍历各架次 N，收集 (N, mk, en)；
容差大以确认完工拐点（更高架次是否更低完工）。约束：零违规/电池。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import eval_full
from p2v35_mk import split_into_ab

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def main():
    tol = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    src = sys.argv[2] if len(sys.argv) > 2 else 'p2v40_mk_tol6_0.json'
    d0 = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 %s: %d 架 / mk %.1f / en %.2f [容差+%.0f]' % (
        src, len(fls), m0['makespan'], m0['energy'], tol))
    cur = fls
    curve = {}
    for rnd in range(30):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d 违规' % (rnd + 1)); break
        n = len(cur)
        if n not in curve or m['makespan'] < curve[n][0]:
            curve[n] = (m['makespan'], m['energy'])
        cands = [f for f in cur if len(f.route) == 1 and f.total_mass >= 20 and len(f.box_ids) >= 2]
        cands.sort(key=lambda f: (-f.total_mass, -f.duration()))
        improved = False
        for f in cands:
            parts = split_into_ab(cur, f, data)
            if not parts:
                continue
            candfl = [x for x in cur if x.fid != f.fid] + parts
            m2, s2, v2, nc2 = eval_full(data, candfl)
            if m2 and v2 == 0 and nc2 == 0 and m2['makespan'] < m['makespan'] - 1e-6 \
                    and m2['energy'] <= m['energy'] + tol:
                cur = candfl
                improved = True
                print('  r%d: 拆 f%d %s -> %d子趟: mk %.1f en %.2f (%d架)' % (
                    rnd + 1, f.fid, f.route[0][0], len(parts), m2['makespan'],
                    m2['energy'], len(candfl)), flush=True)
                break
        if not improved:
            print('r%d 完工收敛' % (rnd + 1))
            break
    m, s, v, nc = eval_full(data, cur)
    print('最终: %d架 / mk %.1f (%.1fmin) / en %.2f / 电池%d / 违规%d' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], v, nc))
    print('--- 轨迹 (N: mk/en): ---')
    for n in sorted(curve):
        print('  N=%2d  mk=%7.1f (%.1fmin)  en=%6.2f' % (
            n, curve[n][0], curve[n][0] / 60, curve[n][1]))
    json.dump({'curve': {str(n): list(v) for n, v in curve.items()},
               'final': {'N': len(cur), 'mk': m['makespan'], 'en': m['energy']}},
              open(os.path.join(OUTD, 'p2v50_scan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v50_scan.json')


if __name__ == '__main__':
    main()