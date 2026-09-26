import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
data = Data()
d = json.load(open('求解代码与结果/结果/进化_v25/p2v61_gatv67c_greedy.json', encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
pt = {'A':0.0,'B':0.0,'C':0.0}
for f in fls: pt[f.model] += f.duration()
print('池T/台:', {g: round(pt[g]/{'A':4,'B':2,'C':2}[g],0) for g in 'ABC'}, '趟数', len(fls))
print('机型分布:', {g: sum(1 for f in fls if f.model==g) for g in 'ABC'})
# 能耗分解
en = {'A':0.0,'B':0.0,'C':0.0}
for f in fls: en[f.model] += f.energy()
print('能耗/池:', {g: round(en[g],2) for g in 'ABC'})
