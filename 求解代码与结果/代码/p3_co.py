# -*- coding: utf-8 -*-
"""问题三核心：联合调度（运输架次平移 + 中继排班）
方法：
1) 每运输架次按“服务区访问段”构造中继任务（悬停点候选 + 服务窗口）
2) 悬停点选择：对每架次取其所有任务的候选交集，无法交集则按段拆分
3) 平移运输架次开始时刻（保持时限/UAV/电池可行），使任意时刻至多2个“中继服务区集合”并发
4) 中继排班：2架中继无人机 + 6能源组件，服务窗口/转场/能量/充电
"""
import sys, os, json, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import (Data, relay_mission_time, relay_mission_energy, charge_time,
                  relay_backhaul_ok, relay_link_ok)
from p3_gaps import analyze_gaps, flight_trajectory
from p2_solve import Flight, dispatch, evaluate, clone_flights, MODELS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = Data()
RELAY_E_BUDGET = (1 - data.relay_type['rho']) * data.relay_type['E_use']  # 2.56 kWh


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
    """按架次展开轨迹，为每“区访问段”构造中继任务。
    offsets: fid -> 平移量（秒）。返回 missions + 每个任务可直接验证覆盖的候选位置。"""
    missions = []
    area_cov = json.load(open(os.path.join(OUT, 'p3_cov.json'), encoding='utf-8'))
    cands = [tuple(c) for c in area_cov['cands']]
    for f in flights:
        off = offsets.get(f.fid, 0.0)
        start = f.start0 + off
        pts, tend = flight_trajectory(f, start)
        # 按区聚合缺口采样点
        groups = {}
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            if pt['phase'] == 'handover':
                # 找该时刻所在的区：用轨迹中的区顺序推断
                pass
            best = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                              data.areas[s]['lon'], data.areas[s]['lat']))
            groups.setdefault(best, []).append(pt)
        for sid, sgs in groups.items():
            cov = [tuple(c) for c in area_cov['area_cov'].get(sid, [])]
            missions.append({
                'fid': f.fid, 'area': sid, 't0': min(g['t'] for g in sgs),
                't1': max(g['t'] for g in sgs),
                'samples': [(g['lon'], g['lat'], g['z']) for g in sgs],
                'pos_cands': cov[:30],
            })
    return missions


def choose_positions(missions):
    """贪心：先取覆盖样本数最多的位置；同架次尽量共享位置。"""
    rng = random.Random(1)
    assigned = []
    used_positions = []
    for m in missions:
        best = None
        best_cov = -1
        for c in m['pos_cands']:
            cov = sum(1 for s in m['samples'] if relay_link_ok(s[0], s[1], s[2], c, data))
            if cov > best_cov:
                best_cov = cov
                best = c
        m['pos'] = best
        m['n_cov'] = best_cov
        m['n_all'] = len(m['samples'])
        if best is not None and best not in used_positions:
            used_positions.append(best)
        assigned.append(m)
    return assigned, used_positions


def cluster_concurrency(missions):
    """按 pos 分簇，计算任意时刻并发簇数。返回 (max_concurrency, conflicts)。"""
    by_pos = {}
    for m in missions:
        if m['pos'] is None:
            continue
        by_pos.setdefault(m['pos'], []).append(m)
    events = []
    for pos, ms in by_pos.items():
        for m in ms:
            events.append((m['t0'], 1, pos))
            events.append((m['t1'], -1, pos))
    events.sort(key=lambda x: (x[0], x[1]))
    active = {}
    maxc = 0
    conflicts = []
    for t, dt, pos in events:
        if dt == 1:
            active[pos] = t
            if len(active) > maxc:
                maxc = len(active)
                conflicts.append((t, list(active.keys())))
        else:
            active.pop(pos, None)
    return maxc, by_pos, conflicts


