# -*- coding: utf-8 -*-
"""v42-χ：90min 构造 v13（B 重区 + C 重区/轻区 + A 轻区尾）：
C 6：S001×2、S002、S003、S004、(S009+S011 混合)
B 6：S006 3+3、S007 3+2、S008 3+2
A：S010+S012+S013+S014+S015+S001/S002/S003 尾 + S009/S011 剩
20-21 趟 80 箱。"""
import sys, os, json, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
data = Data()
data.area_boxes = {s: list(bs) for s, bs in data.area_boxes.items()}

def load(area, model, max_n, first_pass=False, exclude_first=False):
    p = data.uav_types[model]
    pool = list(data.area_boxes[area])
    fb = [b for b in pool if b.endswith('-01')]
    if first_pass:
        if not fb:
            return None, None
        # 基座 = 最多 max_n 个 -01（first_batch 标记优先），再组合补满
        fb_sorted = sorted(fb, key=lambda b: not data.boxes[b]['first_batch'])
        rest = [b for b in pool if b not in fb]
        best_cand, best_m = None, -1.0
        for base_n in range(min(len(fb_sorted), max_n), 0, -1):
            base = fb_sorted[:base_n]
            max_add = max_n - base_n
            for add_n in range(max_add, -1, -1):
                if add_n > len(rest):
                    continue
                for comb in itertools.combinations(rest, add_n):
                    cand = list(base) + list(comb)
                    m = sum(data.boxes[b]['mass'] for b in cand)
                    v = sum(data.boxes[b]['vol'] for b in cand)
                    if m > p['Q'] + 1e-9 or v > p['V'] + 1e-9:
                        continue
                    f = Flight(0, [(area, cand)], model, data)
                    if f.is_feasible() and m > best_m:
                        best_cand, best_m = cand, m
        if best_cand:
            for b in best_cand:
                data.area_boxes[area].remove(b)
            f = Flight(0, [(area, best_cand)], model, data)
            return best_cand, f
        return None, None
    pool = [b for b in pool if b not in fb] if exclude_first else pool
    if not pool:
        return None, None
    for n in range(min(max_n, len(pool)), 0, -1):
        best_cand, best_m = None, -1.0
        for comb in itertools.combinations(pool, n):
            m = sum(data.boxes[b]['mass'] for b in comb)
            v = sum(data.boxes[b]['vol'] for b in comb)
            if m > p['Q'] + 1e-9 or v > p['V'] + 1e-9:
                continue
            f = Flight(0, [(area, list(comb))], model, data)
            if f.is_feasible() and m > best_m:
                best_cand, best_m = list(comb), m
        if best_cand:
            for b in best_cand:
                data.area_boxes[area].remove(b)
            f = Flight(0, [(area, best_cand)], model, data)
            return best_cand, f
    return None, None

fl = []
fid = 1
def add(model, area, max_n, first_pass=False, exclude_first=False):
    global fid
    bs, f = load(area, model, max_n, first_pass, exclude_first)
    if f:
        f.fid = fid; fl.append(f); fid += 1

# C 5 趟重区（首飞批区 S001/S002/S003 前）
add('C', 'S001', 7, True)
add('C', 'S002', 7, True)
add('C', 'S003', 7, True)
add('C', 'S001', 7, False, True)
add('C', 'S004', 6, True)
# C 第 6 趟：S005 6 箱（10800 区，满载）
add('C', 'S005', 6, True)
# B 6 趟：S006 3+3、S007 3+2、S008 3+2
add('B', 'S006', 3, True)
add('B', 'S007', 3, True)
add('B', 'S008', 3, True)
add('B', 'S006', 3, False, True)
add('B', 'S007', 3, False, True)
add('B', 'S008', 3, False, True)
# A：轻区硬区（S010/S012/S013/S014）+ S015 + 尾箱
for s in ('S010', 'S012', 'S013', 'S014', 'S015'):
    add('A', s, 2, True)
for s in ('S010', 'S012', 'S013', 'S014', 'S015'):
    add('A', s, 2, False, True)
# 尾箱拼（A 2 箱跨区）
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
        f1.fid = fid; fl.append(f1); fid += 1

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