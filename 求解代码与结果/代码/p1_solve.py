# -*- coding: utf-8 -*-
"""
问题一：单点往返运输能力与货箱组批方案
1) 三种机型 x 15 服务区 最大安全载荷 q*（满足返航安全余量 E_round(q) <= (1-rho) E_use）
2) 每服务区货箱组批（ILP：最小架次数，再局部搜索能量/时间）
3) 权衡分析（架次数/总能耗/累计作业时间）
4) 返航安全余量 rho 的灵敏度
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from core import (Data, flight_profile, flight_time_with_handover, charge_time,
                  segment_geometry, segment_time, Lg)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

MODELS = ['A', 'B', 'C']


def roundtrip_energy(data, g, sid, q):
    o = data.centers[data.OID]
    a = data.areas[sid]
    z0, za = o['alt'], a['alt'] + 30.0
    nodes = [(o['lon'], o['lat'], z0), (a['lon'], a['lat'], za), (o['lon'], o['lat'], z0)]
    prof = flight_profile(nodes, [q, 0.0], g, data)
    return prof['energy'], prof['time']


def roundtrip_time(data, g, sid):
    o = data.centers[data.OID]
    a = data.areas[sid]
    z0, za = o['alt'], a['alt'] + 30.0
    nodes = [(o['lon'], o['lat'], z0), (a['lon'], a['lat'], za), (o['lon'], o['lat'], z0)]
    prof = flight_profile(nodes, [0.0, 0.0], g, data)
    return prof['time']


def max_safe_payload(data, g, sid, rho=None):
    """二分求最大安全载荷。返回 q*（受 Q_g 上限）。"""
    p = data.uav_types[g]
    rho = p['rho'] if rho is None else rho
    budget = (1.0 - rho) * p['E_use']
    # 空载往返能耗
    e0, _ = roundtrip_energy(data, g, sid, 0.0)
    if e0 > budget:
        return 0.0
    lo, hi = 0.0, p['Q']
    for _ in range(60):
        mid = (lo + hi) / 2.0
        e, _ = roundtrip_energy(data, g, sid, mid)
        if e <= budget:
            lo = mid
        else:
            hi = mid
    return lo


def ilp_min_flights_custom(data, sid, W):
    """ILP 组批：机型容量固定（W[g] 为可用容量），最小化架次数。"""
    bids = data.area_boxes[sid]
    n = len(bids)
    masses = [data.boxes[b]['mass'] for b in bids]
    vols = [data.boxes[b]['vol'] for b in bids]
    Vg = {g: data.uav_types[g]['V'] for g in MODELS}
    F = n
    nvar = n * F + 3 * F + F
    c = np.zeros(nvar)
    for f in range(F):
        c[n * F + 3 * F + f] = 1.0
    A = []
    lb = []
    ub = []
    for b in range(n):
        row = np.zeros(nvar)
        for f in range(F):
            row[b * F + f] = 1.0
        A.append(row); lb.append(1.0); ub.append(1.0)
    for f in range(F):
        row = np.zeros(nvar)
        for g_i in range(3):
            row[n * F + g_i * F + f] = 1.0
        A.append(row); lb.append(0.0); ub.append(1.0)
    for f in range(F):
        row = np.zeros(nvar)
        for g_i in range(3):
            row[n * F + g_i * F + f] = 1.0
        row[n * F + 3 * F + f] = -1.0
        A.append(row); lb.append(0.0); ub.append(0.0)
    for f in range(F):
        row = np.zeros(nvar)
        for b in range(n):
            row[b * F + f] = masses[b]
        for g_i, g in enumerate(MODELS):
            row[n * F + g_i * F + f] = -W[g]
        A.append(row); lb.append(-np.inf); ub.append(0.0)
    for f in range(F):
        row = np.zeros(nvar)
        for b in range(n):
            row[b * F + f] = vols[b]
        for g_i, g in enumerate(MODELS):
            row[n * F + g_i * F + f] = -Vg[g]
        A.append(row); lb.append(-np.inf); ub.append(0.0)
    for b in range(n):
        for f in range(F):
            row = np.zeros(nvar)
            row[b * F + f] = 1.0
            row[n * F + 3 * F + f] = -1.0
            A.append(row); lb.append(-np.inf); ub.append(0.0)
    integrality = np.ones(nvar)
    res = milp(c, integrality=integrality, bounds=Bounds(0, 1),
               constraints=LinearConstraint(np.array(A), np.array(lb), np.array(ub)),
               options={'time_limit': 30})
    if not res.success:
        return None, None, res
    x = np.rint(res.x).astype(int)
    flights = []
    models = []
    for f in range(F):
        boxes_f = [bids[b] for b in range(n) if x[b * F + f] == 1]
        if not boxes_f:
            continue
        g_sel = None
        for g_i, g in enumerate(MODELS):
            if x[n * F + g_i * F + f] == 1:
                g_sel = g
        flights.append(boxes_f)
        models.append(g_sel)
    return flights, models, res


def ilp_min_flights_bias(data, sid, qstar, prefer='B'):
    """B 型优先的策略：在最优架次数已知的前提下，先约束机型偏好。
    简化实现：用 'minflights' 求解，然后 refine 阶段机型成本按偏好折扣，
    这里直接返回 minflights 解（refine 会按能耗重选机型，B 能耗低自然被偏好）。"""
    return ilp_min_flights(data, sid, qstar)


def flight_metrics(data, g, sid, nboxes, q):
    o = data.centers[data.OID]
    a = data.areas[sid]
    z0, za = o['alt'], a['alt'] + 30.0
    nodes = [(o['lon'], o['lat'], z0), (a['lon'], a['lat'], za), (o['lon'], o['lat'], z0)]
    prof = flight_profile(nodes, [q, 0.0], g, data)
    T = flight_time_with_handover(prof, nboxes, g, data)
    return {'time': T, 'energy': prof['energy']}


def ilp_min_flights(data, sid, qstar, max_flights=None):
    """ILP：最小架次数组批。返回 (boxes_per_flight, model_per_flight)。"""
    bids = data.area_boxes[sid]
    n = len(bids)
    masses = [data.boxes[b]['mass'] for b in bids]
    vols = [data.boxes[b]['vol'] for b in bids]
    W = {g: min(qstar[g], data.uav_types[g]['Q']) for g in MODELS}
    Vg = {g: data.uav_types[g]['V'] for g in MODELS}
    F = n if max_flights is None else max_flights
    # 变量: x_{b,f} (n*F) + y_{g,f} (3*F) + z_f (F)
    nvar = n * F + 3 * F + F
    c = np.zeros(nvar)
    for f in range(F):
        c[n * F + 3 * F + f] = 1.0  # z_f
    # 约束
    A = []
    lb = []
    ub = []
    # 1) 每箱恰好一架次: sum_f x_{b,f} = 1
    for b in range(n):
        row = np.zeros(nvar)
        for f in range(F):
            row[b * F + f] = 1.0
        A.append(row); lb.append(1.0); ub.append(1.0)
    # 2) 每架次至多一种机型: sum_g y_{g,f} <= 1
    for f in range(F):
        row = np.zeros(nvar)
        for g_i in range(3):
            row[n * F + g_i * F + f] = 1.0
        A.append(row); lb.append(0.0); ub.append(1.0)
    # 3) z_f = sum_g y_{g,f}: sum_g y - z = 0
    for f in range(F):
        row = np.zeros(nvar)
        for g_i in range(3):
            row[n * F + g_i * F + f] = 1.0
        row[n * F + 3 * F + f] = -1.0
        A.append(row); lb.append(0.0); ub.append(0.0)
    # 4) 质量: sum_b m_b x_{b,f} - sum_g W_g y_{g,f} <= 0
    for f in range(F):
        row = np.zeros(nvar)
        for b in range(n):
            row[b * F + f] = masses[b]
        for g_i, g in enumerate(MODELS):
            row[n * F + g_i * F + f] = -W[g]
        A.append(row); lb.append(-np.inf); ub.append(0.0)
    # 5) 体积
    for f in range(F):
        row = np.zeros(nvar)
        for b in range(n):
            row[b * F + f] = vols[b]
        for g_i, g in enumerate(MODELS):
            row[n * F + g_i * F + f] = -Vg[g]
        A.append(row); lb.append(-np.inf); ub.append(0.0)
    # 6) 有箱才有架次: x_{b,f} <= z_f
    for b in range(n):
        for f in range(F):
            row = np.zeros(nvar)
            row[b * F + f] = 1.0
            row[n * F + 3 * F + f] = -1.0
            A.append(row); lb.append(-np.inf); ub.append(0.0)
    integrality = np.ones(nvar)
    res = milp(c, integrality=integrality, bounds=Bounds(0, 1),
               constraints=LinearConstraint(np.array(A), np.array(lb), np.array(ub)),
               options={'time_limit': 60})
    if not res.success:
        return None, None, res
    x = np.rint(res.x).astype(int)
    flights = []
    models = []
    for f in range(F):
        boxes_f = [bids[b] for b in range(n) if x[b * F + f] == 1]
        if not boxes_f:
            continue
        g_sel = None
        for g_i, g in enumerate(MODELS):
            if x[n * F + g_i * F + f] == 1:
                g_sel = g
        flights.append(boxes_f)
        models.append(g_sel)
    return flights, models, res


def refine_flights(data, sid, flights, models, qstar, n_restart=6):
    """后优化：在架次数不变下，最小化总能耗+时间。
    多次随机重启 + 局部搜索（机型再选 + 箱重分配）。"""
    o = data.centers[data.OID]
    a = data.areas[sid]
    z0, za = o['alt'], a['alt'] + 30.0
    nodes = [(o['lon'], o['lat'], z0), (a['lon'], a['lat'], za), (o['lon'], o['lat'], z0)]
    W = {g: min(qstar[g], data.uav_types[g]['Q']) for g in MODELS}
    rng = np.random.default_rng(1234 + hash(sid) % 1000)

    def best_models_for(flights_cur):
        out = []
        for boxes_f in flights_cur:
            q = sum(data.boxes[b]['mass'] for b in boxes_f)
            v = sum(data.boxes[b]['vol'] for b in boxes_f)
            cand = []
            for g in MODELS:
                if q <= W[g] + 1e-9 and v <= data.uav_types[g]['V'] + 1e-9:
                    prof = flight_profile(nodes, [q, 0.0], g, data)
                    T = flight_time_with_handover(prof, len(boxes_f), g, data)
                    cand.append((prof['energy'], T, g))
            if not cand:
                return None
            cand.sort()
            out.append(cand[0][2])
        return out

    def total_cost(flights_cur, models_cur):
        e = 0.0
        for boxes_f, g in zip(flights_cur, models_cur):
            q = sum(data.boxes[b]['mass'] for b in boxes_f)
            prof = flight_profile(nodes, [q, 0.0], g, data)
            e += prof['energy']
        return e

    best = (flights, models)
    best_e = total_cost(flights, models)
    for restart in range(n_restart):
        fl = [list(f) for f in flights]
        if restart > 0:
            # 随机扰动：把若干箱子随机换位
            allb = [b for f in fl for b in f]
            rng.shuffle(allb)
            fl = []
            k = len(allb) // len(flights)
            for i in range(len(flights)):
                fl.append(allb[i * k:(i + 1) * k] if i < len(flights) - 1 else allb[i * k:])
        mo = best_models_for(fl)
        if mo is None:
            continue
        improved = True
        it = 0
        while improved and it < 300:
            improved = False
            it += 1
            for k1 in range(len(fl)):
                for k2 in range(k1 + 1, len(fl)):
                    for b1 in list(fl[k1]):
                        if b1 not in fl[k1]:
                            continue
                        done_k1 = False
                        for b2 in list(fl[k2]):
                            if b2 not in fl[k2]:
                                continue
                            q1 = sum(data.boxes[b]['mass'] for b in fl[k1])
                            q2 = sum(data.boxes[b]['mass'] for b in fl[k2])
                            m1, m2 = data.boxes[b1]['mass'], data.boxes[b2]['mass']
                            v1, v2 = data.boxes[b1]['vol'], data.boxes[b2]['vol']
                            g1, g2 = mo[k1], mo[k2]
                            nq1, nq2 = q1 - m1 + m2, q2 - m2 + m1
                            nv1 = sum(data.boxes[b]['vol'] for b in fl[k1]) - v1 + v2
                            nv2 = sum(data.boxes[b]['vol'] for b in fl[k2]) - v2 + v1
                            if (nq1 <= W[g1] + 1e-9 and nq2 <= W[g2] + 1e-9
                                    and nv1 <= data.uav_types[g1]['V'] + 1e-9
                                    and nv2 <= data.uav_types[g2]['V'] + 1e-9):
                                e1 = flight_profile(nodes, [q1, 0.0], g1, data)['energy']
                                e2 = flight_profile(nodes, [q2, 0.0], g2, data)['energy']
                                ne1 = flight_profile(nodes, [nq1, 0.0], g1, data)['energy']
                                ne2 = flight_profile(nodes, [nq2, 0.0], g2, data)['energy']
                                if (ne1 + ne2) < (e1 + e2) - 1e-6:
                                    fl[k1].remove(b1); fl[k1].append(b2)
                                    fl[k2].remove(b2); fl[k2].append(b1)
                                    improved = True
                                    done_k1 = True
                                    break
                        if done_k1:
                            break
            for k1 in range(len(fl)):
                for k2 in range(len(fl)):
                    if k1 == k2:
                        continue
                    for b in list(fl[k1]):
                        if b not in fl[k1]:
                            continue
                        q1 = sum(data.boxes[b]['mass'] for b in fl[k1])
                        q2 = sum(data.boxes[b]['mass'] for b in fl[k2])
                        m = data.boxes[b]['mass']; v = data.boxes[b]['vol']
                        g2 = mo[k2]
                        nq2 = q2 + m
                        nv2 = sum(data.boxes[b]['vol'] for b in fl[k2]) + v
                        if nq2 <= W[g2] + 1e-9 and nv2 <= data.uav_types[g2]['V'] + 1e-9:
                            e1 = flight_profile(nodes, [q1, 0.0], mo[k1], data)['energy']
                            e2 = flight_profile(nodes, [q2, 0.0], g2, data)['energy']
                            ne1 = flight_profile(nodes, [q1 - m, 0.0], mo[k1], data)['energy']
                            ne2 = flight_profile(nodes, [nq2, 0.0], g2, data)['energy']
                            if (ne1 + ne2) < (e1 + e2) - 1e-6:
                                fl[k1].remove(b)
                                fl[k2].append(b)
                                improved = True
        mo = best_models_for(fl)
        if mo is None:
            continue
        e = total_cost(fl, mo)
        if e < best_e - 1e-6:
            best_e = e
            best = (fl, mo)
    return best[0], best[1]


def evaluate(data, sid, flights, models):
    tot_e = 0.0
    tot_t = 0.0
    nf = len(flights)
    per = []
    for boxes_f, g in zip(flights, models):
        q = sum(data.boxes[b]['mass'] for b in boxes_f)
        o = data.centers[data.OID]
        a = data.areas[sid]
        z0, za = o['alt'], a['alt'] + 30.0
        nodes = [(o['lon'], o['lat'], z0), (a['lon'], a['lat'], za), (o['lon'], o['lat'], z0)]
        prof = flight_profile(nodes, [q, 0.0], g, data)
        T = flight_time_with_handover(prof, len(boxes_f), g, data)
        tot_e += prof['energy']
        tot_t += T
        per.append({'boxes': boxes_f, 'model': g, 'q': q, 'energy': prof['energy'], 'time': T})
    return {'flights': nf, 'energy': tot_e, 'time': tot_t, 'detail': per}


def main():
    data = Data()
    RHO0 = 0.2
    result = {'qstar': {}, 'grouping': {}, 'sensitivity': {}, 'summary': {}}
    # ---- 1) 最大安全载荷 ----
    for g in MODELS:
        result['qstar'][g] = {}
        for sid in sorted(data.areas):
            q = max_safe_payload(data, g, sid)
            result['qstar'][g][sid] = round(q, 3)
    print('=== 最大安全载荷 q*(kg) ===')
    print('area  ' + '  '.join('%-6s' % g for g in MODELS))
    for sid in sorted(data.areas):
        print('%-4s  ' % sid + '  '.join('%-6.1f' % result['qstar'][g][sid] for g in MODELS))

    # ---- 2) 组批 ----
    summary_rows = []
    tot_flights = 0
    tot_energy = 0.0
    tot_time = 0.0
    plan = {}
    for sid in sorted(data.areas):
        qstar = {g: result['qstar'][g][sid] for g in MODELS}
        # 若某机型 q* < 最轻箱 (3kg) 则不可用
        for g in MODELS:
            if qstar[g] < 3.0:
                qstar[g] = 0.0
        flights, models, res = ilp_min_flights(data, sid, qstar)
        if flights is None or models is None:
            print('SID', sid, 'ILP FAIL', res.message)
            continue
        rf = refine_flights(data, sid, flights, models, qstar)
        if rf is None:
            flights2, models2 = flights, models
        else:
            flights2, models2 = rf
        ev = evaluate(data, sid, flights2, models2)
        plan[sid] = ev
        tot_flights += ev['flights']
        tot_energy += ev['energy']
        tot_time += ev['time']
        summary_rows.append({
            'area': sid, 'nbox': len(data.area_boxes[sid]),
            'mass': data.area_demand[sid]['mass'],
            'flights': ev['flights'], 'energy': round(ev['energy'], 3),
            'time': round(ev['time'], 1),
            'models': Counter([d['model'] for d in ev['detail']]),
        })
    print('\n=== 组批汇总 ===')
    print('%-5s %4s %6s %4s %8s %9s %s' % ('area', 'nbox', 'mass', 'flt', 'energy', 'time', 'models'))
    for r in summary_rows:
        print('%-5s %4d %6.0f %4d %8.3f %9.0f %s' %
              (r['area'], r['nbox'], r['mass'], r['flights'], r['energy'], r['time'],
               {k: v for k, v in r['models'].items()}))
    print('TOTAL flights=%d energy=%.3f kWh time=%.0f s' % (tot_flights, tot_energy, tot_time))
    result['summary'] = {
        'flights': tot_flights, 'energy': round(tot_energy, 3), 'time': round(tot_time, 1),
        'per_area': summary_rows,
    }
    result['grouping'] = {
        sid: {'detail': ev['detail']} for sid, ev in plan.items()
    }

    # ---- 3) 多策略权衡：最小架次 vs 最小能耗(B型优先) vs 单机型 ----
    def solve_strategy(mode):
        """mode: 'minflights' | 'energyB' | 'onlyC' | 'onlyB'"""
        tf = te = tt = 0
        per_area = {}
        for sid in sorted(data.areas):
            qstar = {g: result['qstar'][g][sid] for g in MODELS}
            for g in MODELS:
                if qstar[g] < 3.0:
                    qstar[g] = 0.0
            mass = data.area_demand[sid]['mass']
            vol = data.area_demand[sid]['vol']
            if mode == 'minflights':
                flights, models, res = ilp_min_flights(data, sid, qstar)
            elif mode == 'energyB':
                # B 优先：以 B 容量组批（容量不足时用 C 补足）
                flights, models, res = ilp_min_flights_bias(data, sid, qstar, prefer='B')
            elif mode == 'onlyC':
                W = {'A': 0, 'B': 0, 'C': min(qstar['C'], data.uav_types['C']['Q'])}
                flights, models, res = ilp_min_flights_custom(data, sid, W)
            elif mode == 'onlyB':
                W = {'A': 0, 'B': min(qstar['B'], data.uav_types['B']['Q']), 'C': 0}
                flights, models, res = ilp_min_flights_custom(data, sid, W)
            if flights is None:
                return None
            rf = refine_flights(data, sid, flights, models, qstar)
            if rf is None:
                fl2, mo2 = flights, models
            else:
                fl2, mo2 = rf
            ev = evaluate(data, sid, fl2, mo2)
            tf += ev['flights']; te += ev['energy']; tt += ev['time']
            per_area[sid] = {'flights': ev['flights'], 'energy': ev['energy'], 'time': ev['time']}
        return {'flights': tf, 'energy': round(te, 3), 'time': round(tt, 1), 'per_area': per_area}

    strategies = {}
    for mode in ['minflights', 'energyB', 'onlyC', 'onlyB']:
        s = solve_strategy(mode)
        if s:
            strategies[mode] = s
            print('\nstrategy %-10s flights=%d energy=%.3f time=%.0f'
                  % (mode, s['flights'], s['energy'], s['time']))
    result['strategies'] = strategies

    # ---- 4) 灵敏度：rho 变化 ----
    sens = {}
    for rho in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]:
        tf = te = tt = 0
        qs = {}
        for g in MODELS:
            qs[g] = {}
            for sid in sorted(data.areas):
                qs[g][sid] = max_safe_payload(data, g, sid, rho)
        for sid in sorted(data.areas):
            qs_s = {g: max(0.0, qs[g][sid]) for g in MODELS}
            for g in MODELS:
                if qs_s[g] < 3.0:
                    qs_s[g] = 0.0
            fl, mo, _ = ilp_min_flights(data, sid, qs_s)
            if fl is None:
                continue
            rf = refine_flights(data, sid, fl, mo, qs_s)
            if rf is None:
                fl2, mo2 = fl, mo
            else:
                fl2, mo2 = rf
            ev = evaluate(data, sid, fl2, mo2)
            tf += ev['flights']; te += ev['energy']; tt += ev['time']
        sens[rho] = {'flights': tf, 'energy': round(te, 3), 'time': round(tt, 1)}
        print('rho=%.2f  flights=%d energy=%.3f time=%.0f' % (rho, tf, te, tt))
    result['sensitivity'] = sens

    with open(os.path.join(OUT, 'p1_results.json'), 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print('\nsaved', os.path.join(OUT, 'p1_results.json'))


from collections import Counter

if __name__ == '__main__':
    main()