def relay_energy_sortie(pos, t0, t1):
    """一次中继架次能耗：往返 + 悬停服务。"""
    t_out, t_back, t_flight = relay_mission_time(pos[0], pos[1], pos[2], data)
    serve = max(0.0, t1 - t0)
    return relay_mission_energy(pos[0], pos[1], pos[2], data, serve)


def main():
    flights, r2 = load_p2()
    offsets = {f.fid: 0.0 for f in flights}
    missions, used_pos = choose_positions(build_missions(flights, offsets))
    maxc, by_pos, conflicts = cluster_concurrency(missions)
    print('used positions:', len(used_pos))
    for p in used_pos:
        print('  pos', p)
    print('initial max concurrency:', maxc)

    # ---- 平移修复循环 ----
    # 冲突时间点按簇处理：把“非主簇”且最不紧急的架次平移
    # 简化策略：找到冲突时刻 t，选择该时刻活跃簇中任务数最少的簇，将其所有任务所属架次
    # 整体平移 delta（使其最早任务 t0 移到 t_after），直到并发<=2
    for it in range(200):
        missions, used_pos = choose_positions(build_missions(flights, offsets))
        maxc, by_pos, conflicts = cluster_concurrency(missions)
        if maxc <= 2:
            break
        # 取第一个冲突
        t_conf, pos_active = conflicts[0]
        # 选活跃簇中覆盖任务数最少的一个簇
        sizes = {p: len(by_pos[p]) for p in pos_active}
        victim = min(pos_active, key=lambda p: sizes[p])
        v_missions = by_pos[victim]
        v_t0 = min(m['t0'] for m in v_missions)
        # 平移该簇所有架次：让最晚冲突消失（平移到 conflict 结束之后）
        # 简单：每轮把该簇最早任务的架次平移 +600s
        # 选一个架次平移
        v_fids = sorted(set(m['fid'] for m in v_missions))
        shifted = False
        for fid in v_fids:
            f = next(x for x in flights if x.fid == fid)
            if offsets[fid] < 9000:
                offsets[fid] += 600
                shifted = True
                break
        if not shifted:
            print('cannot shift further')
            break
    print('after shift iterations: max concurrency:', maxc)
    for fid in sorted(offsets):
        if offsets[fid] > 0:
            print('  shift f%02d += %.0f' % (fid, offsets[fid]))

    # ---- 重新调度运输（带偏移），检查时限 ----
    for f in flights:
        f.start0 = f.start0 + offsets[f.fid]
    # 由于 dispatch 用 flight 内部顺序排序（EDF），直接重算
    schedule, _ = dispatch(data, flights)
    met = evaluate(data, flights, schedule)
    print('re-dispatch:', {k: (round(v, 1) if isinstance(v, float) else v)
                           for k, v in met.items() if k != 'box_time'})

    # ---- 中继排班：2 架中继无人机，逐簇服务 ----
    missions_final, used_pos = choose_positions(build_missions(flights, offsets))
    maxc, by_pos, conflicts = cluster_concurrency(missions_final)
    print('final concurrency:', maxc)
    relay_plan = []
    for pos, ms in by_pos.items():
        t0 = min(m['t0'] for m in ms)
        t1 = max(m['t1'] for m in ms)
        e = relay_energy_sortie(pos, t0, t1)
        relay_plan.append({'pos': pos, 't0': t0, 't1': t1, 'n': len(ms),
                           'energy': e, 'fids': sorted(set(m['fid'] for m in ms))})
    for rp in sorted(relay_plan, key=lambda x: x['t0']):
        print('relay sortie pos=%s t=[%.0f,%.0f] len=%.0f n_mission=%d energy=%.2f'
              % (rp['pos'], rp['t0'], rp['t1'], rp['t1'] - rp['t0'], rp['n'], rp['energy']))
    json.dump({'offsets': offsets, 'relay_plan': relay_plan,
               'missions': missions_final},
              open(os.path.join(OUT, 'p3_co.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


from core import direct_ok

if __name__ == '__main__':
    main()