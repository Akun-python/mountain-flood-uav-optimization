# -*- coding: utf-8 -*-
"""v110b：C池组合扫描 v2——按箱拆分构造（S007/S008→B 2趟、S002/S005→C），6组合全验。"""
import sys, os, json, time
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
base = {f['fid']: Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']}
def zboxes(z):
    return [b for f in base.values() for zz, bs in f.route if zz == z for b in bs]
def evalv(fls, tag):
    sch, _ = dispatch_compliant(data, fls)
    mm, s, vv, nn = eval_full(data, fls)
    vb = cb(data, sch, fls)
    ok = mm is not None and vv == 0 and nn == 0 and mm['hard_ok'] and len(vb) == 0
    pools = {}
    for f in fls:
        pools.setdefault(f.model, []).append(sch[f.fid]['return'])
    pl = {m: round(max(v)) for m, v in pools.items()}
    print('%s: %d架 mk=%s en=%s OK=%s 池%s' % (tag, len(fls),
        '%.1f' % mm['makespan'] if mm else '-', '%.2f' % mm['energy'] if mm else '-', ok, pl), flush=True)
    return (mm['makespan'], mm['energy']) if mm and ok else None
def split(B, n1, n2):
    return B[:n1], B[n1:n1+n2] if n2 else None
def mk(keep_fids, new_fls):
    return [base[f] for f in keep_fids] + new_fls
fid = 200
C_S001_1 = [b for f in base.values() if f.fid == 1 for z, bs in f.route for b in bs]
C_S001_2 = [b for f in base.values() if f.fid == 2 for z, bs in f.route for b in bs]
C_S003 = zboxes('S003'); C_S004 = zboxes('S004')
S002 = zboxes('S002'); S005 = zboxes('S005')
S007 = zboxes('S007'); S008 = zboxes('S008')
W = lambda z: sum(data.boxes[b]['mass'] for b in z)
print('重量: S002=%.0f S005=%.0f S007=%.0f S008=%.0f S003=%.0f S004=%.0f' % (W(S002),W(S005),W(S007),W(S008),W(C_S003),W(C_S004)), flush=True)
def try_split(z, model):
    B = zboxes(z); out = []
    # 贪心: 容量内组合 2 趟
    n = len(B)
    for k1 in range(1, n):
        c1, c2 = B[:k1], B[k1:]
        if W(c1) <= 30.05 and W(c2) <= 30.05:
            nf1 = Flight(fid, [(z, list(c1))], model, data); fid_g = fid + 1
            nf2 = Flight(fid_g, [(z, list(c2))], model, data)
            if nf1.is_feasible() and nf2.is_feasible():
                out.append((c1, c2, nf1, nf2, fid + 1))
    return out
res = {}
# C1 基线
base_fls = [base[k] for k in sorted(base)]
r0 = evalv(base_fls, 'C1基线')
res['C1'] = r0
# 拆分可行性
s8b = try_split('S008', 'B'); s7b = try_split('S007', 'B')
print('S008→B2趟候选:%d S007→B2趟候选:%d' % (len(s8b), len(s7b)), flush=True)
for i, (c1, c2, nf1, nf2, fid2) in enumerate(s8b[:3]):
    print('  S008拆B: %d+%d箱 %.0f+%.0fkg dur=%.0f/%.0f' % (len(c1), len(c2), W(c1), W(c2), nf1.duration(), nf2.duration()), flush=True)
