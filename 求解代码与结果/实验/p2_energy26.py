# -*- coding: utf-8 -*-
"""
v20a · P2 能耗最小化（完工 ≤ 6960 s 约束，26 架不变）
=====================================================
目标：在保持"26 架 / 零迟到 / 硬约束 / 完工 ≤ 冠军 6960 s"的前提下降低
运输能耗（当前 70.71 kWh）。算子：**(a) 同区货箱转移（跨架次重排，架次数
不变）**、**(b) 机型换型（A/B/C 可行机型互换）**。接受准则：能耗下降且
重排程后完工 ≤ 6960 s 且零迟到（hard_ok）。逐候选完整 dispatch 验证。
若找到能耗更低的 26 架解，则 P3 联合口径（完工 7260 / 中继 3.417）不变、
端到端能耗下降，是可采纳的真实改进。
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from core import Data
from p2_solve import Flight, normalize_flight
from common import Budget, safe_eval, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v20')
MK_CAP = 6960.0      # 完工上限（冠军 6959.81 s 取整）
ROUNDS = 6


def load_champion(data):
    with open(os.path.join(RES, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in r['flights']]


def eval_full(data, flights):
    b = Budget(100000)
    met, sched = safe_eval(data, flights, b)
    return met, sched


def transfer_candidates(flights):
    """同区货箱转移候选：(src, dst, sid, bid)。"""
    out = []
    areas = {}
    for f in flights:
        for sid, bs in f.route:
            areas.setdefault(sid, []).append(f)
    for f in flights:
        for sid, bs in f.route:
            for g in areas.get(sid, []):
                if g.fid == f.fid:
                    continue
                for b in bs:
                    out.append((f, g, sid, b))
    return out


def apply_transfer(flights, src, dst, sid, bid, data):
    newf = []
    for x in flights:
        if x.fid == src.fid:
            route = [(s, [bb for bb in bs if not (s == sid and bb == bid)]) if s == sid
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


def model_swaps(flights):
    """机型换型候选：(f, model)。"""
    out = []
    for f in flights:
        for g in ('A', 'B', 'C'):
            if g == f.model:
                continue
            out.append((f, g))
    return out


def apply_model(flights, f, g, data):
    newf = []
    for x in flights:
        if x.fid == f.fid:
            nf = Flight(x.fid, [(s, list(bs)) for s, bs in x.route], g, data)
            if not nf.is_feasible():
                return None
            newf.append(nf)
        else:
            newf.append(x)
    return newf


def main():
    data = Data()
    fl0 = load_champion(data)
    met0, _ = eval_full(data, fl0)
    print('baseline:', {k: (round(float(v), 3) if isinstance(v, float) else v)
                        for k, v in met0.items() if k != 'box_time'}, flush=True)
    cur_fl, cur_met = fl0, met0
    log = []
    for rnd in range(ROUNDS):
        improved = False
        # 1) 转移
        for (src, dst, sid, bid) in transfer_candidates(cur_fl):
            cand = apply_transfer(cur_fl, src, dst, sid, bid, data)
            if cand is None:
                continue
            m, _ = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if m['flights'] != 26 or m['makespan'] > MK_CAP + 1e-6:
                continue
            if m['energy'] < cur_met['energy'] - 1e-6:
                log.append({'round': rnd + 1, 'op': 'transfer', 'box': bid,
                            'from': src.fid, 'to': dst.fid, 'area': sid,
                            'mk': round(float(m['makespan']), 2),
                            'en': round(float(m['energy']), 4)})
                cur_fl, cur_met = cand, m
                improved = True
        # 2) 机型换型
        for (f, g) in model_swaps(cur_fl):
            cand = apply_model(cur_fl, f, g, data)
            if cand is None:
                continue
            m, _ = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if m['flights'] != 26 or m['makespan'] > MK_CAP + 1e-6:
                continue
            if m['energy'] < cur_met['energy'] - 1e-6:
                log.append({'round': rnd + 1, 'op': 'model', 'from': f.fid,
                            'model': f.model + '->' + g,
                            'mk': round(float(m['makespan']), 2),
                            'en': round(float(m['energy']), 4)})
                cur_fl, cur_met = cand, m
                improved = True
        print('round %d done en=%.4f improved=%s' % (rnd + 1, cur_met['energy'], improved), flush=True)
        if not improved:
            break
    verdict = ('IMPROVED' if cur_met['energy'] < met0['energy'] - 1e-6
               else 'UNCHANGED')
    out = {
        'baseline': {k: (round(float(v), 3) if isinstance(v, float) else v)
                     for k, v in met0.items() if k != 'box_time'},
        'best': {k: (round(float(v), 3) if isinstance(v, float) else v)
                 for k, v in cur_met.items() if k != 'box_time'},
        'verdict': verdict,
        'mk_cap': MK_CAP,
        'moves_log': log,
        'note': '26 架不变；接受=能耗下降 ∧ 完工≤%g ∧ 零迟到；逐候选完整 dispatch 重排程' % MK_CAP,
    }
    print('\nverdict:', verdict, flush=True)
    print('baseline en=%.4f mk=%.2f' % (met0['energy'], met0['makespan']), flush=True)
    print('best     en=%.4f mk=%.2f' % (cur_met['energy'], cur_met['makespan']), flush=True)
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'p2_energy26.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    # 导出改进解（若存在）
    if verdict == 'IMPROVED':
        from p2_solve import dispatch
        sch, _ = dispatch(data, cur_fl)
        sol = {'metrics': {k: (round(float(v), 4) if isinstance(v, float) else v)
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
        with open(os.path.join(OUTD, 'p2_energy26_solution.json'), 'w', encoding='utf-8') as fh:
            json.dump(sol, fh, ensure_ascii=False, indent=1)
        print('saved p2_energy26_solution.json', flush=True)
    print('saved p2_energy26.json', flush=True)


if __name__ == '__main__':
    main()