# -*- coding: utf-8 -*-
"""p2v46_23local.py —— 23 架局部邻域搜索（锁定 23 趟）。
算子：同区箱迁移（box 从趟 X->趟 Y，同区 + 机型可承载），趟数不变。
接受：完工下降优先、能耗次之、零违规。循环至收敛。
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


def rebuild(fls, move):
    """move=(box, src_fid, dst_fid)。返回新趟列表或 None。"""
    out = []
    box, src, dst = move
    src_f = next(x for x in fls if x.fid == src)
    dst_f = next(x for x in fls if x.fid == dst)
    # 同区
    sid = src_f.route[0][0]
    if dst_f.route[0][0] != sid:
        return None
    sr = [(s, [b for b in bs if b != box]) for s, bs in src_f.route]
    dr = [(s, list(bs) + [box]) for s, bs in dst_f.route]
    if not sr[0][1]:
        return None
    nf = Flight(src_f.fid, sr, src_f.model, data)
    if not nf.is_feasible():
        return None
    nd = Flight(dst_f.fid, dr, dst_f.model, data)
    if not nd.is_feasible():
        return None
    out = [x for x in fls if x.fid not in (src, dst)] + [nf, nd]
    return out


def main():
    d0 = json.load(open(os.path.join(OUTD, 'p2v42_23base.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 23架: mk=%.1f en=%.2f nc=%d' % (m0['makespan'], m0['energy'], nc0))
    cur = fls
    for rnd in range(30):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d 违规出现' % (rnd + 1)); break
        improved = False
        # 同区趟分组
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
                    for dsti in fids:
                        if dsti == src:
                            continue
                        cand = rebuild(cur, (box, src, dsti))
                        if cand is None:
                            continue
                        m2, s2, v2, nc2 = eval_full(data, cand)
                        if m2 and v2 == 0 and nc2 == 0 and \
                                (m2['makespan'] < m['makespan'] - 1e-6 or
                                 (abs(m2['makespan'] - m['makespan']) < 1e-6 and m2['energy'] < m['energy'] - 0.02)):
                            print('  r%d: %s f%d->f%d mk %.1f en %.2f' % (
                                rnd + 1, box, src, dsti, m2['makespan'], m2['energy']), flush=True)
                            cur = cand
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
        if not improved:
            print('r%d 收敛' % (rnd + 1))
            break
    m, s, v, nc = eval_full(data, cur)
    print('最终 23架: mk=%.1f (%.1fmin) en=%.2f hard=%s 电池%d 违规%d' % (
        m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    if nc == 0 and (m['makespan'], m['energy']) < (7771.0, 67.78):
        json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy']},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
                  open(os.path.join(OUTD, 'p2v46_23local.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved p2v46_23local.json (好于基线)')


if __name__ == '__main__':
    main()