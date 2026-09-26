# -*- coding: utf-8 -*-
"""v109g：B池链条分析——f31(S005)尾趟削除可能性：1箱并入已有A/B趟(不新增架次)。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v89_champion25.json', encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
sch, _ = dispatch_compliant(data, fls)
bs_ = [f for f in fls if f.model == 'B']
print('B池 %d 趟:' % len(bs_))
for f in sorted(bs_, key=lambda f: sch[f.fid]['start']):
    print('  f%02d %s start=%.0f ret=%.0f' % (f.fid, [(z, len(bs)) for z, bs in f.route], sch[f.fid]['start'], sch[f.fid]['return']))
# S005 全部箱与所在趟
print('S005 箱分布:')
for f in fls:
    for z, bs in f.route:
        if z == 'S005':
            print('  f%02d %s 箱:%s 重%.0f' % (f.fid, f.model, bs, sum(data.boxes[b]['mass'] for b in bs)))
# A池 S005 附近：找所有 A 趟（含近区、有容量余量）
print('A 池容量余量（箱重 vs 25）:')
for f in sorted([x for x in fls if x.model == 'A'], key=lambda x: sch[x.fid]['start']):
    w = sum(data.boxes[b]['mass'] for z, bs in f.route for b in bs)
    print('  f%02d %s w=%.0f ret=%.0f' % (f.fid, [(z, len(bs)) for z, bs in f.route], w, sch[f.fid]['return']))
