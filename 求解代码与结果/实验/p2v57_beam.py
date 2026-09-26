# -*- coding: utf-8 -*-
"""p2v57_beam.py —— 29 架完工优先束搜索（深度 4，多步组合改进去找 v54/v55 单步贪心漏掉的路）。
起点：29架/7148.2s（p2v54_mk_rettype.json）。算子：换型 + 满载拆分。
接受：零违规 + hard + 电池合规；排序键 (mk, en)；能耗容忍 best_en+20（完工优先）。
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


def ops(fls, src):
    res = []
    seen = set()
    for f in fls:
        for gm in MODELS:
            if gm == f.model:
                continue
            nf = Flight(f.fid, f.route, gm, data)
            if not nf.is_feasible():
                continue
            key = ('r', f.fid, gm)
            if key in seen:
                continue
            seen.add(key)
            res.append(('r', f.fid, gm))
    for f in fls:
        if len(f.route) > 1 or len(f.box_ids) < 2:
            continue
        parts = split_into_ab(src, f, data)
        if not parts:
            continue
        res.append(('s', f.fid))
    return res


def apply(fls, op):
    t, fid, *rest = op
    if t == 'r':
        gm = rest[0]
        nf = Flight(fid, next(f.route for f in fls if f.fid == fid), gm, data)
        return [x for x in fls if x.fid != fid] + [nf], True
    else:
        f = next(x for x in fls if x.fid == fid)
        parts = split_into_ab(fls, f, data)
        if not parts:
            return None, False
        return [x for x in fls if x.fid != fid] + parts, True


def main():
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    D = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    tol_en = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0
    src_j = sys.argv[4] if len(sys.argv) > 4 else 'p2v54_mk_rettype.json'
    d0 = json.load(open(os.path.join(OUTD, src_j), encoding='utf-8'))
    root = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, root)
    print('起点: %d架 mk=%.1f en=%.2f | 束宽%d 深%d 能耗容差+%.0f' % (
        len(root), m0['makespan'], m0['energy'], W, D, tol_en), flush=True)
    pop = [(m0['makespan'], m0['energy'], root)]
    best = (m0['makespan'], m0['energy'], root)
    for d in range(D):
        nxt = []
        for mk, en, fls in pop:
            for op in ops(fls, fls):
                cand, ok = apply(fls, op)
                if not ok:
                    continue
                m, s, v, nc = eval_full(data, cand)
                if m is None or v > 0 or nc > 0 or (not m['hard_ok']):
                    continue
                if m['energy'] > best[1] + tol_en:
                    continue
                nxt.append((m['makespan'], m['energy'], cand))
        if not nxt:
            print('d%d: 无新合规候选' % (d + 1), flush=True)
            break
        nxt.sort(key=lambda x: (x[0], x[1]))
        pop = nxt[:W]
        b0 = pop[0]
        if (b0[0], b0[1]) < (best[0], best[1]):
            best = b0
            print('  d%d 改进: %d架 mk=%.1f (%.2fmin) en=%.2f' % (
                d + 1, len(b0[2]), b0[0], b0[0] / 60, b0[1]), flush=True)
        else:
            print('  d%d 保持: 前%d个候选 mk∈[%.1f,%.1f]' % (
                d + 1, min(W, len(pop)), pop[0][0], pop[-1][0]), flush=True)
        if d == 0 and pop[0][0] >= best[0] - 1e-6:
            pass
    m, s, v, nc = eval_full(data, best[2])
    print('最终: %d架 mk=%.1f (%.1fmin) en=%.2f hard=%s 违规%d 电池%d' % (
        len(best[2]), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy']},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in best[2]]},
              open(os.path.join(OUTD, 'p2v57_beam_w%d_d%d.json' % (W, D)), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v57_beam_w%d_d%d.json' % (W, D))


if __name__ == '__main__':
    main()