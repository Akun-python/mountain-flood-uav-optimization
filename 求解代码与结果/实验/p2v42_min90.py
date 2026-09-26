# -*- coding: utf-8 -*-
"""v42-ν：90min 定向构造器——每机 ≤3 趟（8 机×3=24 趟≈23 架次）、每趟 ≤~1850s。
草案：C 6 趟（S001×2/S002/S004/S005/S006 满载）、B 6 趟（S003×2/S007/S008 3+2）、
A 12 趟（轻区 21 箱 + 剩箱）。dispatch 实测完工/能耗/首飞批，迭代修正。
输出 结果/进化_v42/min90_draft.json。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
data = Data()

# 每区箱（首飞批 -01 前缀保持在前）
def area_boxes(s):
    bs = list(data.area_boxes[s])
    fb = [b for b in bs if b.endswith('-01') or data.boxes[b]['first_batch']]
    rest = [b for b in bs if b not in fb]
    return fb + rest

AB = {s: area_boxes(s) for s in sorted(data.areas)}

def mk(fls, fid, model, segs):
    """segs: [(区, [箱])]"""
    r = [(s, list(b)) for s, b in segs if b]
    mass = sum(data.boxes[b]['mass'] for _, bs in r for b in bs)
    f = Flight(fid, r, model, data)
    if not f.is_feasible():
        print('  ! f%d %s 不可行 m=%.1f %s' % (fid, model, mass, [(s, len(b)) for s, b in r]))
        return None
    return f

# ---- 质量/体积感知分配器（配额 C6/B6/A12，每趟满载） ----
def fill(area, model, max_n, first_pass=False):
    """从 AB[area] 取 ≤max_n 箱（质量降序、可装入），首趟优先首飞批箱。"""
    p = data.uav_types[model]
    pool = list(AB[area])
    if first_pass:
        fb = [b for b in pool if data.boxes[b]['first_batch']]
        pool = fb + [b for b in pool if b not in fb]
    q = sorted(pool, key=lambda b: -data.boxes[b]['mass'])
    take, m, v = [], 0.0, 0.0
    for b in q:
        if len(take) >= max_n:
            break
        bm, bv = data.boxes[b]['mass'], data.boxes[b]['vol']
        if m + bm > p['Q'] + 1e-9 or v + bv > p['V'] + 1e-9:
            continue
        take.append(b); m += bm; v += bv
    for b in take:
        AB[area].remove(b)
    return take

fl = []
fid = 1
# ---- 能量感知装载（构造级回退） ----
def load(area, model, max_n, first_pass=False):
    """返回 (箱列表, Flight) 或 (None, None)。"""
    p = data.uav_types[model]
    pool = list(AB[area])
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
            f = Flight(fid, [(area, cand)], model, data)
            if f.is_feasible():
                for b in cand:
                    AB[area].remove(b)
                return cand, f
    return None, None

# C 6 趟：S001×2、S002、S003、S004、S005（首趟首飞批优先，满载 ≤7 箱）
C_PLAN = [('S001', 2), ('S002', 1), ('S003', 1), ('S004', 1), ('S005', 1)]
for s, cnt in C_PLAN:
    for k in range(cnt):
        bs, f = load(s, 'C', 7, first_pass=(k == 0))
        if f: fl.append(f); fid += 1
# B 6 趟：S006×2、S007×2、S008×2
B_PLAN = [('S006', 2), ('S007', 2), ('S008', 2)]
for s, cnt in B_PLAN:
    for k in range(cnt):
        bs, f = load(s, 'B', 3, first_pass=(k == 0))
        if f: fl.append(f); fid += 1
# A 12 趟：轻区 2 箱/趟 + 重区剩箱（首飞批优先）
light = ['S009', 'S010', 'S011', 'S012', 'S013', 'S014', 'S015']
A_pool = light + [s for s in sorted(data.areas) if s not in light and AB[s]]
for k in range(12):
    s = next((a for a in A_pool if AB[a]), None)
    if s is None:
        break
    bs, f = load(s, 'A', 2, first_pass=(k < 7))
    if f: fl.append(f); fid += 1
# 兜底：剩余任意（不应发生）
while any(AB[a] for a in AB):
    s = next((a for a in sorted(data.areas) if AB[a]), None)
    bs, f = load(s, 'A', 2)
    if f: fl.append(f); fid += 1

sch, _ = dispatch(data, fl)
if sch is None:
    print('dispatch 不可行'); sys.exit(1)
met = evaluate(data, fl, sch)
print('fl=%d mk=%.1f e=%.3f hard=%s tardy=%.2f bad=%d' % (
    met['flights'], met['makespan'], met['energy'], met['hard_ok'],
    met['tardy_w'], len(met['bad_zones'])))
out = {'solver': 'v42-min90-draft', 'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                                                 for k, v in met.items() if k != 'box_time'},
       'flights': [], 'deliveries': []}
for f in fl:
    s = sch[f.fid]
    out['flights'].append({'fid': f.fid, 'uav': s['uav'], 'model': f.model,
                           'battery': s['battery'], 'start': round(s['start'], 1),
                           'return': round(s['return'], 1),
                           'route': [(sid, list(bs)) for sid, bs in f.route],
                           'energy': round(f.energy(), 4), 'nbox': f.nbox,
                           'mass': round(f.total_mass, 2)})
    for sid, bid, t in s['deliveries']:
        out['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
json.dump(out, open(os.path.join(EVO, 'min90_draft.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved min90_draft.json')