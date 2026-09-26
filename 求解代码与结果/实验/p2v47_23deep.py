# -*- coding: utf-8 -*-
"""p2v47_23deep.py —— 23 架深度局部搜索 II（基于 v46 结果）。
扩展算子：①同区箱迁移（v46）②同趟换型（A<->B<->C 可行则试，能耗/完工权衡）
③同区双箱 swap（两趟互换一箱）。循环至全算子收敛。
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


def m(fls):
    r = eval_full(data, fls)
    return r


def try_swap(fls, a_fid, b_fid, swap_boxes):
    """swap_boxes: (boxA, boxB) 互换。同区校验 + 可行性 + eval。"""
    fa = next(x for x in fls if x.fid == a_fid)
    fb = next(x for x in fls if x.fid == b_fid)
    ba, bb = swap_boxes
    if fa.route[0][0] != fb.route[0][0]:
        return None
    ra = [(s, [x for x in bs if x != ba] + ([bb] if bb not in bs else [])) for s, bs in fa.route]
    rb = [(s, [x for x in bs if x != bb] + [ba]) for s, bs in fb.route]
    na = Flight(fa.fid, ra, fa.model, data)
    if not na.is_feasible():
        return None
    nb = Flight(fb.fid, rb, fb.model, data)
    if not nb.is_feasible():
        return None
    return [x for x in fls if x.fid not in (a_fid, b_fid)] + [na, nb]


def try_migrate(fls, box, src, dst):
    sf = next(x for x in fls if x.fid == src)
    df = next(x for x in fls if x.fid == dst)
    if sf.route[0][0] != df.route[0][0]:
        return None
    sr = [(s, [b for b in bs if b != box]) for s, bs in sf.route]
    dr = [(s, list(bs) + [box]) for s, bs in df.route]
    if not sr[0][1] or sr[0][1][0].split('-')[0] != sf.route[0][0]:
        return None
    na = Flight(sf.fid, sr, sf.model, data)
    if not na.is_feasible():
        return None
    nb = Flight(df.fid, dr, df.model, data)
    if not nb.is_feasible():
        return None
    return [x for x in fls if x.fid not in (src, dst)] + [na, nb]


def try_rettype(fls, fid, gm):
    f = next(x for x in fls if x.fid == fid)
    if f.model == gm:
        return None
    nf = Flight(f.fid, f.route, gm, data)
    if not nf.is_feasible():
        return None
    return [x for x in fls if x.fid != fid] + [nf]


def main():
    d0 = json.load(open(os.path.join(OUTD, 'p2v46_23local.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 v46: %d架 mk=%.1f en=%.2f' % (len(fls), m0['makespan'], m0['energy']))
    cur = fls
    for rnd in range(40):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d 违规' % (rnd + 1)); break
        improved = False
        # 1) 迁移
        grp = {}
        for f in cur:
            if len(f.route) == 1:
                grp.setdefault(f.route[0][0], []).append(f.fid)
        for sid, fids in grp.items():
            if len(fids) < 2:
                continue
            for src in fids:
                sf = next(x for x in cur if x.fid == src)
                for box in sf.box_ids:
                    for dst in fids:
                        if dst == src:
                            continue
                        cand = try_migrate(cur, box, src, dst)
                        if cand is None:
                            continue
                        m2, s2, v2, nc2 = eval_full(data, cand)
                        if m2 and v2 == 0 and nc2 == 0 and \
                                (m2['makespan'] < m['makespan'] - 1e-6 or
                                 (abs(m2['makespan'] - m['makespan']) < 1e-6 and m2['energy'] < m['energy'] - 0.02)):
                            print('  r%d 迁移 %s %d->%d mk %.1f en %.2f' % (
                                rnd + 1, box, src, dst, m2['makespan'], m2['energy']), flush=True)
                            cur = cand; improved = True; break
                    if improved: break
                if improved: break
            if improved: break
        if improved:
            continue
        # 2) 换型
        for f in list(cur):
            for gm in MODELS:
                if gm == f.model:
                    continue
                cand = try_rettype(cur, f.fid, gm)
                if cand is None:
                    continue
                m2, s2, v2, nc2 = eval_full(data, cand)
                if m2 and v2 == 0 and nc2 == 0 and \
                        (m2['makespan'] < m['makespan'] - 1e-6 or
                         (abs(m2['makespan'] - m['makespan']) < 1e-6 and m2['energy'] < m['energy'] - 0.02)):
                    print('  r%d 换型 f%d %s->%s mk %.1f en %.2f' % (
                        rnd + 1, f.fid, f.model, gm, m2['makespan'], m2['energy']), flush=True)
                    cur = cand; improved = True; break
            if improved: break
        if improved:
            continue
        # 3) 同区双箱 swap
        for sid, fids in grp.items():
            if len(fids) < 2:
                continue
            for i in range(len(fids)):
                for j in range(i + 1, len(fids)):
                    fa = next(x for x in cur if x.fid == fids[i])
                    fb = next(x for x in cur if x.fid == fids[j])
                    for ba in fa.box_ids:
                        for bb in fb.box_ids:
                            cand = try_swap(cur, fa.fid, fb.fid, (ba, bb))
                            if cand is None:
                                continue
                            m2, s2, v2, nc2 = eval_full(data, cand)
                            if m2 and v2 == 0 and nc2 == 0 and \
                                    (m2['makespan'] < m['makespan'] - 1e-6 or
                                     (abs(m2['makespan'] - m['makespan']) < 1e-6 and m2['energy'] < m['energy'] - 0.02)):
                                print('  r%d swap %s<->%s mk %.1f en %.2f' % (
                                    rnd + 1, ba, bb, m2['makespan'], m2['energy']), flush=True)
                                cur = cand; improved = True; break
                        if improved: break
                    if improved: break
                if improved: break
            if improved: break
        if not improved:
            print('r%d 全算子收敛' % (rnd + 1))
            break
    m, s, v, nc = eval_full(data, cur)
    print('最终: %d架 mk=%.1f (%.1fmin) en=%.2f hard=%s 电池%d 违规%d' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy']},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v47_23deep.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v47_23deep.json')


if __name__ == '__main__':
    main()