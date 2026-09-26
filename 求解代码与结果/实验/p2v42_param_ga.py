# -*- coding: utf-8 -*-
"""v42-π：23-25 架次参数级寻优（遗传算法 + 局部搜索）。
基因 = 区→机型分配（15 区 A/B/C）+ C/B 装载上限 + A 拼趟开关 + 首飞批策略。
多通道目标聚合（完工主导/平衡/能耗主导）× 世代进化 → 合规帕累托前沿。
输出 结果/进化_v42/param_pareto.json。"""
import sys, os, json, random, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
OUT = os.path.join(EVO, 'param_pareto.json')

AREAS = ['S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007', 'S008',
         'S009', 'S010', 'S011', 'S012', 'S013', 'S014', 'S015']
MODELS = {'A': 0, 'B': 1, 'C': 2}

def build(assigns, cap_c, cap_b, cap_a, merge_on):
    """按基因构造趟集。assigns: {area: 'A'|'B'|'C'}；cap: 每趟箱数上限。"""
    data = Data()
    data.area_boxes = {s: list(bs) for s, bs in data.area_boxes.items()}
    caps = {'A': cap_a, 'B': cap_b, 'C': cap_c}
    fl, fid = [], 1

    def is_feasible(area, cand, model):
        f = Flight(0, [(area, cand)], model, data)
        return f.is_feasible(), f

    def take(area, model, first_pass=False):
        p = data.uav_types[model]
        pool = list(data.area_boxes[area])
        if not pool:
            return None, None
        mx = caps[model]
        if first_pass:
            fb = [b for b in pool if b.endswith('-01')]
            fbs = sorted(fb, key=lambda b: not data.boxes[b]['first_batch'])
            best = None
            for bn in range(min(len(fbs), mx), 0, -1):
                base = fbs[:bn]
                rest = [b for b in pool if b not in fbs]
                cand = list(base)
                for b in sorted(rest, key=lambda x: -data.boxes[x]['mass']):
                    if len(cand) >= mx:
                        break
                    if sum(data.boxes[x]['mass'] for x in cand) + data.boxes[b]['mass'] <= p['Q'] + 1e-9 \
                       and sum(data.boxes[x]['vol'] for x in cand) + data.boxes[b]['vol'] <= p['V'] + 1e-9:
                        cand.append(b)
                ok, f = is_feasible(area, cand, model)
                if ok:
                    best = cand
                    break
            if best is None:
                return None, None
            cand = best
        else:
            best = None
            for n in range(mx, 0, -1):
                c = sorted(pool, key=lambda b: -data.boxes[b]['mass'])[:n]
                o, f2 = is_feasible(area, c, model)
                if o:
                    best, f = c, f2
                    break
            if best is None:
                return None, None
            cand = best
        for b in cand:
            data.area_boxes[area].remove(b)
        f.fid = fid
        return cand, f

    # 按机型分组区，先首飞批趟（-01 基座）再满载
    rem = []
    for model in ('C', 'B', 'A'):
        areas = [s for s in AREAS if assigns[s] == model]
        for s in areas:
            cand, f = take(s, model, first_pass=True)
            if f:
                fl.append(f); fid += 1
        for s in areas:
            while data.area_boxes[s]:
                cand, f = take(s, model, first_pass=False)
                if f is None:
                    b = data.area_boxes[s].pop(0)
                    rem.append((s, b))
                    continue
                if len(cand) == 1 and model == 'A':
                    # A 单箱趟压入 merge 池（跨区拼），不全额起飞
                    rem.append((s, cand[0]))
                    continue
                fl.append(f); fid += 1
    # 剩余拼趟（A 跨区）：合并以上 rem 池 + 各机型循环后仍残留的箱
    for s in AREAS:
        while data.area_boxes[s]:
            rem.append((s, data.area_boxes[s].pop(0)))
    if merge_on:
        while rem:
            q = sorted(rem, key=lambda x: -data.boxes[x[1]]['mass'])
            take_c, m, v, seen = [], 0.0, 0.0, set()
            for s, b in q:
                if len(take_c) >= caps['A']:
                    break
                if s in seen:
                    continue
                bm, bv = data.boxes[b]['mass'], data.boxes[b]['vol']
                if m + bm > 25 + 1e-9 or v + bv > 0.06 + 1e-9:
                    continue
                take_c.append((s, [b])); seen.add(s); m += bm; v += bv
            if not take_c:
                s, b = rem.pop(0)
                f = Flight(fid, [(s, [b])], 'A', data); f.fid = fid; fl.append(f); fid += 1
                continue
            f = Flight(fid, take_c, 'A', data)
            if f.is_feasible():
                f.fid = fid; fl.append(f); fid += 1
                for s, bs in take_c:
                    rem.remove((s, bs[0]))
            else:
                s, b = rem.pop(0)
                f = Flight(fid, [(s, [b])], 'A', data); f.fid = fid; fl.append(f); fid += 1
    else:
        for s, b in rem:
            f = Flight(fid, [(s, [b])], 'A', data); f.fid = fid; fl.append(f); fid += 1
    return fl

