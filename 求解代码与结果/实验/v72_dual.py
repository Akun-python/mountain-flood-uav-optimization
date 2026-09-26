# -*- coding: utf-8 -*-
"""v72 双路优化：A) 能耗收敛(完工 cap +120)；B) 模拟退火非单调压完工。"""
import sys, os, json, time, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
random.seed(0)
d = json.load(open(os.path.join(OUTD, 'p2v70_champion.json'), encoding='utf-8'))
base = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m0 = eval_full(data, base)[0]
MK0, EN0 = m0['makespan'], m0['energy']
print(f'起点: {len(base)}架 mk={MK0:.1f} en={EN0:.2f}', flush=True)

def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']

t0 = time.time()
print('== A. 能耗收敛 beam（完工 <= %.0f）==' % (MK0 + 120), flush=True)
beam = [(MK0, EN0, base)]
seen = set()
best_en = (MK0, EN0, base)
for rnd in range(30):
    nxt = []
    for mk, en, fls in beam:
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 24)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            mk2, en2 = r
            key = (round(mk2), round(en2, 3))
            if key in seen: continue
            seen.add(key)
            if mk2 <= MK0 + 120 and en2 < en - 0.001:
                nxt.append((mk2, en2, imp))
                if (en2, mk2) < (best_en[1], best_en[0]):
                    best_en = (mk2, en2, imp)
    if not nxt: break
    nxt.sort(key=lambda t: (t[1], t[0]))
    beam = (nxt[:4] + sorted(nxt, key=lambda t: (t[0], t[1]))[:4])
    bm = {}
    for t in beam: bm[(round(t[0]), round(t[1],3))] = t
    beam = list(bm.values())[:6]
print(f'  能耗最优: {len(best_en[2])}架 mk={best_en[0]:.1f} en={best_en[1]:.2f} ({time.time()-t0:.0f}s)', flush=True)
json.dump({'best': {'makespan': best_en[0], 'energy': best_en[1], 'flights': len(best_en[2])},
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in best_en[2]]},
          open(os.path.join(OUTD, 'p2v72_energy.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print('== B. 模拟退火非单调压完工（T 300→5, 800轮）==', flush=True)
cur = base
mk_c, en_c = MK0, EN0
best_sa = (MK0, EN0, base)
for it in range(800):
    T = 300 * (1 - it / 800) + 5 * it / 800
    c, fa, sc, si, di = build_candidates_x(cur)
    if len(c) == 0: break
    i = random.randrange(min(len(c), 40))
    try: imp = apply_cand_x(cur, c[i])
    except Exception: continue
    if imp is None: continue
    r = evalf(imp)
    if r is None: continue
    mk_n, en_n = r
    d_ = mk_n - mk_c
    if d_ <= 0 or random.random() < math.exp(-d_ / T):
        cur = imp; mk_c, en_c = mk_n, en_n
        if (mk_c, en_c) < (best_sa[0], best_sa[1]):
            best_sa = (mk_c, en_c, cur)
            print(f'  ★SA {it}: {len(cur)}架 mk={mk_c:.1f} en={en_c:.2f} ({time.time()-t0:.0f}s)', flush=True)
    if it % 200 == 199:
        print(f'  SA {it+1}: 当前 mk={mk_c:.1f} en={en_c:.2f} T={T:.0f}', flush=True)
print(f'  SA 最优: {len(best_sa[2])}架 mk={best_sa[0]:.1f} en={best_sa[1]:.2f}', flush=True)
json.dump({'best': {'makespan': best_sa[0], 'energy': best_sa[1], 'flights': len(best_sa[2])},
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in best_sa[2]]},
          open(os.path.join(OUTD, 'p2v72_sa.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('DONE', round(time.time()-t0), 's', flush=True)
