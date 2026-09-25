# -*- coding: utf-8 -*-
"""问题三/四图件：联合甘特图、中继覆盖图、K=3 分区图。"""
import json
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Patch
from matplotlib.lines import Line2D
import plot_style as ps
from core import Data

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')

data = Data()
r = json.load(open(os.path.join(OUT, 'p3_final.json'), encoding='utf-8'))
POS = {'W': (109.2103, 23.047134, 676.5),
       'E': (109.276017, 23.019401, 542.3),
       'N': (109.238171, 23.077841, 496.1)}


def load_xy():
    x0, y0 = data.xy(data.areas['S001']['lon'], data.areas['S001']['lat'])
    out = {}
    for s in data.areas:
        lon, lat = data.areas[s]['lon'], data.areas[s]['lat']
        x, y = data.xy(lon, lat)
        out[s] = (x - x0, y - y0)
    return out


def area_group(sid):
    if sid in ('S004',):
        return 'N'
    if sid in ('S010', 'S012', 'S013', 'S014'):
        return 'E'
    return 'W'


def _base_ax(figsize):
    fig, ax = plt.subplots(figsize=figsize)
    return fig, ax


# ---------------- 中继布设与覆盖 ----------------
def fig_coverage():
    fig, ax = _base_ax((9, 8))
    xy = load_xy()
    ref = data.xy(data.areas['S001']['lon'], data.areas['S001']['lat'])
    # 接入半径圆（先画，置于底层）
    for g, pos in POS.items():
        x, y = data.xy(pos[0], pos[1])
        x, y = x - ref[0], y - ref[1]
        ax.add_patch(Circle((x, y), 6.3, fill=False, ls='--', lw=1.1,
                            edgecolor=ps.AREA_COLORS[g], alpha=0.85, zorder=2))
    # 服务区
    for s, (x, y) in xy.items():
        g = area_group(s)
        ax.scatter(x, y, s=95, c=ps.AREA_COLORS[g], edgecolor='white',
                   linewidth=0.7, zorder=5)
        ax.annotate(s[1:], (x, y), textcoords='offset points', xytext=(5, 5),
                    fontsize=8, color='black')
    # O01
    ox, oy = data.xy(data.gw_pt['lon'], data.gw_pt['lat'])
    ox, oy = ox - ref[0], oy - ref[1]
    ax.scatter([ox], [oy], marker='*', s=300, c=ps.C_RED, edgecolor='white',
               linewidth=0.8, zorder=6)
    ax.annotate('O01', (ox, oy), textcoords='offset points', xytext=(7, -13),
                fontsize=9, fontweight='bold')
    # 中继位置
    for g, pos in POS.items():
        x, y = data.xy(pos[0], pos[1])
        x, y = x - ref[0], y - ref[1]
        ax.scatter([x], [y], marker='^', s=170, c=ps.AREA_COLORS[g],
                   edgecolor=ps.C_BLACK, linewidth=0.8, zorder=6,
                   label='中继布设点 ' + {'W': 'W（西）', 'E': 'E（东）', 'N': 'N（北）'}[g])
    ax.set_aspect('equal')
    ax.set_xlabel('相对东向距离（km）')
    ax.set_ylabel('相对北向距离（km）')
    # 图例：中继点 + 接入半径
    handle2 = Line2D([], [], ls='--', color='#6B7280', lw=1.1,
                     label='接入链路半径 6.3 km')
    ax.legend(handles=ax.get_legend_handles_labels()[0] + [handle2],
              loc='upper right', frameon=False, fontsize=9)
    ax.grid(alpha=0.35)
    fig.savefig(os.path.join(FIG, 'p3_coverage.png'))
    plt.close(fig)
    print('saved p3_coverage.png')


