# -*- coding: utf-8 -*-
"""
v19c · P3 联合完工最小化偏移重寻（官方 26 架输入）
=================================================
官方 SA 目标中完工权重仅 0.05，完工不是其优化重点（联合 7260 s 未必是
最小可达）。本实验把目标改为"联合完工 = max(运输完工, 中继最晚返场) 为主
+ 约束罚"，在同一搜索空间（逐架次偏移 ∈ [-3600, 3600]）重寻偏移，
要求全约束（cover_bad=0 / R2 重叠 0 / machine_pen=0 / 零迟到）下
联合完工最小。若 < 7260 s 且中继能耗不劣化，则采纳为 v19 成果。
"""
import sys, os, json, math, random, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import p3_co2
from p3_co2 import Solver, POS_OF
from core import relay_mission_time, relay_mission_energy
import core

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v21')
TMP = os.path.join(HERE, '_jointmin_tmp')


def data_of(sv):
    return sv.flights[0].data if sv.flights else p3_co2.data


def joint_of(sv, offsets):
    """以官方评估链算联合完工与约束罚。返回 (obj, info)。"""
    dd = data_of(sv)
    releases = {fid: sv.base[fid] + offsets.get(fid, 0.0) for fid in sv.base}
    from p2_solve import dispatch, evaluate
    schedule, _ = dispatch(dd, sv.flights, releases)
    met = evaluate(dd, sv.flights, schedule)
    if not met['hard_ok'] or schedule is None:
        return 1e9, None
    starts = {fid: schedule[fid]['start'] for fid in schedule}
    missions = sv.build_missions(starts)
    cov_bad, overlap, seg, by = sv.relay_load(missions)
    mpen, minfo, relay_energy = sv.machine_penalty(missions)
    latest = 0.0
    for g in ('W', 'E', 'N'):
        for s in by.get(g, []):
            t_out, t_back, _ = relay_mission_time(POS_OF[g][0], POS_OF[g][1], POS_OF[g][2], dd)
            latest = max(latest, s['t1'] + t_back)
    joint = max(met['makespan'], latest)
    obj = (joint + 1e5 * cov_bad + 5e4 * overlap + 1e4 * mpen
           + 1e3 * met['tardy_w'] + 0.5 * met['energy'])
    info = {'joint': joint, 'makespan': met['makespan'], 'energy': met['energy'],
            'tardy': met['tardy_w'], 'cov_bad': cov_bad, 'overlap': overlap,
            'mpen': mpen, 'relay_energy': relay_energy, 'latest_relay': latest,
            'flights': met['flights']}
    return obj, info


def main(iters=4000, seed=7, cand_path=None):
    if cand_path:
        import shutil
        os.makedirs(TMP, exist_ok=True)
        shutil.copy(cand_path, os.path.join(TMP, 'p2_results.json'))
        p3_co2.OUT = TMP
    else:
        p3_co2.OUT = RES
    sv = Solver()
    rng = random.Random(seed)
    cur = {k: 0.0 for k in sv.base}
    cur_obj, cur_info = joint_of(sv, cur)
    best, best_obj, best_info = dict(cur), cur_obj, cur_info
    T = 600.0
    for it in range(iters):
        nxt = copy.deepcopy(cur)
        fid = rng.choice(list(nxt))
        step = rng.choice([300, 600, 900, 1200, 1800, 2400, 3600])
        nxt[fid] = min(3600.0, max(-3600.0, nxt[fid] + rng.choice([-1, 1]) * step))
        if sv.base[fid] + nxt[fid] < 300:
            nxt[fid] = 300 - sv.base[fid]
        o2, i2 = joint_of(sv, nxt)
        if o2 < best_obj - 1e-9:
            best, best_obj, best_info = dict(nxt), o2, i2
        if o2 < cur_obj or rng.random() < math.exp((cur_obj - o2) / max(T, 1e-9)):
            cur, cur_obj = nxt, o2
        T = max(1.0, T * 0.999)
        if it % 500 == 0 and it > 0:
            print('  it=%d best_joint=%.1f' % (it, best_info['joint'] if best_info else -1), flush=True)
    print('SA done. best joint=%.1f  info=%s' % (best_obj if best_info is None else best_info['joint'], best_info), flush=True)
    res = sv.finalize(best)
    met = res['met']
    info = best_info or {}
    out = {
        'objective': 'joint = max(transport_mk, relay_latest_return) + penalties',
        'seed': seed, 'iters': iters,
        'best_offsets': {str(k): round(v, 1) for k, v in best.items()},
        'best_info': {k: (round(v, 3) if isinstance(v, float) else v)
                      for k, v in (info or {}).items()},
        'finalize_met': {k: (round(v, 3) if isinstance(v, float) else v)
                         for k, v in met.items() if k != 'box_time'},
        'finalize_cover_bad': sum(1 for m in res['missions'] if m['n_cov'] < m['n']),
        'finalize_mpen': round(float(res['mpen']), 1),
        'seg': {g: [(round(a), round(b)) for a, b in res['seg'][g]] for g in res['seg']},
        'official_baseline': {'joint': 7260.0, 'makespan': 7259.81,
                              'relay_energy': 3.417},
    }
    latest = 0.0
    for g in ('W', 'E', 'N'):
        for (t0, t1) in res['seg'][g]:
            _, t_back, _ = relay_mission_time(POS_OF[g][0], POS_OF[g][1], POS_OF[g][2], data_of(sv))
            latest = max(latest, t1 + t_back)
    out['finalize_joint'] = round(max(float(met['makespan']), latest), 1)
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'p3_joint_min26.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('\nfinalize: joint=%.1f  makespan=%.1f  cover_bad=%d  mpen=%.0f' %
          (out['finalize_joint'], met['makespan'],
           out['finalize_cover_bad'], out['finalize_mpen']), flush=True)
    print('saved p3_joint_min26.json', flush=True)


if __name__ == '__main__':
    main(iters=int(sys.argv[1]) if len(sys.argv) > 1 else 4000,
         cand_path=sys.argv[2] if len(sys.argv) > 2 else None)