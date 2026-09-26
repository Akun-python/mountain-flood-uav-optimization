# -*- coding: utf-8 -*-
"""v122：按 24 架冠军（v113_best）重绘核心图到论文 figures/（覆盖同名旧图）。
p2_gantt / p2_energy_decomp / p2_battery / p2_soc_curves / p2_network / p3_gantt。"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.join('求解代码与结果', '代码'))
sys.path.insert(0, os.path.join('求解代码与结果', '实验'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import plot_style as ps
from core import Data, charge_time
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant

FIG = 'figures'
os.makedirs(FIG, exist_ok=True)
data = Data()
d = json.load(open(os.path.join('求解代码与结果', '结果', '进化_v25', 'v113_best.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
sch, _ = dispatch_compliant(data, fls)
mk = max(sch[f.fid]['return'] for f in fls)
en = sum(f.energy() for f in fls)
print('24架 mk=%.1f en=%.2f' % (mk, en))

# ---------- 1) p2_gantt：运输甘特图 ----------
def fig_gantt():
    rows = sorted({v['uav'] for v in sch.values()})
    y_uav = {u: i for i, u in enumerate(rows)}
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    for f in sorted(fls, key=lambda x: x.fid):
        s = sch[f.fid]
        ax.barh(y_uav[s['uav']], s['return'] - s['start'], left=s['start'], height=0.62,
                color=ps.MODEL_COLORS[f.model], edgecolor='white', linewidth=0.4, zorder=3)
        ax.text(s['start'] + 90, y_uav[s['uav']], 'F%02d' % f.fid, fontsize=6.5,
                color='black', va='center', zorder=4)
    ax.axvline(mk, color=ps.C_RED, ls='--', lw=1.0)
    ax.text(mk - 60, len(rows) - 0.35, '完成 %d s' % mk, color='black', fontsize=9, ha='right')
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows)
    ax.set_xlabel('时刻（s）'); ax.set_xlim(0, mk * 1.03); ax.grid(axis='x')
    ax.legend(handles=[Patch(color=ps.C_BLUE, label='A 型'), Patch(color=ps.C_ORANGE, label='B 型'),
                       Patch(color=ps.C_RED, label='C 型')], loc='upper right', frameon=False, ncol=3, fontsize=9)
    fig.savefig(os.path.join(FIG, 'p2_gantt.png'), dpi=160); plt.close(fig); print('saved p2_gantt')

# ---------- 2) p2_energy_decomp：能耗构成 ----------
def fig_energy():
    cnt = {m: sum(1 for f in fls if f.model == m) for m in 'ABC'}
    fl = sorted(fls, key=lambda x: (-x.energy(), x.fid))
    fig, ax = plt.subplots(figsize=(10.2, 6.0))
    for yi, f in enumerate(fl):
        ax.barh(yi, f.energy(), height=0.72, color=ps.MODEL_COLORS[f.model], edgecolor='white', linewidth=0.4)
        ax.text(f.energy() + 0.06, yi, '%.2f' % f.energy(), va='center', fontsize=7.4)
    ax.set_yticks(range(len(fl))); ax.set_yticklabels(['f%02d' % f.fid for f in fl], fontsize=7.6)
    ax.set_xlabel('架次能耗（kWh）'); ax.set_ylabel('架次')
    ax.set_xlim(0, max(f.energy() for f in fl) * 1.22)
    ax.legend(handles=[Patch(color=ps.C_BLUE, label='A 型（%d 架）' % cnt['A']),
                       Patch(color=ps.C_ORANGE, label='B 型（%d 架）' % cnt['B']),
                       Patch(color=ps.C_RED, label='C 型（%d 架）' % cnt['C'])], loc='lower right', fontsize=9)
    ax.text(0.02, 0.97, '24 架次总能耗 %.2f kWh' % en, transform=ax.transAxes, fontsize=9.5,
            fontweight='bold', va='top')
    fig.savefig(os.path.join(FIG, 'p2_energy_decomp.png'), dpi=160); plt.close(fig); print('saved p2_energy_decomp')

# ---------- 3) p2_battery：14 组电池时间线 ----------
def fig_battery():
    lanes = sorted({v['battery'] for v in sch.values()})
    lane_y = {b: i for i, b in enumerate(lanes)}
    tmax = mk + 400
    fig, ax = plt.subplots(figsize=(10.6, 6.4))
    for f in sorted(fls, key=lambda x: sch[x.fid]['start']):
        s = sch[f.fid]; b = s['battery']
        soc_end = 1 - f.energy() / data.uav_types[f.model]['E_use']
        t_full = data.batteries[f.model]['T_full']
        ready = s['return'] + charge_time(soc_end, t_full)
        ax.barh(lane_y[b], s['return'] - s['start'], left=s['start'], height=0.62,
                color=ps.MODEL_COLORS[f.model], edgecolor='white', linewidth=0.4, zorder=3)
        ax.barh(lane_y[b], ready - s['return'], left=s['return'], height=0.62,
                color='#D1D5DB', alpha=0.85, hatch='//', edgecolor='white', linewidth=0.3, zorder=2)
    ax.set_yticks(list(lane_y.values())); ax.set_yticklabels(lanes, fontsize=8.5)
    ax.set_xlabel('时间（s）'); ax.set_ylabel('电池编号'); ax.set_xlim(0, tmax)
    ax.grid(axis='x', alpha=0.3)
    ax.legend(handles=[Patch(color=ps.C_BLUE, label='A 型任务'), Patch(color=ps.C_ORANGE, label='B 型任务'),
                       Patch(color=ps.C_RED, label='C 型任务'), Patch(color='#D1D5DB', label='充电段')],
              loc='lower right', frameon=False, ncol=4)
    fig.savefig(os.path.join(FIG, 'p2_battery.png'), dpi=160); plt.close(fig); print('saved p2_battery')

# ---------- 4) p2_soc_curves：SOC 轨迹 ----------
def fig_soc():
    uavs = ['U01', 'U02', 'U03', 'U04', 'U05', 'U06', 'U07', 'U08']
    uav_model = dict(zip(uavs, ['A'] * 4 + ['B'] * 2 + ['C'] * 2))
    fl_by = {}
    for f in fls:
        fl_by.setdefault(sch[f.fid]['uav'], []).append(f)
    fig, axes = plt.subplots(2, 4, figsize=(12.6, 5.4), sharex=True)
    for ax, uid in zip(axes.ravel(), uavs):
        m = uav_model[uid]
        for f in sorted(fl_by.get(uid, []), key=lambda x: sch[x.fid]['start']):
            s = sch[f.fid]
            soc_end = 1 - f.energy() / data.uav_types[m]['E_use']
            t_full = data.batteries[m]['T_full']
            ready = s['return'] + charge_time(soc_end, t_full)
            ax.plot([s['start'], s['return']], [1.0, soc_end], color=ps.MODEL_COLORS[m], lw=1.6)
            ax.plot([s['return'], ready], [soc_end, 1.0], color='#9CA3AF', lw=1.1, ls='--')
        ax.axhline(0.2, color=ps.C_RED, lw=0.8, ls=':')
        ax.set_title(uid, fontsize=9); ax.grid(alpha=0.35)
    for ax in axes[1]: ax.set_xlabel('时间（s）')
    for ax in axes: ax[0].set_ylabel('SOC')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'p2_soc_curves.png'), dpi=160); plt.close(fig); print('saved p2_soc_curves')

# ---------- 5) p2_network：航线网络 ----------
def fig_network():
    o = data.centers['O01']
    fig, ax = plt.subplots(figsize=(9.4, 7.6))
    for f in sorted(fls, key=lambda x: x.fid):
        pts = [(o['lon'], o['lat'])] + [(data.areas[s]['lon'], data.areas[s]['lat']) for s, _ in f.route] + [(o['lon'], o['lat'])]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.plot(xs, ys, color=ps.MODEL_COLORS[f.model], lw=1.1, alpha=0.55, solid_capstyle='round', zorder=3)
    ax.scatter([o['lon']], [o['lat']], marker='*', s=260, color=ps.C_RED, edgecolor='white',
               linewidth=0.7, zorder=7, label='调度中心 O01')
    for sid in sorted(data.areas):
        a = data.areas[sid]
        ax.scatter([a['lon']], [a['lat']], s=26, color=ps.C_BLACK, edgecolor='white', linewidth=0.5, zorder=6)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points', xytext=(4, 3), fontsize=8, color='black')
    ax.legend(handles=[Line2D([0], [0], color=ps.C_BLUE, lw=1.8, label='A 型航线'),
                       Line2D([0], [0], color=ps.C_ORANGE, lw=1.8, label='B 型航线'),
                       Line2D([0], [0], color=ps.C_RED, lw=1.8, label='C 型航线')],
              loc='lower left', frameon=False, fontsize=9)
    ax.set_xlabel('经度（°E）'); ax.set_ylabel('纬度（°N）')
    fig.savefig(os.path.join(FIG, 'p2_network.png'), dpi=160); plt.close(fig); print('saved p2_network')

# ---------- 6) p3_gantt：运输 + 中继联合甘特 ----------
def fig_p3_gantt():
    rows = sorted({v['uav'] for v in sch.values()})
    y_uav = {u: i for i, u in enumerate(rows)}
    fig, ax = plt.subplots(figsize=(11.5, 8.6))
    for f in sorted(fls, key=lambda x: x.fid):
        s = sch[f.fid]
        ax.barh(y_uav[s['uav']], s['return'] - s['start'], left=s['start'], height=0.62,
                color=ps.MODEL_COLORS[f.model], edgecolor='white', linewidth=0.4, zorder=3)
        ax.text((s['start'] + s['return']) / 2, y_uav[s['uav']], 'F%02d' % f.fid,
                ha='center', va='center', fontsize=7, color='black', zorder=4)
    y_relay = {u: len(rows) + 1 + i for i, u in enumerate(['R1', 'R2'])}
    sorties = [('W', 'R01', 686, 6777), ('E', 'R02', 760, 3354), ('N', 'R02', 2562, 3289)]
    for pos, relay, t0, t1 in sorties:
        row = y_relay['R1'] if relay == 'R01' else y_relay['R2']
        ax.barh(row, t1 - t0, left=t0, height=0.62, color=ps.AREA_COLORS[pos],
                edgecolor='white', linewidth=0.4, zorder=3)
        ax.text((t0 + t1) / 2, row, '%s（%s）' % (pos, relay), ha='center', va='center', fontsize=8, zorder=4)
    # E/N 重叠标注
    lo, hi = 2562, 3289
    ax.axvspan(lo, hi, ymin=(y_relay['R2'] - 0.45) / (len(rows) + 2), ymax=(y_relay['R2'] + 0.45) / (len(rows) + 2),
               color='#F87171', alpha=0.18, zorder=1)
    ax.text((lo + hi) / 2, y_relay['R2'] + 0.42, 'E/N 重叠 727 s（机器级需协调）', ha='center', fontsize=7.5, color='#B91C1C')
    handles = [Patch(color=ps.MODEL_COLORS[m], label='%s 型运输机' % m) for m in 'ABC']
    handles += [Patch(color=ps.AREA_COLORS[g], label='中继 %s 位置服务时段' % g) for g in 'WEN']
    ax.legend(handles=handles, loc='upper right', fontsize=9, ncol=2, frameon=False)
    all_uav = list(rows) + ['R1', 'R2']
    ax.set_yticks(range(len(all_uav))); ax.set_yticklabels(all_uav, fontsize=9)
    ax.set_xlabel('时刻（s）'); ax.set_ylabel('运输无人机 / 中继编号')
    ax.set_xlim(0, 9600); ax.grid(axis='x', alpha=0.35)
    fig.savefig(os.path.join(FIG, 'p3_gantt.png'), dpi=160); plt.close(fig); print('saved p3_gantt')

fig_gantt()
fig_energy()
fig_battery()
fig_soc()
fig_network()
fig_p3_gantt()
print('ALL DONE')