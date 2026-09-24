# -*- coding: utf-8 -*-
"""
问题二：异构无人机多点多架次运输调度
- 架次可访问多个服务区（O01 -> S.. -> S.. -> O01），载荷沿途递减
- 约束：货箱不可拆分、载质量/体积、返航安全余量、无人机与共享电池数量、
        充电周转（两阶段等效充电）、物资时限（医疗=期望、首批=截止，其余软约束）
- 目标：及时性(加权迟到)、全部任务完成时间(makespan)、总能耗、架次数
- 方法：路径池构造 + 模拟退火（合并/拆分/换序/换机型/移箱）+ 贪心调度
"""
import sys, os, json, math, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import (Data, flight_profile, flight_time_with_handover, charge_time,
                  segment_geometry, segment_time, Lg, route_profile_fast)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

MODELS = ['A', 'B', 'C']
W_TARDY = 1.0      # 迟到权重
W_MAKESPAN = 0.05  # 时间权重（s 量级大）
W_ENERGY = 0.8     # 能耗权重
W_FLIGHTS = 30.0   # 架次权重


class Flight:
    """一个运输架次：route = [(sid, [box_ids]), ...] 有序访问。"""

    def __init__(self, fid, route, model, data):
        self.fid = fid
        self.route = route           # [(sid, [bid,...]), ...]
        self.model = model
        self.data = data
        self.box_ids = [b for _, bs in route for b in bs]
        self.nbox = len(self.box_ids)
        self.total_mass = sum(data.boxes[b]['mass'] for b in self.box_ids)
        self.total_vol = sum(data.boxes[b]['vol'] for b in self.box_ids)
        self.prep = data.uav_types[model]['t_prep'] + self.nbox * data.uav_types[model]['t_load']
        self._profile = None

    def area_nodes(self):
        d = self.data
        o = d.centers[d.OID]
        nodes = [(o['lon'], o['lat'], o['alt'])]
        for sid, _ in self.route:
            a = d.areas[sid]
            nodes.append((a['lon'], a['lat'], a['alt'] + 30.0))
        nodes.append((o['lon'], o['lat'], o['alt']))
        return nodes

    def keys(self):
        return ['O'] + [sid for sid, _ in self.route] + ['O']

    def profile(self):
        if self._profile is None:
            loads = []
            rem = self.total_mass
            for k in range(len(self.route) + 1):
                loads.append(rem)
                if k < len(self.route):
                    sid, bs = self.route[k]
                    rem -= sum(self.data.boxes[b]['mass'] for b in bs)
            self._profile = route_profile_fast(self.data, self.keys(), loads, self.model)
        return self._profile

    def energy(self):
        return self.profile()['energy']

    def flight_time(self):
        return self.profile()['time']

    def handover_time(self):
        p = self.data.uav_types[self.model]
        return sum(p['t_hand_base'] + len(bs) * p['t_hand_box'] for _, bs in self.route)

    def duration(self):
        return self.prep + self.flight_time() + self.handover_time()

    def is_feasible(self):
        p = self.data.uav_types[self.model]
        if self.total_mass > p['Q'] + 1e-9 or self.total_vol > p['V'] + 1e-9:
            return False
        if self.energy() > (1 - p['rho']) * p['E_use'] + 1e-9:
            return False
        return True

    def delivery_times(self, start):
        """返回 [(sid, box_id, 交付完成时刻)]，交付=到达+交接完成。"""
        d = self.data
        p = d.uav_types[self.model]
        t = start + self.prep          # 起飞时刻
        prof = self.profile()
        res = []
        for k in range(len(self.route)):
            t += prof['legs'][k]['t']
            sid, bs = self.route[k]
            t += p['t_hand_base'] + len(bs) * p['t_hand_box']
            for b in bs:
                res.append((sid, b, t))
        return res


def route_time_energy(data, route, model):
    """临时评估一条 route（不建对象）。"""
    f = Flight(0, route, model, data)
    return f


def feasible_models(data, route):
    """返回所有可行的机型列表。"""
    out = []
    for g in MODELS:
        f = Flight(0, route, g, data)
        if f.is_feasible():
            out.append(g)
    return out


