# -*- coding: utf-8 -*-
"""
导出 P2 冠军方案为 p2_results.json（p3_co2 联合调度管线的输入）
- 用指定求解器（默认 tabu）+ 较大时间预算重跑得到最优架次集
- dispatch 求得架次起始时间，写出与 p2_solve.py 兼容的结果文件
"""
import sys, os, json, copy, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (Data, TimeBudget, make_initial, safe_eval,
                    summarize, clone_flights)
from solvers import tabu_optimize, sa_baseline
from alns import alns_optimize
from solvers import ga_optimize, grasp_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_P2 = os.path.join(HERE, '..', 'results', 'p2_results.json')

SOLVERS = {
    'tabu': tabu_optimize,
    'sa': sa_baseline,
    'alns': alns_optimize,
    'ga': ga_optimize,
    'grasp': grasp_optimize,
}


def main(solver='tabu', seconds=180.0, seed=7, n_restarts=3):
    with open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8') as fh:
        p1 = json.load(fh)
    data = Data()
    flights0 = make_initial(data, p1['grouping'])
    os.makedirs(os.path.dirname(OUT_P2), exist_ok=True)

    best = None
    best_met = None
    for k in range(n_restarts):
        budget = TimeBudget(seconds / n_restarts)
        fn = SOLVERS[solver]
        fl, met = fn(data, clone_flights(flights0), budget, seed + k)
        if fl is None or met is None:
            continue
        if best is None or (met['hard_ok'], -met['tardy_w'], met['makespan'], met['energy']) > \
                (best_met['hard_ok'], -best_met['tardy_w'], best_met['makespan'], best_met['energy']):
            best = fl
            best_met = met
    if best is None:
        print('FAILED to find solution'); return 1

    # 重新 dispatch 拿启动时刻
    from p2_solve import dispatch, evaluate
    schedule, _ = dispatch(data, best)
    if schedule is None:
        print('dispatch failed')
        return 1

    result = {
        'solver': solver,
        'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                    for k, v in best_met.items() if k != 'box_time'},
        'flights': [],
        'deliveries': [],
    }
    for f in best:
        sch = schedule[f.fid]
        result['flights'].append({
            'fid': f.fid, 'uav': sch['uav'], 'model': f.model, 'battery': sch['battery'],
            'start': round(sch['start'], 1), 'return': round(sch['return'], 1),
            'route': [(s, list(bs)) for s, bs in f.route],
            'energy': round(f.energy(), 4), 'nbox': f.nbox, 'mass': round(f.total_mass, 2),
        })
        for sid, bid, t in sch['deliveries']:
            result['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
    with open(OUT_P2, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print('champion (%s) -> %s' % (solver, OUT_P2))
    print({k: v for k, v in result['metrics'].items()})
    return 0


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--solver', default='tabu')
    ap.add_argument('--seconds', type=float, default=180.0)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--restarts', type=int, default=3)
    args = ap.parse_args()
    sys.exit(main(args.solver, args.seconds, args.seed, args.restarts))