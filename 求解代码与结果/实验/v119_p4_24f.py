# -*- coding: utf-8 -*-
"""v119：问题四按 24 架冠军（v113_best.json）重算——趟级分量归属：
多区趟 f37(S006|S014)->东组、f38(S005|S011)->西组、f39(S006|S007)->西组；
S006 单区趟归东组；其余按区。严格电池口径（dispatch_compliant+check_battery）。"""
import sys, os, json, math
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from core import Data, relay_mission_time, relay_mission_energy, direct_ok, relay_link_ok, charge_time
from p2_solve import Flight, evaluate
from p2v28_compliant import dispatch_compliant
from p3_gaps import flight_trajectory
from p3_co2 import P_W, P_E, P_N
from audit_results import check_battery
from dqn23_enhanced import OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'v113_best.json'), encoding='utf-8'))
flights = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
print('输入: %d架次 (24架冠军)' % len(flights))
# 趟级归属：多区趟整块（fid -> 组 W/E）
MULTI_OWN = {37: 'E', 38: 'W', 39: 'W'}
# 组区集合（S006 双归属：单区 S006 归东）
GROUPS_3 = {
    'G1(W)': ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015'],
    'G2(E)': ['S006', 'S010', 'S012', 'S013', 'S014'],
    'G3(N)': ['S004'],
}
GROUPS_2 = {
    'G1(W)': ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015'],
    'G2(E+N)': ['S004', 'S006', 'S010', 'S012', 'S013', 'S014'],
}
E_BUDGET = (1 - data.relay_type['rho']) * data.relay_type['E_use']


def bx_area(data, b):
    return data.boxes[b]['area']


def split_flights(flights, gname, areas):
    aset = set(areas)
    out = []
    fid = 100
    for f in flights:
        zones = [s for s, bs in f.route]
        if len(set(zones)) > 1:
            own = MULTI_OWN.get(f.fid)
            if own is None:
                own = 'E' if 'S014' in zones else 'W'
            if own != gname.split('(')[1][0]:   # gname 形如 'G1(W)'，[2] 为组字母 W/E/N
                continue
        else:
            if not any(z in aset for z in zones):
                continue
        out.append(Flight(fid, [(s, list(bs)) for s, bs in f.route], f.model, data))
        fid += 1
    return out


def minimal_fleet(gf):
    best = None
    for nA in range(0, 5):
        for nB in range(0, 3):
            for nC in range(0, 3):
                for extra in range(0, 3):
                    lim = {'A': (nA, nA + extra), 'B': (nB, nB + extra), 'C': (nC, nC + extra)}
                    if not any(v > 0 for v in (nA, nB, nC)): continue
                    sch, _ = dispatch_compliant(data, gf, lim)
                    if sch is None: continue
                    met = evaluate(data, gf, sch)
                    if not met['hard_ok']: continue
                    bv = check_battery(data, sch, gf)
                    if bv: continue
                    key = (1 if met['tardy_w'] > 1e-6 else 0, nA + nB + nC, extra)
                    if best is None or key < best['key']:
                        best = {'key': key, 'limit': lim, 'schedule': sch, 'met': met}
    return best


