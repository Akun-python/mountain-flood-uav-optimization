# -*- coding: utf-8 -*-
"""v110d：多趟拆A——S008→3趟A、S003→4趟A；C池5/4趟完整方案调度。"""
import sys, os, json, itertools, time
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
def W(B): return sum(data.boxes[b]['mass'] for b in B)
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
def mkA(zz, parts):
    out = []
    for i, c in enumerate(parts):
        nf = Flight(500 + i, [(zz, list(c))], 'A', data)
        if not nf.is_feasible(): return None
        out.append(nf)
    return out
def chkA(zz, k):
    B = zboxes(zz); out = []
    for parts in itertools.combinations(range(len(B)), k - 1):
        idx = list(parts) + [len(B)]
        prev = 0; ps = []
        ok = True
        for i in idx:
            c = B[prev:i]; prev = i
            if not c: ok = False; break
            if W(c) > 25.05: ok = False; break
            ps.append(c)
        if not ok or len(ps) != k: continue
        nfs = mkA(zz, ps)
        if nfs:
            out.append((ps, nfs))
    return out
for zz, k in (('S008', 3), ('S003', 4), ('S005', 3), ('S004', 3)):
    r = chkA(zz, k)
    print('%s 拆A%d趟: %d 个可行拆法' % (zz, k, len(r)), flush=True)
    if r:
        ps, nfs = r[0]
        print('   例: %s dur=%s' % ([round(W(c),1) for c in ps], [round(f.duration()) for f in nfs]), flush=True)
