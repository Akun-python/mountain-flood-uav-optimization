# -*- coding: utf-8 -*-
"""定位决定 E 班服务段末端（t1=3774）的架次：穷举单架次 offset -100s，
找使 machine_pen 归零且运输指标不变的干净解。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_co2 as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
sv = M.Solver()
out = json.load(open(os.path.join(OUT, 'p3_co2_strict_s17.json'), encoding='utf-8'))
base_off = {int(k): float(v) for k, v in out['offsets'].items()}

# 各架次主中继组
groups = {}
for f in sv.flights:
    areas = [s for s, _ in f.route]
    gs = [M.AREA_POS[s] for s in areas if s in M.AREA_POS]
    groups[f.fid] = max(set(gs), key=gs.count) if gs else 'W'


def mpen_of(offsets):
    releases = {fid: sv.base[fid] + offsets.get(fid, 0.0) for fid in sv.base}
    schedule, _ = M.dispatch(M.data, sv.flights, releases)
    met = M.evaluate(M.data, sv.flights, schedule)
    if not met['hard_ok']:
        return None, met
    starts = {fid: schedule[fid]['start'] for fid in schedule}
    missions = sv.build_missions(starts)
    cov_bad, overlap, seg, by = sv.relay_load(missions)
    if cov_bad > 0:
        return 1e9, met
    mpen, minfo, e_sum = sv.machine_penalty(missions)
    return mpen, met


def show(offsets, tag):
    mpen, met = mpen_of(offsets)
    starts_ok = met is not None and met['hard_ok']
    print('%s: mpen=%s makespan=%.1f energy=%.2f tardy=%.1f'
          % (tag, mpen, met['makespan'], met['energy'], met['tardy_w']))
    return mpen

print('基线(seed17):')
show(base_off, '  base')
print('单架次 -100s 试探：')
best_row = None
for fid, g in sorted(groups.items()):
    if g != 'E':
        continue
    off = dict(base_off)
    off[fid] = max(-M.MAXEARLY, off[fid] - 100.0)
    mpen, met = mpen_of(off)
    if mpen is None or mpen >= 1e9:
        print('  f%02d(%s): 覆盖破坏或不可行' % (fid, g))
        continue
    mark = ' <== 缺口消除' if mpen == 0 else ''
    print('  f%02d(%s): mpen=%.0f makespan=%.1f tardy=%.1f%s'
          % (fid, g, mpen, met['makespan'], met['tardy_w'], mark))
    if mpen == 0 and (met['hard_ok'] and met['tardy_w'] < 1e-6):
        best_row = (fid, off)