# ----------------------------------------------------------------------------
# 初始解：箱级紧急度感知 + 机型均衡
# ----------------------------------------------------------------------------
def box_is_urgent(data, bid):
    bx = data.boxes[bid]
    return bx['first_batch'] or bx['type'] == '医疗物资'


def initial_flights(data, p1_grouping):
    """从 P1 组批构造初始架次，但把每服务区的紧急箱（首批/医疗）拆出优先架次。
    紧急架次：单区 ≤25kg 用 A 型、≤30kg 用 B 型，重区用 C 型（路由内紧急区在前）。
    非紧急架次沿用 P1 组批（剔除紧急箱后重组）。"""
    urgent_flights = []
    bulk_flights = []
    fid = 1
    o = data.centers[data.OID]
    z0 = o['alt']
    # ---- 紧急箱 ----
    for sid in sorted(data.areas):
        urg = [b for b in data.area_boxes[sid] if box_is_urgent(data, b)]
        if not urg:
            continue
        m = sum(data.boxes[b]['mass'] for b in urg)
        v = sum(data.boxes[b]['vol'] for b in urg)
        # 机型选择：优先 A(≤25) / B(≤30) / C
        g = None
        for gx in ['A', 'B', 'C']:
            p = data.uav_types[gx]
            if m <= p['Q'] + 1e-9 and v <= p['V'] + 1e-9:
                # 能量校验
                f = Flight(fid, [(sid, urg)], gx, data)
                if f.is_feasible():
                    g = gx
                    break
        if g is None:
            # 拆分紧急箱
            urg.sort(key=lambda b: -data.boxes[b]['mass'])
            part1 = []
            for b in urg:
                if (sum(data.boxes[x]['mass'] for x in part1) + data.boxes[b]['mass'] <= 25):
                    part1.append(b)
            f = Flight(fid, [(sid, part1)], 'A', data)
            if f.is_feasible():
                urgent_flights.append(f)
                fid += 1
                rest = [b for b in urg if b not in part1]
                f2 = Flight(fid, [(sid, rest)], 'C', data)
                urgent_flights.append(f2)
                fid += 1
            continue
        f = Flight(fid, [(sid, urg)], g, data)
        urgent_flights.append(f)
        fid += 1
    # ---- 非紧急箱：沿用 P1 组批，但剔除紧急箱后重算 ----
    for sid, ev in p1_grouping.items():
        urg = set(b for b in data.area_boxes[sid] if box_is_urgent(data, b))
        for det in ev['detail']:
            boxes = [b for b in det['boxes'] if b not in urg]
            if not boxes:
                continue
            route = [(sid, boxes)]
            # 机型重选（去掉紧急箱后可能更轻）
            best = None
            best_e = math.inf
            for g in MODELS:
                f = Flight(fid, route, g, data)
                if f.is_feasible() and f.energy() < best_e:
                    best_e = f.energy()
                    best = f
            if best is None:
                # 拆分超载
                boxes.sort(key=lambda b: -data.boxes[b]['mass'])
                cur = []
                for b in boxes:
                    cur.append(b)
                    f = Flight(fid, [(sid, list(cur))], 'C', data)
                    if not f.is_feasible():
                        cur.pop()
                        f2 = Flight(fid, [(sid, list(cur))], 'C', data)
                        bulk_flights.append(f2)
                        fid += 1
                        cur = [b]
                if cur:
                    f3 = Flight(fid, [(sid, list(cur))], 'C', data)
                    if f3.is_feasible():
                        bulk_flights.append(f3)
                        fid += 1
                continue
            bulk_flights.append(best)
            fid += 1
    # 紧急架次保持独立（保证能尽早起飞）；非紧急架次为 C/B 大载量架次。
    return urgent_flights + bulk_flights


def try_merge(data, f1, f2):
    """尝试把 f2 的箱子并入 f1 的路线。合并后按紧急度重排区序，返回可行新 Flight 或 None。"""
    route_map = {}
    for sid, bs in list(f1.route) + list(f2.route):
        route_map.setdefault(sid, [])
        route_map[sid] = route_map[sid] + bs
    route = [(sid, bs) for sid, bs in route_map.items()]
    route.sort(key=lambda x: flight_critical_time(data, Flight(0, [x], 'A', data)))
    cand = None
    best_e = math.inf
    for g in MODELS:
        f = Flight(0, route, g, data)
        if f.is_feasible():
            e = f.energy()
            if e < best_e:
                best_e = e
                cand = f
    return cand


