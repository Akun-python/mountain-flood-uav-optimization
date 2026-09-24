# -*- coding: utf-8 -*-
"""
自适应大邻域搜索（ALNS, Adaptive Large Neighborhood Search）
- 破坏算子：整架次移除 / 按时限紧迫度移除 / 随机箱群移除 / 连片移除
- 修复算子：最省插（能量+时间+时限感知）/ 新建架次 / 贪心合并
- 自适应轮盘赌选择算子 + 模拟退火接收准则 + 重启
"""
import sys, os, math, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

from common import (Budget, fresh_rng, safe_eval, total_obj, rebuild,
                    tighten, all_feasible, clone_flights, Flight,
                    MODELS, try_merge, normalize_flight, feasible_models,
                    area_distance_table)


def _remove_flight(flights, idx):
    f = flights.pop(idx)
    return [b for _, bs in f.route for b in bs]


def _remove_boxes(flights, bids):
    removed = []
    bidset = set(bids)
    for f in flights:
        keep, drop = [], []
        for sid, bs in f.route:
            k = [b for b in bs if b not in bidset]
            d = [b for b in bs if b in bidset]
            removed.extend(d)
            if k:
                keep.append((sid, k))
        f.route = keep
        normalize_flight(f, f.data)
    return removed


def destroy_random_flights(data, flights, rng, n=2):
    flights = clone_flights(flights)
    if not flights:
        return flights, []
    n = min(n, len(flights))
    idxs = rng.sample(range(len(flights)), n)
    pool = []
    for i in sorted(idxs, reverse=True):
        pool.extend(_remove_flight(flights, i))
    return flights, pool


def destroy_by_deadline(data, flights, rng, k=6):
    """按时限紧迫度抽走 k 箱（首批/医疗/最早期望时限）。"""
    flights = clone_flights(flights)
    scores = []
    for f in flights:
        for b in f.box_ids:
            bx = data.boxes[b]
            t = min(bx['deadline_first'], bx['deadline_exp'])
            urg = 0.0 if math.isinf(t) else -t
            if bx['first_batch']:
                urg -= 1e6
            if bx['type'] == '医疗物资':
                urg -= 1e5
            scores.append((urg, rng.random(), b))
    scores.sort()
    bids = [b for _, _, b in scores[:min(k, len(scores))]]
    pool = _remove_boxes(flights, bids)
    return flights, pool


def destroy_random_boxes(data, flights, rng, k=6):
    flights = clone_flights(flights)
    allb = [b for f in flights for b in f.box_ids]
    if not allb:
        return flights, []
    rng.shuffle(allb)
    pool = _remove_boxes(flights, allb[:min(k, len(allb))])
    return flights, pool


def destroy_contiguous(data, flights, rng, segment=3):
    """移除一段连续架次（按当前列表序）形成"连片"破坏。"""
    flights = clone_flights(flights)
    n = len(flights)
    if n == 0:
        return flights, []
    seg = min(segment, n)
    start = rng.randrange(0, n - seg + 1)
    pool = []
    for i in range(start + seg - 1, start - 1, -1):
        pool.extend(_remove_flight(flights, i))
    return flights, pool


# 修复：插入候选过滤用区域距离表（只试同区/邻近区架次）
_AREA_DIST = {}


def _candidate_flights(data, flights, sid, cutoff=14000.0):
    """返回可尝试插入 sid 箱的架次列表（访问同区或邻近区）。"""
    global _AREA_DIST
    if not _AREA_DIST:
        _AREA_DIST = area_distance_table(data)
    out = []
    for f in flights:
        for s2, _ in f.route:
            if _AREA_DIST.get((sid, s2), math.inf) <= cutoff:
                out.append(f)
                break
    return out or flights


