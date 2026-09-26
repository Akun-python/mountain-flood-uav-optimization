# -*- coding: utf-8 -*-
"""p2v62_heuristic_x.py —— 对照：新算子(跨区迁移+换型)纯启发式贪心（无 RL）能否独立发现 6990.1。
判别 GAT v61 的 RL/边表征是否有独立贡献（vs 新算子本身的启发式价值）。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dqn23_gat import (data, OUTD, K, load_init, build_candidates_x, eval_improve_scene_x, eval_full, clone)


def main():
    fls = clone(load_init())
    m0, _, _, _ = eval_full(data, fls)
    print('起点: %d架 mk=%.1f en=%.2f' % (len(fls), m0['makespan'], m0['energy']))
    rnd = 0
    while True:
        c, feats, scores, sidx, didx = build_candidates_x(fls)
        if not c:
            break
        m0c, _, _, _ = eval_full(data, fls)
        best_ls = None
        n_try = 0
        for i in range(min(len(c), K)):
            imp = eval_improve_scene_x(fls, c[i])
            if imp is None:
                continue
            n_try += 1
            _, nf2 = imp
            m2c, _, v2c, nc2c = eval_full(data, nf2)
            if m2c is None or v2c > 0 or nc2c > 0 or (not m2c['hard_ok']):
                continue
            ok = (m2c['makespan'] < m0c['makespan'] - 1e-6) or \
                 (abs(m2c['makespan'] - m0c['makespan']) < 1e-6 and
                  m2c['energy'] < m0c['energy'] - 0.02)
            if ok and (best_ls is None or
                       (m2c['makespan'], m2c['energy']) < (best_ls[0]['makespan'], best_ls[0]['energy'])):
                best_ls = (m2c, nf2)
        if best_ls is None:
            print('r%d 收敛: 无接受步 (候选%d 试%d)' % (rnd, min(len(c), K), n_try))
            break
        fls = best_ls[1]
        rnd += 1
        print('r%d: mk=%.1f en=%.2f' % (rnd, best_ls[0]['makespan'], best_ls[0]['energy']))
        if rnd > 60:
            break
    m, s, v, nc = eval_full(data, fls)
    print('最终: %d架 mk=%.1f (%.2fmin) en=%.2f hard=%s 违规%d 临界%d' % (
        len(fls), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy']},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in fls]},
              open(os.path.join(OUTD, 'p2v62_heuristic_x.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()