# -*- coding: utf-8 -*-
"""v65b：2 步组合搜索——从 6990.1 找完工≤6990.1+30s 且能耗<75.12 的双步路径。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from ppo23_env import build_candidates, apply_cand
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v61_gatenh_greedy.json'), encoding='utf-8'))
base = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m0, _, _, _ = eval_full(data, base)
MK0, EN0 = m0['makespan'], m0['energy']
print(f'基线: {MK0:.1f}/{EN0:.2f}')

def evalf(fls):
    m, s, v, nc = eval_full(data, fls)
    if m is None or v > 0 or nc > 0 or not m['hard_ok']: return None
    return m['makespan'], m['energy']

# 第1步：全部可行单步及其结果解
step1 = []
for cand in build_candidates(base):
    nf = apply_cand(base, cand)
    if nf is None: continue
    r = evalf(nf)
    if r is None: continue
    step1.append((r[0], r[1], cand, nf))
# 2步：对第1步后完工 < 7250（不太恶化）的每个解再枚举全单步
found = []
for mk1, en1, c1, nf1 in step1:
    if mk1 > 7250: continue
    for c2 in build_candidates(nf1):
        nf2 = apply_cand(nf1, c2)
        if nf2 is None: continue
        r2 = evalf(nf2)
        if r2 is None: continue
        if r2[0] <= MK0 + 30 and r2[1] < EN0 - 0.02:
            found.append((r2[0], r2[1], c1, c2, step1, nf2))
print(f'第1步可行 {len(step1)}; 2步完工+<=30s且能耗降: {len(found)}')
for f_ in sorted(found, key=lambda t: (-(EN0 - t[1]), t[0]))[:10]:
    print(f'  2步: mk={f_[0]:.1f} en={f_[1]:.2f} | {f_[2]} -> {f_[3]}')
# 若 found 非空，落盘最优
if found:
    best = min(found, key=lambda t: (-(EN0 - t[1]), t[0]))
    fls2 = best[5]
    json.dump({'best': {'makespan': best[0], 'energy': best[1]},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in fls2]},
              open(os.path.join(OUTD, 'p2v65_pareto.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('psaved p2v65_pareto.json')
