# -*- coding: utf-8 -*-
"""v105：能耗深度beam——多起点(25/23/20架)+250轮 能耗主键，目标21/20架能耗<66且完工≤7900。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()

def load(p, n=None):
    d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
    if n:
        return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d[n]['solution']]
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]

def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']

def mz_candidates(fls, k=2):
    cands = []
    fid_new = max(x.fid for x in fls) + 1
    for grp in itertools.combinations(fls, k):
        if len({g.model for g in grp}) != 1: continue
        union_z = set(s for g in grp for s, _ in g.route)
        if len(union_z) > 4 or len(union_z) < 2: continue
        boxes_all = [b for g in grp for s2, bs2 in g.route for b in bs2]
        route = []
        for z in sorted(union_z):
            bs = [b for b in boxes_all if b.split('-')[0] == z]
            if bs: route.append((z, bs))
        nf = Flight(fid_new, route, grp[0].model, data)
        if nf.is_feasible() and nf.duration() < sum(g.duration() for g in grp) - 50:
            cands.append(('mz%d' % k, [g.fid for g in grp], nf))
    return cands

starts = []
d = json.load(open(os.path.join(OUTD, 'p2v97_lowfleet.json'), encoding='utf-8'))
for n in ('20', '21'):
    starts.append([Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d[n]['solution']])
starts.append(load('p2v94_champion23.json'))
starts.append(load('p2v89_champion25.json'))
beam = []
seen = set()
for fls in starts:
    r = evalf(fls)
    if r: beam.append((r[0], r[1], len(fls), fls))
beam.sort(key=lambda t: (t[1], t[0], t[2]))
best_by_n = {}
for b in beam:
    n = b[2]
    if n not in best_by_n or b[1] < best_by_n[n][0] - 0.01: best_by_n[n] = (b[1], b[0], b[3])
t0 = time.time()
best21 = best_by_n.get(21); best20 = best_by_n.get(20)
for rnd in range(250):
    nxt = []
    for mk, en, n, fls in beam:
        for tag, gids, nf in mz_candidates(fls, 2) + mz_candidates(fls, 3):
            nfl = [f for f in fls if f.fid not in gids] + [nf]
            r = evalf(nfl)
            if r is None: continue
            if 19 > len(nfl) or len(nfl) > 25: continue
            key = (len(nfl), round(r[0]/20), round(r[1]*10))
            if key in seen: continue
            seen.add(key)
            if r[0] <= 7900: nxt.append((r[0], r[1], len(nfl), nfl))
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 30)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            if 19 > len(imp) or len(imp) > 25: continue
            key = (len(imp), round(r[0]/20), round(r[1]*10))
            if key in seen: continue
            seen.add(key)
            if r[0] <= 7900: nxt.append((r[0], r[1], len(imp), imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[1], t[0], t[2]))
    beam = nxt[:14]
    improved = False
    for mk2, en2, n2, fls2 in beam:
        if n2 not in best_by_n or en2 < best_by_n[n2][0] - 0.01:
            best_by_n[n2] = (en2, mk2, fls2); improved = True
            if n2 in (20, 21):
                print('r%d: ★%d架 en=%.2f mk=%.1f (%.0fs)' % (rnd, n2, en2, mk2, time.time()-t0), flush=True)
    if rnd % 59 == 59:
        print('  ... r%d 覆盖%d %s' % (rnd, len(seen), {k: '%.2f@%.0f' % (v[0], v[1]) for k, v in sorted(best_by_n.items()) if k in (19,20,21,22,23)}), flush=True)
print('=== 各架数能耗最优 (能耗@完工) ===')
out = {}
for n in sorted(best_by_n):
    en, mk, fls = best_by_n[n]
    print('  %d架: en=%.2f mk=%.1f(%.2fmin)' % (n, en, mk, mk/60))
    out[n] = {'energy': en, 'makespan': mk, 'flights': len(fls),
              'solution': [{'fid': f.fid, 'model': f.model,
                            'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]}
json.dump({str(k): v for k, v in out.items()}, open(os.path.join(OUTD, 'p2v105_en_deep.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p2v105_en_deep.json | 覆盖 %d (%.0fs)' % (len(seen), time.time()-t0))
