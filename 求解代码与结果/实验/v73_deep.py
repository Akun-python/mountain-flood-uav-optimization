# -*- coding: utf-8 -*-
"""v73：各架数独立深扫——从 v69c/v71 已存各架数解出发宽带 beam 30 轮，追每架数的完工下界。"""
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
final = {}
for n, (sp, tag) in {29: ('p2v71_n29.json', 'v71'), 27: ('p2v69c_d28_n27.json', 'v69c'),
                     26: ('p2v69c_d28_n26.json', 'v69c'), 25: ('p2v69c_d28_n25.json', 'v69c')}.items():
    try:
        base = load(sp)
    except Exception as e:
        print(f'{n}架 起点缺失 {sp}: {e}', flush=True); continue
    m0 = evalf(base)
    if m0 is None:
        print(f'{n}架 起点不可行', flush=True); continue
    print(f'== {n}架深扫 起点 {tag} mk={m0[0]:.1f} en={m0[1]:.2f} ==', flush=True)
    best_by_n = {n: (m0[0], m0[1], base)}
    beam = [(m0[0], m0[1], base)]
    seen = set()
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
                n2 = len(imp)
                key = (n2, round(mk2), round(en2, 2))
                if key in seen: continue
                seen.add(key)
                if mk2 <= m0[0] + 1500:
                    nxt.append((mk2, en2, imp))
                    cur = best_by_n.get(n2)
                    if cur is None or (mk2, en2) < (cur[0], cur[1]):
                        best_by_n[n2] = (mk2, en2, imp)
        if not nxt: break
        nxt.sort(key=lambda t: (t[0], t[1]))
        beam = (nxt[:5] + sorted(nxt, key=lambda t: (t[1], t[0]))[:5])
        bm = {}
        for t in beam: bm[(round(t[0]), round(t[1],2))] = t
        beam = list(bm.values())[:6]
    for n2, (mk, en, fls) in sorted(best_by_n.items()):
        key = (mk, n2)
        if key[0] < final.get(n2, (1e9,))[0]:
            final[n2] = (mk, en, fls)
            json.dump({'best': {'makespan': mk, 'energy': en, 'flights': n2},
                       'solution': [{'fid': f.fid, 'model': f.model,
                                     'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]},
                      open(os.path.join(OUTD, 'p2v73_n%d.json' % n2), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'  {n2:>3}架: mk={mk:>7.1f}s ({mk/60:>6.1f}min) en={en:>6.2f}', flush=True)
print('=== v73 汇总（完工下界追查）===', flush=True)
for n2 in sorted(final):
    mk, en, _ = final[n2]
    print(f'  {n2:>3}架: mk={mk:>7.1f}s ({mk/60:>6.1f}min) en={en:>6.2f}', flush=True)
print('用时 %.0fs' % (time.time()-t0), flush=True)
