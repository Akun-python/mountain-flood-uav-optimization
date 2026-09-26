# -*- coding: utf-8 -*-
"""v108a：中继2架机器约束复核——E/N重叠[2562,3101]内 S004 航段能否由 W(R01) 覆盖；重排 R02 时序求可执行排班。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
import p3_co2
from p2_solve import Flight, evaluate
from p2v28_compliant import dispatch_compliant
from audit_results import check_battery as cb
from dqn23_enhanced import OUTD
data = p3_co2.data
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
sch, _ = dispatch_compliant(data, fls)
starts = {fid: s['start'] for fid, s in sch.items()}
sv = p3_co2.Solver()
m_base = sv.build_missions(starts)
cov_bad = sum(1 for m in m_base if m['n_cov'] < m['n'])
mp, minfo, esum = sv.machine_penalty(m_base)
print('v92基线: 覆盖不良%d 机器罚%.1f 能耗%.3f' % (cov_bad, mp, esum))
print('  minfo:', {g: [(round(a),round(b)) for a,b in lst] for g, lst in minfo.items()})
# S004(N组) 的 mission 明细 + 每 mission 的 W 覆盖比例
print('== N组(E/N重叠期) 检查 ==')
n_ms = [m for m in m_base if m['grp'] == 'N']
e_span = (min(m['t0'] for m in m_base if m['grp']=='E'), max(m['t1'] for m in m_base if m['grp']=='E'))
GRP_ALT = {'W': 1, 'E': 2, 'N': 3}  # samples raw index cw=2, ce=3, cn=4 (tuple idx1..)
def wcov_of(m):
    arr = sv.samples[m['fid']]
    sgs = sorted(set((t, (cw, ce, cn)) for (t, sid, cw, ce, cn) in arr if sid == m['area']))
    sgs2 = [(t, cw, ce, cn) for t, sid, cw, ce, cn in arr if sid == m['area'] and m['t0'] <= t + starts[m['fid']] - sv.base[m['fid']] + sv.base[m['fid']] <= m['t1']]
    return sgs2
for m in sorted(n_ms, key=lambda x: x['t0']):
    sgs = [(t, cw, ce, cn) for t, sid, cw, ce, cn in sv.samples[m['fid']] if sid == m['area']]
    n = len(sgs)
    cw = sum(1 for _, c1, c2, c3 in sgs if c1)
    ce = sum(1 for _, c1, c2, c3 in sgs if c2)
    print('  N/area=%s fid=%d [%.0f,%.0f] 点%d W覆盖%d/%d E覆盖%d' % (m['area'], m['fid'], m['t0'], m['t1'], n, cw, n, ce))
print('E区间:', (round(e_span[0]), round(e_span[1])))
