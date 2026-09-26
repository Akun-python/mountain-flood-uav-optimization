# -*- coding: utf-8 -*-
"""v75：多起点多样化迭代搜索器——解池+随机扰动+宽带beam+帕累托更新，多轮多版本接近最优。"""
import sys, os, json, time, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from dqn23_gat import build_candidates_x, apply_cand_x
data = Data()
random.seed(7)

def load(p):
    d = json.load(open(os.path.join(OUTD, p), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]

def evalf(fls):
    mm, s, vv, nn = eval_full(data, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok']: return None
    return mm['makespan'], mm['energy']

# 解池初始化（多版本起点）
pool = []
for p in ['p2v74_champion.json', 'p2v73_n27.json', 'p2v70_champion.json', 'p2v72_energy.json',
          'p2v46_23local.json', 'p2v58_rainbow_greedy.json']:
    try:
        fls = load(p)
        r = evalf(fls)
        if r: pool.append((r[0], r[1], fls))
    except Exception:
        pass
# 去重+帕累托池
def pareto(pool):
    out = []
    for t in pool:
        if any((o[0] <= t[0] and o[1] < t[1]) or (o[0] < t[0] and o[1] <= t[1]) for o in out):
            continue
        out = [o for o in out if not ((o[0] >= t[0] and o[1] > t[1]) or (o[0] > t[0] and o[1] >= t[1]))]
        out.append(t)
    return out
pool = pareto(pool)
pool.sort(key=lambda t: (t[0], t[1]))
print('解池初始化(%d个帕累托):' % len(pool))
for mk, en, _ in pool:
    print('  mk=%.1f en=%.2f' % (mk, en))
print('当前冠军: mk=%.1f en=%.2f' % (pool[0][0], pool[0][1]), flush=True)
t0 = time.time()
best_mk = pool[0][0]
for it in range(14):
    improved = False
    # 从池中挑起点（完工前3 + 能耗前3 + 随机2）
    starts = sorted(pool)[:3] + sorted(pool, key=lambda t: (t[1], t[0]))[:3]
    random.shuffle(starts)
    for si, (mk, en, fls) in enumerate(starts[:5]):
        # 扰动：随机 2-4 步（接受完工+<=900 的恶化，构建多样性起点）
        cur = fls
        for _ in range(random.randint(2, 4)):
            c, fa, sc, si2, di2 = build_candidates_x(cur)
            if not c: break
            i = random.randrange(min(len(c), 30))
            if c[i][0] == 'stop': continue
            try: imp = apply_cand_x(cur, c[i])
            except Exception: continue
            if imp is None: continue
            r = evalf(imp)
            if r is None: continue
            if r[0] <= mk + 900:
                cur = imp; mk, en = r
        # 宽带beam（30步）
        MK = mk
        beam = [(mk, en, cur)]
        seen = set()
        for rnd in range(30):
            nxt = []
            for mk2, en2, fx in beam:
                c, fa, sc, si2, di2 = build_candidates_x(fx)
                # 随机 34 个候选（多样性）
                idxs = list(range(min(len(c), 60)))
                random.shuffle(idxs)
                for i in idxs[:34]:
                    cc = c[i]
                    if cc[0] == 'stop': continue
                    try: imp = apply_cand_x(fx, cc)
                    except Exception: continue
                    if imp is None: continue
                    r = evalf(imp)
                    if r is None: continue
                    k = (round(r[0]), round(r[1], 2))
                    if k in seen: continue
                    seen.add(k)
                    if r[0] <= MK + 1400:
                        nxt.append((r[0], r[1], imp))
            if not nxt: break
            nxt.sort(key=lambda t: (t[0], t[1]))
            beam = (nxt[:5] + sorted(nxt, key=lambda t: (t[1], t[0]))[:5])
            bm = {}
            for t in beam: bm[(round(t[0]), round(t[1],2))] = t
            beam = list(bm.values())[:6]
        # 池更新
        added = False
        for t in beam:
            if any((o[0] <= t[0] and o[1] < t[1]) or (o[0] < t[0] and o[1] <= t[1]) for o in pool):
                continue
            pool = [o for o in pool if not ((o[0] >= t[0] and o[1] > t[1]) or (o[0] > t[0] and o[1] >= t[1]))]
            pool.append(t)
            added = True
        if added:
            pool.sort(key=lambda t: (t[0], t[1]))
            improved = True
    if pool[0][0] < best_mk - 0.5:
        best_mk = pool[0][0]
        print('★ iter%d 新完工纪录: %d架 mk=%.1f en=%.2f (%.0fs)' % (it, len(pool[0][2]), pool[0][0], pool[0][1], time.time()-t0), flush=True)
        json.dump({'best': {'makespan': pool[0][0], 'energy': pool[0][1], 'flights': len(pool[0][2])},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s, list(bs)) for s, bs in f.route]} for f in pool[0][2]]},
                  open(os.path.join(OUTD, 'p2v75_champion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    elif not improved and it > 2:
        print(f'iter{it}: 无改进（连续无改善）', flush=True)
        break
    else:
        print(f'iter{it}: 池%02d 冠军 mk=%.1f en=%.2f (%.0fs)' % (len(pool), pool[0][0], pool[0][1], time.time()-t0), flush=True)
print('=== 最终帕累托池 ===')
for mk, en, fls in pool[:12]:
    print('  %3d架 mk=%7.1f (%5.1fmin) en=%6.2f' % (len(fls), mk, mk/60, en))
print('FINAL冠军: mk=%.1f (%.1fmin) en=%.2f 架%d — saved p2v75_champion.json' % (pool[0][0], pool[0][0]/60, pool[0][1], len(pool[0][2])), flush=True)
