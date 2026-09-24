# -*- coding: utf-8 -*-
"""
ALNS 机队并行度感知变体：在修复算子中加入机型负载均衡——
新建/专用架次选择机型时考虑各机型累计飞行时长，避免紧急箱集中挤在
单一机型上造成该机型在线队列过长而迟到。其余算子与 alns.py 一致。
"""
import sys, os, math, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

from common import (Budget, fresh_rng, safe_eval, total_obj, rebuild,
                    tighten, all_feasible, clone_flights, Flight, MODELS,
                    normalize_flight, feasible_models)
import alns as A

MODEL_LOAD = None  # {model: 累计飞行时长}，由 repair 前更新


def _model_load(flights):
    load = {m: 0.0 for m in MODELS}
    for f in flights:
        load[f.model] += f.flight_time()
    return load


def _pick_model_by_load(load, feasible, tol=120.0):
    """在可行机型中按负载均衡选：交付时刻相差 tol 内者取负载最小的。"""
    if not feasible:
        return None
    if len(feasible) == 1:
        return feasible[0]
    mx = max(load.values()) or 1.0
    best = min(feasible, key=lambda g: (load[g] / mx, g))
    return best


def repair_fleet(data, flights, pool, rng):
    """机队均衡修复：紧急箱专用架次 + 普通箱贪心插入，机型选择按负载均衡。"""
    global MODEL_LOAD
    flights = rebuild(flights)
    MODEL_LOAD = _model_load(flights)
    next_fid = max([f.fid for f in flights], default=0) + 1
    # ---- 紧急箱专用架次（机型均衡版）----
    by_area = {}
    for b in pool:
        if A._is_urgent(data, b):
            by_area.setdefault(data.boxes[b]['area'], []).append(b)
    normal = [b for b in pool if not A._is_urgent(data, b)]
    for sid in sorted(by_area):
        rem = list(by_area[sid])
        while rem:
            feas = []
            for g in MODELS:
                f2 = Flight(next_fid, [(sid, list(rem))], g, data)
                if f2.is_feasible():
                    feas.append(g)
            chosen_g = _pick_model_by_load(MODEL_LOAD, feas)
            if chosen_g is None:
                for g in MODELS:
                    f2 = Flight(next_fid, [(sid, [rem[0]])], g, data)
                    if f2.is_feasible():
                        chosen_g = g
                        break
            if chosen_g is None:
                return flights, normal, next_fid
            f2 = Flight(next_fid, [(sid, list(rem))], chosen_g, data)
            flights.append(f2)
            MODEL_LOAD[chosen_g] += f2.flight_time()
            next_fid += 1
            rem = [b for b in rem if b not in f2.box_ids]
    # ---- 普通箱贪心插入 ----
    def rank(b):
        bx = data.boxes[b]
        t = min(bx['deadline_first'], bx['deadline_exp'])
        v = -1e6 if bx['first_batch'] else (0.0 if math.isinf(t) else -t)
        v += -1e5 if bx['type'] == '医疗物资' else 0.0
        return (v, rng.random())
    normal.sort(key=rank)
    next_fid = max([f.fid for f in flights], default=0) + 1
    for b in normal:
        sid = data.boxes[b]['area']
        best = None
        best_cost = math.inf
        cands = A._candidate_flights(data, flights, sid)
        for f in cands:
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
                dl = min(data.boxes[b]['deadline_first'], data.boxes[b]['deadline_exp'])
                if not math.isinf(dl):
                    est_delivery = cand.prep + cand.flight_time() + cand.handover_time()
                    if est_delivery > dl:
                        extra += 6000.0 * (1.0 + (est_delivery - dl) / 3600.0)
                if data.boxes[b]['first_batch'] and cand.nbox > 1:
                    extra += 2000.0
                # 机型负载偏置：同一候选下偏向负载低的机型
                mx = max(MODEL_LOAD.values()) or 1.0
                extra += 0.02 * MODEL_LOAD[g] / mx
                if extra < best_cost - 1e-9:
                    best_cost = extra
                    best = (f, cand, g)
        if best is not None:
            old, cand, g = best
            cand.fid = old.fid
            flights = [cand if x.fid == old.fid else x for x in flights]
            MODEL_LOAD[g] += cand.flight_time() - old.flight_time()
        else:
            g_ok = None
            feas = []
            for g in MODELS:
                f2 = Flight(next_fid, [(sid, [b])], g, data)
                if f2.is_feasible():
                    feas.append(g)
            g_ok = _pick_model_by_load(MODEL_LOAD, feas)
            if g_ok is None:
                return None
            flights.append(Flight(next_fid, [(sid, [b])], g_ok, data))
            MODEL_LOAD[g_ok] += Flight(next_fid, [(sid, [b])], g_ok, data).flight_time()
            next_fid += 1
    flights = tighten(data, flights, rng)
    return flights


def alns_fleet_optimize(data, flights0, budget=None, seed=7, w_removal=0.5,
                        max_no_improve=600, restart_after=4000):
    """同 alns_optimize，但修复算子换成机队均衡版。"""
    rng = fresh_rng(seed)
    if budget is None:
        budget = Budget(20000)
    cur_met_state = {}

    def make_destroyers():
        return [
            lambda fl: A.destroy_random_flights(data, fl, rng, 3),
            lambda fl: A.destroy_many(data, fl, rng),
            lambda fl: A.destroy_by_deadline(data, fl, rng, 10),
            lambda fl: A.destroy_random_boxes(data, fl, rng, 8),
            lambda fl: A.destroy_contiguous(data, fl, rng, 3),
            lambda fl: A.destroy_late_boxes(data, fl, rng, 8,
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
    sigma1, sigma2, sigma3 = 1.5, 0.7, 0.2
    while not budget.used_up():
        it += 1
        tot = sum(w_d)
        r = rng.random() * tot
        acc = 0.0
        di = 0
        for i, w in enumerate(w_d):
            acc += w
            if r <= acc:
                di = i
                break
        base = [f for f in cur_flights if f.box_ids]
        if not base:
            break
        destroyed, pool = DESTROYERS[di](base)
        if not pool:
            continue
        repaired = repair_fleet(data, destroyed, pool, rng)
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
        if it % 100 == 0:
            for i in range(len(w_d)):
                if cnt_d[i] > 0:
                    w_d[i] = w_d[i] * 0.9 + 0.1 * (score_d[i] / cnt_d[i]) + 0.05
            score_d = [0.0] * len(w_d)
            cnt_d = [0.0] * len(w_d)
        if no_improve >= max_no_improve and it % 2000 == 0:
            cur_flights = clone_flights(best_flights)
            cur_met = copy.deepcopy(best_met)
            cur_obj = best_obj
            cur_met_state['box_time'] = best_met.get('box_time')
            no_improve = 0
    return best_flights, best_met


if __name__ == '__main__':
    from common import make_initial, summarize, EVAL_BUDGET_DEFAULT
    import json
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '结果')
    with open(os.path.join(base, 'p1_results.json'), encoding='utf-8') as fh:
        p1 = json.load(fh)
    data = None
    from common import Data
    data = Data()
    flights0 = make_initial(data, p1['grouping'])
    fl, met = alns_fleet_optimize(data, flights0, budget=Budget(EVAL_BUDGET_DEFAULT), seed=7)
    print(summarize(met))