def greedy_merge(data, flights):
    """贪心合并：重复寻找能降低总时长的可合并对。"""
    flights = copy.deepcopy(flights)
    improved = True
    while improved:
        improved = False
        best = None
        best_save = 0.0
        for i in range(len(flights)):
            for j in range(i + 1, len(flights)):
                for fi, fj in ((flights[i], flights[j]), (flights[j], flights[i])):
                    m = try_merge(data, fi, fj)
                    if m is None:
                        continue
                    save = (fi.duration() + fj.duration()) - m.duration()
                    if save > best_save + 1e-3:
                        best_save = save
                        best = (i, j, fi, fj, m)
        if best is not None:
            i, j, fi, fj, m = best
            m.fid = fi.fid
            flights[i] = m
            flights.pop(j)
            improved = True
    return flights


# ----------------------------------------------------------------------------
# 调度器：贪心 EDF + 资源（无人机/电池/充电）
# ----------------------------------------------------------------------------
def make_resources(data, limit=None):
    """limit: {'A': (n_uavs, n_bats), 'B': (...), 'C': (...)}，None=全库存。"""
    uavs = {}
    n_by_g = {'A': 0, 'B': 0, 'C': 0}
    for uid, g in data.uavs:
        if limit is not None:
            nu, _ = limit.get(g, (0, 0))
            if n_by_g[g] >= nu:
                continue
        n_by_g[g] += 1
        uavs[uid] = {'model': g, 'ready': 0.0}
    bats = {}
    for g, bi in data.batteries.items():
        nb = bi['n'] if limit is None else limit.get(g, (0, 0))[1]
        for k in range(min(nb, bi['n'])):
            bats['%s-%02d' % (g, k + 1)] = {'model': g, 'ready': 0.0}
    return uavs, bats


def flight_critical_time(data, f):
    """架次的紧急度：取箱中最小的硬时限（首批截止/医疗期望），无硬时限取期望。"""
    ct = math.inf
    for b in f.box_ids:
        bx = data.boxes[b]
        t = min(bx['deadline_first'], bx['deadline_exp'])
        if not math.isinf(t):
            ct = min(ct, t)
    if math.isinf(ct):
        ct = max(bx['deadline_exp'] for b in f.box_ids)
    return ct


def dispatch(data, flights, releases=None, limit=None):
    """
    贪心调度（EDF：按硬时限/期望时限升序）。flights 列表顺序被忽略，内部按紧急度排序。
    releases: {fid: earliest_start}，架次不得早于该时刻起飞（可写P3协同平移）。
    limit: 资源上限（见 make_resources），用于问题四分组建模。
    schedule[fid] = {'uav','battery','start','return','energy','deliveries':[...]}
    """
    order = sorted(enumerate(flights), key=lambda x: (flight_critical_time(data, x[1]),
                                                      -sum(data.boxes[b]['priority'] for b in x[1].box_ids),
                                                      x[1].fid))
    uavs, bats = make_resources(data, limit)
    schedule = {}
    for _, f in order:
        model = f.model
        cand_uavs = [(u['ready'], u) for u in uavs.values() if u['model'] == model]
        if not cand_uavs:
            return None, None
        cand_uavs.sort()
        uav = cand_uavs[0][1]
        cand_bats = [b for b in bats.values() if b['model'] == model]
        rel = releases.get(f.fid, 0.0) if releases else 0.0
        start = max(rel, uav['ready'])
        # 找最早能赶上起飞时刻(start+prep)的电池
        avail = [b for b in cand_bats if b['ready'] <= start + f.prep]
        if not avail:
            earliest = min(b['ready'] for b in cand_bats)
            start = max(start, earliest - f.prep)
            avail = [b for b in cand_bats if b['ready'] <= start + f.prep]
            if not avail:
                return None, None
        while uav['ready'] > start + 1e-9:
            start = uav['ready']
            avail = [b for b in cand_bats if b['ready'] <= start + f.prep]
            if not avail:
                earliest = min(b['ready'] for b in cand_bats)
                start = max(start, earliest - f.prep)
                avail = [b for b in cand_bats if b['ready'] <= start + f.prep]
                if not avail:
                    return None, None
        bat = avail[0]
        uav['ready'] = start + f.duration()
        bat_end = start + f.prep + f.flight_time()
        soc_end = 1.0 - f.energy() / data.uav_types[model]['E_use']
        bat['ready'] = bat_end + charge_time(soc_end, data.batteries[model]['T_full'])
        deliveries = f.delivery_times(start)
        schedule[f.fid] = {'uav': [u for u, d in uavs.items() if d is uav][0],
                           'battery': [b for b, d in bats.items() if d is bat][0],
                           'start': start, 'return': start + f.duration(),
                           'energy': f.energy(), 'deliveries': deliveries,
                           'route': [(s, b) for s, b in f.route]}
    return schedule, uavs