def evaluate_sol(fl):
    data = Data()
    sch, _ = dispatch(data, fl)
    met = evaluate(data, fl, sch)
    nbox = sum(len(bs) for f in fl for _, bs in f.route)
    uniq = len(set(b for f in fl for _, bs in f.route for b in bs))
    return {'flights': len(fl), 'makespan': met['makespan'], 'energy': met['energy'],
            'hard_ok': met['hard_ok'], 'tardy_w': met['tardy_w'], 'bad': len(met['bad_zones']),
            'nbox': nbox, 'uniq': uniq}

def fitness(met, lam):
    if not met['hard_ok'] or met['tardy_w'] > 1e-6 or met['bad'] > 0:
        return 1e12
    if met['nbox'] != 80 or met['uniq'] != 80:
        return 1e12
    nf = met['flights']
    pen = 0.0
    if nf < 23:
        pen += (23 - nf) * 2000
    elif nf > 25:
        pen += (nf - 25) * 2000
    return met['makespan'] + lam * met['energy'] + pen

def gen_rand(rng):
    assigns = {s: rng.choice('ABC') for s in AREAS}
    cap_c = rng.randint(5, 7)
    cap_b = rng.randint(2, 3)
    cap_a = 2
    merge_on = rng.random() < 0.7
    return {'assigns': assigns, 'cap_c': cap_c, 'cap_b': cap_b,
            'cap_a': cap_a, 'merge_on': merge_on}

def heuristic_seeds():
    """启发式种子（区间→机型分配模式），保证 23-25 架合规起点。"""
    C, B, A = 'C', 'B', 'A'
    allset = set(AREAS)
    seeds = []
    # S1: C 重区 5、B 重区 3、A 余 7（v13 式）
    c1 = set(['S001', 'S002', 'S003', 'S004', 'S005'])
    b1 = set(['S006', 'S007', 'S008'])
    seeds.append({s: C for s in c1} | {s: B for s in b1} | {s: A for s in allset - c1 - b1})
    # S2: C S001-S004+S008、B S005-S007、A 余
    c2 = set(['S001', 'S002', 'S003', 'S004', 'S008'])
    b2 = set(['S005', 'S006', 'S007'])
    seeds.append({s: C for s in c2} | {s: B for s in b2} | {s: A for s in allset - c2 - b2})
    # S3: C 重区 6、B S007-S008、A 余
    c3 = set(['S001', 'S002', 'S003', 'S004', 'S005', 'S006'])
    b3 = set(['S007', 'S008'])
    seeds.append({s: C for s in c3} | {s: B for s in b3} | {s: A for s in allset - c3 - b3})
    # S4: C 前 3、B S004-S008、A 余（B 重区 3 箱）
    c4 = set(['S001', 'S002', 'S003'])
    b4 = set(['S004', 'S005', 'S006', 'S007', 'S008'])
    seeds.append({s: C for s in c4} | {s: B for s in b4} | {s: A for s in allset - c4 - b4})
    # S5: C S001-S004、B S010-S015、A S005-S009（B 轻区 3 箱）
    c5 = set(['S001', 'S002', 'S003', 'S004'])
    b5 = set(['S010', 'S011', 'S012', 'S013', 'S014', 'S015'])
    seeds.append({s: C for s in c5} | {s: B for s in b5} | {s: A for s in allset - c5 - b5})
    out = []
    for i, asg in enumerate(seeds):
        g = {'assigns': asg, 'cap_c': 7, 'cap_b': 3, 'cap_a': 2,
             'merge_on': True}
        if i in (1, 4):
            g['cap_b'] = 2
        out.append(g)
    return out

def mutate(g, rng, rate=0.20, direction=True):
    g = json.loads(json.dumps(g))
    for s in AREAS:
        if rng.random() < rate:
            cur = g['assigns'][s]
            if direction:
                # 方向性：A 区倾向改为 B/C（降架次），C/B 区倾向保留
                if cur == 'A':
                    g['assigns'][s] = rng.choice('BC')
                else:
                    g['assigns'][s] = rng.choice('ABC')
            else:
                g['assigns'][s] = rng.choice('ABC')
    if rng.random() < rate:
        g['cap_c'] = max(4, min(7, g['cap_c'] + rng.choice([-1, 1])))
    if rng.random() < rate:
        g['cap_b'] = max(2, min(3, g['cap_b'] + rng.choice([-1, 1])))
    if rng.random() < rate:
        g['merge_on'] = not g['merge_on']
    return g

