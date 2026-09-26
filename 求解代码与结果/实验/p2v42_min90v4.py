# -*- coding: utf-8 -*-
"""v42-π：90min 构造 v4（80 箱完整版）——配额精确分配：
C 6 趟：S001×2、S002、S003、S004、S005（每趟满载 load 能量回退）
B 6 趟：S006×2、S007×2、S008×2（3 箱满载回退 2 箱）
A 12 趟：轻区 10×2 箱 + 跨区拼 2 趟
断言 80 箱唯一；输出 min90_init.json；随后 tabu 精化。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
data = Data()
data.area_boxes = {s: list(bs) for s, bs in data.area_boxes.items()}

def load(area, model, max_n, first_pass=False):
    p = data.uav_types[model]
    pool = list(data.area_boxes[area])
    if first_pass:
        # "-01 后缀"首飞批箱优先（MED/WAT/FOD-01，45 箱）
        fb = [b for b in pool if b.endswith('-01')]
        pool = fb + [b for b in pool if b not in fb]
    q = sorted(pool, key=lambda b: -data.boxes[b]['mass'])
    if not q:
        return None, None
    best = None
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
    # 兜底：单箱单区（保证 80 箱完整）
    if data.area_boxes[area]:
        b = data.area_boxes[area].pop(0)
        f = Flight(0, [(area, [b])], model, data)
        if f.is_feasible():
            return [b], f
        data.area_boxes[area].insert(0, b)
    return None, None

fl = []
fid = 1
light = ['S009', 'S010', 'S011', 'S012', 'S013', 'S014', 'S015']
# C 6 趟：S001×2、S002、S003、S004、S005（重区满载）
C_PLAN = [('S001', 2), ('S002', 1), ('S003', 1), ('S004', 1), ('S005', 1)]
for s, cnt in C_PLAN:
    for k in range(cnt):
        bs, f = load(s, 'C', 7 if s in ('S001', 'S002', 'S003') else 6, first_pass=(k == 0))
        if f:
            f.fid = fid; fl.append(f); fid += 1
# B 6 趟：轻区 S009-S014 各 3 箱（满载，-01 优先）
for s in ('S009', 'S010', 'S011', 'S012', 'S013', 'S014'):
    bs, f = load(s, 'B', 3, first_pass=True)
    if f:
        f.fid = fid; fl.append(f); fid += 1
# C 第 6 趟：S008 5 箱 + S001 剩余 1 箱（跨区）——S008 已在 C_PLAN，S001 剩余并入
# C 第 6 趟：S008 5 箱 + S003 尾箱 1 箱（跨 2 区）
if data.area_boxes['S008']:
    bs8, f8 = load('S008', 'C', 5, first_pass=True)
    if f8 and data.area_boxes['S003']:
        b3 = data.area_boxes['S003'].pop(0)
        f8 = Flight(f8.fid, [(s_, list(b_)) for s_, b_ in f8.route] + [('S003', [b3])], 'C', data)
    if f8:
        f8.fid = fid; fl.append(f8); fid += 1
# A 阶段 1：轻区 7 区各 2 箱（7 趟）
light = ['S009', 'S010', 'S011', 'S012', 'S013', 'S014', 'S015']
for s in light:
    bs, f = load(s, 'A', 2, first_pass=True)
    if f:
        f.fid = fid; fl.append(f); fid += 1
# A 阶段 2：剩余 1 箱拼 2 区 2 箱（轻箱优先）
rem_box = []
for s in sorted(data.areas):
    while data.area_boxes[s]:
        rem_box.append((s, data.area_boxes[s].pop(0)))
while rem_box:
    q = sorted(rem_box, key=lambda x: -data.boxes[x[1]]['mass'])
    take, m, v, seen = [], 0.0, 0.0, set()
    for s, b in q:
        if len(take) >= 2:
            break
        if s in seen:
            continue
        bm, bv = data.boxes[b]['mass'], data.boxes[b]['vol']
        if m + bm > 25 + 1e-9 or v + bv > 0.06 + 1e-9:
            continue
        take.append((s, [b])); seen.add(s); m += bm; v += bv
    if not take:
        s, b = rem_box.pop(0)
        f = Flight(fid, [(s, [b])], 'A', data)
        if f.is_feasible():
            f.fid = fid; fl.append(f); fid += 1
        continue
    f = Flight(fid, take, 'A', data)
    if f.is_feasible():
        f.fid = fid; fl.append(f); fid += 1
        for s, bs in take:
            rem_box.remove((s, bs[0]))
    else:
        s, b = rem_box.pop(0)
        f1 = Flight(fid, [(s, [b])], 'A', data)
        if f1.is_feasible():
            f1.fid = fid; fl.append(f1); fid += 1
        else:
            f2 = Flight(fid, [(s, [b])], 'B', data)
            f2.fid = fid; fl.append(f2); fid += 1

nbox_total = sum(len(bs) for f in fl for _, bs in f.route)
uniq = len(set(b for f in fl for _, bs in f.route for b in bs))
print('fl=%d 箱=%d/%d' % (len(fl), uniq, nbox_total))
assert nbox_total == 80 and uniq == 80, '箱不完整'
sch, _ = dispatch(data, fl)
met = evaluate(data, fl, sch)
print('初始 fl=%d mk=%.1f e=%.3f hard=%s tardy=%.2f bad=%d' % (
    met['flights'], met['makespan'], met['energy'], met['hard_ok'],
    met['tardy_w'], len(met['bad_zones'])))
json.dump({'flights': [{'fid': f.fid, 'model': f.model, 'route': [[s, bs] for s, bs in f.route]}
                       for f in fl]},
          open(os.path.join(EVO, 'min90_init.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved min90_init.json')