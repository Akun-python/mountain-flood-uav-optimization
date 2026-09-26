# -*- coding: utf-8 -*-
"""v110：C池组合系统扫描——C池区集合候选 × S007/S008拆B × S002/S005移C，全部严格口径验证。
记录每版完工/能耗/hard，找 <6571.4 或 <69.77。"""
import sys, os, json, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
base = {f['fid']: Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']}
def evalv(fls, tag):
    sch, _ = dispatch_compliant(data, fls)
    mm, s, vv, nn = eval_full(data, fls)
    vb = cb(data, sch, fls)
    ok = mm is not None and vv == 0 and nn == 0 and mm['hard_ok'] and len(vb) == 0
    pools = {}
    for f in fls:
        pools.setdefault(f.model, []).append(sch[f.fid]['return'])
    pl = {m: round(max(v)) for m, v in pools.items()}
    r = (mm['makespan'], mm['energy'], len(fls), ok) if mm else (None, None, len(fls), False)
    print('%s: %d架 mk=%s en=%s hard=%s bat=%d 池%s' % (tag, len(fls), '%.1f'%r[0] if r[0] else '-', '%.2f'%r[1] if r[1] else '-', r[3], len(vb), pl), flush=True)
    return r
# 找关键趟
f01 = base[1]; f02 = base[2]; f05 = base[5]  # C S001×2 + ?
cz = {}
for fid, f in base.items():
    for z, bs in f.route:
        if f.model == 'C':
            cz.setdefault(z, []).append((fid, list(bs)))
print('C池区分布:', {z: [(i, b[:2]) for i, b in v] for z, v in cz.items()}, flush=True)
s002 = [b for fid, b in cz.get('S002', [])]
s005 = [b for fid, b in cz.get('S005', [])]
s007 = [b for fid, b in cz.get('S007', [])]
s008 = [b for fid, b in cz.get('S008', [])]
print('S002箱数%d S005箱数%d S007箱数%d S008箱数%d' % (len(s002), len(s005), len(s007), len(s008)), flush=True)
