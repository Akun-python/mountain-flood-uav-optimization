# -*- coding: utf-8 -*-
"""v91：问题三重审——把新 25 架冠军（6571.4s）喂给 p3_co2 中继链路：覆盖审核 + 中继时段/能耗重算。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
import p3_co2
from p2_solve import Flight, dispatch, evaluate
from dqn23_enhanced import OUTD
data = p3_co2.data
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
schedule, _ = dispatch(data, fls)
met = evaluate(data, fls, schedule)
sv = p3_co2.Solver()
m_base = sv.build_missions(dict(sv.base))
cov_bad = sum(1 for m in m_base if m['n_cov'] < m['n'])
mp, minfo, esum = sv.machine_penalty(m_base)
n_need = sum(m['n'] for m in m_base)
print('运输: %d架 mk=%.1f en=%.2f hard=%s' % (met['flights'], met['makespan'], met['energy'], met['hard_ok']))
print('中继: 需点%d 覆盖不良%d 罚%.1f' % (n_need, cov_bad, mp))
REL = data.relay_type
EB = (1 - REL['rho']) * REL['E_use']
sorties = []
relay_e = 0.0
for k, (g, lst) in enumerate(minfo.items()):
    if not lst: continue
    t0 = min(x[0] for x in lst); t1 = max(x[1] for x in lst)
    e = p3_co2.relay_mission_energy(*p3_co2.POS_OF[g], data, t1 - t0)
    relay_e += e
    sorties.append({'pos': g, 't0': t0, 't1': t1, 'dur': t1 - t0, 'energy': round(e, 3), 'ok': bool(e <= EB + 1e-9)})
    print('  中继%s: [%.0f, %.0f] 时长%.0f 能耗%.3f 上限%.1f ok=%s' % (g, t0, t1, t1 - t0, e, EB, e <= EB + 1e-9))
jc = max(met['makespan'], max(s['t1'] + 300 for s in sorties))
print('联合完工 = %.1f (运输%.1f vs 中继最后%.1f+300)' % (jc, met['makespan'], max(s['t1'] for s in sorties)))
json.dump({'solver': 'v91-p2v89', 'met': {'hard_ok': met['hard_ok'], 'makespan': round(met['makespan'], 1),
    'energy': round(met['energy'], 2), 'flights': met['flights']},
    'n_need_relay': n_need, 'cov_bad': cov_bad, 'mpen': round(mp, 1),
    'relay_energy': round(relay_e, 3), 'joint_makespan': round(jc, 1),
    'sorties': sorties},
    open(os.path.join(OUTD, 'p3v91_review.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p3v91_review.json')
