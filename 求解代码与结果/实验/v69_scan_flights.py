# -*- coding: utf-8 -*-
"""v69：架次-完工-能耗三维帕累托扫描。
从 23 架起点(7724.9/67.61) 出发，用拆分(增架)/合并(减架)/迁移/换型全集 beam 搜索，
记录每个架数(23..32)的最优 (完工, 能耗) —— 填补 24-27 架的帕累托空白。"""
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

base = load('p2v46_23local.json')
m0 = evalf(base)
print(f'23架起点: mk={m0[0]:.1f} en={m0[1]:.2f}')
t0 = time.time()
# 帕累托按架数记录：best_by_n[n] = (mk, en, fls)
best_by_n = {23: (m0[0], m0[1], base)}
beam = [(m0[0], m0[1], base)]
seen = set()
for rnd in range(35):
    nxt = []
    for mk, en, fls in beam:
        c, fa, sc, si, di = build_candidates_x(fls)
        # 按启发式评分取 top20 + 随机补 5
        order = list(range(min(len(c), 20)))
        for cand_i in order:
            imp = None
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
            # 接受：完工降 || 完工+<=400 且能耗降
            if mk2 < mk - 0.5 or (mk2 <= mk + 400 and en2 < en - 0.05):
                nxt.append((mk2, en2, imp))
                cur = best_by_n.get(n2)
                if cur is None or (mk2, en2) < (cur[0], cur[1]):
                    best_by_n[n2] = (mk2, en2, imp)
    if not nxt:
        break
    # beam 精选：完工优先 top4 + 能耗优先 top4（去重）
    nxt.sort(key=lambda t: (t[0], t[1]))
    beam = nxt[:4] + sorted(nxt, key=lambda t: (t[1], t[0]))[:4]
    # 去重 beam
    bm = {}
    for t in beam: bm[(round(t[0]), round(t[1],2))] = t
    beam = list(bm.values())[:8]
    if rnd % 5 == 4:
        print(f'r{rnd+1}: beam {len(beam)} 覆盖架数 {sorted(best_by_n.keys())} ({time.time()-t0:.0f}s)', flush=True)
print('=== 架次-完工-能耗 帕累托前沿 ===')
print(f"{'架次':>4} {'完工s':>8} {'完工min':>8} {'能耗kWh':>8}  变化")
rows = sorted(best_by_n.items())
for n, (mk, en, _) in rows:
    rel = f"Δmk={mk-m0[0]:+.0f} Δen={en-m0[1]:+.2f}" if n != 23 else '起点'
    print(f'{n:>4} {mk:>8.1f} {mk/60:>8.1f} {en:>8.2f}  {rel}')
# 落盘每架数最优
for n, (mk, en, fls) in rows:
    json.dump({'best': {'makespan': mk, 'energy': en, 'flights': n},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in fls]},
              open(os.path.join(OUTD, 'p2v69_n%d.json' % n), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p2v69_n*.json', round(time.time()-t0, 0), 's')
