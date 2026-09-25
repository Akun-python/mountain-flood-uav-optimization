# -*- coding: utf-8 -*-
"""v36 完工-能耗容限扫描：从 v34 出发，完工压缩时能耗容限参数化 {3,4,5,6} kWh。
产出每档终点（架次/完工/能耗/违规），找完工<7000 且能耗可接受的前沿点。
逻辑同 v35（C->B 换型 + B/C 满载拆 A 子趟，零紧时限违规保持）。
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


def compress(fls, tol, tag):
    m0, s0, v0, nc0 = eval_full(data, fls)
    cur = fls
    for rnd in range(20):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            break
        chains = {}
        for fid, ss in s.items():
            chains.setdefault(ss['uav'], []).append((ss['return'], fid))
        longest = max(chains, key=lambda u: max(x[0] for x in chains[u]))
        cand = sorted(chains[longest], key=lambda x: -x[0])
        improved = False
        # 换型
        for rt, fid in cand:
            f = next(x for x in cur if x.fid == fid)
            opts = []
            if f.model == 'C' and f.total_mass <= 30:
                opts.append('B')
            if f.model in ('C', 'B') and f.total_mass <= 25 and len(f.route) == 1:
                opts.append('A')
            for gm in opts:
                nf = Flight(fid, f.route, gm, data)
                if not nf.is_feasible():
                    continue
                candfl = [x for x in cur if x.fid != fid] + [nf]
                m2, s2, v2, nc2 = eval_full(data, candfl)
                if m2 and v2 == 0 and nc2 == 0 and m2['makespan'] < m['makespan'] - 1e-6 \
                        and m2['energy'] <= m['energy'] + tol:
                    cur = candfl; improved = True
                    break
            if improved:
                break
        if improved:
            continue
        # 拆分
        for rt, fid in cand:
            f = next(x for x in cur if x.fid == fid)
            if len(f.route) == 1 and f.total_mass >= 25 and len(f.box_ids) >= 3:
                parts = split_into_ab(cur, f, data)
                if not parts:
                    continue
                candfl = [x for x in cur if x.fid != fid] + parts
                m2, s2, v2, nc2 = eval_full(data, candfl)
                if m2 and v2 == 0 and nc2 == 0 and m2['makespan'] < m['makespan'] - 1e-6 \
                        and m2['energy'] <= m['energy'] + tol:
                    cur = candfl; improved = True
                    break
        if not improved:
            break
    m, s, v, nc = eval_full(data, cur)
    print('容限%g: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / 违规%d' % (
        tol, len(cur), m['makespan'], m['makespan'] / 60, m['energy'], nc))
    json.dump({'tol': tol, 'best': {k: vv for k, vv in m.items() if k != 'box_time'},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v36_scan_tol%s.json' % tag), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return m


def main():
    d0 = json.load(open(os.path.join(OUTD, 'p2v34_timely.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    tols = [float(x) for x in sys.argv[1:]] or [3.0, 4.0, 5.0, 6.0]
    best = None
    for tol in tols:
        m = compress(fls, tol, str(tol).replace('.', '_'))
        if best is None or (m['makespan'], m['energy']) < (best['makespan'], best['energy']):
            best = m
    print('最优: mk %.1f en %.2f' % (best['makespan'], best['energy']))


if __name__ == '__main__':
    main()