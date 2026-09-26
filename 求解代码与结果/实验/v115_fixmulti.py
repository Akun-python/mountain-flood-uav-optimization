# -*- coding: utf-8 -*-
"""v115：多区趟冲突修复——S006箱统一并入f39(C S006|S007)，f37拆为A单区S014；重调度验证。"""
import sys, os, json, time, math
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/v113_best.json', encoding='utf-8'))
base = {f['fid']: Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d}
def W(B): return sum(data.boxes[b]['mass'] for b in B)
def angle_key(z, ref):
    a = data.areas[z]
    return math.atan2(a['lat'] - ref[1], (a['lon'] - ref[0]) * math.cos(ref[1] * math.pi / 180))
def eval_full_r(fls):
    sch, _ = dispatch_compliant(data, fls)
    mm, s, vv, nn = eval_full(data, fls)
    vb = cb(data, sch, fls)
    if mm is None or vv > 0 or nn > 0 or not mm['hard_ok'] or len(vb) > 0: return None
    return mm['makespan'], mm['energy']
f37 = base[37]; f39 = base[39]
print('f37:', [(z, len(bs)) for z, bs in f37.route], f37.model, 'f39:', [(z, len(bs)) for z, bs in f39.route], f39.model, flush=True)
s006_37 = [b for z, bs in f37.route if z == 'S006' for b in bs]
s014_37 = [b for z, bs in f37.route if z == 'S014' for b in bs]
print('f37 S006箱:%d(%.0fkg) S014箱:%d(%.0fkg) | f39 S006箱:%d' % (
    len(s006_37), W(s006_37), len(s014_37), W(s014_37),
    len([b for z, bs in f39.route if z == 'S006' for b in bs])), flush=True)
o = data.centers['O01']; ref = (o['lon'], o['lat'])
# 新 f37': A 单区 S014；新 f39': C S006|S007（S006 箱=原f39 S006 + f37的S006）
f39_s006 = [b for z, bs in f39.route if z == 'S006' for b in bs]
f39_s007 = [b for z, bs in f39.route if z == 'S007' for b in bs]
all_s006 = f39_s006 + s006_37
nf37 = Flight(150, [('S014', list(s014_37))], 'A', data)
nf39 = Flight(151, [('S006', list(all_s006)), ('S007', list(f39_s007))], 'C', data)
print('新f37 fea=%s dur=%.0f(旧%.0f) | 新f39 fea=%s dur=%.0f(旧%.0f)' % (
    nf37.is_feasible(), nf37.duration(), f37.duration(), nf39.is_feasible(), nf39.duration(), f39.duration()), flush=True)
if nf37.is_feasible() and nf39.is_feasible():
    new = [base[f] for f in base if f not in (37, 39)] + [nf37, nf39]
    r = eval_full_r(sorted(new, key=lambda x: x.fid))
    print('修复后: %d架 mk=%.1f en=%.2f (vs 6571.4/69.13)' % (len(new), r[0], r[1]), flush=True)
    if r:
        json.dump([{'fid': f.fid, 'model': f.model, 'route': [[z, list(bs)] for z, bs in f.route]} for f in sorted(new, key=lambda x: x.fid)],
                  open('求解代码与结果/结果/进化_v25/v115_best.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
