# -*- coding: utf-8 -*-
"""v31 从 P1 满载组批出发的最小紧急拆分（朝 23架/94min/66kWh 的正确结构）。
P1 满载 18 趟能耗仅 59.02 kWh 但 3 箱硬时限违规（S014-MED/WAT deadline3600、S003-WAT deadline7200）。
策略：从满载趟中把违规紧急箱拆出为独立早飞趟（A/B 机最小能耗），迭代至零违规。
硬约束：首批/医疗 deadline、返航余量、电池周转(dispatch_compliant)、区一致。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, evaluate, normalize_flight
from p2v28_compliant import dispatch_compliant, check_battery

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()


def hard_violations(data, sch):
    bad = []
    for fid, s in sch.items():
        for sid, bid, t in s['deliveries']:
            bx = data.boxes[bid]
            if bx['first_batch'] and t > bx['deadline_first'] + 1e-6:
                bad.append((bid, t, bx['deadline_first'], fid))
            elif bx['type'] == '医疗物资' and t > bx['deadline_exp'] + 1e-6:
                bad.append((bid, t, bx['deadline_exp'], fid))
    return bad


def eval_full(data, fl):
    sch, _ = dispatch_compliant(data, fl)
    if sch is None:
        return None, None, 999
    viol = check_battery(data, sch, fl)
    m = evaluate(data, fl, sch)
    return m, sch, len(viol)


def remove_box(fl, src_fid, bid):
    """从 src 架次移除 bid；若该架次空了则删除。"""
    fl = [x for x in fl if x.fid != src_fid]
    return fl


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
    n0 = len(fls)
    m0, s0, v0 = eval_full(data, fls)
    print('起点 P1 满载: %d 架 / mk %.1f / %.2f kWh / 硬违规箱=%d' % (
        n0, m0['makespan'], m0['energy'], len(hard_violations(data, s0))))
    cur = fls
    for rnd in range(20):
        m, s, v = eval_full(data, cur)
        if m is None or v > 0:
            print('round %d: 调度失败/电池违规 %d' % (rnd + 1, v))
            break
        bad = hard_violations(data, s)
        if not bad:
            print('round %d: 零硬违规达成' % (rnd + 1))
            break
        # 拆出违规箱中 deadline 最紧的（批次/医疗）
        bad.sort(key=lambda b: b[2])
        bid, t, ddl, src_fid = bad[0]
        sid = bid.split('-')[0]
        # 找该箱所在架次（用 sch deliveries 找 src）
        src = next(x for x in cur if x.fid == src_fid)
        # 该架次剩余箱（去掉该箱）
        rest = []
        for s2, bs in src.route:
            for b in bs:
                if b != bid:
                    rest.append((s2, b))
        # 新架次尝试 A/B/C 最小能耗可行性（单箱原区）
        nf = None
        for gm in ['A', 'B', 'C']:
            candf = Flight(max(x.fid for x in cur) + 1, [(sid, [bid])], gm, data)
            if candf.is_feasible():
                nf = candf
                break
        if nf is None:
            print('round %d: %s 无法拆分任何机型' % (rnd + 1, bid))
            break
        # 重建：删旧趟（若空）或更新旧趟（若剩箱）
        cur2 = [x for x in cur if x.fid != src.fid]
        if rest:
            # rest 多元组合并为含区列表
            rmap = {}
            for s2, b in rest:
                rmap.setdefault(s2, []).append(b)
            r2 = [(s2, bs2) for s2, bs2 in rmap.items()]
            r2.sort(key=lambda x: flight_critical_dl(x[0], x[1]))
            newf = Flight(src.fid, r2, src.model, data)
            if newf.is_feasible():
                cur2.append(newf)
            else:
                # 改 C 机照旧（保留原区单区？此处简单重试同模型满箱外的拆分）
                cur2.append(src)  # 保持原趟原样（本箱已拆出则重量轻了仍可行）
        cur2.append(nf)
        cur = cur2
        m2, s2, v2 = eval_full(data, cur)
        print('round %d: 拆 %s (ddl %.0f, 超 %.0f) -> %d 架 / mk %.1f / %.2f kWh / 剩余硬违规 %d' % (
            rnd + 1, bid, ddl, t - ddl, len(cur),
            m2['makespan'] if m2 else -1, m2['energy'] if m2 else -1,
            len(hard_violations(data, s2)) if s2 else -1), flush=True)
    m, s, v = eval_full(data, cur)
    bad = hard_violations(data, s) if s else []
    print('\n最终: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard=%s / 电池违规=%s / 硬违规=%d / 迟到 %.2f' % (
        len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], v, len(bad),
        m['tardy_w']))


def flight_critical_dl(sid, bs):
    return min(min(min(data.boxes[b]['deadline_first'], data.boxes[b]['deadline_exp'])
                   for b in bs), 1e9)


if __name__ == '__main__':
    main()