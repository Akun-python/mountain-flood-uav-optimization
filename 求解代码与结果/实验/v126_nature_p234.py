# -*- coding: utf-8 -*-
"""v126：P2/P3/P4 系列图 Nature 级重绘（24 架冠军数据）。
p2_gantt / p2_energy_decomp / p2_battery / p2_soc_curves / p2_network /
p2_pareto2d / p2_delivery / p3_gantt / p3_relay_tl / p3_comm_tl /
p3_coverage / p3_relay_coverage / p3_margin_hist / p4_load / p4_gap /
p4_partition。输出到论文 figures/（PNG + PDF 双格式）。"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.join('求解代码与结果', '代码'))
sys.path.insert(0, os.path.join('求解代码与结果', '实验'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Circle
from matplotlib.lines import Line2D
import nature_style as ns
from core import Data, charge_time, direct_ok
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant
from p3_gaps import flight_trajectory

FIG = 'figures'
os.makedirs(FIG, exist_ok=True)
data = Data()
d = json.load(open(os.path.join('求解代码与结果', '结果', '进化_v25', 'v113_best.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
sch, _ = dispatch_compliant(data, fls)
mk = max(sch[f.fid]['return'] for f in fls)
en = sum(f.energy() for f in fls)
print('24架 mk=%.1f en=%.2f' % (mk, en))

TYPE_COLOR = {'医疗物资': ns.C_C, '饮用水': ns.C_A, '应急食品': ns.C_B, '生活卫生用品': ns.C_E}

# ---------- 1) p2_gantt：运输甘特 ----------
def fig_gantt():
    rows = sorted({v['uav'] for v in sch.values()})
    y_uav = {u: i for i, u in enumerate(rows)}
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    for f in sorted(fls, key=lambda x: x.fid):
        s = sch[f.fid]
        ax.barh(y_uav[s['uav']], s['return'] - s['start'], left=s['start'], height=0.62,
                color=ns.MODEL_COLORS[f.model], edgecolor='white', linewidth=0.4, zorder=3)
        ax.text(s['start'] + 90, y_uav[s['uav']], 'F%02d' % f.fid, fontsize=6.5,
                color=ns.C_TEXT, va='center', zorder=4)
    ax.axvline(mk, color=ns.C_HERO, ls='--', lw=1.1)
    ax.text(mk - 60, len(rows) - 0.35, '完成 %d s' % mk, color=ns.C_TEXT, fontsize=9, ha='right')
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows)
    ax.set_xlabel('时刻（s）'); ax.set_xlim(0, mk * 1.03); ax.grid(axis='x')
    ax.legend(handles=[Patch(color=ns.C_A, label='A 型'), Patch(color=ns.C_B, label='B 型'),
                       Patch(color=ns.C_C, label='C 型')], loc='upper right', frameon=False, ncol=3, fontsize=9)
    ns.save(fig, 'p2_gantt')

# ---------- 2) p2_energy_decomp：能耗构成 ----------
def fig_energy():
    cnt = {m: sum(1 for f in fls if f.model == m) for m in 'ABC'}
    fl = sorted(fls, key=lambda x: (-x.energy(), x.fid))
    fig, ax = plt.subplots(figsize=(10.2, 6.0))
    for yi, f in enumerate(fl):
        ax.barh(yi, f.energy(), height=0.72, color=ns.MODEL_COLORS[f.model],
                edgecolor='white', linewidth=0.4)
        ax.text(f.energy() + 0.06, yi, '%.2f' % f.energy(), va='center', fontsize=7.4)
    ax.set_yticks(range(len(fl))); ax.set_yticklabels(['f%02d' % f.fid for f in fl], fontsize=7.6)
    ax.set_xlabel('架次能耗（kWh）'); ax.set_ylabel('架次')
    ax.set_xlim(0, max(f.energy() for f in fl) * 1.22)
    ax.legend(handles=[Patch(color=ns.C_A, label='A 型（%d 架）' % cnt['A']),
                       Patch(color=ns.C_B, label='B 型（%d 架）' % cnt['B']),
                       Patch(color=ns.C_C, label='C 型（%d 架）' % cnt['C'])], loc='lower right', fontsize=9)
    ax.text(0.02, 0.97, '24 架次总能耗 %.2f kWh' % en, transform=ax.transAxes, fontsize=9.5,
            fontweight='bold', va='top')
    ns.save(fig, 'p2_energy_decomp')

# ---------- 3) p2_battery：电池时间线 ----------
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
                color=ns.MODEL_COLORS[f.model], edgecolor='white', linewidth=0.4, zorder=3)
        ax.barh(lane_y[b], ready - s['return'], left=s['return'], height=0.62,
                color=ns.C_LIGHT, alpha=0.9, hatch='//', edgecolor='white', linewidth=0.3, zorder=2)
    ax.set_yticks(list(lane_y.values())); ax.set_yticklabels(lanes, fontsize=8.5)
    ax.set_xlabel('时间（s）'); ax.set_ylabel('电池编号'); ax.set_xlim(0, tmax)
    ax.grid(axis='x', alpha=0.3)
    ax.legend(handles=[Patch(color=ns.C_A, label='A 型任务'), Patch(color=ns.C_B, label='B 型任务'),
                       Patch(color=ns.C_C, label='C 型任务'), Patch(color=ns.C_LIGHT, label='充电段')],
              loc='lower right', frameon=False, ncol=4)
    ns.save(fig, 'p2_battery')

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
            ax.plot([s['start'], s['return']], [1.0, soc_end], color=ns.MODEL_COLORS[m], lw=1.6)
            ax.plot([s['return'], ready], [soc_end, 1.0], color=ns.C_GRAY, lw=1.1, ls='--')
        ax.axhline(0.2, color=ns.C_C, lw=0.8, ls=':')
        ax.set_title(uid, fontsize=9); ax.grid(alpha=0.35)
    for ax in axes[1]: ax.set_xlabel('时间（s）')
    for ax in axes: ax[0].set_ylabel('SOC')
    fig.tight_layout()
    ns.save(fig, 'p2_soc_curves')

# ---------- 5) p2_network：航线网络 ----------
def fig_network():
    o = data.centers['O01']
    fig, ax = plt.subplots(figsize=(9.4, 7.6))
    for f in sorted(fls, key=lambda x: x.fid):
        pts = [(o['lon'], o['lat'])] + [(data.areas[s]['lon'], data.areas[s]['lat']) for s, _ in f.route] + [(o['lon'], o['lat'])]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.plot(xs, ys, color=ns.MODEL_COLORS[f.model], lw=1.2, alpha=0.6,
                solid_capstyle='round', zorder=3)
    ax.scatter([o['lon']], [o['lat']], marker='*', s=320, color=ns.C_HERO,
               edgecolor='white', linewidth=0.7, zorder=7, label='调度中心 O01')
    for sid in sorted(data.areas):
        a = data.areas[sid]
        ax.scatter([a['lon']], [a['lat']], s=30, color=ns.C_TEXT,
                   edgecolor='white', linewidth=0.5, zorder=6)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points',
                    xytext=(4, 3), fontsize=8, color=ns.C_TEXT)
    ax.legend(handles=[Line2D([0], [0], color=ns.C_A, lw=1.8, label='A 型航线'),
                       Line2D([0], [0], color=ns.C_B, lw=1.8, label='B 型航线'),
                       Line2D([0], [0], color=ns.C_C, lw=1.8, label='C 型航线')],
              loc='lower left', frameon=False, fontsize=9)
    ax.set_xlabel('经度（°E）'); ax.set_ylabel('纬度（°N）')
    ns.save(fig, 'p2_network')

# ---------- 6) p2_pareto2d：完工-能耗 Pareto ----------
def fig_pareto():
    pts = [('24 架冠军（本文）', 6571.4, 69.13, 24, ns.C_HERO, 'o', True),
           ('26 架完工同速', 6571.4, 70.24, 26, ns.C_B, 'D', False),
           ('27 架早期结构', 6571.4, 70.68, 27, ns.C_B, 'D', False),
           ('23 架完工次优', 6598.8, 69.83, 23, ns.C_A, '^', False),
           ('23 架能耗优先', 6760.6, 69.28, 23, ns.C_A, '^', False),
           ('22 架完工折中', 6993.3, 69.23, 22, ns.C_A, '^', False),
           ('21 架节能均衡', 7837.0, 64.48, 21, ns.C_E, 's', False),
           ('20 架能耗折中', 7778.7, 67.45, 20, ns.C_E, 's', False)]
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    for name, mm, ee, nf, c, mk_, big in pts:
        ax.scatter(mm, ee, s=nf * 26, marker=mk_, color=c, edgecolor='white',
                   linewidth=0.7, alpha=0.85, zorder=3)
        ax.annotate('%s\n%d 架次' % (name, nf), (mm, ee), textcoords='offset points',
                    xytext=(10, 6), fontsize=8.5, color=ns.C_TEXT)
    ax.set_xlabel('完工时间（s）'); ax.set_ylabel('总能耗（kWh）'); ax.grid(alpha=0.4)
    ns.save(fig, 'p2_pareto2d')

# ---------- 7) p2_delivery：逐箱交付时刻 vs 时限 ----------
def fig_delivery():
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    tmax = 0.0
    margin_min = 1e9
    tight = None
    for f in fls:
        for sid, bid, t in sch[f.fid]['deliveries']:
            bx = data.boxes[bid]
            ddl = bx['deadline_first'] if bx['first_batch'] else bx['deadline_exp']
            tmax = max(tmax, ddl, t)
            mk = 'o' if bx['first_batch'] else 's'
            ax.scatter([t], [ddl], s=34, marker=mk, color=TYPE_COLOR[bx['type']], alpha=0.85,
                       edgecolor='white', linewidth=0.3, zorder=3)
            m = ddl - t
            if m < margin_min:
                margin_min, tight = m, bid
    ax.axline((0, 0), slope=1, color=ns.C_GRAY, ls='--', lw=1.0)
    ax.text(tmax * 0.86, tmax * 0.80, '交付时刻等于时限', fontsize=8.5,
            color=ns.C_TEXT, rotation=35, ha='center')
    ax.annotate('最紧裕度 %d s（%s）' % (round(margin_min), tight),
                xy=(tmax * 0.965, margin_min + (tmax - margin_min) * 0.015),
                xytext=(tmax * 0.6, margin_min + tmax * 0.10),
                arrowprops=dict(arrowstyle='->', lw=0.9, color='#374151'),
                fontsize=8.5, color=ns.C_TEXT)
    ax.set_xlim(0, tmax * 1.02); ax.set_ylim(0, tmax * 1.02)
    ax.set_xlabel('交付完成时刻（s）'); ax.set_ylabel('配送时限（s）')
    hd = [Line2D([0], [0], marker='o', ls='', color=c, label=n) for n, c in TYPE_COLOR.items()]
    hd += [Line2D([0], [0], marker='o', ls='', color='#333333', label='首飞批'),
           Line2D([0], [0], marker='s', ls='', color='#333333', label='普通批')]
    ax.legend(handles=hd, loc='upper left', frameon=False, ncol=2, fontsize=8.5)
    ns.save(fig, 'p2_delivery')

# ---------- 8) p3_gantt：联合甘特 ----------
def fig_p3_gantt():
    rows = sorted({v['uav'] for v in sch.values()})
    y_uav = {u: i for i, u in enumerate(rows)}
    fig, ax = plt.subplots(figsize=(11.5, 8.6))
    for f in sorted(fls, key=lambda x: x.fid):
        s = sch[f.fid]
        ax.barh(y_uav[s['uav']], s['return'] - s['start'], left=s['start'], height=0.62,
                color=ns.MODEL_COLORS[f.model], edgecolor='white', linewidth=0.4, zorder=3)
        ax.text((s['start'] + s['return']) / 2, y_uav[s['uav']], 'F%02d' % f.fid,
                ha='center', va='center', fontsize=7, color=ns.C_TEXT, zorder=4)
    y_relay = {u: len(rows) + 1 + i for i, u in enumerate(['R1', 'R2'])}
    sorties = [('W', 'R01', 686, 6777), ('E', 'R02', 760, 3354), ('N', 'R02', 2562, 3289)]
    for pos, relay, t0, t1 in sorties:
        row = y_relay['R1'] if relay == 'R01' else y_relay['R2']
        ax.barh(row, t1 - t0, left=t0, height=0.62, color=ns.AREA_COLORS[pos],
                edgecolor='white', linewidth=0.4, zorder=3)
        ax.text((t0 + t1) / 2, row, '%s（%s）' % (pos, relay),
                ha='center', va='center', fontsize=8, color=ns.C_TEXT, zorder=4)
    lo, hi = 2562, 3289
    ax.axvspan(lo, hi, ymin=(y_relay['R2'] - 0.45) / (len(rows) + 2),
               ymax=(y_relay['R2'] + 0.45) / (len(rows) + 2), color=ns.C_C, alpha=0.18, zorder=1)
    ax.text((lo + hi) / 2, y_relay['R2'] + 0.42, 'E/N 重叠 727 s（机器级需协调）',
            ha='center', fontsize=7.5, color='#B45309')
    handles = [Patch(color=ns.MODEL_COLORS[m], label='%s 型运输机' % m) for m in 'ABC']
    handles += [Patch(color=ns.AREA_COLORS[g], label='中继 %s 位置服务时段' % g) for g in 'WEN']
    ax.legend(handles=handles, loc='upper right', fontsize=9, ncol=2, frameon=False)
    all_uav = list(rows) + ['R1', 'R2']
    ax.set_yticks(range(len(all_uav))); ax.set_yticklabels(all_uav, fontsize=9)
    ax.set_xlabel('时刻（s）'); ax.set_ylabel('运输无人机 / 中继编号')
    ax.set_xlim(0, 9600); ax.grid(axis='x', alpha=0.35)
    ns.save(fig, 'p3_gantt')

# ---------- 9) p3_relay_tl：中继时间线 ----------
def fig_relay_tl():
    fig, ax = plt.subplots(figsize=(10.8, 3.0))
    rows = [('R1 中继 1', 0, 686, '起飞准备', ns.C_LIGHT),
            ('R1 中继 1', 686, 6777, '西点服务', ns.C_W),
            ('R1 中继 1', 6777, 7077, '返航', ns.C_LIGHT),
            ('R2 中继 2', 0, 760, '起飞准备', ns.C_LIGHT),
            ('R2 中继 2', 760, 3354, '东点服务（需求窗口）', ns.C_E),
            ('R2 中继 2', 2562, 3289, '北点服务（需求窗口）', ns.C_N),
            ('R2 中继 2', 3354, 3600, '返航', ns.C_LIGHT)]
    for i, rid in enumerate(['R1 中继 1', 'R2 中继 2']):
        placed = []
        for nm, t0, t1, tag, c in rows:
            if nm != rid:
                continue
            if tag in ('起飞准备', '返航'):
                ax.barh(i, t1 - t0, left=t0, height=0.6, color=c,
                        edgecolor='white', linewidth=0.4, zorder=3)
                placed.append((t0, t1))
                continue
            if any(not (t1 <= p0 or t0 >= p1) for p0, p1 in placed):
                continue
            ax.barh(i, t1 - t0, left=t0, height=0.6, color=c,
                    edgecolor='white', linewidth=0.4, zorder=3)
            ax.text((t0 + t1) / 2, i, '%s\n[%d, %d]' % (tag.split('（')[0], t0, t1),
                    ha='center', va='center', fontsize=8.2, color='white', zorder=4)
            placed.append((t0, t1))
    ax.axvspan(2562, 3289, ymin=0.30, ymax=0.70, color=ns.C_C, alpha=0.30, zorder=2)
    ax.text(2926, 1.42, 'E/N 需求重叠 727 s（机器级需协调）', ha='center', va='top',
            fontsize=8.2, color='#B45309', zorder=5)
    ax.set_yticks([0, 1]); ax.set_yticklabels(['R1 中继 1', 'R2 中继 2'], fontsize=9)
    ax.set_xlabel('时间（s）'); ax.set_xlim(0, 7600); ax.set_ylim(-0.45, 1.62)
    ax.grid(axis='x', alpha=0.35)
    ax.legend(handles=[Patch(color=ns.C_W, label='西点服务'), Patch(color=ns.C_E, label='东点需求窗口'),
                       Patch(color=ns.C_N, label='北点需求窗口'), Patch(color=ns.C_LIGHT, label='起飞准备 / 返航')],
              loc='lower right', frameon=False, ncol=4)
    ns.save(fig, 'p3_relay_tl')

# ---------- 10) p3_comm_tl：通信保障时间线 ----------
def fig_comm_tl():
    area_pos = {}
    for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
        area_pos[s] = 'W'
    for s in ['S010', 'S012', 'S013', 'S014']:
        area_pos[s] = 'E'
    area_pos['S004'] = 'N'
    area_pos['S006'] = 'E'
    flights = sorted(fls, key=lambda x: x.fid)
    fig, ax = plt.subplots(figsize=(11.4, 7.8))
    y_of = {f.fid: i for i, f in enumerate(flights)}
    for f in flights:
        y = y_of[f.fid]
        pts, _ = flight_trajectory(f, sch[f.fid]['start'])
        mode = []
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                mode.append('直连')
            else:
                sid = min(data.areas, key=lambda s: data.dist_ll(
                    pt['lon'], pt['lat'], data.areas[s]['lon'], data.areas[s]['lat']))
                mode.append(area_pos.get(sid, '直连'))
        seg = []
        for pt, m in zip(pts, mode):
            if seg and seg[-1][2] == m:
                seg[-1][1] = pt['t']
            else:
                seg.append([pt['t'], pt['t'], m])
        for t0, t1, m in seg:
            c = {'直连': ns.C_LIGHT, 'W': ns.C_W, 'E': ns.C_E, 'N': ns.C_N}[m]
            ax.barh(y, t1 - t0, left=t0, height=0.62, color=c,
                    edgecolor='white', linewidth=0.25, zorder=3 if m != '直连' else 2)
    ax.set_yticks(list(y_of.values())); ax.set_yticklabels(['f%02d' % f.fid for f in flights], fontsize=8)
    ax.set_xlabel('时间（s）'); ax.set_xlim(0, 7600)
    ax.legend(handles=[Patch(color=ns.C_LIGHT, label='直连'), Patch(color=ns.C_W, label='中继 W 点'),
                       Patch(color=ns.C_E, label='中继 E 点'), Patch(color=ns.C_N, label='中继 N 点')],
              loc='lower right', frameon=False, ncol=4)
    ns.save(fig, 'p3_comm_tl')

# ---------- 11) p3_coverage：接入半径与覆盖圈 ----------
def fig_coverage():
    POS = {'W': (109.2103, 23.047134, 676.5),
           'E': (109.276017, 23.019401, 542.3),
           'N': (109.238171, 23.077841, 496.1)}
    area_pos = {}
    for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
        area_pos[s] = 'W'
    for s in ['S010', 'S012', 'S013', 'S014']:
        area_pos[s] = 'E'
    area_pos['S004'] = 'N'
    area_pos['S006'] = 'E'
    ref = data.xy(data.areas['S001']['lon'], data.areas['S001']['lat'])
    fig, ax = plt.subplots(figsize=(9.4, 7.6))
    for sid, a in data.areas.items():
        x, y = data.xy(a['lon'], a['lat'])
        x, y = x - ref[0], y - ref[1]
        g = area_pos[sid]
        ax.scatter(x, y, s=95, c=ns.AREA_COLORS[g], edgecolor='white',
                   linewidth=0.7, zorder=5)
        ax.annotate(sid[1:], (x, y), textcoords='offset points', xytext=(5, 5),
                    fontsize=8, color=ns.C_TEXT)
    ox, oy = data.xy(data.gw_pt['lon'], data.gw_pt['lat'])
    ox, oy = ox - ref[0], oy - ref[1]
    ax.scatter([ox], [oy], marker='*', s=320, c=ns.C_HERO, edgecolor='white',
               linewidth=0.8, zorder=6)
    ax.annotate('O01', (ox, oy), textcoords='offset points', xytext=(7, -13),
                fontsize=9, fontweight='bold')
    for g, pos in POS.items():
        x, y = data.xy(pos[0], pos[1])
        x, y = x - ref[0], y - ref[1]
        ax.scatter([x], [y], marker='^', s=180, c=ns.AREA_COLORS[g],
                   edgecolor=ns.C_TEXT, linewidth=0.8, zorder=6,
                   label='中继布设点 ' + {'W': 'W（西）', 'E': 'E（东）', 'N': 'N（北）'}[g])
    ax.set_aspect('equal')
    ax.set_xlabel('相对东向距离（km）')
    ax.set_ylabel('相对北向距离（km）')
    handle2 = Line2D([], [], ls='--', color=ns.C_GRAY, lw=1.1,
                     label='接入链路半径 6.3 km')
    ax.legend(handles=ax.get_legend_handles_labels()[0] + [handle2],
              loc='upper right', frameon=False, fontsize=9)
    ax.grid(alpha=0.35)
    ns.save(fig, 'p3_coverage')

# ---------- 12) p3_relay_coverage：中继覆盖归属（需中继点按归属着色） ----------
def fig_relay_coverage():
    area_pos = {}
    for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
        area_pos[s] = 'W'
    for s in ['S010', 'S012', 'S013', 'S014']:
        area_pos[s] = 'E'
    area_pos['S004'] = 'N'
    area_pos['S006'] = 'E'
    ref = data.xy(data.areas['S001']['lon'], data.areas['S001']['lat'])
    fig, ax = plt.subplots(figsize=(9.4, 7.6))
    cnt = {'W': 0, 'E': 0, 'N': 0}
    for f in fls:
        pts, _ = flight_trajectory(f, sch[f.fid]['start'])
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            sid = min(data.areas, key=lambda s: data.dist_ll(
                pt['lon'], pt['lat'], data.areas[s]['lon'], data.areas[s]['lat']))
            g = area_pos.get(sid)
            if g is None:
                continue
            cnt[g] += 1
            x, y = data.xy(pt['lon'], pt['lat'])
            ax.scatter(x - ref[0], y - ref[1], s=3, color=ns.AREA_COLORS[g],
                       alpha=0.35, linewidths=0, zorder=2)
    for sid, a in data.areas.items():
        x, y = data.xy(a['lon'], a['lat'])
        g = area_pos[sid]
        ax.scatter(x - ref[0], y - ref[1], s=70, c='white', edgecolor=ns.AREA_COLORS[g],
                   linewidth=1.0, zorder=5)
        ax.annotate(sid[1:], (x - ref[0], y - ref[1]), textcoords='offset points',
                    xytext=(5, 5), fontsize=7.5, color=ns.C_TEXT)
    ox, oy = data.xy(data.gw_pt['lon'], data.gw_pt['lat'])
    ax.scatter([ox - ref[0]], [oy - ref[1]], marker='*', s=300, c=ns.C_HERO,
               edgecolor='white', linewidth=0.8, zorder=6)
    ax.annotate('O01', (ox - ref[0], oy - ref[1]), textcoords='offset points',
                xytext=(7, -13), fontsize=9, fontweight='bold')
    ax.set_aspect('equal')
    ax.set_xlabel('相对东向距离（km）')
    ax.set_ylabel('相对北向距离（km）')
    ax.legend(handles=[Patch(color=ns.C_W, label='W 点覆盖（%d 点）' % cnt['W']),
                       Patch(color=ns.C_E, label='E 点覆盖（%d 点）' % cnt['E']),
                       Patch(color=ns.C_N, label='N 点覆盖（%d 点）' % cnt['N'])],
              loc='upper right', frameon=False, fontsize=9)
    ax.grid(alpha=0.25)
    ns.save(fig, 'p3_relay_coverage')

# ---------- 13) p3_margin_hist：链路余量分布 ----------
def fig_margin_hist():
    r = json.load(open(os.path.join('求解代码与结果', 'results', 'p3_margins.json'), encoding='utf-8'))
    fig, axes = plt.subplots(1, 3, figsize=(11.6, 3.6), sharey=True)
    for ax, g in zip(axes, 'WEN'):
        s = r[g]
        ax.hist(s['samples'], bins=np.arange(0, 34, 1), color=ns.AREA_COLORS[g],
                edgecolor='white', linewidth=0.4, alpha=0.92)
        ax.axvline(1.0, color=ns.C_GRAY, ls='--', lw=0.9)
        ax.axvline(s['min'], color=ns.C_TEXT, ls=':', lw=0.9)
        ax.text(0.98, 0.92, '%s 点\nn=%d\n最紧 %.1f dB' % (g, s['n'], s['min']),
                transform=ax.transAxes, ha='right', va='top', fontsize=8.5, color=ns.C_TEXT)
        if g == 'W':
            ax.text(1.2, ax.get_ylim()[1] * 0.6, '1 dB\n下压线', fontsize=8, color=ns.C_TEXT)
        ax.set_xlabel('接入链路余量（dB）')
    axes[0].set_ylabel('采样点数')
    fig.tight_layout()
    ns.save(fig, 'p3_margin_hist')

# ---------- 14) p4_load：货箱数与质量 ----------
def fig_p4_load():
    def group3(box):
        sid = box.split('-')[0]
        w = {'S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015'}
        if sid in w:
            return 'G1'
        if sid == 'S004':
            return 'G3'
        return 'G2'
    f39s006 = set()
    for f in fls:
        if f.fid == 39:
            for z, bs in f.route:
                if z == 'S006':
                    f39s006 |= set(bs)
    mass = {}
    for b in data.boxes:
        mass[b] = data.boxes[b]['weight'] if 'weight' in data.boxes[b] else data.boxes[b]['mass']
    g3 = {'G1': [0, 0.0], 'G2': [0, 0.0], 'G3': [0, 0.0]}
    for b in data.boxes:
        g = group3(b)
        if b in f39s006:
            g = 'G1'
        g3[g][0] += 1
        g3[g][1] += mass[b]
    g2 = {'G1': g3['G1'][:], 'G2': [g3['G2'][0] + g3['G3'][0], g3['G2'][1] + g3['G3'][1]]}
    print('三组:', {k: v for k, v in g3.items()}, '两组:', g2)
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    cols = {'G1': ns.C_A, 'G2': ns.C_B, 'G3': ns.C_N}
    for ax, dat in zip(axes, (g3, g2)):
        names = list(dat)
        x = np.arange(len(names))
        nb = [dat[n][0] for n in names]
        ms = [dat[n][1] for n in names]
        ax.bar(x - 0.19, nb, 0.38, color=[cols[n] for n in names],
               edgecolor='white', linewidth=0.5)
        for xi, v in zip(x, nb):
            ax.annotate('%d 箱' % v, (xi - 0.19, v), textcoords='offset points',
                        xytext=(0, 3), ha='center', fontsize=8)
        ax2 = ax.twinx()
        ax2.bar(x + 0.19, ms, 0.38, color=[cols[n] for n in names], alpha=0.45,
                edgecolor='white', linewidth=0.5)
        for xi, v in zip(x, ms):
            ax2.annotate('%d kg' % v, (xi + 0.19, v), textcoords='offset points',
                         xytext=(0, 3), ha='center', fontsize=8)
        ax.set_xticks(x); ax.set_xticklabels(names, fontsize=9)
        ax.set_ylabel('货箱数'); ax2.set_ylabel('总质量（kg）')
        ax.set_ylim(0, max(nb) * 1.25); ax2.set_ylim(0, max(ms) * 1.25)
        ax.set_xlabel('三组分区' if dat is g3 else '两组分区')
    fig.tight_layout()
    ns.save(fig, 'p4_load')

# ---------- 15) p4_gap：库存 vs 缺口 ----------
def fig_p4_gap():
    labels = ['A 机', 'B 机', 'C 机', 'A 电', 'B 电', 'C 电', '中继', '组件']
    inv = [4, 2, 2, 6, 4, 4, 2, 6]
    k3 = [6, 5, 5, 8, 7, 6, 7, 10]
    k2 = [6, 5, 5, 8, 7, 7, 6, 10]
    x = np.arange(len(labels)); w = 0.26
    fig, ax = plt.subplots(figsize=(10.8, 4.6))
    ax.bar(x - w, inv, w, color=ns.C_LIGHT, edgecolor=ns.C_GRAY, linewidth=0.5, label='给定库存')
    for K, vals, off, c in (('2', k2, 0, ns.C_A), ('3', k3, w, ns.C_B)):
        bars = ax.bar(x + off, vals, w, color=c, alpha=0.85, edgecolor='white',
                      linewidth=0.5, label='%s 组配置' % K)
        for xi, v, iv in zip(x + off, vals, inv):
            if v > iv:
                ax.annotate('+%d' % (v - iv), (xi, v), textcoords='offset points',
                            xytext=(0, 3), ha='center', fontsize=8, fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('数量'); ax.grid(axis='y')
    ax.legend(loc='upper left', frameon=False, ncol=3)
    ns.save(fig, 'p4_gap')

# ---------- 16) p4_partition：任务分区示意 ----------
def fig_partition():
    POS = {'W': (109.2103, 23.047134, 676.5),
           'E': (109.276017, 23.019401, 542.3),
           'N': (109.238171, 23.077841, 496.1)}
    area_pos = {}
    for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
        area_pos[s] = 'W'
    for s in ['S010', 'S012', 'S013', 'S014']:
        area_pos[s] = 'E'
    area_pos['S004'] = 'N'
    area_pos['S006'] = 'E'
    ref = data.xy(data.areas['S001']['lon'], data.areas['S001']['lat'])
    fig, ax = plt.subplots(figsize=(9, 8))
    for g, pos in POS.items():
        x, y = data.xy(pos[0], pos[1])
        x, y = x - ref[0], y - ref[1]
        ax.add_patch(Circle((x, y), 6.3, fill=False, ls='--', lw=1.0,
                            edgecolor=ns.AREA_COLORS[g], alpha=0.8, zorder=2))
    for sid, a in data.areas.items():
        x, y = data.xy(a['lon'], a['lat'])
        g = area_pos[sid]
        ax.scatter(x - ref[0], y - ref[1], s=130, c=ns.AREA_COLORS[g],
                   edgecolor='white', linewidth=0.7, zorder=5)
        ax.annotate(sid, (x - ref[0], y - ref[1]), textcoords='offset points',
                    xytext=(5, 5), fontsize=8, color=ns.C_TEXT)
    ox, oy = data.xy(data.gw_pt['lon'], data.gw_pt['lat'])
    ax.scatter([ox - ref[0]], [oy - ref[1]], marker='*', s=320, c=ns.C_HERO,
               edgecolor='white', linewidth=0.8, zorder=6)
    ax.annotate('O01', (ox - ref[0], oy - ref[1]), textcoords='offset points',
                xytext=(7, -13), fontsize=9, fontweight='bold')
    ax.set_aspect('equal')
    ax.set_xlabel('相对东向距离（km）')
    ax.set_ylabel('相对北向距离（km）')
    ax.legend(handles=[Patch(color=ns.C_W, label='西片（G1）'), Patch(color=ns.C_E, label='东片（G2）'),
                       Patch(color=ns.C_N, label='北片（G3）')],
              loc='upper right', frameon=False, fontsize=9)
    ax.grid(alpha=0.3)
    ns.save(fig, 'p4_partition')

fig_gantt()
fig_energy()
fig_battery()
fig_soc()
fig_network()
fig_pareto()
fig_delivery()
fig_p3_gantt()
fig_relay_tl()
fig_comm_tl()
fig_coverage()
fig_relay_coverage()
fig_margin_hist()
fig_p4_load()
fig_p4_gap()
fig_partition()
print('P2P3P4 ALL DONE')