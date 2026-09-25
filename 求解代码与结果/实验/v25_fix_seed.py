# -*- coding: utf-8 -*-
"""v25 修复种子：把 v24 冠军的 14 个跨区箱全部归位到属区段（投递位置正确）。

归位规则：优先移入已有属区段架次（容量/能量可行）；无处可去者新增正确区段架次。
段序按 O 出发方位角排序。输出：零跨区 + 全部 is_feasible + 派单指标。
"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data
from p2_solve import Flight, dispatch, evaluate

data = Data()
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
p2 = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))

o = data.centers[data.OID]
def angle(sid):
    a = data.areas[sid]
    return math.atan2(a['lat'] - o['lat'], a['lon'] - o['lon'])

def rebuild(route_by_zone):
    """按方位角排序段序构造 route。"""
    return [(z, route_by_zone[z]) for z in sorted(route_by_zone, key=angle)]

# 现有架次：段区 -> 箱（先全摘跨区，再归位）
flights = {}
zones = {}
for f in p2['flights']:
    fz = {}
    for s, bs in f['route']:
        for b in bs:
            fz.setdefault(b.split('-')[0], []).append(b)  # 全部按属区重挂
    flights[f['fid']] = {'model': f['model'], 'zones': fz}

# ---- 归位决策：箱 -> 目标架次 ----
# 直接移到已有属区段架次的箱（保持 26 架结构）
place = {
    'S002-MED-01': 2,   # f02 的 S002 段
    'S010-MED-01': 14,  # f14 加 S010 段（路径真访问）
    'S008-MED-01': 8,   # f08 的 S008 段
    'S012-MED-01': 12,  # f12 的 S012 段
    'S002-FOD-01': 18,  # f18 的 S002 段
    'S002-FOD-02': 18,  # f18 的 S002 段
    'S010-FOD-01': 10,  # f10 的 S010 段
}
# 新架次：箱集合 -> (model, fid)
new_missions = [
    (['S004-HYG-01', 'S004-FOD-01'], 'B'),   # S004 区剩余 2 箱
    (['S008-FOD-01'], 'A'),                   # S008 区剩余 1 箱
    (['S012-FOD-01'], 'A'),                   # S012 区剩余 1 箱
    (['S013-MED-01', 'S013-WAT-01'], 'B'),    # S013 区剩余 2 箱
    (['S007-HYG-01'], 'A'),                   # S007 区剩余 1 箱
]
new_fid = max(flights) + 1

# 应用到现有架次
for b, tf in place.items():
    tz = b.split('-')[0]
    # 从所有架次摘除 b
    for fid in list(flights):
        zz = flights[fid]['zones']
        for z in list(zz):
            if b in zz[z]:
                zz[z].remove(b)
                if not zz[z]:
                    del zz[z]
    # 放入目标架次的属区段
    flights[tf]['zones'].setdefault(tz, []).append(b)

# 新架次
for boxes, model in new_missions:
    tz = boxes[0].split('-')[0]
    for b in boxes:
        for fid in list(flights):
            zz = flights[fid]['zones']
            for z in list(zz):
                if b in zz[z]:
                    zz[z].remove(b)
                    if not zz[z]:
                        del zz[z]
    flights[new_fid] = {'model': model, 'zones': {tz: boxes}}
    new_fid += 1

# 构造 Flight 并验证
fl = []
for fid, d in sorted(flights.items()):
    route = rebuild(d['zones'])
    f = Flight(fid, route, d['model'], data)
    fl.append(f)
    ok = f.is_feasible()
    if not ok:
        print('!! f%02d %s 不可行: route=%s mass=%.0f vol=%.3f e=%.2f'
              % (fid, d['model'], [(s, len(bs)) for s, bs in route], f.total_mass, f.total_vol, f.energy()))
n_flights = len(fl)
print('架次数: %d（原 26，新增 %d）' % (n_flights, n_flights - 26))

schedule, _ = dispatch(data, fl)
met = evaluate(data, fl, schedule)
print('evaluate: hard_ok=%s tardy=%.2f makespan=%.1f energy=%.2f flights=%d bad_zones=%d'
      % (met['hard_ok'], met['tardy_w'], met['makespan'], met['energy'], met['flights'], len(met['bad_zones'])))
if met['bad_zones']:
    print('  bad_zones:', met['bad_zones'][:8])

# 逐架输出新 route
print()
for f in sorted(fl, key=lambda x: x.fid):
    print('f%02d %s %s' % (f.fid, f.model, [(s, len(bs)) for s, bs in f.route]))
