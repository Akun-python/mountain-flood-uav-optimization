# -*- coding: utf-8 -*-
"""v32 机队均衡（完工优先）：从 v31 21架(65.5kWh/9407s)出发。
算子1：C机趟 mass<=30 换 B、<=25 换 A（route 不变重选最小能耗可行机型）
算子2：C机趟 mass>30：拆成 (B[30], rest) 等多趟同区（增趟并行）
接受：完工降（最好 <=6000），能耗上限监控。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, evaluate, normalize_flight, clone_flights
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


def best_model(route, data, cur_model):
    """route 的所有可行机型中能耗最小（含当前）。"""
    best = None
    for gm in ['A', 'B', 'C']:
        f = Flight(0, route, gm, data)
        if f.is_feasible():
            if best is None or f.energy() < best[1]:
                best = (gm, f.energy())
    return best


def split_heavy(fl_in, f, data):
    """把 C 机重载趟拆成多趟（尽量 1 B30 + 余量），同区。返回新架次列表或 None。"""
    if len(f.route) != 1:
        return None
    sid, bs = f.route[0]
    boxes = sorted(bs, key=lambda b: -data.boxes[b]['mass'])
    parts = []
    while boxes:
        take, mass = [], 0.0
        for b in list(boxes):
            if mass + data.boxes[b]['mass'] <= 30.0:
                take.append(b); mass += data.boxes[b]['mass']
        if not take:
            take = [boxes.pop(0)]
        else:
            for b in take:
                boxes.remove(b)
        parts.append((take, mass))
    if len(parts) <= 1:
        return None
    fid = max(x.fid for x in fl_in) + 1
    out = []
    for i, (bs_p, m_p) in enumerate(parts):
        gm = best_model([(sid, bs_p)], data, None)[0]
        out.append((fid + i, gm, [(sid, bs_p)]))
    return out


def main():
    d0 = json.load(open(os.path.join(OUTD, 'p2v31_full.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0 = eval_full(data, fls)
    print('起点 v31: %d 架 / mk %.1f / %.2f kWh' % (len(fls), m0['makespan'], m0['energy']))
    cur = fls
    for rnd in range(10):
        m, s, v = eval_full(data, cur)
        chains = {}
        for fid, ss in s.items():
            chains.setdefault(ss['uav'], []).append(ss['return'])
        longest_uav = max(chains, key=lambda u: max(chains[u]))
        # 候选：最长链上 C 机趟
        long_fids = [fid for fid, ss in s.items() if ss['uav'] == longest_uav]
        improved = False
        for fid in sorted(long_fids, key=lambda x: -s[x]['return']):
            f = next(x for x in cur if x.fid == fid)
            if f.model == 'C':
                # 1) 换型尝试
                bm = best_model(f.route, data, f.model)
                if bm and bm[0] != 'C':
                    cand = clone_flights(cur)
                    tgt = next(x for x in cand if x.fid == fid)
                    tgt.model = bm[0]
                    normalize_flight(tgt, data)
                    if tgt.is_feasible():
                        m2, s2, v2 = eval_full(data, cand)
                        if m2 and v2 == 0 and (m2['makespan'] < m['makespan'] - 1e-6
                                               or (m2['makespan'] <= m['makespan'] + 5 and m2['energy'] < m['energy'] - 0.2)):
                            print('  r%d: f%d C->%s (mass %.0f) mk %.1f en %.2f' % (
                                rnd + 1, fid, bm[0], f.total_mass, m2['makespan'], m2['energy']))
                            cur = cand; improved = True
                            break
        if improved:
            continue
        # 2) 拆分最长链 C 大载趟
        for fid in sorted(long_fids, key=lambda x: -s[x]['return']):
            f = next(x for x in cur if x.fid == fid)
            if f.model == 'C' and f.total_mass > 30:
                parts = split_heavy(cur, f, data)
                if parts:
                    cand = [x for x in cur if x.fid != fid]
                    for nid, gm, route in parts:
                        cand.append(Flight(nid, route, gm, data))
                    m2, s2, v2 = eval_full(data, cand)
                    if m2 and v2 == 0 and (m2['makespan'] < m['makespan'] - 1e-6):
                        # 复核硬约束
                        from p2_solve import evaluate as ev
                        hard = m2['hard_ok'] and m2['tardy_w'] < 1e-6
                        if hard:
                            print('  r%d: 拆 f%d C %s mass%.0f -> %d架 mk %.1f en %.2f' % (
                                rnd + 1, fid, [s2 for s2, _ in f.route], f.total_mass,
                                len(cand), m2['makespan'], m2['energy']))
                            cur = cand; improved = True
                            break
        if not improved:
            print('r%d: 无改进停止' % (rnd + 1))
            break
    m, s, v = eval_full(data, cur)
    print('\n最终: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 电池违规=%d / 迟到 %.1f' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, m['tardy_w']))
    if m['makespan'] < m0['makespan'] - 1e-6:
        json.dump({'best': {k: vv for k, vv in m.items() if k != 'box_time'},
                   'prev': {'mk': m0['makespan'], 'en': m0['energy']},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
                  open(os.path.join(OUTD, 'p2v32_balance.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v32_balance.json')


if __name__ == '__main__':
    main()