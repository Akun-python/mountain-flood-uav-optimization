# -*- coding: utf-8 -*-
"""v25 P3 多 seed 长 SA 搜索：以 28 架区一致解（7394.9s/83.12kWh）为输入，
对若干 (iters, seed, w_relay) 组合跑 SA 偏移优化，finalize 后记录
运输/联合完工/迟到/覆盖/机器罚/中继能耗，选零迟到且联合完工最小者。"""
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
print('P2 输入: %d 架 / mk %.1f / %.2f kWh / hard %s / tardy %.3f' % (
    met0['flights'], met0['makespan'], met0['energy'], met0['hard_ok'], met0['tardy_w']))

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

combos = [(3000, 7, 0.0), (3000, 11, 0.0), (3000, 13, 0.0),
          (5000, 7, 0.0), (5000, 11, 0.0), (4000, 17, 5.0)]
best_joint = None
for iters, seed, wr in combos:
    sv = p3_co2.Solver()
    best, best_obj = sv.sa(iters=iters, seed=seed, w_relay=wr)
    res = sv.finalize(best)
    m = res['met']
    cov_bad, overlap, seg, by = sv.relay_load(res['missions'])
    joint = max(m['makespan'], max((s[1] for g, ss in seg.items() for s in ss), default=0) +
                p3_co2.relay_mission_time(*p3_co2.POS_OF['W'], data)[1])
    print('iters=%d seed=%d wr=%.1f: tardy=%.1f mk=%.1f joint=%.1f cover=%d ov=%.0f mpen=%.0f en=%.2f' % (
        iters, seed, wr, m['tardy_w'], m['makespan'], joint, cov_bad, overlap,
        res['mpen'], sum(p3_co2.relay_mission_energy(*p3_co2.POS_OF[g], data, s[1] - s[0])
                         for g, ss in seg.items() for s in ss)))
    ok = m['hard_ok'] and m['tardy_w'] < 1e-6 and cov_bad == 0 and overlap < 1e-6
    if ok and (best_joint is None or joint < best_joint[0]):
        best_joint = (joint, iters, seed, wr, best)
    print('  零迟到零覆盖零重叠=%s' % ok, flush=True)
print('\n== 最佳零迟到零覆盖解 ==')
print(best_joint[0] if best_joint else '无', 'iters/seed/wr:', best_joint[1:4] if best_joint else None)
if best_joint:
    json.dump({'joint': best_joint[0], 'iters': best_joint[1], 'seed': best_joint[2],
               'w_relay': best_joint[3], 'offsets': best_joint[4]},
              open(os.path.join(HERE, '..', '结果', '进化_v25', 'p3v25_search_best.json'),
                   'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p3v25_search_best.json')