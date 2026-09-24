# -*- coding: utf-8 -*-
"""问题三：通信约束下的运输+中继联合调度
步骤：
1) 读取 P2 平衡解（24 架次），展开各运输架次轨迹（爬升/巡航/下降/交接），采样 (t, lon, lat, z)
2) 逐采样点判定 直连/中继/中断；累积“需中继”时间段（通信缺口）
3) 贪心放置中继：对缺口聚类，网格搜索悬停点（回传OK+接入OK），构造中继架次服务窗
4) 中继调度：2 架中继无人机 + 6 能源组件（充放电），能量<= (1-rho)*E_use
5) 若 2 架中继无法覆盖（时间重叠），对运输架次开始时刻做平移消解
输出：Q3_中继架次表 + Q3_通信保障表 + 指标
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import (Data, direct_ok, relay_backhaul_ok, relay_link_ok, charge_time,
                  relay_mission_time, relay_mission_energy, _los_occluded, path_loss)
from p2_solve import Flight

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
os.makedirs(OUT, exist_ok=True)
data = Data()
DT = 10.0  # 采样步长


def flight_trajectory(f, start):
    """展开运输架次的 (t, lon, lat, z, phase) 采样序列。
    f: Flight; start: 准备开始时刻。"""
    pts = []
    p = data.uav_types[f.model]
    t = start + f.prep
    o = data.centers['O01']
    z0 = o['alt']
    keys = f.keys()   # ['O', sid..., 'O']
    loads = []
    rem = f.total_mass
    for k in range(len(f.route) + 1):
        loads.append(rem)
        if k < len(f.route):
            sid, bs = f.route[k]
            rem -= sum(data.boxes[b]['mass'] for b in bs)
    # 交接时长表
    hand = [p['t_hand_base'] + len(bs) * p['t_hand_box'] for _, bs in f.route]
    prof = f.profile()
    pts.append({'t': t, 'lon': o['lon'], 'lat': o['lat'], 'z': z0, 'phase': 'prep'})
    for k in range(len(keys) - 1):
        a_key, b_key = keys[k], keys[k + 1]
        leg = data.leg_table[(a_key, b_key)]
        lg = prof['legs'][k]
        if a_key == 'O':
            lon1, lat1, z1 = o['lon'], o['lat'], z0
        else:
            ar = data.areas[a_key]
            lon1, lat1, z1 = ar['lon'], ar['lat'], ar['alt'] + 30
        if b_key == 'O':
            lon2, lat2, z2 = o['lon'], o['lat'], z0
        else:
            ar = data.areas[b_key]
            lon2, lat2, z2 = ar['lon'], ar['lat'], ar['alt'] + 30
        cruise = leg['cruise']
        h_up, h_down = leg['h_up'], leg['h_down']
        # 爬升
        t_up = h_up / p['v_up']
        n = max(1, int(math.ceil(t_up / DT)))
        for i in range(1, n + 1):
            t += t_up / n
            pts.append({'t': t, 'lon': lon1, 'lat': lat1, 'z': z1 + h_up * i / n, 'phase': 'climb'})
        # 巡航
        d = leg['d']
        t_cr = d / p['v_c']
        n = max(1, int(math.ceil(t_cr / DT)))
        for i in range(1, n + 1):
            t += t_cr / n
            pts.append({'t': t, 'lon': lon1 + (lon2 - lon1) * i / n,
                        'lat': lat1 + (lat2 - lat1) * i / n, 'z': cruise, 'phase': 'cruise'})
        # 下降
        t_dn = h_down / p['v_down']
        n = max(1, int(math.ceil(t_dn / DT)))
        for i in range(1, n + 1):
            t += t_dn / n
            pts.append({'t': t, 'lon': lon2, 'lat': lat2, 'z': cruise - h_down * i / n, 'phase': 'descent'})
        # 交接
        if k < len(f.route):
            t_hand = hand[k]
            n = max(1, int(math.ceil(t_hand / DT)))
            for i in range(1, n + 1):
                t += t_hand / n
                pts.append({'t': t, 'lon': lon2, 'lat': lat2, 'z': z2, 'phase': 'handover'})
    return pts, t  # t = 回到 O01 时刻


def analyze_gaps():
    with open(os.path.join(OUT, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    flights = {}
    for fj in r['flights']:
        route = [(s, list(b)) for s, b in fj['route']]
        f = Flight(fj['fid'], route, fj['model'], data)
        flights[fj['fid']] = (f, fj)
    all_gaps = []   # {'fid', 't', 'lon', 'lat', 'z', 'phase'}
    n_direct = n_need = 0
    for fid, (f, fj) in flights.items():
        pts, tend = flight_trajectory(f, fj['start'])
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                n_direct += 1
            else:
                n_need += 1
                all_gaps.append({'fid': fid, 't': pt['t'], 'lon': pt['lon'],
                                 'lat': pt['lat'], 'z': pt['z'], 'phase': pt['phase'],
                                 'uav': fj['uav'], 'model': f.model})
    print('total samples: %d, direct: %d, need relay: %d (%.1f%%)'
          % (n_direct + n_need, n_direct, n_need, 100.0 * n_need / max(1, n_direct + n_need)))
    # 按架次分组的缺口区间
    gaps_by_flight = {}
    for g in all_gaps:
        gaps_by_flight.setdefault(g['fid'], []).append(g)
    # 打印每架次的缺口时间范围和主要位置
    for fid in sorted(gaps_by_flight):
        gs = gaps_by_flight[fid]
        ts = [g['t'] for g in gs]
        lons = [g['lon'] for g in gs]
        lats = [g['lat'] for g in gs]
        print('f%02d gaps: t=[%.0f, %.0f] len=%.0f n=%d center=(%.5f,%.5f) phases=%s'
              % (fid, min(ts), max(ts), max(ts) - min(ts), len(gs),
                 np.mean(lons), np.mean(lats), sorted(set(g['phase'] for g in gs))))
    json.dump({'gaps': all_gaps},
              open(os.path.join(OUT, 'p3_gaps.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return all_gaps, flights


def main():
    gaps, flights = analyze_gaps()
    print('total gap points:', len(gaps))


if __name__ == '__main__':
    main()