# -*- coding: utf-8 -*-
"""v26 ALNS 全局重搜索（P2，严格口径，完工优先）。
破坏目标 = dispatch 后 load 最重的一条机链的随机 1-2 个架次，取出全部箱；
重建 = 按区把这些箱重装入访问该区且容量够的架次（best-fit 能量增量最小），
       该区无架次则新建最小可行机型架次；
接受 = ensures zone-consistent & 硬约束 &（makespan 下降，或 makespan<=bestMK+180 而能耗降）。
起点：v25j（24架/7889.9s）与 v25b（28架/7394.9s）各跑，攻 makespan<7395。"""
import sys, os, json, copy, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
random.seed(11)
data = Data()
MODELS = ['A', 'B', 'C']


def eval_full(data, fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None, None
    return evaluate(data, fl, sch), sch


def rebuild_box(data, fl, bid, src_sid):
    """把 bid（属 src_sid 区）装入访问 src_sid 且质量/体积够的架次，能量增量最小。
    若有架次访问该区则并入；否则新建。返回 fl（破坏型）或删掉原架次时可能引用无效。"""
    real = bid.split('-')[0]
    bx = data.boxes[bid]
    best = None
    for f in fl:
        if src_sid in [s for s, _ in f.route] and bid.split('-')[0] == real:
            # 装载容量
            if f.total_mass + bx['mass'] <= data.uav_types[f.model]['Q'] + 1e-9:
                if f.total_vol + bx['vol'] <= data.uav_types[f.model]['V'] + 1e-9:
                    cand = clone_flights(fl)
                    fc = next(x for x in cand if x.fid == f.fid)
                    fc.route = [(s, list(bs)) for s, bs in f.route if s != src_sid]
                    # route 重新加该区（保持原序插入）
                    extra = bx['mass'] - f.total_mass
                    d_inc = f.energy() * 0  # 占位
                    # 计算增量：并入后新架次能量 - 原架次能量
                    merged_route = list(f.route)
                    done = False
                    for i, (s2, bs2) in enumerate(merged_route):
                        if s2 == src_sid:
                            merged_route[i] = (s2, bs2 + [bid])
                            done = True
                            break
                    if not done:
                        merged_route.append((src_sid, [bid]))
                    fc.route = merged_route
                    normalize_flight(fc, data)
                    if fc.is_feasible():
                        inc = fc.energy() - f.energy()
                        if best is None or inc < best[0]:
                            best = (inc, bid, f.fid, 'merge')
    if best is not None:
        if best[3] == 'merge':
            fl2 = clone_flights(fl)
            fc = next(x for x in fl2 if x.fid == best[2])
            merged_route = list(fc.route)
            done = False
            for i, (s2, bs2) in enumerate(merged_route):
                if s2 == src_sid:
                    merged_route[i] = (s2, bs2 + [bid])
                    done = True
                    break
            if not done:
                merged_route.append((src_sid, [bid]))
            fc.route = merged_route
            normalize_flight(fc, data)
            return fl2
    # 新建架次
    fid = max(x.fid for x in fl if x.fid is not None) + 1
    nf = Flight(fid, [(real, [bid])], 'C', data)
    fl = clone_flights(fl)
    fl.append(nf)
    return fl


def remove_boxes(data, fl, fid):
    """移除架次 fid 的所有箱。返回 (new_fl, removed_boxes, 是否删架次)。"""
    fl = clone_flights(fl)
    f = next(x for x in fl if x.fid == fid)
    removed = [(s, b) for s, bs in f.route for b in bs]
    fl = [x for x in fl if x.fid != fid]
    return fl, removed


def destroy_repair(data, fl):
    """破坏 1 个随机架次并重建。返回新 fl（可能不更优）。"""
    # 选 load 最高的机链的随机架次（破坏 edge）
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None
    chains = {}
    for f in fl:
        chains.setdefault(sch[f.fid]['uav'], []).append((f, sch[f.fid]))
    longest = max(chains.values(), key=lambda c: max(x[1]['return'] for x in c))
    target = random.choice(longest)
    fl2, removed = remove_boxes(data, fl, target[0].fid)
    fl3 = clone_flights(fl2)
    for sid, b in removed:
        fl3 = rebuild_box(data, fl3, b, sid)
        if fl3 is None:
            return None
    return fl3


# 需要 rebuild 返回 fl（忽略增量）
def rebuild(data, fl, bid, src_sid):
    fl = clone_flights(fl)
    real = bid.split('-')[0]
    bx = data.boxes[bid]
    best_f = None
    for f in fl:
        if any(s == src_sid for s, _ in f.route):
            if f.total_mass + bx['mass'] <= data.uav_types[f.model]['Q'] + 1e-9:
                fc = clone_flights(fl)
                tgt = next(x for x in fc if x.fid == f.fid)
                merged = list(tgt.route)
                done = False
                for i, (s2, bs2) in enumerate(merged):
                    if s2 == src_sid:
                        merged[i] = (s2, bs2 + [bid])
                        done = True
                        break
                if not done:
                    merged.append((src_sid, [bid]))
                tgt.route = merged
                normalize_flight(tgt)
                if tgt.is_feasible():
                    best_f = fc
                    break
    if best_f is not None:
        return best_f
    fid = max(x.fid for x in fl if x.fid is not None) + 1
    fl.append(Flight(fid, [(real, [bid])], 'C', data))
    return fl


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'p2v25b_compress26.json'
    start = json.load(open(os.path.join(OUTD, src), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in start['solution']]
    m0, s0 = eval_full(data, fls)
    print('起点 %s: %d 架 / mk %.1f / %.2f kWh' % (src, len(fls), m0['makespan'], m0['energy']))
    best_fl, best_mk = clone_flights(fls), m0['makespan']
    for it in range(int(sys.argv[2]) if len(sys.argv) > 2 else 300):
        cand = destroy_repair(data, best_fl)
        if cand is None:
            continue
        m, s = eval_full(data, cand)
        if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
            continue
        if m['makespan'] < best_mk - 1e-6 and m['energy'] < 90.0:
            best_fl, best_mk = clone_flights(cand), m['makespan']
            print('  it%d: %d 架 / mk %.1f / %.2f kWh' % (it, len(cand), m['makespan'], m['energy']))
    m, s = eval_full(data, best_fl)
    print('结果: %d 架 / mk %.1f (%.1f min) / %.2f kWh / hard %s' % (
        len(best_fl), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok']))
    if m['makespan'] < m0['makespan'] - 1e-6:
        json.dump({'best': {k: v for k, v in m.items() if k != 'box_time'},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s, list(bs)) for s, bs in f.route]} for f in best_fl]},
                  open(os.path.join(OUTD, 'p2v26_alns.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v26_alns.json')


if __name__ == '__main__':
    main()