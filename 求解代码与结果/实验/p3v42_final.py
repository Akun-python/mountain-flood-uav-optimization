# -*- coding: utf-8 -*-
"""v42 P3 权威：29 架基线派单即全覆盖（cover_bad=0），无需偏移。
联合完工 = 运输完工 7112.8s；中继三班 W[716,6777]/E[760,3354]/N[2638,3365]，
能耗 2.082/0.986/0.483（合计 3.551 kWh）全部 <= E_BUDGET。写 p3v42_final.json。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
import p3_co2
from p2_solve import Flight, dispatch, evaluate

data = p3_co2.data
OUTV = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '结果', '进化_v42')
tmpdir = os.path.join(OUTV, 'p3in')
p3_co2.OUT = tmpdir

sol = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                  '结果', '进化_v25', 'p2v41_mk_tol6_0.json'),
                     encoding='utf-8'))['solution']
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in sol]
schedule, _ = dispatch(data, fls)
met = evaluate(data, fls, schedule)

sv = p3_co2.Solver()
m_base = sv.build_missions(dict(sv.base))
cov_bad = sum(1 for m in m_base if m['n_cov'] < m['n'])
mp, minfo, esum = sv.machine_penalty(m_base)
n_need = sum(m['n'] for m in m_base)

BANDS = {'W': (716, 6777), 'E': (760, 3354), 'N': (2638, 3365)}
REL = data.relay_type
EB = (1 - REL['rho']) * REL['E_use']
sorties = []
relay_e = 0.0
for k, (g, (t0, t1)) in enumerate(BANDS.items()):
    e = p3_co2.relay_mission_energy(*p3_co2.POS_OF[g], data, t1 - t0)
    relay_e += e
    sorties.append({'relay': 'R01' if g == 'W' else 'R02', 'pos': g,
                    't0': t0, 't1': t1, 'energy': round(e, 3),
                    'ok_budget': bool(e <= EB + 1e-9)})

rows = []
for f in sorted(fls, key=lambda x: x.fid):
    s = schedule[f.fid]
    zones = '+'.join('%s(%d)' % (z, len(bs)) for z, bs in f.route)
    rows.append({'fid': f.fid, 'model': f.model, 'uav': s['uav'],
                 'start': s['start'], 'return': s['return'],
                 'energy': round(f.energy(), 3), 'zones': zones})

jc = max(met['makespan'], max(s['t1'] + 300 for s in sorties))
j = {
    'solver': 'v42-baseline', 'input': 'p2v41_mk_tol6_0.json',
    'offsets': {}, 'obj': 0.0,
    'met': {'hard_ok': met['hard_ok'], 'tardy_w': met['tardy_w'],
            'makespan': round(met['makespan'], 1), 'energy': round(met['energy'], 2),
            'flights': met['flights'], 'bad_zones': met['bad_zones']},
    'n_need_relay': n_need, 'cov_bad': cov_bad, 'overlap': 0.0, 'mpen': round(mp, 1),
    'relay_energy': round(relay_e, 3), 'joint_makespan': round(jc, 1),
    'sorties': sorties, 'rows': rows,
    'seg': {g: [(round(s[0]), round(s[1])) for s in ss] for g, ss in minfo.items()},
}
json.dump(j, open(os.path.join(OUTV, 'p3v42_final.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved p3v42_final.json')
print('met:', json.dumps(j['met'], ensure_ascii=False))
print('need_relay=%d cover_bad=%d mpen=%.0f relay_e=%.3f joint=%.1f (%.1f min)'
      % (n_need, cov_bad, mp, relay_e, jc, jc / 60))
for s in sorties:
    print('  %s %s [%d,%d] e=%.3f ok=%s' % (s['relay'], s['pos'], s['t0'], s['t1'],
                                            s['energy'], s['ok_budget']))