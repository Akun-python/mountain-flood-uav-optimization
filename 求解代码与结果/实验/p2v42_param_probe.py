# -*- coding: utf-8 -*-
"""v42-πσ：参数空间架次构成诊断——对启发式种子×变异体做快速扫描，
统计架次分布与 23-25 合规点是否存在；确定可行编码方向。"""
import sys, os, json, random, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import p2v42_param_ga as P

rng = random.Random(42)
stats = {'<23': 0, '23-25': 0, '>25': 0, 'fail': 0}
pts = []
SAMPLE = 400
HEUR = P.heuristic_seeds()
for i in range(SAMPLE):
    if i < len(HEUR):
        g = json.loads(json.dumps(HEUR[i]))
    elif i < 60:
        g = P.mutate(HEUR[i % len(HEUR)], rng, rate=0.35)
    else:
        g = P.gen_rand(rng)
        if rng.random() < 0.5:
            g = P.mutate(g, rng, rate=0.4)
    fl = P.build(**g)
    m = P.evaluate_sol(fl)
    if not (m['hard_ok'] and m['tardy_w'] < 1e-6 and m['bad'] == 0 and m['nbox'] == 80 and m['uniq'] == 80):
        stats['fail'] += 1
        continue
    if m['flights'] < 23:
        stats['<23'] += 1
    elif m['flights'] <= 25:
        stats['23-25'] += 1
        pts.append((m['flights'], m['makespan'], m['energy'], g))
    else:
        stats['>25'] += 1
print(stats)
print('23-25 合规点 %d 个:' % len(pts))
for nf, mk, en, g in sorted(pts)[:20]:
    cnt = {m: sum(1 for a in g['assigns'].values() if a == m) for m in 'ABC'}
    print('  %d架 mk=%7.0f e=%6.2f 区数A/B/C=%d/%d/%d capC=%d capB=%d merge=%s' % (
        nf, mk, en, cnt['A'], cnt['B'], cnt['C'], g['cap_c'], g['cap_b'], g['merge_on']))
if not pts:
    print('分布参考（>25 的部分）:')
    for i in range(SAMPLE):
        g = P.mutate(HEUR[i % len(HEUR)], rng, rate=0.3) if i % 2 else P.gen_rand(rng)
        fl = P.build(**g)
        m = P.evaluate_sol(fl)
        if m['hard_ok'] and m['tardy_w'] < 1e-6 and m['bad'] == 0 and m['nbox'] == 80:
            cnt = {mm: sum(1 for a in g['assigns'].values() if a == mm) for mm in 'ABC'}
            print('  %d架 mk=%7.0f e=%6.2f A/B/C区=%d/%d/%d capC=%d capB=%d' % (
                m['flights'], m['makespan'], m['energy'], cnt['A'], cnt['B'], cnt['C'], g['cap_c'], g['cap_b']))
            if i > 250:
                break