def crossover(a, b, rng):
    c = json.loads(json.dumps(a))
    for s in AREAS:
        if rng.random() < 0.5:
            c['assigns'][s] = b['assigns'][s]
    return c

def main(pop_size=18, gens=18, seeds=(3, 7, 11)):
    rng = random.Random(777)
    heur = heuristic_seeds()
    pareto, evaled = [], {}
    for lam in (0.1, 0.6, 1.5, 4.0):
        pop = [json.loads(json.dumps(h)) for h in heur]
        while len(pop) < pop_size:
            if rng.random() < 0.5:
                pop.append(mutate(rng.choice(heur), rng, rate=0.3))
            else:
                pop.append(gen_rand(rng))
        fits = []
        for g in pop:
            met = evaluate_sol(build(**g))
            evaled[json.dumps(g)] = met
            fits.append(fitness(met, lam))
        for gen in range(gens):
            newpop = []
            ranked = sorted(zip(pop, fits), key=lambda x: x[1])
            newpop.append(ranked[0][0]); newpop.append(ranked[1][0])
            while len(newpop) < pop_size:
                t = sorted(rng.sample(list(zip(pop, fits)), 3), key=lambda x: x[1])
                p1 = t[0][0] if rng.random() < 0.8 else t[1][0]
                t2 = sorted(rng.sample(list(zip(pop, fits)), 3), key=lambda x: x[1])
                p2 = t2[0][0] if rng.random() < 0.8 else t2[1][0]
                child = crossover(p1, p2, rng)
                child = mutate(child, rng)
                newpop.append(child)
            pop = newpop
            fits = []
            for g in pop:
                key = json.dumps(g)
                met = evaled.get(key)
                if met is None:
                    met = evaluate_sol(build(**g))
                    evaled[key] = met
                fits.append(fitness(met, lam))
            # 更新帕累托
            for g, ft in zip(pop, fits):
                met = evaled[json.dumps(g)]
                if ft < 1e11:
                    pareto.append((met['flights'], met['makespan'], met['energy'], json.dumps(g)))
            best_c = [(m['flights'], m['makespan'], m['energy'])
                      for m in (evaled[json.dumps(g)] for g in pop)
                      if m['flights'] and (23 <= m['flights'] <= 25)
                      and m['hard_ok'] and m['tardy_w'] < 1e-6 and m['bad'] == 0]
            b = min(best_c) if best_c else None
            print('λ=%.1f gen=%d best=%.0f 合规23-25:%s' % (
                lam, gen, min(fits), ('%d架/%d/%.2f' % b) if b else '无'), flush=True)
            with open(os.path.join(EVO, 'param_progress.json'), 'w', encoding='utf-8') as f:
                json.dump({'lam': lam, 'gen': gen, 'best23_25': b, 'npareto': len(pareto)}, f)
    # 去重 + 非支配筛选（23-25 架）
    clean = {}
    for nf, mk, en, gj in pareto:
        clean[(round(mk, 1), round(en, 3))] = (nf, mk, en, gj)
    pts = [(nf, mk, en, gj) for (mk, en), (nf, mk2, en2, gj) in clean.items()]
    non_dom = []
    for p in pts:
        if not (23 <= p[0] <= 25):
            continue
        dominated = False
        for q in pts:
            if q is p:
                continue
            if not (23 <= q[0] <= 25):
                continue
            if q[1] <= p[1] + 1e-6 and q[2] <= p[2] + 1e-6 and (q[1] < p[1] - 1e-6 or q[2] < p[2] - 1e-6):
                dominated = True
                break
        if not dominated:
            non_dom.append(p)
    non_dom.sort(key=lambda x: (x[1], x[2]))
    out = {'solver': 'v42-param-ga-23-25', 'pareto': []}
    for nf, mk, en, gj in non_dom:
        g = json.loads(gj)
        out['pareto'].append({'flights': nf, 'makespan': round(mk, 1), 'energy': round(en, 3),
                              'gene': g})
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('PARETO %d 点:' % len(non_dom))
    for nf, mk, en, gj in non_dom:
        print('  %d 架  mk=%7.1f  e=%6.3f' % (nf, mk, en))
    print('saved param_pareto.json')

if __name__ == '__main__':
    t0 = time.time()
    main()
    print('总耗时 %.0fs' % (time.time() - t0))