# -*- coding: utf-8 -*-
"""v25j 两阶段交替：从 v25i（25 架/7639s/78.88kWh）出发。
阶段 A 能耗合并（energy↓，完工允许 +400s）
阶段 B 完工压缩（makespan↓，能耗允许 +0.5kWh：merge/transfer 完工优先）
交替至双收敛，输出帕累托轨迹。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

d = json.load(open(os.path.join(OUTD, 'p2v25i_merge.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in d['solution']]


def eval_full(data, fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None, None
    return evaluate(data, fl, sch), sch


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
    m0, s0 = eval_full(data, fls)
    print('起点(v25i): %d 架 / mk %.1f / %.2f kWh' % (len(fls), m0['makespan'], m0['energy']), flush=True)
    cur, cur_met, cur_sch = fls, m0, s0
    log = []
    for rnd in range(40):
        # 阶段 A：能耗合并
        improved = False
        singles = [f for f in cur if len(f.route) == 1]
        cands = []
        for i in range(len(singles)):
            for j in range(len(singles)):
                if i == j:
                    continue
                a, b = singles[i], singles[j]
                if a.model == 'C' and b.model != 'C' and b.total_mass <= 45:
                    cands.append((b, a))
                elif a.model == 'C' and b.model == 'C' and a.total_mass <= 45:
                    cands.append((b, a))
        cands.sort(key=lambda c: cur_sch.get(c[0].fid, {}).get('return', 0))
        for (src, tgt) in cands[:300]:
            cand = merge_into(data, cur, src, tgt)
            if cand is None:
                continue
            m, s = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if m['energy'] < cur_met['energy'] - 1e-6 and m['makespan'] <= cur_met['makespan'] + 400.0:
                log.append({'round': rnd + 1, 'op': 'mergeA', 'src': src.fid, 'tgt': tgt.fid,
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur, cur_met, cur_sch = cand, m, s
                improved = True
                break
        if not improved:
            # 阶段 B：完工压缩（merge 完工降）
            fls_sorted = sorted(cur, key=lambda f: cur_sch[f.fid]['return'])
            done = False
            for i in range(len(fls_sorted)):
                for j in range(len(fls_sorted)):
                    if i == j:
                        continue
                    a, b = fls_sorted[i], fls_sorted[j]
                    if a.model != b.model:
                        continue
                    if set(s for s, _ in a.route) & set(s for s, _ in b.route):
                        continue
                    gap = cur_sch[b.fid]['start'] - cur_sch[a.fid]['return']
                    if not (0 <= gap <= 1500):
                        continue
                    fl = clone_flights(cur)
                    fa = next(x for x in fl if x.fid == a.fid)
                    fb = next(x for x in fl if x.fid == b.fid)
                    fa.route = [(s, list(bs)) for s, bs in a.route] + [(s, list(bs)) for s, bs in b.route]
                    normalize_flight(fa, data)
                    if not fa.is_feasible():
                        continue
                    fl = [x for x in fl if x.fid != b.fid]
                    m, s = eval_full(data, fl)
                    if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                        continue
                    if m['makespan'] < cur_met['makespan'] - 1e-6 and m['energy'] <= cur_met['energy'] + 0.5:
                        log.append({'round': rnd + 1, 'op': 'mergeB', 'flights': (a.fid, b.fid),
                                    'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                        cur, cur_met, cur_sch = fl, m, s
                        improved = True
                        done = True
                        break
                if done:
                    break
        print('round %d: mk=%.1f en=%.2f n=%d improved=%s' % (
            rnd + 1, cur_met['makespan'], cur_met['energy'], cur_met['flights'], improved), flush=True)
        if not improved:
            break
    print('\n结果: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard %s' % (
        cur_met['flights'], cur_met['makespan'], cur_met['makespan'] / 60,
        cur_met['energy'], cur_met['hard_ok']))
    json.dump({'best': {k: v for k, v in cur_met.items() if k != 'box_time'}, 'moves_log': log,
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v25j_dual.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p2v25j_dual.json')


if __name__ == '__main__':
    main()