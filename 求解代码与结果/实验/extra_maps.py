# -*- coding: utf-8 -*-
"""论文增强图件：研究区地形总览地图 / 典型航线 DEM 高程剖面 /
中继覆盖归属地图 / 架次能耗构成 / 无人机电池 SOC 曲线。
输出到 求解代码与结果/figures/（与 advanced_figures 同目录）。"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plot_style as ps
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from core import Data, direct_ok, charge_time
from p2_solve import Flight
from p3_gaps import flight_trajectory

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
FIGD = os.path.join(HERE, '..', '代码', 'figures')
os.makedirs(FIGD, exist_ok=True)
data = Data()

POS = {'W': (109.2103, 23.047134, 676.5),
       'E': (109.276017, 23.019401, 542.3),
       'N': (109.238171, 23.077841, 496.1)}
AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'
POS_LABEL = {'W': '西点', 'E': '东点', 'N': '北点'}


def dem_geo():
    """DEM 数组 + 地理 extent（经度左、经度右、纬度下、纬度上）。"""
    lon_min = data.dem_lon_min
    lat_max = data.dem_lat_max
    H, W = data.dem.shape
    return data.dem, (lon_min, lon_min + W * data.dem_res,
                      lat_max - H * data.dem_res, lat_max)


def draw_dem_base(ax, cmap='terrain', contour=True):
    dem, ext = dem_geo()
    vmax = np.nanpercentile(dem, 97)
    ax.imshow(dem, extent=ext, origin='upper', cmap=cmap, vmin=0, vmax=vmax,
              interpolation='bilinear', alpha=0.92)
    if contour:
        cs = ax.contour(dem, levels=np.arange(50, 900, 50),
                        extent=ext, origin='upper',
                        colors='#555555', linewidths=0.35, alpha=0.45)
    ax.set_aspect(1.0 / np.cos(np.radians(data.lat0)))
    return dem


def save(fig, name):
    fig.savefig(os.path.join(FIGD, name), bbox_inches='tight', pad_inches=0.06)
    plt.close(fig)
    print('saved', name)


# ---------------- 图：研究区地形与服务区/中继总览 ----------------
def fig_dem_map():
    fig, ax = plt.subplots(figsize=(10.2, 7.2))
    draw_dem_base(ax)
    # 服务区
    for sid, a in data.areas.items():
        ax.scatter([a['lon']], [a['lat']], s=58, color='white', edgecolor='#222222',
                   linewidth=1.0, zorder=5)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points',
                    xytext=(6, 6), fontsize=8.2, zorder=6)
    o = data.centers['O01']
    ax.scatter([o['lon']], [o['lat']], marker='*', s=340, color=ps.C_RED,
               edgecolor='white', linewidth=0.8, zorder=7)
    ax.annotate('O01 调度中心', (o['lon'], o['lat']), textcoords='offset points',
                xytext=(10, -22), fontsize=9.5, fontweight='bold', zorder=7)
    # 中继
    for g, (lo, la, zz) in POS.items():
        ax.scatter([lo], [la], marker='^', s=150, color=ps.AREA_COLORS[g],
                   edgecolor='#222222', linewidth=0.9, zorder=6)
        ax.annotate(POS_LABEL[g], (lo, la), textcoords='offset points',
                    xytext=(10, 2), fontsize=9, zorder=6)
    ax.set_xlabel('经度（°E）')
    ax.set_ylabel('纬度（°N）')
    ax.legend(handles=[Patch(color=ps.C_RED, label='调度中心 O01'),
                       Patch(color='white', edgecolor='#222222', label='服务区'),
                       Patch(color=ps.AREA_COLORS['W'], label='西点中继'),
                       Patch(color=ps.AREA_COLORS['E'], label='东点中继'),
                       Patch(color=ps.AREA_COLORS['N'], label='北点中继')],
              loc='lower left', fontsize=9, framealpha=0.92)
    save(fig, 'p1_dem_map.png')


# ---------------- 图：典型航线 DEM 高程剖面 ----------------
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
        ax.axhline(zmax + 50, color=ps.C_BLUE, ls='--', lw=1.1, zorder=4)
        ax.axhline(a['alt'] + 30, color=ps.C_ORANGE, ls=':', lw=1.0, zorder=4)
        ax.annotate('巡航高度 %d m' % (zmax + 50), (0.5, zmax + 50),
                    xytext=(0.04, 0.86), textcoords='axes fraction',
                    fontsize=8.4, color=ps.C_BLUE)
        ax.set_title('', fontsize=0)
        ax.text(0.02, 0.12, '%s（地面 %d m，装载 %d kg）' % (sid, a['alt'], _m),
                transform=ax.transAxes, fontsize=8.6)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, zmax * 1.35 + 60)
        ax.set_xlabel('航程归一化位置')
        ax.set_ylabel('海拔（m）')
    fig.suptitle('')
    save(fig, 'p1_alt_profiles.png')


# ---------------- 图：中继覆盖归属地图 ----------------
def fig_relay_coverage_map():
    r = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
    r3 = json.load(open(os.path.join(RES, 'p3_co2.json'), encoding='utf-8'))
    off = {int(k): float(v) for k, v in r3.get('offsets', {}).items()}
    base = {fj['fid']: float(fj['start']) for fj in r['flights']}
    pts_by = {'W': ([], []), 'E': ([], []), 'N': ([], [])}
    n_relay = 0
    for fj in r['flights']:
        f = Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
        pts, _ = flight_trajectory(f, base[f.fid] + off.get(f.fid, 0.0))
        groups = {}
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            sid = min(data.areas, key=lambda s: data.dist_ll(
                pt['lon'], pt['lat'], data.areas[s]['lon'], data.areas[s]['lat']))
            groups.setdefault(sid, []).append(pt)
        for sid, sgs in groups.items():
            g = AREA_POS.get(sid)
            if g is None:
                continue
            pts_by[g][0].extend(p['lon'] for p in sgs)
            pts_by[g][1].extend(p['lat'] for p in sgs)
            n_relay += len(sgs)
    fig, ax = plt.subplots(figsize=(10.2, 7.2))
    draw_dem_base(ax)
    for g in 'WEN':
        lons, lats = pts_by[g]
        ax.scatter(lons, lats, s=6, color=ps.AREA_COLORS[g], alpha=0.55,
                   edgecolor='none', zorder=4)
    for sid, a in data.areas.items():
        ax.scatter([a['lon']], [a['lat']], s=30, color='white',
                   edgecolor='#222222', linewidth=0.8, zorder=5)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points',
                    xytext=(4, 4), fontsize=7.6, zorder=6)
    o = data.centers['O01']
    ax.scatter([o['lon']], [o['lat']], marker='*', s=260, color=ps.C_RED,
               edgecolor='white', linewidth=0.8, zorder=7)
    for g, (lo, la, zz) in POS.items():
        ax.scatter([lo], [la], marker='^', s=170, color=ps.AREA_COLORS[g],
                   edgecolor='#222222', linewidth=0.9, zorder=6)
    ax.set_xlabel('经度（°E）')
    ax.set_ylabel('纬度（°N）')
    ax.legend(handles=[Patch(color=ps.AREA_COLORS['W'], label='西点保障（%d 采样）' % len(pts_by['W'][0])),
                       Patch(color=ps.AREA_COLORS['E'], label='东点保障（%d 采样）' % len(pts_by['E'][0])),
                       Patch(color=ps.AREA_COLORS['N'], label='北点保障（%d 采样）' % len(pts_by['N'][0]))],
              loc='lower left', fontsize=9, framealpha=0.92)
    ax.text(0.02, 0.97, '需中继采样点合计 %d，直连采样点未显示' % n_relay,
            transform=ax.transAxes, fontsize=8.6, va='top')
    save(fig, 'p3_relay_coverage.png')


# ---------------- 图：架次能耗构成 ----------------
def fig_energy_decomp():
    r = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
    fl = sorted(r['flights'], key=lambda x: (-x['energy'], x['fid']))
    fig, ax = plt.subplots(figsize=(10.2, 6.0))
    y = np.arange(len(fl))
    for f, yi in zip(fl, y):
        ax.barh(yi, f['energy'], height=0.72, color=ps.MODEL_COLORS[f['model']],
                edgecolor='white', linewidth=0.4)
        ax.text(f['energy'] + 0.06, yi, '%.2f' % f['energy'], va='center', fontsize=7.4)
    ax.set_yticks(y)
    ax.set_yticklabels(['f%02d' % f['fid'] for f in fl], fontsize=7.6)
    ax.set_xlabel('架次能耗（kWh）')
    ax.set_ylabel('架次')
    ax.set_xlim(0, max(f['energy'] for f in fl) * 1.22)
    ax.legend(handles=[Patch(color=ps.MODEL_COLORS['A'], label='A 型（12 架）'),
                       Patch(color=ps.MODEL_COLORS['B'], label='B 型（7 架）'),
                       Patch(color=ps.MODEL_COLORS['C'], label='C 型（7 架）')],
              loc='lower right', fontsize=9)
    ax.text(0.02, 0.97, '26 架次总能耗 70.71 kWh', transform=ax.transAxes,
            fontsize=9.5, fontweight='bold', va='top')
    save(fig, 'p2_energy_decomp.png')


# ---------------- 图：无人机电池 SOC 曲线 ----------------
def fig_soc_curves():
    r = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
    uavs = ['U01', 'U02', 'U03', 'U04', 'U05', 'U06', 'U07', 'U08']
    uav_model = {'U01': 'A', 'U02': 'A', 'U03': 'A', 'U04': 'A',
                 'U05': 'B', 'U06': 'B', 'U07': 'C', 'U08': 'C'}
    fl_by = {}
    for f in r['flights']:
        fl_by.setdefault(f['uav'], []).append(f)
    tmax = r['metrics']['makespan'] + 400
    fig, axes = plt.subplots(2, 4, figsize=(12.6, 5.4), sharex=True)
    for ax, uid in zip(axes.ravel(), uavs):
        m = uav_model[uid]
        for f in sorted(fl_by.get(uid, []), key=lambda x: x['start']):
            soc_end = 1 - f['energy'] / data.uav_types[m]['E_use']
            t_full = data.batteries[m]['T_full']
            ready = f['return'] + charge_time(soc_end, t_full)
            ax.plot([f['start'], f['return']], [1.0, soc_end],
                    color=ps.MODEL_COLORS[m], lw=2.0, zorder=3)
            ax.plot([f['return'], ready], [soc_end, 1.0],
                    color=ps.MODEL_COLORS[m], lw=1.0, ls='--', alpha=0.7, zorder=2)
        ax.set_title('', fontsize=0)
        ax.text(0.02, 0.94, uid, transform=ax.transAxes, fontsize=9,
                fontweight='bold', va='top')
        ax.axhline(0.2, color=ps.C_RED, ls=':', lw=0.9, alpha=0.8)
        ax.set_ylim(0.12, 1.06)
        ax.set_xlim(0, tmax)
        if ax.get_subplotspec().is_last_row():
            ax.set_xlabel('时间（s）')
        if ax.get_subplotspec().is_first_col():
            ax.set_ylabel('荷电状态')
    fig.legend(handles=[Patch(color=ps.MODEL_COLORS['A'], label='A 型'),
                        Patch(color=ps.MODEL_COLORS['B'], label='B 型'),
                        Patch(color=ps.MODEL_COLORS['C'], label='C 型'),
                        plt.Line2D([0], [0], color=ps.C_RED, ls=':', lw=1.0, label='20% 安全下限')],
               loc='lower center', ncol=4, fontsize=9, frameon=False, bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    save(fig, 'p2_soc_curves.png')


if __name__ == '__main__':
    fig_dem_map()
    fig_alt_profiles()
    fig_relay_coverage_map()
    fig_energy_decomp()
    fig_soc_curves()
    print('extra maps done')