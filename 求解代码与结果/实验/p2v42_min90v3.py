# -*- coding: utf-8 -*-
"""v42-ξ：90min 定向构造 v3 —— C 6 趟(重区,S003提前) + B 6 趟(2箱) + A 12 趟(轻区+跨区拼)
生成 24 趟初始解 -> tabu 完工强权重精化 -> 官方复核。
输出 结果/进化_v42/min90_init.json / min90_tabu.json。"""
import sys, os, json, copy, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate
from common import set_weights, clone_flights, TimeBudget
from solvers import tabu_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
data = Data()

def AB(s):
    bs = list(data.area_boxes[s])
    fb = [b for b in bs if data.boxes[b]['first_batch']]
    rest = [b for b in bs if b not in fb]
    return fb + rest

def load(area, model, max_n, first_pass=False):
    p = data.uav_types[model]
    pool = list(AB(area))
    if first_pass:
        fb = [b for b in pool if data.boxes[b]['first_batch']]
        pool = fb + [b for b in pool if b not in fb]
    q = sorted(pool, key=lambda b: -data.boxes[b]['mass'])
    for n in range(max_n, 0, -1):
        for skip in range(0, max(1, len(q) - n + 1)):
            cand = q[skip:skip + n]
            m = sum(data.boxes[b]['mass'] for b in cand)
            v = sum(data.boxes[b]['vol'] for b in cand)
            if m > p['Q'] + 1e-9 or v > p['V'] + 1e-9:
                continue
            f = Flight(0, [(area, cand)], model, data)
            if f.is_feasible():
                for b in cand:
                    data.area_boxes[area].remove(b)
                return cand, f
    return None, None

fl = []
fid = 1
# C 6 趟：S001×2、S003、S002、S004、S005（S003 提前保首飞批）
C_PLAN = [('S001', 2), ('S003', 1), ('S002', 1), ('S004', 1), ('S005', 1)]
for s, cnt in C_PLAN:
    for k in range(cnt):
        bs, f = load(s, 'C', 7, first_pass=(k == 0))
        if f:
            f.fid = fid; fl.append(f); fid += 1
# B 6 趟：S006×2、S007×2、S008×2
B_PLAN = [('S006', 2), ('S007', 2), ('S008', 2)]
for s, cnt in B_PLAN:
    for k in range(cnt):
        bs, f = load(s, 'B', 3, first_pass=(k == 0))
        if f:
            f.fid = fid; fl.append(f); fid += 1
# A 12 趟：轻区 10 趟 2 箱 + 跨区拼 2 趟
light = ['S009', 'S010', 'S011', 'S012', 'S013', 'S014', 'S015']
for _ in range(10):
    s = next((a for a in light if data.area_boxes[a]), None)
    if s is None:
        break
    bs, f = load(s, 'A', 2)
    if f:
        f.fid = fid; fl.append(f); fid += 1
# 剩余（轻区 1 箱 + 重区剩箱）跨区拼 3 箱/趟
rem_box = []
for s in sorted(data.areas):
    while data.area_boxes[s]:
        rem_box.append((s, data.area_boxes[s].pop(0)))
while rem_box:
    take = []
    for _ in range(3):
        if rem_box:
            s, b = rem_box.pop(0)
            take.append((s, [b]))
    merged = {}
    for s, bs in take:
        merged.setdefault(s, []).extend(bs)
    take = [(s, bs) for s, bs in merged.items()]
    m = sum(data.boxes[x]['mass'] for _, bs in take for x in bs)
    v = sum(data.boxes[x]['vol'] for _, bs in take for x in bs)
    if m <= 25 and v <= 0.06:
        f = Flight(fid, take, 'A', data)
        if f.is_feasible():
            f.fid = fid; fl.append(f); fid += 1
            continue
    # 失败：拆成单区单箱趟兜底
    for s, bs in take:
        for b in bs:
            f = Flight(fid, [(s, [b])], 'A', data)
            if f.is_feasible():
                f.fid = fid; fl.append(f); fid += 1

nbox_total = sum(len(bs) for f in fl for _, bs in f.route)
uniq = len(set(b for f in fl for _, bs in f.route for b in bs))
assert nbox_total == 80 and uniq == 80, '箱不完整: %d/%d' % (uniq, nbox_total)
sch, _ = dispatch(data, fl)
met = evaluate(data, fl, sch)
print('初始 fl=%d mk=%.1f e=%.3f hard=%s tardy=%.2f bad=%d' % (
    met['flights'], met['makespan'], met['energy'], met['hard_ok'],
    met['tardy_w'], len(met['bad_zones'])))
json.dump({'flights': [{'fid': f.fid, 'model': f.model, 'route': [[s, bs] for s, bs in f.route]}
                       for f in fl]},
          open(os.path.join(EVO, 'min90_init.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

# ---- tabu 精化（完工强权重） ----
set_weights(10.0, 0.5, 0.5, 10.0)
best_fl, best_met = None, None
for seed in (7, 11, 13, 17):
    t0 = time.time()
    fl2, met2 = tabu_optimize(data, clone_flights(fl), TimeBudget(120), seed)
    if met2 and (best_met is None or met2['makespan'] < best_met['makespan']):
        best_fl, best_met = fl2, met2
print('tabu 完工最优: fl=%d mk=%.1f e=%.3f hard=%s (%.0fs)' % (
    len(best_fl), best_met['makespan'], best_met['energy'], best_met['hard_ok'],
    time.time() - t0))