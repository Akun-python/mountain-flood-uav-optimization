# -*- coding: utf-8 -*-
"""
v22a · W 窗口末端收口（架构式：反向转移压缩联合完工）
=====================================================
诊断：官方联合完工 7259.81 s 由两条链路共同驱动——① W 窗口起点 1078
（最早 W 区任务不得早于中继到位）触发早班 +300 延迟级联；② W 窗口末端
6802 由 f5 的 S005 段 [6043,6802] 定义。v20 把 S005 箱从 f23 移入 f5
（窗口变宽至 7102）；本实验取**相反方向**：把 f5 的 S005 箱前移到更早
的 f23，压缩 W 窗口末端 → 运输侧不再需要为窗口末端延迟 → 联合完工
有望 < 7259.81 s。

每步移动后：P2 完整 dispatch 复核（26 架 / hard_ok / 零迟到 / 能耗），
再跑联合完工最小化 SA 求联合下界。
"""
import sys, os, json, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from core import Data
from p2_solve import Flight, dispatch as _dispatch
from common import Budget, safe_eval
import p3_co2
from p3_co2 import Solver

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v22')
TMP = os.path.join(HERE, '_wcomp_tmp')


def load_champion(data):
    with open(os.path.join(RES, 'p2_results.json'), encoding='utf-8') as fh:
        r = json.load(fh)
    base = {f['fid']: f['start'] for f in r['flights']}
    fl = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
          for f in r['flights']]
    return fl, base


def apply_move(flights, src, dst, sid, bids, data):
    newf = []
    for x in flights:
        if x.fid == src.fid:
            route = []
            for s, bs in x.route:
                if s == sid:
                    bs = [b for b in bs if b not in bids]
                    if bs:
                        route.append((s, bs))
                else:
                    route.append((s, list(bs)))
            newf.append(Flight(x.fid, route, x.model, data))
        elif x.fid == dst.fid:
            route = [(s, list(bs)) for s, bs in x.route]
            for i, (s, bs) in enumerate(route):
                if s == sid:
                    route[i] = (s, bs + bids)
                    break
            else:
                route.append((sid, bids))
            newf.append(Flight(x.fid, route, x.model, data))
        else:
            newf.append(x)
    newf = [x for x in newf if x.box_ids]
    for x in newf:
        if not x.is_feasible():
            return None
    return newf


def joint_floor(cand_flights, base, data, iters=1500, seed=7):
    os.makedirs(TMP, exist_ok=True)
    sol = {'metrics': {}, 'flights': [{'fid': f.fid, 'start': base[f.fid],
                                       'route': [(s, list(bs)) for s, bs in f.route],
                                       'model': f.model} for f in cand_flights]}
    with open(os.path.join(TMP, 'p2_results.json'), 'w', encoding='utf-8') as fh:
        json.dump(sol, fh, ensure_ascii=False)
    old_out = p3_co2.OUT
    p3_co2.OUT = TMP
    try:
        sv = Solver()
        offs, obj = sv.sa(iters, seed=seed)
        res = sv.finalize(offs)
        met = res['met']
        mpen, minfo, relay_energy = sv.machine_penalty(res['missions'])
        cov_bad, overlap, _, _ = sv.relay_load(res['missions'])
        latest = 0.0
        for g, ss in minfo.items():
            pos = p3_co2.POS_OF[g]
            _, t_back, _ = p3_co2.relay_mission_time(pos[0], pos[1], pos[2], data)
            latest = max(latest, max(s[1] + t_back for s in ss))
        record = {'met': {k: (round(float(v), 3) if isinstance(v, float) else v)
                          for k, v in met.items() if k != 'box_time'},
                  'mpen': mpen, 'cover_bad': cov_bad, 'overlap': overlap,
                  'relay_energy': round(float(relay_energy), 3),
                  'latest_relay': round(float(latest), 1),
                  'joint': round(max(float(met['makespan']), float(latest)), 1)}
    finally:
        p3_co2.OUT = old_out
        shutil.rmtree(TMP, ignore_errors=True)
    return record


def main():
    data = Data()
    fl0, base = load_champion(data)
    b = Budget(100000)
    met0, sched0 = safe_eval(data, fl0, b)
    print('baseline: en=%.3f mk=%.2f fl=%d' % (met0['energy'], met0['makespan'], met0['flights']), flush=True)
    candidates = []
    # 候选 1：f5 两个 S005 箱 → f23（整组；质量超限会被 is_feasible 拒绝）
    candidates.append(('f5_S005x2_to_f23', 5, 23, 'S005', ['S005-MED-01', 'S005-WAT-01']))
    # 候选 2：仅 MED（医疗优先）+仅 WAT 分别试
    candidates.append(('f5_S005MED_to_f23', 5, 23, 'S005', ['S005-MED-01']))
    candidates.append(('f5_S005WAT_to_f23', 5, 23, 'S005', ['S005-WAT-01']))
    results = []
    for name, src_fid, dst_fid, sid, bids in candidates:
        src = next(x for x in fl0 if x.fid == src_fid)
        dst = next(x for x in fl0 if x.fid == dst_fid)
        cand = apply_move(fl0, src, dst, sid, bids, data)
        if cand is None:
            results.append({'name': name, 'p2': 'infeasible(mass/route)'})
            print('%-22s infeasible' % name, flush=True)
            continue
        m, _ = safe_eval(data, cand, Budget(100000))
        if m is None:
            results.append({'name': name, 'p2': 'infeasible'})
            continue
        ok = m['hard_ok'] and m['tardy_w'] < 1e-6 and m['flights'] == 26
        print('%-22s en=%.3f mk=%.2f ok=%s' % (name, m['energy'], m['makespan'], ok), flush=True)
        if not ok:
            results.append({'name': name, 'p2': {k: round(float(v), 3) if isinstance(v, float) else v
                                                 for k, v in m.items() if k != 'box_time'},
                            'pass': False})
            continue
        res = joint_floor(cand, base, data, iters=1500)
        rec = {'name': name,
               'p2': {k: round(float(v), 3) if isinstance(v, float) else v
                      for k, v in m.items() if k != 'box_time'},
               'joint': res['joint'], 'makespan': res['met']['makespan'],
               'relay_energy': res['relay_energy'],
               'cover_bad': res['cover_bad'], 'mpen': res['mpen']}
        print('   joint=%.1f relay=%.3f cov=%d mpen=%d' % (rec['joint'], rec['relay_energy'],
                                                           rec['cover_bad'], rec['mpen']), flush=True)
        results.append(rec)
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'w_compress26.json'), 'w', encoding='utf-8') as fh:
        json.dump({'baseline': {k: round(float(v), 3) if isinstance(v, float) else v
                                for k, v in met0.items() if k != 'box_time'},
                   'results': results}, fh, ensure_ascii=False, indent=1)
    print('saved w_compress26.json', flush=True)


if __name__ == '__main__':
    main()