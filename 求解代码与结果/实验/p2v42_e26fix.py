# -*- coding: utf-8 -*-
"""v42-κ：修复 p2_energy26_solution（26架/6927.1/70.09）的区一致违规。
违规 5 箱（旧口径捎带）：挪回所属区趟并满足容量，26 趟不增：
- f31 收 S013-MED-01(f3 出)、S013-WAT-01(f24 出)，并让出 S002-FOD-01 给 f2
- f8  收 S008-MED-01(f6 出)
- f12 收 S010-MED-01(f14 出)，变 S012+S010 两区
- f14 收 S012-MED-01(f18 出)，变 S014+S012 两区
输出 结果/进化_v42/e26_fixed.json + 复核 8 项。"""
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
fls = {f['fid']: Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']],
                        f['model'], data) for f in d['flights']}

def route_of(fid):
    return {s: list(bs) for s, bs in fls[fid].route}

def set_route(fid, route):
    """route: dict {区: [箱]} -> 单一或多区 Flight（保持机型，超载报错）。"""
    f = fls[fid]
    r = [(s, bs) for s, bs in route.items()]
    model = f.model
    mass = sum(data.boxes[b]['mass'] for _, bs in r for b in bs)
    Q = data.uav_types[model]['Q']
    if mass > Q + 1e-9:
        # 自动升格（B->C）
        for mm in ('C',):
            if mass <= data.uav_types[mm]['Q']:
                model = mm; break
    nf = Flight(fid, r, model, data)
    if not nf.is_feasible():
        raise ValueError('f%d 不可行 %s %.1fkg %s' % (fid, model, mass, r))
    fls[fid] = nf

# ---- 执行修复 ----
# 1) f31: 让出 S002-FOD-01，收 S013-MED-01（f3 出）与 S013-WAT-01（f24 出）
r31 = route_of(31)
s002_fod = r31['S013'].pop(r31['S013'].index('S002-FOD-01'))
r3 = route_of(3)
s013_med = r3['S003'].pop(r3['S003'].index('S013-MED-01'))
r24 = route_of(24)
s013_wat = r24['S006'].pop(r24['S006'].index('S013-WAT-01'))
r31['S013'] += [s013_med, s013_wat]
set_route(31, r31)
set_route(3, r3)
set_route(24, r24)
# 2) f2 收 S002-FOD-01
r2 = route_of(2)
r2['S002'] = [s002_fod] + r2.get('S002', [])
set_route(2, r2)
# 3) f8 收 S008-MED-01（f6 出）
r6 = route_of(6)
s008_med = r6['S006'].pop(r6['S006'].index('S008-MED-01'))
r8 = route_of(8)
r8['S008'] += [s008_med]
set_route(8, r8)
set_route(6, r6)
# 4) f12 收 S010-MED-01（f14 出），变 S012+S010
r14 = route_of(14)
s010_med = r14['S014'].pop(r14['S014'].index('S010-MED-01'))
r12 = route_of(12)
r12.setdefault('S010', []).append(s010_med)   # S010 段
set_route(12, r12)
set_route(14, r14)
# 5) f14 收 S012-MED-01（f18 出），变 S014+S012
r18 = route_of(18)
s012_med = r18['S002'].pop(r18['S002'].index('S012-MED-01'))
r14b = route_of(14)
r14b.setdefault('S012', []).append(s012_med)
set_route(14, r14b)
set_route(18, r18)

flist = [fls[fid] for fid in sorted(fls)]
sch, _ = dispatch(data, flist)
if sch is None:
    print('dispatch 不可行!'); sys.exit(1)
met = evaluate(data, flist, sch)
print('修复后  fl=%d mk=%.1f e=%.3f hard=%s tardy=%.2f bad=%d'
      % (met['flights'], met['makespan'], met['energy'], met['hard_ok'],
         met['tardy_w'], len(met['bad_zones'])))
if met['bad_zones']:
    print('bad:', met['bad_zones'])
out = {'solver': 'v42-e26fix', 'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                                            for k, v in met.items() if k != 'box_time'},
       'flights': [], 'deliveries': []}
for f in flist:
    s = sch[f.fid]
    out['flights'].append({'fid': f.fid, 'uav': s['uav'], 'model': f.model,
                           'battery': s['battery'], 'start': round(s['start'], 1),
                           'return': round(s['return'], 1),
                           'route': [(sid, list(bs)) for sid, bs in f.route],
                           'energy': round(f.energy(), 4), 'nbox': f.nbox,
                           'mass': round(f.total_mass, 2)})
    for sid, bid, t in s['deliveries']:
        out['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
json.dump(out, open(os.path.join(EVO, 'e26_fixed.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved e26_fixed.json')