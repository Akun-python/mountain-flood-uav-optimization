# -*- coding: utf-8 -*-
"""v88：23/24/25 架专用深扫——宽带 beam(mz+GAT算子, 接受完工+2500s) 从多起点出发,
按架数分组报告各架数(22-26)的完工/能耗帕累托——补齐帕累托面缺失段。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()

def load(p):
    d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]

def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']

def mz_candidates(fls):
    cands = []
    fid_new = max(x.fid for x in fls) + 1
    for fa, fb in itertools.combinations(fls, 2):
        if fa.model != fb.model: continue
        union_z = set(s for s, _ in fa.route) | set(s for s, _ in fb.route)
        if len(union_z) > 4 or len(union_z) < 2: continue
        boxes_all = [b for s2, bs2 in fa.route for b in bs2] + [b for s2, bs2 in fb.route for b in bs2]
        route = []
        for z in sorted(union_z):
            bs = [b for b in boxes_all if b.split('-')[0] == z]
            if bs: route.append((z, bs))
        nf = Flight(fid_new, route, fa.model, data)
        if nf.is_feasible():
            cands.append(('mz', fa.fid, fb.fid, nf))
    return cands

# 多起点：22架/21架(能耗端) + 26架/27架(完工端) + 25架旧方案
starts = []
for p in ['p2v75_champion.json', 'p2v85_best.json']:
    starts.append(load(p))
# v75 池里的 22 架等：尝试加载
for p in ['p2v75_pareto.json']:
    try:
        d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
        for sol in d.get('solutions', []):
            if sol.get('flights', 0) in (21, 22, 23, 24, 25):
                starts.append([Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in sol['solution']])
    except Exception as e:
        print('pareto 加载跳过:', e)

beam = []
seen = set()
for fls in starts:
    r = evalf(fls)
    if r:
        beam.append((r[0], r[1], len(fls), fls))
beam.sort()
print('起点: %d解 架数%s 最佳mk=%.1f' % (len(beam), sorted(set(b[2] for b in beam)), beam[0][0]), flush=True)
t0 = time.time()
best_by_n = {}
for b in beam:
    key = b[2]
    if key not in best_by_n or (b[0], b[1]) < best_by_n[key]:
        best_by_n[key] = (b[0], b[1], b[3])
ACCEPT = 2500
for rnd in range(60):
    nxt = []
    for mk, en, n, fls in beam:
        for tag, fa_id, fb_id, nf in mz_candidates(fls):
            nfl = [f for f in fls if f.fid not in (fa_id, fb_id)] + [nf]
            r = evalf(nfl)
            if r is None: continue
            key = (round(r[0]), len(nfl), round(r[1]*10))
            if key in seen: continue
            seen.add(key)
            if r[0] <= mk + ACCEPT: nxt.append((r[0], r[1], len(nfl), nfl))
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 18)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            key = (round(r[0]), len(imp), round(r[1]*10))
            if key in seen: continue
            seen.add(key)
            if r[0] <= mk + ACCEPT: nxt.append((r[0], r[1], len(imp), imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[0], t[1], t[2]))
    beam = nxt[:10]
    for mk, en, n, fls in beam:
        if n not in best_by_n or (mk, en) < best_by_n[n][:2]:
            best_by_n[n] = (mk, en, fls)
    if rnd % 14 == 13:
        print('r%d: 覆盖%d 各架数最佳 %s (%.0fs)' % (rnd, len(seen),
              {k: '%.0f/%.2f' % (v[0], v[1]) for k, v in sorted(best_by_n.items())}, time.time()-t0), flush=True)
print('=== 各架数最优 (完工/能耗) ===')
for n in sorted(best_by_n):
    mk, en, fls = best_by_n[n]
    print('  %2d架: mk=%.1f(%.2fmin) en=%.2f' % (n, mk, mk/60, en))
print('覆盖 %d 候选 (%.0fs)' % (len(seen), time.time()-t0))
json.dump({'best_by_n': {str(k): {'makespan': v[0], 'energy': v[1], 'flights': len(v[2])} for k, v in best_by_n.items()},
           'solutions': [{'flights': len(v[2]), 'makespan': v[0], 'energy': v[1],
                          'solution': [{'fid': f.fid, 'model': f.model,
                                        'route': [(s, list(bs)) for s, bs in f.route]} for f in v[2]]}
                         for k, v in sorted(best_by_n.items()) if k in (22, 23, 24, 25)]},
          open(os.path.join(OUTD, 'p2v88_fleet23.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p2v88_fleet23.json')
