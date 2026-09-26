# -*- coding: utf-8 -*-
"""v77：冠军瓶颈解剖——逐趟明细 + 池负载精确核算 + 完工-池负载差额来源分析。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v75_champion.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m, sch, v, nc = eval_full(data, fls)
print('完工 %.1f 能耗 %.2f 硬=%s 违规%d' % (m['makespan'], m['energy'], m['hard_ok'], v))
print()
print('== 逐趟明细（fid 机 区 箱数 质量kg 时长s 能耗）==')
for f in sorted(fls, key=lambda x: x.fid):
    z = f.route[0][0]
    print('  %2d %s %s %2d箱 %5.1fkg %6.0fs %5.2fkWh' % (f.fid, f.model, z, len(f.box_ids), f.total_mass, f.duration(), f.energy()))
print()
# 池负载
pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}
en_p = {'A': 0.0, 'B': 0.0, 'C': 0.0}
N = {'A': 4, 'B': 2, 'C': 2}
rows = {'A': [], 'B': [], 'C': []}
for f in fls:
    pt[f.model] += f.duration(); en_p[f.model] += f.energy()
    rows[f.model].append(f.duration())
print('池 T/台:', {g: '%.0f (池总%.0f/台%d)' % (pt[g]/N[g], pt[g], N[g]) for g in 'ABC'})
print('池能耗:', {g: '%.2f' % en_p[g] for g in 'ABC'})
# 最长池趟分析（瓶颈趟）
for g in 'ABC':
    rr = sorted(rows[g], reverse=True)
    print('  %s池趟时长排序: %s' % (g, ['%.0f' % x for x in rr]))
# 分析完工-池T/台差额：C 池 5990 是 max，完工 6571.4-5990=581.4
maxp = max(pt[g]/N[g] for g in 'ABC')
print('完工-最大池T/台 = %.1f' % (m['makespan'] - maxp))
# 调度首趟开始时间与最后结束检查
if sch:
    st = min(x[1] for x in sch) if sch else 0
    en_t = max(x[2] for x in sch) if sch else 0
    print('调度窗: 开始%.0f 结束%.0f (跨度%.0f)' % (st, en_t, en_t - st))
    # 电池相关（充电等待）
    print('调度条数 %d' % len(sch))
