# -*- coding: utf-8 -*-
"""v86：宽带 beam + 多区合并算子（mz）——接受完工+2500s 中间态，30轮×beam10。
v74 beam 只用单区算子；mz 合并是全新算子，搜索空间未探索。目标 <6571.4。"""
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
    """多区合并：同机型两趟（含多区趟本身）→ 合并为多区趟。"""
    cands = []
    fid_new = max(x.fid for x in fls) + 1
    for fa, fb in itertools.combinations(fls, 2):
        if fa.model != fb.model: continue
        union_z = set(s for s, _ in fa.route) | set(s for s, _ in fb.route)
        if len(union_z) > 4 or len(union_z) < 2: continue
        boxes_all = [b for s2, bs2 in fa.route for b in bs2] + [b for s2, bs2 in fb.route for b in bs2]
        # 每段箱必须属于该区
        route = []
        for z in sorted(union_z):
            bs = [b for b in boxes_all if b.split('-')[0] == z]
            if bs: route.append((z, bs))
        nf = Flight(fid_new, route, fa.model, data)
        if nf.is_feasible():
            cands.append(('mz', fa.fid, fb.fid, nf))
    return cands

starts = [load('p2v75_champion.json'), load('p2v84_multizone.json')]
beam = []
seen = set()
for fls in starts:
    r = evalf(fls)
    if r: beam.append((r[0], r[1], fls))
beam.sort()
best = beam[0]
print('起点: %d解 最佳 mk=%.1f en=%.2f (%.0fs)' % (len(beam), best[0], best[1], 0), flush=True)
t0 = time.time()
for rnd in range(30):
    nxt = []
    for mk, en, fls in beam:
        # 1) 多区合并候选
        for tag, fa_id, fb_id, nf in mz_candidates(fls):
            if len(fls) <= 21: continue
            nfl = [f for f in fls if f.fid not in (fa_id, fb_id)] + [nf]
            r = evalf(nfl)
            if r is None: continue
            key = (round(r[0]), len(nfl))
            if key in seen: continue
            seen.add(key)
            if r[0] <= best[0] + 2500: nxt.append((r[0], r[1], nfl))
        # 2) GAT 单区算子候选
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 20)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            key = (round(r[0]), len(imp))
            if key in seen: continue
            seen.add(key)
            if r[0] <= best[0] + 2500: nxt.append((r[0], r[1], imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True)
        break
    nxt.sort(key=lambda t: (t[0], t[1], len(t[2])))
    beam = nxt[:10]
    if beam[0][0] < best[0] - 0.5:
        best = beam[0]
        print('r%d: ★mk=%.1f en=%.2f 架%d (%.0fs)' % (rnd, best[0], best[1], len(best[2]), time.time()-t0), flush=True)
    elif rnd % 9 == 8:
        print('r%d: 当前最佳 mk=%.1f 覆盖%d (%.0fs)' % (rnd, beam[0][0], len(seen), time.time()-t0), flush=True)
print('最终: mk=%.1f en=%.2f 架%d | 覆盖%d' % (best[0], best[1], len(best[2]), len(seen)))
mk0 = evalf(load('p2v75_champion.json'))[0]
print('vs 冠军 6571.4: %s' % ('★超越!' if best[0] < mk0 - 0.5 else '未超越'))
if best[0] < mk0 - 0.5:
    json.dump({'best': {'makespan': best[0], 'energy': best[1], 'flights': len(best[2])},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in best[2]]},
              open(os.path.join(OUTD, 'p2v86_best.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('DONE %.0fs' % (time.time()-t0), flush=True)
