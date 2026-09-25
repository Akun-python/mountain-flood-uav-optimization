# -*- coding: utf-8 -*-
"""v25c：整骨修复——26 架骨架 + 机队感知最小修正（尽量保留原机型，避免机队失衡）。
流程：跨区箱挂回属区段 → 原机型优先验证（次选换型）→ 不可行减载 → 摘出箱归位
（已有属区段架次原机型优先）→ 剩余合并最少新架次。输出指标 + 机型分布 + 零跨区。
"""
import sys, os, json, math, itertools, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data
from p2_solve import Flight, dispatch, evaluate

data = Data()
o = data.centers[data.OID]
def angle(sid):
    a = data.areas[sid]
    return math.atan2(a['lat'] - o['lat'], a['lon'] - o['lon'])

old = subprocess.run(['git', 'show', 'afc4405:求解代码与结果/results/p2_results.json'],
                     capture_output=True, text=True, encoding='utf-8')
p2 = json.loads(old.stdout)

by_flight = {}
for f in p2['flights']:
    fz = {}
    for s, bs in f['route']:
        for b in bs:
            fz.setdefault(b.split('-')[0], []).append(b)
    by_flight[f['fid']] = {'model': f['model'], 'zones': fz}

def best_route(fz, models):
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

need_move = []
for fid, d in sorted(by_flight.items()):
    zz = {z: list(bs) for z, bs in d['zones'].items()}
    # 优先原机型（再试 A、C、B 顺序）
    ok = False
    for g in [d['model']] + [x for x in ('A', 'B', 'C') if x != d['model']]:
        r, gg, e = best_route(zz, (g,))
        if r is not None:
            d['model'] = g
            d['zones'] = {z: list(bs) for z, bs in r}
            ok = True
            break
    if ok:
        continue
    # 减载：摘非紧急箱（离 O 远/重者优先）
    progressed = True
    while progressed:
        progressed = False
        for g in [d['model']] + [x for x in ('A', 'B', 'C') if x != d['model']]:
            r, gg, e = best_route(zz, (g,))
            if r is not None:
                d['model'] = g
                d['zones'] = {z: list(bs) for z, bs in r}
                progressed = True
                break
        if progressed:
            break
        def prio(z, b):
            bx = data.boxes[b]
            return (0 if (bx['first_batch'] or bx['type'] == '医疗物资') else 1,
                    -data.dist_ll(o['lon'], o['lat'], data.areas[z]['lon'], data.areas[z]['lat']),
                    -bx['mass'])
        cands = [(z, b) for z, bs in zz.items() for b in bs]
        if not cands:
            break
        cands.sort(key=lambda x: prio(*x))
        z, b = cands[0]
        zz[z].remove(b)
        if not zz[z]:
            del zz[z]
        need_move.append((fid, b))
        progressed = True

# 摘出箱归位：已有属区段架次（原机型优先，再其他）
placed = []
pending = []
for fid, b in need_move:
    pjx = b.split('-')[0]
    dest = None
    for tfid, td in sorted(by_flight.items()):
        if tfid == fid or pjx not in td['zones']:
            continue
        tz = {z: list(bs) for z, bs in td['zones'].items()}
        tz[pjx] = tz[pjx] + [b]
        r, g, e = best_route(tz, (td['model'],))
        if r is not None:
            td['zones'] = {z: list(bs) for z, bs in r}
            dest = tfid
            break
        r, g, e = best_route(tz, ('A', 'B', 'C'))
        if r is not None:
            td['model'] = g
            td['zones'] = {z: list(bs) for z, bs in r}
            dest = tfid
            break
    if dest is not None:
        placed.append((b, dest))
    else:
        pending.append(b)

# 新架次（同区合并；机型按能量最优）
newfid = max(by_flight) + 1
pend_by_zone = {}
for b in pending:
    pend_by_zone.setdefault(b.split('-')[0], []).append(b)
for z, boxes in sorted(pend_by_zone.items()):
    r, g, e = best_route({z: boxes}, ('A', 'B', 'C'))
    assert r is not None, '新架次 %s %s 不可行!' % (z, boxes)
    by_flight[newfid] = {'model': g, 'zones': {z: boxes}}
    print('新架次 f%02d %s型 %s %s e=%.2f' % (newfid, g, z, boxes, e))
    newfid += 1

fl = []
for fid, d in sorted(by_flight.items()):
    route = [(z, d['zones'][z]) for z in sorted(d['zones'], key=angle)]
    f = Flight(fid, route, d['model'], data)
    if not f.is_feasible():
        print('!! f%02d 不可行: %s mass=%.0f vol=%.3f e=%.2f' % (fid, d['model'], f.total_mass, f.total_vol, f.energy()))
    fl.append(f)
bad = [(f.fid, b, s) for f in fl for s, bs in f.route for b in bs if b.split('-')[0] != s]
print('零跨区复核: %d 处' % len(bad))
sch, _ = dispatch(data, fl)
met = evaluate(data, fl, sch)
print('evaluate: hard_ok=%s tardy=%.2f makespan=%.1f energy=%.2f flights=%d bad_zones=%d'
      % (met['hard_ok'], met['tardy_w'], met['makespan'], met['energy'], met['flights'], len(met['bad_zones'])))
from collections import Counter
print('机型分布: %s' % dict(Counter(f.model for f in fl)))
print('归位 %d 箱，新架次 %d' % (len(placed), newfid - (max(by_flight) + 1) + len(pend_by_zone)))
for f in sorted(fl, key=lambda x: x.fid):
    print('f%02d %s %s' % (f.fid, f.model, [(s, len(bs)) for s, bs in f.route]))