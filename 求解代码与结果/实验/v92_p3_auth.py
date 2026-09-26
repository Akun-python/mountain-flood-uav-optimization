# -*- coding: utf-8 -*-
"""v92：权威口径问题三重审——用 dispatch_compliant 的 schedule 时刻喂 p3_co2，重算中继时段/联合完工。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
import p3_co2
from p2_solve import Flight, evaluate
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
from p2v28_compliant import dispatch_compliant
data = p3_co2.data
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
# 权威口径调度
sch, _ = dispatch_compliant(data, fls)
m, s2, v, nc = eval_full(data, fls)
vb = cb(data, sch, fls)
print('权威运输: %d架 mk=%.1f en=%.2f hard=%s 电池%d' % (len(fls), m['makespan'], m['energy'], m['hard_ok'], len(vb)))
starts = {fid: s['start'] for fid, s in sch.items()}
sv = p3_co2.Solver()
m_base = sv.build_missions(starts)
cov_bad = sum(1 for mm2 in m_base if mm2['n_cov'] < mm2['n'])
mp, minfo, esum = sv.machine_penalty(m_base)
n_need = sum(mm2['n'] for mm2 in m_base)
print('中继: 需点%d 覆盖不良%d 罚%.1f' % (n_need, cov_bad, mp))
REL = data.relay_type
EB = (1 - REL['rho']) * REL['E_use']
sorties = []; relay_e = 0.0
for k, (g, lst) in enumerate(minfo.items()):
    if not lst: continue
    t0 = min(x[0] for x in lst); t1 = max(x[1] for x in lst)
    e = p3_co2.relay_mission_energy(*p3_co2.POS_OF[g], data, t1 - t0)
    relay_e += e
    sorties.append({'pos': g, 't0': t0, 't1': t1, 'dur': t1 - t0, 'energy': round(e, 3), 'ok': bool(e <= EB + 1e-9)})
    print('  中继%s: [%.0f, %.0f] 时长%.0f 能耗%.3f 上限%.1f ok=%s' % (g, t0, t1, t1 - t0, e, EB, e <= EB + 1e-9))
jc = max(m['makespan'], max(s['t1'] + 300 for s in sorties))
print('联合完工 = %.1f (运输%.1f vs 中继最后%.1f+300)' % (jc, m['makespan'], max(s['t1'] for s in sorties)))
json.dump({'solver': 'v92-authoritative', 'met': {'hard_ok': bool(m['hard_ok']), 'makespan': round(m['makespan'], 1),
    'energy': round(m['energy'], 2), 'flights': len(fls)},
    'n_need_relay': n_need, 'cov_bad': cov_bad, 'mpen': round(mp, 1),
    'relay_energy': round(relay_e, 3), 'joint_makespan': round(jc, 1), 'sorties': sorties},
    open(os.path.join(OUTD, 'p3v92_review.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p3v92_review.json')
