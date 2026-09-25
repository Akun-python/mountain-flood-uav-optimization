# -*- coding: utf-8 -*-
"""v25e 能耗-完工帕累托探索（严格口径）：从 v25b 28 架解（7394.9s/83.12kWh）出发，
在完工上限 7450s 内最小化能耗。
算子：merge（省起飞/返场）+ 换型（低载 C->B/A）+ transfer（箱移到更高效架次）。
接受：(energy 下降) 且 (makespan <= 7450) 且 hard True 零迟到。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()
CAP = float(sys.argv[1]) if len(sys.argv) > 1 else 7450.0

d = json.load(open(os.path.join(OUTD, 'p2v25b_compress26.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in d['solution']]


def eval_full(data, fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None, None
    return evaluate(data, fl, sch), sch


m0, s0 = eval_full(data, fls)
print('起点(v25b): %d 架 / mk %.1f / %.2f kWh / hard %s' % (
    len(fls), m0['makespan'], m0['energy'], m0['hard_ok']))

cur, cur_met, cur_sch = fls, m0, s0
log = []
for rnd in range(12):
    improved = False
    # 1) 换型：低载 C/B 单区架次 -> 更小型号（质量<=上限）
    for f in cur:
        if len(f.route) != 1:
            continue
        sid, bs = f.route[0]
        mass = f.total_mass
        for newm in (('C', 'B'), ('B', 'A'), ('C', 'A')):
            if f.model != newm[0]:
                continue
            q = data.uav_types[newm[1]]['Q']
            if mass > q + 1e-9:
                continue
            fl = clone_flights(cur)
            fa = next(x for x in fl if x.fid == f.fid)
            fa.model = newm[1]
            normalize_flight(fa, data)
            if not fa.is_feasible():
                continue
            m, s = eval_full(data, fl)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6 and m['makespan'] <= CAP):
                continue
            if m['energy'] < cur_met['energy'] - 1e-6:
                log.append({'round': rnd + 1, 'op': 'retype', 'flight': f.fid, 'to': newm[1],
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur, cur_met, cur_sch = fl, m, s
                improved = True
                break
        if improved:
            break
    if improved:
        continue
    # 2) merge：同机型相邻架次合并（省一次起飞/返场/准备）
    fls_sorted = sorted(cur, key=lambda f: cur_sch[f.fid]['return'])
    done = False
    for i in range(len(fls_sorted)):
        for j in range(len(fls_sorted)):
            if i == j:
                continue
            a, b = fls_sorted[i], fls_sorted[j]
            if a.model != b.model or set(s for s, _ in a.route) & set(s for s, _ in b.route):
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
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6 and m['makespan'] <= CAP):
                continue
            if m['energy'] < cur_met['energy'] - 1e-6:
                log.append({'round': rnd + 1, 'op': 'merge', 'flights': (a.fid, b.fid),
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur, cur_met, cur_sch = fl, m, s
                improved = True
                done = True
                break
        if done:
            break
    if improved:
        continue
    # 3) transfer：把 C 机架次箱移给 B/A（更高效路径，若可省能耗）
    cfs = [f for f in cur if f.model == 'C']
    done = False
    for f in cfs:
        for sid, bs in list(f.route):
            for g in cur:
                if g.fid == f.fid or g.model != 'B':
                    continue
                if any(s2 == sid for s2, _ in g.route):
                    continue
                for b in list(bs):
                    fl = clone_flights(cur)
                    ga = next(x for x in fl if x.fid == f.fid)
                    gb = next(x for x in fl if x.fid == g.fid)
                    for i, (s2, b2) in enumerate(ga.route):
                        if s2 == sid and b in b2:
                            b2.remove(b)
                            if not b2:
                                del ga.route[i]
                            break
                    normalize_flight(ga, data)
                    if not ga.route:
                        fl = [x for x in fl if x.fid != ga.fid]
                    elif not ga.is_feasible():
                        continue
                    gb.route.append((sid, [b]))
                    normalize_flight(gb, data)
                    if not gb.is_feasible():
                        continue
                    m, s = eval_full(data, fl)
                    if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6 and m['makespan'] <= CAP):
                        continue
                    if m['energy'] < cur_met['energy'] - 1e-6:
                        log.append({'round': rnd + 1, 'op': 'transfer_CtoB', 'box': b,
                                    'from': f.fid, 'to': g.fid,
                                    'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                        cur, cur_met, cur_sch = fl, m, s
                        improved = True
                        done = True
                        break
                if done:
                    break
            if done:
                break
    print('round %d: mk=%.1f en=%.2f n=%d improved=%s' % (
        rnd + 1, cur_met['makespan'], cur_met['energy'], cur_met['flights'], improved), flush=True)
    if not improved:
        break

print('\n结果: %d 架 / mk %.1f s / %.2f kWh / hard %s' % (
    cur_met['flights'], cur_met['makespan'], cur_met['energy'], cur_met['hard_ok']))
json.dump({'best': {k: v for k, v in cur_met.items() if k != 'box_time'}, 'moves_log': log, 'cap': CAP,
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
          open(os.path.join(OUTD, 'p2v25e_pareto_%d.json' % int(CAP)), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved -> 结果/进化_v25/p2v25e_pareto_%d.json' % int(CAP))