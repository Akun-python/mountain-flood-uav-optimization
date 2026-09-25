# -*- coding: utf-8 -*-
"""v29 合规口径能耗优先全局搜索（目标：逼近 23架/94min/66kWh）。
起点：25架能耗冠军（p2v28d_compliant_energy.json，7790.5s/78.88kWh）。
算子：C吸收(非C轻载<=45kg并入C)、C内部合并、B内部/升舱、A升舱；
接受：energy↓ 且 makespan<=cur+250（能耗优先），或 makespan↓ 且 energy<=cur+0.5；
全程 dispatch_compliant + check_battery + 严格 evaluate（hard+零迟到）。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data, charge_time
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


def merge_into(data, fl, src_f, tgt_f):
    fl = clone_flights(fl)
    src = next(x for x in fl if x.fid == src_f.fid)
    tgt = next(x for x in fl if x.fid == tgt_f.fid)
    q = data.uav_types[tgt.model]['Q']
    if src.total_mass + tgt.total_mass > q + 1e-9:
        return None
    seen, route = {}, []
    for s, bs in list(tgt.route) + list(src.route):
        if s in seen:
            for b in bs:
                seen[s].append(b)
        else:
            seen[s] = list(bs)
            route.append((s, seen[s]))
    tgt.route = route
    normalize_flight(tgt, data)
    if not tgt.is_feasible():
        return None
    return [x for x in fl if x.fid != src.fid]


def main():
    start = json.load(open(os.path.join(OUTD, 'p2v28d_compliant_energy.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in start['solution']]
    m0, s0, v0 = eval_full(data, fls)
    print('起点(v28d): %d 架 / mk %.1f / %.2f kWh / 电池违规=%d' % (
        len(fls), m0['makespan'], m0['energy'], v0))
    cur, cur_met, cur_sch, cur_v = fls, m0, s0, v0
    log = []
    for rnd in range(30):
        improved = False
        singles = [f for f in cur if len(f.route) == 1]
        cands = []
        for i in range(len(singles)):
            for j in range(len(singles)):
                if i == j:
                    continue
                a, b = singles[i], singles[j]
                if a.model == 'C' and b.model != 'C' and b.total_mass <= 45:
                    cands.append((b, a, 'Cabsorb'))
                elif a.model == 'C' and b.model == 'C' and a.total_mass <= 45 and b.total_mass <= 45:
                    cands.append((b, a, 'Cmerge'))
                elif a.model == 'B' and b.model == 'B' and a.total_mass <= 12 and b.total_mass <= 12:
                    cands.append((b, a, 'Bmerge'))
        cands.sort(key=lambda c: cur_sch.get(c[0].fid, {}).get('return', 0))
        for (src, tgt, kind) in cands[:400]:
            cand = merge_into(data, cur, src, tgt)
            if cand is None:
                continue
            m, s, v = eval_full(data, cand)
            if m is None or v > 0 or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            better = (m['energy'] < cur_met['energy'] - 1e-6 and m['makespan'] <= cur_met['makespan'] + 250.0) \
                or (m['makespan'] < cur_met['makespan'] - 1e-6 and m['energy'] <= cur_met['energy'] + 0.5)
            if better:
                log.append({'round': rnd + 1, 'op': kind, 'src': src.fid, 'tgt': tgt.fid,
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur, cur_met, cur_sch, cur_v = cand, m, s, v
                improved = True
                break
        print('round %d: mk=%.1f en=%.2f n=%d improved=%s' % (
            rnd + 1, cur_met['makespan'], cur_met['energy'], cur_met['flights'], improved), flush=True)
        if not improved:
            break
    print('\n结果: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard %s / 电池违规=%d' % (
        cur_met['flights'], cur_met['makespan'], cur_met['makespan'] / 60,
        cur_met['energy'], cur_met['hard_ok'], cur_v))
    if cur_met['energy'] < m0['energy'] - 1e-6 or cur_met['makespan'] < m0['makespan'] - 1e-6:
        json.dump({'best': {k: v for k, v in cur_met.items() if k != 'box_time'}, 'moves_log': log,
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
                  open(os.path.join(OUTD, 'p2v29_energy.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v29_energy.json')
    else:
        print('无改进，不保存')


if __name__ == '__main__':
    main()