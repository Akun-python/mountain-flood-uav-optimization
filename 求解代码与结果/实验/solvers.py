# -*- coding: utf-8 -*-
"""
元启发式家族 集成模块
- sa_baseline: 基线模拟退火（与原 p2_solve 同算子），改为预算驱动以便对比
- ga_optimize: 分组遗传算法（GGA，路线继承交叉 + 稳态替换）
- tabu_optimize: 禁忌搜索（移动/换箱/换机型算子 + 禁忌表 + 藐视准则）
- grasp_optimize: 随机化贪心构造 + 局部搜索（多起点）
```
"""
import sys, os, math, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (Budget, fresh_rng, safe_eval, total_obj, rebuild,
                    tighten, all_feasible, clone_flights, Flight,
                    MODELS, try_merge, normalize_flight, feasible_models)


# ---------------------------------------------------------------------------
# SA 基线
# ---------------------------------------------------------------------------
def sa_baseline(data, flights0, budget, seed=7):
    rng = fresh_rng(seed)
    flights = clone_flights(flights0)
    met, _ = safe_eval(data, flights, budget)
    if met is None:
        return None, None
    best_flights = clone_flights(flights)
    best_met = copy.deepcopy(met)
    best_obj = total_obj(met)
    cur = (flights, met, best_obj)
    T0 = best_obj * 0.12
    it = 0
    while not budget.used_up():
        it += 1
        T = T0 * (1.0 - it / (budget.limit + 1)) ** 1.2 + 1e-6
        fl = clone_flights(cur[0])
        n = len(fl)
        op = rng.random()
        if op < 0.25 and n > 1:
            i, j = rng.sample(range(n), 2)
            m = try_merge(data, fl[i], fl[j])
            if m is not None:
                m.fid = fl[i].fid
                fl[i] = m
                fl.pop(j)
        elif op < 0.42:
            i = rng.randrange(n)
            r = fl[i].route
            rr = rng.randrange(len(r))
            sid, bs = r[rr]
            if len(bs) >= 2:
                k = rng.randrange(1, len(bs))
                part, rest = bs[:k], bs[k:]
                fl[i].route[rr] = (sid, rest)
                normalize_flight(fl[i], data)
                nf = Flight(max((f.fid for f in fl), default=0) + 1, [(sid, part)],
                            fl[i].model if feasible_models(data, [(sid, part)]) else 'A', data)
                if not nf.is_feasible():
                    continue
                fl.append(nf)
        elif op < 0.58:
            i = rng.randrange(n)
            if len(fl[i].route) > 1:
                a, b = rng.sample(range(len(fl[i].route)), 2)
                fl[i].route[a], fl[i].route[b] = fl[i].route[b], fl[i].route[a]
                normalize_flight(fl[i], data)
        elif op < 0.75 and n > 1:
            i, j = rng.sample(range(n), 2)
            ri = rng.randrange(len(fl[i].route))
            rj = rng.randrange(len(fl[j].route))
            if fl[i].route[ri][0] == fl[j].route[rj][0]:
                bs_i = fl[i].route[ri][1]
                bs_j = fl[j].route[rj][1]
                if bs_i:
                    b = rng.choice(bs_i)
                    fl[i].route[ri] = (fl[i].route[ri][0], [x for x in bs_i if x != b])
                    fl[j].route[rj] = (fl[j].route[rj][0], bs_j + [b])
                    normalize_flight(fl[i], data)
                    normalize_flight(fl[j], data)
        else:
            i = rng.randrange(n)
            cand = [g for g in MODELS if g != fl[i].model]
            rng.shuffle(cand)
            for g in cand:
                f2 = Flight(fl[i].fid, [(s, list(b)) for s, b in fl[i].route], g, data)
                if f2.is_feasible():
                    fl[i] = f2
                    break
        fl = [f for f in fl if f.box_ids]
        if not fl or not all_feasible(fl):
            continue
        met2, _ = safe_eval(data, fl, budget)
        if met2 is None:
            continue
        obj2 = total_obj(met2)
        if obj2 < best_obj - 1e-9:
            best_flights = clone_flights(fl)
            best_met = copy.deepcopy(met2)
            best_obj = obj2
        if obj2 < cur[2] or rng.random() < math.exp((cur[2] - obj2) / max(T, 1e-9)):
            cur = (fl, met2, obj2)
    return best_flights, best_met