def repair_greedy(data, flights, pool, rng):
    """最优插入修复：按池中箱（时限升序）逐一插入现有架次或开新架次。"""
    flights = rebuild(flights)
    # 池内排序：紧迫度优先
    def rank(b):
        bx = data.boxes[b]
        t = min(bx['deadline_first'], bx['deadline_exp'])
        v = -1e6 if bx['first_batch'] else (0.0 if math.isinf(t) else -t)
        v += -1e5 if bx['type'] == '医疗物资' else 0.0
        return (v, rng.random())
    pool.sort(key=rank)
    next_fid = max([f.fid for f in flights], default=0) + 1
    for b in pool:
        sid = data.boxes[b]['area']
        best = None
        best_cost = math.inf
        cands = _candidate_flights(data, flights, sid)
        for f in cands:
            # 候选：把 b 并入该架次的 sid 站点（若已访问则加箱，否则加站）
            route = [(s, list(bs)) for s, bs in f.route]
            found = False
            for k in range(len(route)):
                if route[k][0] == sid:
                    route[k][1].append(b)
                    found = True
                    break
            if not found:
                route.append((sid, [b]))
            gs = feasible_models(data, route)
            if not gs:
                continue
            for g in gs:
                cand = Flight(next_fid, route, g, data)
                if not cand.is_feasible():
                    continue
                extra = cand.energy() * 0.4 + cand.duration() * 0.15
                # 交付时限感知：若该箱并入后预计交付超过时限，重罚
                dl = min(data.boxes[b]['deadline_first'], data.boxes[b]['deadline_exp'])
                if not math.isinf(dl):
                    est_delivery = cand.prep + cand.flight_time() + cand.handover_time()
                    if est_delivery > dl:
                        extra += 6000.0 * (1.0 + (est_delivery - dl) / 3600.0)
                if data.boxes[b]['first_batch'] and cand.nbox > 1:
                    extra += 2000.0  # 首批箱尽量独占紧凑架次
                if extra < best_cost - 1e-9:
                    best_cost = extra
                    best = (f, cand)
        if best is not None:
            old, cand = best
            cand.fid = old.fid
            flights = [cand if x.fid == old.fid else x for x in flights]
        else:
            # 开新架次
            g_ok = None
            for g in MODELS:
                f2 = Flight(next_fid, [(sid, [b])], g, data)
                if f2.is_feasible():
                    g_ok = g
                    break
            if g_ok is None:
                return None  # 修复失败（理论上不该发生）
            flights.append(Flight(next_fid, [(sid, [b])], g_ok, data))
            next_fid += 1
    # 轻量收紧：一轮合并 + 机型重选（控制开销）
    flights = tighten(data, flights, rng)
    return flights


def destroy_late_boxes(data, flights, rng, k=6, box_time=None):
    """按时效违规度抽箱：用最近一次调度得到的交付时刻，把最迟到的箱移除。"""
    flights = clone_flights(flights)
    if not box_time:
        return destroy_random_boxes(data, flights, rng, k)
    scored = []
    for f in flights:
        for b in f.box_ids:
            bx = data.boxes[b]
            t = box_time.get(b, math.inf)
            dl = min(bx['deadline_first'], bx['deadline_exp'])
            late = max(0.0, t - dl) if not math.isinf(dl) else 0.0
            if bx['first_batch']:
                late += 3600.0 if late <= 1e-6 else 0.0
            scored.append((late, rng.random(), b))
    scored.sort(reverse=True)
    bids = [b for _, _, b in scored[:min(k, len(scored))]]
    pool = _remove_boxes(flights, bids)
    return flights, pool


