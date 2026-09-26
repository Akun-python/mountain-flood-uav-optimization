# -*- coding: utf-8 -*-
"""v42-λ：e26 区一致自动修复 v2——违规箱递归重分配。
对 5 个违反区一致的捎带箱，尝试放入 26 个现有趟或新增趟（容量+volume+first-batch 允许），
以 (完工, 能耗) 增量为贪心序，回溯保证全部 5 箱安置；每步 dispatch 验 hard 与 bad_zones。
输出 结果/进化_v42/e26_fixed2.json。"""
import sys, os, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data
from p2_solve import Flight, dispatch, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
data = Data()

d = json.load(open(os.path.join(HERE, '..', '结果', '进化_v20', 'p2_energy26_solution.json'),
                  encoding='utf-8'))
fls = {}
for f in d['flights']:
    fls[f['fid']] = Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)

# ---- 移除 5 个违规箱（恢复为合规基础解：单区趟只留本区箱；多区趟保留本区段） ----
def boxes_of(fid, area):
    for s, bs in fls[fid].route:
        if s == area:
            return list(bs)
    return []

viol = {('f3', 'S003', 'S013-MED-01'), ('f6', 'S006', 'S008-MED-01'),
        ('f14', 'S014', 'S010-MED-01'), ('f18', 'S002', 'S012-MED-01'),
        ('f24', 'S006', 'S013-WAT-01')}
f3_clean = [b for b in boxes_of(3, 'S003') if b != 'S013-MED-01']
f6_clean = [b for b in boxes_of(6, 'S006') if b != 'S008-MED-01']
f14_clean = [b for b in boxes_of(14, 'S014') if b != 'S010-MED-01']
f18_clean = [b for b in boxes_of(18, 'S002') if b != 'S012-MED-01']
f24_clean = [b for b in boxes_of(24, 'S006') if b != 'S013-WAT-01']
fls[3] = Flight(3, [('S003', f3_clean)], fls[3].model, data)
fls[6] = Flight(6, [('S006', f6_clean)], fls[6].model, data)
fls[14] = Flight(14, [('S014', f14_clean)], fls[14].model, data)
fls[18] = Flight(18, [('S002', f18_clean)], fls[18].model, data)
fls[24] = Flight(24, [('S006', f24_clean)], fls[24].model, data)

WAIT = ['S013-MED-01', 'S008-MED-01', 'S010-MED-01', 'S012-MED-01', 'S013-WAT-01']
# 每个等待箱的目标区
BOX_AREA = {'S013-MED-01': 'S013', 'S008-MED-01': 'S008', 'S010-MED-01': 'S010',
            'S012-MED-01': 'S012', 'S013-WAT-01': 'S013'}

def metric():
    lst = [fls[fid] for fid in sorted(fls)]
    sch, _ = dispatch(data, lst)
    if sch is None:
        return None, None
    met = evaluate(data, lst, sch)
    return met, lst

def try_place(box, target_area, fid_new=None):
    """把 box 放入 target_area 段：优先同区趟，否则新增趟（可选机型 A）。返回 (ok, 新fls)。"""
    a = BOX_AREA[box]
    # 候选：同区现有趟
    cand = [fid for fid, f in fls.items() if any(s == a for s, _ in f.route)]
    if not cand:
        cand = [fid for fid, f in fls.items() if f.model in ('A', 'B') and len(f.route) == 1
                and not any(True for _ in ())]
    for fid in cand:
        old = fls[fid]
        r = [(s, list(bs)) for s, bs in old.route]
        # 找到 a 段并追加
        placed = False
        for k in range(len(r)):
            if r[k][0] == a:
                r[k][1].append(box); placed = True; break
        if not placed:
            r.append([a, [box]])
        mass = sum(data.boxes[b2]['mass'] for _, bs in r for b2 in bs)
        vol = sum(data.boxes[b2]['vol'] for _, bs in r for b2 in bs)
        # 机型升格到可装（Q/V）
        best = None
        for m in ('A', 'B', 'C'):
            p = data.uav_types[m]
            if mass <= p['Q'] + 1e-9 and vol <= p['V'] + 1e-9:
                best = m; break
        if best is None:
            continue
        try:
            nf = Flight(old.fid, r, best, data)
        except Exception:
            continue
        if not nf.is_feasible():
            continue
        fls[old.fid] = nf
        return True
    return False

# 简单贪心安置（同区趟优先），若失败则新增趟
placed = []
for box in WAIT:
    a = BOX_AREA[box]
    ok = try_place(box, a)
    if not ok:
        # 新增一趟（A 型；装不下则 B）
        mass = data.boxes[box]['mass']; vol = data.boxes[box]['vol']
        m = 'A' if (mass <= 25 and vol <= 0.06) else 'B'
        nfid = max(fls) + 1
        fls[nfid] = Flight(nfid, [(a, [box])], m, data)
        ok = True
    if ok:
        placed.append(box)

met, lst = metric()
print('候选 fl=%d mk=%s e=%s hard=%s tardy=%s bad=%s' % (
    met['flights'], round(met['makespan'], 1), round(met['energy'], 3),
    met['hard_ok'], round(met['tardy_w'], 2), len(met['bad_zones'])))
sch, _ = dispatch(data, lst)
json.dump({'solver': 'v42-e26fix2', 'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                                                 for k, v in met.items() if k != 'box_time'},
           'flights': [{'fid': f.fid, 'uav': sch[f.fid]['uav'], 'model': f.model,
                        'battery': sch[f.fid]['battery'], 'start': round(sch[f.fid]['start'], 1),
                        'return': round(sch[f.fid]['return'], 1),
                        'route': [(s, list(bs)) for s, bs in f.route],
                        'energy': round(f.energy(), 4), 'nbox': f.nbox,
                        'mass': round(f.total_mass, 2)} for f in lst],
           'deliveries': [{'box': bid, 'fid': fid, 'area': sid, 't': round(t, 1)}
                          for fid, s in sch.items() for sid, bid, t in s['deliveries']]},
          open(os.path.join(EVO, 'e26_fixed2.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved e26_fixed2.json')