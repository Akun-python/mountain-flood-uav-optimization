# -*- coding: utf-8 -*-
"""v108b：S004 趟详情 + E组航段明细 + 重叠期S004采样点分布。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
import p3_co2
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import OUTD
data = p3_co2.data
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
sch, _ = dispatch_compliant(data, fls)
starts = {fid: s['start'] for fid, s in sch.items()}
sv = p3_co2.Solver()
for f in fls:
    if f.fid == 4:
        print('f04: %s %s start=%.0f dur=%.0f ret=%.0f' % (f.model, [(z, b) for z, b in f.route], sch[4]['start'], f.duration(), sch[4]['return']))
        for z, bs in f.route:
            for b in bs:
                bx = data.boxes[b]
                print('   箱 %s 型=%s 时限首=%.0f 期望=%.0f' % (b, bx['type'], bx.get('deadline_first', 0), bx.get('deadline_exp', 0)))
# E组 missions
m_base = sv.build_missions(starts)
for m in sorted([m for m in m_base if m['grp']=='E'], key=lambda x: x['t0']):
    print('E mission fid=%d area=%s [%.0f,%.0f] 点%d cov%d' % (m['fid'], m['area'], m['t0'], m['t1'], m['n'], m['n_cov']))
# S004 采样点时间分布
sgs = [(t, cw, ce, cn) for t, sid, cw, ce, cn in sv.samples[4] if sid == 'S004']
print('S004-%d 采样点: 共%d 个, t范围 [%.0f, %.0f], 2562-3101重叠期内 %d 个 (W覆盖 %d)' % (
    len(sgs), len(sgs), sgs[0][0], sgs[-1][0],
    sum(1 for t, c, _, _ in sgs if 2562 <= t <= 3101),
    sum(1 for t, c, _, _ in sgs if 2562 <= t <= 3101 and c)))
# 这些点对应绝对时刻（start 偏移）
st4 = starts[4]
bs = [(st4 + t, cw) for t, cw, ce, cn in sgs if 2562 <= st4 + t <= 3101]
print('重叠期绝对时刻(W覆盖/总数): %d/%d, 最早%.0f 最晚%.0f' % (
    sum(1 for _, c in bs if c), len(bs), min(t for t, _ in bs), max(t for t, _ in bs)))
