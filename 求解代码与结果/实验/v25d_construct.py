# -*- coding: utf-8 -*-
"""v25d：27 架精细构造——26 架骨架 + 显式归位映射（跨区箱全部收编或并入已有架次），
只有 S004[HYG,FOD] 需要 1 个新架次。关键：段序用 best_route 最优序并保序（不重排）。
"""
import sys, os, json, math, itertools, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data
from p2_solve import Flight, dispatch, evaluate

data = Data()
old = subprocess.run(['git', 'show', 'afc4405:求解代码与结果/results/p2_results.json'],
                     capture_output=True, text=True, encoding='utf-8')
p2 = json.loads(old.stdout)

# 每架：按属区收箱（跨区箱挂回属区段）
by_flight = {}
for f in p2['flights']:
    fz = {}
    for s, bs in f['route']:
        for b in bs:
            fz.setdefault(b.split('-')[0], []).append(b)
    by_flight[f['fid']] = {'model': f['model'], 'zones': fz}

def best_route(fz, models=('A', 'B', 'C')):
    zones = list(fz)
    best = None; best_e = math.inf; best_g = None
    perms = list(itertools.permutations(zones)) if len(zones) <= 5 else [tuple(zones)]
    for g in models:
        for perm in perms:
            route = [(z, fz[z]) for z in perm]
            f = Flight(0, route, g, data)
            if f.is_feasible() and f.energy() < best_e:
                best_e, best, best_g = f.energy(), route, g
    return best, best_g, best_e

# ---- 显式归位映射：箱 -> 目标架次（fid 为 v24 编号）----
place = {
    'S002-MED-01': 10,   # f10 加 S002 段（B 型，顺路）
    'S010-FOD-01': 10,   # f10 加 S010 段第 2 箱
    'S010-MED-01': 14,   # f14 加 S010 段（B，e 2.16）
    'S012-MED-01': 12,   # f12 收（S012 段）
    'S008-MED-01': 8,    # f08 收（S008 段）
    'S013-MED-01': 24,   # f24 收（S006+S013 双区 C 型）
    'S013-WAT-01': 24,   # f24 收
    'S013-FOD-01': 24,   # f24 收
    'S002-FOD-01': 31,   # f31 收（S002 段，单区 B）
    'S012-FOD-01': 32,   # f32 加 S012 段（B，e 3.03）
    'S008-FOD-01': 35,   # f35 加 S008 段（B，e 3.16，段序 S007 先）
    'S002-FOD-02': 18,   # f18 收（S002 段，C 5 箱）
    'S007-HYG-01': 99,   # 99 = 新架次
    'S004-HYG-01': 99,
    'S004-FOD-01': 99,
    'S005-WAT-02': 5,    # f23 的 S005 箱并入 f05（C 型主架次）
    'S005-WAT-03': 5,
    'S005-FOD-01': 5,
    'S005-HYG-01': 5,
}
# 先摘除所有要移动的箱，再放入目标
move_boxes = list(place)
for fid in list(by_flight):
    zz = by_flight[fid]['zones']
    for z in list(zz):
        zz[z] = [b for b in zz[z] if b not in move_boxes or place[b] == fid]
        if not zz[z]:
            del zz[z]
for b, tf in place.items():
    if tf == 99:
        continue
    pjx = b.split('-')[0]
    if b not in by_flight[tf]['zones'].get(pjx, []):
        by_flight[tf]['zones'].setdefault(pjx, []).append(b)

# 新架次：S004 剩余 2 箱 + S007 剩余 1 箱
newfid = max(by_flight) + 1
by_flight[newfid] = {'model': 'B', 'zones': {'S004': ['S004-HYG-01', 'S004-FOD-01']}}
by_flight[newfid + 1] = {'model': 'A', 'zones': {'S007': ['S007-HYG-01']}}

# 删除摘空的架次
for fid in [f for f in list(by_flight) if not by_flight[f]['zones']]:
    del by_flight[fid]
# 逐架：原机型优先 → 换型（保持段序最优）
fl = []
for fid, d in sorted(by_flight.items()):
    r, g, e = best_route(d['zones'], (d['model'],))
    if r is None:
        r, g, e = best_route(d['zones'])
        if r is None:
            print('!! f%02d 全机型不可行: %s' % (fid, {z: len(bs) for z, bs in d['zones'].items()}))
            continue
    f = Flight(fid, r, g, data)
    fl.append(f)
    if not f.is_feasible():
        print('!! f%02d %s 仍不可行: %s mass=%.0f vol=%.3f e=%.2f' % (fid, g, [(s, len(bs)) for s, bs in r], f.total_mass, f.total_vol, f.energy()))

bad = [(f.fid, b, s) for f in fl for s, bs in f.route for b in bs if b.split('-')[0] != s]
print('零跨区复核: %d 处 架次=%d' % (len(bad), len(fl)))
sch, _ = dispatch(data, fl)
met = evaluate(data, fl, sch)
print('evaluate: hard_ok=%s tardy=%.2f makespan=%.1f energy=%.2f flights=%d bad_zones=%d'
      % (met['hard_ok'], met['tardy_w'], met['makespan'], met['energy'], met['flights'], len(met['bad_zones'])))
from collections import Counter
print('机型分布: %s' % dict(Counter(f.model for f in fl)))
# 电池满充复核
from core import charge_time
bats = {}
for fid, s in sch.items():
    bats.setdefault(s['battery'], []).append(s)
issues = 0
for b, segs in bats.items():
    segs.sort(key=lambda x: x['start'])
    for k in range(1, len(segs)):
        gap = segs[k]['start'] - segs[k-1]['return']
        # 前一任务的满充时长（近似 soc 下限）
        issues += 1 if gap < 0 else 0
print('电池复用间隔检查: %d 处负间隔' % issues)
for f in sorted(fl, key=lambda x: x.fid):
    print('f%02d %s %s' % (f.fid, f.model, [(s, len(bs)) for s, bs in f.route]))
json.dump([{'fid': f.fid, 'model': f.model, 'route': [(s, list(bs)) for s, bs in f.route]}
           for f in fl], open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples', 'v25d_routes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)