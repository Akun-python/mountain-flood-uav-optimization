# -*- coding: utf-8 -*-
"""问题四：任务分区（K=2 / K=3）与分组资源配置
- 分组以问题三通信保障结构为基础（W9/E4/N1）
- 每组独立调度：将 P2 平衡解的架次按组分拆，EDF 重调度
- 资源需求 = 实际使用（无人机/电池/中继/能源组件）+ 冗余备份
- 校验各组可独立完成保障且总量不超过库存
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import (Data, relay_mission_time, relay_mission_energy, direct_ok,
                  relay_link_ok, charge_time)
from p2_solve import Flight, dispatch, evaluate
from p3_gaps import flight_trajectory
from p3_co2 import P_W, P_E, P_N, AREA_POS, POS_OF

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = Data()
E_BUDGET = (1 - data.relay_type['rho']) * data.relay_type['E_use']
T_FULL = data.relay_energy['T_full']

GROUPS_3 = {
    'G1': ['S001', 'S002', 'S003', 'S005', 'S006', 'S007', 'S008', 'S009', 'S011', 'S015'],
    'G2': ['S010', 'S012', 'S013', 'S014'],
    'G3': ['S004'],
}
GROUPS_2 = {
    'G1': ['S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007', 'S008', 'S009', 'S011', 'S015'],
    'G2': ['S010', 'S012', 'S013', 'S014'],
}


def load_p2_flights():
    # 使用问题三最终协同方案（p3_final.json）的架次/时刻
    p = os.path.join(OUT, 'p3_final.json')
    if os.path.exists(p):
        r = json.load(open(p, encoding='utf-8'))
        return [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
                for fj in r['flights']], r
    r = json.load(open(os.path.join(OUT, 'p2_results.json'), encoding='utf-8'))
    return [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
            for fj in r['flights']], r


def minimal_fleet(gf, releases=None):
    """搜索该组满足时限的最小机队（各机型 UAV 数 + 电池数）。"""
    best = None
    # 机型上限：A 4 / B 2 / C 2（全库存为其上界）
    for nA in range(0, 5):
        for nB in range(0, 3):
            for nC in range(0, 3):
                for extra in range(0, 3):   # 电池冗余（各机型 +extra）
                    lim = {'A': (nA, nA + extra), 'B': (nB, nB + extra), 'C': (nC, nC + extra)}
                    if not any(v > 0 for v in (nA, nB, nC)):
                        continue
                    sch, _ = dispatch(data, gf, releases, lim)
                    if sch is None:
                        continue
                    met = evaluate(data, gf, sch)
                    if met['hard_ok']:
                        # 优先零迟到，其次无人机总数少，再次电池冗余少
                        key = (1 if met['tardy_w'] > 1e-6 else 0,
                               nA + nB + nC, extra)
                        if best is None or key < best['key']:
                            best = {'key': key, 'limit': lim, 'schedule': sch, 'met': met}
    return best


def split_flights(flights, areas):
    """把 P2 架次按组分拆：只保留该组区域的货箱。"""
    aset = set(areas)
    out = []
    fid = 100
    for f in flights:
        route = [(s, [b for b in bs if data.boxes[b]['area'] in aset]) for s, bs in f.route]
        route = [(s, bs) for s, bs in route if bs]
        if route:
            out.append(Flight(fid, route, f.model, data))
            fid += 1
    return out


def group_plan(name, areas, n_box_expected=None):
    """返回该组的资源需求统计。"""
    flights, _ = load_p2_flights()
    gfl = split_flights(flights, areas)
    # 检查箱覆盖
    got = set()
    for f in gfl:
        got.update(f.box_ids)
    all_boxes = [b for b, bx in data.boxes.items() if bx['area'] in set(areas)]
    if got != set(all_boxes):
        missing = set(all_boxes) - got
        extra = got - set(all_boxes)
        print('  WARN group %s missing=%d extra=%d' % (name, len(missing), len(extra)))
    schedule, _ = dispatch(data, gfl)
    met = evaluate(data, gfl, schedule)
    # 最小机队搜索
    mf = minimal_fleet(gfl)
    if mf is None:
        print('  !! no minimal fleet found (deadlines unmet even with full inventory)')
        mf = {'key': (99, 4, 2, 2, 0), 'limit': None, 'schedule': schedule, 'met': met}
    schedule = mf['schedule']
    met = mf['met']
    uav_by_model = {m: n for m, (n, _) in mf['limit'].items() if n > 0}
    extra = mf['key'][2] if len(mf['key']) > 2 else 0
    bat_by_model = {m: n + extra for m, n in uav_by_model.items()}
    # 中继需求：逐样本判覆盖位置，统计必要位置与并发
    POS_ALL = {'W': P_W, 'E': P_E, 'N': P_N}
    needed = set()
    active = []          # (t0, t1, pos)
    for f in gfl:
        start = schedule[f.fid]['start']
        pts, _ = flight_trajectory(f, start)
        groups = {}
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            best = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                              data.areas[s]['lon'], data.areas[s]['lat']))
            groups.setdefault(best, []).append(pt)
        for sid, sgs in groups.items():
            cover = []
            for g, pos in POS_ALL.items():
                if all(relay_link_ok(pt['lon'], pt['lat'], pt['z'], pos, data) for pt in sgs):
                    cover.append(g)
            if not cover:
                # 退化：取覆盖最多的位置
                best_g = max(POS_ALL, key=lambda g: sum(1 for pt in sgs
                                                        if relay_link_ok(pt['lon'], pt['lat'], pt['z'], POS_ALL[g], data)))
                cover = [best_g]
            g = cover[0]
            needed.add(g)
            active.append((min(pt['t'] for pt in sgs), max(pt['t'] for pt in sgs), g))
    events = []
    for t0, t1, g in active:
        events.append((t0, 1, g))
        events.append((t1, -1, g))
    events.sort(key=lambda x: (x[0], x[1]))
    cur_pos = set()
    maxcc = 0
    for t, dt, g in events:
        if dt == 1:
            cur_pos.add(g)
        else:
            cur_pos.discard(g)
        maxcc = max(maxcc, len(cur_pos))
    n_pos = len(needed)
    windows = {}
    for t0, t1, g in active:
        windows.setdefault(g, []).append((t0, t1))
    # 中继架次（能量切分：每位置窗口可能拆成多个架次）
    n_relay_sorties = 0
    relay_e = 0.0
    max_sortie_s = E_BUDGET / (data.relay_type['P_hover'] + data.relay_type['P_comm']) * 3600.0
    for g, wlist in windows.items():
        pos = POS_ALL[g]
        t0 = min(w[0] for w in wlist)
        t1 = max(w[1] for w in wlist)
        a, b = t0, t1
        # 窗口内合并：先按时间合并重叠窗口再切架次
        wlist.sort()
        merged = [list(wlist[0])]
        for (x0, x1) in wlist[1:]:
            if x0 <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], x1)
            else:
                merged.append([x0, x1])
        for (a, b) in merged:
            dur = max(0.0, b - a)
            k = max(1, int(math.ceil(dur / max_sortie_s)))
            n_relay_sorties += k
            relay_e += relay_mission_energy(pos[0], pos[1], pos[2], data, dur)
    return {
        'name': name, 'areas': areas,
        'nbox': len(all_boxes),
        'mass': round(sum(data.boxes[b]['mass'] for b in all_boxes), 1),
        'hard_ok': met['hard_ok'], 'tardy_w': round(met['tardy_w'], 1),
        'makespan': round(met['makespan'], 1), 'energy': round(met['energy'], 2),
        'flights': len(gfl),
        'uav_by_model': uav_by_model, 'bat_by_model': bat_by_model,
        'relay_positions': sorted(needed), 'relay_concurrency': maxcc,
        'relay_sorties': n_relay_sorties, 'relay_energy': round(relay_e, 2),
    }


def redundancy(plan):
    """资源需求 = 最小机队 + 冗余备份（每种在用机型 +1 架、电池 +1 组、中继 +1 架）。"""
    uav = {'A': plan['uav_by_model'].get('A', 0),
           'B': plan['uav_by_model'].get('B', 0),
           'C': plan['uav_by_model'].get('C', 0)}
    bat = {'A': plan['bat_by_model'].get('A', 0),
           'B': plan['bat_by_model'].get('B', 0),
           'C': plan['bat_by_model'].get('C', 0)}
    alloc_uav = {g: v + 1 for g, v in uav.items() if v > 0}
    alloc_bat = {g: v + 1 for g, v in bat.items() if v > 0}
    n_relay = max(1, plan['relay_concurrency']) + 1
    n_comp = max(1, plan['relay_sorties'])
    return alloc_uav, alloc_bat, n_relay, n_comp


def save_p4(K, plans, tot_uav, tot_bat, tot_relay, tot_comp, ok):
    """保存各组配置到 results/p4_results.json。"""
    path = os.path.join(OUT, 'p4_results.json')
    all_out = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    all_out[str(K)] = {
        'groups': [{'name': it['plan']['name'], 'areas': it['plan']['areas'],
                    'nbox': it['plan']['nbox'], 'mass': it['plan']['mass'],
                    'hard_ok': it['plan']['hard_ok'], 'tardy_w': it['plan']['tardy_w'],
                    'makespan': it['plan']['makespan'], 'energy': it['plan']['energy'],
                    'flights': it['plan']['flights'],
                    'used_uav': it['plan']['uav_by_model'], 'used_bat': it['plan']['bat_by_model'],
                    'relay_positions': it['plan']['relay_positions'],
                    'relay_concurrency': it['plan']['relay_concurrency'],
                    'relay_sorties': it['plan']['relay_sorties'],
                    'relay_energy': it['plan']['relay_energy'],
                    'alloc_uav': it['alloc'][0], 'alloc_bat': it['alloc'][1],
                    'alloc_relay': it['alloc'][2], 'alloc_comp': it['alloc'][3]}
                    for it in plans],
        'totals': {'uav': tot_uav, 'bat': tot_bat, 'relay': tot_relay, 'comp': tot_comp},
        'within_inventory': {'uav': ok[0], 'bat': ok[1], 'relay': ok[2], 'comp': ok[3]},
    }
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(all_out, fh, ensure_ascii=False, indent=1)
    print('saved p4_results.json (K=%d)' % K)


def main():
    for K, groups in [(3, GROUPS_3), (2, GROUPS_2)]:
        print('\n===== K=%d 分组 =====' % K)
        plans = []
        for gname, areas in groups.items():
            print('--- %s: %s ---' % (gname, areas))
            pl = group_plan(gname, areas)
            print('  boxes=%d mass=%.0f hard=%s tardy=%.1f makespan=%.0f energy=%.2f flights=%d'
                  % (pl['nbox'], pl['mass'], pl['hard_ok'], pl['tardy_w'],
                     pl['makespan'], pl['energy'], pl['flights']))
            print('  uav used: %s  bat used: %s' % (pl['uav_by_model'], pl['bat_by_model']))
            print('  relay positions=%s concurrency=%d sorties=%d energy=%.2f'
                  % (pl['relay_positions'], pl['relay_concurrency'], pl['relay_sorties'],
                     pl['relay_energy']))
            au, ab, nr, nc = redundancy(pl)
            print('  alloc: uav=%s bat=%s relay=%d comps=%d' % (au, ab, nr, nc))
            plans.append({'plan': pl, 'alloc': (au, ab, nr, nc)})
        # 汇总 vs 库存
        tot_uav = {'A': 0, 'B': 0, 'C': 0}
        tot_bat = {'A': 0, 'B': 0, 'C': 0}
        tot_relay = 0
        tot_comp = 0
        for item in plans:
            au, ab, nr, nc = item['alloc']
            for g in tot_uav:
                tot_uav[g] += au.get(g, 0)
                tot_bat[g] += ab.get(g, 0)
            tot_relay += nr
            tot_comp += nc
        print('  TOTAL alloc uav=%s (库存 A4/B2/C2) bat=%s (A6/B4/C4) relay=%d (2) comps=%d (6)'
              % (tot_uav, tot_bat, tot_relay, tot_comp))
        ok_uav = all(tot_uav[g] <= {'A': 4, 'B': 2, 'C': 2}[g] for g in tot_uav)
        ok_bat = all(tot_bat[g] <= {'A': 6, 'B': 4, 'C': 4}[g] for g in tot_bat)
        ok_relay = tot_relay <= 2
        ok_comp = tot_comp <= 6
        print('  within inventory: uav=%s bat=%s relay=%s comps=%s' % (ok_uav, ok_bat, ok_relay, ok_comp))
        save_p4(K, plans, tot_uav, tot_bat, tot_relay, tot_comp,
                (ok_uav, ok_bat, ok_relay, ok_comp))


if __name__ == '__main__':
    main()