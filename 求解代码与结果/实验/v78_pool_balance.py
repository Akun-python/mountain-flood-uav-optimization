# -*- coding: utf-8 -*-
"""v78：池均衡引导搜索——目标 min max(池T/台)，用快评估引导，最终 eval_full 验证完工。
关键洞察：C池6趟(5990T/台)覆盖区S001/S003/S004/S007/S008在A/B池无同区趟——只能靠拆分建A子趟或迁移。"""
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

N = {'A': 4, 'B': 2, 'C': 2}
def pool_load(fls):
    pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    for f in fls: pt[f.model] += f.duration()
    return max(pt[g] / N[g] for g in 'ABC'), pt

def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']

base = load('p2v75_champion.json')
ml0, pt0 = pool_load(base)
print('起点: 27架 max池T/台=%.0f (A%.0f/B%.0f/C%.0f) 完工6571.4' % (ml0, pt0['A']/N['A'], pt0['B']/N['B'], pt0['C']/N['C']), flush=True)
t0 = time.time()
beam = [(pool_load(base)[0], base)]
seen = set()
best_pool = (pool_load(base)[0], base)
pool_history = []
for rnd in range(45):
    nxt = []
    for ml, fls in beam:
        c, fa, sc, si, di = build_candidates_x(fls)
        for i in range(min(len(c), 22)):
            cc = c[i]
            if cc[0] == 'stop': continue
            try: imp = apply_cand_x(fls, cc)
            except Exception: continue
            if imp is None: continue
            # 快评估：能量硬约束（is_feasible 已查）+ 池负载
            ml2, pt2 = pool_load(imp)
            key = (len(imp), round(ml2), round(pt2['A']/N['A']), round(pt2['B']/N['B']), round(pt2['C']/N['C']))
            if key in seen: continue
            seen.add(key)
            # 接受：max池负载 ≤ 起点+80（温和）+ 不劣于当前解太多
            if ml2 <= ml0 + 80:
                nxt.append((ml2, imp))
                if (ml2, len(imp)) < (best_pool[0], len(best_pool[1])):
                    best_pool = (ml2, imp)
    if not nxt: break
    nxt.sort(key=lambda t: (t[0], len(t[1])))
    beam = nxt[:10]
    pool_history.append(best_pool[0])
    if rnd % 9 == 8:
        print('r%d: max池=%.0f 覆盖%d解 (%.0fs)' % (rnd+1, best_pool[0], len(seen), time.time()-t0), flush=True)
print('=== 池均衡结果 ===')
print('最佳池负载: max=%.0f (%d架)' % (best_pool[0], len(best_pool[1])))
mlb, ptb = pool_load(best_pool[1])
print('  A%.0f/B%.0f/C%.0f' % (ptb['A']/N['A'], ptb['B']/N['B'], ptb['C']/N['C']))
# 对搜索中的候选做完工验证（收集 max 池负载最低的 12 个解 + 起点比较）
cands = [best_pool]
# 从 beam 历史补几个（重建：简化——只验证 best_pool 和起点）
for i, (mk, en) in [('best', None)]:
    pass
r = evalf(best_pool[1])
if r:
    print('池均衡解完工验证: mk=%.1f en=%.2f → %s' % (r[0], r[1], '★新纪录!' if r[0] < 6571.4 else '未突破'))
    json.dump({'best': {'makespan': r[0], 'energy': r[1], 'flights': len(best_pool[1])},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in best_pool[1]]},
              open(os.path.join(OUTD, 'p2v78_poolbest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
else:
    print('池均衡解完工无效（硬门槛失败）')
print('DONE %.0fs' % (time.time()-t0), flush=True)
