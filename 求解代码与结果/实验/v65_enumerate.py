# -*- coding: utf-8 -*-
"""v65：全单步动作枚举消融（完工均衡验证）+ 能耗帕累托搜索。
从 6990.1 出发枚举全部可行迁移/换型，统计完工改善/恶化的分布；记录能耗<75.22 且完工恶化<200s 的点。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '实验'))
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v61_gatenh_greedy.json'), encoding='utf-8'))
base = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m0, _, _, _ = eval_full(data, base)
MK0, EN0 = m0['makespan'], m0['energy']
print(f'基线: mk={MK0:.1f} en={EN0:.2f}')

def try_cand(fls, cand):
    from ppo23_env import apply_cand
    nf = apply_cand(fls, cand)
    if nf is None: return None
    m, s, v, nc = eval_full(data, nf)
    if m is None or v > 0 or nc > 0 or not m['hard_ok']: return None
    return m['makespan'], m['energy'], nf

# 单步枚举（同区迁移 + 换型）
from ppo23_env import build_candidates
impr = []
worse = []
par = []
for cand in build_candidates(base):
    r = try_cand(base, cand)
    if r is None: continue
    mk, en, nf = r
    if mk < MK0 - 0.5:
        impr.append((mk, en, cand))
    elif mk < MK0 + 200 and en < EN0 - 0.05:
        par.append((mk, en, cand))
    worse.append((mk, en))
print(f'单步: 可行 {len(worse)} 个; 完工改善 {len(impr)}; 完工+<200s且能耗降 {len(par)}; 完工恶化分布 {len(worse)}')
if impr:
    for x in sorted(impr)[:5]: print('  改善:', round(x[0],1), round(x[1],2), x[2])
if par:
    for x in sorted(par, key=lambda t: (-(EN0-t[1]), t[0]))[:5]: print('  帕累托候选:', round(x[0],1), round(x[1],2), x[2])
else:
    print('  无加工完+<200s 的能耗降点 → 帕累托多需要 2 步组合')
# 分布统计
if worse:
    ws = sorted(w[0] for w in worse)
    print(f'  完工分布: min={ws[0]:.1f} p25={ws[len(ws)//4]:.1f} med={ws[len(ws)//2]:.1f} max={ws[-1]:.1f}')
    es = sorted(w[1] for w in worse)
    print(f'  能耗分布: min={es[0]:.2f} max={es[-1]:.2f}')
# 2步组合：先做能耗降最多/完工恶化最小的 20 个单步，再对每个做第2步拉回
cands2 = sorted([(mk, en, cand) for mk, en, cand in worse + [(MK0, EN0, None)]], key=lambda t: (-(EN0 - t[1]), t[0]))[:20]
print(f'--- 2步组合：前 {len(cands2)} 个能耗降点做第2步拉回 ---')
found = []
for mk, en, cand in cands2:
    nf1 = base
    if cand is not None:
        from ppo23_env import apply_cand
        nf1 = apply_cand(base, cand)
        if nf1 is None: continue
    for cand2 in build_candidates(nf1):
        r2 = try_cand(nf1, cand2)
        if r2 is None: continue
        mk2, en2, _ = r2
        if mk2 <= MK0 + 30 and en2 < EN0 - 0.02:
            found.append((mk2, en2, cand, cand2))
if found:
    for x in sorted(found, key=lambda t: (-(EN0 - t[1]), t[0]))[:8]:
        print('  2步帕累托:', round(x[0],1), round(x[1],2), x[2], '→', x[3])
else:
    print('  2步组合也无完工+<30s 的能耗降点（完工均衡强）')
