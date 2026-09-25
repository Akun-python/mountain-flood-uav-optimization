# -*- coding: utf-8 -*-
"""v25 区一致化修复：把 25 架压缩解的错区箱移回真实服务区架次。
策略：对每个错区箱，找 route 含真实区且容量/能耗可行的架次转移；
无目标则在原架次真实区新增条目。全部修复后严格 evaluate 验证 hard True。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

sol = json.load(open(os.path.join(OUTD, 'p2v25_compress.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in sol['solution']]


def mismatches(fls):
    bad = []
    for f in fls:
        for s, bs in f.route:
            for b in bs:
                if b.split('-')[0] != s:
                    bad.append((f, s, b))
    return bad


def area_of(b):
    return b.split('-')[0]


def try_move(fls, f, s, b):
    """把 f 中挂错区 s 的箱 b 移到含真实区的架次；成功返回新 fls，否则 None。"""
    fl = clone_flights(fls)
    src = next((x for x in fl if x.fid == f.fid), None)
    target = None
    for g in fl:
        if g.fid == f.fid:
            continue
        if any(s2 == area_of(b) for s2, _ in g.route):
            target = g
            break
    if target is None:
        return None
    # 从 src 移除
    for i, (s2, bs) in enumerate(src.route):
        if s2 == s and b in bs:
            bs.remove(b)
            if not bs:
                del src.route[i]
            break
    normalize_flight(src, data)
    # 加入 target 真实区条目
    for i, (s2, bs) in enumerate(target.route):
        if s2 == area_of(b):
            bs.append(b)
            target.route[i] = (s2, bs)
            break
    else:
        target.route.append((area_of(b), [b]))
    normalize_flight(target, data)
    if not src.route:                      # 源架次转空 -> 删除
        fl = [x for x in fl if x.fid != src.fid]
    elif not src.is_feasible():
        return None
    if not target.is_feasible():
        return None
    return fl


def main():
    bad = mismatches(fls)
    print('修复前错区箱:', len(bad))
    cur = fls
    moves = []
    for rnd in range(4):
        bad = mismatches(cur)
        if not bad:
            break
        moved = False
        for (f, s, b) in list(bad):
            cand = try_move(cur, f, s, b)
            if cand is None:
                continue
            sch, _ = dispatch(data, cand)
            if sch is None:
                continue
            met = evaluate(data, cand, sch)
            if not (met['hard_ok'] and met['tardy_w'] < 1e-6):
                continue
            if met['makespan'] <= 7300:    # 允许完工小幅上浮，但不超过 7300s
                moves.append((b, f.fid, area_of(b)))
                cur = cand
                moved = True
                break
        print('round %d: 修复 %d 箱, 当前 %d 架 / mk %.1f / %.2f kWh' % (
            rnd + 1, len(moves), met['flights'], met['makespan'], met['energy']))
        if not moved:
            break
    bad = mismatches(cur)
    sch, _ = dispatch(data, cur)
    met = evaluate(data, cur, sch)
    print('\n修复后: 错区箱=%d  架=%d  mk=%.1f  kWh=%.2f  hard=%s  tardy=%.3f' % (
        len(bad), met['flights'], met['makespan'], met['energy'], met['hard_ok'], met['tardy_w']))
    if not bad and met['hard_ok']:
        out = {'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in cur],
               'metrics': {'flights': met['flights'], 'makespan': round(met['makespan'], 1),
                           'energy': round(met['energy'], 3), 'hard_ok': True, 'tardy_w': 0.0},
               'moves': moves}
        json.dump(out, open(os.path.join(OUTD, 'p2v25_repairzones.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v25_repairzones.json')
    else:
        print('修复未完全：剩余错区箱', bad[:10])


if __name__ == '__main__':
    main()