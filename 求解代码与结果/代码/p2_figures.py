# -*- coding: utf-8 -*-
"""问题二图件：运输甘特图 / 路线图 / 交付时刻与时限对照。"""
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


def fig_gantt():
    with open(os.path.join(RES, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    fl = sorted(r['flights'], key=lambda x: (x['uav'], x['start']))
    uavs = sorted(set(f['uav'] for f in fl))
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    for i, u in enumerate(uavs):
        for f in [x for x in fl if x['uav'] == u]:
            ax.barh(i, f['return'] - f['start'], left=f['start'], height=0.62,
                    color=ps.MODEL_COLORS[f['model']], edgecolor='white',
                    linewidth=0.4, zorder=3)
            ax.text(f['start'] + 90, i , 'F%02d' % f['fid'], fontsize=6.5,
                    color='black', va='center', zorder=4)
    ax.axvline(r['metrics']['makespan'], color=ps.C_RED, ls='--', lw=1.0)
    ax.text(r['metrics']['makespan'] - 60, len(uavs) - 0.35, '完成 %d s' % r['metrics']['makespan'],
            color='black', fontsize=9, ha='right')
    ax.set_yticks(range(len(uavs)))
    ax.set_yticklabels(uavs)
    ax.set_xlabel('时刻（s）')
    ax.set_xlim(0, r['metrics']['makespan'] * 1.03)
    ax.grid(axis='x')
    handles = [Patch(color=ps.C_BLUE, label='A 型'), Patch(color=ps.C_ORANGE, label='B 型'),
               Patch(color=ps.C_RED, label='C 型')]
    ax.legend(handles=handles, loc='upper right', frameon=False, ncol=3, fontsize=9)
    fig.savefig(os.path.join(FIG, 'p2_gantt.png'))
    plt.close(fig)
    print('saved p2_gantt.png')


def fig_routes():
    data = Data()
    with open(os.path.join(RES, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    lons = [data.centers['O01']['lon']] + [a['lon'] for a in data.areas.values()]
    lats = [data.centers['O01']['lat']] + [a['lat'] for a in data.areas.values()]
    lon_lo, lon_hi = min(lons) - 0.012, max(lons) + 0.012
    lat_lo, lat_hi = min(lats) - 0.012, max(lats) + 0.012
    c0 = int((lon_lo - data.dem_lon_min) / data.dem_res)
    c1 = int((lon_hi - data.dem_lon_min) / data.dem_res)
    r0 = int((data.dem_lat_max - lat_hi) / data.dem_res)
    r1 = int((data.dem_lat_max - lat_lo) / data.dem_res)
    dem = data.dem[r0:r1 + 1, c0:c1 + 1]
    lon_grid = data.dem_lon_min + (np.arange(c0, c1 + 1) + 0.5) * data.dem_res
    lat_grid = data.dem_lat_max - (np.arange(r0, r1 + 1) + 0.5) * data.dem_res
    X, Y = np.meshgrid(lon_grid, lat_grid)
    fig, ax = plt.subplots(figsize=(8.6, 7.6))
    ax.pcolormesh(X, Y, dem, cmap='terrain', shading='auto', vmin=50, vmax=800)
    o = data.centers['O01']
    ax.scatter([o['lon']], [o['lat']], marker='*', s=220, color=ps.C_RED,
               edgecolor='white', linewidth=0.7, zorder=6)
    for sid in sorted(data.areas):
        a = data.areas[sid]
        ax.scatter([a['lon']], [a['lat']], s=20, color=ps.C_BLACK,
                   edgecolor='white', linewidth=0.5, zorder=5)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points',
                    xytext=(4, 2), fontsize=7.5, zorder=6)
    # 按机型着色的航线集合
    for m, c in [('A', ps.C_BLUE), ('B', ps.C_ORANGE), ('C', ps.C_RED)]:
        xs, ys = [], []
        for f in r['flights']:
            if f['model'] != m:
                continue
            leg = [o['lon']]
            latl = [o['lat']]
            for sid, _ in f['route']:
                a = data.areas[sid]
                leg.append(a['lon']); latl.append(a['lat'])
            ax.plot(leg, latl, '-', color=c, lw=1.0, alpha=0.6, zorder=4)
        if xs:
            ax.plot([], [], '-', color=c, lw=1.4)
    handles = [plt.Line2D([], [], color=ps.C_BLUE, lw=1.4, label='A 型架次'),
               plt.Line2D([], [], color=ps.C_ORANGE, lw=1.4, label='B 型架次'),
               plt.Line2D([], [], color=ps.C_RED, lw=1.4, label='C 型架次')]
    ax.legend(handles=handles, loc='lower right', frameon=False, fontsize=9)
    ax.set_xlabel('经度（°E）')
    ax.set_ylabel('纬度（°N）')
    fig.savefig(os.path.join(FIG, 'p2_routes.png'))
    plt.close(fig)
    print('saved p2_routes.png')


def fig_delivery():
    data = Data()
    with open(os.path.join(RES, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    cats = {'医疗物资': ps.C_RED, '饮用水': ps.C_BLUE, '应急食品': ps.C_ORANGE,
            '生活卫生用品': ps.C_GREEN}
    for i, (k, c) in enumerate(cats.items()):
        pts = [(d['t'], data.boxes[d['box']]['deadline_exp']) for d in r['deliveries']
               if data.boxes[d['box']]['type'] == k]
        if not pts:
            continue
        ts = np.array([p[0] for p in pts]); exps = np.array([p[1] for p in pts])
        ax.scatter(ts / 3600, np.full(len(ts), i) + 0.15, s=20, color=c, alpha=0.9,
                   zorder=3, label=k)
        ax.scatter(exps / 3600, np.full(len(exps), i) - 0.15, marker='v', s=26,
                   color='black', alpha=0.65, zorder=2)
    ax.set_yticks(range(4))
    ax.set_yticklabels(list(cats.keys()))
    ax.set_xlabel('时刻（h）')
    ax.grid(axis='x')
    from matplotlib.lines import Line2D
    ax.legend(handles=[
        Line2D([], [], marker='o', ls='', color=ps.C_BLACK, label='实际交付时刻'),
        Line2D([], [], marker='v', ls='', color=ps.C_BLACK, label='期望送达时间')],
        loc='upper right', frameon=False, fontsize=9)
    fig.savefig(os.path.join(FIG, 'p2_delivery.png'))
    plt.close(fig)
    print('saved p2_delivery.png')


if __name__ == '__main__':
    fig_gantt()
    fig_routes()
    fig_delivery()
    print('p2 figures done')