# -*- coding: utf-8 -*-
"""v25 P2 完工压缩：23 架解 → 更短完工。
策略（对方 23 架/5694 s 的启示：架次少+完工短的组合只能来自"多区合并+紧凑链"）：
  1) 多区合并：同机型、时间相邻的架次对，若可合并且经完整 dispatch 验证零迟到
     且完工下降 -> 接受（省起飞/返场/准备开销）
  2) 尾部转移：返场 > TAIL 的架次，货箱转移到同区更早架次（v19 算子）
  3) B->A 换型：B 机长链上的低载架次换 A 机（A 机 4 架冗余），压缩 B 链
接受准则：(makespan, energy) 字典序，硬性零迟到。
输出：最优解 JSON + 移动日志 + 与 26 架冠军、对方参考的对照。"""
import sys, os, json, time, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from common import Data, TimeBudget, make_initial, clone_flights, set_weights, summarize
from solvers import tabu_optimize
from p2_solve import dispatch, evaluate, normalize_flight, Flight

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
os.makedirs(OUTD, exist_ok=True)

TAIL = 6000.0


def eval_full(data, fl):
    schedule, _ = dispatch(data, fl)
    if schedule is None:
        return None, None
    met = evaluate(data, fl, schedule)
    return met, schedule


def rebuild_route(data, fl, fid, new_route, model=None):
    """按新 route 替换架次（重算全部状态）。"""
    for f in fl:
        if f.fid == fid:
            f.route = [(s, list(bs)) for s, bs in new_route]
            if model:
                f.model = model
            normalize_flight(f, data)
            return f
    return None


def load_or_search(data, budget_s=300.0, seed=13):
    """优先读诊断出的 23 架解 JSON；否则重跑 tabu。"""
    diag = os.path.join(OUTD, 'p2v25_diag.json')
    if os.path.exists(diag):
        return None  # 需要完整 Flight，诊断 JSON 只有快照 -> 走重搜
    return None


def load_23(data):
    """从诊断 JSON 重建 23 架解（route 含 box id）。"""
    diag = os.path.join(OUTD, 'p2v25_diag.json')
    if not os.path.exists(diag):
        return None
    d = json.load(open(diag, encoding='utf-8'))
    from p2_solve import Flight
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d['solution']]
    print('load 23 架解: %d flights (mk %.1f)' % (len(fls), d['makespan']), flush=True)
    return fls


