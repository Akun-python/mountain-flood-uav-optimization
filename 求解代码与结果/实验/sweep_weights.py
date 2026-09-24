# -*- coding: utf-8 -*-
"""
Tabu 目标权重扫描（问题二）
- 在同一算力预算与种子下，扫描多组 (tardy, makespan, energy, flights) 权重
- 目标：找出能进一步压低 makespan / 能耗且保持零迟到的 Tabu 配置
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (Data, TimeBudget, make_initial, safe_eval, summarize,
                    clone_flights, set_weights)
from solvers import tabu_optimize, sa_baseline

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'samples')

CONFIGS = {
    'baseline':      dict(tardy=1.0,  makespan=0.05, energy=0.8,  flights=30.0),
    'makespan_strong': dict(tardy=10.0, makespan=0.5, energy=0.5,  flights=10.0),
    'energy_strong': dict(tardy=1.0, makespan=0.02, energy=2.0,  flights=20.0),
    'flights_strong': dict(tardy=10.0, makespan=0.05, energy=0.8, flights=60.0),
    'balanced':      dict(tardy=5.0,  makespan=0.3,  energy=1.0,  flights=20.0),
}


def run(seconds=60.0, seeds=(7, 11), solver='tabu'):
    with open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8') as fh:
        p1 = json.load(fh)
    data = Data()
    flights0 = make_initial(data, p1['grouping'])
    fn = tabu_optimize if solver == 'tabu' else sa_baseline
    rows = []
    for cfg_name, w in CONFIGS.items():
        set_weights(**w)
        for seed in seeds:
            budget = TimeBudget(seconds)
            t0 = time.time()
            fl, met = fn(data, clone_flights(flights0), budget, seed)
            dt = time.time() - t0
            if fl is None or met is None:
                print('%-16s seed=%d FAILED' % (cfg_name, seed))
                continue
            m = summarize(met)
            rows.append({'config': cfg_name, 'seed': seed, **w, **m,
                         'time_s': round(dt, 1), 'evals': budget.spent()})
            print('%-16s seed=%d flights=%d makespan=%s energy=%s tardy=%s hard=%s'
                  % (cfg_name, seed, m['flights'], m['makespan'], m['energy'],
                     m['tardy_w'], m['hard_ok']))
    # 按 (硬约束, 迟到, makespan, energy) 排序报表
    rows.sort(key=lambda r: (not r['hard_ok'], r['tardy_w'], r['makespan'], r['energy']))
    with open(os.path.join(OUT, 'sweep_weights_%s.json' % solver), 'w', encoding='utf-8') as fh:
        json.dump({'seconds': seconds, 'seeds': list(seeds), 'rows': rows},
                  fh, ensure_ascii=False, indent=1)
    print('\nranked (hard, tardy, makespan, energy):')
    for r in rows[:10]:
        print('  %-16s s%d fl=%d mk=%.1f e=%.3f tardy=%.3f hard=%s'
              % (r['config'], r['seed'], r['flights'], r['makespan'], r['energy'],
                 r['tardy_w'], r['hard_ok']))
    return rows


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--seeds', type=str, default='7,11')
    ap.add_argument('--solver', default='tabu')
    args = ap.parse_args()
    seeds = tuple(int(s) for s in args.seeds.split(','))
    run(args.seconds, seeds, args.solver)