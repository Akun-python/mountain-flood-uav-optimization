# -*- coding: utf-8 -*-
"""问题一图件：q* 分组柱状图 / 策略权衡散点 / 安全裕度灵敏度 / DEM 任务地图。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import plot_style as ps
from core import Data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')
FIG = os.path.join(ROOT, 'figures')
os.makedirs(FIG, exist_ok=True)


def fig_qstar():
    data = Data()
    with open(os.path.join(RES, 'p1_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    sids = sorted(data.areas)
    x = np.arange(len(sids))
    w = 0.26
    fig, ax = plt.subplots(figsize=(9.2, 4.2))
    caps = {'A': data.uav_types['A']['Q'], 'B': data.uav_types['B']['Q'],
            'C': data.uav_types['C']['Q']}
    for i, g in enumerate(['A', 'B', 'C']):
        vals = [r['qstar'][g][s] for s in sids]
        bars = ax.bar(x + (i - 1) * w, vals, w,
                      label='%s 型，载重上限 %g kg' % (g, caps[g]),
                      color=ps.MODEL_COLORS[g], edgecolor='white', linewidth=0.6)
        # 能量受限的柱顶标注
        for xi, v, cap in zip(x + (i - 1) * w, vals, vals):
            pass
    ax.axhline(80, color='#6B7280', ls='--', lw=0.9)
    ax.text(len(x) - 0.5, 81.5, 'C 型载重上限 80 kg', fontsize=8.5, color='black', ha='right')
    ax.set_xticks(x)
    ax.set_xticklabels(sids, fontsize=8.5)
    ax.set_xlabel('服务区')
    ax.set_ylabel('单点往返最大安全载荷 q*（kg）')
    ax.set_ylim(0, 92)
    ax.grid(axis='y')
    ax.legend(loc='upper right', ncol=3, frameon=False, fontsize=9)
    fig.savefig(os.path.join(FIG, 'p1_qstar.png'))
    plt.close(fig)
    print('saved p1_qstar.png')


def fig_tradeoff():
    with open(os.path.join(RES, 'p1_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    st = r['strategies']
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    marks = {'minflights': ('混合机型最小架次', 'o', ps.C_BLUE),
             'onlyC': ('全部 C 型', 's', ps.C_RED),
             'onlyB': ('全部 B 型', '^', ps.C_ORANGE)}
    for mode, (lab, mk, c) in marks.items():
        s = st[mode]
        ax.scatter(s['flights'], s['energy'], marker=mk, s=130, color=c, zorder=3,
                   label='%s：%d 架次 / %.1f kWh / 约 %.1f h'
                         % (lab, s['flights'], s['energy'], s['time'] / 3600))
        ax.annotate('%d 架次' % s['flights'], (s['flights'], s['energy']),
                    textcoords='offset points', xytext=(9, 5), fontsize=9, color='black')
    ax.set_xlabel('往返架次数')
    ax.set_ylabel('总运输能耗（kWh）')
    ax.grid(alpha=0.4)
    ax.legend(loc='upper left', frameon=False)
    fig.savefig(os.path.join(FIG, 'p1_tradeoff.png'))
    plt.close(fig)
    print('saved p1_tradeoff.png')


def fig_sensitivity():
    with open(os.path.join(RES, 'p1_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    sens = r['sensitivity']
    rhos = [float(k) for k in sens]
    flights = [sens[str(k)]['flights'] for k in rhos]
    energy = [sens[str(k)]['energy'] for k in rhos]
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    ax.plot(rhos, flights, 'o-', color=ps.C_BLUE, lw=1.8, ms=6, label='往返架次数')
    for xi, yi in zip(rhos, flights):
        ax.annotate(str(yi), (xi, yi), textcoords='offset points', xytext=(0, 7),
                    ha='center', fontsize=8.5, color='black')
    ax.set_xlabel('返航安全余量比例 ρ')
    ax.set_ylabel('往返架次数')
    ax.tick_params(axis='y')
    ax.grid(axis='y')
    ax2 = ax.twinx()
    ax2.plot(rhos, energy, 's--', color=ps.C_RED, lw=1.8, ms=6, label='总运输能耗（kWh）')
    ax2.set_ylabel('总运输能耗（kWh）')
    ax2.tick_params(axis='y')
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=False, ncol=2)
    fig.savefig(os.path.join(FIG, 'p1_sensitivity.png'))
    plt.close(fig)
    print('saved p1_sensitivity.png')


def fig_map():
    data = Data()
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
    ax.scatter([o['lon']], [o['lat']], marker='*', s=240, color=ps.C_RED,
               edgecolor='white', linewidth=0.7, zorder=6, label='调度中心 O01')
    for sid in sorted(data.areas):
        a = data.areas[sid]
        ax.scatter([a['lon']], [a['lat']], s=22, color=ps.C_BLACK,
                   edgecolor='white', linewidth=0.5, zorder=5)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points',
                    xytext=(4, 3), fontsize=8, color='black')
    ax.set_xlabel('经度（°E）')
    ax.set_ylabel('纬度（°N）')
    ax.legend(loc='lower right', frameon=False, fontsize=9)
    fig.savefig(os.path.join(FIG, 'p1_map.png'))
    plt.close(fig)
    print('saved p1_map.png')


if __name__ == '__main__':
    fig_qstar()
    fig_tradeoff()
    fig_sensitivity()
    fig_map()
    print('p1 figures done')