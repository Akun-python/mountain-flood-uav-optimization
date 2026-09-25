# -*- coding: utf-8 -*-
"""进化 v24：S011-FOD 单箱转移 f5 -> f11 的端到端验证（P2 口径 + 联合口径）。

动机（第一性原理）：
- f5(C, 末班 4926→6960) 同时服务 S005、S004-FOD、S011-FOD；S011 走廊需中继段
  把 W 窗口尾段拖到 6502 s，且 f5 返场 6960 定义了运输完工。
- f11(A) 5458→6673 已飞 S011（MED+WAT，17 kg），加 S011-FOD(8 kg) 恰 25 kg = A 型上限。
- 转移后 f5 少飞 S011 段 → C 链完工可能提前；f11 的 S011 需中继段结束时刻
  可能早于 6502（f11 在 6502 时已进入返航直连区）→ W 窗口可能缩短。
- v20 曾把该转移与另外 3 处转移组合尝试并失败（W 窗口扩至 7102，因 S005 箱
  并入 f5 拉长），单独做此一项是干净实验。
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from p2_solve import Flight, dispatch, evaluate
import p3_co2

data = p3_co2.data

def rebuild(f, route):
    nf = Flight(f.fid, route, f.model, data)
    nf.start0 = getattr(f, 'start0', p3_co2.sv_base.get(f.fid, 0.0))
    return nf

print('=== 基线（v23 冠军，直接用 p3_co2.Solver）===')
sv = p3_co2.Solver()
res0 = sv.finalize({4: 3300.0, 22: 1000.0})
print('baseline joint makespan=%.2f energy=%.2f mpen=%s' %
      (res0['met']['makespan'], res0['met']['energy'], res0['mpen']))
p3_co2.sv_base = dict(sv.base)

print()
print('=== 实验：S011-FOD f5 -> f11 ===')
f5 = next(f for f in sv.flights if f.fid == 5)
f11 = next(f for f in sv.flights if f.fid == 11)
print('f5 route:', f5.route, 'mass=', f5.total_mass)
print('f11 route:', f11.route, 'mass=', f11.total_mass)

# 新路线
r5 = []
for s, bs in f5.route:
    if s == 'S011':
        nb = [b for b in bs if b != 'S011-FOD-01']   # S004-FOD 留在 f5
        if nb:
            r5.append((s, nb))
    else:
        r5.append((s, list(bs)))
r11 = [('S011', list(f11.box_ids) + ['S011-FOD-01'])]
print('new f5 route:', r5)
print('new f11 route:', r11)

f5n = rebuild(f5, r5)
f11n = rebuild(f11, r11)
print('f5n feasible:', f5n.is_feasible(), 'mass=', f5n.total_mass, 'vol=', round(f5n.total_vol, 4),
      'E=', round(f5n.energy(), 3), 'dur=', round(f5n.duration(), 1))
print('f11n feasible:', f11n.is_feasible(), 'mass=', f11n.total_mass, 'vol=', round(f11n.total_vol, 4),
      'E=', round(f11n.energy(), 3), 'dur=', round(f11n.duration(), 1))

# 替换进 Solver，重新预计算（轨迹采样依赖载荷/机型）
for i, f in enumerate(sv.flights):
    if f.fid in (5, 11):
        sv.flights[i] = f5n if f.fid == 5 else f11n
for f in sv.flights:
    f.start0 = sv.base[f.fid]
sv.precompute()

print()
print('=== P2 口径（无释放派单）===')
sch, _ = dispatch(data, sv.flights)
met = evaluate(data, sv.flights, sch)
print('P2: hard_ok=%s tardy_w=%.2f makespan=%.2f energy=%.2f flights=%d'
      % (met['hard_ok'], met['tardy_w'], met['makespan'], met['energy'], met['flights']))

print()
print('=== 联合口径（先试 v23 偏移 {4:3300, 22:1000}）===')
res = sv.finalize({4: 3300.0, 22: 1000.0})
print('joint: makespan=%.2f energy=%.2f mpen=%s' %
      (res['met']['makespan'], res['met']['energy'], res['mpen']))

print()
print('=== 联合口径（零偏移）===')
resz = sv.finalize({})
print('joint-zero: makespan=%.2f energy=%.2f mpen=%s' %
      (resz['met']['makespan'], resz['met']['energy'], resz['mpen']))

print()
print('=== 联合口径（多起点 SA 搜索最小偏移）===')
best, obj = None, 1e18
for start in [dict(sv.base and {}), {4: 3300.0, 22: 1000.0}, {4: 3600.0, 22: 1200.0}]:
    import copy
    cur = {k: start.get(k, 0.0) for k in sv.base}
    cur_obj, met0 = sv.evaluate(cur)
    if cur_obj < obj:
        best, obj = copy.deepcopy(cur), cur_obj
b, o = sv.sa(iters=1500, seed=7)
print('SA best obj=%.1f offsets=%s' % (o, {k: round(v) for k, v in b.items()}))
resb = sv.finalize(b)
print('joint-SA: makespan=%.2f energy=%.2f mpen=%s' %
      (resb['met']['makespan'], resb['met']['energy'], resb['mpen']))

out = {}
for name, r in [('baseline', res0), ('v23offs', res), ('zero', resz), ('sa', resb)]:
    out[name] = {'makespan': round(r['met']['makespan'], 2),
                 'energy': round(r['met']['energy'], 3),
                 'mpen': r['mpen'], 'hard_ok': r['met']['hard_ok'],
                 'tardy': r['met']['tardy_w'], 'flights': r['met']['flights']}
print(json.dumps(out, ensure_ascii=False, indent=1))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '结果', '进化_v24',
                       'v24_s011_transfer.json'), 'w', encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print('saved v24_s011_transfer.json')