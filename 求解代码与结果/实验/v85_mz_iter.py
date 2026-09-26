# -*- coding: utf-8 -*-
"""v85：多区合并迭代——循环尝试(多区合并/单区合并/迁移/换型)，目标完工降或(完工平+架次降)。
从 26架/6571.4 出发，看能否 25/24 架仍 6571 或找到 <6571.4。"""
import sys, os, json, itertools, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()

def load(p):
    d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]

cur = load('p2v84_multizone.json')
m0 = eval_full(data, cur)[0]
MK0 = m0['makespan']
print('起点: %d架 mk=%.1f en=%.2f' % (len(cur), MK0, m0['energy']))
t0 = time.time()

def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']

# 多区合并/单区迁移的全部原子算子集
def all_candidates(fls):
    cands = []
    N = len(fls)
    for fa, fb in itertools.combinations(fls, 2):
        if fa.model != fb.model: continue
        # 多区合并（任意区组合）
        za = set(s for s, _ in fa.route); zb = set(s for s, _ in fb.route)
        if len(fls) > 25:  # 优先多区合并
            union_z = za | zb
            if len(union_z) <= 4:
                route = []
                for z in sorted(union_z):
                    bs = [b for s2, bs2 in (fa.route + fb.route) for b in bs2 if b.split('-')[0] == z]
                    if bs: route.append((z, bs))
                nf = Flight(max(x.fid for x in fls) + 1, route, fa.model, data)
                if nf.is_feasible():
                    cands.append(('mz', fa.fid, fb.fid, None, None, nf))
        else:
            # 单区合并（同区）
            if za == zb and len(za) == 1 and len(zb) == 1:
                z = za.pop() if False else next(iter(za))
                bs = [b for s2, bs2 in (fa.route + fb.route) for b in bs2]
                nf = Flight(max(x.fid for x in fls) + 1, [(z, bs)], fa.model, data)
                if nf.is_feasible():
                    cands.append(('m1', fa.fid, fb.fid, None, None, nf))
    return cands

best = (MK0, m0['energy'], cur)
history = [(len(cur), MK0, m0['energy'])]
for rnd in range(30):
    cands = all_candidates(cur)
    improved = None
    for tag, fa, fb, _, _, nf in cands:
        nfl = [f for f in cur if f.fid not in (fa, fb)] + [nf]
        r = evalf(nfl)
        if r is None: continue
        if r[0] < best[0] - 0.5 or (abs(r[0] - best[0]) < 0.5 and len(nfl) < len(best[2])):
            improved = (tag, r[0], r[1], nfl)
            best = (r[0], r[1], nfl)
    if improved is None:
        # 完工持平：记录但保持
        pass
    else:
        tag, mk, en, nfl = improved
        cur = nfl
        MK0 = mk
        print('r%d: %s → %d架 mk=%.1f en=%.2f (%.0fs)' % (rnd, tag, len(cur), mk, en, time.time()-t0), flush=True)
    if rnd % 10 == 9:
        print('  ... r%d 当前 %d架 mk=%.1f (%.0fs)' % (rnd, len(cur), MK0, time.time()-t0), flush=True)
        if len(history) > 3 and history[-1][1] == history[-2][1] == history[-3][1] == history[-4][1]:
            break
    history.append((len(cur), MK0, best[1]))
print('最终: %d架 mk=%.1f en=%.2f | 历史架数%s' % (len(best[2]), best[0], best[1], sorted(set(h[0] for h in history))))
json.dump({'best': {'makespan': best[0], 'energy': best[1], 'flights': len(best[2])},
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s, list(bs)) for s, bs in f.route]} for f in best[2]]},
          open(os.path.join(OUTD, 'p2v85_best.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p2v85_best.json', round(time.time()-t0), 's')
