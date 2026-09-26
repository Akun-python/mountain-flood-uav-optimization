# -*- coding: utf-8 -*-
"""v100：能耗优先低架次精炼——19/20/21/22/23 架能耗最小化（完工≤8000接受带）。
双档记录：完工≤6600 档能耗最优（25架69.77 挑战）+ 完工≤8000 档能耗最优（Tabu 62.46@21 挑战）。"""
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
best_le6600 = None
best_le8000 = None
for b in beam:
    n = b[2]
    if n not in best_by_n or b[1] < best_by_n[n][0] - 0.01: best_by_n[n] = (b[1], b[0], b[3])
    if b[0] <= 6600 and (best_le6600 is None or b[1] < best_le6600[0]): best_le6600 = (b[1], b[0], b[3])
    if b[0] <= 8000 and (best_le8000 is None or b[1] < best_le8000[0]): best_le8000 = (b[1], b[0], b[3])
t0 = time.time()
for rnd in range(160):
    nxt = []
    for mk, en, n, fls in beam:
        for tag, fa_id, fb_id, nf in mz_candidates(fls):
            nfl = [f for f in fls if f.fid not in (fa_id, fb_id)] + [nf]
            r = evalf(nfl)
            if r is None: continue
            key = (len(nfl), round(r[0]/10), round(r[1]*20))
            if key in seen: continue
            seen.add(key)
            if 18 <= len(nfl) <= 24 and r[0] <= 8000: nxt.append((r[0], r[1], len(nfl), nfl))
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 26)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            if 18 > len(imp) or len(imp) > 24: continue
            key = (len(imp), round(r[0]/10), round(r[1]*20))
            if key in seen: continue
            seen.add(key)
            if r[0] <= 8000: nxt.append((r[0], r[1], len(imp), imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[1], t[0], t[2]))
    beam = nxt[:14]
    improved = False
    for mk2, en2, n2, fls2 in beam:
        if n2 not in best_by_n or en2 < best_by_n[n2][0] - 0.01:
            best_by_n[n2] = (en2, mk2, fls2); improved = True
        if mk2 <= 6600 and (best_le6600 is None or en2 < best_le6600[0]):
            best_le6600 = (en2, mk2, fls2); improved = True
            print('r%d: ★完工≤6600 能耗 %.2f mk=%.1f 架%d (%.0fs)' % (rnd, en2, mk2, n2, time.time()-t0), flush=True)
        if mk2 <= 8000 and (best_le8000 is None or en2 < best_le8000[0]):
            best_le8000 = (en2, mk2, fls2); improved = True
            print('r%d: ★完工≤8000 能耗 %.2f mk=%.1f 架%d' % (rnd, en2, mk2, n2), flush=True)
    if rnd % 39 == 39:
        print('  ... r%d 覆盖%d (%.0fs)' % (rnd, len(seen), time.time()-t0), flush=True)
print('=== 各架数能耗最优 (能耗/完工) ===')
out = {}
for n in sorted(best_by_n):
    en, mk, fls = best_by_n[n]
    print('  %d架: en=%.2f mk=%.1f(%.2fmin)' % (n, en, mk, mk/60))
    out[n] = {'energy': en, 'makespan': mk, 'flights': len(fls),
              'solution': [{'fid': f.fid, 'model': f.model,
                            'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]}
print('完工≤6600 能耗最优: en=%.2f mk=%.1f 架%d' % (best_le6600[0], best_le6600[1], len(best_le6600[2])))
print('完工≤8000 能耗最优: en=%.2f mk=%.1f 架%d' % (best_le8000[0], best_le8000[1], len(best_le8000[2])))
json.dump({str(k): v for k, v in out.items()}, open(os.path.join(OUTD, 'p2v100_en_min.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p2v100_en_min.json | 覆盖 %d (%.0fs)' % (len(seen), time.time()-t0))
