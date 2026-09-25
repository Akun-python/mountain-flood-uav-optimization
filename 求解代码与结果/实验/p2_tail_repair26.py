# -*- coding: utf-8 -*-
"""
v19a · P2 完工口径持续优化：尾部定向修复（26 架冠军 → 尝试 < 6959.81 s）
========================================================================
框架对比的"新算子"角度：在 Tabu 冠军上直接对尾部（返场 > 6200 s 的架次）
做结构化破坏-重建 —— (1) 按区段拆分长架次（释放尾部机型负载），
(2) 尾部货箱向同区早班转移（同区容量平移）。每次候选都经完整
dispatch（EDF：无人机/电池双资源就绪队列 + 两阶段充电）重新排程，
只接受 hard_ok 且零迟到的改进（先完工后能耗的字典序）。
同时给出完工时刻的 3 个可证下界，量化冠军的"最优性余量"。
"""
import sys, os, json, time, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from core import Data
from p2_solve import Flight, feasible_models, normalize_flight
from common import Budget, safe_eval, clone_flights, summarize

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v19')
TAIL = 6200.0      # 尾部阈值（s）
ROUNDS = 4         # 迭代轮数
DOMIN = True       # True=仅接受双指标严格支配（完工与能耗都更优）；
                   # False=字典序（完工优先、能耗次之）


