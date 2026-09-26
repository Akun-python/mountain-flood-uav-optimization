# -*- coding: utf-8 -*-
"""v42-ζ：24 架更低能耗候选——从 25 架出发，放宽多区段数上限再合并。
s23 贪心在 route<=3 处停在 25 架；此处允许 3 段合并（route<=4）再合 1-2 对到 24 架，
目标"能耗下降且完工可接受（≤ 7350）"。每次合并 dispatch 校验零迟到零跨区+is_feasible。
输出 结果/进化_v42/s24_search.json。"""
import sys, os, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
EVO = os.path.join(HERE, '..', '结果', '进化_v42')

data = Data()
obj = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in obj['flights']]

def metrics(fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None
    return evaluate(data, fl, sch)

def base_metric(fl):
    sch, _ = dispatch(data, fl)
    return evaluate(data, fl, sch)

met0 = base_metric(fls)
print('基线 fl=%d mk=%.1f e=%.2f' % (len(fls), met0['makespan'], met0['energy']))

def seq_route(r1, r2):
    m = {}
    for s, bs in list(r1) + list(r2):
        m.setdefault(s, []).extend(bs)
    return [(s, bs) for s, bs in m.items()]

def try_merge(fl, i, j, max_len):
    a, b = fl[i], fl[j]
    # 同区直接并
    if len(a.route) == 1 and len(b.route) == 1 and a.route[0][0] == b.route[0][0]:
        s = a.route[0][0]
        route = [(s, a.route[0][1] + b.route[0][1])]
    else:
        route = seq_route(a.route, b.route)
    if len(route) > max_len:
        return None
    # 重载优先
    model = max((a.model, b.model), key=lambda m: data.uav_types[m]['Q'])
    try:
        nf = Flight(10000 + i * 100 + j, route, model, data)
    except Exception:
        return None
    if not nf.is_feasible():
        return None
    rest = [copy.deepcopy(x) for k, x in enumerate(fl) if k not in (i, j)]
    rest.append(nf)
    m = metrics(rest)
    if m is None or not m['hard_ok'] or m['tardy_w'] > 1e-6 or m['bad_zones']:
        return None
    if m['flights'] > len(fl) - 1:
        return None
    return nf.fid, m, rest

def best_merge(fl, max_route, max_mk):
    best = None
    n = len(fl)
    for i in range(n):
        for j in range(i + 1, n):
            r = try_merge(fl, i, j, max_route)
            if r is None:
                continue
            fid, m, rest = r
            if m['makespan'] > max_mk:
                continue
            # 评分：完工 + 能耗（完工优先，但允许能耗优先换完工）
            score = (m['makespan'], m['energy'])
            if best is None or score < best[0]:
                best = (score, m, rest, fid)
    return best

cur = fls
steps = []
# 从 25 架寻找一次合法 3 段合并到 24 架（也可连续多合到目标 24）
while len(cur) > 24:
    best = best_merge(cur, max_route=4, max_mk=7350.0)
    if best is None:
        print('无可合并对（当前 %d 架，route<=4 下无法继续）' % len(cur))
        break
    (mk, e), m, cur, fid = best
    steps.append({'flights': len(cur), 'makespan': round(mk, 1), 'energy': round(e, 3),
                  'merge': fid, 'max_route': 4})
    print('合 %s -> fl=%d mk=%.1f e=%.2f' % (fid, len(cur), mk, e))

mc = metrics(cur)
fl_out = [{'fid': f.fid, 'model': f.model, 'route': [[s, bs] for s, bs in f.route]}
          for f in cur]
json.dump({'baseline': {'flights': met0['flights'], 'makespan': round(met0['makespan'], 1),
                        'energy': round(met0['energy'], 3)},
           'steps': steps,
           'final': {'flights': len(cur), 'makespan': round(mc['makespan'], 1),
                     'energy': round(mc['energy'], 3), 'routes': fl_out}},
          open(os.path.join(EVO, 's24_search.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('final fl=%d mk=%.1f e=%.2f  (saved s24_search.json)'
      % (len(cur), mc['makespan'], mc['energy']))