# -*- coding: utf-8 -*-
"""v124：按 24 架冠军（v113_best）重绘三维航线图集 routes3d_* 到论文 figures/。
全部 24 架次 3D 航线 + DEM 地形底图 + 站点标注；A/B/C 分图；满载链特写；高度剖面。"""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.join('求解代码与结果', '代码'))
sys.path.insert(0, os.path.join('求解代码与结果', '实验'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
for _f in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/simsun.ttc'):
    if os.path.exists(_f):
        font_manager.fontManager.addfont(_f)
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=_f).get_name()
        break
plt.rcParams['axes.unicode_minus'] = False
from mpl_toolkits.mplot3d import Axes3D  # noqa
from core import Data, node_positions
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant

FIG = 'figures'
os.makedirs(FIG, exist_ok=True)
data = Data()
d = json.load(open(os.path.join('求解代码与结果', '结果', '进化_v25', 'v113_best.json'), encoding='utf-8'))
FL = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
sch, _ = dispatch_compliant(data, FL)
print('24架 mk=%.1f' % max(sch[f.fid]['return'] for f in FL))

MODEL_COLOR = {'A': '#1f77b4', 'B': '#ff7f0e', 'C': '#d62728'}
PHASE_COLOR = {'climb': '#2ca02c', 'cruise': '#1f77b4', 'descent': '#d62728', 'prep': '#999999'}
LAT0 = data.centers[data.OID]['lat']; LON0 = data.centers[data.OID]['lon']
KX = 111320.0 * math.cos(math.radians(LAT0)); KY = 110540.0

def to_xy(lon, lat):
    return (lon - LON0) * KX, (lat - LAT0) * KY

def dem_mesh(step=9):
    dem = data.dem
    H, W = dem.shape
    lat = data.dem_lat_max - np.arange(H) * data.dem_res
    lon = data.dem_lon_min + np.arange(W) * data.dem_res
    lat2, lon2 = lat[::step], lon[::step]
    z = dem[::step, ::step]
    x, y = to_xy(lon2[None, :], lat2[:, None])
    return x, y, z

def flight_waypoints(f):
    nodes = f.area_nodes()
    pts = node_positions(nodes, None, f.model, data, dt=10.0)
    xs, ys, zs, ph = [], [], [], []
    for p in pts:
        x, y = to_xy(p['lon'], p['lat'])
        xs.append(x); ys.append(y); zs.append(p['z']); ph.append(p['phase'])
    return np.array(xs), np.array(ys), np.array(zs), ph

def style_ax(ax, title):
    ax.set_xlabel('东向距离 (m)', fontsize=9)
    ax.set_ylabel('北向距离 (m)', fontsize=9)
    ax.set_zlabel('海拔 (m)', fontsize=9)
    ax.set_title(title, fontsize=11, pad=8)
    ax.view_init(elev=38, azim=-52)
    ax.tick_params(labelsize=7)

def plot_sites(ax):
    o = data.centers[data.OID]
    x0, y0 = to_xy(o['lon'], o['lat'])
    ax.scatter([x0], [y0], [o['alt']], marker='*', s=220, c='#111111', zorder=20, label='调度中心 O01')
    ax.text(x0 + 60, y0 + 60, o['alt'] + 30, 'O01', fontsize=8, color='#111111', weight='bold', zorder=25)
    for s in sorted(data.areas):
        a = data.areas[s]
        x, y = to_xy(a['lon'], a['lat'])
        ax.scatter([x], [y], [a['alt'] + 30], marker='o', s=26, c='#111111', edgecolors='white', linewidths=0.4, zorder=18)
        ax.text(x + 40, y + 40, a['alt'] + 60, s, fontsize=6.5, color='#333333', zorder=19)

def plot_flight(ax, f, alpha=1.0, lw=1.9, color=None, label=None, zoff=25.0):
    xs, ys, zs, ph = flight_waypoints(f)
    c = color or MODEL_COLOR[f.model]
    ax.plot(xs, ys, zs + zoff, c=c, alpha=alpha, lw=lw, zorder=12, label=label or ('%s-%02d' % (f.model, f.fid)))
    ax.scatter(xs[:1], ys[:1], zs[:1] + zoff, c=c, s=14, zorder=14)
    return xs, ys, zs

def fig_all():
    fig = plt.figure(figsize=(11, 8.6), dpi=300)
    ax = fig.add_subplot(111, projection='3d')
    x, y, z = dem_mesh(step=12)
    ax.plot_surface(x, y, z, cmap='terrain', alpha=0.26, linewidth=0, antialiased=True, rstride=3, cstride=3)
    seen = set()
    for f in FL:
        lbl = 'A 型' if f.model == 'A' and 'A' not in seen else (
            'B 型' if f.model == 'B' and 'B' not in seen else (
                'C 型' if f.model == 'C' and 'C' not in seen else None))
        if lbl:
            seen.add(f.model)
        plot_flight(ax, f, color=MODEL_COLOR[f.model], label=lbl)
    plot_sites(ax)
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    style_ax(ax, '无人机运输三维航线总图（24 架次 · 地形 DEM 底图）')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'routes3d_all.png'), dpi=300)
    plt.close(fig)
    print('saved routes3d_all.png')