# ---------------------------------------------------------------------------
# GA（路线继承 + 稳态替换）
# ---------------------------------------------------------------------------
def _route_inherit_crossover(data, p1, p2, rng):
    """子代：随机取父1的若干条路线继承，父2 未覆盖的箱按父2分组补全。"""
    p1b = [f for f in p1 if f.box_ids]
    if not p1b:
        p1b = p2
    k = rng.randint(1, max(1, len(p1b)))
    seeds = rng.sample(p1b, k)
    child = clone_flights(seeds)
    covered = set(b for f in child for b in f.box_ids)
    remain = [b for f in p2 for b in f.box_ids if b not in covered]
    # 按父2分组补全
    p2_groups = [[b for _, bs in f.route for b in bs] for f in p2 if f.box_ids]
    fid = max([f.fid for f in child], default=0) + 1
    for group in p2_groups:
        gm = [b for b in group if b in remain]
        if not gm:
            continue
        route_map = {}
        for b in gm:
            route_map.setdefault(data.boxes[b]['area'], []).append(b)
        route = [(sid, bs) for sid, bs in route_map.items()]
        route.sort(key=lambda x: x[0])
        g_ok = None
        for g in MODELS:
            f = Flight(fid, route, g, data)
            if f.is_feasible():
                g_ok = g
                break
        if g_ok is None:
            # 超载：拆成可装载团（贪心）
            boxes = [b for b in gm]
            boxes.sort(key=lambda b: -data.boxes[b]['mass'])
            cur = []
            for b in boxes:
                cur.append(b)
                rr = {}
                for bb in cur:
                    rr.setdefault(data.boxes[bb]['area'], []).append(bb)
                rl = [(s, bs) for s, bs in rr.items()]
                if not any(Flight(fid, rl, g, data).is_feasible() for g in MODELS):
                    cur.pop()
                    children = [b for b in cur and cur or []]
                    rr2 = {}
                    for bb in children:
                        rr2.setdefault(data.boxes[bb]['area'], []).append(bb)
                    r2 = [(s, bs) for s, bs in rr2.items()]
                    for g2 in MODELS:
                        f2 = Flight(fid, r2, g2, data)
                        if f2.is_feasible():
                            child.append(f2)
                            fid += 1
                            break
                    cur = [b]
            if cur:
                rr3 = {}
                for bb in cur:
                    rr3.setdefault(data.boxes[bb]['area'], []).append(bb)
                r3 = [(s, bs) for s, bs in rr3.items()]
                for g3 in MODELS:
                    f3 = Flight(fid, r3, g3, data)
                    if f3.is_feasible():
                        child.append(f3)
                        fid += 1
                        break
            continue
        child.append(Flight(fid, route, g_ok, data))
        fid += 1
    child = tighten(data, child, rng)
    return child


def _mutate(data, flights, rng):
    if not flights:
        return flights
    fl = clone_flights(flights)
    i = rng.randrange(len(fl))
    kind = rng.random()
    if kind < 0.4:
        # 移箱到同区另一架次
        i2 = rng.randrange(len(fl))
        if i2 == i:
            i2 = (i2 + 1) % len(fl)
        ri = rng.randrange(len(fl[i].route))
        rj = rng.randrange(len(fl[i2].route))
        bs_i = fl[i].route[ri][1]
        if bs_i:
            b = rng.choice(bs_i)
            fl[i].route[ri] = (fl[i].route[ri][0], [x for x in bs_i if x != b])
            fl[i2].route[rj] = (fl[i2].route[rj][0], fl[i2].route[rj][1] + [b])
            normalize_flight(fl[i], data)
            normalize_flight(fl[i2], data)
    elif kind < 0.7:
        # 换机型
        cand = [g for g in MODELS if g != fl[i].model]
        rng.shuffle(cand)
        for g in cand:
            f2 = Flight(fl[i].fid, [(s, list(b)) for s, b in fl[i].route], g, data)
            if f2.is_feasible():
                fl[i] = f2
                break
    elif kind < 0.9 and len(fl[i].route) > 1:
        a, b = rng.sample(range(len(fl[i].route)), 2)
        fl[i].route[a], fl[i].route[b] = fl[i].route[b], fl[i].route[a]
        normalize_flight(fl[i], data)
    else:
        # 重建一个小架次
        pass
    return rebuild([f for f in fl if f.box_ids])


