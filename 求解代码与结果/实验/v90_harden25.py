# -*- coding: utf-8 -*-
"""v90：25架新冠军窄带硬化确认（20轮，接受完工<=6571+120）+ 能耗微压（完工不动能耗下降）。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']
mk0, en0 = evalf(fls)
print('起点: 25架 mk=%.1f en=%.2f' % (mk0, en0), flush=True)
t0 = time.time()
best_mk, best_en = mk0, en0
for rnd in range(20):
    c, fa, sc, si, di = build_candidates_x(fls)
    improved = None
    for i in range(len(c)):
        cc = c[i]
        if cc[0] == 'stop': continue
        try: imp = apply_cand_x(fls, cc)
        except Exception: continue
        if imp is None: continue
        r = evalf(imp)
        if r is None: continue
        m, e = r
        if m <= best_mk + 120 and (m, -e) < (best_mk, -best_en):
            improved = (m, e, imp)
    if improved is None:
        if rnd % 5 == 4: print('  r%d 无改善' % rnd, flush=True)
        continue
    m, e, imp = improved
    if m < best_mk - 0.5 or (abs(m - best_mk) < 0.5 and e < best_en - 0.01):
        print('r%d: ★mk=%.1f en=%.2f' % (rnd, m, e), flush=True)
        best_mk, best_en = m, e
        fls = imp
print('硬化后: mk=%.1f en=%.2f (%.0fs) → %s' % (best_mk, best_en, time.time()-t0, '不动点确认' if best_mk >= mk0 - 0.5 else '新纪录!'))
if best_mk < mk0 - 0.5 or best_en < en0 - 0.01:
    json.dump({'best': {'makespan': best_mk, 'energy': best_en, 'flights': len(fls)},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in fls]},
              open(os.path.join(OUTD, 'p2v90_hardened.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved p2v90_hardened.json')
