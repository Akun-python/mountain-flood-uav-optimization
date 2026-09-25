# -*- coding: utf-8 -*-
"""v38 就地瘦身（能耗 <66 冲刺）：对 v37 解（22架/8172/66.58）做拆出箱合并。
算子：同区拆出的轻载单箱/双箱趟合并成 B/A 满载趟（省 prep 与飞行能耗）；
同区趟并入邻近趟（体积/质量/能量可行）；保持零紧时限违规，能耗降即接受。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import tardy_boxes, eval_full

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def rebuild(fls, pairs):
    """pairs: [(drop_fid, [(sid, [boxes])], model), ...] 替换对应架次。"""
    out = []
    drops = {p[0] for p in pairs}
    for f in fls:
        if f.fid in drops:
            continue
        out.append(f)
    fid = max(x.fid for x in fls) + 1
    for drop_fid, route, model in pairs:
        nf = Flight(fid, route, model, data)
        if not nf.is_feasible():
            return None
        out.append(nf)
        fid += 1
    return out


def main():
    d0 = json.load(open(os.path.join(OUTD, 'p2v37_merge.json'), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d0['solution']]
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 v37: %d 架 / mk %.1f / %.2f kWh / 违规%d' % (
        len(fls), m0['makespan'], m0['energy'], nc0))
    cur = fls
    for rnd in range(12):
        m, s, v, nc = eval_full(data, cur)
        if nc > 0:
            print('r%d: 违规出现' % (rnd + 1)); break
        # 找同区轻载趟（<=2箱 或 <=16kg 单区）
        light = []
        for f in cur:
            if len(f.route) == 1 and f.nbox <= 2 and f.total_mass <= 16:
                light.append(f)
        improved = False
        for i in range(len(light)):
            for j in range(i + 1, len(light)):
                a, b = light[i], light[j]
                if a.fid == b.fid:
                    continue
                if a.route[0][0] != b.route[0][0]:
                    continue
                sid = a.route[0][0]
                bs = a.route[0][1] + b.route[0][1]
                for gm in ['B', 'A', 'C']:
                    nf = Flight(0, [(sid, bs)], gm, data)
                    if not nf.is_feasible():
                        continue
                    cand = [x for x in cur if x.fid not in (a.fid, b.fid)]
                    fid = max(x.fid for x in cur) + 1
                    nf.fid = fid
                    cand.append(nf)
                    m2, s2, v2, nc2 = eval_full(data, cand)
                    if m2 and v2 == 0 and nc2 == 0 and m2['energy'] < m['energy'] - 0.05:
                        print('r%d: 合并 f%d+f%d (%s %d箱%.0fkg->%s) mk %.1f en %.2f (-%.2f)' % (
                            rnd + 1, a.fid, b.fid, sid, len(bs), nf.total_mass, gm,
                            m2['makespan'], m2['energy'], m['energy'] - m2['energy']), flush=True)
                        cur = cand
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
        if not improved:
            print('r%d: 无瘦身合并' % (rnd + 1))
            break
    m, s, v, nc = eval_full(data, cur)
    print('\n最终: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 电池违规=%d / 紧时限违规=%d' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    if nc == 0 and m['energy'] < 66.58 - 1e-6:
        print('>>> 能耗再破: %.2f kWh (原 66.58)' % m['energy'])
        json.dump({'best': {k: vv for k, vv in m.items() if k != 'box_time'},
                   'prev': {'mk': m0['makespan'], 'en': m0['energy']},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
                  open(os.path.join(OUTD, 'p2v38_lean.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v38_lean.json')
    else:
        print('未突破 66.58')


if __name__ == '__main__':
    main()