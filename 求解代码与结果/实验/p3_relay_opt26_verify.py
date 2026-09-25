# -*- coding: utf-8 -*-
"""
v17b · P3 新中继位置严格复核（官方口径同源）
============================================
对 26 架冠军 + 官方偏移（results/p3_co2.json），把 POS_OF 替换为
v17 爬山最优位置，用与 p3_co2.py 完全相同的判定链复核：
  1) 任务级 cover_bad / R2 重叠
  2) 中继窗口 seg 是否与官方一致（W 5724 / E 2668 / N 552 s）
  3) machine_penalty：准备 180 s + 周转 300 s + 按需补电（严格口径）
  4) 中继能耗合计（W/E/N 各架次之和）
  5) 联合完工：运输 makespan vs 中继最晚返场
同时输出官方位置对照，并校验各新位置悬停离地高度 <=300 m 且高于地面。
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import p3_co2
from p3_co2 import Solver, POS_OF, P_W, P_E, P_N, data, REL, T_FULL
from core import relay_mission_time, relay_mission_energy

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v17')

OFFICIAL = {'W': P_W, 'E': P_E, 'N': P_N}


def load_candidates():
    """从搜索输出读取精确（6 位小数）候选位置，避免取整漂移。"""
    p = os.path.join(OUTD, 'p3_relay_opt26.json')
    with open(p, encoding='utf-8') as fh:
        d = json.load(fh)
    cands = {}
    for tag, key in (('grid', 'frameworkB_grid'), ('hill', 'frameworkC_restart_hill')):
        cands[tag] = {g: tuple(d[key][g]['pos']) for g in 'WEN'}
    dpos = {g: tuple(d['frameworkD_margin1dB'][g]['pos'])
            for g in d['frameworkD_margin1dB'] if g != 'total_energy'}
    # 框架 D 组合：W 保持官方（已到余量极限），E/N 用 D 搜索的 ≥1 dB 位置
    cands['margin1dB_combo'] = {'W': OFFICIAL['W'], 'E': dpos['E'], 'N': dpos['N']}
    return cands


def check_hover(pos):
    """悬停离地高度校验：z > 地面 且 z - 地面 <= 300 m。"""
    t = data.dem_at(pos[0], pos[1])
    if math_isnan(t):
        return 'dem-nan'
    if pos[2] <= t:
        return 'below-ground'
    if pos[2] - t > 300.0 + 1e-6:
        return '>300m'
    return 'ok(h=%.0f)' % (pos[2] - t)


def math_isnan(x):
    import math
    return math.isnan(x)


def run(pos_set, offsets, fresh=False):
    """两种解释：
    fresh=False（保持官方货箱安排）：先按官方位置构造 Solver（surgical_fix 与官方一致），
        再打补丁换中继位置并重建覆盖标志 —— 对应"只移动中继、运输方案不变"；
    fresh=True（新位置自洽求解）：先打补丁再构造 Solver，surgical_fix 也按新位置执行。
    """
    if not fresh:
        sv = Solver()          # 官方位置构造（结构 = 官方方案）
        p3_co2.P_W, p3_co2.P_E, p3_co2.P_N = pos_set['W'], pos_set['E'], pos_set['N']
        p3_co2.POS_OF = dict(pos_set)
        sv.precompute()        # 用新位置重建样本覆盖标志
    else:
        p3_co2.P_W, p3_co2.P_E, p3_co2.P_N = pos_set['W'], pos_set['E'], pos_set['N']
        p3_co2.POS_OF = dict(pos_set)
        sv = Solver()          # 新位置下重新 surgical_fix
        sv.precompute()

    res = sv.finalize(offsets)
    met = res['met']
    seg = res['seg']
    # 逐架次能耗与返场
    by = {}
    for m in res['missions']:
        by.setdefault(m['grp'], []).append(m)
    energy = {'W': 0.0, 'E': 0.0, 'N': 0.0}
    latest_return = 0.0
    for g in 'WEN':
        pos = pos_set[g]
        t_out, t_back, _ = relay_mission_time(pos[0], pos[1], pos[2], data)
        ms = sorted(by.get(g, []), key=lambda m: m['t0'])
        if not ms:
            continue
        t0, t1 = ms[0]['t0'], ms[0]['t1']
        # 合并连续窗口（同 p3_co2 pack 逻辑：预算内合并）
        sorties = []
        cur = {'t0': t0, 't1': t1}
        for m in ms[1:]:
            nt1 = max(cur['t1'], m['t1'])
            if relay_mission_energy(pos[0], pos[1], pos[2], data, nt1 - cur['t0']) <= (1 - REL['rho']) * REL['E_use']:
                cur['t1'] = nt1
            else:
                sorties.append(cur)
                cur = {'t0': m['t0'], 't1': m['t1']}
        sorties.append(cur)
        for s in sorties:
            e = relay_mission_energy(pos[0], pos[1], pos[2], data, s['t1'] - s['t0'])
            energy[g] += e
            latest_return = max(latest_return, s['t1'] + t_back)
    total = sum(energy.values())
    return {'met': {k: (round(v, 2) if isinstance(v, float) else v)
                    for k, v in met.items() if k != 'box_time'},
            'cover_bad': res['mpen'] is not None and _cov_bad(res),
            'seg': {g: [(round(a), round(b)) for a, b in seg[g]] for g in seg},
            'energy': {g: round(energy[g], 3) for g in energy},
            'total_energy_kwh': round(total, 3),
            'latest_relay_return': round(latest_return, 1),
            'joint_makespan': max(round(met['makespan'], 1), round(latest_return, 1)),
            'hover_check': {g: check_hover(pos_set[g]) for g in pos_set}}


def _cov_bad(res):
    """复用 p3_co2 relay_load 的 cover_bad 口径。"""
    by = {}
    for m in res['missions']:
        by.setdefault(m['grp'], []).append(m)
    from p3_co2 import AREA_POS
    return sum(1 for m in res['missions'] if m['n_cov'] < m['n'])


def main():
    off = json.load(open(os.path.join(RES, 'p3_co2.json'), encoding='utf-8'))
    offsets = {int(k): float(v) for k, v in off.get('offsets', {}).items()}
    out = {}
    cands = load_candidates()
    runs = [('official', OFFICIAL, False)]
    for tag, pos_set in cands.items():
        runs.append(('v17_%s_official_struct' % tag, pos_set, False))
        runs.append(('v17_%s_fresh' % tag, pos_set, True))
    for name, pos_set, fresh in runs:
        print('\n==== %s ====' % name, flush=True)
        r = run(pos_set, offsets, fresh=fresh)
        print('  transport: %s' % r['met'], flush=True)
        print('  cover_bad=%d  seg=%s' % (r['cover_bad'], r['seg']), flush=True)
        print('  relay_energy=%s total=%.3f kWh  latest_return=%.0f joint_mk=%.0f'
              % (r['energy'], r['total_energy_kwh'], r['latest_relay_return'],
                 r['joint_makespan']), flush=True)
        print('  hover: %s' % r['hover_check'], flush=True)
        out[name] = r
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'p3_relay_opt26_verify.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('\nsaved', os.path.join(OUTD, 'p3_relay_opt26_verify.json'), flush=True)


if __name__ == '__main__':
    main()
