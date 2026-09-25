# -*- coding: utf-8 -*-
"""v25b 构造：26 架骨架（v24）上做最小归位修正 → 零跨区 + 全部可行 + 尽量少新增架次。

归位原则：跨区箱尽量留在原架次（换 B 型 + 最优段序）；重载 C 型减载后把箱移给
已有属区段架次；无处可去者新增正确区段架次（机型选最优）。
输出：新 flights 列表 + evaluate 指标（零跨区/零迟到）+ 机队机型压力。
"""
import sys, os, json, math, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data
from p2_solve import Flight, dispatch, evaluate

data = Data()
o = data.centers[data.OID]
def angle(sid):
    a = data.areas[sid]
    return math.atan2(a['lat'] - o['lat'], a['lon'] - o['lon'])

# v24 26 架（git 取）
import subprocess
old = subprocess.run(['git', 'show', 'afc4405:求解代码与结果/results/p2_results.json'],
                     capture_output=True, text=True, encoding='utf-8')
p2 = json.loads(old.stdout)

# 1) 每架按属区归位（跨区箱挂回属区段）
by_flight = {}   # fid -> {'model': g, 'zones': {z: [boxes]}}
for f in p2['flights']:
    fz = {}
    for s, bs in f['route']:
        for b in bs:
            fz.setdefault(b.split('-')[0], []).append(b)
    by_flight[f['fid']] = {'model': f['model'], 'zones': fz}

def best_route(fz, models=('A', 'B', 'C')):
    """枚举段序+机型，返回 (Flight or None, model, energy)。"""
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

# 2) 逐架决策：原架次尽量保留（换型+最优序），失败则减载（摘非紧急箱）待归位
need_move = []          # (fid, box)
for fid, d in sorted(by_flight.items()):
    zz = {z: list(bs) for z, bs in d['zones'].items()}
    progressed = True
    while progressed:
        progressed = False
        r, g, e = best_route(zz)
        if r is not None:
            d['model'] = g
            d['zones'] = {z: list(bs) for z, bs in r}
            break
        # 摘箱：非首批/非医疗优先，其次质量大、区离 O 远；医疗/首批最后摘
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

# 3) 待移箱归位：优先已有属区段架次（换型后可行），否则待新架次
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
        r, g, e = best_route(tz)
        if r is not None:
            td['model'] = g
            td['zones'] = {z: list(bs) for z, bs in r}
            dest = tfid
            break
    if dest is not None:
        placed.append((b, dest))
    else:
        pending.append(b)

# 4) 待新架次：按属区合并
newfid = max(by_flight) + 1
pend_by_zone = {}
for b in pending:
    pend_by_zone.setdefault(b.split('-')[0], []).append(b)
for z, boxes in sorted(pend_by_zone.items()):
    r, g, e = best_route({z: boxes})
    assert r is not None, '新架次 %s %s 不可行!' % (z, boxes)
    by_flight[newfid] = {'model': g, 'zones': {z: boxes}}
    print('新架次 f%02d %s型 %s %s e=%.2f' % (newfid, g, z, boxes, e))
    newfid += 1

# 5) 构造 + 全验证
fl = []
for fid, d in sorted(by_flight.items()):
    route = [(z, d['zones'][z]) for z in sorted(d['zones'], key=angle)]
    f = Flight(fid, route, d['model'], data)
    if not f.is_feasible():
        print('!! f%02d 不可行: %s %s mass=%.0f vol=%.3f e=%.2f' % (fid, d['model'], [(s, len(bs)) for s, bs in route], f.total_mass, f.total_vol, f.energy()))
    fl.append(f)
# 零跨区复核
bad = [(f.fid, b, s) for f in fl for s, bs in f.route for b in bs if b.split('-')[0] != s]
print('零跨区复核: %d 处跨区' % len(bad))
sch, _ = dispatch(data, fl)
met = evaluate(data, fl, sch)
print('evaluate: hard_ok=%s tardy=%.2f makespan=%.1f energy=%.2f flights=%d bad_zones=%d'
      % (met['hard_ok'], met['tardy_w'], met['makespan'], met['energy'], met['flights'], len(met['bad_zones'])))
from collections import Counter
mc = Counter(f.model for f in fl)
print('机型分布: %s' % dict(mc))
print()
for f in sorted(fl, key=lambda x: x.fid):
    print('f%02d %s %s' % (f.fid, f.model, [(s, len(bs)) for s, bs in f.route]))
json.dump([{'fid': f.fid, 'model': f.model, 'route': [(s, list(bs)) for s, bs in f.route]}
           for f in fl], open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples', 'v25b_routes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)