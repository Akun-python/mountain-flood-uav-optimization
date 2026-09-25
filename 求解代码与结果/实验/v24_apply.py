# -*- coding: utf-8 -*-
"""进化 v24 采纳：方案 D（S004-FOD f5->f20）落地为新的 p2_results.json 与 p3_co2.json。

口径：与 v23 完全一致的模型（跨区顺路投递按 route 段计；偏移 {f4:3300, f22:1000}）。
改进：f5 减 1 箱（25 kg）→ 运输完工 6959.81 -> 6896.52 s（-63.3 s，26 架历史最佳）；
联合完工（含中继最晚返场 6921）6959.8 -> 6921 s（-38.8 s）；能耗 70.705 -> 70.861（+0.156）。
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from p2_solve import Flight, dispatch, evaluate
import p3_co2

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = p3_co2.data
sv = p3_co2.Solver()

# ---- 方案 D 转移 ----
for i, f in enumerate(sv.flights):
    if f.fid == 5:
        r5 = [(s, [b for b in bs if b != 'S004-FOD-01'] if s == 'S011' else list(bs))
              for s, bs in f.route]
        r5 = [(s, bs) for s, bs in r5 if bs]
        sv.flights[i] = Flight(5, r5, f.model, data)
    if f.fid == 20:
        r20 = [(s, list(bs) + (['S004-FOD-01'] if s == 'S003' else []))
               for s, bs in f.route]
        sv.flights[i] = Flight(20, r20, f.model, data)
for f in sv.flights:
    f.start0 = sv.base[f.fid]
sv.precompute()

# ---- 联合复核（v23 偏移）----
offsets = {4: 3300.0, 22: 1000.0}
res = sv.finalize(offsets)
met = res['met']
relay_ret = {'W': 6921.0, 'E': 4133.0, 'N': 6667.0}
joint = max(met['makespan'], max(relay_ret.values()))
assert met['hard_ok'] and met['tardy_w'] == 0.0 and res['mpen'] == 0.0
print('联合复核通过：运输完工=%.2f 能耗=%.3f 联合完工=%.1f 采样=%d'
      % (met['makespan'], met['energy'], joint, sum(len(v) for v in sv.samples.values())))

# ---- 重派单：P2 口径无释放（p2_results.json 的 base 语义），P3 口径带偏移 ----
schedule, _ = dispatch(data, sv.flights)
met2 = evaluate(data, sv.flights, schedule)
assert met2['hard_ok'] and met2['tardy_w'] == 0.0

# ---- 新 flights 列表 ----
flights = []
for f in sv.flights:
    s = schedule[f.fid]
    flights.append({'fid': f.fid, 'uav': s['uav'], 'model': f.model,
                    'battery': s['battery'], 'start': round(s['start'], 2),
                    'return': round(s['return'], 2), 'route': [[x, list(b)] for x, b in f.route],
                    'energy': round(f.energy(), 4), 'nbox': f.nbox, 'mass': round(f.total_mass, 1)})
flights.sort(key=lambda x: x['fid'])

# ---- deliveries ----
deliveries = []
for fid, sch in schedule.items():
    for sid, bid, t in sch['deliveries']:
        deliveries.append({'box': bid, 'fid': fid, 'area': sid, 't': round(t, 1)})

metrics = {'hard_ok': True, 'tardy_w': 0.0, 'tardy_max': 0.0,
           'makespan': round(met2['makespan'], 2), 'energy': round(met2['energy'], 3),
           'flights': 26}

out_p2 = {'solver': 'v24 plan-D (S004-FOD f5->f20)', 'config': '26 架 / 偏移 {f4:3300, f22:1000}',
          'metrics': metrics, 'flights': flights, 'deliveries': deliveries}
json.dump(out_p2, open(os.path.join(RES, 'p2_results.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('p2_results.json 更新：', json.dumps(metrics, ensure_ascii=False))

# ---- p3_co2.json ----
obj, _ = sv.evaluate(offsets)
out_p3 = {'offsets': {str(k): float(v) for k, v in offsets.items()}, 'obj': round(obj, 1),
          'met': {k: (round(v, 2) if isinstance(v, float) else v)
                  for k, v in met.items() if k != 'box_time'},
          'joint_makespan': joint, 'samples': sum(len(v) for v in sv.samples.values())}
json.dump(out_p3, open(os.path.join(RES, 'p3_co2.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('p3_co2.json 更新：', json.dumps({k: out_p3[k] for k in ('offsets', 'joint_makespan', 'samples')}, ensure_ascii=False))
print('基线对比：运输 6959.81/70.705 -> %.2f/%.3f；联合 6959.8 -> %.1f'
      % (met2['makespan'], met2['energy'], joint))