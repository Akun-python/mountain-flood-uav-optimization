# -*- coding: utf-8 -*-
"""v42-θ：满载重打包构造器——打破局部最优的重新装箱尝试。
目标：21-24 架满载（C 80/B 30/A 25），每机趟数 ≤4，完工 < 7113，能耗尽量低。
装箱规则：每趟质量 ≤ 机型 Q；单区趟 7 箱上限(C)/3 箱(B)/2 箱(A)由质量决定；
C 型优先装"必须重载"的区（S001 每箱 10.3kg，C 最多 7 箱）。
输出 结果/进化_v42/repack_cands.json（含每候选 dispatch 指标）。"""
import sys, os, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')

data = Data()
Q = {m: data.uav_types[m]['Q'] for m in 'ABC'}

# 每区箱清单（质量升序）
from collections import OrderedDict
ab = OrderedDict()
for bid in sorted(data.box_ids):
    s = bid.split('-')[0]
    ab.setdefault(s, []).append((bid, data.boxes[bid]['mass']))
# 每区按质量排序后：预估趟数（C 最多 ceil(mass/80) 但受每箱限制）
area_info = {}
for s, lst in ab.items():
    ms = [m for _, m in lst]
    area_info[s] = {'n': len(lst), 'mass': sum(ms),
                    'max_per_C': max(1, int(Q['C'] // (sum(ms) / len(lst)))) if lst else 1}

def pack_area(s, model, n_split):
    """把区 s 的箱拆成 n_split 趟（均衡质量）。"""
    items = sorted(ab[s], key=lambda x: x[1], reverse=True)
    loads = [[] for _ in range(n_split)]
    cur = [0.0] * n_split
    for bid, m in items:
        j = min(range(n_split), key=lambda k: cur[k])
        loads[j].append(bid); cur[j] += m
    return [[s, [bid for bid in loads[k]]] for k in range(n_split) if loads[k]]

def check(flights):
    sch, _ = dispatch(data, flights)
    if sch is None:
        return None
    met = evaluate(data, flights, sch)
    return met

# ---------- 候选 1：C=S001x3+S004+S005+S006, B=S002x4+S003x4+S007x2+S008x2, A=轻区x7 ------
# ---------- （B 8 趟偏多，看实际完工）--------
def cand_base():
    routes = []
    # C 6 趟
    routes += pack_area('S001', 'C', 3)            # 7+7+1 箱（71.9+71.9+10.3）
    routes += pack_area('S004', 'C', 1)
    routes += pack_area('S005', 'C', 1)
    routes += pack_area('S006', 'C', 1)
    # B 8 趟
    routes += pack_area('S002', 'B', 4)            # 2+2+2+2（20.5/趟）
    routes += pack_area('S003', 'B', 4)
    routes += pack_area('S007', 'B', 2)
    routes += pack_area('S008', 'B', 2)
    # A 7 趟（轻区）
    for s in ['S009', 'S010', 'S011', 'S012', 'S013', 'S014', 'S015']:
        routes.append([s, [b for b, _ in ab[s]]])
    return routes

def build(routes):
    fls = []
    for i, r in enumerate(routes):
        s, bids = r[0], r[1]
        m = sum(data.boxes[b]['mass'] for b in bids)
        model = next(mm for mm in 'CBA' if m <= Q[mm] + 1e-9)
        fls.append(Flight(i + 1, [r], model, data))
    return fls

def run(routes, name):
    fls = build(routes)
    # 满载检查
    bad = [(f.fid, f.model, f.mass()) for f in fls if not f.is_feasible()]
    met = check(fls)
    if met is None:
        print('%-24s 不可行! 超载: %s' % (name, bad[:3]))
        return None
    print('%-24s fl=%d mk=%7.1f e=%6.2f hard=%s tardy=%.2f' %
          (name, met['flights'], met['makespan'], met['energy'], met['hard_ok'], met['tardy_w']))
    return (name, met, fls)

outs = []
C1 = run(cand_base(), 'C6_B8_A7 (21趟)')

# ---------- 候选 2：压缩 B——S007/S008 并入 C（C=8 趟）或 B 混合 ----------
def cand_v2():
    routes = []
    # C 7 趟：S001x3 + S004 + S005 + S007 + S008
    routes += pack_area('S001', 'C', 3)
    routes += pack_area('S004', 'C', 1)
    routes += pack_area('S005', 'C', 1)
    routes += pack_area('S007', 'C', 1)
    routes += pack_area('S008', 'C', 1)
    # B 6 趟：S002x4 + S003x2（2+2 箱？不——S003 4 趟→改 2 趟 3+3 箱=30.4 超 → 保持拆分）
    routes += pack_area('S002', 'B', 4)
    routes += pack_area('S003', 'B', 2)   # 3+3 箱 30.4 超——pack 均衡会给 30.4 ✗
    # S006 59kg -> B 2 趟
    routes += pack_area('S006', 'B', 2)
    # A 7 趟
    for s in ['S009', 'S010', 'S011', 'S012', 'S013', 'S014', 'S015']:
        routes.append([s, [b for b, _ in ab[s]]])
    return routes

# S003 2 趟 3+3 会超 30.4——pack_area 均衡后仍超——build() 会选 C? 不——m=60.8 → C 80 ✓
# 但那是 C 拖着 B 的活——行，观察。
C2 = run(cand_v2(), 'C7_B6_A7 (20趟)')

json.dump({'cands': [{'name': r[0], 'flights': r[1]['flights'],
                      'makespan': round(r[1]['makespan'], 1), 'energy': round(r[1]['energy'], 3)}
                     for r in outs if r],
           'routes': {'c1': [[fid, f.model, f.route] for fid, f in
                             (C1 and [(f.fid, f) for f in C1[2]] or [])] if C1 else [],
                      'c2': [[f.fid, f.model, f.route] for f in (C2[2] if C2 else [])] if C2 else []}},
          open(os.path.join(EVO, 'repack_cands.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved repack_cands.json')