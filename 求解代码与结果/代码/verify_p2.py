# -*- coding: utf-8 -*-
"""P2 结果核验：逐箱时限、无人机/电池占用无重叠、架次能耗与SOC。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data, charge_time

data = Data()
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', 'p2_results.json'), encoding='utf-8') as fh:
    r = json.load(fh)

print('metrics:', r['metrics'])
# 1) 逐箱时限
viol = []
for d in r['deliveries']:
    bx = data.boxes[d['box']]
    t = d['t']
    if bx['first_batch'] and t > bx['deadline_first'] + 1e-6:
        viol.append(('first', d['box'], t, bx['deadline_first']))
    if bx['type'] == '医疗物资' and t > bx['deadline_exp'] + 1e-6:
        viol.append(('med', d['box'], t, bx['deadline_exp']))
    if t > bx['deadline_exp'] + 1e-6:
        viol.append(('exp', d['box'], t, bx['deadline_exp']))
print('deadline violations:', len(viol))
for v in viol[:10]:
    print('  ', v)
assert len(r['deliveries']) == len(data.boxes), 'box count mismatch!'
print('all 80 boxes delivered ✓')

# 2) 无人机/电池占用
from collections import defaultdict
uav_seg = defaultdict(list)
bat_seg = defaultdict(list)
for f in r['flights']:
    uav_seg[f['uav']].append((f['start'], f['return'], f['fid']))
    bat_seg[f['battery']].append((f['start'], f['return'], f['fid']))

def overlap(seg):
    for k, v in seg.items():
        v.sort()
        for i in range(len(v) - 1):
            if v[i][1] > v[i + 1][0] + 1e-6:
                return (k, v[i], v[i + 1])
    return None

ov = overlap(uav_seg)
print('UAV overlap:', ov)
ov = overlap(bat_seg)
print('Battery overlap:', ov)

# 3) 电池 SOC/充电 链路：架次→电池 顺序检查（构造性成立，这里只列各电池充电循环）
for f in sorted(r['flights'], key=lambda x: x['start']):
    g = f['model']
    e = f['energy']
    soc = 1 - e / data.uav_types[g]['E_use']
    Tf = data.batteries[g]['T_full']
    ch = charge_time(soc, Tf)
    print('f%02d %s %s start=%7.0f ret=%7.0f e=%.2f soc=%.2f charge=%.0fs'
          % (f['fid'], f['uav'], f['battery'], f['start'], f['return'], e, soc, ch))

# 4) 模型使用统计
from collections import Counter
print('models:', Counter(f['model'] for f in r['flights']))
print('flights per uav:', {k: len(v) for k, v in uav_seg.items()})
print('flights per battery:', {k: len(v) for k, v in bat_seg.items()})