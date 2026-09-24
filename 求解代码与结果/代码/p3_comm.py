# -*- coding: utf-8 -*-
"""问题三通信分析：直连覆盖图、各航段/交接点直连状态、中继候选点搜索。"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import Data, direct_ok, relay_backhaul_ok, relay_link_ok, path_loss

data = Data()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
os.makedirs(OUT, exist_ok=True)

print('=== 交接点（服务区 30m 高度）直连状态 ===')
area_direct = {}
for sid in sorted(data.areas):
    a = data.areas[sid]
    z = a['alt'] + 30
    ok = direct_ok(a['lon'], a['lat'], z, data)
    area_direct[sid] = ok
    print('%-4s alt=%6.1f direct=%s' % (sid, z, ok))

print('\n=== 航段巡航直连状态（O01→Si→O01）===')
leg_direct = {}
for sid in sorted(data.areas):
    a = data.areas[sid]
    o = data.centers['O01']
    leg = data.leg_table[('O', sid)]
    cruise = leg['cruise']
    # 巡航中点
    lon_m = (o['lon'] + a['lon']) / 2
    lat_m = (o['lat'] + a['lat']) / 2
    ok_mid = direct_ok(lon_m, lat_m, cruise, data)
    # 两个端点上方巡航
    ok_o = direct_ok(o['lon'], o['lat'], cruise, data)
    ok_s = direct_ok(a['lon'], a['lat'], cruise, data)
    leg_direct[sid] = (ok_o, ok_mid, ok_s)
    print('%-4s cruise=%6.1f direct(O,mid,S)=%s' % (sid, cruise, (ok_o, ok_mid, ok_s)))

# 网关回传可达性：对候选中继点
print('\n=== 中继候选：O01 周边 4km 网格，高度 = 地形+[100,200,300]，回传可用性 ===')
gw = data.gw_pt
# 以 O01 为中心
lon0, lat0 = data.centers['O01']['lon'], data.centers['O01']['lat']
count = 0
cands = []
for dlon in np.arange(-0.045, 0.046, 0.006):     # ~0.6km 步长
    for dlat in np.arange(-0.045, 0.046, 0.006):
        lon, lat = lon0 + dlon, lat0 + dlat
        z_g = data.dem_at(lon, lat)
        if math.isnan(z_g):
            continue
        for dz in [100, 200, 300]:
            z = z_g + dz
            if relay_backhaul_ok((lon, lat, z), data):
                cands.append((lon, lat, z))
                count += 1
print('backhaul-OK candidate points:', count)

# 每个服务区交接点，找能同时满足 回传+接入 的中继候选（哪个中继点可以覆盖这个交接点）
print('\n=== 各交接点可用的中继候选数（回传OK且接入OK）===')
for sid in sorted(data.areas):
    a = data.areas[sid]
    z = a['alt'] + 30
    n = 0
    best = None
    best_d = 1e18
    for (lon, lat, rz) in cands:
        if relay_link_ok(a['lon'], a['lat'], z, (lon, lat, rz), data):
            n += 1
            d = data.dist_ll(a['lon'], a['lat'], lon, lat)
            if d < best_d:
                best_d = d
                best = (lon, lat, rz, d)
    print('%-4s n_cand=%3d best=(%.5f,%.5f,z=%.0f,d=%.0fm)' % (sid, n, *((best[0], best[1], best[2], best[3]) if best else (0,0,0,0))))

json.dump({'area_direct': {k: bool(v) for k, v in area_direct.items()},
           'leg_direct': {k: [bool(x) for x in v] for k, v in leg_direct.items()}},
          open(os.path.join(OUT, 'p3_comm_analysis.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\nsaved p3_comm_analysis.json')