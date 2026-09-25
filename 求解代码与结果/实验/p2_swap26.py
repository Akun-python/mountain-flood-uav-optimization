# -*- coding: utf-8 -*-
"""
v20b · 中继安全换型搜索（窗口包含性准则）
=========================================
理论依据（保证准确）：若候选解的每个需中继任务段都包含于官方窗口
（W ⊆ [1078,6802]、E ⊆ [1406,4074]、N ⊆ [5894,6446]），则官方偏移
对该候选仍可行 → 联合完工 ≤ 7259.81 s 且中继能耗 ≤ 3.417 kWh（官方
偏移是联合下界处的可行实现）。因此：**窗口包含性 = 端到端无损的充分条件**。

算子：单架次机型换型（A/B/C，不改变架次结构与箱分配）。接受准则：
能耗下降 ∧ P2 完工 ≤ 6960 s ∧ 零迟到 ∧ 窗口包含性成立。逐候选构建
官方 Solver 判定链（precompute → surgical_fix → build_missions）验证。
"""
import sys, os, json, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from core import Data
from p2_solve import Flight
from common import Budget, safe_eval
import p3_co2
from p3_co2 import Solver

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v20')
TMP = os.path.join(HERE, '_swap_tmp')
W_BOX = (1078.0, 6802.0)
E_BOX = (1406.0, 4074.0)
N_BOX = (5894.0, 6446.0)


def load_champion(data):
    with open(os.path.join(RES, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in r['flights']]


def eval_p2(data, flights):
    b = Budget(100000)
    met, sched = safe_eval(data, flights, b)
    return met, sched


def windows_of(cand_flights, base_starts, offsets):
    """把候选写入 TMP，构建官方 Solver，取 finalize(offsets) 的任务段窗口。
    offsets 取官方 p3_co2.json（联合下界处的可行实现）。"""
    os.makedirs(TMP, exist_ok=True)
    sol = {'flights': [{'fid': f.fid, 'start': base_starts[f.fid],
                        'route': [(s, list(bs)) for s, bs in f.route],
                        'model': f.model} for f in cand_flights]}
    with open(os.path.join(TMP, 'p2_results.json'), 'w', encoding='utf-8') as fh:
        json.dump(sol, fh, ensure_ascii=False)
    old_out = p3_co2.OUT
    p3_co2.OUT = TMP
    try:
        sv = Solver()
        res = sv.finalize({int(k): v for k, v in offsets.items()})
    finally:
        p3_co2.OUT = old_out
    seg = res['seg']
    return seg, sv


def contained(seg, ref):
    """候选（官方偏移下）每组的全部任务段 ⊆ 官方窗口（同样官方偏移下）。"""
    for g in ('W', 'E', 'N'):
        lo = min(a for a, b in ref[g])
        hi = max(b for a, b in ref[g])
        for (a, b) in seg[g]:
            if a < lo - 1e-6 or b > hi + 1e-6:
                return False
    return True


def main():
    data = Data()
    fl0 = load_champion(data)
    met0, _ = eval_p2(data, fl0)
    base = {f.fid: json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))['flights'][i]['start']
            for i, f in enumerate(fl0)}
    print('baseline en=%.4f mk=%.2f fl=%d' % (met0['energy'], met0['makespan'], met0['flights']), flush=True)
    off = {int(k): v for k, v in
           json.load(open(os.path.join(RES, 'p3_co2.json'), encoding='utf-8'))['offsets'].items()}
    # 官方窗口基线（官方偏移下）
    seg0, _ = windows_of(fl0, base, off)
    print('official windows (offset-applied): W_minmax=(%.0f, %.0f) E=(%.0f, %.0f) N=(%.0f, %.0f)' % (
        min(a for a, b in seg0['W']), max(b for a, b in seg0['W']),
        min(a for a, b in seg0['E']), max(b for a, b in seg0['E']),
        min(a for a, b in seg0['N']), max(b for a, b in seg0['N'])), flush=True)

    results = []
    for f in fl0:
        for g in ('A', 'B', 'C'):
            if g == f.model:
                continue
            cand = []
            for x in fl0:
                if x.fid == f.fid:
                    nf = Flight(x.fid, [(s, list(bs)) for s, bs in x.route], g, data)
                    if not nf.is_feasible():
                        nf = None
                    if nf is None:
                        break
                    cand.append(nf)
                else:
                    cand.append(x)
            if len(cand) != len(fl0):
                continue
            m, _ = eval_p2(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if m['flights'] != 26 or m['makespan'] > 6960.0 + 1e-6:
                continue
            d_en = m['energy'] - met0['energy']
            if d_en >= -1e-6:
                continue
            seg, _ = windows_of(cand, base, off)
            safe = contained(seg, seg0)
            results.append({'fid': f.fid, 'model': f.model + '->' + g,
                            'delta_en': round(float(d_en), 4),
                            'mk': round(float(m['makespan']), 2),
                            'window_safe': safe,
                            'windows_minmax': {k: (round(min(a for a, b in seg[k]), 1),
                                                   round(max(b for a, b in seg[k]), 1))
                                               for k in ('W', 'E', 'N')}})
            print('  %s delta_en=%.4f mk=%.2f window_safe=%s' %
                  (f.model + '->' + g, d_en, m['makespan'], safe), flush=True)
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'p2_swap26.json'), 'w', encoding='utf-8') as fh:
        json.dump({'baseline_en': round(float(met0['energy']), 4),
                   'results': results}, fh, ensure_ascii=False, indent=1)
    safe_hits = [r for r in results if r['window_safe']]
    print('\nwindow-safe energy-reducing swaps: %d' % len(safe_hits), flush=True)
    for r in safe_hits:
        print('  ', r['fid'], r['model'], r['delta_en'], flush=True)
    print('saved p2_swap26.json', flush=True)


if __name__ == '__main__':
    main()