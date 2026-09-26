# -*- coding: utf-8 -*-
"""v109c：完工≤6571.4 前提下的能耗最小化——合并仅限 A/B 池与轻区（C 池 6 趟不变）。
目标：能耗 <65.97（对方22架能耗）同时完工 ≤6571.4。"""
import sys, os, json, time, math
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
CAP = {'A': 25, 'B': 30, 'C': 80}
CZ = {'S001','S002','S003','S004','S005','S006','S007','S008','S009','S010','S011','S012','S013','S014','S015'}
C_ZONES = {'S001','S003','S004','S007','S008'}   # 25架冠军C池服务区(重区)
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
    o = data.centers['O01']; ref = (o['lon'], o['lat'])
    fid_new = max(f.fid for f in fls) + 1
    for src in [f for f in fls if len(set(z for z, _ in f.route)) == 1]:
        z_src = [z for z, _ in src.route][0]
        if z_src in C_ZONES: continue            # C 池区不动
        w_src = sum(data.boxes[b]['mass'] for b in src.box_ids)
        for tgt in fls:
            if tgt.fid == src.fid: continue
            if z_src in [z for z, _ in tgt.route]: continue
            if tgt.model == 'C': continue        # 不并入 C（避免加长 C 池）
            w_tgt = sum(data.boxes[b]['mass'] for b in tgt.box_ids)
            if w_tgt + w_src > CAP[tgt.model]: continue
            bmap = {z: list(bs) for z, bs in tgt.route}
            zs = sorted([z for z, _ in tgt.route] + [z_src], key=lambda z: angle_key(z, ref))
            route = [(z, list(src.box_ids) if z == z_src else bmap[z]) for z in zs]
            nf = Flight(fid_new, route, tgt.model, data)
            if not nf.is_feasible(): continue
            gain = src.duration() + tgt.duration() - nf.duration()
            if gain < 60: continue
            cands.append((gain, src.fid, tgt.fid, nf))
    return cands
def apply(fls, cand):
    gain, sfid, tfid, nf = cand
    return [nf if f.fid == tfid else f for f in fls if f.fid != sfid]
r0 = evalf(fls0)
print('起点: 25架 mk=%.1f en=%.2f 总飞%.0f' % (r0[0], r0[1], r0[2]), flush=True)
t0 = time.time()
beam = [(r0[0], r0[1], fls0)]
seen = set()
best = (r0[0], r0[1], fls0)
for rnd in range(60):
    nxt = []
    for mk, en, fls in beam:
        cands = sorted(merge_cands(fls), key=lambda c: -c[0])
        for cand in cands[:10]:
            nfl = apply(fls, cand)
            key = tuple(sorted(f.fid for f in nfl))
            if key in seen: continue
            seen.add(key)
            r = evalf(nfl)
            if r is None: continue
            if r[0] > 6571.4 + 5: continue      # 完工不回退
            nxt.append((r[0], r[1], nfl))
    if not nxt:
        print('r%d: 无候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[0], t[1]))
    beam = nxt[:10]
    for mk2, en2, fls2 in beam:
        if en2 < best[1] - 0.01:
            best = (mk2, en2, fls2)
            tf = sum(f.duration() for f in fls2)
            print('r%d: ★%d架 mk=%.1f en=%.2f 总飞%.0f (%.0fs)' % (rnd, len(fls2), mk2, en2, tf, time.time()-t0), flush=True)
print('=== 最终 ===')
mk, en, fls = best
print('%d架 mk=%.1f en=%.2f 总飞%.0f (vs 冠军6571.4/69.77/45312; 对方22架5749.5/65.97)' % (len(fls), mk, en, sum(f.duration() for f in fls)))
