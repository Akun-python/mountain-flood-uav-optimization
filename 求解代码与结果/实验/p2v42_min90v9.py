# -*- coding: utf-8 -*-
"""v42-σ：90min 构造 v9（首飞批波次显式）——23-24 趟 80 箱：
波1(0s)  C:S001/S003  B:S004/S005  A:S008/S009/S010/S011
波2(1204-2169) C:S002/S001-2  B:S006/S007  A:S012/S013/S014/S015
波3  满载补（非首飞批）
输出 min90_init.json。"""
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
        fb = [b for b in pool if b.endswith('-01')]
        pool = fb + [b for b in pool if b not in fb]
    q = sorted(pool, key=lambda b: -data.boxes[b]['mass'])
    if not q:
        return None, None
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
def add(model, area, max_n, first_pass=False):
    global fid
    bs, f = load(area, model, max_n, first_pass)
    if f:
        f.fid = fid; fl.append(f); fid += 1

# 波 1（0s 起飞：C/B/A 各机首趟）
add('C', 'S001', 7, True)
add('C', 'S003', 7, True)
add('B', 'S004', 3, True)
add('B', 'S005', 3, True)
add('A', 'S008', 2, True)
add('A', 'S009', 2, True)
add('A', 'S010', 2, True)
add('A', 'S011', 2, True)
# 波 2（~1204-2169s 起飞）
add('C', 'S002', 7, True)
add('C', 'S001', 7, False)      # S001 第 2 趟（非首飞批）
add('B', 'S006', 3, True)
add('B', 'S007', 3, True)
add('A', 'S012', 2, True)
add('A', 'S013', 2, True)
add('A', 'S014', 2, True)
add('A', 'S015', 2, True)
# 波 3：满载补（非首飞批区）
add('C', 'S004', 6, False)
add('C', 'S005', 6, False)
add('B', 'S008', 3, False)
add('B', 'S005', 3, False)
add('B', 'S006', 3, False)
add('A', 'S009', 2, False)
# A 尾箱拼（轻区 1 箱 3 区拼 + 重区尾）
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