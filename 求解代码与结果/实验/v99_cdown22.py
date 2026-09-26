# -*- coding: utf-8 -*-
"""v99：22架 C池降载专项——A池(4642)吸 C池(6299)的 S007/S008 箱，目标C≤5990 → 完工<6600。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
N = {'A': 4, 'B': 2, 'C': 2}

def load(p, n=None):
    d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
    if n:
        return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d[n]['solution']]
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]

def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']

def pool(fls):
    pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    for f in fls: pt[f.model] += f.duration()
    return {g: pt[g] / N[g] for g in 'ABC'}

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

fls0 = load('p2v97_lowfleet.json', '22')
r0 = evalf(fls0)
pl = pool(fls0)
print('起点: 22架 mk=%.1f en=%.2f 池A%.0f/B%.0f/C%.0f' % (r0[0], r0[1], pl['A'], pl['B'], pl['C']), flush=True)
t0 = time.time()
beam = [(r0[0], r0[1], fls0)]
seen = set()
best = (r0[0], r0[1], fls0)
for rnd in range(120):
    nxt = []
    for mk, en, fls in beam:
        for tag, fa_id, fb_id, nf in mz_candidates(fls):
            nfl = [f for f in fls if f.fid not in (fa_id, fb_id)] + [nf]
            r = evalf(nfl)
            if r is None: continue
            key = round(r[0]/10)
            if key in seen: continue
            seen.add(key)
            if r[0] <= mk + 1500: nxt.append((r[0], r[1], nfl))
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 26)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            if len(imp) != 22: continue
            key = round(r[0]/10)
            if key in seen: continue
            seen.add(key)
            if r[0] <= mk + 1500: nxt.append((r[0], r[1], imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[0], t[1]))
    beam = nxt[:12]
    for mk2, en2, fls2 in beam:
        if mk2 < best[0] - 0.5:
            best = (mk2, en2, fls2)
            pl2 = pool(fls2)
            print('r%d: ★22架 mk=%.1f en=%.2f 池A%.0f/B%.0f/C%.0f (%.0fs)' % (rnd, mk2, en2, pl2['A'], pl2['B'], pl2['C'], time.time()-t0), flush=True)
print('=== 最终 ===')
mk, en, fls = best
pl = pool(fls)
print('22架最优: mk=%.1f(%.2fmin) en=%.2f 池A%.0f/B%.0f/C%.0f (%s vs 起点6993.3 / 冠军6571.4)' % (
    mk, mk/60, en, pl['A'], pl['B'], pl['C'], '%+d' % (mk-6993.3)))
json.dump({'best': {'makespan': mk, 'energy': en, 'flights': len(fls)},
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]},
          open(os.path.join(OUTD, 'p2v99_best22.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p2v99_best22.json | 覆盖 %d (%.0fs)' % (len(seen), time.time()-t0))
