# -*- coding: utf-8 -*-
"""计算 27 架冠军的最紧时限裕度（逐箱交付 vs 时限）。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v75_champion.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m, sch, v, nc = eval_full(data, fls)
# 收集逐箱交付时刻与时限裕度
rows = []
for fid, s in sch.items():
    for sid, bid, t in s['deliveries']:
        bx = data.boxes[bid]
        dl_first = bx['deadline_first']; dl_exp = bx['deadline_exp']
        margin = min(dl_first, dl_exp) - t if not (dl_first == float('inf') and dl_exp == float('inf')) else None
        if margin is not None:
            rows.append((margin, bid, t, dl_first, dl_exp, fid, sid))
rows.sort(key=lambda x: x[0])
print('最紧裕度 Top5:')
for r in rows[:5]:
    print('  %6.0fs 裕度 | %s 交付%6.0f 首批时限%s 期望%s 趟%s 区%s' % (r[0], r[1], r[2], r[3], r[4], r[5], r[6]))
first = [r for r in rows if r[3] < 1e15]
print('首飞批最紧: %s 裕度%.0fs 交付%.0f 时限%.0f' % (first[0][1], first[0][0], first[0][2], first[0][3]) if first else '无首飞批')

