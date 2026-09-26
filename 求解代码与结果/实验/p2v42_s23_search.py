# -*- coding: utf-8 -*-
"""v42-β：23 架严格合规搜索——从 29 架冠军贪心合法合并。
合并任意两架（同区或串联多区，保持区一致），合并后 dispatch 必须
零迟到+零跨区。每次选 (makespan<=8000, energy 最小) 的合法合并，
迭代直到架次数=23 或无可合并对。输出 结果/进化_v42/s23_search.json。"""
import sys, os, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
SRC = os.path.join(HERE, '..', '结果', '进化_v25', 'p2v41_mk_tol6_0.json')

data = Data()
sol = json.load(open(SRC, encoding='utf-8'))['solution']
fls = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in sol]

def metrics(fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None
    return evaluate(data, fl, sch)

def route_key(route):
    return tuple((s, tuple(bs)) for s, bs in route)

def seq_route(r1, r2):
    """串联两架次：r1 的服务区序列 + r2 的服务区序列（箱合并同区）。"""
    m = {}
    for s, bs in list(r1) + list(r2):
        m.setdefault(s, []).extend(bs)
    return [(s, bs) for s, bs in m.items()]

def try_merge(fl, i, j, mode):
    a, b = fl[i], fl[j]
    if mode == 'same':
        # 仅同区（且访问区集合相同）可同架；否则跳过
        if set(s for s, _ in a.route) != set(s for s, _ in b.route) or len(a.route) != 1:
            return None
        s = a.route[0][0]
        route = [(s, a.route[0][1] + b.route[0][1])]
        model = a.model if a.model in ('B', 'C') else b.model  # 重载优先
    else:
        route = seq_route(a.route, b.route)
        model = max((a.model, b.model), key=lambda m: data.uav_types[m]['Q'])
    if len(route) > 3:
        return None
    fid = 10000 + i * 100 + j  # int，与解文件 fid(int) 比较兼容
    try:
        nf = Flight(fid, route, model, data)
    except Exception:
        return None
    if not nf.is_feasible():
        return None
    # 保证架次 id 唯一
    rest = [copy.deepcopy(x) for k, x in enumerate(fl) if k not in (i, j)]
    rest.append(nf)
    m = metrics(rest)
    if m is None or not m['hard_ok'] or m['tardy_w'] > 1e-6 or m['bad_zones']:
        return None
    return nf, m, rest

def best_merge(fl, max_mk=8000.0):
    best = None
    n = len(fl)
    for i in range(n):
        for j in range(i + 1, n):
            for mode in ('same', 'seq'):
                r = try_merge(fl, i, j, mode)
                if r is None:
                    continue
                nf, m, rest = r
                if m['makespan'] > max_mk or m['flights'] > n - 1:
                    continue
                score = (m['makespan'], m['energy'], nf.fid)
                if best is None or score < best[0]:
                    best = (score, m, rest)
    return best

met0 = metrics(fls)
print('基线: fl=%d mk=%.1f e=%.2f' % (len(fls), met0['makespan'], met0['energy']))
cur = fls
steps = []
for it in range(1, 7):
    if len(cur) <= 23:
        break
    best = best_merge(cur, max_mk=8000.0)
    if best is None:
        print('第 %d 轮无可合并对（下限架次 %d）' % (it, len(cur)))
        break
    (mk, e, fid), m, cur = best
    steps.append({'it': it, 'flights': len(cur), 'makespan': round(mk, 1),
                  'energy': round(e, 3), 'merge': fid})
    print('第 %d 轮合并 %s -> fl=%d mk=%.1f e=%.2f'
          % (it, fid, len(cur), mk, e))

if len(cur) == 23:
    print('\n== 成功到达 23 架 ==')
    print('mk=%.1f e=%.2f' % (metrics(cur)['makespan'], metrics(cur)['energy']))
    # 导出路由（P3 后续可用）
    fl_out = []
    for f in cur:
        fl_out.append({'fid': f.fid, 'model': f.model,
                       'route': [[s, bs] for s, bs in f.route]})
    json.dump({'baseline': {'flights': met0['flights'], 'makespan': round(met0['makespan'], 1),
                            'energy': round(met0['energy'], 2)},
               'steps': steps,
               'final': {'flights': len(cur), 'makespan': round(metrics(cur)['makespan'], 1),
                         'energy': round(metrics(cur)['energy'], 2),
                         'routes': fl_out}},
              open(os.path.join(EVO, 's23_search.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
else:
    print('\n未到达 23 架，最终架次 %d（历史归档，无 s23 冠军）' % len(cur))
    fl_out = []
    for f in cur:
        fl_out.append({'fid': f.fid, 'model': f.model,
                       'route': [[s, bs] for s, bs in f.route]})
    mc = metrics(cur)
    json.dump({'baseline': {'flights': met0['flights'], 'makespan': round(met0['makespan'], 1),
                            'energy': round(met0['energy'], 2)},
               'steps': steps,
               'final': {'flights': len(cur), 'makespan': round(mc['makespan'], 1),
                         'energy': round(mc['energy'], 2), 'routes': fl_out}},
              open(os.path.join(EVO, 's23_search.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
print('saved s23_search.json')