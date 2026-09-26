# -*- coding: utf-8 -*-
"""v68：能耗本地搜索追赶——从 6990.1/74.22 出发，允许完工+≤120s 的能耗下降链（beam3），找 74.1x。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from ppo23_env import build_candidates, apply_cand
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v61_gatv67smoke_greedy.json'), encoding='utf-8'))
base = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m0, _, _, _ = eval_full(data, base)
MK0, EN0 = m0['makespan'], m0['energy']
print(f'起点: {MK0:.1f}/{EN0:.2f} 趟{len(base)}')

def evalf(fls):
    m, s, v, nc = eval_full(data, fls)
    if m is None or v > 0 or nc > 0 or not m['hard_ok']: return None
    return m['makespan'], m['energy'], fls

# beam 搜索（允许完工+120s，目标能耗降）
beam = [(MK0, EN0, base)]
for rnd in range(25):
    nxt = []
    for mk, en, fls in beam[:3]:
        for cand in build_candidates(fls):
            nf = apply_cand(fls, cand)
            if nf is None: continue
            r = evalf(nf)
            if r is None: continue
            mk2, en2, _ = r
            if mk2 <= MK0 + 120 and en2 < en - 0.001:
                nxt.append((mk2, en2, nf))
    if not nxt:
        break
    nxt.sort(key=lambda t: (t[1], t[0]))  # 能耗优先
    beam = nxt[:3]
    print(f'r{rnd}: 能耗最佳 {beam[0][1]:.2f} @完工 {beam[0][0]:.1f} ({len(nxt)}条)')
best = min(beam, key=lambda t: (t[1], t[0]))
print(f'最终: 完工 {best[0]:.1f} 能耗 {best[1]:.2f} 趟{len(best[2])}')
json.dump({'best': {'makespan': best[0], 'energy': best[1]},
           'solution': [{'fid': f.fid, 'model': f.model,
                         'route': [(s2, list(bs)) for s2, bs in f.route]} for f in best[2]]},
          open(os.path.join(OUTD, 'p2v68_energy_best.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('psaved p2v68_energy_best.json')
