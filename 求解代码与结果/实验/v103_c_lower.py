# -*- coding: utf-8 -*-
"""v103：C池最后返场理论下界枚举——6趟×2台所有分配 × 充电间隙精确模拟，求理论最小最后返场。"""
import sys, os, itertools, math, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
cfl = [(f.duration(), f.energy()) for f in fls if f.model == 'C']
print('C趟(时长,能耗):', [(round(d2), round(e,2)) for d2, e in cfl])
T_FULL = 3000.0; E_USE = 8.0
def charge_time(frac):
    if frac <= 0: return 0.0
    t1 = 0.5 * frac * T_FULL
    if frac <= 0.7: return t1
    return t1 + 0.5 * (frac - 0.7) * T_FULL
# 枚举 6 趟分给 2 台的所有 2^6 分配（每台≥1趟），每台内部按起飞完成模拟
best = 1e18; best_alloc = None
for mask in range(64):
    A = [cfl[i] for i in range(6) if mask >> i & 1]
    B = [cfl[i] for i in range(6) if not (mask >> i & 1)]
    if not A or not B: continue
    def finish(chain):
        t = 0.0
        for dur, en in chain:
            if t < 0: pass
            ready = t
            # 若上一趟存在，需充电到满
            t = ready + dur
        return t
    # 台内顺序固定为输入顺序（fid序），两台并行
    # 实际两台独立链：每台 3 趟链接 = 趟间充电
    def chain_finish(chain):
        t = 0.0; prev_en = 0.0
        for i, (dur, en) in enumerate(chain):
            if i > 0:
                frac = max(0.0, prev_en / E_USE)
                t += charge_time(frac)   # 充满上一趟电池
            t += dur
            prev_en = en
        return t
    fa = chain_finish(A); fb = chain_finish(B)
    mk = max(fa, fb)
    if mk < best:
        best = mk; best_alloc = (A, B)
print('C池理论最小最后返场 = %.0fs (分配 %s vs %s)' % (best,
    [(round(d2), round(e,2)) for d2, e in best_alloc[0]], [(round(d2), round(e,2)) for d2, e in best_alloc[1]]))
print('=> 完工下界 >= %.0fs = %.1f min —— %s6000' % (best, best/60, '≥' if best >= 6000 else '<'))
print('25架冠军实际 C 池最后返场 6233s（排班非最优均衡，但已接近）')

