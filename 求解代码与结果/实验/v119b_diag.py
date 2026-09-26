# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from core import Data
from p2_solve import Flight
from dqn23_enhanced import OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'v113_best.json'), encoding='utf-8'))
flights = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
G1 = {'S001','S002','S003','S005','S007','S008','S009','S011','S015'}
G2 = {'S006','S010','S012','S013','S014'}
MULTI = {37:'E',38:'W',39:'W'}
got = set()
for f in flights:
    zones = [s for s,_ in f.route]
    if len(set(zones))>1:
        own = MULTI.get(f.fid)
        if own=='E': got |= set(f.box_ids)
    else:
        z = zones[0]
        if z in G1: got |= set(f.box_ids)
print('G1 got 箱数:', len(got))
# 分区的箱
by = {}
for b, bx in data.boxes.items():
    by.setdefault(bx['area'], []).append(b)
allb = set()
for z in G1: allb |= set(by[z])
for f in flights:
    if len(set(s for s,_ in f.route))>1 and MULTI.get(f.fid)=='W':
        allb |= set(f.box_ids)
miss = sorted(allb - got)
from collections import Counter
print('G1 missing:', len(miss), Counter(data.boxes[b]['area'] for b in miss))
for b in miss[:10]: print('  ', b, data.boxes[b]['area'], data.boxes[b]['mass'])
