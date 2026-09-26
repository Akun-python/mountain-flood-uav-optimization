# -*- coding: utf-8 -*-
"""v118-fix：24架方案时限核对。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
data = Data()
def stats(path, is_sol):
    dd = json.load(open(path, encoding='utf-8'))
    sol = dd['solution'] if is_sol else dd
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in sol]
    sch, _ = dispatch_compliant(data, fls)
    tmin = 1e9; tmax = 0; late = []; n3600 = 0
    allt = []
    for f in fls:
        for sid, b, t in f.delivery_times(sch[f.fid]['start']):
            df = data.boxes[b].get('deadline_first')
            de = data.boxes[b].get('deadline_exp', 10800)
            dl = df if df is not None else de
            tmin = min(tmin, t); tmax = max(tmax, t); allt.append(t)
            if df is not None and df <= 3600: n3600 += 1
            if t > dl + 0.5: late.append((b, round(t), dl))
    e3 = sum(1 for t in allt if t <= 3600)
    return fls, len(late), tmin, tmax, n3600, e3
fls, late, tmin, tmax, n3600, e3 = stats('求解代码与结果/结果/进化_v25/v113_best.json', False)
f2, l2, t2, t2m, n2, e32 = stats('求解代码与结果/结果/进化_v25/p2v89_champion25.json', True)
print('24架: %d趟 迟送%d 首投=%.0f 末投=%.0f 3600前%d/80 | 25架: 迟送%d 首投=%.0f 末投=%.0f 3600前%d/80' % (
    len(fls), late, tmin, tmax, e3, l2, t2, t2m, e32), flush=True)