def _diverse_walk(data, flights, rng, steps=4):
    """从种子出发做随机算子游走（合并/拆分/移箱/换机型），只保持可行，不评价目标。
    用于 GA 初始种群去同质化。"""
    fl = clone_flights(flights)
    for _ in range(steps):
        n = len(fl)
        if n == 0:
            break
        op = rng.random()
        if op < 0.35 and n > 1:
            i, j = rng.sample(range(n), 2)
            m = try_merge(data, fl[i], fl[j])
            if m is not None:
                m.fid = fl[i].fid
                fl[i] = m
                fl.pop(j)
        elif op < 0.55 and n > 1:
            i, j = rng.sample(range(n), 2)
            ri = rng.randrange(len(fl[i].route))
            rj = rng.randrange(len(fl[j].route))
            si, sj = fl[i].route[ri][0], fl[j].route[rj][0]
            bs_i = fl[i].route[ri][1]
            if bs_i:
                b = rng.choice(bs_i)
                fl[i].route[ri] = (si, [x for x in bs_i if x != b])
                fl[j].route[rj] = (sj, fl[j].route[rj][1] + [b])
                normalize_flight(fl[i], data)
                normalize_flight(fl[j], data)
                fl = [f for f in fl if f.box_ids]
        elif op < 0.75:
            i = rng.randrange(n)
            cand = [g for g in MODELS if g != fl[i].model]
            rng.shuffle(cand)
            for g in cand:
                f2 = Flight(fl[i].fid, [(s, list(b)) for s, b in fl[i].route], g, data)
                if f2.is_feasible():
                    fl[i] = f2
                    break
        else:
            # 拆分
            i = rng.randrange(n)
            if len(fl[i].route) >= 1:
                ri = rng.randrange(len(fl[i].route))
                sid, bs = fl[i].route[ri]
                if len(bs) >= 2:
                    k = rng.randrange(1, len(bs))
                    part, rest = bs[:k], bs[k:]
                    fl[i].route[ri] = (sid, rest)
                    normalize_flight(fl[i], data)
                    nf = Flight(max((f.fid for f in fl), default=0) + 1, [(sid, part)],
                                fl[i].model if feasible_models(data, [(sid, part)]) else 'A', data)
                    if nf.is_feasible():
                        fl.append(nf)
        fl = [f for f in fl if f.box_ids]
        if fl and not all_feasible(fl):
            break
    return rebuild([f for f in fl if f.box_ids])


def ga_optimize(data, flights0, budget, seed=7, pop=28, elite=2):
    rng = fresh_rng(seed)
    # 初始种群：种子本身 + 多样化随机游走（避免同质化导致交叉失效）
    pop_list = [clone_flights(flights0)]
    for _ in range(pop - 1):
        ind = _diverse_walk(data, flights0, rng, steps=rng.randint(2, 6))
        if not ind or not all_feasible(ind):
            pop_list.append(clone_flights(flights0))
        else:
            pop_list.append(ind)
    # 评估初始种群
    scored = []
    for p in pop_list:
        met, _ = safe_eval(data, p, budget)
        scored.append((total_obj(met) if met else math.inf, copy.deepcopy(met), p))
    scored = [s for s in scored if s[0] != math.inf]
    if not scored:
        return None, None
    scored.sort(key=lambda x: x[0])
    while not budget.used_up():
        # 锦标赛选择父代
        def pick():
            a = scored[rng.randrange(len(scored))]
            b = scored[rng.randrange(len(scored))]
            return a if a[0] <= b[0] else b
        p1 = pick(); p2 = pick()
        child = _route_inherit_crossover(data, p1[2], p2[2], rng)
        child = _mutate(data, child, rng) if rng.random() < 0.7 else child
        child = [f for f in child if f.box_ids]
        if not child or not all_feasible(child):
            continue
        met, _ = safe_eval(data, child, budget)
        if met is None:
            continue
        obj = total_obj(met)
        if obj >= scored[-1][0] and rng.random() < 0.2:
            continue
        scored.append((obj, copy.deepcopy(met), child))
        scored.sort(key=lambda x: x[0])
        scored = scored[:pop]
    best_obj, best_met, best_fl = scored[0]
    return best_fl, best_met


