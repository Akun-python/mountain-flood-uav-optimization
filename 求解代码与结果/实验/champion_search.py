# -*- coding: utf-8 -*-
"""
P2 强化冠军搜索：多权重配置 x 多种子 x 多次重启，收集全部零迟到解，
按 (makespan, energy) 与 (energy, makespan) 双口径排序，输出强化后的冠军
可选 --export 把最优解写入 results/p2_results.json（供 P3 管线使用）
"""
import sys, os, json, time, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (Data, TimeBudget, make_initial, safe_eval,
                    summarize, clone_flights, set_weights)
from solvers import tabu_optimize

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_P2 = os.path.join(HERE, '..', 'results', 'p2_results.json')
SAMPLE = os.path.join(HERE, 'samples', 'champion_search.json')

CONFIGS = {
    'baseline':        (1.0, 0.05, 0.8, 30.0),
    'balanced':        (5.0, 0.3,  1.0, 20.0),
    'energy_strong':   (1.0, 0.02, 2.0, 20.0),
    'makespan_strong': (10.0, 0.5, 0.5, 10.0),
}


def run(total_seconds=600.0, seeds=(7, 11, 13), n_restarts=2, solver='tabu',
        export=False):
    with open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8') as fh:
        p1 = json.load(fh)
    data = Data()
    flights0 = make_initial(data, p1['grouping'])
    fn = tabu_optimize
    rows = []
    for cfg_name, w in CONFIGS.items():
        set_weights(*w)
        per = total_seconds / (len(CONFIGS) * len(seeds) * n_restarts)
        for seed in seeds:
            for k in range(n_restarts):
                budget = TimeBudget(per)
                t0 = time.time()
                fl, met = fn(data, clone_flights(flights0), budget, seed + 17 * k)
                dt = time.time() - t0
                if fl is None or met is None:
                    continue
                m = summarize(met)
                rows.append({'config': cfg_name, 'seed': seed, 'restart': k,
                             'flights': m['flights'], 'makespan': m['makespan'],
                             'energy': m['energy'], 'tardy_w': m['tardy_w'],
                             'hard_ok': m['hard_ok'], 'time_s': round(dt, 1),
                             'fl': fl, 'met': m})
    ok_rows = [r for r in rows if r['hard_ok'] and r['tardy_w'] < 1e-6]
    print('total runs=%d  zero-tardy=%d' % (len(rows), len(ok_rows)))
    by_mk = sorted(ok_rows, key=lambda r: (r['makespan'], r['energy']))
    by_en = sorted(ok_rows, key=lambda r: (r['energy'], r['makespan']))
    print('\n== top-6 by makespan ==')
    for r in by_mk[:6]:
        print('  %-16s s%-3d fl=%d mk=%.1f e=%.3f' %
              (r['config'], r['seed'], r['flights'], r['makespan'], r['energy']))
    print('\n== top-6 by energy ==')
    for r in by_en[:6]:
        print('  %-16s s%-3d fl=%d mk=%.1f e=%.3f' %
              (r['config'], r['seed'], r['flights'], r['makespan'], r['energy']))
    # 保存（不含 Flight 对象，仅指标）
    slim = [{k: v for k, v in r.items() if k != 'fl'}
            for r in sorted(rows, key=lambda r: (not r['hard_ok'], r['tardy_w']))]
    with open(SAMPLE, 'w', encoding='utf-8') as fh:
        json.dump({'rows': slim}, fh, ensure_ascii=False, indent=1)
    # 导出：makespan 口径冠军
    if export and by_mk:
        champ = by_mk[0]
        from p2_solve import dispatch
        schedule, _ = dispatch(data, champ['fl'])
        result = {'solver': solver, 'config': champ['config'],
                  'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                              for k, v in champ['met'].items() if k != 'box_time'},
                  'flights': [], 'deliveries': []}
        for f in champ['fl']:
            sch = schedule[f.fid]
            result['flights'].append({
                'fid': f.fid, 'uav': sch['uav'], 'model': f.model, 'battery': sch['battery'],
                'start': round(sch['start'], 1), 'return': round(sch['return'], 1),
                'route': [(s, list(bs)) for s, bs in f.route],
                'energy': round(f.energy(), 4), 'nbox': f.nbox, 'mass': round(f.total_mass, 2)})
            for sid, bid, t in sch['deliveries']:
                result['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
        json.dump(result, open(OUT_P2, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\nchampion exported ->', OUT_P2, result['metrics'])
    return rows


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=600.0)
    ap.add_argument('--seeds', type=str, default='7,11,13')
    ap.add_argument('--restarts', type=int, default=2)
    ap.add_argument('--export', action='store_true')
    args = ap.parse_args()
    run(args.seconds, tuple(int(s) for s in args.seeds.split(',')),
        args.restarts, export=args.export)