def destroy_many(data, flights, rng):
    """大破坏：移除约 1/3 的架次，制造结构性变化。"""
    flights = clone_flights(flights)
    n = len(flights)
    if n == 0:
        return flights, []
    k = max(2, n // 3)
    idxs = rng.sample(range(n), k)
    pool = []
    for i in sorted(idxs, reverse=True):
        pool.extend(_remove_flight(flights, i))
    return flights, pool


def alns_optimize(data, flights0, budget=None, seed=7, w_removal=0.5,
                  max_no_improve=600, restart_after=4000):
    rng = fresh_rng(seed)
    if budget is None:
        budget = Budget(20000)
    cur_met_state = {}

    def make_destroyers():
        return [
            lambda fl: destroy_random_flights(data, fl, rng, 3),
            lambda fl: destroy_many(data, fl, rng),
            lambda fl: destroy_by_deadline(data, fl, rng, 10),
            lambda fl: destroy_random_boxes(data, fl, rng, 8),
            lambda fl: destroy_contiguous(data, fl, rng, 3),
            lambda fl: destroy_late_boxes(data, fl, rng, 8,
                                          box_time=cur_met_state.get('box_time')),
        ]

    DESTROYERS = make_destroyers()
    w_d = [1.0] * len(DESTROYERS)
    score_d = [0.0] * len(DESTROYERS)
    cnt_d = [0.0] * len(DESTROYERS)

    flights = clone_flights(flights0)
    met, _ = safe_eval(data, flights, budget)
    if met is None:
        return None, None
    cur_met_state['box_time'] = met.get('box_time')
    best_flights = clone_flights(flights)
    best_met = copy.deepcopy(met)
    best_obj = total_obj(met)
    cur_flights, cur_met, cur_obj = flights, met, best_obj

    T0 = max(best_obj * 0.30, 1.0)
    it = 0
    no_improve = 0
    sigma1, sigma2, sigma3 = 1.5, 0.7, 0.2   # 全局新优 / 改善 / 接收
    while not budget.used_up():
        it += 1
        # 自适应选破坏算子
        tot = sum(w_d)
        r = rng.random() * tot
        acc = 0.0
        di = 0
        for i, w in enumerate(w_d):
            acc += w
            if r <= acc:
                di = i
                break
        # 执行破坏
        base = [f for f in cur_flights if f.box_ids]
        if not base:
            break
        destroyed, pool = DESTROYERS[di](base)
        if not pool:
            continue
        # 修复
        repaired = repair_greedy(data, destroyed, pool, rng)
        if repaired is None or not repaired or not all_feasible(repaired):
            cnt_d[di] += 1
            continue
        met2, _ = safe_eval(data, repaired, budget)
        if met2 is None:
            cnt_d[di] += 1
            continue
        obj2 = total_obj(met2)
        T = T0 * (0.999 ** it) + 1e-6
        delta = obj2 - cur_obj
        gain = 0.0
        if obj2 < best_obj - 1e-9:
            gain = sigma1
            best_flights = clone_flights(repaired)
            best_met = copy.deepcopy(met2)
            best_obj = obj2
            no_improve = 0
            cur_met_state['box_time'] = met2.get('box_time')
        elif obj2 < cur_obj - 1e-9:
            gain = sigma2
            no_improve += 1
        else:
            no_improve += 1
        if obj2 < cur_obj - 1e-9 or rng.random() < math.exp(-delta / max(T, 1e-9)):
            cur_flights, cur_met, cur_obj = repaired, met2, obj2
            cur_met_state['box_time'] = met2.get('box_time')
        score_d[di] += gain
        cnt_d[di] += 1
        # 每 100 次迭代更新权重
        if it % 100 == 0:
            for i in range(len(w_d)):
                if cnt_d[i] > 0:
                    w_d[i] = w_d[i] * 0.9 + 0.1 * (score_d[i] / cnt_d[i]) + 0.05
            score_d = [0.0] * len(w_d)
            cnt_d = [0.0] * len(w_d)
        if no_improve >= max_no_improve and it % 2000 == 0:
            # 重启：回到历史最优
            cur_flights = clone_flights(best_flights)
            cur_met = copy.deepcopy(best_met)
            cur_obj = best_obj
            cur_met_state['box_time'] = best_met.get('box_time')
            no_improve = 0
    return best_flights, best_met


if __name__ == '__main__':
    from common import make_initial, summarize, EVAL_BUDGET_DEFAULT
    import json
    data, p1g = Data(), None
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '结果')
    with open(os.path.join(base, 'p1_results.json'), encoding='utf-8') as fh:
        p1 = json.load(fh)
    flights0 = make_initial(data, p1['grouping'])
    fl, met = alns_optimize(data, flights0, budget=Budget(EVAL_BUDGET_DEFAULT), seed=7)
    print(summarize(met))