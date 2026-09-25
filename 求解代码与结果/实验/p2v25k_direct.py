# -*- coding: utf-8 -*-
"""v25k 定向结构优化（从 24 架/7889.9/77.41 出发）：
  M1: S007 6kg 从 f3([S003,S007]) 并入 f18(S002) -> C 机 7->6 趟（f3 变单区 S003）
  M2: f5(S009 22kg B) 并入 f23([S005,S008] C) -> [S005,S008,S009] 70kg，B 机 7->6 趟
目标：22-23 架 / 完工 <7400 / 能耗 <77，严格口径。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

d = json.load(open(os.path.join(OUTD, 'p2v25j_dual.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in d['solution']]


def eval_full(data, fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None, None
    return evaluate(data, fl, sch), sch


def move_box(data, fl, src_fid, sid, bid, tgt_fid, tgt_sid=None):
    """把 bid（源 src_fid 的 sid 条目）移到 tgt_fid 的 tgt_sid 条目（默认真实区）。"""
    fl = clone_flights(fl)
    src = next(x for x in fl if x.fid == src_fid)
    tgt = next(x for x in fl if x.fid == tgt_fid)
    real = bid.split('-')[0]
    tgt_sid = tgt_sid or real
    for i, (s2, bs2) in enumerate(src.route):
        if s2 == sid and bid in bs2:
            bs2.remove(bid)
            if not bs2:
                del src.route[i]
            break
    else:
        return None
    normalize_flight(src, data)
    if not src.route:
        fl = [x for x in fl if x.fid != src.fid]
    elif not src.is_feasible():
        return None
    for i, (s2, bs2) in enumerate(tgt.route):
        if s2 == tgt_sid:
            bs2.append(bid)
            tgt.route[i] = (s2, bs2)
            break
    else:
        tgt.route.append((tgt_sid, [bid]))
    normalize_flight(tgt, data)
    if not tgt.is_feasible():
        return None
    return fl


def main():
    m0, s0 = eval_full(data, fls)
    print('起点: %d 架 / mk %.1f / %.2f kWh' % (len(fls), m0['makespan'], m0['energy']), flush=True)
    cur, cur_met, cur_sch = fls, m0, s0
    log = []
    # 找目标架次
    f3 = next(x for x in cur if x.fid == 3)
    f18 = next((x for x in cur if x.fid == 18), None)
    f23 = next((x for x in cur if x.fid == 23), None)
    f5 = next((x for x in cur if x.fid == 5), None)
    print('f3 route=%s' % [(s, bs) for s, bs in f3.route])
    # M1: S007 箱从 f3 转 f18
    s007_boxes = [b for s, bs in f3.route if s == 'S007' for b in bs]
    for b in s007_boxes:
        cand = move_box(data, cur, 3, 'S007', b, 18, 'S007')
        if cand is None:
            print('M1 失败: %s 转移不可行' % b, flush=True)
            continue
        m, s = eval_full(data, cand)
        if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
            print('M1 失败: %s 硬约束不满足 mk=%.1f' % (b, m['makespan'] if m else -1), flush=True)
            continue
        log.append({'op': 'M1', 'box': b, 'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
        cur, cur_met, cur_sch = cand, m, s
        print('M1 ok: %d 架 / mk %.1f / %.2f kWh' % (len(cur), m['makespan'], m['energy']), flush=True)
        break
    # M2: S009 箱从 f5 转 f23（并入 C [S005,S008]）
    f5 = next((x for x in cur if x.fid == 5), None)
    f23 = next((x for x in cur if x.fid == 23), None)
    if f5 is not None and f23 is not None:
        s009_boxes = [b for s, bs in f5.route if s == 'S009' for b in bs]
        for b in s009_boxes:
            cand = move_box(data, cur, 5, 'S009', b, 23, 'S009')
            if cand is None:
                print('M2 失败: %s 不可行' % b, flush=True)
                continue
            m, s = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                print('M2 失败: %s 硬约束不满足' % b, flush=True)
                continue
            log.append({'op': 'M2', 'box': b, 'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
            cur, cur_met, cur_sch = cand, m, s
            print('M2 ok: %d 架 / mk %.1f / %.2f kWh' % (len(cur), m['makespan'], m['energy']), flush=True)
            break
    # 完工压缩：同机合并（完工降）
    for rnd in range(6):
        improved = False
        fls_sorted = sorted(cur, key=lambda f: cur_sch[f.fid]['return'])
        for i in range(len(fls_sorted)):
            for j in range(len(fls_sorted)):
                if i == j:
                    continue
                a, b = fls_sorted[i], fls_sorted[j]
                if a.model != b.model or set(s for s, _ in a.route) & set(s for s, _ in b.route):
                    continue
                gap = cur_sch[b.fid]['start'] - cur_sch[a.fid]['return']
                if not (0 <= gap <= 1500):
                    continue
                fl = clone_flights(cur)
                fa = next(x for x in fl if x.fid == a.fid)
                fb = next(x for x in fl if x.fid == b.fid)
                fa.route = [(s, list(bs)) for s, bs in a.route] + [(s, list(bs)) for s, bs in b.route]
                normalize_flight(fa, data)
                if not fa.is_feasible():
                    continue
                fl = [x for x in fl if x.fid != b.fid]
                m, s = eval_full(data, fl)
                if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                    continue
                if m['makespan'] < cur_met['makespan'] - 1e-6 and m['energy'] <= cur_met['energy'] + 0.3:
                    log.append({'round': rnd + 1, 'op': 'merge', 'flights': (a.fid, b.fid),
                                'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                    cur, cur_met, cur_sch = fl, m, s
                    improved = True
                    break
            if improved:
                break
        print('round %d: mk=%.1f en=%.2f n=%d improved=%s' % (
            rnd + 1, cur_met['makespan'], cur_met['energy'], cur_met['flights'], improved), flush=True)
        if not improved:
            break
    print('\n结果: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard %s' % (
        cur_met['flights'], cur_met['makespan'], cur_met['makespan'] / 60,
        cur_met['energy'], cur_met['hard_ok']))
    json.dump({'best': {k: v for k, v in cur_met.items() if k != 'box_time'}, 'moves_log': log,
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v25k_direct.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p2v25k_direct.json')


if __name__ == '__main__':
    main()