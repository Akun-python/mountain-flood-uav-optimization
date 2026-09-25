# -*- coding: utf-8 -*-
"""B2 侦察：位置自由化可行性 —— 为 W/E/N 每组在 DEM 上网格搜索"单位置全覆盖"的悬停点。
只做侦察（不跑 SA）：输出每组能否被一个悬停点全覆盖 + 最优位置（覆盖数最多、其次往返时间最短）。
用法: python p3v29_relayfree_probe.py <makespan|energy>
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
import numpy as np
from core import Data, direct_ok, relay_link_ok, relay_backhaul_ok, relay_mission_time, relay_mission_energy
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant
from p3_gaps import flight_trajectory

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()
GROUPS = {
    'W': ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015'],
    'E': ['S010', 'S012', 'S013', 'S014'],
    'N': ['S004'],
}
ORIG = {'W': (109.2103, 23.047134, 676.5), 'E': (109.268918, 23.012732, 650.0),
        'N': (109.234314, 23.059248, 600.0)}


def collect_need_pts(src_json):
    d = json.load(open(os.path.join(OUTD, src_json), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d['solution']]
    sch, _ = dispatch_compliant(data, fls)
    base = {fid: sch[fid]['start'] for fid in sch}
    # 每架次轨迹采样，找需中继点并归属最近区
    by_area = {}
    for f in fls:
        pts, _ = flight_trajectory(f, base[f.fid])
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            best = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                              data.areas[s]['lon'], data.areas[s]['lat']))
            by_area.setdefault(best, []).append((pt['lon'], pt['lat'], pt['z']))
    return by_area


def search_pos(pts, center=None, rad=0.025, step=0.004, alts=(100, 150, 200, 250, 300),
               fine_rad=0.002, fine_step=0.0004):
    """在 center 周围网格搜索悬停点，使覆盖 pts 最多；全覆盖中选往返飞行时间最短。
    约束：回传 ok + dem 非 nan + 离地=alt <= 300。"""
    if not pts:
        return None, 0, len(pts)
    if center is None:
        center = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    npts = len(pts)

    def cover(lon, lat, z):
        return sum(1 for p in pts if relay_link_ok(p[0], p[1], p[2], (lon, lat, z), data))

    def feasible(lon, lat, alt):
        h = data.dem_at(lon, lat)
        if math.isnan(h):
            return None
        z = h + alt
        if alt > data.relay_type['h_max'] + 1e-6:
            return None
        if not relay_backhaul_ok((lon, lat, z), data):
            return None
        return z

    best = None
    best_cover = -1
    # 粗网格
    for _i in range(2):
        r = rad if _i == 0 else fine_rad
        st = step if _i == 0 else fine_step
        n = int(r / st)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                lon = center[0] + i * st
                lat = center[1] + j * st
                for alt in alts:
                    z = feasible(lon, lat, alt)
                    if z is None:
                        continue
                    c = cover(lon, lat, z)
                    if c > best_cover or (c == best_cover and best is not None and
                                          relay_mission_time(lon, lat, z, data)[2] < best[3]):
                        best_cover = c
                        t_out, t_back, tt = relay_mission_time(lon, lat, z, data)
                        best = (lon, lat, z, tt, c)
    return best, best_cover, npts


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else 'makespan'
    src = 'p2v28_compliant_makespan.json' if tag == 'makespan' else 'p2v28d_compliant_energy.json'
    by_area = collect_need_pts(src)
    print('需中继采样点按区: ' + ', '.join('%s=%d' % (s, len(v)) for s, v in sorted(by_area.items())))
    out = {'src': src}
    for g, areas in GROUPS.items():
        pts = []
        for s in areas:
            pts.extend(by_area.get(s, []))
        print('\n组 %s: 区 %s, 需中继点 %d' % (g, areas, len(pts)))
        if not pts:
            continue
        # 先看原位置覆盖
        c0 = sum(1 for p in pts if relay_link_ok(p[0], p[1], p[2], ORIG[g], data))
        best, bc, npts = search_pos(pts)
        print('  原位置覆盖: %d/%d' % (c0, npts))
        if best is None:
            print('  搜索失败（无可行业态位置）')
            out[g] = {'orig_cov': c0, 'n': npts, 'best': None}
            continue
        lon, lat, z, tt, c = best
        h = data.dem_at(lon, lat)
        print('  新位置: (%.6f, %.6f, z=%.1f) 离地=%.0f m 覆盖 %d/%d 往返飞行 %.0f s' % (
            lon, lat, z, z - h, c, npts, tt))
        out[g] = {'orig_cov': c0, 'n': npts, 'best': (round(lon, 6), round(lat, 6), round(z, 1)),
                  'ground': round(h, 1), 'alt_agl': round(z - h, 1), 'cov': c, 'roundtrip': round(tt, 1)}
    json.dump(out, open(os.path.join(OUTD, 'p3v29_probe_%s.json' % tag), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\nsaved -> 结果/进化_v25/p3v29_probe_%s.json' % tag)


if __name__ == '__main__':
    main()