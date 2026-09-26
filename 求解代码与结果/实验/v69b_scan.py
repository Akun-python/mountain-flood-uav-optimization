# -*- coding: utf-8 -*-
"""v69b：双向架次扫描。A) 28架冠军(6990.1/74.16)减架→27..24；B) 23架起点加架→24..28。宽接受带。"""
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
    m, s, v, nc = eval_full(data, fls)
    if m is None or v > 0 or nc > 0 or not m['hard_ok']: return None
    return m['makespan'], m['energy']

def scan(name, start_p, accept_delta=700, rounds=30, beam_w=6):
    base = load(start_p)
    m0 = evalf(base)
    print(f'== {name}: {len(base)}架起点 mk={m0[0]:.1f} en={m0[1]:.2f} ==')
    best_by_n = {len(base): (m0[0], m0[1], base)}
    beam = [(m0[0], m0[1], base)]
    seen = set()
    t0 = time.time()
    for rnd in range(rounds):
        nxt = []
        for mk, en, fls in beam:
            c, fa, sc, si, di = build_candidates_x(fls)
            od = list(range(min(len(c), 24)))
            for cand_i in od:
                try:
                    imp = apply_cand_x(fls, c[cand_i])
                except Exception:
                    continue
                if imp is None: continue
                r = evalf(imp)
                if r is None: continue
                mk2, en2 = r
                n2 = len(imp)
                key = (n2, round(mk2), round(en2, 2))
                if key in seen: continue
                seen.add(key)
                if mk2 < mk - 0.5 or (mk2 <= mk + accept_delta and en2 < en - 0.02):
                    nxt.append((mk2, en2, imp))
                    cur = best_by_n.get(n2)
                    if cur is None or (mk2, en2) < (cur[0], cur[1]):
                        best_by_n[n2] = (mk2, en2, imp)
        if not nxt: break
        nxt.sort(key=lambda t: (t[0], t[1]))
        beam = (nxt[:beam_w] + sorted(nxt, key=lambda t: (t[1], t[0]))[:beam_w])
        bm = {}
        for t in beam: bm[(round(t[0]), round(t[1],2))] = t
        beam = list(bm.values())[:beam_w]
    rows = sorted(best_by_n.items())
    for n, (mk, en, _) in rows:
        print(f'  {n:>3}架: mk={mk:>7.1f}s ({mk/60:>6.1f}min) en={en:>6.2f}  Δmk={mk-m0[0]:+7.0f} Δen={en-m0[1]:+.2f}')
    for n, (mk, en, fls) in rows:
        json.dump({'best': {'makespan': mk, 'energy': en, 'flights': n},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in fls]},
                  open(os.path.join(OUTD, 'p2v69b_%s_n%d.json' % (name, n)), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  [{name}] 用时 {time.time()-t0:.0f}s')

scan('down28', 'p2v61_gatv67c_greedy.json', accept_delta=800, rounds=30)
scan('up23', 'p2v46_23local.json', accept_delta=600, rounds=30)
print('DONE')