def group_plan(gname, areas):
    gfl = split_flights(flights, gname, areas)
    got = set()
    for f in gfl: got.update(f.box_ids)
    allb = [b for b, bx in data.boxes.items() if bx['area'] in set(areas)]
    for f in flights:
        if len(set(s for s, _ in f.route)) > 1:
            own = MULTI_OWN.get(f.fid, 'E' if 'S014' in [s for s, _ in f.route] else 'W')
            if own == gname.split('(')[1][0]:
                allb += [b for s, bs in f.route for b in bs if bx_area(data, b) not in set(areas)]
    if got != set(allb):
        print('  WARN %s missing=%d extra=%d' % (gname, len(set(allb) - got), len(got - set(allb))))
    mf = minimal_fleet(gfl)
    if mf is None:
        print('  !! %s: 全库存不可行' % gname); return None
    sch = mf['schedule']; met = mf['met']
    uav = {m: n for m, (n, _) in mf['limit'].items() if n > 0}
    extra = mf['key'][2]
    bat = {m: n + extra for m, n in uav.items()}
    POS_ALL = {'W': P_W, 'E': P_E, 'N': P_N}
    needed = set(); active = []
    for f in gfl:
        start = sch[f.fid]['start']
        pts, _ = flight_trajectory(f, start)
        groups = {}
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data): continue
            best = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'], data.areas[s]['lon'], data.areas[s]['lat']))
            groups.setdefault(best, []).append(pt)
        for sid, sgs in groups.items():
            cover = [g for g, pos in POS_ALL.items() if all(relay_link_ok(pt['lon'], pt['lat'], pt['z'], pos, data) for pt in sgs)]
            if not cover:
                best_g = max(POS_ALL, key=lambda g: sum(1 for pt in sgs if relay_link_ok(pt['lon'], pt['lat'], pt['z'], POS_ALL[g], data)))
                cover = [best_g]
            g = cover[0]
            needed.add(g)
            active.append((min(pt['t'] for pt in sgs), max(pt['t'] for pt in sgs), g))
    ev = []
    for t0, t1, g in active:
        ev.append((t0, 1, g)); ev.append((t1, -1, g))
    ev.sort(key=lambda x: (x[0], x[1]))
    cur = set(); maxcc = 0
    for t, dt, g in ev:
        cur.add(g) if dt == 1 else cur.discard(g)
        maxcc = max(maxcc, len(cur))
    windows = {}
    for t0, t1, g in active: windows.setdefault(g, []).append((t0, t1))
    n_sorties = 0; relay_e = 0.0
    max_sortie_s = E_BUDGET / (data.relay_type['P_hover'] + data.relay_type['P_comm']) * 3600.0
    for g, wlist in windows.items():
        pos = POS_ALL[g]
        wlist.sort(); merged = [list(wlist[0])]
        for (x0, x1) in wlist[1:]:
            if x0 <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], x1)
            else: merged.append([x0, x1])
        for (a, b) in merged:
            dur = max(0.0, b - a)
            k = max(1, int(math.ceil(dur / max_sortie_s)))
            n_sorties += k
            relay_e += relay_mission_energy(pos[0], pos[1], pos[2], data, dur)
    return {'name': gname, 'nbox': len(allb), 'makespan': round(met['makespan'], 1),
            'energy': round(met['energy'], 2), 'tardy': round(met['tardy_w'], 1),
            'flights': len(gfl), 'uav': uav, 'bat': bat,
            'relay_pos': sorted(needed), 'relay_cc': maxcc, 'relay_sorties': n_sorties,
            'relay_energy': round(relay_e, 2)}


def redundancy(pl):
    au = {g: v + 1 for g, v in pl['uav'].items() if v > 0}
    ab = {g: v + 1 for g, v in pl['bat'].items() if v > 0}
    nr = max(1, pl['relay_cc']) + 1
    nc = max(1, pl['relay_sorties'])
    return au, ab, nr, nc


def report(K, groups):
    print('===== K=%d =====' % K)
    tot_u = {'A': 0, 'B': 0, 'C': 0}; tot_b = {'A': 0, 'B': 0, 'C': 0}; tot_r = 0; tot_c = 0
    for gname, areas in groups.items():
        pl = group_plan(gname, areas)
        if pl is None: continue
        au, ab, nr, nc = redundancy(pl)
        print('  %s: 箱%d 趟%d 完工%.0fs 能耗%.2f 迟%.1f | 在用 A%d B%d C%d 电池%d/%d/%d | 中继%s 并发%d 架次%d | 含冗余 A%d B%d C%d 电池%d/%d/%d 中继%d 组件%d' % (
            gname, pl['nbox'], pl['flights'], pl['makespan'], pl['energy'], pl['tardy'],
            pl['uav'].get('A', 0), pl['uav'].get('B', 0), pl['uav'].get('C', 0),
            pl['bat'].get('A', 0), pl['bat'].get('B', 0), pl['bat'].get('C', 0),
            pl['relay_pos'], pl['relay_cc'], pl['relay_sorties'],
            au.get('A', 0), au.get('B', 0), au.get('C', 0),
            ab.get('A', 0), ab.get('B', 0), ab.get('C', 0), nr, nc))
        for g in 'ABC':
            tot_u[g] += au.get(g, 0); tot_b[g] += ab.get(g, 0)
        tot_r += nr; tot_c += nc
    print('  合计(含冗余): A机%d/B机%d/C机%d (库存4/2/2) 电池A%d/B%d/C%d (6/4/4) 中继%d(2) 组件%d(6)' % (
        tot_u['A'], tot_u['B'], tot_u['C'], tot_b['A'], tot_b['B'], tot_b['C'], tot_r, tot_c))
    print('  缺口: 机A%d B%d C%d | 电池A%d B%d C%d | 中继%d | 组件%d' % (
        max(0, tot_u['A'] - 4), max(0, tot_u['B'] - 2), max(0, tot_u['C'] - 2),
        max(0, tot_b['A'] - 6), max(0, tot_b['B'] - 4), max(0, tot_b['C'] - 4),
        max(0, tot_r - 2), max(0, tot_c - 6)))
    return None


r3 = report(3, GROUPS_3)
r2 = report(2, GROUPS_2)
print('done v119')
