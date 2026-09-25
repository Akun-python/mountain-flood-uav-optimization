# -*- coding: utf-8 -*-
"""v35 完工压缩（第二指标）——从 v34（23架/70.67kWh/9787s/零违规）出发。
手段：最长机链上重载趟拆 A25/B30 子趟（A 机闲置优先）+ 整趟换型。
接受：完工降 且 紧时限违规保持 0（及时性第一不破坏）且 能耗增 <= 2.0（第三指标监控）。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, evaluate
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import tardy_boxes, eval_full

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def split_into_ab(fl_in, f, data):
    """单区重载趟拆 A25 子趟为主（A 机闲置），A 装不下体积的用 B30；返回子趟列表或 None。
    A 子趟同时约束质量<=25 与 体积<=0.058（A V=0.06）。"""
    if len(f.route) != 1:
        return None
    sid, bs = f.route[0]
    boxes = sorted(bs, key=lambda b: -data.boxes[b]['mass'])
    parts = []
    while boxes:
        # 装 A25（质量+体积双约束）
        take, mass, vol = [], 0.0, 0.0
        for b in list(boxes):
            bv = data.boxes[b]['vol']
            if mass + data.boxes[b]['mass'] <= 25.0 and vol + bv <= 0.058:
                take.append(b); mass += data.boxes[b]['mass']; vol += bv
        if take:
            for b in take: boxes.remove(b)
            parts.append(('A', take))
            continue
        # A 装不下：B30
        take, mass, vol = [], 0.0, 0.0
        for b in list(boxes):
            if mass + data.boxes[b]['mass'] <= 30.0 and vol + data.boxes[b]['vol'] <= 0.071:
                take.append(b); mass += data.boxes[b]['mass']; vol += data.boxes[b]['vol']
        if take:
            for b in take: boxes.remove(b)
            parts.append(('B', take))
            continue
        parts.append(('B', [boxes.pop(0)]))
    if len(parts) <= 1:
        return None
    fid = max(x.fid for x in fl_in) + 1
    out = []
    for i, (gm, bs_p) in enumerate(parts):
        nf = Flight(fid + i, [(sid, bs_p)], gm, data)
        if not nf.is_feasible():
            nf2 = Flight(fid + i, [(sid, bs_p)], 'A', data)
            if nf2.is_feasible():
                nf = nf2
            else:
                return None
        out.append(nf)
    return out


def main():
    d0 = json.load(open(os.path.join(OUTD, 'p2v34_timely.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 v34: %d 架 / mk %.1f (%.1f min) / %.2f kWh / 违规=%d' % (
        len(fls), m0['makespan'], m0['makespan'] / 60, m0['energy'], nc0))
    cur = fls
    mk_hist = [m0['makespan']]; en_hist = [m0['energy']]
    for rnd in range(15):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d: 违规出现，停止' % (rnd + 1)); break
        chains = {}
        for fid, ss in s.items():
            chains.setdefault(ss['uav'], []).append((ss['return'], fid))
        longest = max(chains, key=lambda u: max(x[0] for x in chains[u]))
        cand = sorted(chains[longest], key=lambda x: -x[0])
        improved = False
        # 1) 整趟换型
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
                        and m2['energy'] <= m['energy'] + 3.0:
                    print('  r%d: f%d %s->%s mk %.1f en %.2f' % (
                        rnd + 1, fid, f.model, gm, m2['makespan'], m2['energy']), flush=True)
                    cur = candfl
                    mk_hist.append(m2['makespan']); en_hist.append(m2['energy'])
                    improved = True
                    break
            if improved:
                break
        if improved:
            continue
        # 2) 拆重载/满载（B/C 机 3 箱以上，A 装不下体积）
        for rt, fid in cand:
            f = next(x for x in cur if x.fid == fid)
            if len(f.route) == 1 and f.total_mass >= 25 and len(f.box_ids) >= 3:
                parts = split_into_ab(cur, f, data)
                if not parts:
                    continue
                candfl = [x for x in cur if x.fid != fid] + parts
                m2, s2, v2, nc2 = eval_full(data, candfl)
                if m2 and v2 == 0 and nc2 == 0 and m2['makespan'] < m['makespan'] - 1e-6 \
                        and m2['energy'] <= m['energy'] + 3.0:
                    print('  r%d: 拆 f%d %s mass%.0f -> %d子趟 mk %.1f en %.2f' % (
                        rnd + 1, fid, [s3 for s3, _ in f.route], f.total_mass,
                        len(parts), m2['makespan'], m2['energy']), flush=True)
                    cur = candfl
                    mk_hist.append(m2['makespan']); en_hist.append(m2['energy'])
                    improved = True
                    break
        if not improved:
            print('r%d: 无接受' % (rnd + 1))
            break
    m, s, v, nc = eval_full(data, cur)
    print('\n最终: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 电池违规=%d / 紧时限违规=%d' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    print('完工轨迹:', [round(x, 1) for x in mk_hist])
    print('能耗轨迹:', [round(x, 2) for x in en_hist])
    if m['makespan'] < m0['makespan'] - 1e-6:
        json.dump({'best': {k: vv for k, vv in m.items() if k != 'box_time'},
                   'traj': {'mk': mk_hist, 'en': en_hist},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
                  open(os.path.join(OUTD, 'p2v35_mk.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v35_mk.json')


if __name__ == '__main__':
    main()