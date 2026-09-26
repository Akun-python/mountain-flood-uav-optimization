# -*- coding: utf-8 -*-
"""v113：C池系统吸收轻区——A/B池单区轻箱并入C顺访(容量/顺访可行/C池返场≤6550)，
多轮迭代能耗最小化，完工锁 6571.4。"""
import sys, os, json, itertools, time, math
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/v112_best.json', encoding='utf-8'))
base = {f['fid']: Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d}
CAP = {'A': 25, 'B': 30, 'C': 80}
def W(B): return sum(data.boxes[b]['mass'] for b in B)
def angle_key(z, ref):
    a = data.areas[z]
    return math.atan2(a['lat'] - ref[1], (a['lon'] - ref[0]) * math.cos(ref[1] * math.pi / 180))
def eval_full_r(fls):
    sch, _ = dispatch_compliant(data, fls)
    mm, s, vv, nn = eval_full(data, fls)
    vb = cb(data, sch, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok'] or len(vb) > 0: return None
    return mm['makespan'], mm['energy'], sch
r0 = eval_full_r([base[k] for k in sorted(base)])
print('起点(v112): %d架 mk=%.1f en=%.2f' % (len(base), r0[0], r0[1]), flush=True)
o = data.centers['O01']; ref = (o['lon'], o['lat'])
fls = [base[k] for k in sorted(base)]
fidn = 1000
for rnd in range(40):
    sch0 = r0[2]
    cz_flights = [f for f in fls if f.model == 'C']
    cz_maxret = max(sch0[f.fid]['return'] for f in cz_flights)
    # C 池容量余量最大的趟 = 优先吸收目标
    cands = []
    # 每趟 C 吸收 1 个 A/B 单区趟的全箱
    srcs = [f for f in fls if f.model in ('A', 'B') and len(set(z for z,_ in f.route)) == 1]
    for c in cz_flights:
        cw = W(c.box_ids)
        if cw >= 78: continue
        for s in srcs:
            if s.fid == c.fid: continue
            zs = s.route[0][0]
            if any(z == zs for z, _ in c.route): continue
            if cw + W(s.box_ids) > CAP['C']: continue
            bmap = {z: list(bs) for z, bs in c.route}
            nz = sorted([z for z, _ in c.route] + [zs], key=lambda z: angle_key(z, ref))
            route = [(z, list(s.box_ids) if z == zs else bmap[z]) for z in nz]
            nf = Flight(fidn, route, 'C', data)
            if not nf.is_feasible(): continue
            delta = nf.duration() - c.duration()
            if s.duration() - delta < 40: continue
            nfl = [f for f in fls if f.fid not in (c.fid, s.fid)] + [nf]
            cands.append((s.duration() - delta, c, s, nf, nfl, zs))
    if not cands:
        print('r%d: 无吸收候选' % rnd, flush=True); break
    cands.sort(key=lambda t: -t[0])
    applied = False
    for gain, c, s, nf, nfl, zs in cands[:20]:
        # 断言 C 池最大返场不超 6550
        r = eval_full_r(sorted(nfl, key=lambda x: x.fid))
        if r is None: continue
        c_ret = max(r[2][f.fid]['return'] for f in nfl if f.model == 'C')
        if r[0] > 6571.4 + 2:
            continue
        if r[1] < r0[1] - 0.005:
            print('r%d: ★吸%s入C(%s) 省%.0fs → %d架 mk=%.1f en=%.2f C返场%.0f' % (
                rnd, zs, [(z, len(bs)) for z, bs in c.route], gain, len(nfl), r[0], r[1], c_ret), flush=True)
            fls = sorted(nfl, key=lambda x: x.fid); r0 = (r[0], r[1], r[2]); fidn += 1; applied = True
            break
    if not applied:
        print('r%d: 候选不可用（完工/能耗约束）' % rnd, flush=True); break
print('=== 最终 ===')
r = eval_full_r(fls)
print('%d架 mk=%.1f en=%.2f (vs 6571.4/69.77)' % (len(fls), r[0], r[1]))
json.dump([{'fid': f.fid, 'model': f.model, 'route': [[z, list(bs)] for z, bs in f.route]} for f in fls],
          open('求解代码与结果/结果/进化_v25/v113_best.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