# ---------------------------------------------------------------------------
# Tabu 搜索
# ---------------------------------------------------------------------------
def _neighborhood_move(data, flights, rng):
    """返回 (new_flights, tabu_key) 或 (None,None)。多种算子，有限试探。"""
    n = len(flights)
    if n < 1:
        return None, None
    for _ in range(14):
        fl = clone_flights(flights)
        op = rng.random()
        if op < 0.35 and n > 1:
            # 合并两架次
            i, j = rng.sample(range(n), 2)
            m = try_merge(data, fl[i], fl[j])
            if m is not None:
                lo, hi = min(i, j), max(i, j)
                m.fid = fl[lo].fid
                fl[lo] = m
                fl.pop(hi)
                return fl, ('merge', lo, hi)
        elif op < 0.65 and n > 1:
            # 移箱（同区优先，允许跨区产生可行新组合）
            i = rng.randrange(n)
            j = rng.randrange(n)
            if i == j:
                continue
            ri = rng.randrange(len(fl[i].route))
            rj = rng.randrange(len(fl[j].route))
            bs = fl[i].route[ri][1]
            if not bs:
                continue
            b = rng.choice(bs)
            fl[i].route[ri] = (fl[i].route[ri][0], [x for x in bs if x != b])
            fl[j].route[rj] = (fl[j].route[rj][0], fl[j].route[rj][1] + [b])
            normalize_flight(fl[i], data)
            normalize_flight(fl[j], data)
            fl = [f for f in fl if f.box_ids]
            if fl and all_feasible(fl):
                return fl, ('move', b, j)
        elif op < 0.85:
            # 换机型（能耗最低可行）
            i = rng.randrange(n)
            best = None
            best_e = math.inf
            for g in MODELS:
                if g == fl[i].model:
                    continue
                cand = Flight(fl[i].fid, [(s, list(b)) for s, b in fl[i].route], g, data)
                if cand.is_feasible() and cand.energy() < best_e:
                    best_e = cand.energy()
                    best = cand
            if best is not None:
                fl[i] = best
                return fl, ('model', i, best.model)
        else:
            # 拆分一架次为两架次
            i = rng.randrange(n)
            if len(fl[i].route) == 1:
                sid, bs = fl[i].route[0]
                if len(bs) >= 2:
                    k = rng.randrange(1, len(bs))
                    part, rest = bs[:k], bs[k:]
                    fl[i].route[0] = (sid, rest)
                    normalize_flight(fl[i], data)
                    nf = Flight(max((f.fid for f in fl), default=0) + 1, [(sid, part)], fl[i].model, data)
                    if fl[i].box_ids and nf.is_feasible() and fl[i].is_feasible():
                        fl.append(nf)
                        return fl, ('split', i)
    return None, None


def tabu_optimize(data, flights0, budget, seed=7, tabu_len=240, n_neighbors=6):
    rng = fresh_rng(seed)
    flights = clone_flights(flights0)
    met, _ = safe_eval(data, flights, budget)
    if met is None:
        return None, None
    best_fl, best_met, best_obj = clone_flights(flights), copy.deepcopy(met), total_obj(met)
    cur_fl, cur_met, cur_obj = flights, met, best_obj
    tabu = {}
    while not budget.used_up():
        cands = []
        for _ in range(n_neighbors):
            ne, key = _neighborhood_move(data, cur_fl, rng)
            if ne is None:
                continue
            if not all_feasible(ne):
                continue
            met2, _ = safe_eval(data, ne, budget)
            if met2 is None:
                continue
            cands.append((total_obj(met2), copy.deepcopy(met2), ne, key))
        if not cands:
            break
        cands.sort(key=lambda x: x[0])
        chosen = None
        for c in cands:
            obj2, met2, ne, key = c
            if key in tabu and tabu[key] > 0 and obj2 >= best_obj - 1e-9:
                continue
            chosen = c
            break
        if chosen is None:
            chosen = cands[0]
        obj2, met2, ne, key = chosen
        # 更新禁忌表
        for k in list(tabu):
            tabu[k] -= 1
            if tabu[k] <= 0:
                del tabu[k]
        if key is not None:
            tabu[key] = tabu_len
        if obj2 < best_obj - 1e-9:
            best_obj, best_met, best_fl = obj2, copy.deepcopy(met2), clone_flights(ne)
        cur_fl, cur_met, cur_obj = ne, met2, obj2
    return best_fl, best_met


