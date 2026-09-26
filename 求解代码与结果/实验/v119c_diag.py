# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from core import Data
from p2_solve import Flight
from dqn23_enhanced import OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'v113_best.json'), encoding='utf-8'))
flights = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d]
print('多区趟:', [(f.fid, f.model, [s for s,_ in f.route]) for f in flights if len(set(s for s,_ in f.route))>1])
print('单区趟:', [(f.fid, f.model, [s for s,_ in f.route][0]) for f in flights if len(set(s for s,_ in f.route))==1])
