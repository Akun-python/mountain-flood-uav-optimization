# -*- coding: utf-8 -*-
"""p2v54_mk.py —— 完工优先转移搜索（从 29 架出发）。
算子：单趟换型（B<->C / A->B 等，可行且零违规时）；接受 = 完工降（或完工平能耗降）。
预期：B 池 6993 瓶颈 → f16(S013 1505s) 换 C 池（C 5957 半闲）→ 完工 ~6709。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import eval_full

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()
MODELS = ['A', 'B', 'C']


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'p2v40_mk_tol6_0.json'
    d0 = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 %s: %d架 mk=%.1f en=%.2f' % (src, len(fls), m0['makespan'], m0['energy']))
    cur = fls
    for rnd in range(20):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d 违规' % (rnd + 1)); break
        best = None
        for f in cur:
            for gm in MODELS:
                if gm == f.model:
                    continue
                nf = Flight(f.fid, f.route, gm, data)
                if not nf.is_feasible():
                    continue
                cand = [x for x in cur if x.fid != f.fid] + [nf]
                m2, s2, v2, nc2 = eval_full(data, cand)
                if m2 is None or v2 > 0 or nc2 > 0 or (not m2['hard_ok']):
                    continue
                ok = (m2['makespan'] < m['makespan'] - 1e-6) or \
                     (abs(m2['makespan'] - m['makespan']) < 1e-6 and
                      m2['energy'] < m['energy'] - 0.02)
                if ok and (best is None or
                           (m2['makespan'], m2['energy']) < (best[0]['makespan'], best[0]['energy'])):
                    best = (m2, cand, f.fid, gm)
        if best is None:
            print('r%d 收敛: mk=%.1f en=%.2f' % (rnd + 1, m['makespan'], m['energy']))
            break
        m2, cand, fid, gm = best
        print('  r%d: f%d %s->%s: mk %.1f en %.2f (%d架)' % (
            rnd + 1, fid, next(x for x in cur if x.fid == fid).model, gm,
            m2['makespan'], m2['energy'], len(cand)), flush=True)
        cur = cand
    m, s, v, nc = eval_full(data, cur)
    print('最终: %d架 mk=%.1f (%.1fmin) en=%.2f hard=%s 电池%d 违规%d' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy']},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v54_mk_rettype.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v54_mk_rettype.json')


if __name__ == '__main__':
    main()