def evaluate(data, flights, schedule):
    """指标：加权迟到（硬约束检验）、makespan、能耗、架次数。"""
    hard_ok = True
    tardy_w = 0.0
    tardy_max = 0.0
    box_time = {}
    for fid, sch in schedule.items():
        for sid, bid, t in sch['deliveries']:
            box_time[bid] = t
            bx = data.boxes[bid]
            if bx['first_batch'] and t > bx['deadline_first'] + 1e-6:
                hard_ok = False
            if bx['type'] == '医疗物资' and t > bx['deadline_exp'] + 1e-6:
                hard_ok = False
            late = max(0.0, t - bx['deadline_exp'])
            tardy_w += late * bx['priority'] / 24.0
            tardy_max = max(tardy_max, late)
    expect = set()
    for f in flights:
        expect.update(f.box_ids)
    if len(box_time) != len(expect):
        hard_ok = False
    makespan = max(sch['return'] for sch in schedule.values()) if schedule else 0.0
    energy = sum(f.energy() for f in flights)
    nfl = len(flights)
    return {'hard_ok': hard_ok, 'tardy_w': tardy_w, 'tardy_max': tardy_max,
            'makespan': makespan, 'energy': energy, 'flights': nfl,
            'box_time': box_time}


def objective(metrics):
    return (W_TARDY * metrics['tardy_w'] + W_MAKESPAN * metrics['makespan']
            + W_ENERGY * metrics['energy'] + W_FLIGHTS * metrics['flights'])


def normalize_flight(f, data):
    """重算缓存并按紧急度排序区序（剔除空区）。"""
    f.route = [(s, bs) for s, bs in f.route if bs]
    f.route.sort(key=lambda x: flight_critical_time(data, f))
    f.box_ids = [b for _, bs in f.route for b in bs]
    f.nbox = len(f.box_ids)
    f.total_mass = sum(data.boxes[b]['mass'] for b in f.box_ids)
    f.total_vol = sum(data.boxes[b]['vol'] for b in f.box_ids)
    f.prep = data.uav_types[f.model]['t_prep'] + f.nbox * data.uav_types[f.model]['t_load']
    f._profile = None


def clone_flights(fl):
    """轻量克隆架次列表（共享 data 引用，不深拷贝 DEM）。"""
    return [Flight(f.fid, [(s, list(b)) for s, b in f.route], f.model, f.data) for f in fl]


