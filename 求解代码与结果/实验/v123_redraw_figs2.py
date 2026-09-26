# -*- coding: utf-8 -*-
"""v123：24 架冠军下重绘 p2_pareto2d / p3_relay_tl / p3_comm_tl / p4_load / p4_gap。"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.join('求解代码与结果', '代码'))
sys.path.insert(0, os.path.join('求解代码与结果', '实验'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import plot_style as ps
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant

FIG = 'figures'
data = Data()
d = json.load(open(os.path.join('求解代码与结果', '结果', '进化_v25', 'v113_best.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
sch, _ = dispatch_compliant(data, fls)
mk = max(sch[f.fid]['return'] for f in fls)
en = sum(f.energy() for f in fls)
print('mk=%.1f en=%.2f' % (mk, en))

# ---------- 1) p2_pareto2d：完工-能耗前沿 ----------
def fig_pareto():
    pts = [('24 架冠军（本文）', 6571.4, 69.13, 24, ps.C_GREEN, 'o', True),
           ('26 架完工同速', 6571.4, 70.24, 26, ps.C_ORANGE, 'D', False),
           ('27 架早期结构', 6571.4, 70.68, 27, ps.C_ORANGE, 'D', False),
           ('23 架完工次优', 6598.8, 69.83, 23, ps.C_BLUE, '^', False),
           ('23 架能耗优先', 6760.6, 69.28, 23, ps.C_BLUE, '^', False),
           ('22 架完工折中', 6993.3, 69.23, 22, ps.C_BLUE, '^', False),
           ('21 架节能均衡', 7837.0, 64.48, 21, ps.C_VIOLET, 's', False),
           ('20 架能耗折中', 7778.7, 67.45, 20, ps.C_VIOLET, 's', False)]
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    for name, mm, ee, nf, c, mk_, big in pts:
        ax.scatter(mm, ee, s=nf * 26, marker=mk_, color=c, edgecolor='white',
                   linewidth=0.7, alpha=0.85, zorder=3)
        ax.annotate('%s\n%d 架次' % (name, nf), (mm, ee), textcoords='offset points',
                    xytext=(10, 6), fontsize=8.5, color='black')
    ax.set_xlabel('完工时间（s）'); ax.set_ylabel('总能耗（kWh）'); ax.grid(alpha=0.4)
    fig.savefig(os.path.join(FIG, 'p2_pareto2d.png'), dpi=160); plt.close(fig); print('saved p2_pareto2d')

# ---------- 2) p3_relay_tl：中继两机时间线 ----------
def fig_relay_tl():
    # R1 西点全程；R2 东点需求窗口 [760,3354]、北点需求窗口 [2562,3289]（E/N 重叠如实标注）
    fig, ax = plt.subplots(figsize=(10.8, 3.0))
    rows = [('R1 中继 1', 0, 686, '起飞准备', '#E5E7EB'),
            ('R1 中继 1', 686, 6777, '西点服务', '#D97706'),
            ('R1 中继 1', 6777, 7077, '返航', '#E5E7EB'),
            ('R2 中继 2', 0, 760, '起飞准备', '#E5E7EB'),
            ('R2 中继 2', 760, 3354, '东点服务（需求窗口）', '#2563EB'),
            ('R2 中继 2', 2562, 3289, '北点服务（需求窗口）', '#7C3AED'),
            ('R2 中继 2', 3354, 3600, '返航', '#E5E7EB')]
    for i, rid in enumerate(['R1 中继 1', 'R2 中继 2']):
        draw = [r for r in rows if r[0] == rid]
        # 按 t0 排序且不与已画区间重叠才画（北点段与东点段重叠时后来者优先覆盖）
        placed = []
        for nm, t0, t1, tag, c in draw:
            if tag in ('起飞准备', '返航'):
                ax.barh(i, t1 - t0, left=t0, height=0.6, color=c, edgecolor='white', linewidth=0.4, zorder=3)
                placed.append((t0, t1))
                continue
            if any(not (t1 <= p0 or t0 >= p1) for p0, p1 in placed):
                continue  # 与已画服务段重叠 -> 留给第三架/协调，图上由阴影标注
            ax.barh(i, t1 - t0, left=t0, height=0.6, color=c, edgecolor='white', linewidth=0.4, zorder=3)
            ax.text((t0 + t1) / 2, i, '%s\n[%d, %d]' % (tag.split('（')[0], t0, t1),
                    ha='center', va='center', fontsize=8.2, color='white', zorder=4)
            placed.append((t0, t1))
    # E/N 需求重叠阴影（R2 行）
    ax.axvspan(2562, 3289, ymin=0.35, ymax=0.65, color='#F87171', alpha=0.30, zorder=2)
    ax.text(2925, 0.55, 'E/N 需求重叠 727 s', ha='center', fontsize=8, color='#B91C1C',
            transform=ax.get_yaxis_transform(), zorder=5)
    ax.set_yticks([0, 1]); ax.set_yticklabels(['R1 中继 1', 'R2 中继 2'], fontsize=9)
    ax.set_xlabel('时间（s）'); ax.set_xlim(0, 7600); ax.grid(axis='x', alpha=0.35)
    ax.legend(handles=[Patch(color='#D97706', label='西点服务'), Patch(color='#2563EB', label='东点需求窗口'),
                       Patch(color='#7C3AED', label='北点需求窗口'), Patch(color='#6B7280', label='转场'),
                       Patch(color='#E5E7EB', label='起飞准备 / 返航')],
              loc='lower right', frameon=False, ncol=5)
    fig.savefig(os.path.join(FIG, 'p3_relay_tl.png'), dpi=160); plt.close(fig); print('saved p3_relay_tl')

# ---------- 3) p3_comm_tl：通信保障方式时间线 ----------
def fig_comm_tl():
    from p3_gaps import flight_trajectory, direct_ok
    area_pos = {}
    for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
        area_pos[s] = 'W'
    for s in ['S010', 'S012', 'S013', 'S014']:
        area_pos[s] = 'E'
    area_pos['S004'] = 'N'
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
            c = {'直连': '#E5E7EB', 'W': '#D97706', 'E': '#2563EB', 'N': '#7C3AED'}[m]
            ax.barh(y, t1 - t0, left=t0, height=0.62, color=c,
                    edgecolor='white', linewidth=0.25, zorder=3 if m != '直连' else 2)
    ax.set_yticks(list(y_of.values())); ax.set_yticklabels(['f%02d' % f.fid for f in flights], fontsize=8)
    ax.set_xlabel('时间（s）'); ax.set_xlim(0, 7600)
    ax.legend(handles=[Patch(color='#E5E7EB', label='直连'), Patch(color='#D97706', label='中继 W 点'),
                       Patch(color='#2563EB', label='中继 E 点'), Patch(color='#7C3AED', label='中继 N 点')],
              loc='lower right', frameon=False, ncol=4)
    fig.savefig(os.path.join(FIG, 'p3_comm_tl.png'), dpi=160); plt.close(fig); print('saved p3_comm_tl')

# ---------- 4) p4_load：各组货箱数与总质量 ----------
def fig_p4_load():
    # 箱 -> 区 -> 组归属（24 架：f39 的 S006 1 箱归 G1，其余 S006 归 G2）
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
            g = 'G1'  # f39 顺访箱归西组
        g3[g][0] += 1
        g3[g][1] += mass[b]
    g2 = {'G1': g3['G1'][:], 'G2': [g3['G2'][0] + g3['G3'][0], g3['G2'][1] + g3['G3'][1]]}
    print('三组(箱,kg):', {k: v for k, v in g3.items()}, '两组:', g2)
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    cols = {'G1': ps.C_BLUE, 'G2': ps.C_ORANGE, 'G3': ps.C_VIOLET}
    for ax, dat in zip(axes, (g3, g2)):
        names = list(dat)
        x = np.arange(len(names))
        nb = [dat[n][0] for n in names]
        ms = [dat[n][1] for n in names]
        ax.bar(x - 0.19, nb, 0.38, color=[cols[n] for n in names], edgecolor='white', linewidth=0.5)
        for xi, v in zip(x, nb):
            ax.annotate('%d 箱' % v, (xi - 0.19, v), textcoords='offset points', xytext=(0, 3), ha='center', fontsize=8)
        ax2 = ax.twinx()
        ax2.bar(x + 0.19, ms, 0.38, color=[cols[n] for n in names], alpha=0.45, edgecolor='white', linewidth=0.5)
        for xi, v in zip(x, ms):
            ax2.annotate('%d kg' % v, (xi + 0.19, v), textcoords='offset points', xytext=(0, 3), ha='center', fontsize=8)
        ax.set_xticks(x); ax.set_xticklabels(names, fontsize=9)
        ax.set_ylabel('货箱数'); ax2.set_ylabel('总质量（kg）')
        ax.set_ylim(0, max(nb) * 1.25); ax2.set_ylim(0, max(ms) * 1.25)
        ax.set_xlabel('三组分区' if dat is g3 else '两组分区')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'p4_load.png'), dpi=160); plt.close(fig); print('saved p4_load')

# ---------- 5) p4_gap：库存 vs 配置缺口 ----------
def fig_p4_gap():
    labels = ['A 机', 'B 机', 'C 机', 'A 电', 'B 电', 'C 电', '中继', '组件']
    inv = [4, 2, 2, 6, 4, 4, 2, 6]
    k3 = [6, 5, 5, 8, 7, 6, 7, 10]
    k2 = [6, 5, 5, 8, 7, 7, 6, 10]
    x = np.arange(len(labels)); w = 0.26
    fig, ax = plt.subplots(figsize=(10.8, 4.6))
    ax.bar(x - w, inv, w, color='#E5E7EB', edgecolor='#9CA3AF', linewidth=0.5, label='给定库存')
    for K, vals, off, c in (('2', k2, 0, ps.C_BLUE), ('3', k3, w, ps.C_ORANGE)):
        bars = ax.bar(x + off, vals, w, color=c, alpha=0.85, edgecolor='white', linewidth=0.5, label='%s 组配置' % K)
        for xi, v, iv in zip(x + off, vals, inv):
            if v > iv:
                ax.annotate('+%d' % (v - iv), (xi, v), textcoords='offset points',
                            xytext=(0, 3), ha='center', fontsize=8, fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('数量'); ax.grid(axis='y')
    ax.legend(loc='upper left', frameon=False, ncol=3)
    fig.savefig(os.path.join(FIG, 'p4_gap.png'), dpi=160); plt.close(fig); print('saved p4_gap')

fig_pareto()
fig_relay_tl()
fig_comm_tl()
fig_p4_load()
fig_p4_gap()
print('ALL DONE')