# -*- coding: utf-8 -*-
"""v42-φ：90min 构造 v12（最终版）——v4 分配 + v11 load(-01 强制同趟)：
C 6：S001×2、S002、S003、S004、S005（40 箱）
B 6：S009-S014 各 3 箱（18 箱，含 -01 强制）
A 12：S015 3+S006 6+S007 5+S008 5+S001/S002/S003 尾（22 箱）
24 趟 80 箱；EDF 排产验证。"""
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

def load(area, model, max_n, first_pass=False, exclude_first=False):
    p = data.uav_types[model]
    pool = list(data.area_boxes[area])
    fb = [b for b in pool if b.endswith('-01')]
    if first_pass:
        if not fb:
            return None, None
        import itertools
        rest = [b for b in pool if b not in fb]
        best_cand, best_m = None, -1.0
        for add_n in range(max_n - len(fb), -1, -1):
            if add_n > len(rest):
                continue
            for comb in itertools.combinations(rest, add_n):
                cand = list(fb) + list(comb)
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
    import itertools
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

# C 6 趟：重区满载（首飞批区 S001/S002/S003 前排）
add('C', 'S001', 7, True)
add('C', 'S002', 7, True)
add('C', 'S003', 7, True)
add('C', 'S001', 7, False, True)
add('C', 'S004', 6, True)
add('C', 'S005', 6, True)
# B 6 趟：轻区 3 箱（-01 强制同趟；S013/S014 3600 硬区）
for s in ('S009', 'S010', 'S011', 'S012', 'S013', 'S014'):
    add('B', s, 3, True)
# A 12 趟：S015+S006+S007+S008+重区尾（2 箱/趟拼）
for s in ('S015', 'S006', 'S007', 'S008', 'S015', 'S006', 'S007', 'S008', 'S015', 'S006', 'S007', 'S008'):
    add('A', s, 2, True)
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