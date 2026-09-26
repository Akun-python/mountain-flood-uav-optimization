# -*- coding: utf-8 -*-
"""v96：完工挤压专项——目标完工<6500。换型算子(新) + GAT + 多区合并，大轮数宽带beam。
换型：同容量趟换机型(C→B→A 优先省能耗, 容量满足时)——重分配池负载+压最后返场。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
N = {'A': 4, 'B': 2, 'C': 2}
MODEL_ORDER = {'C': 0, 'B': 1, 'A': 2}  # 换型方向：C→B→A（省能耗）

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

def retype_candidates(fls):
    """换型：每趟尝试换更小机型（C→B→A），容量可行则替换。"""
    cands = []
    for f in fls:
        m_new = {'C': 'B', 'B': 'A'}.get(f.model)
        if not m_new: continue
        nf = Flight(f.fid, f.route, m_new, data)
        if nf.is_feasible():
            def apply(fi=f, nf=nf, flist=fls):
                return [nf if x.fid == fi.fid else x for x in flist]
            cands.append(('retype', f.fid, f.model, m_new, apply))
    return cands

starts = []
d = json.load(open(os.path.join(OUTD, 'p2v88_fleet23.json'), encoding='utf-8'))
for s in d['solutions']:
    if s['flights'] in (23, 24, 25):
        starts.append([Flight(f['fid'], [(s2, list(bs)) for s2, bs in f['route']], f['model'], data) for f in s['solution']])
starts.append(load('p2v89_champion25.json'))
beam = []
seen = set()
for fls in starts:
    r = evalf(fls)
    if r: beam.append((r[0], r[1], len(fls), fls))
beam.sort(key=lambda t: (t[0], t[1], t[2]))
best_mk = (beam[0][0], beam[0][1], beam[0][3])
best_en_under6571 = None
t0 = time.time()
for rnd in range(300):
    nxt = []
    for mk, en, n, fls in beam:
        for tag, fa_id, fb_id, nf in mz_candidates(fls):
            nfl = [f for f in fls if f.fid not in (fa_id, fb_id)] + [nf]
            r = evalf(nfl)
            if r is None: continue
            key = (round(r[0]/5), round(r[1]*20))
            if key in seen: continue
            seen.add(key)
            if r[0] <= mk + 1500: nxt.append((r[0], r[1], len(nfl), nfl))
        for tag, fid, mo, mn, apply in retype_candidates(fls):
            imp = apply()
            r = evalf(imp)
            if r is None: continue
            key = (round(r[0]/5), round(r[1]*20))
            if key in seen: continue
            seen.add(key)
            if r[0] <= mk + 1500: nxt.append((r[0], r[1], len(imp), imp))
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 20)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            key = (round(r[0]/5), round(r[1]*20))
            if key in seen: continue
            seen.add(key)
            if r[0] <= mk + 1500: nxt.append((r[0], r[1], len(imp), imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[0], t[1]))
    beam = nxt[:14]
    for mk2, en2, n2, fls2 in beam:
        if mk2 < best_mk[0] - 0.5:
            best_mk = (mk2, en2, fls2)
            print('r%d: ★完工 mk=%.1f en=%.2f 架%d (%.0fs)' % (rnd, mk2, en2, n2, time.time()-t0), flush=True)
        if mk2 <= 6571.4 and (best_en_under6571 is None or en2 < best_en_under6571[0]):
            best_en_under6571 = (en2, mk2, n2, fls2)
            print('r%d: ★完工≤6571 能耗 mk=%.1f en=%.2f 架%d' % (rnd, mk2, en2, n2), flush=True)
    if rnd % 49 == 48:
        print('  ... r%d 覆盖%d best=%.1f (%.0fs)' % (rnd, len(seen), best_mk[0], time.time()-t0), flush=True)
print('=== 最终 ===')
print('完工最优: mk=%.1f(%.2fmin) en=%.2f 架%d (%s)' % (best_mk[0], best_mk[0]/60, best_mk[1], len(best_mk[2]), '★<6571!' if best_mk[0] < 6571 else '未超越'))
if best_en_under6571:
    print('完工≤6571 能耗最优: en=%.2f mk=%.1f 架%d' % (best_en_under6571[0], best_en_under6571[1], best_en_under6571[2]))
    json.dump({'best': {'makespan': best_en_under6571[1], 'energy': best_en_under6571[0], 'flights': best_en_under6571[2]},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in best_en_under6571[3]]},
              open(os.path.join(OUTD, 'p2v96_en6571.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v96_en6571.json')
if best_mk[0] < 6571:
    json.dump({'best': {'makespan': best_mk[0], 'energy': best_mk[1], 'flights': len(best_mk[2])},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in best_mk[2]]},
              open(os.path.join(OUTD, 'p2v96_mk_best.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v96_mk_best.json')
print('覆盖 %d (%.0fs)' % (len(seen), time.time()-t0))


