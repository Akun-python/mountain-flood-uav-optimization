# -*- coding: utf-8 -*-
"""v121-fix：24架冠军需中继采样点归属分布（用 build_missions 的 grp/n 聚合）。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
import p3_co2
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant
data = p3_co2.data
d = json.load(open('求解代码与结果/结果/进化_v25/v113_best.json', encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
sch, _ = dispatch_compliant(data, fls)
starts = {fid: s['start'] for fid, s in sch.items()}
sv = p3_co2.Solver()
m_base = sv.build_missions(starts)
cnt = {'W': 0, 'E': 0, 'N': 0}
for m in m_base:
    cnt[m['grp']] += m['n']
print('归属分布 W/E/N:', cnt, '总计:', sum(cnt.values()))
# 每区任务窗口（用于核对 E/N 重叠）
seg = {}
for m in m_base: seg.setdefault(m['grp'], []).append((m['t0'], m['t1']))
for g in 'WEN':
    lo = min(a for a, b in seg.get(g, [])); hi = max(b for a, b in seg.get(g, []))
    print('%s: [%d, %d]' % (g, lo, hi))
