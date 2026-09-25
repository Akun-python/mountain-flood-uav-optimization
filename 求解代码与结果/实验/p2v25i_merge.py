# -*- coding: utf-8 -*-
"""v25i 严格口径大合并+升舱搜索：目标 完工 6000-7000s 且能耗 60-70 kWh。
当前 28 架解（12A+8B+8C）能耗 83.12 的根源=架次数多（prep 多）。
策略：
  1) C 吸收：非 C 单区轻载架次（<=40kg）并入 C 机相邻架次（总质量 <=80kg）
  2) C 内部合并：C 单区架次对合并（<=80kg）
  3) B 内部/升舱：B 1 箱级轻载并入 B 多区架次或 C
接受准则（双目标有界）：
  能量下降且完工 <= max(7000, 当前完工-1)，或 完工下降且能耗 <= 当前+0.5；
  必须 hard True + 零迟到 + 区一致。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

d = json.load(open(os.path.join(OUTD, 'p2v25b_compress26.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in d['solution']]


def eval_full(data, fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None, None
    return evaluate(data, fl, sch), sch


def merge_into(data, fl, src_f, tgt_f):
    """把 src 的 route 并入 tgt（同机型或 tgt 容量足够），删除 src。返回新 fl 或 None。"""
    fl = clone_flights(fl)
    src = next(x for x in fl if x.fid == src_f.fid)
    tgt = next(x for x in fl if x.fid == tgt_f.fid)
    q = data.uav_types[tgt.model]['Q']
    if src.total_mass + tgt.total_mass > q + 1e-9:
        return None
    merged_route = [(s, list(bs)) for s, bs in tgt.route] + [(s, list(bs)) for s, bs in src.route]
    # 若同区条目合并
    seen = {}
    route = []
    for s, bs in merged_route:
        if s in seen:
            for b in bs:
                seen[s].append(b)
        else:
            seen[s] = list(bs)
            route.append((s, seen[s]))
    tgt.route = route
    normalize_flight(tgt, data)
    if not tgt.is_feasible():
        return None
    return [x for x in fl if x.fid != src.fid]


def main():
    m0, s0 = eval_full(data, fls)
    print('起点: %d 架 / mk %.1f / %.2f kWh' % (len(fls), m0['makespan'], m0['energy']), flush=True)
    cur, cur_met, cur_sch = fls, m0, s0
    log = []
    for rnd in range(30):
        improved = False
        # 候选合并：质量互补（总质量 <= 机型 Q），优先轻载被大载吸收
        singles = [f for f in cur if len(f.route) == 1]
        cands = []
        for i in range(len(singles)):
            for j in range(len(singles)):
                if i == j:
                    continue
                a, b = singles[i], singles[j]
                if a.model == 'C' and b.model != 'C' and b.total_mass <= 40:
                    cands.append((b, a, 'Cabsorb'))
                elif a.model == 'C' and b.model == 'C' and a.total_mass <= 40 and b.total_mass <= 40:
                    cands.append((b, a, 'Cmerge'))
                elif a.model == 'B' and b.model == 'B' and a.total_mass <= 12 and b.total_mass <= 12:
                    cands.append((b, a, 'Bmerge'))
        # 按源架次返场排序（优先处理尾部）
        def ret(f):
            return cur_sch.get(f.fid, {}).get('return', 1e9) if hasattr(f, 'fid') else 1e9
        cands.sort(key=lambda c: -ret(c[0]))
        for (src, tgt, kind) in cands[:200]:
            cand = merge_into(data, cur, src, tgt)
            if cand is None:
                continue
            m, s = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            better = (m['energy'] < cur_met['energy'] - 1e-6 and m['makespan'] <= cur_met['makespan'] + 250.0) \
                or (m['makespan'] < cur_met['makespan'] - 1e-6 and m['energy'] <= cur_met['energy'] + 0.5)
            if better:
                log.append({'round': rnd + 1, 'op': kind, 'src': src.fid, 'tgt': tgt.fid,
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur, cur_met, cur_sch = cand, m, s
                improved = True
                break
        print('round %d: mk=%.1f en=%.2f n=%d improved=%s' % (
            rnd + 1, cur_met['makespan'], cur_met['energy'], cur_met['flights'], improved), flush=True)
        if not improved:
            break
    print('\n结果: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard %s' % (
        cur_met['flights'], cur_met['makespan'], cur_met['makespan'] / 60,
        cur_met['energy'], cur_met['hard_ok']))
    sch, _ = dispatch(data, cur)
    chains = {}
    for f in cur:
        chains.setdefault(sch[f.fid]['uav'], []).append((f, sch[f.fid]))
    for uid in sorted(chains):
        ch = chains[uid]
        last = max(c['return'] for _, c in ch)
        print('  %s (%s): %d 架次, 最后返场 %7.0f' % (uid, ch[0][0].model, len(ch), last))
    json.dump({'best': {k: v for k, v in cur_met.items() if k != 'box_time'}, 'moves_log': log,
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v25i_merge.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p2v25i_merge.json')


if __name__ == '__main__':
    main()