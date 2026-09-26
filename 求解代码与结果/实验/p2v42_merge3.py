# -*- coding: utf-8 -*-
"""v42-ι：升级合并搜索——合并后允许升格 C 型（Q=80kg，之前 s23 只试 max(a,b) 机型，
B+B 的 25+25=50kg 必然不可行，导致合并空间被错误截断）。
评分：完工优先（≤7350 下限）或能耗优先（完工 ≤7350）；每次 dispatch 验零迟到零跨区。
输出 结果/进化_v42/merge3_search.json。"""
import sys, os, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
EVO = os.path.join(HERE, '..', '结果', '进化_v42')

data = Data()
Q = {m: data.uav_types[m]['Q'] for m in 'ABC'}

def load(path):
    obj = json.load(open(path, encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
            for f in obj['flights']]

def metric(fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None
    return evaluate(data, fl, sch)

def try_merge(fl, i, j, max_route=3, allow_c=True):
    a, b = fl[i], fl[j]
    # 合并路线（同区合并/顺序拼接）
    from collections import OrderedDict
    m = OrderedDict()
    for s, bs in list(a.route) + list(b.route):
        m.setdefault(s, []).extend(bs)
    route = [(s, bs) for s, bs in m.items()]
    if len(route) > max_route:
        return None
    mass = sum(data.boxes[bid]['mass'] for _, bs in route for bid in bs)
    nbox = sum(len(bs) for _, bs in route)
    # 机型：优先保持最大型；若超载则升 C（仅当 allow_c 且不超 C）
    cand_models = [max(a.model, b.model, key=lambda mm: Q[mm])] + (['C'] if allow_c else [])
    for model in cand_models:
        if mass > Q[model] + 1e-9:
            continue
        try:
            nf = Flight(10000 + i * 100 + j, route, model, data)
        except Exception:
            continue
        if not nf.is_feasible():
            continue
        rest = [copy.deepcopy(x) for k, x in enumerate(fl) if k not in (i, j)]
        rest.append(nf)
        mt = metric(rest)
        if mt is None or not mt['hard_ok'] or mt['tardy_w'] > 1e-6 or mt['bad_zones']:
            continue
        if mt['flights'] > len(fl) - 1:
            continue
        return mt, rest
    return None

def best_merge(fl, max_mk, mode='mk'):
    best = None
    n = len(fl)
    for i in range(n):
        for j in range(i + 1, n):
            r = try_merge(fl, i, j)
            if r is None:
                continue
            mt, rest = r
            if mt['makespan'] > max_mk:
                continue
            key = (mt['makespan'], mt['energy']) if mode == 'mk' else (mt['energy'], mt['makespan'])
            if best is None or key < best[0]:
                best = (key, mt, rest)
    return best

def run_mode(fls, mode, max_mk, min_fl, label):
    cur = copy.deepcopy(fls)
    steps = []
    while len(cur) > min_fl:
        best = best_merge(cur, max_mk, mode)
        if best is None:
            break
        (k1, k2), mt, cur = best
        steps.append({'flights': len(cur), 'mk': round(mt['makespan'], 1),
                      'e': round(mt['energy'], 3), 'mode': label})
        print('%-4s fl=%d mk=%7.1f e=%6.2f' % (label, len(cur), mt['makespan'], mt['energy']))
    return cur, steps

fls = load(os.path.join(RES, 'p2_results.json'))
m0 = metric(fls)
print('基线 fl=%d mk=%.1f e=%.2f' % (len(fls), m0['makespan'], m0['energy']))

out = {}
for mode in ('mk', 'en'):
    cur, steps = run_mode(fls, mode, max_mk=7450.0, min_fl=21, label=mode)
    mf = metric(cur)
    out[mode] = {'steps': steps, 'final': {'flights': len(cur), 'mk': round(mf['makespan'], 1),
                                           'e': round(mf['energy'], 3), 'routes': [
        {'fid': f.fid, 'model': f.model, 'route': [[s, bs] for s, bs in f.route]} for f in cur]
    }}
json.dump({'baseline': {'flights': len(fls), 'mk': round(m0['makespan'], 1), 'e': round(m0['energy'], 3)},
           **out}, open(os.path.join(EVO, 'merge3_search.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved merge3_search.json')