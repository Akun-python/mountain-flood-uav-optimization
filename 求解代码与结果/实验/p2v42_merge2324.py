# -*- coding: utf-8 -*-
"""v42-ρ：23-24 架次合并寻优——从 25 架权威解出发，
枚举 A 碎趟（1-2 箱趟）成对合并（同区 2 箱 / 跨区质量体积可行），
生成 24 架（并 1）与 23 架（并 2）候选，评估后选能耗最低合规解。
输出 结果/进化_v42/merge2324.json。"""
import sys, os, json, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
RES = os.path.join(HERE, '..', 'results')
data = Data()
base = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
fl0 = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
       for f in base['flights']]

def met_of(fl):
    d = Data()
    sch, _ = dispatch(d, fl)
    m = evaluate(d, fl, sch)
    return {'flights': len(fl), 'makespan': m['makespan'], 'energy': m['energy'],
            'hard_ok': m['hard_ok'], 'tardy_w': m['tardy_w'], 'bad': len(m['bad_zones'])}

# 基线
m0 = met_of(fl0)
print('基线 25架: mk=%.1f e=%.3f hard=%s' % (m0['makespan'], m0['energy'], m0['hard_ok']))

# 找 A 型可合并趟（1-2 箱单区趟；不含 first_batch 硬窗箱且非 -01 首飞批箱）
A_idx = [i for i, f in enumerate(fl0) if f.model == 'A']
cand_idx = []
for i in A_idx:
    f = fl0[i]
    nb = sum(len(bs) for _, bs in f.route)
    if nb <= 2 and len(f.route) == 1:
        boxes = f.route[0][1]
        if any(b.endswith('-01') for b in boxes):
            continue  # 保留首飞批趟
        cand_idx.append(i)
print('A 可合并趟 %d 个:' % len(cand_idx), [(fl0[i].fid, fl0[i].route) for i in cand_idx])

def try_merge(i, j):
    """合并 fl0[i] 与 fl0[j] 成 1 趟 A（同区并箱 / 跨区 2 区 2 箱）。"""
    a, b = fl0[i], fl0[j]
    if len(a.route) != 1 or len(b.route) != 1:
        return None
    (sa, ba), (sb, bb) = a.route[0], b.route[0]
    merged = []
    if sa == sb:
        boxes = ba + bb
        f = Flight(0, [(sa, boxes)], 'A', data)
        if f.is_feasible():
            merged.append(f)
    else:
        if len(ba) == 1 and len(bb) == 1:
            m = sum(data.boxes[x]['mass'] for x in ba + bb)
            v = sum(data.boxes[x]['vol'] for x in ba + bb)
            if m <= 25 + 1e-9 and v <= 0.06 + 1e-9:
                f = Flight(0, [(sa, list(ba)), (sb, list(bb))], 'A', data)
                if f.is_feasible():
                    merged.append(f)
        elif len(ba) == 1 and len(bb) == 2:
            pass  # 3 箱跨区超容量
        elif len(bb) == 1 and len(ba) == 2:
            pass
    return merged[0] if merged else None

# 24 架：并 1 对
best24, best_e = None, 1e9
combos = []
for i, j in itertools.combinations(cand_idx, 2):
    fm = try_merge(i, j)
    if fm is None:
        continue
    fl = [f for k, f in enumerate(fl0) if k not in (i, j)] + [fm]
    m = met_of(fl)
    if m['hard_ok'] and m['tardy_w'] < 1e-6 and m['bad'] == 0 and m['energy'] < best_e:
        best_e = m['energy']; best24 = (fl, m, (i, j))
print('24架最优: 并(%d,%d) mk=%.1f e=%.3f' % (
    best24[2][0], best24[2][1], best24[1]['makespan'], best24[1]['energy']))

# 23 架：在 24 架基础上再并 1 对
if best24:
    fl24 = best24[0]
    cand2 = [k for k in cand_idx if k not in best24[2]]
    # 重建索引：fl24 中对应 cand2 的位置
    fid_map = {}
    for k in cand2:
        fid_map[fl0[k].fid] = k
    A2_idx = [n for n, f in enumerate(fl24) if f.model == 'A' and f.nbox <= 2
              and len(f.route) == 1 and not any(b.endswith('-01') for _, bs in f.route for b in bs)
              and f.fid in fid_map]
    best23, best_e2 = None, 1e9
    for i, j in itertools.combinations(A2_idx, 2):
        fm = try_merge(i, j)
        if fm is None:
            continue
        fl = [f for k, f in enumerate(fl24) if k not in (i, j)] + [fm]
        m = met_of(fl)
        if m['hard_ok'] and m['tardy_w'] < 1e-6 and m['bad'] == 0 and m['energy'] < best_e2:
            best_e2 = m['energy']; best23 = (fl, m, (i, j))
    if best23:
        print('23架最优: mk=%.1f e=%.3f' % (best23[1]['makespan'], best23[1]['energy']))

out = {'solver': 'v42-merge-23-24', 'base': {'flights': 25, 'makespan': m0['makespan'],
                                              'energy': m0['energy']}}
if best24:
    fl24, m24, pair = best24
    out['n24'] = {'makespan': round(m24['makespan'], 1), 'energy': round(m24['energy'], 3),
                  'flights': 24, 'merged_pair': [fl0[pair[0]].fid, fl0[pair[1]].fid],
                  'flights_route': [[f.fid, f.model, [[s, bs] for s, bs in f.route]] for f in fl24]}
if best23:
    fl23, m23, pair2 = best23
    out['n23'] = {'makespan': round(m23['makespan'], 1), 'energy': round(m23['energy'], 3),
                  'flights': 23,
                  'flights_route': [[f.fid, f.model, [[s, bs] for s, bs in f.route]] for f in fl23]}
json.dump(out, open(os.path.join(EVO, 'merge2324.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved merge2324.json')