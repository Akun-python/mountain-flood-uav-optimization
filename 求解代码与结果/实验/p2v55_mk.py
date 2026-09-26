# -*- coding: utf-8 -*-
"""p2v55_mk.py —— 从 v54(7148.2) 出发的完工优先联合搜索（拆分+换型）。
算子：①满载拆 A/B 子趟（保/增趟数）②单趟换型。接受：完工降（容差 en +15）。
目的：确认 29 架完工是否已到结构极限。
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
MODELS = ['A', 'B', 'C']


def main():
    tol = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
    src = sys.argv[2] if len(sys.argv) > 2 else 'p2v54_mk_rettype.json'
    d0 = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 %s: %d架 mk=%.1f en=%.2f [容差+%.0f]' % (src, len(fls), m0['makespan'], m0['energy'], tol))
    cur = fls
    for rnd in range(25):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d 违规' % (rnd + 1)); break
        best = None
        # 1) 拆分
        for f in cur:
            if len(f.route) > 1 or len(f.box_ids) < 2:
                continue
            parts = split_into_ab(cur, f, data)
            if not parts:
                continue
            cand = [x for x in cur if x.fid != f.fid] + parts
            m2, s2, v2, nc2 = eval_full(data, cand)
            if m2 is not None and v2 == 0 and nc2 == 0 and m2['makespan'] < m['makespan'] - 1e-6 \
                    and m2['energy'] <= m['energy'] + tol:
                key = (m2['makespan'], m2['energy'])
                if best is None or key < (best[1]['makespan'], best[1]['energy']):
                    best = ('split', f.fid, m2, cand)
        # 2) 换型
        for f in cur:
            for gm in MODELS:
                if gm == f.model:
                    continue
                nf = Flight(f.fid, f.route, gm, data)
                if not nf.is_feasible():
                    continue
                cand = [x for x in cur if x.fid != f.fid] + [nf]
                m2, s2, v2, nc2 = eval_full(data, cand)
                if m2 is not None and v2 == 0 and nc2 == 0 and m2['makespan'] < m['makespan'] - 1e-6 \
                        and m2['energy'] <= m['energy'] + tol:
                    key = (m2['makespan'], m2['energy'])
                    if best is None or key < (best[1]['makespan'], best[1]['energy']):
                        best = ('ret', f.fid, m2, cand)
        if best is None:
            print('r%d 收敛: %d架 mk=%.1f en=%.2f' % (rnd + 1, len(cur), m['makespan'], m['energy']))
            break
        op, fid, m2, cand = best
        print('  r%d: %s f%d: mk %.1f en %.2f (%d架)' % (
            rnd + 1, op, fid, m2['makespan'], m2['energy'], len(cand)), flush=True)
        cur = cand
    m, s, v, nc = eval_full(data, cur)
    print('最终: %d架 mk=%.1f (%.1fmin) en=%.2f hard=%s 电池%d 违规%d' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy']},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v55_mk_joint.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v55_mk_joint.json')


if __name__ == '__main__':
    main()