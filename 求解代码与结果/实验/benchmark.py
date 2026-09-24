# -*- coding: utf-8 -*-
"""
D题 算法家族横向对比基准（问题二）
- 统一预算（目标评估次数）+ 多随机种子
- 输出：bench_p2_results.json + bench_p2_report.md
- 求解器：sa_baseline / ga / alns / tabu / grasp
"""
import sys, os, json, time, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (Data, Budget, TimeBudget, make_initial, safe_eval,
                    summarize, clone_flights)
from solvers import sa_baseline, ga_optimize, tabu_optimize, grasp_optimize
from alns import alns_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(HERE, 'samples')
os.makedirs(RESULT_DIR, exist_ok=True)

SOLVERS = {
    'sa_baseline': lambda data, fl0, budget, seed: sa_baseline(data, fl0, budget, seed),
    'ga': lambda data, fl0, budget, seed: ga_optimize(data, fl0, budget, seed),
    'alns': lambda data, fl0, budget, seed: alns_optimize(data, fl0, budget, seed),
    'tabu': lambda data, fl0, budget, seed: tabu_optimize(data, fl0, budget, seed),
    'grasp': lambda data, fl0, budget, seed: grasp_optimize(data, fl0, budget, seed),
}


def run_benchmark(seconds=60, seeds=(7, 11, 13), solvers=None):
    data, p1g = None, None
    with open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8') as fh:
        p1 = json.load(fh)
    data = Data()
    flights0 = make_initial(data, p1['grouping'])
    met0, _ = safe_eval(data, clone_flights(flights0), Budget(10**9))
    print('seed solution:', summarize(met0))

    solvers = solvers or list(SOLVERS)
    rows = []
    for name in solvers:
        fn = SOLVERS[name]
        for seed in seeds:
            budget = TimeBudget(seconds)
            t0 = time.time()
            fl, met = fn(data, clone_flights(flights0), budget, seed)
            dt = time.time() - t0
            if fl is None or met is None:
                print('%-6s seed=%d  FAILED' % (name, seed))
                continue
            evals = budget.spent()
            m = summarize(met)
            row = {'solver': name, 'seed': seed, 'evals': evals,
                   'time_s': round(dt, 1), **m}
            rows.append(row)
            print('%-6s seed=%d  flights=%d makespan=%s energy=%s tardy_w=%s hard=%s  (%ds, %d evals)'
                  % (name, seed, m['flights'], m['makespan'], m['energy'], m['tardy_w'],
                     m['hard_ok'], round(dt), evals))
            # 最优快照存档
            save = os.path.join(RESULT_DIR, 'best_%s_s%d.json' % (name, seed))
            with open(save, 'w', encoding='utf-8') as fh:
                json.dump({'solver': name, 'seed': seed, 'metrics': m,
                           'flights': [{'fid': f.fid, 'model': f.model,
                                        'route': [(s, b) for s, b in f.route],
                                        'energy': round(f.energy(), 4),
                                        'mass': round(f.total_mass, 2),
                                        'nbox': f.nbox} for f in fl]},
                          fh, ensure_ascii=False, indent=1)

    # ---- 汇总：每求解器取最优种子 ----
    best_by_solver = {}
    for name in solvers:
        rs = [r for r in rows if r['solver'] == name]
        if not rs:
            continue
        rs.sort(key=lambda r: (not r['hard_ok'], r['tardy_w'], r['makespan'],
                               r['energy'], r['flights']))
        best_by_solver[name] = rs[0]

    with open(os.path.join(RESULT_DIR, 'bench_p2_results.json'), 'w', encoding='utf-8') as fh:
        json.dump({'seconds': seconds, 'seeds': list(seeds),
                   'rows': rows, 'best_by_solver': best_by_solver},
                  fh, ensure_ascii=False, indent=1)

    # ---- Markdown 报告 ----
    lines = ['# D题 问题二 算法家族横向对比（墙钟预算=%ds/次）' % seconds, '']
    lines.append('| 求解器 | 种子 | 架次 | makespan (s) | 能耗 (kWh) | 加权迟到 | 硬约束 | 评估数 | 耗时(s) |')
    lines.append('|---|---|---|---|---|---|---|---|---|')
    for r in sorted(rows, key=lambda x: (x['solver'], x['seed'])):
        lines.append('| %s | %d | %d | %.1f | %.3f | %.3f | %s | %d | %.1f |'
                     % (r['solver'], r['seed'], r['flights'], r['makespan'],
                        r['energy'], r['tardy_w'], r['hard_ok'], r['evals'], r['time_s']))
    lines.append('')
    lines.append('## 每求解器最优种子')
    lines.append('| 求解器 | 种子 | 架次 | makespan | 能耗 | 加权迟到 |')
    lines.append('|---|---|---|---|---|---|')
    for name, r in sorted(best_by_solver.items(), key=lambda kv: kv[1]['makespan']):
        lines.append('| %s | %d | %d | %.1f | %.3f | %.3f |'
                     % (name, r['seed'], r['flights'], r['makespan'], r['energy'], r['tardy_w']))
    rep = os.path.join(RESULT_DIR, 'bench_p2_report.md')
    with open(rep, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print('report ->', rep)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--seeds', type=str, default='7,11,13')
    ap.add_argument('--solver', type=str, default='')
    args = ap.parse_args()
    seeds = tuple(int(s) for s in args.seeds.split(','))
    solvers = [s.strip() for s in args.solver.split(',') if s.strip()] or None
    run_benchmark(args.seconds, seeds, solvers)