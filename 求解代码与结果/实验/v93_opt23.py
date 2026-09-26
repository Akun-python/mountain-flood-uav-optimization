# -*- coding: utf-8 -*-
"""v93：23 架专用优化——目标把 B 池(6560)降回 ≤C 池、C 池(6087)降回 ≤5990。
算子：多区合并 + GAT(迁移/换型/拆分) + 专门轻载B趟(B S011)→A 迁移。架次 22-24 浮动，记录 23 最优。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
N = {'A': 4, 'B': 2, 'C': 2}

def load(p):
    d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]

def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']

def pool_load(fls):
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

# 起点池：v88 的 23/24 架 + 25 架冠军（减架路径）
starts = []
d = json.load(open(os.path.join(OUTD, 'p2v88_fleet23.json'), encoding='utf-8'))
for s in d['solutions']:
    if s['flights'] in (23, 24):
        starts.append([Flight(f['fid'], [(s2, list(bs)) for s2, bs in f['route']], f['model'], data) for f in s['solution']])
starts.append(load('p2v89_champion25.json'))
beam = []
seen = set()
for fls in starts:
    r = evalf(fls)
    if r: beam.append((r[0], r[1], len(fls), fls))
beam.sort()
best23 = None
t0 = time.time()
for rnd in range(80):
    nxt = []
    for mk, en, n, fls in beam:
        for tag, fa_id, fb_id, nf in mz_candidates(fls):
            nfl = [f for f in fls if f.fid not in (fa_id, fb_id)] + [nf]
            r = evalf(nfl)
            if r is None: continue
            key = (round(r[0]), len(nfl), round(r[1]*10))
            if key in seen: continue
            seen.add(key)
            if 21 <= len(nfl) <= 24 and r[0] <= mk + 1200:
                nxt.append((r[0], r[1], len(nfl), nfl))
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 22)):
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
            if 21 <= len(imp) <= 24 and r[0] <= mk + 1200:
                nxt.append((r[0], r[1], len(imp), imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[0], t[1]))
    beam = nxt[:12]
    for mk2, en2, n2, fls2 in beam:
        if n2 == 23 and (best23 is None or mk2 < best23[0]):
            best23 = (mk2, en2, fls2)
            pl = pool_load(fls2)
            print('r%d: ★23架 mk=%.1f en=%.2f 池A%.0f/B%.0f/C%.0f (%.0fs)' % (
                rnd, mk2, en2, pl['A'], pl['B'], pl['C'], time.time()-t0), flush=True)
    if rnd % 19 == 18:
        print('  ... r%d 覆盖%d (%.0fs)' % (rnd, len(seen), time.time()-t0), flush=True)
print('=== 结果 ===')
if best23:
    mk, en, fls = best23
    pl = pool_load(fls)
    print('23架最优: mk=%.1f(%.2fmin) en=%.2f 池A%.0f/B%.0f/C%.0f 趟%d' % (mk, mk/60, en, pl['A'], pl['B'], pl['C'], len(fls)))
    print('vs 当前23架 6680.6: %+ds | vs 25架冠军 6571.4: %+ds' % (mk - 6680.6, mk - 6571.4))
    json.dump({'best': {'makespan': mk, 'energy': en, 'flights': len(fls)},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]},
              open(os.path.join(OUTD, 'p2v93_best23.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v93_best23.json')
print('覆盖 %d (%.0fs)' % (len(seen), time.time()-t0))
