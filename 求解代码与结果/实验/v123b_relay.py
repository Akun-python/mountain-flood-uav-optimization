# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join('求解代码与结果', '代码'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import plot_style as ps
FIG = 'figures'
fig, ax = plt.subplots(figsize=(10.8, 3.0))
rows = [('R1 中继 1', 0, 686, '起飞准备', '#E5E7EB'),
        ('R1 中继 1', 686, 6777, '西点服务', '#D97706'),
        ('R1 中继 1', 6777, 7077, '返航', '#E5E7EB'),
        ('R2 中继 2', 0, 760, '起飞准备', '#E5E7EB'),
        ('R2 中继 2', 760, 3354, '东点服务（需求窗口）', '#2563EB'),
        ('R2 中继 2', 2562, 3289, '北点服务（需求窗口）', '#7C3AED'),
        ('R2 中继 2', 3354, 3600, '返航', '#E5E7EB')]
for i, rid in enumerate(['R1 中继 1', 'R2 中继 2']):
    placed = []
    for nm, t0, t1, tag, c in rows:
        if nm != rid:
            continue
        if tag in ('起飞准备', '返航'):
            ax.barh(i, t1 - t0, left=t0, height=0.6, color=c, edgecolor='white', linewidth=0.4, zorder=3)
            placed.append((t0, t1))
            continue
        if any(not (t1 <= p0 or t0 >= p1) for p0, p1 in placed):
            continue
        ax.barh(i, t1 - t0, left=t0, height=0.6, color=c, edgecolor='white', linewidth=0.4, zorder=3)
        ax.text((t0 + t1) / 2, i, '%s\n[%d, %d]' % (tag.split('（')[0], t0, t1),
                ha='center', va='center', fontsize=8.2, color='white', zorder=4)
        placed.append((t0, t1))
ax.axvspan(2562, 3289, ymin=0.30, ymax=0.70, color='#F87171', alpha=0.30, zorder=2)
ax.text(2926, 1.42, 'E/N 需求重叠 727 s（机器级需协调）', ha='center', va='top', fontsize=8.2, color='#B91C1C', zorder=5)
ax.set_yticks([0, 1]); ax.set_yticklabels(['R1 中继 1', 'R2 中继 2'], fontsize=9)
ax.set_xlabel('时间（s）'); ax.set_xlim(0, 7600); ax.set_ylim(-0.45, 1.62); ax.grid(axis='x', alpha=0.35)
ax.legend(handles=[Patch(color='#D97706', label='西点服务'), Patch(color='#2563EB', label='东点需求窗口'),
                   Patch(color='#7C3AED', label='北点需求窗口'), Patch(color='#E5E7EB', label='起飞准备 / 返航')],
          loc='lower right', frameon=False, ncol=4)
fig.savefig(os.path.join(FIG, 'p3_relay_tl.png'), dpi=160)
plt.close(fig)
print('saved p3_relay_tl again')
