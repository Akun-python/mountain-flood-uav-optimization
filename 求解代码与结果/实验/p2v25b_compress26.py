# -*- coding: utf-8 -*-
"""v25b 区一致完工压缩：从 26 架冠军（v24 plan-D, 6896.5s/70.86kWh）出发，
用 merge（同机多区合并）+ transfer（只移真实区条目）尝试再压完工。
全程严格 evaluate（区一致硬检查），只接受 hard True + 零迟到 + 完工下降。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

p2 = json.load(open(os.path.join(HERE, '..', 'results', 'p2_results.json'), encoding='utf-8'))
fls0 = [Flight(fj['fid'], [(s, list(bs)) for s, bs in fj['route']], fj['model'], data)
        for fj in p2['flights']]


def eval_full(data, fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None, None
    return evaluate(data, fl, sch), sch


m0, s0 = eval_full(data, fls0)
print('起点(v24 plan-D): %d 架 / mk %.1f / %.2f kWh / hard %s / tardy %.3f' % (
    len(fls0), m0['makespan'], m0['energy'], m0['hard_ok'], m0['tardy_w']))

cur = fls0
cur_met, cur_sch = m0, s0
log = []
for rnd in range(14):
    improved = False
    # 1) merge：同机型、route 区不重叠、时间相邻（gap <= 1200s）
    fls = sorted(cur, key=lambda f: cur_sch[f.fid]['return'])
    cand_list = []
    for i in range(len(fls)):
        for j in range(len(fls)):
            if i == j:
                continue
            a, b = fls[i], fls[j]
            if a.model != b.model or set(s for s, _ in a.route) & set(s for s, _ in b.route):
                continue
            gap = cur_sch[b.fid]['start'] - cur_sch[a.fid]['return']
            if 0 <= gap <= 1200:
                cand_list.append((a, b))
    for (a, b) in cand_list[:100]:
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
        if m['makespan'] < cur_met['makespan'] - 1e-6:
            log.append({'round': rnd + 1, 'op': 'merge', 'flights': (a.fid, b.fid),
                        'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3), 'n': m['flights']})
            cur, cur_met, cur_sch = fl, m, s
            improved = True
            break
    if improved:
        continue
    # 2) transfer：把尾架次箱移到同区更早架次（区一致保持）
    tail = [fid for fid, sch in cur_sch.items() if sch['return'] > 6300]
    done = False
    for f in cur:
        if f.fid not in tail:
            continue
        for sid, bs in list(f.route):
            for g in cur:
                if g.fid == f.fid:
                    continue
                same_zone = any(s == sid for s, _ in g.route)
                for gb in list(bs):
                    fl = clone_flights(cur)
                    ga = next(x for x in fl if x.fid == f.fid)
                    gb_ = next(x for x in fl if x.fid == g.fid)
                    for i, (s2, b2) in enumerate(ga.route):
                        if s2 == sid and gb in b2:
                            b2.remove(gb)
                            if not b2:
                                del ga.route[i]
                            break
                    normalize_flight(ga, data)
                    if not ga.route:
                        fl = [x for x in fl if x.fid != ga.fid]
                    elif not ga.is_feasible():
                        continue
                    tgt = None
                    for i, (s2, b2) in enumerate(gb_.route):
                        if s2 == sid:
                            b2.append(gb)
                            tgt = gb_
                            break
                    if tgt is None:
                        gb_.route.append((sid, [gb]))
                        normalize_flight(gb_, data)
                    else:
                        normalize_flight(gb_, data)
                    if not gb_.is_feasible():
                        continue
                    m, s = eval_full(data, fl)
                    if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                        continue
                    if m['makespan'] < cur_met['makespan'] - 1e-6:
                        log.append({'round': rnd + 1, 'op': 'transfer', 'box': gb,
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
    if improved:
        continue
    # 3) split：把链尾长单区架次拆成两趟（并行早班），区一致保持
    tail = sorted([f for f in cur if len(f.route) == 1 and cur_sch[f.fid]['return'] > 5600],
                  key=lambda f: cur_sch[f.fid]['return'], reverse=True)
    for f in tail[:5]:
        if f.nbox < 2:
            continue
        sid, bs = f.route[0]
        half = f.nbox // 2
        if half < 1:
            continue
        fl = clone_flights(cur)
        fa = next(x for x in fl if x.fid == f.fid)
        fa.route = [(sid, list(bs[:half]))]
        normalize_flight(fa, data)
        if not fa.is_feasible():
            continue
        newid = max(x.fid for x in fl) + 1
        fb = Flight(newid, [(sid, list(bs[half:]))], f.model, data)
        if not fb.is_feasible():
            continue
        fl.append(fb)
        m, s = eval_full(data, fl)
        if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
            continue
        if m['makespan'] < cur_met['makespan'] - 1e-6:
            log.append({'round': rnd + 1, 'op': 'split', 'flight': f.fid, 'n_after': m['flights'],
                        'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
            cur, cur_met, cur_sch = fl, m, s
            improved = True
            break
    print('round %d: mk=%.1f en=%.2f n=%d improved=%s' % (
        rnd + 1, cur_met['makespan'], cur_met['energy'], cur_met['flights'], improved), flush=True)
    if not improved:
        break

print('\n结果: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard %s / 零迟到' % (
    cur_met['flights'], cur_met['makespan'], cur_met['makespan'] / 60,
    cur_met['energy'], cur_met['hard_ok']))
json.dump({'best': {k: v for k, v in cur_met.items() if k != 'box_time'}, 'moves_log': log,
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
          open(os.path.join(OUTD, 'p2v25b_compress26.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved -> 结果/进化_v25/p2v25b_compress26.json')