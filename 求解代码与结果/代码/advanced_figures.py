# -*- coding: utf-8 -*-
"""高级图件套件：11 张补充图（无图内标题、300dpi、Okabe-Ito、中文字体）。

p1_lg_curve / p1_soc / p2_network / p2_battery / p2_delivery / p2_pareto2d
p3_margin_hist / p3_relay_tl / p3_comm_tl / p4_gap / p4_load
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import matplotlib.pyplot as plt
import plot_style as ps
from core import Data, flight_profile, charge_time, relay_mission_time, direct_ok

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')
FIG = os.path.join(ROOT, 'figures')
os.makedirs(FIG, exist_ok=True)
data = Data()

TYPE_SHORT = {'医疗物资': '医疗', '饮用水': '饮用水', '应急食品': '应急食品', '生活卫生用品': '生活卫生'}
TYPE_COLOR = {'医疗物资': ps.C_RED, '饮用水': ps.C_BLUE, '应急食品': ps.C_ORANGE, '生活卫生用品': ps.C_VIOLET}


def load(name):
    with open(os.path.join(RES, name), encoding='utf-8') as fh:
        return json.load(fh)


def save(fig, fname):
    fig.savefig(os.path.join(FIG, fname))
    plt.close(fig)
    print('saved', fname)


# ---------------- P1：等效航程与能量约束 ----------------
def fig1_lg_curve():
    qs = np.linspace(0.1, 1.0, 300)
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(10.2, 4.3),
                                   gridspec_kw={'width_ratios': [1, 1.25]})
    for g in ('A', 'B', 'C'):
        p = data.uav_types[g]
        q = qs * p['Q']
        lg = p['L0'] - (p['L0'] - p['LF']) * (q / p['Q']) ** 1.5
        axL.plot(q, lg, color=ps.MODEL_COLORS[g], lw=2.0,
                 label='%s 型，L0=%.0f m' % (g, p['L0']))
        axL.fill_between(q, lg, p['L0'], color=ps.MODEL_COLORS[g], alpha=0.08)
    axL.axvline(25, color=ps.C_BLUE, ls=':', lw=0.9, alpha=0.7)
    axL.axvline(30, color=ps.C_ORANGE, ls=':', lw=0.9, alpha=0.7)
    axL.axvline(80, color=ps.C_RED, ls=':', lw=0.9, alpha=0.7)
    axL.set_xlabel('载荷 q（kg）')
    axL.set_ylabel('等效航程 $L_g(q)$（m）')
    axL.set_ylim(0, 26000)
    axL.legend(loc='lower left', frameon=False)
    # 右侧：到 S008 往返的能耗-载荷曲线与能量上限
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
        axR.plot(qq, ee, color=ps.MODEL_COLORS[g], lw=2.0, label='%s 型' % g)
        axR.axhline(cap, color=ps.MODEL_COLORS[g], ls='--', lw=0.8, alpha=0.55)
        # 能量限制载荷：E(q*) = cap
        idx = np.searchsorted(ee, cap) - 1
        if 0 < idx < len(qq):
            q1, q2 = qq[idx], qq[idx + 1]
            e1, e2 = ee[idx], ee[idx + 1]
            qstar = q1 + (cap - e1) / (e2 - e1) * (q2 - q1)
            axR.scatter([qstar], [cap], s=46, color=ps.MODEL_COLORS[g], zorder=5,
                        edgecolor='white', linewidth=0.6)
            axR.annotate('q*=%.1f kg' % qstar, (qstar, cap),
                         textcoords='offset points', xytext=(6, 4),
                         fontsize=8.5, color='black')
    axR.set_xlabel('载荷 q（kg）')
    axR.set_ylabel('S008 往返能耗（kWh）')
    axR.set_xlim(0, 82)
    axR.legend(loc='upper left', frameon=False)
    fig.tight_layout()
    save(fig, 'p1_lg_curve.png')


# ---------------- P1：返航荷电状态 ----------------
def fig1_soc():
    r = load('p1_results.json')
    rows = []
    for area, g in r['grouping'].items():
        for d in g['detail']:
            rows.append((d['model'], d['energy']))
    rows.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(9.6, 4.2))
    x = np.arange(len(rows))
    soc = [1 - e / data.uav_types[m]['E_use'] for m, e in rows]
    colors = [ps.MODEL_COLORS[m] for m, _ in rows]
    ax.bar(x, [s * 100 for s in soc], color=colors, edgecolor='white', linewidth=0.5)
    ax.axhline(20, color=ps.C_RED, ls='--', lw=1.1)
    ax.text(len(x) - 0.5, 21.5, '返航安全下限 20%', fontsize=8.5, color='black', ha='right')
    ax.set_xlabel('架次（按能耗升序）')
    ax.set_ylabel('返航荷电状态（%）')
    ax.set_ylim(0, 100)
    ax.set_xticks(range(0, len(x), 2))
    ax.set_xticklabels([str(i + 1) for i in range(0, len(x), 2)], fontsize=8.5)
    ax.grid(axis='y')
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ps.C_BLUE, label='A 型'), Patch(color=ps.C_ORANGE, label='B 型'),
                       Patch(color=ps.C_RED, label='C 型')],
              loc='upper right', frameon=False, ncol=3)
    save(fig, 'p1_soc.png')


# ---------------- P2：航线网络图 ----------------
def fig2_network():
    r = load('p2_pareto.json')['balanced']
    o = data.centers['O01']
    lons = [o['lon']] + [a['lon'] for a in data.areas.values()]
    lats = [o['lat']] + [a['lat'] for a in data.areas.values()]
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
    fig, ax = plt.subplots(figsize=(9.4, 7.6))
    ax.pcolormesh(X, Y, dem, cmap='terrain', shading='auto', vmin=50, vmax=800)
    for f in sorted(r['flights'], key=lambda x: x['fid']):
        pts = [(o['lon'], o['lat'])] + [(data.areas[s]['lon'], data.areas[s]['lat'])
                                        for s, _ in f['route']] + [(o['lon'], o['lat'])]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, color=ps.MODEL_COLORS[f['model']], lw=1.1, alpha=0.55,
                solid_capstyle='round', zorder=3)
    ax.scatter([o['lon']], [o['lat']], marker='*', s=260, color=ps.C_RED,
               edgecolor='white', linewidth=0.7, zorder=7, label='调度中心 O01')
    for sid in sorted(data.areas):
        a = data.areas[sid]
        ax.scatter([a['lon']], [a['lat']], s=26, color=ps.C_BLACK,
                   edgecolor='white', linewidth=0.5, zorder=6)
        ax.annotate(sid, (a['lon'], a['lat']), textcoords='offset points',
                    xytext=(4, 3), fontsize=8, color='black')
    from matplotlib.lines import Line2D
    hd = [Line2D([0], [0], color=ps.C_BLUE, lw=1.8, label='A 型航线'),
          Line2D([0], [0], color=ps.C_ORANGE, lw=1.8, label='B 型航线'),
          Line2D([0], [0], color=ps.C_RED, lw=1.8, label='C 型航线')]
    ax.legend(handles=hd, loc='lower left', frameon=False, fontsize=9)
    ax.set_xlabel('经度（°E）')
    ax.set_ylabel('纬度（°N）')
    save(fig, 'p2_network.png')


# ---------------- P2：电池时间线 ----------------
def fig2_battery():
    r = load('p2_pareto.json')['balanced']
    flights = sorted(r['flights'], key=lambda x: x['start'])
    batches = data.batteries
    lanes = sorted({f['battery'] for f in flights})
    lane_y = {b: i for i, b in enumerate(lanes)}
    fig, ax = plt.subplots(figsize=(10.6, 6.4))
    tmax = r['metrics']['makespan'] + 400
    rets = {}
    for f in flights:
        b = f['battery']
        soc_end = 1 - f['energy'] / data.uav_types[f['model']]['E_use']
        t_full = batches[f['model']]['T_full']
        ready = f['return'] + charge_time(soc_end, t_full)
        y = lane_y[b]
        ax.barh(y, f['return'] - f['start'], left=f['start'], height=0.62,
                color=ps.MODEL_COLORS[f['model']], edgecolor='white', linewidth=0.4, zorder=3)
        # 充电段
        ax.barh(y, ready - f['return'], left=f['return'], height=0.62,
                color='#D1D5DB', alpha=0.85, hatch='//', edgecolor='white',
                linewidth=0.3, zorder=2)
    ax.set_yticks(list(lane_y.values()))
    ax.set_yticklabels(lanes, fontsize=8.5)
    ax.set_xlabel('时间（s）')
    ax.set_ylabel('电池编号')
    ax.set_xlim(0, tmax)
    ax.grid(axis='x', alpha=0.3)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ps.C_BLUE, label='A 型任务'),
                       Patch(color=ps.C_ORANGE, label='B 型任务'),
                       Patch(color=ps.C_RED, label='C 型任务'),
                       Patch(color='#D1D5DB', label='充电段')],
              loc='lower right', frameon=False, ncol=4)
    save(fig, 'p2_battery.png')


# ---------------- P2：逐箱交付时刻 vs 时限 ----------------
def fig2_delivery():
    r = load('p2_pareto.json')['balanced']
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    tmax = 0.0
    margin_min = 1e9
    tight = None
    for dbox in r['deliveries']:
        bx = data.boxes[dbox['box']]
        ddl = bx['deadline_first'] if bx['first_batch'] else bx['deadline_exp']
        t = dbox['t']
        tmax = max(tmax, ddl, t)
        mk = 'o' if bx['first_batch'] else 's'
        ax.scatter([t], [ddl], s=34, marker=mk, color=TYPE_COLOR[bx['type']], alpha=0.85,
                   edgecolor='white', linewidth=0.3, zorder=3)
        m = ddl - t
        if m < margin_min:
            margin_min, tight = m, dbox['box']
    ax.axline((0, 0), slope=1, color='#6B7280', ls='--', lw=1.0)
    ax.text(tmax * 0.86, tmax * 0.80, '交付时刻等于时限', fontsize=8.5,
            color='black', rotation=35, ha='center')
    ax.annotate('最紧裕度 %d s（%s）' % (round(margin_min), tight),
                xy=(tmax * 0.965, margin_min + (tmax - margin_min) * 0.015),
                xytext=(tmax * 0.6, margin_min + tmax * 0.10),
                arrowprops=dict(arrowstyle='->', lw=0.9, color='#374151'),
                fontsize=8.5, color='black')
    ax.set_xlim(0, tmax * 1.02)
    ax.set_ylim(0, tmax * 1.02)
    ax.set_xlabel('交付完成时刻（s）')
    ax.set_ylabel('配送时限（s）')
    from matplotlib.lines import Line2D
    hd = [Line2D([0], [0], marker='o', ls='', color=c, label=n)
          for n, c in TYPE_COLOR.items()]
    hd += [Line2D([0], [0], marker='o', ls='', color='#333333', label='首飞批'),
           Line2D([0], [0], marker='s', ls='', color='#333333', label='普通批')]
    ax.legend(handles=hd, loc='upper left', frameon=False, ncol=2, fontsize=8.5)
    save(fig, 'p2_delivery.png')


# ---------------- P2：多目标权衡气泡 ----------------
def fig2_pareto():
    r = load('p2_pareto.json')
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    names = {'balanced': '完工冠军（本文）', 'min_flights': '节能均衡（21 架）',
             'min_makespan': '最短完工（26 架）', 'min_energy': '最低能耗（19 架）'}
    mk = {'balanced': 'o', 'min_flights': '^', 'min_makespan': 'D', 'min_energy': 's'}
    colors = {'balanced': ps.C_GREEN, 'min_flights': ps.C_BLUE,
              'min_makespan': ps.C_ORANGE, 'min_energy': ps.C_VIOLET}
    for k, v in r.items():
        m = v['metrics']
        ax.scatter(m['makespan'], m['energy'], s=m['flights'] * 26, marker=mk[k],
                   color=colors[k], edgecolor='white', linewidth=0.7, alpha=0.85, zorder=3)
        ax.annotate('%s\n%d 架次 / 迟到 %g' % (names[k], m['flights'], m['tardy_w']),
                    (m['makespan'], m['energy']), textcoords='offset points',
                    xytext=(12, 8), fontsize=8.5, color='black')
    for k in ('min_flights', 'min_energy'):
        m = r[k]['metrics']
        ax.scatter(m['makespan'], m['energy'], s=180, marker='x', color=colors[k], zorder=2)
    ax.set_xlabel('完工时间（s）')
    ax.set_ylabel('总能耗（kWh）')
    ax.grid(alpha=0.4)
    save(fig, 'p2_pareto2d.png')


# ---------------- P3：链路余量分布 ----------------
def fig3_margin_hist():
    r = load('p3_margins.json')
    fig, axes = plt.subplots(1, 3, figsize=(11.6, 3.6), sharey=True)
    for ax, g in zip(axes, 'WEN'):
        s = r[g]
        ax.hist(s['samples'], bins=np.arange(0, 34, 1), color=ps.AREA_COLORS[g],
                edgecolor='white', linewidth=0.4, alpha=0.92)
        ax.axvline(1.0, color='#6B7280', ls='--', lw=0.9)
        ax.axvline(s['min'], color=ps.C_BLACK, ls=':', lw=0.9)
        ax.text(0.98, 0.92, '%s 点\nn=%d\n最紧 %.1f dB' % (g, s['n'], s['min']),
                transform=ax.transAxes, ha='right', va='top', fontsize=8.5,
                color=ps.C_BLACK)
        if g == 'W':
            ax.text(1.2, ax.get_ylim()[1] * 0.6, '1 dB\n下压线', fontsize=8, color='black')
        ax.set_xlabel('接入链路余量（dB）')
    axes[0].set_ylabel('采样点数')
    fig.tight_layout()
    save(fig, 'p3_margin_hist.png')


# ---------------- P3：中继时序 ----------------
def fig3_relay_tl():
    r = load('p3_final.json')
    fig, ax = plt.subplots(figsize=(10.6, 3.4))
    rows = []
    n1 = n2 = 0
    for k, sg in enumerate(r['sorties'], start=1):
        relay = sg['relay']
        pos = sg['pos']
        if relay == 'R01':
            n1 += 1
            rid = 'R1-0%d' % n1
        else:
            n2 += 1
            rid = 'R2-0%d' % n2
        rows.append((rid, pos, sg))
    for i, (rid, pos, sg) in enumerate(rows):
        y = len(rows) - 1 - i
        t0, t1 = sg['t0'], sg['t1']
        # 起飞准备与建链（t0 之前）
        dep = t0 - 30.0
        ax.barh(y, t0 - dep, left=dep, height=0.5, color='#E5E7EB',
                edgecolor='#9CA3AF', linewidth=0.4, zorder=2)
        ax.barh(y, t1 - t0, left=t0, height=0.5, color=ps.AREA_COLORS[pos],
                edgecolor='white', linewidth=0.4, zorder=3)
        # 返航段
        ax.barh(y, 300, left=t1, height=0.5, color='#E5E7EB',
                edgecolor='#9CA3AF', linewidth=0.4, zorder=2)
        seg = len(sg['missions'])
        ax.text(t0, y + 0.55, '%s 点 %d 段  %d s' % (pos, seg, round(t1 - t0)),
                fontsize=8, va='bottom', color='black')
        ax.text(t1 + 310, y, '能耗 %.2f kWh' % sg['energy'], fontsize=8.5,
                va='center', ha='left', color='black')
        ax.text(dep - 120, y, rid, fontsize=9, va='center', ha='right',
                color='black', fontweight='bold')
    # W 点占空比标注（数据驱动）
    ax.axhline(len(rows) - 0.5, color='#6B7280', ls=':', lw=0.7)
    w0 = next(sg for sg in r['sorties'] if sg['relay'] == 'R01' and sg['pos'] == 'W')
    ax.text(8800, len(rows) - 0.62,
            'W 点最长服务 %.0f s（%.0f 个任务段）\n能耗 %.2f kWh，返航荷电约 %.1f%%'
            % (w0['t1'] - w0['t0'], len(w0['missions']), w0['energy'],
               100 * (1 - w0['energy'] / 3.2)),
            fontsize=8, color='black', va='top', ha='right')
    ax.set_yticks([len(rows) - 1 - i for i in range(len(rows))])
    ax.set_yticklabels([rid for rid, _, _ in rows], fontsize=9)
    ax.set_xlabel('时间（s）')
    ax.set_xlim(0, 9800)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ps.AREA_COLORS['W'], label='西点服务'),
                       Patch(color=ps.AREA_COLORS['E'], label='东点服务'),
                       Patch(color=ps.AREA_COLORS['N'], label='北点服务'),
                       Patch(color='#E5E7EB', label='起飞准备 / 返航')],
              loc='lower right', frameon=False, ncol=4)
    save(fig, 'p3_relay_tl.png')


# ---------------- P3：通信保障方式时间线 ----------------
def fig3_comm_tl():
    r = load('p3_final.json')
    sched = r['schedule']
    pos_pt = {'W': (109.2103, 23.047134, 676.5),
              'E': (109.276017, 23.019401, 542.3),
              'N': (109.238171, 23.077841, 496.1)}
    area_pos = {s: 'W' for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']}
    for s in ['S010', 'S012', 'S013', 'S014']:
        area_pos[s] = 'E'
    area_pos['S004'] = 'N'
    from p2_solve import Flight
    from p3_gaps import flight_trajectory
    flights = sorted(r['flights'], key=lambda x: x['fid'])
    fig, ax = plt.subplots(figsize=(11.4, 7.8))
    y_of = {f['fid']: i for i, f in enumerate(flights)}
    for f in flights:
        y = y_of[f['fid']]
        fl = Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
        pts, _ = flight_trajectory(fl, sched[str(f['fid'])]['start'])
        mode = []
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                mode.append('直连')
            else:
                sid = min(data.areas, key=lambda s: data.dist_ll(
                    pt['lon'], pt['lat'], data.areas[s]['lon'], data.areas[s]['lat']))
                mode.append(area_pos.get(sid, '直连'))
        # 合并连续相同模式的段
        seg = []
        for pt, m in zip(pts, mode):
            if seg and seg[-1][2] == m:
                seg[-1][1] = pt['t']
            else:
                seg.append([pt['t'], pt['t'], m])
        for t0, t1, m in seg:
            c = {'直连': '#E5E7EB', 'W': ps.AREA_COLORS['W'],
                 'E': ps.AREA_COLORS['E'], 'N': ps.AREA_COLORS['N']}[m]
            ax.barh(y, t1 - t0, left=t0, height=0.62, color=c,
                    edgecolor='white', linewidth=0.25, zorder=3 if m != '直连' else 2)
    ax.set_yticks(list(y_of.values()))
    ax.set_yticklabels(['f%02d' % fid for fid in y_of], fontsize=8)
    ax.set_xlabel('时间（s）')
    ax.set_xlim(0, 9600)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color='#E5E7EB', label='直连'),
                       Patch(color=ps.AREA_COLORS['W'], label='中继 W 点'),
                       Patch(color=ps.AREA_COLORS['E'], label='中继 E 点'),
                       Patch(color=ps.AREA_COLORS['N'], label='中继 N 点')],
              loc='lower right', frameon=False, ncol=4)
    save(fig, 'p3_comm_tl.png')


# ---------------- P4：资源缺口 ----------------
def fig4_gap():
    r = load('p4_results.json')
    inv = r.get('inventory', {'A': 4, 'B': 2, 'C': 2, 'A_bat': 6, 'B_bat': 4, 'C_bat': 4,
                              'relay': 2, 'comp': 6})
    labels = ['A 型机', 'B 型机', 'C 型机', 'A 电池', 'B 电池', 'C 电池', '中继', '能源组件']
    inv_v = [inv['A'], inv['B'], inv['C'], inv['A_bat'], inv['B_bat'], inv['C_bat'],
             inv['relay'], inv['comp']]
    tot = {}
    for K in ('2', '3'):
        au = {'A': 0, 'B': 0, 'C': 0}
        ab = {'A': 0, 'B': 0, 'C': 0}
        ar = ac = 0
        for g in r[K]['groups']:
            for t, v in g['alloc_uav'].items():
                au[t] += v
            for t, v in g['alloc_bat'].items():
                ab[t] += v
            ar += g['alloc_relay']
            ac += g['alloc_comp']
        tot[K] = [au['A'], au['B'], au['C'], ab['A'], ab['B'], ab['C'], ar, ac]
    x = np.arange(len(labels))
    w = 0.26
    fig, ax = plt.subplots(figsize=(10.8, 4.6))
    ax.bar(x - w, inv_v, w, color='#E5E7EB', edgecolor='#9CA3AF', linewidth=0.5,
           label='给定库存')
    for K, off, c in (('2', 0, ps.C_BLUE), ('3', w, ps.C_ORANGE)):
        vals = tot[K]
        bars = ax.bar(x + off, vals, w, color=c, alpha=0.85, edgecolor='white',
                      linewidth=0.5, label='%s 组配置' % K)
        for xi, v, iv in zip(x + off, vals, inv_v):
            if v > iv:
                ax.annotate('+%d' % (v - iv), (xi, v), textcoords='offset points',
                            xytext=(0, 3), ha='center', fontsize=8, color='black',
                            fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('数量')
    ax.grid(axis='y')
    ax.legend(loc='upper left', frameon=False, ncol=3)
    save(fig, 'p4_gap.png')


# ---------------- P4：分组负荷 ----------------
def fig4_load():
    r = load('p4_results.json')
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), sharex=False)
    cols = {'G1': ps.C_BLUE, 'G2': ps.C_ORANGE, 'G3': ps.C_VIOLET}
    for ax, K in zip(axes, ('3', '2')):
        gs = r[K]['groups']
        x = np.arange(len(gs))
        nb = [g['nbox'] for g in gs]
        ms = [g['mass'] for g in gs]
        bars = ax.bar(x - 0.19, nb, 0.38, color=[cols[g['name']] for g in gs],
                      edgecolor='white', linewidth=0.5, label='货箱数')
        for xi, v, g in zip(x, nb, gs):
            ax.annotate('%d 箱' % v, (xi - 0.19, v), textcoords='offset points',
                        xytext=(0, 3), ha='center', fontsize=8)
        ax2 = ax.twinx()
        ax2.bar(x + 0.19, ms, 0.38, color=[cols[g['name']] for g in gs], alpha=0.45,
                edgecolor='white', linewidth=0.5)
        for xi, v in zip(x, ms):
            ax2.annotate('%d kg' % v, (xi + 0.19, v), textcoords='offset points',
                         xytext=(0, 3), ha='center', fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(['%s\n（%s）' % (g['name'], '、'.join(g['areas'][:3]) + ('…' if len(g['areas']) > 3 else ''))
                            for g in gs], fontsize=8)
        ax.set_ylabel('货箱数')
        ax2.set_ylabel('总质量（kg）')
        ax.set_ylim(0, max(nb) * 1.25)
        ax2.set_ylim(0, max(ms) * 1.25)
        ax.set_xlabel('%s 组分区' % K)
    fig.tight_layout()
    save(fig, 'p4_load.png')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--fig', action='append', default=[],
                    help='只生成指定图（可多次），例如 --fig p2_battery --fig p2_pareto2d')
    args = ap.parse_args()
    all_figs = [fig1_lg_curve, fig1_soc, fig2_network, fig2_battery,
                fig2_delivery, fig2_pareto, fig3_margin_hist, fig4_gap, fig4_load]
    wanted = set(args.fig)
    for fn in all_figs:
        if wanted and fn.__name__ not in wanted:
            continue
        try:
            fn()
        except Exception as e:
            print('skip %s: %s' % (fn.__name__, e))
    print('advanced figures done')