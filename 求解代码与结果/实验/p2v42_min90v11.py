# -*- coding: utf-8 -*-
"""v42-υ：90min 构造 v11（第一性完备）——8 硬区(3600s)首飞批=8 机首趟：
C(U07/U08): S001、S002   B(U05/U06): S006、S007   A(U01-U04): S010/S012/S013/S014
SPD 区(7200/10800)走后段；满载剩余；24 趟 80 箱；dispatch 排产验证。"""
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
        # 强制包含全部 -01 箱再补满（质量/体积/能量可行）
        if not fb:
            return None, None
        rest = sorted([b for b in pool if b not in fb], key=lambda b: -data.boxes[b]['mass'])
        cand = list(fb)
        m = sum(data.boxes[b]['mass'] for b in cand)
        v = sum(data.boxes[b]['vol'] for b in cand)
        for b in rest:
            if len(cand) >= max_n:
                break
            if m + data.boxes[b]['mass'] > p['Q'] + 1e-9 or v + data.boxes[b]['vol'] > p['V'] + 1e-9:
                continue
            cand.append(b); m += data.boxes[b]['mass']; v += data.boxes[b]['vol']
        f = Flight(0, [(area, cand)], model, data)
        if f.is_feasible():
            for b in cand:
                data.area_boxes[area].remove(b)
            return cand, f
        return None, None
    pool = [b for b in pool if b not in fb] if exclude_first else pool
    if not pool:
        return None, None
    for n in range(max_n, 0, -1):
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

# 波 1（8 硬区满载趟，含首飞批 → EDF 前 8 位 → 0s 起飞）
add('C', 'S001', 7, True)
add('C', 'S002', 7, True)
add('B', 'S006', 3, True)
add('B', 'S007', 3, True)
add('A', 'S010', 2, True)
add('A', 'S012', 2, True)
add('A', 'S013', 2, True)
add('A', 'S014', 2, True)
# 波 2（7200/10800 区满载）
add('C', 'S003', 7, True)
add('C', 'S004', 6, True)
add('B', 'S005', 3, True)
add('B', 'S008', 3, True)
add('A', 'S009', 2, True)
add('A', 'S011', 2, True)
add('A', 'S015', 2, True)
add('C', 'S001', 7, False, True)
# 波 3（尾箱满载）
add('C', 'S002', 7, False, True)
add('C', 'S008', 5, False, True)
add('B', 'S005', 3, False, True)
add('B', 'S006', 3, False, True)
add('A', 'S010', 2, False, True)
# 剩余拼（A 2 箱跨区 / 单区）
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