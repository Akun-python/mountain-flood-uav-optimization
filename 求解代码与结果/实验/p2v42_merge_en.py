# -*- coding: utf-8 -*-
"""v42-μ：能耗优先合并（29 架冠军起点，含 2/3 元合并 + C 升格）。
评分：(完工≤7113 前提下能耗最小)；每步 dispatch 验零迟到零跨区。
目标 25 架或更低，看能否在 25-27 架区间拿到能耗 < 70.28 且完工 ≤ 7113 的支配解。
输出 结果/进化_v42/merge_en_search.json。"""
import sys, os, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
data = Data()
Q = {m: data.uav_types[m]['Q'] for m in 'ABC'}

# 29 架起点（v41 冠军，与 s23 相同来源）
src = os.path.join(HERE, '..', '结果', '进化_v42', 'p2v41_mk_tol6_0.json')
if not os.path.exists(src):
    src = os.path.join(HERE, '..', '结果', '进化_v25', 'p2v41_mk_tol6_0.json')
print('source:', src)
d0 = json.load(open(src, encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in (d0.get('flights') or d0.get('final', {}).get('routes'))]

def metric(fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None
    return evaluate(data, fl, sch)

def merged_route(sets):
    m = OrderedDict()
    for s, bs in sets:
        m.setdefault(s, []).extend(bs)
    return [(s, bs) for s, bs in m.items()]

def mk_flight(fid, route, mass, old_models):
    for model in (max(old_models, key=lambda x: Q.get(x, 0)), 'C'):
        p = data.uav_types[model]
        if mass <= p['Q'] + 1e-9:
            try:
                nf = Flight(fid, route, model, data)
            except Exception:
                continue
            if nf.is_feasible():
                return nf
    return None

def try_merge(fl, idxs):
    """idx 元组（2 或 3 个趟）-> 合并一趟；route 段数 ≤3。返回 (met, rest) 或 None。"""
    parts = [fl[i] for i in idxs]
    route = merged_route([(s, bs) for f in parts for s, bs in f.route])
    if len(route) > 3:
        return None
    mass = sum(data.boxes[b]['mass'] for _, bs in route for b in bs)
    nf = mk_flight(10000 + idxs[0] * 100 + idxs[1], route, mass,
                   [f.model for f in parts])
    if nf is None:
        return None
    rest = [copy.deepcopy(x) for k, x in enumerate(fl) if k not in idxs]
    rest.append(nf)
    mt = metric(rest)
    if mt is None or not mt['hard_ok'] or mt['tardy_w'] > 1e-6 or mt['bad_zones']:
        return None
    if mt['flights'] > len(fl) - 1:
        return None
    return mt, rest

def best_step(fl, max_mk, allow3):
    best = None
    n = len(fl)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    triples = [(i, j, k) for i in range(n) for j in range(i + 1, n)
               for k in range(j + 1, n)] if allow3 else []
    for idxs in pairs + triples:
        r = try_merge(fl, idxs)
        if r is None:
            continue
        mt, rest = r
        if mt['makespan'] > max_mk:
            continue
        key = (mt['energy'], mt['makespan'], len(idxs))
        if best is None or key < best[0]:
            best = (key, mt, rest, idxs)
    return best

m0 = metric(fls)
print('起点 fl=%d mk=%.1f e=%.2f' % (len(fls), m0['makespan'], m0['energy']))
cur = fls
steps = []
mode = 'en'
while len(cur) > 24:
    best = best_step(cur, max_mk=7113.0, allow3=(mode == 'en'))
    if best is None:
        print('无可合并对（%d 架）' % len(cur))
        break
    (e, mk, _), mt, cur, idxs = best
    steps.append({'flights': len(cur), 'mk': round(mt['makespan'], 1),
                  'e': round(mt['energy'], 3), 'merge': [len(x) for x in idxs]})
    print('fl=%d mk=%7.1f e=%6.2f  (合并 %d 趟)' % (len(cur), mt['makespan'], mt['energy'], len(idxs)))
    if len(cur) == 25:
        # 25 架后若能耗仍 >70.28 且完工 ≤7113，允许再试 3 元到 24
        if mt['energy'] >= 70.28 - 1e-6:
            mode = 'en3'
mc = metric(cur)
json.dump({'baseline': {'flights': len(fls), 'mk': round(m0['makespan'], 1), 'e': round(m0['energy'], 3)},
           'steps': steps,
           'final': {'flights': len(cur), 'mk': round(mc['makespan'], 1), 'e': round(mc['energy'], 3),
                     'routes': [{'fid': f.fid, 'model': f.model, 'route': [[s, bs] for s, bs in f.route]}
                                for f in cur]}},
          open(os.path.join(EVO, 'merge_en_search.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('final fl=%d mk=%.1f e=%.2f (saved merge_en_search.json)' % (len(cur), mc['makespan'], mc['energy']))