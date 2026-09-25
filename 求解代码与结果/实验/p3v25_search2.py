# -*- coding: utf-8 -*-
"""v25 P3 修复版输入下的最优搜索：多 (iters, seed, w_relay) 组合，
每组合 finalize 后取 machine_penalty 真实中继班次，选零迟到/零覆盖/联合最小。
写 结果/进化_v25/p3v25_search2_best.json 与汇总打印。"""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
CODEDIR = os.path.join(HERE, '..', '代码')
sys.path.insert(0, CODEDIR)
sys.path.insert(0, HERE)
os.chdir(CODEDIR)
import p3_co2

data = p3_co2.data
sv = p3_co2.Solver()
print('base 派单: %d 架' % len(sv.flights), file=sys.stderr)

def run(iters, seed, w_relay):
    best, obj = sv.sa(iters=iters, seed=seed, w_relay=w_relay)
    res = sv.finalize(best)
    m = res['met']
    cov_bad, overlap, seg, by = sv.relay_load(res['missions'])
    # 真实中继班次（machine_penalty 打包 + 组件池语义）
    missions = sv.build_missions({fid: sv.base[fid] + best.get(fid, 0.0) for fid in sv.base})
    mp, minfo, esum = sv.machine_penalty(missions)
    # 班次最晚返场（minfo: {g: [(t0,t1),...]}）
    latest_ret = 0.0
    sortie_txt = []
    for g, ss in minfo.items():
        for (a0, a1) in ss:
            pos = p3_co2.POS_OF[g]
            t_out, t_back, _ = p3_co2.relay_mission_time(pos[0], pos[1], pos[2], data)
            e = p3_co2.relay_mission_energy(pos[0], pos[1], pos[2], data, a1 - a0)
            latest_ret = max(latest_ret, a1 + t_back)
            sortie_txt.append('%s [%.0f, %.0f] e=%.3f ret=%.0f' % (g, a0, a1, e, a1 + t_back))
    joint = max(m['makespan'], latest_ret)
    return {'iters': iters, 'seed': seed, 'w_relay': w_relay,
            'obj': obj, 'makespan': m['makespan'], 'tardy': m['tardy_w'],
            'hard': m['hard_ok'], 'bad_zones': len(m['bad_zones']),
            'cov_bad': cov_bad, 'overlap': overlap, 'mpen': res['mpen'],
            'joint': joint, 'latest_ret': latest_ret, 'sorties': sortie_txt}

combos = []
for iters, seeds, wr in [(3000, [7, 11, 13], [0.0]),
                          (2500, [7, 11], [0.0])]:
    for sd in seeds:
        for w in wr:
            combos.append((iters, sd, w))
results = []
t0 = time.time()
for k, (it, sd, wr) in enumerate(combos):
    try:
        r = run(it, sd, wr)
    except Exception as ex:
        print('comb(%d,%d,%s) FAIL: %s' % (it, sd, wr, ex), file=sys.stderr)
        continue
    results.append(r)
    print('[%02d/%02d] iters=%d seed=%d w=%.1f hard=%s tardy=%.1f mk=%.0f joint=%.0f '
          'cov=%d mpen=%.0f' % (k + 1, len(combos), it, sd, wr, r['hard'],
                                 r['tardy'], r['makespan'], r['joint'],
                                 r['cov_bad'], r['mpen']))
    for s in r['sorties'][:6]:
        print('       ', s)
best = min([r for r in results if r['hard'] and r['tardy'] <= 1e-6 and r['cov_bad'] == 0
            and r['bad_zones'] == 0], key=lambda r: r['joint'], default=None)
print('==== 最优（零迟到/零覆盖/区一致，联合最小） ====')
print(json.dumps(best, ensure_ascii=False, indent=1) if best else '无可行')
json.dump({'elapsed_s': round(time.time() - t0),
           'results': results, 'best': best},
          open(os.path.join(HERE, '..', '结果', '进化_v25', 'p3v25_search2_best.json'),
               'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved p3v25_search2_best.json', file=sys.stderr)