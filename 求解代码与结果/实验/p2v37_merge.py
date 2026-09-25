# -*- coding: utf-8 -*-
"""v37 能耗 66~68.3 区间补搜（回应"68.3 是否为能耗下界"的质疑）。
核心算子升级：及时性拆分不再每箱新增一趟（v34 做法），而是把超时箱**并入已有早趟**的
可用载重/体积/能量余量，或并入后替换同区轻箱（被替换箱并入别趟），保持架次增量最小——
省 prep 与飞行能耗，目标零紧时限违规 + 能耗 < 68.3（v35 能耗优）。
起点：P1 满载 18 趟（59.02 kWh，紧时限违规 8 箱）。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, evaluate
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import tardy_boxes, eval_full

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def try_merge(cur, fls_cur, bid, data, used_fid):
    """把 bid 并入现有某趟（同区），尽量不加趟。返回 (new_fls, ok) 或 None。"""
    sid = bid.split('-')[0]
    bx = data.boxes[bid]
    for f in fls_cur:
        # 只并入含同区的单区趟或该区趟（保持区一致；多区趟并入第二区会改 ct，先限单区）
        if len(f.route) == 1 and f.route[0][0] == sid:
            bs = f.route[0][1]
            if bid in bs:
                continue
            nbs = bs + [bid]
            # 机型不变试；不行试更大机型
            for gm in [f.model] + ([x for x in ['A', 'B', 'C'] if x != f.model]):
                nf = Flight(f.fid, [(sid, nbs)], gm, data)
                if nf.is_feasible():
                    cand = [x for x in cur if x.fid != f.fid] + [nf]
                    m2, s2, v2, nc2 = eval_full(data, cand)
                    if m2 and v2 == 0 and nc2 <= cur_nc_global[0] and m2['tardy_w'] <= cur_tw_global[0] + 1e-6:
                        return cand, nf.fid
                    break
    return None


cur_nc_global = [10 ** 9]
cur_tw_global = [10 ** 9]


def main():
    p1 = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results',
                                     'p1_results.json'), encoding='utf-8'))
    g = p1['grouping']
    fls = []
    fid = 1
    for sid in sorted(g):
        for det in g[sid]['detail']:
            fls.append(Flight(fid, [(sid, det['boxes'])], det['model'], data))
            fid += 1
    m0, s0, v0, nc0 = eval_full(data, fls)
    print('起点 P1 满载: %d 架 / mk %.1f / %.2f kWh / 紧时限违规 %d' % (
        len(fls), m0['makespan'], m0['energy'], nc0))
    cur = fls
    hist = []
    for rnd in range(30):
        m, s, v, nc = eval_full(data, cur)
        if m is None or v > 0:
            print('r%d: 调度失败/电池违规' % (rnd + 1)); break
        cur_nc_global[0] = nc
        cur_tw_global[0] = m['tardy_w']
        tb = tardy_boxes(data, s)
        if not tb:
            print('r%d: 零紧时限违规达成' % (rnd + 1)); break
        improved = False
        for late, bid, ddl, t, src_fid in tb:
            # 1) 先试并入已有同区趟
            r = try_merge(cur, cur, bid, data, max(x.fid for x in cur) + 1)
            if r:
                cand, _ = r
                m2, s2, v2, nc2 = eval_full(data, cand)
                if m2 and nc2 < nc and v2 == 0:
                    cur = cand
                    print('r%d: %s 并入现有趟 (%d架) mk %.1f en %.2f 违规%d' % (
                        rnd + 1, bid, len(cur), m2['makespan'], m2['energy'], nc2), flush=True)
                    hist.append((len(cur), m2['makespan'], m2['energy'], nc2))
                    improved = True
                    break
            # 2) 否则新增独立趟（v34 老法，兜底）
            src = next(x for x in cur if x.fid == src_fid)
            rest = {}
            for s2, bs in src.route:
                for b in bs:
                    if b != bid:
                        rest.setdefault(s2, []).append(b)
            nf = None
            for gm in ['A', 'B', 'C']:
                cf = Flight(max(x.fid for x in cur) + 1, [(bid.split('-')[0], [bid])], gm, data)
                if cf.is_feasible():
                    nf = cf; break
            if nf is None:
                continue
            cur2 = [x for x in cur if x.fid != src.fid]
            if rest:
                r2 = [(s2, bs2) for s2, bs2 in rest.items()]
                ok = False
                for gm in ['A', 'B', 'C']:
                    nf3 = Flight(src.fid, r2, gm, data)
                    if nf3.is_feasible():
                        cur2.append(nf3); ok = True; break
                if not ok:
                    continue
            cur2.append(nf)
            m2, s2, v2, nc2 = eval_full(data, cur2)
            if m2 and v2 == 0 and nc2 < nc:
                cur = cur2
                print('r%d: %s 新增趟 (%d架) mk %.1f en %.2f 违规%d' % (
                    rnd + 1, bid, len(cur), m2['makespan'], m2['energy'], nc2), flush=True)
                hist.append((len(cur), m2['makespan'], m2['energy'], nc2))
                improved = True
                break
        if not improved:
            print('r%d: 无法修复违规箱' % (rnd + 1))
            break
    m, s, v, nc = eval_full(data, cur)
    tb = tardy_boxes(data, s) if s else []
    print('\n最终: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 电池违规=%d / 紧时限违规=%d' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, nc))
    if nc == 0 and m['energy'] < 68.30 - 1e-6:
        print('>>> 能耗新冠军: %.2f kWh (原 68.30)' % m['energy'])
        json.dump({'best': {k: vv for k, vv in m.items() if k != 'box_time'},
                   'traj': hist,
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
                  open(os.path.join(OUTD, 'p2v37_merge.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v37_merge.json')
    else:
        print('未突破 68.30（零违规最低仍为 v35 能耗优）')


if __name__ == '__main__':
    main()