# -*- coding: utf-8 -*-
"""v69c：宽带双向扫描（完工+<=2500s 都走，记录全部架数帕累托）+ 候选诊断。"""
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

def scan(name, start_p, rounds=26, beam_w=6):
    base = load(start_p)
    m0 = evalf(base)
    print(f'== {name}: {len(base)}架起点 mk={m0[0]:.1f} en={m0[1]:.2f} ==', flush=True)
    best_by_n = {len(base): (m0[0], m0[1], base)}
    beam = [(m0[0], m0[1], base)]
    seen = set()
    t0 = time.time()
    ctypes = {}
    for rnd in range(rounds):
        nxt = []
        ncand = nok = 0
        for mk, en, fls in beam:
            c, fa, sc, si, di = build_candidates_x(fls)
            ncand += len(c)
            types = {}
            for cc in c: types[cc[0]] = types.get(cc[0], 0) + 1
            ctypes = types
            od = list(range(min(len(c), 28)))
            for cand_i in od:
                cc = c[cand_i]
                if cc[0] == 'stop': continue
                try:
                    imp = apply_cand_x(fls, cc)
                except Exception:
                    continue
                if imp is None: continue
                nok += 1
                r = evalf(imp)
                if r is None: continue
                mk2, en2 = r
                n2 = len(imp)
                key = (n2, round(mk2), round(en2, 2))
                if key in seen: continue
                seen.add(key)
                if mk2 <= m0[0] + 2500:  # 宽带：完工+<=2500s 全部保留（记录中间架数）
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
        if rnd % 4 == 3:
            print(f'  r{rnd+1}: 候选{sum(ncand for _ in [0])//1} 类型{ctypes} 覆盖{len(best_by_n)}架 ({time.time()-t0:.0f}s)', flush=True)
    rows = sorted(best_by_n.items())
    print(f'  [前 {min(len(rows), 14)} 项] 候选类型: {ctypes}', flush=True)
    for n, (mk, en, _) in rows:
        print(f'    {n:>3}架: mk={mk:>7.1f}s ({mk/60:>6.1f}min) en={en:>6.2f}  Δmk={mk-m0[0]:+7.0f} Δen={en-m0[1]:+.2f}', flush=True)
    for n, (mk, en, fls) in rows:
        json.dump({'best': {'makespan': mk, 'energy': en, 'flights': n},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in fls]},
                  open(os.path.join(OUTD, 'p2v69c_%s_n%d.json' % (name, n)), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  [{name}] 用时 {time.time()-t0:.0f}s', flush=True)

scan('d28', 'p2v61_gatv67c_greedy.json')
scan('u23', 'p2v46_23local.json')
print('DONE', flush=True)
