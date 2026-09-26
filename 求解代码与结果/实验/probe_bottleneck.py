# -*- coding: utf-8 -*-
"""探查 6990.1 解的池/趟/箱结构：找换型与能耗优化机会。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
from p2_solve import Flight, Data
OUTD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '结果', '进化_v25')
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v61_gatenh_greedy.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
print('=== 池负载 ===')
pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}
for f in fls: pt[f.model] += f.duration()
for g in 'ABC':
    n = {'A': 4, 'B': 2, 'C': 2}[g]
    print(f'  {g}池: {sum(1 for f in fls if f.model==g)}趟 T/台={pt[g]/n:.0f}s 总时长={pt[g]:.0f}')
print('=== 各趟箱属性（质量>25 或体积>0.058 标记 ★不可A）===')
for f in sorted(fls, key=lambda x: x.fid):
    mxs = [(data.boxes[b]['mass'], data.boxes[b]['vol']) for b in f.box_ids]
    nA = sum(1 for m, v in mxs if m <= 25.0 and v <= 0.058)
    flag = '' if len(mxs) == nA else ' ★不可A'
    print(f"  {f.fid} {f.model} 趟{f.duration():.0f}s 箱{len(f.box_ids)} 质量{sum(m for m,_ in mxs):.1f}/{max(m for m,_ in mxs):.1f}kg 体积{sum(v for _,v in mxs):.3f} A可行{nA}/{len(mxs)}{flag}")
print('=== 箱质量分布（>25 必须B/C, >30 必须C）===')
for b in sorted(data.boxes, key=lambda b: -data.boxes[b]['mass'])[:12]:
    bb = data.boxes[b]
    print(f"  {b} {bb['mass']:.1f}kg {bb['vol']:.3f}m3 zone={b.split('-')[0]} exp={bb['deadline_exp']}")
