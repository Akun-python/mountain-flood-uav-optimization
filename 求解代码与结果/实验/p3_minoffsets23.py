# -*- coding: utf-8 -*-
"""
v23b · 多起点联合完工最小化（快速评估，确认最小偏移盆地）
=========================================================
复用 p3_joint_min26.joint_of（单次构建 Solver，逐偏移快速评估）。
多起点：A=仅{f4:3600,f22:1200}（7087 盆地）、B=全零、C=官方偏移。
每起点 2500 迭代；记录各起点最优可行联合。
"""
import sys, os, json, random, copy, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import p3_co2
from p3_co2 import Solver, POS_OF
from p3_joint_min26 import joint_of

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v23')
MAXDELAY, MAXEARLY = 3600.0, 3600.0


def sa_from(sv, init, iters, seed):
    rng = random.Random(seed)
    cur = {k: init.get(k, 0.0) for k in sv.base}
    cur_obj, cur_info = joint_of(sv, cur)
    best, best_obj, best_info = dict(cur), cur_obj, cur_info
    T = 300.0
    for it in range(iters):
        nxt = copy.deepcopy(cur)
        kind = rng.random()
        if kind < 0.35:
            # 整组平移（W/E/N 各自整体）
            g = rng.choice(['W', 'E', 'N'])
            step = rng.choice([-2400, -1200, -600, 600, 1200, 2400])
            for fid, gg in groups.items():
                if gg == g:
                    nxt[fid] = min(MAXDELAY, max(-MAXEARLY, nxt[fid] + step))
        elif kind < 0.8:
            for _ in range(rng.choice([1, 1, 2])):
                fid = rng.choice(list(nxt))
                step = rng.choice([100, 200, 300, 600, 1200])
                nxt[fid] = min(MAXDELAY, max(-MAXEARLY, nxt[fid] + rng.choice([-1, 1]) * step))
        else:
            # f4/f22（N 对齐）与 W 尾段微调
            for fid in (4, 22):
                nxt[fid] = min(MAXDELAY, max(-MAXEARLY, nxt[fid] + rng.choice([-300, -100, 100, 300])))
        o2, i2 = joint_of(sv, nxt)
        if o2 <= cur_obj or rng.random() < math.exp(min(0.0, (cur_obj - o2) / T)):
            cur, cur_obj = nxt, o2
            if i2 is not None and i2['joint'] < best_info['joint']:
                best, best_obj, best_info = dict(nxt), o2, i2
        if it % 800 == 0:
            print('    [%s] it=%d best_joint=%.1f' % (seed, it, best_info['joint']), flush=True)
        T = max(5.0, T * 0.999)
    return best, best_obj, best_info


def math_exp(x):
    import math
    return math.exp(x)


def main():
    global groups
    p3_co2.OUT = RES
    sv = Solver()
    groups = {}
    for f in sv.flights:
        areas = [s for s, _ in f.route]
        gs = [p3_co2.AREA_POS[s] for s in areas if s in p3_co2.AREA_POS]
        groups[f.fid] = max(set(gs), key=gs.count) if gs else 'W'
    official = {int(k): v for k, v in
                json.load(open(os.path.join(RES, 'p3_co2.json'), encoding='utf-8'))['offsets'].items()}
    only = sys.argv[1] if len(sys.argv) > 1 else 'all'
    starts = {
        'A_f4f22': {4: 3600.0, 22: 1200.0},
        'B_zero': {k: 0.0 for k in sv.base},
        'C_official': official,
    }
    if only != 'all':
        starts = {k: v for k, v in starts.items() if k.startswith(only)}
    os.makedirs(OUTD, exist_ok=True)
    out = {'starts': {}, 'best': None}
    best_overall = None
    for name, init in starts.items():
        print('== start %s ==' % name, flush=True)
        best, obj, info = sa_from(sv, init, 1500, seed=11)
        # 用修正后的模型完整复核（joint_of 已含 cov/overlap/mpen 罚）
        o_final, info_final = joint_of(sv, best)
        rec = {'init': name, 'offsets': {str(k): round(float(v), 1) for k, v in sorted(best.items())},
               'info': {k: (round(float(v), 2) if isinstance(v, float) else v)
                        for k, v in info_final.items()},
               'joint': info_final['joint'] if info_final else None}
        out['starts'][name] = rec
        print('  result joint=%.1f cov=%d mpen=%s relay=%.3f' % (
            rec['joint'], rec['info'].get('cov_bad', -1), rec['info'].get('mpen'),
            rec['info'].get('relay_energy')), flush=True)
        if info_final and info_final['joint'] < (best_overall[1] if best_overall else 1e18):
            best_overall = (name, info_final['joint'], best, info_final)
    if best_overall:
        out['best'] = {'start': best_overall[0], 'joint': round(float(best_overall[1]), 2),
                       'offsets': {str(k): round(float(v), 1) for k, v in sorted(best_overall[2].items())},
                       'info': {k: (round(float(v), 2) if isinstance(v, float) else v)
                                for k, v in best_overall[3].items()}}
    out['official_baseline'] = {'joint': 7259.81, 'relay_energy': 3.417}
    with open(os.path.join(OUTD, 'v23_multistart.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('\nBEST: %s joint=%.1f' % (out['best']['start'], out['best']['joint']), flush=True)
    print('saved v23_multistart.json', flush=True)


if __name__ == '__main__':
    main()