# ----------------------------------------------------------------------------
# 模拟退火
# ----------------------------------------------------------------------------
def sa_optimize(data, flights0, iters=6000, seed=7):
    rng = random.Random(seed)
    flights = clone_flights(flights0)
    schedule, _ = dispatch(data, flights)
    if schedule is None:
        return None, None
    best_flights = clone_flights(flights)
    best_metrics = evaluate(data, flights, schedule)
    best_obj = objective(best_metrics) + (0 if best_metrics['hard_ok'] else 1e6)
    cur = (flights, schedule, best_metrics, best_obj)
    T0 = best_obj * 0.12
    accept = 0
    for it in range(iters):
        T = T0 * (1.0 - it / iters) ** 1.2 + 1e-6
        fl = clone_flights(cur[0])
        # ---- 随机扰动 ----
        op = rng.random()
        n = len(fl)
        if op < 0.25 and n > 1:
            # 合并两架次
            i, j = rng.sample(range(n), 2)
            m = try_merge(data, fl[i], fl[j])
            if m is not None:
                m.fid = fl[i].fid
                fl[i] = m
                fl.pop(j)
        elif op < 0.42:
            # 拆分：随机一架次随机取一个区，拆出部分箱子为新架次
            i = rng.randrange(n)
            r = fl[i].route
            ri = rng.randrange(len(r))
            sid, bs = r[ri]
            if len(bs) >= 2:
                k = rng.randrange(1, len(bs))
                part, rest = bs[:k], bs[k:]
                fl[i].route[ri] = (sid, rest)
                normalize_flight(fl[i], data)
                nf = Flight(max(f.fid for f in fl) + 1, [(sid, part)],
                            fl[i].model if feasible_models(data, [(sid, part)]) else 'A', data)
                if not nf.is_feasible():
                    continue
                fl.append(nf)
        elif op < 0.58:
            # 区顺序换位（多区架次内）
            i = rng.randrange(n)
            if len(fl[i].route) > 1:
                a, b = rng.sample(range(len(fl[i].route)), 2)
                fl[i].route[a], fl[i].route[b] = fl[i].route[b], fl[i].route[a]
                normalize_flight(fl[i], data)
        elif op < 0.75 and n > 1:
            # 跨架次移箱（同服务区）
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
            # 换机型
            i = rng.randrange(n)
            cand = [g for g in MODELS if g != fl[i].model]
            rng.shuffle(cand)
            for g in cand:
                f2 = Flight(fl[i].fid, [(s, list(b)) for s, b in fl[i].route], g, data)
                if f2.is_feasible():
                    fl[i] = f2
                    break
        fl = [f for f in fl if f.box_ids]
        if not fl:
            continue
        if not all(f.is_feasible() for f in fl):
            continue
        schedule, _ = dispatch(data, fl)
        if schedule is None:
            continue
        met = evaluate(data, fl, schedule)
        obj = objective(met) + (0 if met['hard_ok'] else 1e6)
        if obj < cur[3] or rng.random() < math.exp((cur[3] - obj) / max(T, 1e-9)):
            cur = (fl, schedule, met, obj)
            accept += 1
            if obj < best_obj - 1e-9:
                best_flights = clone_flights(fl)
                best_metrics = copy.deepcopy(met)
                best_obj = obj
    print('SA accept rate: %.3f' % (accept / iters))
    return best_flights, best_metrics


def main():
    data = Data()
    with open(os.path.join(OUT, 'p1_results.json'), encoding='utf-8') as fh:
        p1 = json.load(fh)
    flights0 = initial_flights(data, p1['grouping'])
    print('initial flights:', len(flights0))
    for f in flights0:
        assert f.is_feasible(), f.fid
    schedule0, _ = dispatch(data, flights0)
    m0 = evaluate(data, flights0, schedule0)
    print('seed metrics:', {k: (round(v, 2) if isinstance(v, float) else v)
                            for k, v in m0.items() if k != 'box_time'})
    print('seed hard_ok:', m0['hard_ok'])
    flights, met = sa_optimize(data, flights0, iters=5000, seed=7)
    if flights is None:
        print('SA FAILED')
        return
    schedule, _ = dispatch(data, flights)
    print('\n=== P2 最终结果 ===')
    print({k: (round(v, 2) if isinstance(v, float) else v)
           for k, v in met.items() if k != 'box_time'})
    result = {
        'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                    for k, v in met.items() if k != 'box_time'},
        'box_time': met['box_time'],
        'flights': [],
        'deliveries': [],
    }
    for f in flights:
        sch = schedule[f.fid]
        result['flights'].append({
            'fid': f.fid, 'uav': sch['uav'], 'model': f.model, 'battery': sch['battery'],
            'start': round(sch['start'], 1), 'return': round(sch['return'], 1),
            'route': [(s, b) for s, b in f.route], 'energy': round(f.energy(), 4),
            'nbox': f.nbox, 'mass': round(f.total_mass, 2),
        })
        for sid, bid, t in sch['deliveries']:
            result['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid,
                                         't': round(t, 1)})
    with open(os.path.join(OUT, 'p2_results.json'), 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print('saved', os.path.join(OUT, 'p2_results.json'))


if __name__ == '__main__':
    main()