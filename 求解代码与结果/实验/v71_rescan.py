# -*- coding: utf-8 -*-
"""v71：从 6799.9 冠军再轮宽带 beam（完工+<=2000），压完工下限 + 找 27/26 架结构。"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v70_champion.json'), encoding='utf-8'))
base = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m0 = eval_full(data, base)[0]
MK0 = m0['makespan']
print(f'起点: {len(base)}架 mk={MK0:.1f} en={m0["energy"]:.2f}', flush=True)
best_by_n = {28: (MK0, m0['energy'], base)}
beam = [(MK0, m0['energy'], base)]
seen = set()
t0 = time.time()
best_ever = (MK0, m0['energy'], base)
for rnd in range(28):
    nxt = []
    for mk, en, fls in beam:
        c, fa, sc, si, di = build_candidates_x(fls)
        for cand_i in range(min(len(c), 26)):
            cc = c[cand_i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            m, s, v, nc = eval_full(data, imp)
            if m is None or v > 0 or nc > 0 or not m['hard_ok']: continue
            mk2, en2 = m['makespan'], m['energy']
            n2 = len(imp)
            key = (n2, round(mk2), round(en2, 2))
            if key in seen: continue
            seen.add(key)
            if mk2 <= MK0 + 2000:
                nxt.append((mk2, en2, imp))
                cur = best_by_n.get(n2)
                if cur is None or (mk2, en2) < (cur[0], cur[1]):
                    best_by_n[n2] = (mk2, en2, imp)
                if (mk2, en2) < (best_ever[0], best_ever[1]):
                    best_ever = (mk2, en2, imp)
                    print(f'  ★r{rnd+1} 新纪录: {n2}架 mk={mk2:.1f} en={en2:.2f} ({time.time()-t0:.0f}s)', flush=True)
    if not nxt: break
    nxt.sort(key=lambda t: (t[0], t[1]))
    beam = (nxt[:6] + sorted(nxt, key=lambda t: (t[1], t[0]))[:6])
    bm = {}
    for t in beam: bm[(round(t[0]), round(t[1],2))] = t
    beam = list(bm.values())[:6]
print('=== 各架数最优（第二轮）===', flush=True)
for n, (mk, en, _) in sorted(best_by_n.items()):
    print(f'  {n:>3}架: mk={mk:>7.1f}s ({mk/60:>6.1f}min) en={en:>6.2f} Δmk={mk-MK0:+7.0f}', flush=True)
be = best_ever
json.dump({'best': {'makespan': be[0], 'energy': be[1], 'flights': len(be[2])},
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in be[2]]},
          open(os.path.join(OUTD, 'p2v71_best.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('best_ever: %d架 mk=%.1f en=%.2f → saved p2v71_best.json' % (len(be[2]), be[0], be[1]), flush=True)
# 各架数解落盘
for n, (mk, en, fls) in sorted(best_by_n.items()):
    json.dump({'best': {'makespan': mk, 'energy': en, 'flights': n},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]},
              open(os.path.join(OUTD, 'p2v71_n%d.json' % n), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('DONE', round(time.time()-t0), 's', flush=True)
