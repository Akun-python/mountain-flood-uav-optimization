# -*- coding: utf-8 -*-
import sys, os, json
from collections import Counter
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from core import Data
from p2_solve import Flight
from dqn23_enhanced import OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'v113_best.json'), encoding='utf-8'))
flights = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
MULTI = {37: 'E', 38: 'W', 39: 'W'}
def assign(gname):
    letter = gname.split('(')[1][0]
    out = []
    for f in flights:
        zones = [s for s, _ in f.route]
        if len(set(zones)) > 1:
            own = MULTI.get(f.fid)
            if own == letter: out.append(f)
        else:
            # 按区归属表
            z = zones[0]
            zm = {'S001':'W','S002':'W','S003':'W','S005':'W','S007':'W','S008':'W','S009':'W','S011':'W','S015':'W',
                  'S004':'N','S006':'E','S010':'E','S012':'E','S013':'E','S014':'E'}
            if zm.get(z) == letter: out.append(f)
    return out
K3 = ['G1(W)','G2(E)','G3(N)']
g3 = {}
for g in K3: g3[g] = assign(g)
all3 = set()
for g, fs in g3.items():
    bs = set()
    for f in fs: bs |= set(f.box_ids)
    g3[g] = (len(fs), len(bs))
    all3 |= set().union(*[set(f.box_ids) for f in fs])
print('K3 各组(趟,箱):', g3, '并集箱:', len(all3), '(应80)')
dup = [b for b, c in Counter(b for f in sum([fs for fs in g3.values()], []) for b in f.box_ids).items() if c > 1]
print('K3 跨组重复箱:', dup[:5])
