# -*- coding: utf-8 -*-
"""v110c-fix：S008/S003 拆 A 型可行性 + C池5趟方案调度验证。"""
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
def splitA2(zz):
    B = zboxes(zz); out = []
    for c1 in itertools.combinations(B, len(B)//2):
        c1 = list(c1); c2 = [b for b in B if b not in c1]
        if W(c1) <= 25.05 and W(c2) <= 25.05:
            n1 = Flight(300, [(zz, c1)], 'A', data); n2 = Flight(301, [(zz, c2)], 'A', data)
            if n1.is_feasible() and n2.is_feasible():
                out.append((c1, c2, n1, n2))
    return out
S008 = zboxes('S008'); S003 = zboxes('S003')
print('S008=%.0fkg 分A2趟候选:%d | S003=%.0fkg 分A2趟候选:%d' % (W(S008), len(splitA2('S008')), W(S003), len(splitA2('S003'))), flush=True)
for zz in ('S008', 'S003'):
    B = zboxes(zz)
    for k1 in range(1, len(B)):
        for c1 in itertools.combinations(B, k1):
            c1 = list(c1); c2 = [b for b in B if b not in c1]
            if not c2 or W(c1) > 25.05 or W(c2) > 25.05: continue
            n1 = Flight(400, [(zz, c1)], 'A', data); n2 = Flight(401, [(zz, c2)], 'A', data)
            if n1.is_feasible() and n2.is_feasible():
                print('  %s 拆A2趟: %d+%d箱 %.0f+%.0fkg dur=%.0f/%.0f' % (zz, len(c1), len(c2), W(c1), W(c2), n1.duration(), n2.duration()), flush=True)
                break
