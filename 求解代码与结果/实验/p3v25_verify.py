# -*- coding: utf-8 -*-
"""v25 P3 端到端验证：把 25 架压缩解（6807s/71.98kWh）放入官方 P3 管线
（monkey-patch 临时输入目录），SA 重寻偏移，看联合完工 / cover_bad / mpen /
中继能耗 —— 沿用 v19 教训：P2 完工提升必须 P3 联合口径可行才有效。"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
CODEDIR = os.path.join(HERE, '..', '代码')
sys.path.insert(0, CODEDIR)
sys.path.insert(0, HERE)
os.chdir(CODEDIR)  # p3_co2 内相对依赖按文件目录

from p2_solve import Flight, dispatch, evaluate
import p3_co2

data = p3_co2.data

sol_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, '..', '结果', '进化_v25', 'p2v25_compress.json')
tag = os.path.splitext(os.path.basename(sol_file))[0]

# 1. 加载 solution 并 dispatch
sol = json.load(open(sol_file, encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in sol['solution']]
schedule, _ = dispatch(data, fls)
met = evaluate(data, fls, schedule)
print('P2 口径: %d 架 / mk %.1f / %.2f kWh / hard %s / tardy %.3f' % (
    met['flights'], met['makespan'], met['energy'], met['hard_ok'], met['tardy_w']))
bad = sum(1 for scd in schedule.values() for sid, bid, t in scd['deliveries']
          if bid.split('-')[0] != sid)
print('区不符箱: %d' % bad)

# 2. 写出 p2_results.json 格式到临时目录
tmpdir = os.path.join(HERE, '..', '结果', '进化_v25', 'p3in')
os.makedirs(tmpdir, exist_ok=True)
out = {'solver': 'v25-compress', 'config': '25fl/6807s',
       'metrics': {'makespan': met['makespan'], 'energy': met['energy'],
                   'flights': met['flights'], 'tardy_w': 0.0, 'hard_ok': True},
       'flights': [], 'deliveries': []}
for f in fls:
    sch = schedule[f.fid]
    out['flights'].append({
        'fid': f.fid, 'uav': sch['uav'], 'model': f.model, 'battery': sch['battery'],
        'start': round(sch['start'], 1), 'return': round(sch['return'], 1),
        'route': [(s, list(bs)) for s, bs in f.route],
        'energy': round(f.energy(), 4), 'nbox': f.nbox, 'mass': round(f.total_mass, 2)})
    for sid, bid, t in sch['deliveries']:
        out['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
with open(os.path.join(tmpdir, 'p2_results.json'), 'w', encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print('临时输入 ->', os.path.join(tmpdir, 'p2_results.json'))

# 3. monkey-patch OUT 并跑官方 P3 Solver
p3_co2.OUT = tmpdir
sv = p3_co2.Solver()
best, best_obj = sv.sa(iters=2500, seed=7, w_relay=0.0)
res = sv.finalize(best)
m = res['met']
print('\n== v25 P3 端到端 ==')
print('联合完工: %.1f s (%.1f min)  运输完工 %.1f s' % (m['makespan'], m['makespan'] / 60, met['makespan']))
print('cover_bad=%d  R2_overlap=%.0fs  machine_pen=%.0fs  零迟到=%s' % (
    res['seg']['cov_bad'], res['seg']['overlap'], res['mpen'], m['tardy_w'] < 1e-6))
json.dump({'offsets': best, 'obj': best_obj, 'tag': tag,
           'met': {k: (round(v, 2) if isinstance(v, float) else v)
                   for k, v in m.items() if k != 'box_time'},
           'seg': {k: v for k, v in res['seg'].items() if k != 'by'}},
          open(os.path.join(HERE, '..', '结果', '进化_v25', 'p3v25_verify_%s.json' % tag), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved -> 结果/进化_v25/p3v25_verify_%s.json' % tag)