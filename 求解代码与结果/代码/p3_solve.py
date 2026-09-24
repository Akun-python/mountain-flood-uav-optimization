# -*- coding: utf-8 -*-
"""问题三求解：中继位置选择 + 中继架次构造
- 锚点法：每服务区 2 个锚点（交接点 alt+30、巡航点 alt=cruise），中继须同时覆盖
- 每架次按其服务区的缺口窗口构造“中继任务” (position, [t0, t1], flight)
- 输出 p3_missions.json 供调度阶段使用
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import (Data, direct_ok, relay_backhaul_ok, relay_link_ok, charge_time,
                  relay_mission_time, relay_mission_energy, path_loss)
from p3_gaps import analyze_gaps

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = Data()


def build_candidates():
    cands = []
    areas = list(data.areas.values())
    lons = [data.centers['O01']['lon']] + [a['lon'] for a in areas]
    lats = [data.centers['O01']['lat']] + [a['lat'] for a in areas]
    lon_lo, lon_hi = min(lons) - 0.03, max(lons) + 0.03
    lat_lo, lat_hi = min(lats) - 0.03, max(lats) + 0.03
    seen = set()
    for lon in np.arange(lon_lo, lon_hi + 1e-9, 0.006):
        for lat in np.arange(lat_lo, lat_hi + 1e-9, 0.006):
            zg = data.dem_at(lon, lat)
            if math.isnan(zg):
                continue
            for dz in (120, 220, 300):
                z = zg + dz
                c = (round(lon, 6), round(lat, 6), round(z, 1))
                if c not in seen and relay_backhaul_ok(c, data):
                    seen.add(c)
                    cands.append(c)
    for a in areas:
        for dlon in np.arange(-0.021, 0.022, 0.003):
            for dlat in np.arange(-0.021, 0.022, 0.003):
                lon, lat = a['lon'] + dlon, a['lat'] + dlat
                zg = data.dem_at(lon, lat)
                if math.isnan(zg):
                    continue
                for dz in (120, 220, 300):
                    z = zg + dz
                    c = (round(lon, 6), round(lat, 6), round(z, 1))
                    if c not in seen and relay_backhaul_ok(c, data):
                        seen.add(c)
                        cands.append(c)
    return cands


def area_anchors(sid):
    """服务区 2 个锚点。"""
    a = data.areas[sid]
    cruise = max(data.leg_table[('O', sid)]['cruise'], data.leg_table[(sid, 'O')]['cruise'])
    return [(a['lon'], a['lat'], a['alt'] + 30, 'handover'),
            (a['lon'], a['lat'], cruise, 'cruise')]


def area_candidates(sid, cands):
    """覆盖该服务区两个锚点的候选位置。"""
    anchors = area_anchors(sid)
    out = []
    for c in cands:
        ok = all(relay_link_ok(an[0], an[1], an[2], c, data) for an in anchors)
        if ok:
            out.append(c)
    return out


def main():
    gaps, flights = analyze_gaps()
    cands = build_candidates()
    print('candidates:', len(cands))
    area_cov = {}
    for sid in sorted(data.areas):
        cov = area_candidates(sid, cands)
        area_cov[sid] = cov
        print('%-4s anchor-covering candidates: %d' % (sid, len(cov)))
    json.dump({'cands': cands, 'area_cov': {k: v for k, v in area_cov.items()}},
              open(os.path.join(OUT, 'p3_cov.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # 每架次：按服务区聚合缺口窗口
    by_flight = {}
    for g in gaps:
        by_flight.setdefault(g['fid'], []).append(g)

    # 求每个缺口采样点到最近服务区的归属
    area_pos = {sid: (data.areas[sid]['lon'], data.areas[sid]['lat']) for sid in data.areas}

    missions = []
    for fid, gs in sorted(by_flight.items()):
        # 按最近服务区分组
        groups = {}
        for g in gs:
            best = min(area_pos, key=lambda s: data.dist_ll(g['lon'], g['lat'], *area_pos[s]))
            groups.setdefault(best, []).append(g)
        for sid, sgs in groups.items():
            ts = [g['t'] for g in sgs]
            cov = area_cov.get(sid, [])
            if not cov:
                # 退化为任意可覆盖点的中继
                print('WARN fid=%d area=%s no anchor-covering candidate' % (fid, sid))
                continue
            missions.append({
                'fid': fid, 'area': sid,
                't0': min(ts), 't1': max(ts),
                'n': len(sgs),
                'pos_cands': [list(c) for c in cov[:20]],
            })
    print('\nmissions built:', len(missions))
    for m in sorted(missions, key=lambda x: x['t0']):
        print('f%02d %s t=[%6.0f, %6.0f] len=%5.0f cands=%d'
              % (m['fid'], m['area'], m['t0'], m['t1'], m['t1'] - m['t0'], len(m['pos_cands'])))
    json.dump(missions, open(os.path.join(OUT, 'p3_missions.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()