# -*- coding: utf-8 -*-
"""v93a：23/24/25 架结构瓶颈分析——池负载精确核算，找出 23 架完工 6680.6 的瓶颈池。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
data = Data()
N = {'A': 4, 'B': 2, 'C': 2}
d = json.load(open(os.path.join(OUTD, 'p2v88_fleet23.json'), encoding='utf-8'))
for s in d['solutions']:
    fls = [Flight(f['fid'], [(s2, list(bs)) for s2, bs in f['route']], f['model'], data) for f in s['solution']]
    m, sch, v, nc = eval_full(data, fls)
    pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}; cnt = {'A': 0, 'B': 0, 'C': 0}
    for f in fls:
        pt[f.model] += f.duration(); cnt[f.model] += 1
    print('%2d架 mk=%6.1f en=%6.2f | 池T/台 A%5.0f(%d趟) B%5.0f(%d趟) C%5.0f(%d趟) | 硬%s 违%d' % (
        s['flights'], s['makespan'], s['energy'],
        pt['A']/N['A'], cnt['A'], pt['B']/N['B'], cnt['B'], pt['C']/N['C'], cnt['C'],
        m['hard_ok'], v))
    # 23 架逐趟
    if s['flights'] == 23:
        print('  23架趟结构:')
        for f in sorted(fls, key=lambda x: x.fid):
            print('    f%02d %s %s %d箱 %5.0fs' % (f.fid, f.model, [z for z, _ in f.route], len(f.box_ids), f.duration()))
