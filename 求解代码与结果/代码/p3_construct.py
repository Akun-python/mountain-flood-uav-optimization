# -*- coding: utf-8 -*-
"""问题三构建式协同方案（v4）：货箱重排 + 释放时刻平移 + 中继排班
核心结构：
  位置: PW(西9区) / PE(东南4区) / PN(S004)
  R1 中继: W 区（抵达 810s 后持续服务）
  R2 中继: E 区[830~4300] -> 转场补电 -> N 区[S004][6200~7800] -> 转场 -> W尾(f55)
构建步骤：
  1) S014-FOD: f10 -> f67;  S012-FOD: f58 -> f72  (缩短 f10/f58 的 E 相位)
  2) f58/f72 提前，f70/f42/f73 推后(释放时刻)，使 E 相位收于 ~4200、S004 相位落入 R2 的 N 槽
  3) 校验运输可行性后生成中继架次排班与通信保障表
"""
import sys, os, json, math, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import (Data, relay_mission_time, relay_mission_energy, direct_ok,
                  relay_link_ok, charge_time)
from p3_gaps import flight_trajectory
from p2_solve import Flight, dispatch, evaluate

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = Data()
REL = data.relay_type
E_BUDGET = (1 - REL['rho']) * REL['E_use']
P_HOVER = REL['P_hover'] + REL['P_comm']
T_FULL = data.relay_energy['T_full']

P_W = (109.2103, 23.047134, 676.5)
P_E = (109.276017, 23.019401, 542.3)
P_N = (109.238171, 23.077841, 496.1)
AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'
POS_OF = {'W': P_W, 'E': P_E, 'N': P_N}

# 货箱重排（src_fid, box, tgt_fid）——
#   缩短 E 尾相位：f10 只留 S001（S014/S010-FOD 移走），f58 改运 S013+S010-FOD
#   S009 尾班入早间 W1 窗口；S004 MED 与 S008-HYG 进已有时段
BOX_MOVES = [('S014-FOD-01', 10, 67), ('S012-FOD-01', 58, 72), ('S002-MED-01', 63, 1),
             ('S010-FOD-01', 10, 58),
             ('S004-MED-01', 42, 70), ('S009-MED-01', 69, 10), ('S008-HYG-01', 69, None),
             ('S009-WAT-01', 55, 10), ('S009-FOD-01', 55, 10), ('S011-FOD-01', 55, 10)]
# 新增架次（fid: (model, route)）—— 独立 A 型班次运 S008-HYG，使 S008 尾部进 W1 窗口
NEW_FLIGHTS = {200: ('A', [('S008', ['S008-HYG-01'])])}
# 释放时刻平移（fid, delta）
RELEASES = {58: -1500.0, 72: -500.0, 70: 950.0, 73: 2600.0, 40: 700.0}


def rebuild_route(route, box, tgt_area, remove=False):
    out = []
    added = False
    for s, bs in route:
        if remove and box in bs:
            bs = [b for b in bs if b != box]
        if not remove and s == tgt_area:
            bs = list(bs) + [box]
            added = True
        if bs:
            out.append((s, bs))
    if not remove and not added:
        out.append((tgt_area, [box]))   # 新签到架次末尾
    return out


def apply_moves(flights):
    for box, src, tgt in BOX_MOVES:
        bx = data.boxes[box]
        sf = next(f for f in flights if f.fid == src)
        flights[flights.index(sf)] = Flight(sf.fid, rebuild_route(sf.route, box, None, remove=True), sf.model, data)
        if tgt is not None:
            tf = next(f for f in flights if f.fid == tgt)
            flights[flights.index(tf)] = Flight(tf.fid, rebuild_route(tf.route, box, bx['area'], remove=False), tf.model, data)
        print('moved %s f%02d -> %s' % (box, src, 'DROP' if tgt is None else ('f%02d' % tgt)))
    # 撤销空架次
    out = [f for f in flights if f.box_ids]
    # 新增架次
    for fid, (model, route) in NEW_FLIGHTS.items():
        out.append(Flight(fid, [(s, list(b)) for s, b in route], model, data))
    removed = len(flights) - len([f for f in flights if f.box_ids])
    print('dropped %d empty flights, added %d new' % (removed, len(NEW_FLIGHTS)))
    return out


