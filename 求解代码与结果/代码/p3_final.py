# -*- coding: utf-8 -*-
"""问题三最终求解：运输平移 + 双中继排班（能量/组件/转场）
结构：
  R1 固定服务 西区位置 P1（S001,S002,S003,S005,S007,S008,S009,S011,S015）
  R2 轮转服务 东区位置 P2（S006,S010,S012,S013）/ P3（S004）/ P4（S014）
迭代：平移运输架次 -> 重排中继架次 -> 检查覆盖与时限 -> 收敛
"""
import sys, os, json, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import (Data, relay_mission_time, relay_mission_energy, charge_time,
                  relay_backhaul_ok, relay_link_ok, direct_ok)
from p3_gaps import analyze_gaps, flight_trajectory
from p2_solve import Flight, dispatch, evaluate, MODELS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = Data()
REL = data.relay_type
E_BUDGET = (1 - REL['rho']) * REL['E_use']   # 2.56 kWh
P_HOVER = REL['P_hover'] + REL['P_comm']     # 1.10 kW

# 悬停位置（由锚点集合覆盖求得）
POS = {
    'W': (109.204858, 23.04721, 689.9),
    'E': (109.258858, 23.01121, 630.2),
    'N': (109.222858, 23.07121, 454.6),
    'SE': (109.264858, 23.00521, 584.0),
}
AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S006', 'S010', 'S012', 'S013']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'
AREA_POS['S014'] = 'SE'


def load_p2():
    with open(os.path.join(OUT, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    flights = []
    for fj in r['flights']:
        f = Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
        f.start0 = fj['start']
        flights.append(f)
    return flights, r


def build_missions(flights, offsets):
    """每架次每区访问段 -> 中继任务。verification: 位置须覆盖全部样本。"""
    missions = []
    for f in flights:
        start = f.start0 + offsets.get(f.fid, 0.0)
        pts, _ = flight_trajectory(f, start)
        groups = {}
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            best = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                              data.areas[s]['lon'], data.areas[s]['lat']))
            groups.setdefault(best, []).append(pt)
        for sid, sgs in groups.items():
            pos = POS[AREA_POS[sid]]
            n_cov = sum(1 for g in sgs if relay_link_ok(g['lon'], g['lat'], g['z'], pos, data))
            missions.append({'fid': f.fid, 'area': sid, 'pos': pos,
                             't0': min(g['t'] for g in sgs), 't1': max(g['t'] for g in sgs),
                             'n': len(sgs), 'n_cov': n_cov})
    return missions


def sorties_for_position(ms, t_build=REL['t_link'], verbose=False):
    """对一个位置的中继任务序列，构造架次（能量约束 + 转场）。ms: missions at that pos.
    返回 sorties: [{t0_serve, t1_serve, dispatch, return, energy}] 以及覆盖情况。"""
    ms = sorted(ms, key=lambda m: m['t0'])
    t_out, t_back, _ = relay_mission_time(POS_NONE := None, 0, 0, data) if False else (0, 0, 0)
    sorties = []
    cur = None
    for m in ms:
        e_flight_single = relay_energy_sortie_single(m['pos'])
        if cur is None:
            cur = {'pos': m['pos'], 't0': m['t0'], 't1': m['t1'], 'ms': [m]}
            continue
        # 尝试把 m 并入当前架次
        e_new = relay_mission_energy(m['pos'][0], m['pos'][1], m['pos'][2], data, cur['t1'] - cur['t0']) \
            if False else None
        serve_len = max(cur['t1'], m['t1']) - min(cur['t0'], m['t0'])
        e_all = relay_energy_for(serve_len, m['pos'])
        if e_all <= E_BUDGET:
            cur['t1'] = max(cur['t1'], m['t1'])
            cur['ms'].append(m)
        else:
            sorties.append(cur)
            cur = {'pos': m['pos'], 't0': m['t0'], 't1': m['t1'], 'ms': [m]}
    if cur is not None:
        sorties.append(cur)
    return sorties


RELAY_FLY = {}


def relay_energy_for(serve_len, pos):
    return relay_mission_energy(pos[0], pos[1], pos[2], data, serve_len)


def relay_energy_sortie_single(pos):
    return relay_mission_energy(pos[0], pos[1], pos[2], data, 0.0)


def cover_check(missions, sorties_by_pos, t_build=REL['t_link']):
    """检查每个任务的窗口是否被其位置的某架次覆盖（含转场与建链提前量）。"""
    problems = []
    for m in missions:
        pos = m['pos']
        covered = False
        for s in sorties_by_pos.get(pos, []):
            # 架次服务窗口 [s.t0, s.t1]；转场后建链完成时刻 = dispatch + t_out + t_link
            # 简化：服务窗口即 [t0_serve, t1_serve]，并要求任务 t0 >= t0_serve - t_link, t1 <= t1_serve
            if m['t0'] >= s['t0'] - t_build - 1e-6 and m['t1'] <= s['t1'] + 1e-6:
                covered = True
                break
        if not covered:
            problems.append(m)
    return problems


def n_perfect(missions):
    return sum(1 for m in missions if m['n_cov'] == m['n'])


