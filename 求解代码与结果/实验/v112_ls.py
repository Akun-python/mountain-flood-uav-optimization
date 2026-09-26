# -*- coding: utf-8 -*-
"""v112：全局局部搜索跳出局部最优——操作空间{区拆法切换、C型2区顺访、同区合趟}，
完工优先(降1s也收)、能耗次之(完工不回退)。beam 宽度 8 × 120 轮。"""
import sys, os, json, itertools, time, math, random
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
base = {f['fid']: Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']}
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
    return mm['makespan'], mm['energy']
r0 = eval_full_r([base[k] for k in sorted(base)])
print('起点: 25架 mk=%.1f en=%.2f' % (r0[0], r0[1]), flush=True)
o = data.centers['O01']; ref = (o['lon'], o['lat'])
# 操作集构建（每轮从当前方案生成所有可用操作）
def gen_ops(fls):
    ops = []  # (desc, new_fls) 不验证, 由 eval 决定
    dmap = {f.fid: f for f in fls}
    byz = {}
    for f in fls:
        for z, bs in f.route:
            byz.setdefault(z, []).append(f)
    fidn = max(f.fid for f in fls) + 1
    # 1) C型2区顺访：两个单区趟(其一C型)合成顺访
    for z1, fs1 in byz.items():
        for z2, fs2 in byz.items():
            if z1 >= z2: continue
            for f1 in fs1:
                for f2 in fs2:
                    if f1.model != 'C' and f2.model != 'C': continue
                    if len(set(z for z,_ in f1.route)) > 1 or len(set(z for z,_ in f2.route)) > 1: continue
                    B = f1.box_ids + f2.box_ids
                    if W(B) > CAP['C']: continue
                    zs = sorted([z1, z2], key=lambda z: angle_key(z, ref))
                    r1, r2 = (z1, z2) if zs[0] == z1 else (z2, z1)
                    nf = Flight(fidn, [(r1, list(f1.box_ids)), (r2, list(f2.box_ids))], 'C', data)
                    if nf.is_feasible():
                        gain = f1.duration() + f2.duration() - nf.duration()
                        if gain > 60:
                            nfl = [f for f in fls if f.fid not in (f1.fid, f2.fid)] + [nf]
                            ops.append(('顺访C %s|%s +%.0f' % (z1, z2, gain), nfl))
    # 2) 同区合趟（两单区趟同区同机型, 箱重和≤容量）
    for z, fs in byz.items():
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                f1, f2 = fs[i], fs[j]
                if f1.model != f2.model: continue
                if len(set(z for z,_ in f1.route)) > 1 or len(set(z for z,_ in f2.route)) > 1: continue
                B = f1.box_ids + f2.box_ids
                if W(B) > CAP[f1.model]: continue
                nf = Flight(fidn + 1, [(z, list(B))], f1.model, data)
                if nf.is_feasible():
                    gain = f1.duration() + f2.duration() - nf.duration()
                    if gain > 60:
                        nfl = [f for f in fls if f.fid not in (f1.fid, f2.fid)] + [nf]
                        ops.append(('合趟 %s %s +%.0f' % (z, f1.model, gain), nfl))
    # 3) 拆分（C型远区拆为 B/A 多趟——仅当可行）按重量切分
    heavy = [f for f in fls if f.model == 'C' and len(set(z for z,_ in f.route)) == 1]
    for f in heavy:
        z = [z for z,_ in f.route][0]
        B = f.box_ids
        w = W(B)
        if w <= 60 or not (z in ('S003','S004','S007','S008')):
            # 也考虑轻些的 C 区拆给 A
            if z not in ('S003','S004','S007','S008','S005'): continue
        for nm, cap in (('A', 25), ('B', 30)):
            kmin = max(2, math.ceil(w / cap))
            if kmin > 4: continue
            for parts in itertools.combinations(range(len(B)), kmin - 1):
                idx = list(parts) + [len(B)]
                prev = 0; ps = []; okk = True
                for ii in idx:
                    c = B[prev:ii]; prev = ii
                    if not c or W(c) > cap: okk = False; break
                    ps.append(c)
                if not okk or len(ps) < 2: continue
                nfs = []
                for c in ps:
                    nf = Flight(fidn + 2, [(z, list(c))], nm, data)
                    if not nf.is_feasible(): nfs = None; break
                    nfs.append(nf)
                if nfs:
                    nfl = [x for x in fls if x.fid != f.fid] + nfs
                    ops.append(('拆%s %s→%s×%d' % (z, f.model, nm, len(nfs)), nfl))
                if len(list(itertools.combinations(range(len(B)), kmin - 1))) > 30: break
    return ops
# beam
beam = [(0.0, r0[0], r0[1], [base[k] for k in sorted(base)])]
seen = set()
best = (r0[0], r0[1], [base[k] for k in sorted(base)])
t0 = time.time()
for rnd in range(120):
    nxt = []
    for dcost, mk, en, fls in beam:
        ops = gen_ops(fls)
        for desc, nfl in ops[:30]:
            key = tuple(sorted(f.fid for f in nfl))
            if key in seen: continue
            seen.add(key)
            r = eval_full_r(nfl)
            if r is None: continue
            nxt.append((r[0], r[1], nfl, desc))
    if not nxt:
        print('r%d: 无改进候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[0], t[1]))
    # 保留: 完工更优 或 (完工同/略优 且 能耗更优)
    filt = []
    for mk2, en2, fls2, desc in nxt[:40]:
        if mk2 < best[0] - 0.5 or (abs(mk2 - best[0]) <= 0.5 and en2 < best[1] - 0.02):
            filt.append((mk2, en2, fls2, desc))
    if filt:
        mk2, en2, fls2, desc = filt[0]
        print('r%d: ★%s → %d架 mk=%.1f en=%.2f (%.0fs)' % (rnd, desc, len(fls2), mk2, en2, time.time()-t0), flush=True)
        best = (mk2, en2, fls2)
    beam = [(0, mk2, en2, fls2) for mk2, en2, fls2, _ in nxt[:8]]
print('=== 最终 ===')
print('%d架 mk=%.1f en=%.2f (vs 冠军6571.4/69.77)' % (len(best[2]), best[0], best[1]))
json.dump([{'fid': f.fid, 'model': f.model, 'route': [[z, list(bs)] for z, bs in f.route]} for f in best[2]],
          open('求解代码与结果/结果/进化_v25/v112_best.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
