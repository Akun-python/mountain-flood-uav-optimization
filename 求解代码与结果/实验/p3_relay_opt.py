# -*- coding: utf-8 -*-
"""
P3 中继覆盖-能耗联合优化：在"零覆盖缺口 + 回程可行"约束下，
为三班中继（W/E/N）搜索使中继总能耗最低的布设位置。
思路：对每个中继组，在其局域网格上枚举位置，统计该组归属区的未覆盖采样数，
选出"零缺口且 backhaul 可行"中 relay_mission_energy 最小的位置。
"""
import sys, os, json, math, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (Data, direct_ok, relay_link_ok, relay_backhaul_ok,
                  relay_mission_energy)
from p3_gaps import flight_trajectory
from p2_solve import Flight

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v10')

POS0 = {'W': (109.2103, 23.047134, 676.5),
        'E': (109.270017, 23.019401, 842.3),   # 当前：东点已上调 300 m
        'N': (109.238171, 23.077841, 496.1)}
AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'
# 服务时长（s）= 当前中继窗口，与论文一致
SERVE = {'W': 7083.0, 'E': 2725.0, 'N': 2945.0}

data = None


def build_samples():
    """读冠军方案 + p3_co2 偏移，沿航线 30m 采样需中继点。"""
    p2 = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
    flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
               for fj in p2['flights']]
    base = {fj['fid']: float(fj['start']) for fj in p2['flights']}
    off = {}
    off_p = os.path.join(RES, 'p3_co2.json')
    if os.path.exists(off_p):
        r3 = json.load(open(off_p, encoding='utf-8'))
        off = {int(k): float(v) for k, v in r3.get('offsets', {}).items()}
    samples = []
    for f in flights:
        s0 = base[f.fid] + off.get(f.fid, 0.0)
        pts, _ = flight_trajectory(f, s0)
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            sid = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                              data.areas[s]['lon'], data.areas[s]['lat']))
            samples.append({'fid': f.fid, 't': pt['t'], 'sid': sid,
                            'lon': pt['lon'], 'lat': pt['lat'], 'z': pt['z']})
    by_g = {g: [s for s in samples if AREA_POS.get(s['sid']) == g] for g in 'WEN'}
    return samples, by_g


def gap_of_group(g, pos, by_g):
    """该组归属区样本中，pos 无法接入的采样数。"""
    n = 0
    for s in by_g[g]:
        if not relay_link_ok(s['lon'], s['lat'], s['z'], pos, data):
            n += 1
    return n


def optimize_group(g, pos, by_g):
    """局域网格搜索：零缺口 + backhaul 可行，取能耗最小。返回 (best_pos, best_e, best_gap)。"""
    bx, by_, bz = pos
    coslat = math.cos(math.radians(by_))
    best = None
    for dlon in (-0.012, -0.008, -0.004, 0, 0.004, 0.008, 0.012):
        for dlat in (-0.012, -0.008, -0.004, 0, 0.004, 0.008, 0.012):
            for z in (450, 550, 650, 750, 850, 950, 1050, 1150):
                cand = (bx + dlon, by_ + dlat, z)
                gap = gap_of_group(g, cand, by_g)
                if gap > 0:
                    continue
                if not relay_backhaul_ok(cand, data):
                    continue
                e = relay_mission_energy(cand[0], cand[1], cand[2], data, SERVE[g])
                if best is None or e < best[0]:
                    best = (e, cand, gap)
    return best


def main():
    global data
    data = Data()
    samples, by_g = build_samples()
    print('need-relay samples:', len(samples))
    for g in 'WEN':
        print('  group %s samples=%d' % (g, len(by_g[g])))
    # 当前状态（E 已上调 300m 的修复版）
    cur_gap = 0
    cur_e = sum(relay_mission_energy(*POS0[g], data, SERVE[g]) for g in 'WEN')
    print('current (E+300m): total_e=%.3f kWh' % cur_e)
    out = {'current': {'pos': POS0, 'energy': round(cur_e, 3)},
           'optimized': {}}
    total_new = 0.0
    for g in ('W', 'E', 'N'):
        r = optimize_group(g, POS0[g], by_g)
        if r is None:
            print('  %s: no zero-gap feasible position found' % g)
            continue
        e, cand, gap = r
        total_new += e
        print('  %s -> %s gap=%d e=%.3f kWh (was %.3f)'
              % (g, tuple(round(x, 3) for x in cand), gap, e,
                 relay_mission_energy(*POS0[g], data, SERVE[g])))
        out['optimized'][g] = {'pos': cand, 'gap': gap, 'energy': round(e, 3),
                               'backhaul': bool(relay_backhaul_ok(cand, data))}
    out['optimized']['total_energy'] = round(total_new, 3)
    print('optimized total: %.3f kWh (current %.3f, saving %.3f)'
          % (total_new, cur_e, cur_e - total_new))
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'p3_relay_opt.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('saved', os.path.join(OUTD, 'p3_relay_opt.json'))


if __name__ == '__main__':
    main()