# ---------------- 无人机 + 中继联合甘特图 ----------------
def fig_gantt():
    sch = r['schedule']
    flights = sorted(r['flights'], key=lambda f: (f['model'], f['fid']))
    uavs = sorted({v['uav'] for v in sch.values()})
    y_uav = {u: i for i, u in enumerate(uavs)}
    fig, ax = plt.subplots(figsize=(11.5, 8.6))
    for f in flights:
        s = sch[str(f['fid'])]
        m = f['model']
        ax.barh(y_uav[s['uav']], s['return'] - s['start'], left=s['start'],
                height=0.62, color=ps.MODEL_COLORS[m], edgecolor='white',
                linewidth=0.4, zorder=3)
        ax.text((s['start'] + s['return']) / 2, y_uav[s['uav']], 'F%02d' % f['fid'],
                ha='center', va='center', fontsize=7, color='black', zorder=4)
    # 中继泳道：悬停 + 转场
    y_relay = {u: len(uavs) + 1 + i for i, u in enumerate(['R1', 'R2'])}
    for k, sg in enumerate(r['sorties']):
        relay = sg['relay']
        pos = sg['pos']
        row = y_relay['R1'] if relay == 'R01' else y_relay['R2']
        ax.barh(row, sg['t1'] - sg['t0'], left=sg['t0'], height=0.62,
                color=ps.AREA_COLORS[pos], edgecolor='white', linewidth=0.4, zorder=3)
        ax.text((sg['t0'] + sg['t1']) / 2, row, '%s（%s）' % (pos, relay),
                ha='center', va='center', fontsize=8, color='black', zorder=4)
    # 两段之间的转场时间（R2 泳道画短箭头）
    r2 = [sg for sg in r['sorties'] if sg['relay'] == 'R02']
    if len(r2) == 2:
        row = y_relay['R2']
        ax.annotate('', xy=(r2[1]['t0'] - 30, row), xytext=(r2[0]['t1'] + 30, row),
                    arrowprops=dict(arrowstyle='->', color='#6B7280', lw=1.2))
        ax.text((r2[0]['t1'] + r2[1]['t0']) / 2, row + 0.32, '转场',
                ha='center', fontsize=8, color='black')
    handles = [Patch(color=ps.MODEL_COLORS[m], label='%s 型运输机' % m) for m in 'ABC']
    handles += [Patch(color=ps.AREA_COLORS[g], label='中继 %s 位置服务时段' % g) for g in 'WEN']
    ax.legend(handles=handles, loc='upper right', fontsize=9, ncol=2, frameon=False)
    all_uav = list(uavs) + ['R1', 'R2']
    ax.set_yticks(range(len(all_uav)))
    ax.set_yticklabels(all_uav, fontsize=9)
    ax.set_xlabel('时刻（s）')
    ax.set_ylabel('运输无人机 / 中继编号')
    ax.set_xlim(0, 9600)
    ax.grid(axis='x', alpha=0.35)
    fig.savefig(os.path.join(FIG, 'p3_gantt.png'))
    plt.close(fig)
    print('saved p3_gantt.png')


# ---------------- K=3 任务分区 ----------------
def fig_partition():
    xy = load_xy()
    fig, ax = plt.subplots(figsize=(9, 8))
    ref = data.xy(data.areas['S001']['lon'], data.areas['S001']['lat'])
    for g, pos in POS.items():
        x, y = data.xy(pos[0], pos[1])
        x, y = x - ref[0], y - ref[1]
        ax.add_patch(Circle((x, y), 6.3, fill=False, ls='--', lw=1.0,
                            edgecolor=ps.AREA_COLORS[g], alpha=0.8, zorder=2))
    for s, (x, y) in xy.items():
        g = area_group(s)
        ax.scatter(x, y, s=120, c=ps.AREA_COLORS[g], edgecolor='white',
                   linewidth=0.7, zorder=5)
        ax.annotate('S' + s[1:], (x, y), textcoords='offset points', xytext=(5, 5),
                    fontsize=9, color='black')
    ox, oy = data.xy(data.gw_pt['lon'], data.gw_pt['lat'])
    ox, oy = ox - ref[0], oy - ref[1]
    ax.scatter([ox], [oy], marker='*', s=320, c=ps.C_RED, edgecolor='white',
               linewidth=0.8, zorder=6)
    ax.annotate('O01', (ox, oy), textcoords='offset points', xytext=(7, -13),
                fontsize=9, fontweight='bold')
    for g, pos in POS.items():
        x, y = data.xy(pos[0], pos[1])
        x, y = x - ref[0], y - ref[1]
        ax.scatter([x], [y], marker='^', s=150, c=ps.AREA_COLORS[g],
                   edgecolor=ps.C_BLACK, linewidth=0.8, zorder=6)
    # 分组标注（axes 坐标，避免与数据冲突）
    ax.annotate('G1 西/北 10 区', xy=(0.02, 0.04), xycoords='axes fraction',
                fontsize=10, color='black', fontweight='bold')
    ax.annotate('G2 东 4 区', xy=(0.72, 0.30), xycoords='axes fraction',
                fontsize=10, color='black', fontweight='bold')
    ax.annotate('G3 S004（独立组）', xy=(0.60, 0.68), xycoords='axes fraction',
                fontsize=10, color='black', fontweight='bold')
    ax.set_aspect('equal')
    ax.set_xlabel('相对东向距离（km）')
    ax.set_ylabel('相对北向距离（km）')
    ax.grid(alpha=0.35)
    fig.savefig(os.path.join(FIG, 'p4_partition.png'))
    plt.close(fig)
    print('saved p4_partition.png')


if __name__ == '__main__':
    fig_coverage()
    fig_gantt()
    fig_partition()