# -*- coding: utf-8 -*-
"""v25 P3 最终解：SA(iters=3000, seed=7) 复现 9304.9 级解，保存 offsets、
偏移后派单 schedule（28 行表数据）、中继时段，写 p3v25_final.json。"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
CODEDIR = os.path.join(HERE, '..', '代码')
sys.path.insert(0, CODEDIR)
sys.path.insert(0, HERE)
os.chdir(CODEDIR)

from p2_solve import Flight, dispatch, evaluate
import p3_co2

data = p3_co2.data
sol_file = os.path.join(HERE, '..', '结果', '进化_v25', 'p2v25b_compress26.json')
sol = json.load(open(sol_file, encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in sol['solution']]
schedule, _ = dispatch(data, fls)
met0 = evaluate(data, fls, schedule)

tmpdir = os.path.join(HERE, '..', '结果', '进化_v25', 'p3in')
os.makedirs(tmpdir, exist_ok=True)
out = {'solver': 'v25b_compress26', 'config': '28fl/7394.9s',
       'metrics': {'makespan': met0['makespan'], 'energy': met0['energy'],
                   'flights': met0['flights'], 'tardy_w': 0.0, 'hard_ok': True},
       'flights': [], 'deliveries': []}
for f in fls:
    sch = schedule[f.fid]
    out['flights'].append({'fid': f.fid, 'uav': sch['uav'], 'model': f.model,
                           'battery': sch['battery'], 'start': round(sch['start'], 1),
                           'return': round(sch['return'], 1),
                           'route': [(s, list(bs)) for s, bs in f.route],
                           'energy': round(f.energy(), 4), 'nbox': f.nbox,
                           'mass': round(f.total_mass, 2)})
    for sid, bid, t in sch['deliveries']:
        out['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
json.dump(out, open(os.path.join(tmpdir, 'p2_results.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
p3_co2.OUT = tmpdir

sv = p3_co2.Solver()
best, best_obj = sv.sa(iters=3000, seed=7, w_relay=0.0)
res = sv.finalize(best)
m = res['met']
cov_bad, overlap, seg, by = sv.relay_load(res['missions'])
releases = {fid: sv.base[fid] + best.get(fid, 0.0) for fid in sv.base}
schedule2, _ = dispatch(data, fls, releases)
rows = []
for f in sorted(fls, key=lambda x: x.fid):
    s2 = schedule2[f.fid]
    zones = '+'.join('%s(%d)' % (z, len(bs)) for z, bs in f.route)
    rows.append((f.fid, f.model, s2['uav'], s2['start'], s2['return'], f.energy(), zones))
print('final: hard=%s tardy=%.1f mk=%.1f en=%.2f fl=%d' % (
    m['hard_ok'], m['tardy_w'], m['makespan'], m['energy'], m['flights']))
print('cover_bad=%d overlap=%.0f mpen=%.0f' % (cov_bad, overlap, res['mpen']))
for g, ss in seg.items():
    for s in ss:
        print('  %s sortie [%.0f, %.0f]' % (g, s[0], s[1]))
print('== 偏移后 28 行表 ==')
for r in rows:
    print('f%02d & %s & %s & %d & %d & %.2f & %s \\\\' % r)
relay_e = sum(p3_co2.relay_mission_energy(*p3_co2.POS_OF[g], data, s[1] - s[0])
              for g, ss in seg.items() for s in ss)
json.dump({'offsets': best, 'obj': best_obj,
           'met': {k: (round(v, 2) if isinstance(v, float) else v)
                   for k, v in m.items() if k != 'box_time'},
           'seg': {g: [(round(s[0]), round(s[1])) for s in ss] for g, ss in seg.items()},
           'cov_bad': cov_bad, 'overlap': round(overlap, 1), 'mpen': res['mpen'],
           'relay_energy': round(relay_e, 3),
           'rows': [{'fid': r[0], 'model': r[1], 'uav': r[2], 'start': r[3],
                     'return': r[4], 'energy': round(r[5], 3), 'zones': r[6]} for r in rows]},
          open(os.path.join(HERE, '..', '结果', '进化_v25', 'p3v25_final.json'),
               'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved -> 结果/进化_v25/p3v25_final.json')