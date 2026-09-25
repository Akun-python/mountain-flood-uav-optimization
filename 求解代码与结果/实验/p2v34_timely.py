# -*- coding: utf-8 -*-
"""v34 从 P1 满载出发 + 及时性驱动拆分（指标优先级：及时性 > 完工 > 能耗 > 架次）。
迭代：dispatch 后找所有"到达 > 期望 deadline"的箱（按超时降序），拆出为独立 A/B 早趟，
直到 tardy_w=0（零迟到）。接受：tardy_w 单调降。
起点：P1 满载 18 趟（59.02kWh）。目标：23架级 / 零迟到 / 低能耗。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, evaluate
from p2v28_compliant import dispatch_compliant, check_battery

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def tardy_boxes(data, sch):
    """所有到达>紧时限(取首批截止/医疗期望与普通期望更紧者)的箱，按超时降序。
    返回 [(late, bid, ddl, t, src_fid)]。"""
    out = []
    for fid, s in sch.items():
        for sid, bid, t in s['deliveries']:
            bx = data.boxes[bid]
            ddl = min(bx['deadline_first'], bx['deadline_exp'])
            late = t - ddl
            if late > 1e-6:
                out.append((late, bid, ddl, t, fid))
    out.sort(reverse=True)
    return out


def eval_full(data, fl):
    sch, _ = dispatch_compliant(data, fl)
    if sch is None:
        return None, None, 999, 999
    viol = check_battery(data, sch, fl)
    m = evaluate(data, fl, sch)
    ncrit = len(tardy_boxes(data, sch))
    return m, sch, len(viol), ncrit


def best_new_flight(bid, data, used_fid):
    sid = bid.split('-')[0]
    for gm in ['A', 'B', 'C']:
        nf = Flight(used_fid, [(sid, [bid])], gm, data)
        if nf.is_feasible():
            return nf
    return None


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
    print('起点 P1 满载: %d 架 / mk %.1f / %.2f kWh / tardy %.1f / 紧时限违规 %d' % (
        len(fls), m0['makespan'], m0['energy'], m0['tardy_w'], nc0))
    cur = fls
    hist = [(m0['makespan'], m0['energy'], m0['tardy_w'])]
    for rnd in range(25):
        m, s, v, nc = eval_full(data, cur)
        if m is None or v > 0:
            print('r%d: 调度失败/电池违规' % (rnd + 1)); break
        tb = tardy_boxes(data, s)
        if not tb:
            print('r%d: 零紧时限违规达成' % (rnd + 1)); break
        late, bid, ddl, t, src_fid = tb[0]
        nf = best_new_flight(bid, data, max(x.fid for x in cur) + 1)
        if nf is None:
            print('r%d: %s 无法拆分' % (rnd + 1, bid)); break
        # 原架次移除该箱
        src = next(x for x in cur if x.fid == src_fid)
        rest = {}
        for s2, bs in src.route:
            for b in bs:
                if b != bid:
                    rest.setdefault(s2, []).append(b)
        cur2 = [x for x in cur if x.fid != src.fid]
        if rest:
            r2 = [(s2, bs2) for s2, bs2 in rest.items()]
            nf2 = Flight(src.fid, r2, src.model, data)
            if nf2.is_feasible():
                cur2.append(nf2)
            else:
                # 剩余箱换最小能耗可行机型
                added = False
                for gm in ['A', 'B', 'C']:
                    nf3 = Flight(src.fid, r2, gm, data)
                    if nf3.is_feasible():
                        cur2.append(nf3); added = True; break
                if not added:
                    print('r%d: 剩余箱 %s 不可行' % (rnd + 1, [b for _, bs in rest.items() for b in bs]))
                    break
        cur2.append(nf)
        m2, s2, v2, nc2 = eval_full(data, cur2)
        if m2 is None or v2 > 0:
            print('r%d: 拆分后调度失败' % (rnd + 1)); break
        # 接受：紧时限违规数必须下降（且硬约束过）
        if nc2 >= nc and nc2 > 0:
            print('r%d: 拆 %s 无改善 (%d->%d)，回退' % (rnd + 1, bid, nc, nc2))
            cur = sorted([x for x in fls0], key=lambda x: x.fid) if False else cur
            # 回退：保持 cur 不变，试下一个违规箱（若还有）
            continue
        cur = cur2
        print('r%d: 拆 %s(超%.0f,紧限%.0f) -> %d架 mk %.1f en %.2f 违规%d' % (
            rnd + 1, bid, late, ddl, len(cur), m2['makespan'], m2['energy'], nc2), flush=True)
        hist.append((m2['makespan'], m2['energy'], m2['tardy_w']))
    m, s, v, nc = eval_full(data, cur)
    tb = tardy_boxes(data, s) if s else []
    print('\n最终: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 电池违规=%d / tardy=%.1f / 紧时限违规=%d' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, m['tardy_w'], nc))
    if m['tardy_w'] < m0['tardy_w'] - 1e-6:
        json.dump({'best': {k: vv for k, vv in m.items() if k != 'box_time'},
                   'traj': hist,
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in cur]},
                  open(os.path.join(OUTD, 'p2v34_timely.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v34_timely.json')


if __name__ == '__main__':
    main()