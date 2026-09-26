# -*- coding: utf-8 -*-
"""生成 24 架冠军（v113_best）调度明细 LaTeX 表（tab:p2flights 替换内容）。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'v113_best.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
mm, sch, v, nc = eval_full(data, fls)
print('mk=%.1f en=%.2f vv=%d nn=%d' % (mm['makespan'], mm['energy'], v, nc))
rows = []
for f in sorted(fls, key=lambda x: x.fid):
    s = sch[f.fid]
    zs = ' $|$ '.join('%s' % z for z, _ in f.route)
    rows.append((f.fid, f.model, s['uav'].split('-')[0] if '-' in s['uav'] else s['uav'], s['start'], s['return'], f.energy(), zs))
out = []
out.append('\\begin{longtable}{cccllcl}')
out.append('\\caption{精炼冠军 24 架次调度明细（区一致零违例；时刻单位 s，能耗单位 kWh）}')
out.append('\\label{tab:p2flights}\\\\')
out.append('\\toprule 架次 & 机型 & 无人机 & 开始时刻 & 返场时刻 & 能耗 & 服务区 \\\\ \\midrule \\endfirsthead')
out.append('\\toprule 架次 & 机型 & 无人机 & 开始时刻 & 返场时刻 & 能耗 & 服务区 \\\\ \\midrule \\endhead')
for fid, gm, uav, st, rt, en, zs in rows:
    out.append('f%02d & %s & %s & %d & %d & %.2f & %s \\\\' % (fid, gm, uav, st, rt, en, zs))
out.append('\\bottomrule')
out.append('\\end{longtable}')
open('求解代码与结果/结果/进化_v25/p2flights24_tab.tex', 'w', encoding='utf-8').write('\n'.join(out))
print('生成 %d 行' % len(rows))
# 能耗构成
ce = sum(f.energy() for f in fls if f.model == 'C')
ae = sum(f.energy() for f in fls if f.model == 'A')
be = sum(f.energy() for f in fls if f.model == 'B')
tot = ce + ae + be
print('C=%.2f(%.1f%%) A=%.2f(%.1f%%) B=%.2f(%.1f%%) 总=%.2f' % (ce, 100*ce/tot, ae, 100*ae/tot, be, 100*be/tot, tot))