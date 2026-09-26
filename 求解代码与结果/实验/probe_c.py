# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v61_gatenh_greedy.json', encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
print('=== C/B 趟区与箱 ===')
for f in sorted(fls, key=lambda x: x.fid):
    if f.model in 'CB':
        ms = [data.boxes[b]['mass'] for b in f.box_ids]
        print(f"  {f.fid} {f.model} 区{f.route[0][0]} 箱{len(f.box_ids)} 质量{ms} 总{sum(ms):.0f}kg 时长{f.duration():.0f}s")
heavy = [b for b in data.boxes if data.boxes[b]['mass'] > 30.0]
print('=== >30kg 箱:', len(heavy), '===')
for b in heavy: print(' ', b, data.boxes[b]['mass'], 'kg 区', b.split('-')[0])
mid = [b for b in data.boxes if 25.0 < data.boxes[b]['mass'] <= 30.0]
print('=== 25-30kg 箱:', len(mid), '===')
for b in mid: print(' ', b, data.boxes[b]['mass'], 'kg 区', b.split('-')[0])
