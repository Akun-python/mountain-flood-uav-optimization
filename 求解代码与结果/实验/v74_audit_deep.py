# -*- coding: utf-8 -*-
"""v74：审计 27架/6797.6/70.11 冠军 + 从它深扫（完工再压 + 能耗再降）。"""
import sys, os, json, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v73_n27.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m, sch, v, nc = eval_full(data, fls)
print('v73 27架: mk=%.1f en=%.2f hard=%s 违规%d 临界%d 趟%d' % (m['makespan'], m['energy'], m['hard_ok'], v, nc, len(fls)))
bat = cb(data, sch, fls)
allb = set(data.boxes); used = set()
for f in fls:
    for b in f.box_ids: used.add(b)
print('电池%d 覆盖缺%d重%d' % (len(bat), len(allb-used), len(used)-len(allb)))
pt = {'A':0.0,'B':0.0,'C':0.0}
for f in fls: pt[f.model] += f.duration()
en_p = {'A':0.0,'B':0.0,'C':0.0}
for f in fls: en_p[f.model] += f.energy()
print('池T/台:', {g: round(pt[g]/{'A':4,'B':2,'C':2}[g],0) for g in 'ABC'}, '能耗/池', {g: round(en_p[g],2) for g in 'ABC'})
print('机型:', {g: sum(1 for f in fls if f.model==g) for g in 'ABC'})
bad = [f.fid for f in fls if not f.is_feasible()]
zb = [f.fid for f in fls for s2, bs in f.route for b in bs if b.split('-')[0] != s2]
low = [f.fid for f in fls if f.energy() > 0.8*{'A':4.5,'B':4.0,'C':8.0}[f.model]]
empty = [f.fid for f in fls if not f.box_ids]
print('逐趟可行%d 区一致%d 返航保底%d 空趟%d → %s' % (len(bad), len(zb), len(low), len(empty),
      'PASS' if (v==0 and nc==0 and not bat and not bad and not zb and not low and not empty) else 'FAIL'))
# 深扫
def evalf(x):
    mm, ss, vv, nn = eval_full(data, x)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']
cur = fls
MK0, EN0 = m['makespan'], m['energy']
t0 = time.time()
final = {(len(fls), MK0, EN0)}
best = (len(fls), MK0, EN0, fls)
beam = [(MK0, EN0, fls)]
seen = set()
for rnd in range(30):
    nxt = []
    for mk, en, fx in beam:
        c, fa, sc, si, di = build_candidates_x(fx)
        for i in range(min(len(c), 26)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fx, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            mk2, en2 = r
            n2 = len(imp)
            key = (n2, round(mk2), round(en2, 2))
            if key in seen: continue
            seen.add(key)
            if mk2 <= MK0 + 1200:
                nxt.append((mk2, en2, imp))
                if (mk2, en2) < (best[1], best[2]):
                    best = (n2, mk2, en2, imp)
    if not nxt: break
    nxt.sort(key=lambda t: (t[0], t[1]))
    beam = (nxt[:5] + sorted(nxt, key=lambda t: (t[1], t[0]))[:5])
    bm = {}
    for t in beam: bm[(round(t[0]), round(t[1],2))] = t
    beam = list(bm.values())[:6]
print('深扫最优: %d架 mk=%.1f en=%.2f (%.0fs)' % (best[0], best[1], best[2], time.time()-t0))
if (best[1], best[2]) < (MK0, EN0):
    m2, s2, v2, n2c = eval_full(data, best[3])
    bat2 = cb(data, s2, best[3])
    print('新纪录审计: hard=%s 违规%d 临界%d 电池%d' % (m2['hard_ok'], v2, n2c, len(bat2)))
    json.dump({'best': {'makespan': best[1], 'energy': best[2], 'flights': best[0]},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in best[3]]},
              open(os.path.join(OUTD, 'p2v74_champion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v74_champion.json')
else:
    print('无更优（27架/6797.6/70.11 保持）')
