# -*- coding: utf-8 -*-
"""v40 完工冲刺：从 v39 26架(7509.5s)出发，容限 +4/+5/+6 继续拆 B/C 满载给 A 池。
总趟时 44988/8台=5623s≈目标5694——瓶颈纯机型池不均(A 4台~4303-5574 vs B/C 2台~6900-7500)。
拆到 A 池并行至 ~5600 级。完工第二优先，能耗限制放宽（+6）。
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
    tol = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    src = sys.argv[2] if len(sys.argv) > 2 else 'p2v39_mk22.json'
    d0 = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 v39: %d 架 / mk %.1f / %.2f kWh / 违规%d  [容限+%.0f]' % (
        len(fls), m0['makespan'], m0['energy'], nc0, tol))
    cur = fls
    for rnd in range(20):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d: 违规出现' % (rnd + 1)); break
        chains = {}
        for fid, ss in s.items():
            chains.setdefault(ss['uav'], []).append((ss['return'], fid))
        longest = max(chains, key=lambda u: max(x[0] for x in chains[u]))
        cand = sorted(chains[longest], key=lambda x: -x[0])
        improved = False
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
                    print('  r%d: 拆 f%d %s mass%.0f -> %d子趟 mk %.1f en %.2f (%d架)' % (
                        rnd + 1, fid, [x for x, _ in f.route], f.total_mass, len(parts),
                        m2['makespan'], m2['energy'], len(candfl)), flush=True)
                    cur = candfl
                    improved = True
                    break
        if not improved:
            print('r%d: 无接受（完工下界收敛）' % (rnd + 1))
            break
    m, s, v, nc = eval_full(data, cur)
    print('最终[+%.0f]: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 违规%d' % (
        tol, len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], nc))
    tag = 'p2v40_mk_tol%s' % str(tol).replace('.', '_')
    json.dump({'tol': tol, 'best': {k: vv for k, vv in m.items() if k != 'box_time'},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, tag + '.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/%s.json' % tag)


if __name__ == '__main__':
    main()