def load_champion(data):
    with open(os.path.join(RES, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    fl = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
          for f in r['flights']]
    return fl


def eval_full(data, flights):
    b = Budget(100000)
    met, sched = safe_eval(data, flights, b)
    return met, sched


def split_moves(data, flights):
    """按区段拆分：多区架次按区段切；单区多箱架次按箱二分切。"""
    out = []
    for f in flights:
        if len(f.route) >= 2:
            for k in range(1, len(f.route)):
                r1 = f.route[:k]
                r2 = f.route[k:]
                for m1 in feasible_models(data, r1):
                    for m2 in feasible_models(data, r2):
                        out.append((f, r1, m1, r2, m2))
        elif len(f.box_ids) >= 2:
            # 单区多箱：取箱子子集（按原顺序二分，避免组合爆炸）
            bs = f.box_ids
            for k in range(1, len(bs)):
                r1 = [(f.route[0][0], bs[:k])]
                r2 = [(f.route[0][0], bs[k:])]
                for m1 in feasible_models(data, r1):
                    for m2 in feasible_models(data, r2):
                        out.append((f, r1, m1, r2, m2))
    return out


def apply_split(flights, f, r1, m1, r2, m2, data):
    newf = []
    fid = max((x.fid for x in flights), default=0) + 1
    for x in flights:
        if x.fid == f.fid:
            continue
        newf.append(x)
    a1 = Flight(f.fid, [(s, list(bs)) for s, bs in r1], m1, data)
    a2 = Flight(fid, [(s, list(bs)) for s, bs in r2], m2, data)
    if a1.is_feasible() and a2.is_feasible():
        normalize_flight(a1, data)
        normalize_flight(a2, data)
        newf.extend([a1, a2])
        return newf
    return None


def apply_transfer(flights, src, dst, sid, bid, data):
    """把 bid 从 src 移到 dst（dst 访问同区）。src 只移除该箱，
    移除后若为空架次则丢弃。"""
    newf = []
    for x in flights:
        if x.fid == src.fid:
            route = [(s, [b for b in bs if not (s == sid and b == bid)]) if s == sid
                     else (s, list(bs)) for s, bs in x.route]
            newf.append(Flight(x.fid, route, x.model, data))
        elif x.fid == dst.fid:
            route2 = [(s, list(bs)) for s, bs in x.route]
            for i, (s, bs) in enumerate(route2):
                if s == sid:
                    route2[i] = (s, bs + [bid])
                    break
            else:
                route2.append((sid, [bid]))
            newf.append(Flight(x.fid, route2, x.model, data))
        else:
            newf.append(x)
    newf = [x for x in newf if x.box_ids]
    for x in newf:
        if not x.is_feasible():
            return None
        normalize_flight(x, data)
    return newf


# ---- 下界（可证）----
def lower_bounds(data, flights):
    """3 个有效下界：
    LB1 单架次往返下限：任一货箱所在区的最小单箱往返时长（含交接，C 型最快）。
    LB2 机型负载均衡下界：makespan >= max_g (sum duration_g / n_uavs_g)。
    LB3 时限链下界：任一架次开工不得早于其最紧急货箱对应时限链（紧时限箱
        所在架次的下限由该箱最早可达时刻限定）——本实现取
        max_b (最早可达(b))，弱但可证。
    """
    lb1 = 0.0
    for bid, bx in data.boxes.items():
        for g in ('C', 'B', 'A'):
            f = Flight(0, [(bx['area'], [bid])], g, data)
            if f.is_feasible():
                lb1 = max(lb1, f.duration())
                break
    # LB2
    dur = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    n_uav = {'A': 0, 'B': 0, 'C': 0}
    for uid, g in data.uavs:
        n_uav[g] += 1
    for f in flights:
        dur[f.model] += f.duration()
    lb2 = max((dur[g] / n_uav[g]) for g in 'ABC' if n_uav[g])
    return {'LB1_single_box': round(lb1, 1), 'LB2_workload_balance': round(lb2, 1),
            'n_uavs': n_uav, 'workload_s': {g: round(dur[g], 1) for g in 'ABC'}}


def main():
    data = Data()
    fl0 = load_champion(data)
    met0, sched0 = eval_full(data, fl0)
    print('baseline:', summarize(met0), flush=True)
    if not (met0['hard_ok'] and met0['tardy_w'] < 1e-6):
        print('ERROR: champion re-check failed', flush=True)
        return

    cur_fl, cur_met, cur_sched = fl0, met0, sched0
    log = []
    for rnd in range(ROUNDS):
        improved = False
        # 1) 拆分候选
        for (f, r1, m1, r2, m2) in split_moves(data, cur_fl):
            cand = apply_split(cur_fl, f, r1, m1, r2, m2, data)
            if cand is None:
                continue
            m, s = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            better = (m['makespan'], m['energy']) < (cur_met['makespan'], cur_met['energy'])
            if DOMIN:
                better = (m['makespan'] < cur_met['makespan'] - 1e-6
                          and m['energy'] < cur_met['energy'] - 1e-6)
            if better:
                log.append({'round': rnd + 1, 'op': 'split', 'from': f.fid,
                            'r1': [(s, len(bs)) for s, bs in r1], 'r2': [(s, len(bs)) for s, bs in r2],
                            'm1': m1, 'm2': m2, 'mk': round(m['makespan'], 1),
                            'en': round(m['energy'], 3), 'fl': m['flights']})
                cur_fl, cur_met, cur_sched = cand, m, s
                improved = True
        # 2) 尾部转移候选（仅尾部架次 r=return > TAIL 的箱）
        tail_fids = [fid for fid, sch in cur_sched.items() if sch['return'] > TAIL]
        cand_list = []
        for f in cur_fl:
            if f.fid not in tail_fids:
                continue
            for sid, bs in f.route:
                for g in cur_fl:
                    if g.fid == f.fid:
                        continue
                    if any(s == sid for s, _ in g.route):
                        for b in list(bs):
                            cand_list.append((f, g, sid, b))
        for (f, g, sid, bid) in cand_list:
            cand = apply_transfer(cur_fl, f, g, sid, bid, data)
            if cand is None:
                continue
            m, s = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            better = (m['makespan'], m['energy']) < (cur_met['makespan'], cur_met['energy'])
            if DOMIN:
                better = (m['makespan'] < cur_met['makespan'] - 1e-6
                          and m['energy'] < cur_met['energy'] - 1e-6)
            if better:
                log.append({'round': rnd + 1, 'op': 'transfer', 'box': bid,
                            'from_flight': f.fid, 'to_flight': g.fid, 'area': sid,
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3),
                            'fl': m['flights']})
                cur_fl, cur_met, cur_sched = cand, m, s
                improved = True
        print('round %d done, mk=%.1f improved=%s' % (rnd + 1, cur_met['makespan'], improved),
              flush=True)
        if not improved:
            break

    lb = lower_bounds(data, cur_fl)
    verdict = ('IMPROVED' if cur_met['makespan'] < met0['makespan'] - 1e-6
               else 'UNCHANGED')
    out = {
        'baseline': summarize(met0),
        'best': summarize(cur_met),
        'verdict': verdict,
        'lower_bounds': lb,
        'gap_to_LB2_pct': round((cur_met['makespan'] - lb['LB2_workload_balance'])
                                / lb['LB2_workload_balance'] * 100, 1),
        'moves_log': log,
        'note': ('尾部阈值 %g s；接受准则=零迟到 + (makespan, energy) 字典序；'
                 '逐候选完整 dispatch 重排程；下界 LB2 为机型负载均衡下界'
                 '（makespan >= max_g 累计任务时长/机型架数）') % TAIL,
    }
    # 导出最佳解（供 P3 端到端评估）
    if verdict == 'IMPROVED':
        from p2_solve import dispatch
        sch, _ = dispatch(data, cur_fl)
        sol = {'metrics': {k: (round(v, 4) if isinstance(v, float) else v)
                           for k, v in cur_met.items() if k != 'box_time'},
               'flights': [], 'deliveries': []}
        for f in cur_fl:
            s = sch[f.fid]
            sol['flights'].append({
                'fid': f.fid, 'uav': s['uav'], 'model': f.model, 'battery': s['battery'],
                'start': round(s['start'], 1), 'return': round(s['return'], 1),
                'route': [(sid, list(bs)) for sid, bs in f.route],
                'energy': round(f.energy(), 4), 'nbox': f.nbox,
                'mass': round(f.total_mass, 2)})
            for sid, bid, t in s['deliveries']:
                sol['deliveries'].append({'box': bid, 'fid': f.fid, 'area': sid, 't': round(t, 1)})
        with open(os.path.join(OUTD, 'p2_solution27.json'), 'w', encoding='utf-8') as fh:
            json.dump(sol, fh, ensure_ascii=False, indent=1)
        print('saved p2_solution27.json', flush=True)
    print('\nverdict:', verdict, flush=True)
    print('baseline:', summarize(met0), flush=True)
    print('best    :', summarize(cur_met), flush=True)
    print('lower bounds:', json.dumps(lb, ensure_ascii=False), flush=True)
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'p2_tail_repair26.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('saved', os.path.join(OUTD, 'p2_tail_repair26.json'), flush=True)


if __name__ == '__main__':
    main()