# -*- coding: utf-8 -*-
"""v117：问题三重算——24架冠军(v113)航班时刻 → 中继窗口/覆盖/能耗/联合完工（v92口径）。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
import p3_co2
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import OUTD
data = p3_co2.data
d = json.load(open('求解代码与结果/结果/进化_v25/v113_best.json', encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
sch, _ = dispatch_compliant(data, fls)
starts = {fid: s['start'] for fid, s in sch.items()}
sv = p3_co2.Solver()
m_base = sv.build_missions(starts)
cov_bad = sum(1 for m in m_base if m['n_cov'] < m['n'])
mp, minfo, esum = sv.machine_penalty(m_base)
n_need = sum(m['n'] for m in m_base)
print('24架: 需点%d 覆盖不良%d 机器罚%.1f' % (n_need, cov_bad, mp), flush=True)
REL = data.relay_type
EB = (1 - REL['rho']) * REL['E_use']
sorties = []; relay_e = 0.0
for k, (g, lst) in enumerate(minfo.items()):
    if not lst: continue
    t0 = min(x[0] for x in lst); t1 = max(x[1] for x in lst)
    e = p3_co2.relay_mission_energy(*p3_co2.POS_OF[g], data, t1 - t0)
    relay_e += e
    sorties.append({'pos': g, 't0': t0, 't1': t1, 'dur': t1 - t0, 'energy': round(e, 3), 'ok': bool(e <= EB + 1e-9)})
    print('  中继%s: [%.0f, %.0f] 时长%.0f 能耗%.3f ok=%s' % (g, t0, t1, t1 - t0, e, e <= EB + 1e-9), flush=True)
m = json.load(open('求解代码与结果/结果/进化_v25/v113_best.json', encoding='utf-8'))
import p2_solve
mm = None
from dqn23_enhanced import eval_full
mm2, s2, v2, n2 = eval_full(data, fls)
jc = max(mm2['makespan'], max(s['t1'] + 300 for s in sorties))
print('运输 mk=%.1f en=%.2f | 中继能耗=%.3f | 联合完工=%.1f(+)' % (mm2['makespan'], mm2['energy'], relay_e, jc), flush=True)
json.dump({'solver': 'v117-24flight', 'met': {'hard_ok': bool(mm2['hard_ok']), 'makespan': round(mm2['makespan'],1),
    'energy': round(mm2['energy'],2), 'flights': len(fls)},
    'n_need_relay': n_need, 'cov_bad': cov_bad, 'mpen': round(mp,1),
    'relay_energy': round(relay_e,3), 'joint_makespan': round(jc,1), 'sorties': sorties},
    open(os.path.join(OUTD, 'p3v117_24f.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p3v117_24f.json')
