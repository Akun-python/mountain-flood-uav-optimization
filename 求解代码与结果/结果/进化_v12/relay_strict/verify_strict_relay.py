# -*- coding: utf-8 -*-
"""严格口径中继时序验证：评估 seed17 解（E 班提前 300s）的运输指标，
并测试将 N 组架次整体推迟 100s 能否消除两班衔接缺口（pen=0）。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_co2 as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
sv = M.Solver()
out = json.load(open(os.path.join(OUT, 'p3_co2_strict_s17.json'), encoding='utf-8'))
off17 = {int(k): float(v) for k, v in out['offsets'].items()}

# 每架次主中继组
groups = {}
for f in sv.flights:
    areas = [s for s, _ in f.route]
    gs = [M.AREA_POS[s] for s in areas if s in M.AREA_POS]
    groups[f.fid] = max(set(gs), key=gs.count) if gs else 'W'


def check(offsets, tag):
    releases = {fid: sv.base[fid] + offsets.get(fid, 0.0) for fid in sv.base}
    schedule, _ = M.dispatch(M.data, sv.flights, releases)
    met = M.evaluate(M.data, sv.flights, schedule)
    starts = {fid: schedule[fid]['start'] for fid in schedule}
    missions = sv.build_missions(starts)
    cov_bad, overlap, seg, by = sv.relay_load(missions)
    mpen, minfo, e_sum = sv.machine_penalty(missions)
    ret_max = 0.0
    for g, ss in minfo.items():
        pos = M.POS_OF[g]
        t_out, t_back, _ = M.relay_mission_time(pos[0], pos[1], pos[2], M.data)
        for s in ss:
            ret_max = max(ret_max, s[1] + t_back)
    print('%s: hard=%s tardy=%.1f makespan=%.1f energy=%.2f | cover_bad=%d mpen=%.0f '
          'relayE=%.3f 中继最晚返场=%.0f (运输完工 %.1f)'
          % (tag, met['hard_ok'], met['tardy_w'], met['makespan'], met['energy'],
             cov_bad, mpen, e_sum, ret_max, met['makespan']))
    for g, ss in sorted(minfo.items()):
        for s in ss:
            print('   %s t=[%.0f, %.0f]' % (g, s[0], s[1]))
    return met, mpen

met17, _ = check(off17, 'seed17 原案')
# 变体：E 组整体 -100 s（提前 E 班结束，压缩充电后周转缺口）
off_e = dict(off17)
for fid, g in groups.items():
    if g == 'E':
        off_e[fid] = min(M.MAXDELAY, max(-M.MAXEARLY, off_e[fid] - 100.0))
check(off_e, 'E组-100s')
# 变体：N 组整体 +100 s
off_n = dict(off17)
for fid, g in groups.items():
    if g == 'N':
        off_n[fid] = min(M.MAXDELAY, max(-M.MAXEARLY, off_n[fid] + 100.0))
check(off_n, 'N组+100s')