def fig_model():
    fig = plt.figure(figsize=(15, 5.4), dpi=300)
    for i, m in enumerate('ABC'):
        ax = fig.add_subplot(1, 3, i + 1, projection='3d')
        x, y, z = dem_mesh(step=14)
        ax.plot_surface(x, y, z, cmap='terrain', alpha=0.26, linewidth=0, antialiased=True, rstride=3, cstride=3)
        for f in FL:
            if f.model == m:
                plot_flight(ax, f)
        plot_sites(ax)
        style_ax(ax, '%s 型（%d 架次）' % (m, sum(1 for f in FL if f.model == m)))
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'routes3d_model.png'), dpi=300)
    plt.close(fig)
    print('saved routes3d_model.png')

def fig_key():
    C_ids = sorted({f.fid for f in FL if f.model == 'C'})
    B_ids = sorted({f.fid for f in FL if f.model == 'B' and sch[f.fid]['start'] < 100})
    B_chain = [66, 13, 4, 18, 15, 12, 16, 31]  # B 池 U05/U06 链条（24 架内存在者为链）
    B_chain = [fid for fid in B_chain if fid in {f.fid for f in FL}]
    fig = plt.figure(figsize=(11, 8.6), dpi=300)
    ax = fig.add_subplot(111, projection='3d')
    x, y, z = dem_mesh(step=12)
    ax.plot_surface(x, y, z, cmap='terrain', alpha=0.26, linewidth=0, antialiased=True, rstride=3, cstride=3)
    for f in FL:
        if f.fid in C_ids:
            plot_flight(ax, f, color='#d62728', lw=1.5, alpha=1.0, label='C 型满载' if f.fid == min(C_ids) else None)
    for f in FL:
        if f.fid in B_chain:
            plot_flight(ax, f, color='#ff7f0e', lw=1.5, alpha=1.0, label='B 型链条' if f.fid == min(B_chain) else None)
    plot_sites(ax)
    ax.legend(loc='upper right', fontsize=8)
    style_ax(ax, '满载长链特写：C 型 6 趟重区满载与 B 型两条机链（U05/U06）')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'routes3d_key.png'), dpi=300)
    plt.close(fig)
    print('saved routes3d_key.png')

def fig_altitude():
    pick = []
    for f in sorted(FL, key=lambda x: x.fid):
        if f.model == 'C' and 'S003' in [s for s, _ in f.route] and not any(p.model == 'C' for p in pick):
            if sch[f.fid]['start'] < 2000:
                pick.append(f)
        if f.model == 'B' and not any(p.model == 'B' for p in pick):
            pick.append(f)
        if f.model == 'A' and not any(p.model == 'A' for p in pick):
            pick.append(f)
    pick = pick[:3]
    fig, axes = plt.subplots(len(pick), 1, figsize=(9, 3.2 * len(pick)), dpi=300)
    if len(pick) == 1:
        axes = [axes]
    for ax, f in zip(axes, pick):
        xs, ys, zs, ph = flight_waypoints(f)
        dist = np.cumsum(np.sqrt(np.diff(xs, prepend=xs[0]) ** 2 + np.diff(ys, prepend=ys[0]) ** 2))
        for seg_start, seg_end in [(0, len(xs))]:
            legs = []
            for k in range(seg_start, seg_end - 1):
                legs.append((k, k + 1, ph[k + 1]))
            for k0, k1, phase in legs:
                ax.plot(dist[k0:k1 + 1], zs[k0:k1 + 1], color=PHASE_COLOR.get(phase, '#999999'), lw=1.6)
        ax.set_title('f%02d（%s 型）高度剖面' % (f.fid, f.model), fontsize=10)
        ax.set_xlabel('里程 (m)', fontsize=9); ax.set_ylabel('海拔 (m)', fontsize=9)
        ax.grid(alpha=0.35)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, p: '%d' % v))
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'routes3d_alt.png'), dpi=300)
    plt.close(fig)
    print('saved routes3d_alt.png')

fig_all()
fig_model()
fig_key()
fig_altitude()
print('ALL DONE')