# -*- coding: utf-8 -*-
"""v74b：迭代深扫循环——从当前冠军重复宽带 beam 直到收敛（完工下界逼近）。"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
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

t0 = time.time()
src = 'p2v74_champion.json'
for outer in range(6):
    base = load(src)
    mk0, en0 = evalf(base)
    print(f'== 第{outer+1}轮 起点 {len(base)}架 mk={mk0:.1f} en={en0:.2f} ==', flush=True)
    MK0 = mk0
    beam = [(mk0, en0, base)]
    seen = set()
    best = (mk0, en0, base)
    for rnd in range(30):
        nxt = []
        for mk, en, fls in beam:
            c, fa, sc, si, di = build_candidates_x(fls)
            for i in range(min(len(c), 26)):
                cc = c[i]
                if cc[0] == 'stop': continue
                try: imp = apply_cand_x(fls, cc)
                except Exception: continue
                if imp is None: continue
                r = evalf(imp)
                if r is None: continue
                mk2, en2 = r
                key = (round(mk2), round(en2, 2))
                if key in seen: continue
                seen.add(key)
                if mk2 <= MK0 + 1200:
                    nxt.append((mk2, en2, imp))
                    if (mk2, en2) < (best[0], best[1]):
                        best = (mk2, en2, imp)
        if not nxt: break
        nxt.sort(key=lambda t: (t[0], t[1]))
        beam = (nxt[:5] + sorted(nxt, key=lambda t: (t[1], t[0]))[:5])
        bm = {}
        for t in beam: bm[(round(t[0]), round(t[1],2))] = t
        beam = list(bm.values())[:6]
    print(f'  本轮最优: {len(best[2])}架 mk={best[0]:.1f} en={best[1]:.2f}', flush=True)
    if (best[0], best[1]) >= (mk0, en0):
        print('收敛——无更优', flush=True)
        break
    json.dump({'best': {'makespan': best[0], 'energy': best[1], 'flights': len(best[2])},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in best[2]]},
              open(os.path.join(OUTD, 'p2v74_champion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    src = 'p2v74_champion.json'
    print(f'  → 新一轮起点更新 ({time.time()-t0:.0f}s)', flush=True)
be = load('p2v74_champion.json') if (best[0], best[1]) >= (mk0, en0) else best[2]
mm, ss, vv, nn = eval_full(data, be)
print('FINAL: %d架 mk=%.1f (%.1fmin) en=%.2f hard=%s 违规%d 临界%d' % (len(be), mm['makespan'], mm['makespan']/60, mm['energy'], mm['hard_ok'], vv, nn), flush=True)
print('DONE %.0fs' % (time.time()-t0), flush=True)