def main():
    data = Data()
    fl0_ = load_23(data)
    if fl0_ is None:
        print('诊断 JSON 缺失，先重搜 23 架起点...', flush=True)
        p1 = json.load(open(os.path.join(HERE, '..', '结果', 'p1_results.json'), encoding='utf-8'))
        init = make_initial(data, p1['grouping'])
        set_weights(200.0, 0.1, 0.1, 5.0)
        fl0_, _met0 = tabu_optimize(data, clone_flights(init), TimeBudget(300), seed=13)
        if fl0_ is None:
            print('ERROR: 重搜失败', flush=True)
            return
    m0, s0 = eval_full(data, fl0_)
    print('起点: %d 架 / mk %.1f / %.2f kWh / 零迟到=%s' % (
        len(fl0_), m0['makespan'], m0['energy'], m0['hard_ok']), flush=True)

    # ---- 候选生成：多区合并 ----
    cur_fl = fl0_
    cur_met, cur_sched = m0, s0
    log = []
    for rnd in range(6):
        improved = False
        # 1) 合并候选：相同机型、route 不重叠、时间相邻（a.return 与 b.start 间隔 < 900s）
        cand_list = []
        fls = sorted(cur_fl, key=lambda f: cur_sched[f.fid]['return'])
        for i in range(len(fls)):
            for j in range(len(fls)):
                if i == j:
                    continue
                a, b = fls[i], fls[j]
                if a.model != b.model:
                    continue
                if any(s for s, _ in b.route if any(s == s2 for s2, _ in a.route)):
                    continue
                gap = cur_sched[b.fid]['start'] - cur_sched[a.fid]['return']
                if gap < 0 or gap > 900:
                    continue
                cand_list.append((a, b))
        for (a, b) in cand_list[:120]:
            merged = merge_two(data, cur_fl, a, b)
            if merged is None:
                continue
            m, s = eval_full(data, merged)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            better = (m['makespan'], m['energy']) < (cur_met['makespan'], cur_met['energy'])
            if better:
                log.append({'round': rnd + 1, 'op': 'merge', 'flights': (a.fid, b.fid),
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3),
                            'n': m['flights']})
                cur_fl, cur_met, cur_sched = merged, m, s
                improved = True
                break
        if improved:
            continue
        # 1b) C->A 换型：把返场最晚的 C 近区架次换 A 机（A 机 4 架并行吸收）
        c_fls = [f for f in cur_fl if f.model == 'C']
        c_fls.sort(key=lambda f: cur_sched[f.fid]['return'], reverse=True)
        for f in c_fls[:3]:
            cand = retype_c_to_a(data, cur_fl, f)
            if cand is None:
                continue
            m, s = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if (m['makespan'], m['energy']) < (cur_met['makespan'], cur_met['energy']):
                log.append({'round': rnd + 1, 'op': 'retype_CtoA', 'flight': f.fid,
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur_fl, cur_met, cur_sched = cand, m, s
                improved = True
                break
        if improved:
            continue
        # 1c) C 近区大载架次拆分转 A 机（S001 13 箱等：A 机多趟并行 0 点起飞）
        c_fls = [f for f in cur_fl if f.model == 'C' and len(f.route) == 1]
        c_fls.sort(key=lambda f: cur_sched[f.fid]['return'], reverse=True)
        for f in c_fls[:4]:
            cand = split_c_to_a(data, cur_fl, f)
            if cand is None:
                continue
            m, s = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if (m['makespan'], m['energy']) < (cur_met['makespan'], cur_met['energy']):
                log.append({'round': rnd + 1, 'op': 'split_CtoA', 'flight': f.fid, 'n_after': m['flights'],
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur_fl, cur_met, cur_sched = cand, m, s
                improved = True
                break
        if improved:
            continue
        # 2) 尾部转移
        tail_fids = [fid for fid, sch in cur_sched.items() if sch['return'] > TAIL]
        done = False
        for f in cur_fl:
            if f.fid not in tail_fids:
                continue
            for sid, bs in f.route:
                for g in cur_fl:
                    if g.fid == f.fid or any(s == sid for s, _ in g.route):
                        continue
                    for b in list(bs):
                        cand = transfer_box(data, cur_fl, f, g, sid, b)
                        if cand is None:
                            continue
                        m, s = eval_full(data, cand)
                        if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                            continue
                        if (m['makespan'], m['energy']) < (cur_met['makespan'], cur_met['energy']):
                            log.append({'round': rnd + 1, 'op': 'transfer', 'box': b,
                                        'from': f.fid, 'to': g.fid,
                                        'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                            cur_fl, cur_met, cur_sched = cand, m, s
                            improved = True
                            done = True
                            break
                    if done:
                        break
                if done:
                    break
            if done:
                break
        print('round %d: mk=%.1f en=%.2f n=%d improved=%s' % (
            rnd + 1, cur_met['makespan'], cur_met['energy'], cur_met['flights'], improved), flush=True)
        if not improved:
            break

    print('\n结果: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / 零迟到' % (
        cur_met['flights'], cur_met['makespan'], cur_met['makespan'] / 60, cur_met['energy']))
    print('对照: 对方 23 架 / 5694 s (94.9 min) / 67.14 kWh；26 架冠军 6959.8 s / 70.71 kWh')
    # 导出最终解结构 + 链分析
    sch_final, _ = dispatch(data, cur_fl)
    fl_rows = []
    for f in sorted(cur_fl, key=lambda x: sch_final[x.fid]['return']):
        s = sch_final[f.fid]
        fl_rows.append({'fid': f.fid, 'uav': s['uav'], 'model': f.model,
                        'route': [(sid, list(bs)) for sid, bs in f.route],
                        'start': round(s['start'], 1), 'return': round(s['return'], 1),
                        'energy': round(f.energy(), 3)})
    chains = {}
    for r in fl_rows:
        chains.setdefault(r['uav'], []).append(r)
    print('\n== 最终解每机链 ==')
    for uid in sorted(chains):
        ch = chains[uid]
        last = max(c['return'] for c in ch)
        print('  %s (%s): %d 架次, 最后返场 %7.0f s' % (uid, ch[0]['model'], len(ch), last))
        for c in ch:
            print('      f%-3d %s %-14s [%6.0f -> %6.0f] %.2f kWh' % (
                c['fid'], c['model'], str(c['route']), c['start'], c['return'], c['energy']))
    json.dump({'best': summarize(cur_met), 'moves_log': log, 'solution': [
        {'fid': f.fid, 'model': f.model, 'route': [(s, list(bs)) for s, bs in f.route]}
        for f in cur_fl]},
        open(os.path.join(OUTD, 'p2v25_compress.json'), 'w', encoding='utf-8'),
        ensure_ascii=False, indent=1)
    print('\nsaved -> 结果/进化_v25/p2v25_compress.json（含 solution）')


def merge_two(data, fl, a, b):
    """合并架次 a、b（同机型、route 无重叠）：b 的 route 追加到 a，移除 b。"""
    fl = clone_flights(fl)
    fa = rebuild_route(data, fl, a.fid, a.route + b.route)
    if fa is None:
        return None
    if not fa.is_feasible():
        return None
    fl = [f for f in fl if f.fid != b.fid]
    return fl


def transfer_box(data, fl, f, g, sid, bid):
    """把 f 的箱 bid（区 sid）转移到 g。"""
    fl = clone_flights(fl)
    def find(fid):
        for x in fl:
            if x.fid == fid:
                return x
        return None
    fa, gb = find(f.fid), find(g.fid)
    if fa is None or gb is None:
        return None
    found = False
    for i, (s, bs) in enumerate(fa.route):
        if s == sid and bid in bs:
            bs.remove(bid)
            found = True
            if not bs:
                del fa.route[i]
            break
    if not found:
        return None
    normalize_flight(fa, data)
    if not fa.route:                       # 源架次已被转空 -> 删除该架次
        fl = [x for x in fl if x.fid != fa.fid]
        return fl
    for i, (s, bs) in enumerate(gb.route):
        if s == sid:
            bs.append(bid)
            gb.route[i] = (s, bs)
            break
    else:
        gb.route.append((sid, [bid]))
    normalize_flight(gb, data)
    if not (fa.is_feasible() and gb.is_feasible()):
        return None
    return fl


def retype_c_to_a(data, fl, f):
    """把近区 C 架次改为 A 机（A 机 4 架并行、0 点起飞吸收轻载）。
    仅当质量/体积/能耗在 A 上限内且可行。"""
    if f.model != 'C':
        return None
    fl = clone_flights(fl)
    fa = rebuild_route(data, fl, f.fid, f.route, model='A')
    if fa is None or not fa.is_feasible():
        return None
    return fl


def split_c_to_a(data, fl, f, boxes_per=None):
    """把 C 架次按质量拆分转给 A 机：每趟 A 机 <= A.Q(25kg) 且可行。
    返回新架次列表（原 f 被替换为若干 A 机架次），超容量返回 None。"""
    if f.model != 'C' or len(f.route) != 1:
        return None
    sid, bs = f.route[0]
    aq = data.uav_types['A']['Q']
    total = sum(data.boxes[b]['mass'] for b in bs)
    if total > aq * 4:          # 4 架 A 机也是上限
        return None
    # 装箱：质量贪心累积，每趟 <= aq
    fl = clone_flights(fl)
    batches = []
    cur, cur_m = [], 0.0
    for b in sorted(bs, key=lambda x: -data.boxes[x]['mass']):
        m = data.boxes[b]['mass']
        if cur_m + m <= aq + 1e-9:
            cur.append(b)
            cur_m += m
        else:
            if cur:
                batches.append(cur)
            cur, cur_m = [b], m
    if cur:
        batches.append(cur)
    if len(batches) < 2:        # 单趟就能装下就不用拆
        return None
    new_fls = []
    fid = max(f.fid for f in fl if f.fid is not None) + 1
    for k, bt in enumerate(batches):
        nf = Flight(fid + k, [(sid, list(bt))], 'A', data)
        if not nf.is_feasible():
            return None
        new_fls.append(nf)
    return [x for x in fl if x.fid != f.fid] + new_fls


if __name__ == '__main__':
    main()