# -*- coding: utf-8 -*-
"""v125：P1 系列图 Nature 级重绘（样式统一升级，数据不变）。
p1_map / p1_dem_map / p1_alt_profiles / p1_lg_curve / p1_qstar / p1_soc /
p1_sensitivity / p1_tradeoff。输出到论文 figures/（PNG + PDF 双格式）。"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.join('求解代码与结果', '代码'))
sys.path.insert(0, os.path.join('求解代码与结果', '实验'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import nature_style as ns
from core import Data, flight_profile

FIG = 'figures'
os.makedirs(FIG, exist_ok=True)
data = Data()
RES = os.path.join('求解代码与结果', '结果', '进化_v25')
r = json.load(open(os.path.join('求解代码与结果', '结果', 'p1_results.json'), encoding='utf-8'))


# ---------- 1) p1_map：研究区域 DEM 底图 ----------
def fig_map():
    lons = [data.centers['O01']['lon']] + [a['lon'] for a in data.areas.values()]
    lats = [data.centers['O01']['lat']] + [a['lat'] for a in data.areas.values()]
    lon_lo, lon_hi = min(lons) - 0.02, max(lons) + 0.02
    lat_lo, lat_hi = min(lats) - 0.02, max(lats) + 0.02
    c0 = int((lon_lo - data.dem_lon_min) / data.dem_res)
    c1 = int((lon_hi - data.dem_lon_min) / data.dem_res)
    r0 = int((data.dem_lat_max - lat_hi) / data.dem_res)
    r1 = int((data.dem_lat_max - lat_lo) / data.dem_res)
    dem = data.dem[r0:r1 + 1, c0:c1 + 1]
    lon_grid = data.dem_lon_min + (np.arange(c0, c1 + 1) + 0.5) * data.dem_res
    lat_grid = data.dem_lat_max - (np.arange(r0, r1 + 1) + 0.5) * data.dem_res
    X, Y = np.meshgrid(lon_grid, lat_grid)
    fig, ax = plt.subplots(figsize=(9.2, 7.4))
    im = ax.pcolormesh(X, Y, dem, cmap='terrain', shading='auto', vmin=50, vmax=800)
    cb = fig.colorbar(im, ax=ax, shrink=0.9, pad=0.02)
    cb.set_label('地面高程（m）', fontsize=10)
    o = data.centers['O01']
    ax.scatter([o['lon']], [o['lat']], marker='*', s=300, color=ns.C_HERO,
               edgecolor='white', linewidth=0.8, zorder=6, label='调度中心 O01')
    for sid in sorted(data.areas):
        a = data.areas[sid]
        ax.scatter([a['lon']], [a['lat']], s=26, color=ns.C_TEXT,
                   edgecolor='white', linewidth=0.5, zorder=5)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points',
                    xytext=(4, 3), fontsize=8, color=ns.C_TEXT)
    ax.set_xlabel('经度（°E）')
    ax.set_ylabel('纬度（°N）')
    ax.legend(loc='lower right', frameon=False, fontsize=9)
    ns.save(fig, 'p1_map')


# ---------- 2) p1_dem_map：地形 + 服务区 + 中继 ----------
def dem_geo():
    lon_min = data.dem_lon_min
    lat_max = data.dem_lat_max
    H, W = data.dem.shape
    return data.dem, (lon_min, lon_min + W * data.dem_res,
                      lat_max - H * data.dem_res, lat_max)


def fig_dem_map():
    POS = {'W': (109.2103, 23.047134, 676.5),
           'E': (109.276017, 23.019401, 542.3),
           'N': (109.238171, 23.077841, 496.1)}
    POS_LABEL = {'W': '西点中继', 'E': '东点中继', 'N': '北点中继'}
    dem, ext = dem_geo()
    vmax = np.nanpercentile(dem, 97)
    fig, ax = plt.subplots(figsize=(10.2, 7.2))
    ax.imshow(dem, extent=ext, origin='upper', cmap='terrain', vmin=0, vmax=vmax,
              interpolation='bilinear', alpha=0.92)
    cs = ax.contour(dem, levels=np.arange(50, 900, 50), extent=ext, origin='upper',
                    colors='#555555', linewidths=0.35, alpha=0.45)
    ax.set_aspect(1.0 / np.cos(np.radians(data.lat0)))
    for sid, a in data.areas.items():
        ax.scatter([a['lon']], [a['lat']], s=60, color='white', edgecolor='#222222',
                   linewidth=1.0, zorder=5)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points',
                    xytext=(6, 6), fontsize=8.2, zorder=6)
    o = data.centers['O01']
    ax.scatter([o['lon']], [o['lat']], marker='*', s=380, color=ns.C_HERO,
               edgecolor='white', linewidth=0.8, zorder=7)
    ax.annotate('O01 调度中心', (o['lon'], o['lat']), textcoords='offset points',
                xytext=(10, -22), fontsize=9.5, fontweight='bold', zorder=7)
    for g, (lo, la, zz) in POS.items():
        ax.scatter([lo], [la], marker='^', s=170, color=ns.AREA_COLORS[g],
                   edgecolor='#222222', linewidth=0.9, zorder=6)
        ax.annotate(POS_LABEL[g], (lo, la), textcoords='offset points',
                    xytext=(10, 2), fontsize=9, zorder=6)
    ax.set_xlabel('经度（°E）')
    ax.set_ylabel('纬度（°N）')
    ax.legend(handles=[Patch(color=ns.C_HERO, label='调度中心 O01'),
                       Patch(color='white', edgecolor='#222222', label='服务区'),
                       Patch(color=ns.C_W, label='西点中继'),
                       Patch(color=ns.C_E, label='东点中继'),
                       Patch(color=ns.C_N, label='北点中继')],
              loc='lower left', fontsize=9, framealpha=0.92)
    ns.save(fig, 'p1_dem_map')


# ---------- 3) p1_alt_profiles：典型航线高程剖面 ----------
def fig_alt_profiles():
    o = data.centers['O01']
    routes = [('S001', 154.0), ('S004', 59.0), ('S012', 38.0), ('S008', 55.0)]
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 6.4))
    for ax, (sid, _m) in zip(axes.ravel(), routes):
        a = data.areas[sid]
        n = 240
        lons = np.linspace(o['lon'], a['lon'], n)
        lats = np.linspace(o['lat'], a['lat'], n)
        z = data.dem_at_many(lons, lats)
        zmax = np.nanmax(z)
        t = np.sqrt((lons - o['lon']) ** 2 + (lats - o['lat']) ** 2)
        t = t / t[-1] * 1.0
        ax.fill_between(t, 0, z, color='#D9C9A3', alpha=0.85, zorder=2)
        ax.plot(t, z, color='#8B7355', lw=1.0, zorder=3)
        ax.axhline(zmax + 50, color=ns.C_A, ls='--', lw=1.2, zorder=4)
        ax.axhline(a['alt'] + 30, color=ns.C_B, ls=':', lw=1.0, zorder=4)
        ax.annotate('巡航高度 %d m' % (zmax + 50), (0.5, zmax + 50),
                    xytext=(0.04, 0.86), textcoords='axes fraction',
                    fontsize=8.4, color=ns.C_TEXT)
        ax.text(0.02, 0.12, '%s（地面 %d m，装载 %d kg）' % (sid, a['alt'], _m),
                transform=ax.transAxes, fontsize=8.6)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, zmax * 1.35 + 60)
        ax.set_xlabel('航程归一化位置')
        ax.set_ylabel('海拔（m）')
    fig.tight_layout()
    ns.save(fig, 'p1_alt_profiles')


# ---------- 4) p1_lg_curve：等效航程与能量约束 ----------
def fig_lg_curve():
    qs = np.linspace(0.1, 1.0, 300)
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(10.2, 4.3),
                                   gridspec_kw={'width_ratios': [1, 1.25]})
    for g in ('A', 'B', 'C'):
        p = data.uav_types[g]
        q = qs * p['Q']
        lg = p['L0'] - (p['L0'] - p['LF']) * (q / p['Q']) ** 1.5
        axL.plot(q, lg, color=ns.MODEL_COLORS[g], lw=2.2,
                 label='%s 型，L0=%.0f m' % (g, p['L0']))
        axL.fill_between(q, lg, p['L0'], color=ns.MODEL_COLORS[g], alpha=0.08)
    axL.axvline(25, color=ns.C_A, ls=':', lw=0.9, alpha=0.7)
    axL.axvline(30, color=ns.C_B, ls=':', lw=0.9, alpha=0.7)
    axL.axvline(80, color=ns.C_C, ls=':', lw=0.9, alpha=0.7)
    axL.set_xlabel('载荷 q（kg）')
    axL.set_ylabel('等效航程 $L_g(q)$（m）')
    axL.set_ylim(0, 26000)
    axL.legend(loc='lower left', frameon=False)
    sid = 'S008'
    o = data.centers[data.OID]
    a = data.areas[sid]
    z0, za = o['alt'], a['alt'] + 30.0
    nodes = [(o['lon'], o['lat'], z0),
             (a['lon'], a['lat'], za),
             (o['lon'], o['lat'], z0)]
    for g in ('A', 'B', 'C'):
        p = data.uav_types[g]
        cap = (1 - p['rho']) * p['E_use']
        qq = np.linspace(0.2, p['Q'], 400)
        ee = [flight_profile(nodes, [q, q], g, data)['energy'] for q in qq]
        axR.plot(qq, ee, color=ns.MODEL_COLORS[g], lw=2.2, label='%s 型' % g)
        axR.axhline(cap, color=ns.MODEL_COLORS[g], ls='--', lw=0.8, alpha=0.55)
        idx = np.searchsorted(ee, cap) - 1
        if 0 < idx < len(qq):
            q1, q2 = qq[idx], qq[idx + 1]
            e1, e2 = ee[idx], ee[idx + 1]
            qstar = q1 + (cap - e1) / (e2 - e1) * (q2 - q1)
            axR.scatter([qstar], [cap], s=52, color=ns.MODEL_COLORS[g], zorder=5,
                        edgecolor='white', linewidth=0.6)
            axR.annotate('q*=%.1f kg' % qstar, (qstar, cap),
                         textcoords='offset points', xytext=(6, 4),
                         fontsize=8.5, color=ns.C_TEXT)
    axR.set_xlabel('载荷 q（kg）')
    axR.set_ylabel('S008 往返能耗（kWh）')
    axR.set_xlim(0, 82)
    axR.legend(loc='upper left', frameon=False)
    fig.tight_layout()
    ns.save(fig, 'p1_lg_curve')


# ---------- 5) p1_qstar：最大安全载荷 ----------
def fig_qstar():
    sids = sorted(data.areas)
    x = np.arange(len(sids))
    w = 0.26
    caps = {'A': data.uav_types['A']['Q'], 'B': data.uav_types['B']['Q'],
            'C': data.uav_types['C']['Q']}
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    for i, g in enumerate(['A', 'B', 'C']):
        vals = [r['qstar'][g][s] for s in sids]
        ax.bar(x + (i - 1) * w, vals, w,
               label='%s 型，载重上限 %g kg' % (g, caps[g]),
               color=ns.MODEL_COLORS[g], edgecolor='white', linewidth=0.6)
    ax.axhline(80, color=ns.C_GRAY, ls='--', lw=0.9)
    ax.text(len(x) - 0.5, 81.5, 'C 型载重上限 80 kg', fontsize=8.5,
            color=ns.C_TEXT, ha='right')
    ax.set_xticks(x)
    ax.set_xticklabels(sids, fontsize=8.5)
    ax.set_xlabel('服务区')
    ax.set_ylabel('单点往返最大安全载荷 q*（kg）')
    ax.set_ylim(0, 92)
    ax.grid(axis='y')
    ax.legend(loc='upper right', ncol=3, frameon=False, fontsize=9)
    ns.save(fig, 'p1_qstar')


# ---------- 6) p1_soc：返航荷电状态 ----------
def fig_soc():
    rows = []
    for area, g in r['grouping'].items():
        for d in g['detail']:
            rows.append((d['model'], d['energy']))
    rows.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    x = np.arange(len(rows))
    soc = [1 - e / data.uav_types[m]['E_use'] for m, e in rows]
    colors = [ns.MODEL_COLORS[m] for m, _ in rows]
    ax.bar(x, [s * 100 for s in soc], color=colors, edgecolor='white', linewidth=0.5)
    ax.axhline(20, color=ns.C_C, ls='--', lw=1.2)
    ax.text(len(x) - 0.5, 21.5, '返航安全下限 20%', fontsize=8.5,
            color=ns.C_TEXT, ha='right')
    ax.set_xlabel('架次（按能耗升序）')
    ax.set_ylabel('返航荷电状态（%）')
    ax.set_ylim(0, 100)
    ax.set_xticks(range(0, len(x), 2))
    ax.set_xticklabels([str(i + 1) for i in range(0, len(x), 2)], fontsize=8.5)
    ax.grid(axis='y')
    ax.legend(handles=[Patch(color=ns.C_A, label='A 型'), Patch(color=ns.C_B, label='B 型'),
                       Patch(color=ns.C_C, label='C 型')],
              loc='upper right', frameon=False, ncol=3)
    ns.save(fig, 'p1_soc')


# ---------- 7) p1_sensitivity：安全余量灵敏度 ----------
def fig_sensitivity():
    sens = r['sensitivity']
    rhos = [float(k) for k in sens]
    flights = [sens[str(k)]['flights'] for k in rhos]
    energy = [sens[str(k)]['energy'] for k in rhos]
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.plot(rhos, flights, 'o-', color=ns.C_A, lw=2.0, ms=6, label='往返架次数')
    for xi, yi in zip(rhos, flights):
        ax.annotate(str(yi), (xi, yi), textcoords='offset points', xytext=(0, 7),
                    ha='center', fontsize=8.5, color=ns.C_TEXT)
    ax.set_xlabel('返航安全余量比例 ρ')
    ax.set_ylabel('往返架次数')
    ax.grid(axis='y')
    ax2 = ax.twinx()
    ax2.plot(rhos, energy, 's--', color=ns.C_C, lw=2.0, ms=6, label='总运输能耗（kWh）')
    ax2.set_ylabel('总运输能耗（kWh）')
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=False, ncol=2)
    ns.save(fig, 'p1_sensitivity')


# ---------- 8) p1_tradeoff：策略权衡 ----------
def fig_tradeoff():
    st = r['strategies']
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    marks = {'minflights': ('混合机型最小架次', 'o', ns.C_A),
             'onlyC': ('全部 C 型', 's', ns.C_C),
             'onlyB': ('全部 B 型', '^', ns.C_B)}
    for mode, (lab, mk, c) in marks.items():
        s = st[mode]
        ax.scatter(s['flights'], s['energy'], marker=mk, s=150, color=c, zorder=3,
                   label='%s：%d 架次 / %.1f kWh / 约 %.1f h'
                         % (lab, s['flights'], s['energy'], s['time'] / 3600))
        ax.annotate('%d 架次' % s['flights'], (s['flights'], s['energy']),
                    textcoords='offset points', xytext=(9, 5), fontsize=9,
                    color=ns.C_TEXT)
    ax.set_xlabel('往返架次数')
    ax.set_ylabel('总运输能耗（kWh）')
    ax.grid(alpha=0.4)
    ax.legend(loc='upper left', frameon=False)
    ns.save(fig, 'p1_tradeoff')


fig_map()
fig_dem_map()
fig_alt_profiles()
fig_lg_curve()
fig_qstar()
fig_soc()
fig_sensitivity()
fig_tradeoff()
print('P1 ALL DONE')