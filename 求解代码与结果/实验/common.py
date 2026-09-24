# -*- coding: utf-8 -*-
"""
D题 进化实验 共享框架
- 复用 p2_solve 的 Flight / dispatch / evaluate / objective
- 统一"目标函数评估次数"预算，保证各元启发式在同一算力口径下对比
- 提供共用的算子库（repair / 算子计数），供 GA、ALNS、Tabu、GRASP 复用
"""
import sys, os, json, math, random, time, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
import numpy as np

from core import Data
from p2_solve import (
    Flight, MODELS, dispatch, evaluate, objective,
    clone_flights, normalize_flight, feasible_models, try_merge,
    initial_flights, flight_critical_time,
)

EVAL_BUDGET_DEFAULT = 20000   # 每求解器一次运行的目标评估次数预算


class TimeBudget:
    """墙钟时间预算：各元启发式在同一算力口径（秒）下对比。
    used_up() 按运行时长判定；tick() 仅统计评估次数供记录。"""
    def __init__(self, seconds, rng=None):
        self.limit = seconds
        self.deadline = time.time() + seconds
        self.count = 0

    def spent(self):
        return self.count

    def used_up(self):
        return time.time() >= self.deadline

    def tick(self):
        self.count += 1


class Budget:
    """目标评估计数器（dispatch+evaluate 计为一次）。"""
    def __init__(self, limit):
        self.limit = limit
        self.count = 0

    def spent(self):
        return self.count

    def used_up(self):
        return self.count >= self.limit

    def tick(self):
        self.count += 1


def fresh_rng(seed):
    return random.Random(seed)


def data_from_results(p1_json_path):
    """加载数据并返回 p1 grouping（键为分箱表现结构）。"""
    data = Data()
    with open(p1_json_path, encoding='utf-8') as fh:
        p1 = json.load(fh)
    return data, p1['grouping']


def make_initial(data, p1_grouping):
    """初始架次集（源自问题一组批 + 紧急箱拆出）。"""
    flights0 = initial_flights(data, p1_grouping)
    return flights0


# ---------------------------------------------------------------------------
# 评估包装：一次 dispatch+evaluate
# ---------------------------------------------------------------------------
def safe_eval(data, flights, budget):
    """dispatch+evaluate；返回 (metrics, schedule)。失败返回 None,None。"""
    schedule, _ = dispatch(data, flights)
    if schedule is None:
        return None, None
    budget.tick()
    met = evaluate(data, flights, schedule)
    return met, schedule


def total_obj(met, hard_penalty=1e6):
    from p2_solve import objective
    return objective(met) + (0 if met['hard_ok'] else hard_penalty)


def summarize(met):
    return {k: (round(v, 2) if isinstance(v, float) else v)
            for k, v in met.items() if k != 'box_time'}


# ---- 算子库（面向 Flight 对象列表）----
def rebuild(flights):
    """清洗：剔除空区、按紧急度归并同区、重排。返回新的 Flight 列表。"""
    flights = [f for f in flights if f.box_ids]
    for f in flights:
        normalize_flight(f, f.data)
    return [f for f in flights if f.box_ids]


def greedy_repair(data, flights, budget, rng):
    """极简修复：对每个多区架次尝试同区合并、以及对超载拆分。
    主要让破坏后重组的解回到可行 + 紧凑。返回 (flights, feasible_all)? 由调用方判定。"""
    flights = rebuild(flights)
    # 1) 贪心合并：优先同簇路线能合并的架次（复用 p2 的 try_merge）
    improved = True
    guard = 0
    while improved and guard < 50:
        improved = False
        guard += 1
        n = len(flights)
        if n < 2:
            break
        best = None
        best_save = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                m = try_merge(data, flights[i], flights[j])
                if m is None:
                    continue
                save = (flights[i].duration() + flights[j].duration()) - m.duration()
                if save > best_save + 1e-3:
                    best_save = save
                    best = (i, j, m)
        if best:
            i, j, m = best
            m.fid = flights[i].fid
            flights[i] = m
            flights.pop(j)
            improved = True
    flights = rebuild(flights)
    return flights


def all_feasible(flights):
    return all(f.box_ids and f.is_feasible() for f in flights) if flights else False


def tighten(data, flights, rng=None):
    """轻量收紧：一轮合并扫描 + 逐架次机型重选（不循环到收敛，控制开销）。"""
    flights = rebuild(flights)
    n = len(flights)
    for i in range(n):
        for j in range(i + 1, n):
            m = try_merge(data, flights[i], flights[j])
            if m is not None:
                save = (flights[i].duration() + flights[j].duration()) - m.duration()
                if save > 1e-3:
                    m.fid = flights[i].fid
                    flights[i] = m
                    flights.pop(j)
                    n -= 1
                    break
    # 机型重选（当前路线下能耗最优的可行机型）
    out = []
    for f in flights:
        best = None
        best_e = math.inf
        for g in MODELS:
            cand = Flight(f.fid, [(s, list(bs)) for s, bs in f.route], g, data)
            if cand.is_feasible() and cand.energy() < best_e:
                best_e = cand.energy()
                best = cand
        out.append(best if best is not None else f)
    return rebuild(out)


def area_distance_table(data):
    """服务区对直线距离 (m) 查表，供插入候选过滤。"""
    keys = data.node_keys
    tbl = {}
    for i, a in enumerate(keys):
        for j, b in enumerate(keys):
            if a == b:
                tbl[(a, b)] = 0.0
            elif (a, b) in data.leg_table:
                tbl[(a, b)] = data.leg_table[(a, b)]['d']
            else:
                tbl[(a, b)] = data.leg_table[(b, a)]['d']
    return tbl


def save_solution(result_dir, name, flights, met, extra=None):
    """把一组架次写入 JSON（增量快照）。"""
    os.makedirs(result_dir, exist_ok=True)
    out = {'name': name,
           'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                       for k, v in met.items() if k != 'box_time'},
           'flights': [{'fid': f.fid, 'model': f.model, 'route': [(s, b) for s, b in f.route],
                         'energy': round(f.energy(), 4), 'mass': round(f.total_mass, 2),
                         'nbox': f.nbox} for f in flights]}
    if extra:
        out.update(extra)
    p = os.path.join(result_dir, '%s.json' % name)
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return p