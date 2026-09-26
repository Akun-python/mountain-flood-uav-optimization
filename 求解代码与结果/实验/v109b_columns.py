# -*- coding: utf-8 -*-
"""v109b-fix：跨机型顺访合并列 beam——把任意单区趟并入另一趟顺访(容量/顺访/时限)。"""
import sys, os, json, itertools, time, math
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
CAP = {'A': 25, 'B': 30, 'C': 80}
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls0 = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy'], sum(f.duration() for f in fls)
def angle_key(z, ref):
    a = data.areas[z]
    return math.atan2(a['lat'] - ref[1], (a['lon'] - ref[0]) * math.cos(ref[1] * math.pi / 180))
def merge_cands(fls):
    cands = []
    o = data.centers['O01']
    ref = (o['lon'], o['lat'])
    fid_new = max(f.fid for f in fls) + 1
    for src in [f for f in fls if len(set(z for z, _ in f.route)) == 1]:
        z_src = [z for z, _ in src.route][0]
        w_src = sum(data.boxes[b]['mass'] for b in src.box_ids)
        for tgt in fls:
            if tgt.fid == src.fid: continue
            if z_src in [z for z, _ in tgt.route]: continue
            w_tgt = sum(data.boxes[b]['mass'] for b in tgt.box_ids)
            if w_tgt + w_src > CAP[tgt.model]: continue
            bmap = {z: list(bs) for z, bs in tgt.route}
            zs = sorted([z for z, _ in tgt.route] + [z_src], key=lambda z: angle_key(z, ref))
            route = [(z, list(src.box_ids) if z == z_src else bmap[z]) for z in zs]
            nf = Flight(fid_new, route, tgt.model, data)
            if not nf.is_feasible(): continue
            gain = src.duration() + tgt.duration() - nf.duration()
            if gain < 80: continue
            cands.append((gain, src.fid, tgt.fid, nf))
    return cands
def apply(fls, cand):
    gain, sfid, tfid, nf = cand
    return [nf if f.fid == tfid else f for f in fls if f.fid != sfid]
t0 = time.time()
beam = [(0.0, fls0)]
seen = set()
best = None
for rnd in range(40):
    nxt = []
    for cost, fls in beam:
        cands = sorted(merge_cands(fls), key=lambda c: -c[0])
        for cand in cands[:10]:
            nfl = apply(fls, cand)
            key = tuple(sorted(f.fid for f in nfl))
            if key in seen: continue
            seen.add(key)
            r = evalf(nfl)
            if r is None: continue
            nxt.append((cost + cand[0], nfl))
    if not nxt:
        print('r%d: 无合并候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: -t[0])
    beam = nxt[:8]
    for cost, fls in beam:
        r = evalf(fls)
        if best is None or r[1] < best[1]:
            best = (r, fls, cost)
            print('r%d: ★%d架 mk=%.1f en=%.2f 总飞%.0f 省%.0fs (%.0fs)' % (rnd, len(fls), r[0], r[1], r[2], cost, time.time()-t0), flush=True)
print('=== 最终 ===')
if best:
    r, fls, cost = best
    print('%d架 mk=%.1f(%.2fmin) en=%.2f 总飞%.0f (vs 冠军6571.4/69.77/45312)' % (len(fls), r[0], r[0]/60, r[1], r[2]))