# ---------------------------------------------------------------------------
# GRASP
# ---------------------------------------------------------------------------
def grasp_optimize(data, flights0, budget, seed=7, restarts_equal=0.25, alpha=0.3):
    rng = fresh_rng(seed)
    best_fl, best_met, best_obj = None, None, math.inf
    first = True
    while not budget.used_up():
        base = clone_flights(flights0) if first else rebuild_random(data, flights0, rng)
        first = False
        fl = first_improve(data, base, rng, budget)
        if fl is None or not fl:
            continue
        met, _ = safe_eval(data, fl, budget)
        if met is None:
            continue
        obj = total_obj(met)
        if obj < best_obj - 1e-9:
            best_obj, best_met, best_fl = obj, copy.deepcopy(met), clone_flights(fl)
    return best_fl, best_met


def first_improve(data, flights, rng, budget):
    """目标感知的首改进局部搜索：对随机候选算子（合并优先）施加并验证目标。"""
    fl = clone_flights(flights)
    met, _ = safe_eval(data, fl, budget)
    if met is None:
        return None
    cur_obj = total_obj(met)
    improved = True
    while improved and not budget.used_up():
        improved = False
        n = len(fl)
        if n < 2:
            break
        order = list(range(n))
        rng.shuffle(order)
        for i in order:
            if budget.used_up():
                break
            for j in range(i + 1, n):
                m = try_merge(data, fl[i], fl[j])
                if m is None:
                    continue
                cand = clone_flights(fl)
                cand[i] = m
                cand.pop(j)
                cand = [f for f in cand if f.box_ids]
                if not all_feasible(cand):
                    continue
                met2, _ = safe_eval(data, cand, budget)
                if met2 is None:
                    continue
                if total_obj(met2) < cur_obj - 1e-9:
                    fl = cand
                    cur_obj = total_obj(met2)
                    improved = True
                    break
            if improved:
                break
    return fl


def rebuild_random(data, flights0, rng):
    """随机化构造：在初始可行解内按区域打散重装（保持同区约束，保证可行），
    然后用 tighten 局部收紧。GRASP 的多样性来自随机装箱 + 重合并。"""
    # 按区域收集全部箱
    by_area = {}
    for f in flights0:
        for sid, bs in f.route:
            by_area.setdefault(sid, []).extend(bs)
    fl = []
    fid = 1
    for sid, boxes in by_area.items():
        rng.shuffle(boxes)
        # 时限升序（紧急箱先分配小机型架次）
        boxes.sort(key=lambda b: (0 if data.boxes[b]['first_batch'] or data.boxes[b]['type'] == '医疗物资'
                                  else 1, min(data.boxes[b]['deadline_first'],
                                              data.boxes[b]['deadline_exp'])))
        # 贪心按容量上限分组（同区域）
        groups = []
        cur = []
        for b in boxes:
            m_new = sum(data.boxes[x]['mass'] for x in cur) + data.boxes[b]['mass']
            if cur and m_new > 30.0:
                groups.append(cur)
                cur = []
            cur.append(b)
        if cur:
            groups.append(cur)
        for group in groups:
            route = [(sid, group)]
            g_ok = None
            for g in MODELS:
                f = Flight(fid, route, g, data)
                if f.is_feasible():
                    g_ok = g
                    break
            if g_ok is not None:
                fl.append(Flight(fid, route, g_ok, data))
                fid += 1
            else:
                # 超载：拆成可装载小团
                for b in group:
                    f1 = Flight(fid, [(sid, [b])], 'A', data)
                    f2 = Flight(fid, [(sid, [b])], 'B', data)
                    f3 = Flight(fid, [(sid, [b])], 'C', data)
                    for cand in (f3, f2, f1):
                        if cand.is_feasible():
                            fl.append(cand)
                            fid += 1
                            break
    fl = tighten(data, [f for f in fl if f.box_ids], rng)
    return fl if all_feasible(fl) else clone_flights(flights0)


def rcl_local(data, flights, rng, budget):
    flights = rebuild(flights) or flights
    improved = True
    while improved:
        improved = False
        for i in range(len(flights)):
            for j in range(i + 1, len(flights)):
                m = try_merge(data, flights[i], flights[j])
                if m is not None:
                    save = (flights[i].duration() + flights[j].duration()) - m.duration()
                    if save > 1e-6:
                        m.fid = flights[i].fid
                        flights[i] = m
                        flights.pop(j)
                        improved = True
                        break
            if improved:
                break
    return flights