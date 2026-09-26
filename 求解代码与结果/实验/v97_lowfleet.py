# -*- coding: utf-8 -*-
"""v97：低架次大幅精炼——从 23/25 架出发减架，19/20/21/22 架各完工最优（接受带+2500s 宽通道）。"""
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

starts = []
d = json.load(open(os.path.join(OUTD, 'p2v94_champion23.json'), encoding='utf-8'))
starts.append([Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']])
starts.append(load('p2v89_champion25.json'))
beam = []
seen = set()
for fls in starts:
    r = evalf(fls)
    if r: beam.append((r[0], r[1], len(fls), fls))
beam.sort(key=lambda t: (t[0], t[1], t[2]))
best_by_n = {}
for b in beam:
    if b[2] not in best_by_n: best_by_n[b[2]] = (b[0], b[1], b[3])
t0 = time.time()
for rnd in range(250):
    nxt = []
    for mk, en, n, fls in beam:
        for tag, fa_id, fb_id, nf in mz_candidates(fls):
            nfl = [f for f in fls if f.fid not in (fa_id, fb_id)] + [nf]
            r = evalf(nfl)
            if r is None: continue
            key = (round(r[0]/10), len(nfl), round(r[1]*10))
            if key in seen: continue
            seen.add(key)
            if 18 <= len(nfl) <= 23 and r[0] <= mk + 2500:
                nxt.append((r[0], r[1], len(nfl), nfl))
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 24)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            key = (round(r[0]/10), len(imp), round(r[1]*10))
            if key in seen: continue
            seen.add(key)
            if 18 <= len(imp) <= 23 and r[0] <= mk + 2500:
                nxt.append((r[0], r[1], len(imp), imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[0], t[1], t[2]))
    beam = nxt[:14]
    improved = False
    for mk2, en2, n2, fls2 in beam:
        if n2 not in best_by_n or (mk2, en2) < best_by_n[n2][:2]:
            best_by_n[n2] = (mk2, en2, fls2); improved = True
    if improved and rnd % 9 == 0:
        print('r%d: %s (%.0fs)' % (rnd, {k: '%.0f/%.2f' % (v[0], v[1]) for k, v in sorted(best_by_n.items())}, time.time()-t0), flush=True)
    if rnd % 49 == 48:
        print('  ... r%d 覆盖%d (%.0fs)' % (rnd, len(seen), time.time()-t0), flush=True)
print('=== 各架数最优 (完工/能耗) ===')
out = {}
for n in sorted(best_by_n):
    mk, en, fls = best_by_n[n]
    print('  %d架: mk=%.1f(%.2fmin) en=%.2f' % (n, mk, mk/60, en))
    out[n] = {'makespan': mk, 'energy': en, 'flights': len(fls),
              'solution': [{'fid': f.fid, 'model': f.model,
                            'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]}
json.dump({str(k): v for k, v in out.items()}, open(os.path.join(OUTD, 'p2v97_lowfleet.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p2v97_lowfleet.json | 覆盖 %d (%.0fs)' % (len(seen), time.time()-t0))
