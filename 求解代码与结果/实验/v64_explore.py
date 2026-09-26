# -*- coding: utf-8 -*-
"""v64 定向探索（修正 fid 类型）：池间换型消融。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v61_gatenh_greedy.json'), encoding='utf-8'))
base = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
print('基线:', round(eval_full(data, base)[0]['makespan'],1), round(eval_full(data, base)[0]['energy'],2))

def apply(fls, fid, gm):
    out = []
    for f in fls:
        if str(f.fid) == str(fid):
            nf = Flight(f.fid, f.route, gm, data)
            if not nf.is_feasible():
                print(f'  {fid}→{gm} 不可行')
                return None
            out.append(nf)
        else:
            out.append(Flight(f.fid, f.route, f.model, data))
    return out

def mk(fls):
    m, s, v, nc = eval_full(data, fls)
    pt = {'A':0.0,'B':0.0,'C':0.0}
    for f in fls: pt[f.model] += f.duration()
    return (round(m['makespan'],1), round(m['energy'],2), v, nc, {g: round(pt[g]/{'A':4,'B':2,'C':2}[g],0) for g in 'ABC'})

print('--- E1: 趟4+6 B→A ---')
f1 = apply(base, 4, 'A'); f1 = apply(f1, 6, 'A')
if f1: print('  E1:', mk(f1))
print('--- E2: 趟23 C→B ---')
f2 = apply(base, 23, 'B')
if f2: print('  E2:', mk(f2))
print('--- E3: E1+E2 ---')
f3 = apply(base, 4, 'A'); f3 = apply(f3, 6, 'A'); f3 = apply(f3, 23, 'B')
if f3: print('  E3:', mk(f3))
print('--- E4: 趟23 C→A ---')
f4 = apply(base, 23, 'A')
if f4: print('  E4:', mk(f4))
print('--- E5: 趟3 B→A (体积0.063>0.058 预判失败) ---')
f5 = apply(base, 3, 'A')
if f5: print('  E5:', mk(f5))
print('--- E6: 趟12 B→A (质量25体积0.067 预判失败) ---')
f6 = apply(base, 12, 'A')
if f6: print('  E6:', mk(f6))
print('--- E7: 趟12 箱移给B(腾出) ---')
