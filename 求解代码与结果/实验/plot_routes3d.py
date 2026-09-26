# -*- coding: utf-8 -*-
"""v42-σ3：三维航线图批量生成（论文级）——地形底图 + 航点序列 + 分段连线 + 统一视角。
图集：
  routes3d_all   全部 25 架次 + DEM 地形 + 站点标注
  routes3d_model A/B/C 机型分图（1×3 子图，统一视角）
  routes3d_key   C 满载链 + B 满载链特写
  routes3d_alt   高度剖面（里程-海拔，含爬升/巡航/下降相位着色）
输出 求解代码与结果/figures/。"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
for _f in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf',
           'C:/Windows/Fonts/simsun.ttc'):
    if os.path.exists(_f):
        font_manager.fontManager.addfont(_f)
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=_f).get_name()
        break
plt.rcParams['axes.unicode_minus'] = False
from mpl_toolkits.mplot3d import Axes3D  # noqa
from core import Data, node_positions

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
FIG = os.path.join(HERE, '..', 'figures')
os.makedirs(FIG, exist_ok=True)

data = Data()
BASE = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
FL = [f for f in BASE['flights']]
MODEL_COLOR = {'A': '#1f77b4', 'B': '#ff7f0e', 'C': '#d62728'}
PHASE_COLOR = {'climb': '#2ca02c', 'cruise': '#1f77b4', 'descent': '#d62728',
               'prep': '#999999'}
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
    z = dem[::step, ::step]                      # (H', W')
    x, y = to_xy(lon2[None, :], lat2[:, None])   # (H', W') 广播
    return x, y, z

def flight_waypoints(f):
    """架次航点 (x, y, z, phase)：O→区(alt+30)→O，10s 采样。"""
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
    ax.scatter([x0], [y0], [o['alt']], marker='*', s=220, c='#111111', zorder=20,
               label='调度中心 O01')
    ax.text(x0 + 60, y0 + 60, o['alt'] + 30, 'O01', fontsize=8, color='#111111',
            weight='bold', zorder=25)
    for s in sorted(data.areas):
        a = data.areas[s]
        x, y = to_xy(a['lon'], a['lat'])
        ax.scatter([x], [y], [a['alt'] + 30], marker='o', s=26, c='#111111',
                   edgecolors='white', linewidths=0.4, zorder=18)
        ax.text(x + 40, y + 40, a['alt'] + 60, s, fontsize=6.5, color='#333333',
                zorder=19)

def plot_flight(ax, f, alpha=1.0, lw=1.9, color=None, label=None, zoff=25.0):
    xs, ys, zs, ph = flight_waypoints(f)
    c = color or MODEL_COLOR[f.model]
    ax.plot(xs, ys, zs + zoff, c=c, alpha=alpha, lw=lw, zorder=12,
            label=label or ('%s-%02d' % (f.model, f.fid)))
    ax.scatter(xs[:1], ys[:1], zs[:1] + zoff, c=c, s=14, zorder=14)
    return xs, ys, zs

def fig_all():
    fig = plt.figure(figsize=(11, 8.6), dpi=300)
    ax = fig.add_subplot(111, projection='3d')
    x, y, z = dem_mesh(step=12)
    ax.plot_surface(x, y, z, cmap='terrain', alpha=0.26, linewidth=0,
                    antialiased=True, rstride=3, cstride=3)
    seen = set()
    for f in FL:
        lbl = 'A 型' if f['model'] == 'A' and 'A' not in seen else (
            'B 型' if f['model'] == 'B' and 'B' not in seen else (
                'C 型' if f['model'] == 'C' and 'C' not in seen else None))
        if lbl:
            seen.add(f['model'])
        plot_flight(ax, Flight_(f), color=MODEL_COLOR[f['model']], label=lbl)
    plot_sites(ax)
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    style_ax(ax, '无人机运输三维航线总图（25 架次 · 地形 DEM 底图）')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'routes3d_all.png'), dpi=300)
    fig.savefig(os.path.join(FIG, 'routes3d_all.pdf'))
    plt.close(fig)
    print('saved routes3d_all.png/pdf')

def fig_model():
    fig = plt.figure(figsize=(15, 5.4), dpi=300)
    for i, m in enumerate('ABC'):
        ax = fig.add_subplot(1, 3, i + 1, projection='3d')
        x, y, z = dem_mesh(step=14)
        ax.plot_surface(x, y, z, cmap='terrain', alpha=0.26, linewidth=0,
                        antialiased=True, rstride=3, cstride=3)
        for f in FL:
            if f['model'] == m:
                plot_flight(ax, Flight_(f))
        plot_sites(ax)
        style_ax(ax, '%s 型（%d 架次）' % (m, sum(1 for f in FL if f['model'] == m)))
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'routes3d_model.png'), dpi=300)
    fig.savefig(os.path.join(FIG, 'routes3d_model.pdf'))
    plt.close(fig)
    print('saved routes3d_model.png/pdf')

def fig_key():
    """C 型满载链（S001×2 / S002 / S003）与 B 型满载链（S002→S012→S015→S009）特写。"""
    C_ids = set(); B_ids = set()
    for f in FL:
        if f['model'] == 'C':
            C_ids.add(f['fid'])
        if f['model'] == 'B' and f['start'] < 100:
            B_ids.add(f['fid'])
    fig = plt.figure(figsize=(11, 8.6), dpi=300)
    ax = fig.add_subplot(111, projection='3d')
    x, y, z = dem_mesh(step=12)
    ax.plot_surface(x, y, z, cmap='terrain', alpha=0.26, linewidth=0,
                    antialiased=True, rstride=3, cstride=3)
    for f in FL:
        if f['fid'] in C_ids:
            plot_flight(ax, Flight_(f), color='#d62728', lw=1.5, alpha=1.0,
                        label='C 型满载' if f['fid'] == min(C_ids) else None)
    for f in FL:
        if f['fid'] in B_ids:
            plot_flight(ax, Flight_(f), color='#ff7f0e', lw=1.5, alpha=1.0,
                        label='B 型满载链' if f['fid'] == min(B_ids) else None)
    plot_sites(ax)
    ax.legend(loc='upper right', fontsize=8)
    style_ax(ax, '满载长链特写：C 型重区满载（S001×2/S002/S003）与 B 型四趟链')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'routes3d_key.png'), dpi=300)
    fig.savefig(os.path.join(FIG, 'routes3d_key.pdf'))
    plt.close(fig)
    print('saved routes3d_key.png/pdf')

def fig_altitude():
    """高度剖面：里程-海拔折线（按相位着色），4 个代表性架次。"""
    pick = []
    for f in FL:
        if f['model'] == 'C' and 'S003' in [s for s, _ in f['route']] and len(pick) < 1:
            pick.append(f)
        if f['model'] == 'B' and f['start'] < 100 and len([p for p in pick if p['model'] == 'B']) < 1:
            pick.append(f)
        if f['model'] == 'A' and len([p for p in pick if p['model'] == 'A']) < 1:
            pick.append(f)
    pick = pick[:3]
    fig, axes = plt.subplots(len(pick), 1, figsize=(9, 3.2 * len(pick)), dpi=300)
    if len(pick) == 1:
        axes = [axes]
    for ax, f in zip(axes, pick):
        xs, ys, zs, ph = flight_waypoints(Flight_(f))
        dist = np.hstack([0, np.cumsum(np.hypot(np.diff(xs), np.diff(ys)))])
        for k in range(len(dist) - 1):
            ax.plot([dist[k], dist[k + 1]], [zs[k], zs[k + 1]],
                    c=PHASE_COLOR[ph[k]], lw=1.4)
        ax.set_title('%s-%02d  %s  →  %s  （%.1f km / %.0f m 海拔）' % (
            f['model'], f['fid'],
            'O01', ' → '.join([s for s, _ in f['route']]) + ' → O01',
            dist[-1] / 1000, np.nanmax(zs)), fontsize=9)
        ax.set_ylabel('海拔 (m)', fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel('水平里程 (m)', fontsize=8)
    from matplotlib.patches import Patch
    axes[0].legend(handles=[Patch(color=PHASE_COLOR['climb'], label='爬升'),
                            Patch(color=PHASE_COLOR['cruise'], label='巡航'),
                            Patch(color=PHASE_COLOR['descent'], label='下降')],
                   fontsize=7, loc='upper right', ncol=3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'routes3d_alt.png'), dpi=300)
    fig.savefig(os.path.join(FIG, 'routes3d_alt.pdf'))
    plt.close(fig)
    print('saved routes3d_alt.png/pdf')

def Flight_(d):
    """把结果 JSON 的架次转为 Flight 对象（惰性 import 避免循环）。"""
    from p2_solve import Flight
    return Flight(d['fid'], [(s, list(b)) for s, b in d['route']], d['model'], data)

if __name__ == '__main__':
    fig_all()
    fig_model()
    fig_key()
    fig_altitude()
