# -*- coding: utf-8 -*-
"""v41 完工冲刺 II：全局满载扫描拆分（修正 v40 只看最长链的盲区）。
从 29 架（7168.5s）出发：扫描所有池的满载趟（单区 mass>=25 且 >=3 箱），
优先拆 B 池（T/台 6993 最高），拆出的 A 子趟并行进 A 池（4 台）。
T/8=6218 为当前可及下界。完工降 + 零违规 + 能耗限 +6。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import eval_full
from p2v35_mk import split_into_ab

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def main():
    tol = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    src = sys.argv[2] if len(sys.argv) > 2 else 'p2v40_mk_tol6_0.json'
    d0 = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 %s: %d 架 / mk %.1f / %.2f kWh / 违规%d  [容限+%.0f]' % (
        src, len(fls), m0['makespan'], m0['energy'], nc0, tol))
    cur = fls
    for rnd in range(20):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d: 违规出现' % (rnd + 1)); break
        # 全局满载候选（按池 T/台 超载优先：B/C 池）
        pools = {'A': 4, 'B': 2, 'C': 2}
        cands = []
        for f in cur:
            if len(f.route) == 1 and f.total_mass >= 25 and len(f.box_ids) >= 3:
                cands.append(f)
        # 排序：池超载度（T/台 高者优先）+ 趟长
        cands.sort(key=lambda f: (-(pools[f.model]), -f.duration(), f.fid))
        improved = False
        for f in cands:
            # 不预筛期望——让拆后评估判定（拆出子趟含医疗箱也可由 A 池早飞满足）
            parts = split_into_ab(cur, f, data)
            if not parts:
                continue
            candfl = [x for x in cur if x.fid != f.fid] + parts
            m2, s2, v2, nc2 = eval_full(data, candfl)
            if m2 and v2 == 0 and nc2 == 0 and m2['makespan'] < m['makespan'] - 1e-6 \
                    and m2['energy'] <= m['energy'] + tol:
                print('  r%d: 拆 f%d %s mass%.0f (限%.0f) -> %d子趟 mk %.1f en %.2f (%d架)' % (
                    rnd + 1, f.fid, [x for x, _ in f.route], f.total_mass, mn, len(parts),
                    m2['makespan'], m2['energy'], len(candfl)), flush=True)
                cur = candfl
                improved = True
                break
        if not improved:
            print('r%d: 无接受（完工收敛）' % (rnd + 1))
            break
    m, s, v, nc = eval_full(data, cur)
    print('最终[+%.0f]: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 违规%d' % (
        tol, len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], nc))
    tag = 'p2v41_mk_tol%s' % str(tol).replace('.', '_')
    json.dump({'tol': tol, 'best': {k: vv for k, vv in m.items() if k != 'box_time'},
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, tag + '.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/%s.json' % tag)


if __name__ == '__main__':
    main()