def main():
    flights, r2 = load_p2()
    offsets = {f.fid: 0.0 for f in flights}
    # ---- 迭代修复 ----
    for it in range(60):
        missions = build_missions(flights, offsets)
        # 按位置分组建架次（并行贪心）
        by_pos = {}
        for m in missions:
            by_pos.setdefault(m['pos'], []).append(m)
        sorties_by_pos = {}
        for pos, ms in by_pos.items():
            sorties_by_pos[pos] = []
            ms = sorted(ms, key=lambda m: m['t0'])
            cur = None
            for m in ms:
                if cur is None:
                    cur = {'pos': pos, 't0': m['t0'], 't1': m['t1'], 'ms': [m]}
                    continue
                serve_len = max(cur['t1'], m['t1']) - min(cur['t0'], m['t0'])
                if relay_energy_for(serve_len, pos) <= E_BUDGET:
                    cur['t1'] = max(cur['t1'], m['t1'])
                    cur['ms'].append(m)
                else:
                    sorties_by_pos[pos].append(cur)
                    cur = {'pos': pos, 't0': m['t0'], 't1': m['t1'], 'ms': [m]}
            if cur is not None:
                sorties_by_pos[pos].append(cur)
        # 覆盖检查
        problems = cover_check(missions, sorties_by_pos)
        # 时间冲突检查：R2 承载的 E/N/SE 位置服务窗口不得重叠
        r2_segments = (sorties_by_pos.get('E', []) + sorties_by_pos.get('N', [])
                       + sorties_by_pos.get('SE', []))
        r2_segments.sort(key=lambda s: s['t0'])
        conflict = None
        for i in range(len(r2_segments) - 1):
            if r2_segments[i]['t1'] > r2_segments[i + 1]['t0']:
                conflict = (r2_segments[i], r2_segments[i + 1])
                break
        print('iter %2d: missions=%d perfect=%d/%d cover_problems=%d r2_conflict=%s'
              % (it, len(missions), n_perfect(missions), len(missions), len(problems),
                 (conflict is not None)))
        if not problems and conflict is None:
            break
        # 修复：优先处理冲突/未覆盖任务，平移其架次 +600s
        shift_set = set()
        if conflict is not None:
            shift_set.update(m['fid'] for m in conflict[1]['ms'])
        else:
            m0 = problems[0]
            shift_set.add(m0['fid'])
        for fid in shift_set:
            offsets[fid] = offsets.get(fid, 0.0) + 600.0
    # ---- 运输重调度（带偏移）并检验时限 ----
    for f in flights:
        f.start0 = f.start0 + offsets.get(f.fid, 0.0)
    schedule, _ = dispatch(data, flights)
    met = evaluate(data, flights, schedule)
    print('transport after shift:', {k: (round(v, 1) if isinstance(v, float) else v)
                                     for k, v in met.items() if k != 'box_time'})
    # 重新构建最终架次
    missions = build_missions(flights, offsets)
    by_pos = {}
    for m in missions:
        by_pos.setdefault(m['pos'], []).append(m)
    sorties_by_pos = {}
    for pos, ms in by_pos.items():
        ms = sorted(ms, key=lambda m: m['t0'])
        sorties_by_pos[pos] = []
        cur = None
        for m in ms:
            if cur is None:
                cur = {'pos': pos, 't0': m['t0'], 't1': m['t1'], 'ms': [m]}
                continue
            serve_len = max(cur['t1'], m['t1']) - min(cur['t0'], m['t0'])
            if relay_energy_for(serve_len, pos) <= E_BUDGET:
                cur['t1'] = max(cur['t1'], m['t1'])
                cur['ms'].append(m)
            else:
                sorties_by_pos[pos].append(cur)
                cur = {'pos': pos, 't0': m['t0'], 't1': m['t1'], 'ms': [m]}
        if cur is not None:
            sorties_by_pos[pos].append(cur)
    problems = cover_check(missions, sorties_by_pos)
    print('final cover problems:', len(problems))
    for p in problems[:10]:
        print('  ', p['fid'], p['area'], p['t0'], p['t1'], p['n_cov'], p['n'])
    total_relay_e = 0.0
    n_sorties = 0
    rows = []
    for pos, ss in sorties_by_pos.items():
        for s in ss:
            t_out, t_back, t_flight = relay_mission_time(pos[0], pos[1], pos[2], data)
            e = relay_energy_for(s['t1'] - s['t0'], pos)
            total_relay_e += e
            n_sorties += 1
            rows.append({'pos': pos, 't0_serve': s['t0'], 't1_serve': s['t1'],
                         'dispatch': s['t0'] - t_out - REL['t_link'],
                         'return': s['t1'] + t_back, 'energy': round(e, 3),
                         'n_mission': len(s['ms'])})
            print('sortie %s t=[%.0f, %.0f] dispatch=%.0f ret=%.0f e=%.3f kWh n_mission=%d'
                  % (pos, s['t0'], s['t1'], s['t0'] - t_out - REL['t_link'],
                     s['t1'] + t_back, e, len(s['ms'])))
    print('total relay sorties:', n_sorties, ' total relay energy: %.2f kWh' % total_relay_e)
    json.dump({'offsets': offsets,
               'transport_metrics': {k: (round(v, 2) if isinstance(v, float) else v)
                                     for k, v in met.items() if k != 'box_time'},
               'relay_sorties': rows, 'missions': missions,
               'total_relay_energy': round(total_relay_e, 3)},
              open(os.path.join(OUT, 'p3_final.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()