# -*- coding: utf-8 -*-
"""v95b：全局重装箱 beam——A/B多区化 + C移箱，池负载快评估引导(快) + 完工验证(慢)混合。
目标：max池≤5400 → 完工<6000。200轮×beam12，接受max池+1500s中间态。"""
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
    return max(pt[g] / N[g] for g in 'ABC'), {g: pt[g] / N[g] for g in 'ABC'}

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

fls0 = load('p2v89_champion25.json')
ml0, _ = pool_load(fls0)
r0 = evalf(fls0)
print('起点: 25架 max池=%.0f mk=%.1f en=%.2f' % (ml0, r0[0], r0[1]), flush=True)
t0 = time.time()
beam = [(ml0, r0[0], r0[1], fls0)]
seen = set()
best_overall = (r0[0], r0[1], fls0)
under6000 = []
for rnd in range(200):
    nxt = []
    for ml, mk, en, fls in beam:
        # 快评估候选池负载（不 eval_full——快）——但完工验证必须精确……折中：所有候选计算池负载，接受带内保留
        for tag, fa_id, fb_id, nf in mz_candidates(fls):
            nfl = [f for f in fls if f.fid not in (fa_id, fb_id)] + [nf]
            ml2, _ = pool_load(nfl)
            key = (len(nfl), round(ml2))
            if key in seen: continue
            seen.add(key)
            if ml2 <= ml + 1500 and 22 <= len(nfl) <= 27:
                nxt.append((ml2, ml2, 0.0, nfl))
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 24)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            ml2, _ = pool_load(imp)
            key = (len(imp), round(ml2))
            if key in seen: continue
            seen.add(key)
            if ml2 <= ml + 1500 and 22 <= len(imp) <= 27:
                nxt.append((ml2, ml2, 0.0, imp))
    if not nxt:
        print('r%d: 无新候选' % rnd, flush=True); break
    nxt.sort(key=lambda t: (t[0], len(t[3])))
    beam = nxt[:12]
    # 每 25 轮对 beam top6 做完工验证
    if rnd % 25 == 24:
        for ml2, mk2, en2, fls2 in beam[:6]:
            r = evalf(fls2)
            if r is None: continue
            if r[0] < best_overall[0] - 0.5:
                best_overall = (r[0], r[1], fls2)
                print('r%d: ★完工 mk=%.1f en=%.2f 架%d max池%.0f (%.0fs)' % (
                    rnd, r[0], r[1], len(fls2), pool_load(fls2)[0], time.time()-t0), flush=True)
            if r[0] < 6000:
                under6000.append((r[0], r[1], len(fls2), fls2))
                print('★★★ <6000! mk=%.1f en=%.2f 架%d (%.0fs)' % (r[0], r[1], len(fls2), time.time()-t0), flush=True)
print('=== 最终 ===')
print('最佳完工: mk=%.1f en=%.2f 架%d (%s)' % (best_overall[0], best_overall[1], len(best_overall[2]), '★超越6571!' if best_overall[0] < 6571 else '未超越'))
if under6000:
    u = min(under6000)
    print('★★ 完工<6000: mk=%.1f en=%.2f 架%d' % (u[0], u[1], u[2]))
    json.dump({'best': {'makespan': u[0], 'energy': u[1], 'flights': u[2]},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in u[3]]},
              open(os.path.join(OUTD, 'p2v95_sub6000.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v95_sub6000.json')
elif best_overall[0] < 6571:
    json.dump({'best': {'makespan': best_overall[0], 'energy': best_overall[1], 'flights': len(best_overall[2])},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in best_overall[2]]},
              open(os.path.join(OUTD, 'p2v95_best.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v95_best.json (改善解)')
print('覆盖 %d (%.0fs)' % (len(seen), time.time()-t0))