def run(rel_override=None):
    r = json.load(open(os.path.join(OUT, 'p2_results.json'), encoding='utf-8'))
    base = {fj['fid']: fj['start'] for fj in r['flights']}
    flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
               for fj in r['flights']]
    flights = apply_moves(flights)
    releases = dict(RELEASES if rel_override is None else rel_override)
    # 释放时刻下限：不让开始时刻为负
    rel_all = {}
    for f in flights:
        v = max(0.0, base.get(f.fid, 0.0) + releases.get(f.fid, 0.0))
        rel_all[f.fid] = v
    schedule, _ = dispatch(data, flights, rel_all)
    met = evaluate(data, flights, schedule)
    print('transport:', {k: (round(v, 1) if isinstance(v, float) else v)
                         for k, v in met.items() if k != 'box_time'})
    print('releases:', {k: round(v) for k, v in rel_all.items() if v != base.get(k, 0.0)})
    if not met['hard_ok']:
        print('HARD VIOLATION'); return None
    # ---- 任务与中继排班 ----
    missions = []
    for f in flights:
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
            if sid not in AREA_POS:
                continue
            def cov(g):
                pos = POS_OF[g]
                return all(relay_link_ok(pt['lon'], pt['lat'], pt['z'], pos, data) for pt in sgs)
            # 优先本区组位置；其次任一全覆盖位置；否则取覆盖最多
            cands = [AREA_POS[sid]] + [g for g in ('W', 'E', 'N') if g != AREA_POS[sid]]
            g = next((c for c in cands if cov(c)), None)
            if g is None:
                g = max(('W', 'E', 'N'), key=lambda gg: sum(1 for pt in sgs
                                                            if relay_link_ok(pt['lon'], pt['lat'], pt['z'], POS_OF[gg], data)))
            pos = POS_OF[g]
            n_cov = sum(1 for pt in sgs if relay_link_ok(pt['lon'], pt['lat'], pt['z'], pos, data))
            missions.append({'fid': f.fid, 'area': sid, 'grp': g,
                             't0': min(pt['t'] for pt in sgs), 't1': max(pt['t'] for pt in sgs),
                             'n': len(sgs), 'n_cov': n_cov})
    cov_bad = [m for m in missions if m['n_cov'] < m['n']]
    print('missions=%d cover_bad=%d' % (len(missions), len(cov_bad)))
    for m in cov_bad[:8]:
        print('  BAD f%02d %s %s cov=%d/%d [%.0f,%.0f]' % (m['fid'], m['area'], m['grp'],
                                                            m['n_cov'], m['n'], m['t0'], m['t1']))
    # ---- 中继架次：R1=W；R2=E,N,W2(尾段W) ----
    by = {}
    for m in missions:
        by.setdefault(m['grp'], []).append(m)

    def make_sorties(g):
        ms = sorted(by.get(g, []), key=lambda m: m['t0'])
        pos = POS_OF[g]
        out = []
        cur = None
        for m in ms:
            if cur is None:
                cur = {'t0': m['t0'], 't1': m['t1'], 'ms': [m]}
                continue
            t1 = max(cur['t1'], m['t1'])
            e = relay_mission_energy(pos[0], pos[1], pos[2], data, t1 - cur['t0'])
            if e <= E_BUDGET:
                cur['t1'] = t1
                cur['ms'].append(m)
            else:
                out.append(cur)
                cur = {'t0': m['t0'], 't1': m['t1'], 'ms': [m]}
        if cur is not None:
            out.append(cur)
        return out, pos

    w_s, w_pos = make_sorties('W')
    e_s, e_pos = make_sorties('E')
    n_s, n_pos = make_sorties('N')
    print('sorties: W=%d E=%d N=%d' % (len(w_s), len(e_s), len(n_s)))
    for g, ss, pos in (('W', w_s, w_pos), ('E', e_s, e_pos), ('N', n_s, n_pos)):
        for s in ss:
            t_out, t_back, _ = relay_mission_time(pos[0], pos[1], pos[2], data)
            e = relay_mission_energy(pos[0], pos[1], pos[2], data, s['t1'] - s['t0'])
            print('  %s [%.0f, %.0f] e=%.3f dispatch=%.0f ret=%.0f'
                  % (g, s['t0'], s['t1'], e, s['t0'] - t_out - REL['t_link'], s['t1'] + t_back))
    # 校验 2 中继时间线
    def seq_penalty(sorties, pos, label, start_ready=0.0):
        t_out, t_back, _ = relay_mission_time(pos[0], pos[1], pos[2], data)
        ready = start_ready
        pen = 0.0
        for k, s in enumerate(sorties):
            dispatch_t = s['t0'] - t_out - REL['t_link']
            if k > 0 and dispatch_t < ready:
                pen += ready - dispatch_t
                print('  TRANSIT %s sortie%d: need >=%.0f have %.0f' % (label, k, ready, dispatch_t))
            e = relay_mission_energy(pos[0], pos[1], pos[2], data, s['t1'] - s['t0'])
            ch = charge_time(1 - e / REL['E_use'], T_FULL)
            ready = s['t1'] + t_back + ch
        return pen

    p1 = seq_penalty(w_s, w_pos, 'R1-W')
    # R2: E 架次 + N 架次 + W 尾段
    tail = [s for s in w_s[1:]]
    r2 = sorted(e_s + n_s + tail, key=lambda s: s['t0'])
    ready2 = 0.0
    pen2 = 0.0
    for k, s in enumerate(r2):
        g = 'E' if s in e_s else ('N' if s in n_s else 'W')
        pos = POS_OF[g]
        t_out, t_back, _ = relay_mission_time(pos[0], pos[1], pos[2], data)
        dispatch_t = s['t0'] - t_out - REL['t_link']
        if k > 0 and dispatch_t < ready2:
            pen2 += ready2 - dispatch_t
            print('  R2 TRANSIT sortie%d (%s): need >=%.0f have %.0f' % (k, g, ready2, dispatch_t))
        e = relay_mission_energy(pos[0], pos[1], pos[2], data, s['t1'] - s['t0'])
        ch = charge_time(1 - e / REL['E_use'], T_FULL)
        ready2 = s['t1'] + t_back + ch
    print('R1 pen=%.0f  R2 pen=%.0f' % (p1, pen2))
    # ---- 保存最终结果 ----
    out = {
        'transport': {k: (float(v) if hasattr(v, 'item') else v)
                      for k, v in met.items() if k != 'box_time'},
        'releases': rel_all,
        'flights': [{'fid': f.fid, 'model': f.model, 'mass': round(f.total_mass, 1),
                     'energy': round(f.energy(), 3),
                     'route': [[s, b] for s, b in f.route]}
                    for f in flights],
        'schedule': {str(k): {'uav': v['uav'], 'battery': v['battery'],
                              'start': round(v['start'], 1), 'return': round(v['return'], 1),
                              'energy': round(v['energy'], 3),
                              'deliveries': [[d[0], d[1], round(d[2], 1)] for d in v['deliveries']]}
                     for k, v in schedule.items()},
        'missions': missions,
        'sorties': [{'relay': 'R01', 'pos': 'W', 't0': round(s['t0'], 1), 't1': round(s['t1'], 1),
                     'energy': round(relay_mission_energy(w_pos[0], w_pos[1], w_pos[2], data, s['t1'] - s['t0']), 3),
                     'missions': [m['fid'] for m in s['ms']]} for s in w_s] +
                    [{'relay': 'R02', 'pos': 'E', 't0': round(s['t0'], 1), 't1': round(s['t1'], 1),
                      'energy': round(relay_mission_energy(e_pos[0], e_pos[1], e_pos[2], data, s['t1'] - s['t0']), 3),
                      'missions': [m['fid'] for m in s['ms']]} for s in e_s] +
                    [{'relay': 'R02', 'pos': 'N', 't0': round(s['t0'], 1), 't1': round(s['t1'], 1),
                      'energy': round(relay_mission_energy(n_pos[0], n_pos[1], n_pos[2], data, s['t1'] - s['t0']), 3),
                      'missions': [m['fid'] for m in s['ms']]} for s in n_s],
    }
    with open(os.path.join(OUT, 'p3_final.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('saved p3_final.json')
    return {'met': met, 'missions': missions, 'schedule': schedule, 'flights': flights,
            'w': w_s, 'e': e_s, 'n': n_s, 'pen': p1 + pen2}


if __name__ == '__main__':
    res = run()
    json.dump({'ok': res is not None},
              open(os.path.join(OUT, 'p3_construct_check.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)