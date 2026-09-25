# -*- coding: utf-8 -*-
"""v33 拆分 C 重载趟给 A/B 并行（完工优先，朝 94min）。
起点 v31（21架/65.5kWh/9407s）。循环：最长 C 链上的重载趟(mass>30)拆成 A25/B30 子趟(同区)。
接受：完工降（电池0违规+hard+零迟到硬），能耗增量受限（每步 <=+1.2kWh，总上限逐步放宽探测前沿）。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, evaluate
from p2v28_compliant import dispatch_compliant, check_battery

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def eval_full(data, fl):
    sch, _ = dispatch_compliant(data, fl)
    if sch is None:
        return None, None, 999
    viol = check_battery(data, sch, fl)
    m = evaluate(data, fl, sch)
    return m, sch, len(viol)


def split_into_ab(fl_in, f, data):
    """把单区重载趟拆成 A(<=25) 子趟为主（A 机 4 台闲置），剩余用 B(<=30)。
    返回 (new_flights_list) 或 None。"""
    if len(f.route) != 1:
        return None
    sid, bs = f.route[0]
    boxes = sorted(bs, key=lambda b: -data.boxes[b]['mass'])
    parts = []
    while boxes:
        # 装满 A25（A 机闲置资源）
        take, mass = [], 0.0
        for b in list(boxes):
            if mass + data.boxes[b]['mass'] <= 25.0:
                take.append(b)
                mass += data.boxes[b]['mass']
        if take:
            for b in take:
                boxes.remove(b)
            parts.append(('A', take))
            continue
        # 单箱超 25：试 B 30
        take, mass = [], 0.0
        for b in list(boxes):
            if mass + data.boxes[b]['mass'] <= 30.0:
                take.append(b)
                mass += data.boxes[b]['mass']
        if take:
            for b in take:
                boxes.remove(b)
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
            # B 不可行试 A
            nf2 = Flight(fid + i, [(sid, bs_p)], 'A', data)
            if nf2.is_feasible():
                nf = nf2
            else:
                return None
        out.append(nf)
    return out


def main():
    d0 = json.load(open(os.path.join(OUTD, 'p2v31_full.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0 = eval_full(data, fls)
    print('起点: %d 架 / mk %.1f (%.1f min) / %.2f kWh' % (
        len(fls), m0['makespan'], m0['makespan'] / 60, m0['energy']))
    cur = fls
    mk_hist = [m0['makespan']]
    en_hist = [m0['energy']]
    for rnd in range(12):
        m, s, v = eval_full(data, cur)
        chains = {}
        for fid, ss in s.items():
            chains.setdefault(ss['uav'], []).append((ss['return'], fid))
        # 找出完工最大的机链
        longest = max(chains, key=lambda u: max(x[0] for x in chains[u]))
        cand = sorted(chains[longest], key=lambda x: -x[0])
        improved = False
        # 1) 整趟换型（C->B mass<=30，C/B->A mass<=25）
        for rt, fid in cand:
            f = next(x for x in cur if x.fid == fid)
            for gm in (['B', 'A'] if f.model == 'C' else ['A']):
                if gm == 'B' and f.model == 'C' and f.total_mass <= 30:
                    candfl = [x for x in cur if x.fid != fid] + [Flight(fid, f.route, 'B', data)]
                elif gm == 'A' and f.model in ('C', 'B') and f.total_mass <= 25 and len(f.route) == 1:
                    candfl = [x for x in cur if x.fid != fid] + [Flight(fid, f.route, 'A', data)]
                else:
                    continue
                if not candfl[-1].is_feasible():
                    continue
                m2, s2, v2 = eval_full(data, candfl)
                if m2 is None or v2 > 0 or not (m2['hard_ok'] and m2['tardy_w'] <= m['tardy_w'] + 10.0):
                    continue
                if m2['makespan'] < m['makespan'] - 1e-6 and m2['energy'] <= m['energy'] + 1.5:
                    print('  r%d: f%d %s->%s (mass%.0f) mk %.1f en %.2f' % (
                        rnd + 1, fid, f.model, gm, f.total_mass, m2['makespan'], m2['energy']), flush=True)
                    cur = candfl
                    mk_hist.append(m2['makespan']); en_hist.append(m2['energy'])
                    improved = True
                    break
            if improved:
                break
        if improved:
            continue
        # 2) 最长链上重载趟拆 A/B
        for rt, fid in cand:
            f = next(x for x in cur if x.fid == fid)
            if len(f.route) == 1 and f.total_mass > 30:
                parts = split_into_ab(cur, f, data)
                if not parts:
                    continue
                cand_fl = [x for x in cur if x.fid != fid] + parts
                m2, s2, v2 = eval_full(data, cand_fl)
                if m2 is None or v2 > 0:
                    continue
                if not (m2['hard_ok'] and m2['tardy_w'] < 1e-6):
                    continue
                d_en = m2['energy'] - m['energy']
                if m2['makespan'] < m['makespan'] - 1e-6 and d_en <= 1.5:
                    print('  r%d: 拆 f%d %s mass%.0f -> %d子趟: mk %.1f en %.2f (+%.2f)' % (
                        rnd + 1, fid, [s3 for s3, _ in f.route], f.total_mass,
                        len(parts), m2['makespan'], m2['energy'], d_en), flush=True)
                    cur = cand_fl
                    mk_hist.append(m2['makespan'])
                    en_hist.append(m2['energy'])
                    improved = True
                    break
        if not improved:
            print('r%d: 无接受拆分' % (rnd + 1))
            break
    m, s, v = eval_full(data, cur)
    print('\n最终: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 电池违规=%d / 迟到 %.1f' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, m['tardy_w']))
    print('完工轨迹:', [round(x, 1) for x in mk_hist])
    print('能耗轨迹:', [round(x, 2) for x in en_hist])
    json.dump({'best': {k: vv for k, vv in m.items() if k != 'box_time'},
               'traj': {'mk': mk_hist, 'en': en_hist},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v33_split.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p2v33_split.json')


if __name__ == '__main__':
    main()