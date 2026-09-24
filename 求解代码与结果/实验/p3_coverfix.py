# -*- coding: utf-8 -*-
"""
问题三中继覆盖修复：在给定运输冠军方案下，消灭自动化管线留下的未覆盖采样点（cov_bad）
流程：
  1) 读 p2_results.json（冠军架次 + 起始时刻），叠加 p3_co2 的时间偏移
  2) 沿航线采样，复用 p3 几何覆盖模型，找"本区指定中继未覆盖"的任务
  3) 修复 a) 微移中继坐标（对每个中继局域网格做坐标下降），b) 中继归属重分配
  4) 输出修复后中继坐标、覆盖统计与对比
"""
import sys, os, json, math, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (Data, direct_ok, relay_link_ok, relay_mission_time,
                  relay_mission_energy)
from p3_gaps import flight_trajectory
from p2_solve import Flight

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v6')

data = None  # 模块级（main 内初始化）

# 原中继布设
P = {'W': (109.2103, 23.047134, 676.5),
     'E': (109.276017, 23.019401, 542.3),
     'N': (109.238171, 23.077841, 496.1)}
AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'


def cov_bad_with(area_pos, POS, samples):
    """给定中继位与归属表，统计未覆盖任务数与未覆盖采样点数。"""
    by_area = {}
    for s in samples:
        by_area.setdefault((s['fid'], s['sid']), []).append(s)
    bad_tasks = 0
    bad_samples = 0
    for (fid, sid), slist in by_area.items():
        g = area_pos.get(sid)
        if g is None:
            continue
        rel = POS[g]
        ncov = sum(1 for s in slist if relay_link_ok(s['lon'], s['lat'], s['z'], rel, data))
        if ncov < len(slist):
            bad_tasks += 1
        bad_samples += len(slist) - ncov
    return bad_tasks, bad_samples


def score_key(c):
    return (c[0], c[1])


def main():
    global data
    data = Data()
    with open(os.path.join(RES, 'p2_results.json'), encoding='utf-8') as fh:
        p2 = json.load(fh)
    flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
               for fj in p2['flights']]
    base = {fj['fid']: float(fj['start']) for fj in p2['flights']}
    # 应用 p3_co2 的时间偏移（若有）
    offsets = {}
    off_p = os.path.join(RES, 'p3_co2.json')
    if os.path.exists(off_p):
        r3 = json.load(open(off_p, encoding='utf-8'))
        offsets = {int(k): float(v) for k, v in r3.get('offsets', {}).items()}

    # 采样：每架次 30 m 步长，跳过直连点
    samples = []
    for f in flights:
        s0 = base[f.fid] + offsets.get(f.fid, 0.0)
        pts, _ = flight_trajectory(f, s0)
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            sid = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                              data.areas[s]['lon'], data.areas[s]['lat']))
            samples.append({'fid': f.fid, 't': pt['t'], 'sid': sid,
                            'lon': pt['lon'], 'lat': pt['lat'], 'z': pt['z']})
    print('need-relay samples:', len(samples))

    c0 = cov_bad_with(AREA_POS, P, samples)
    print('baseline: bad_tasks=%d bad_samples=%d' % c0)

    # 各中继组未覆盖采样点数
    gdef = {'W': [], 'E': [], 'N': []}
    for s in samples:
        g = AREA_POS.get(s['sid'])
        if g is not None and not relay_link_ok(s['lon'], s['lat'], s['z'], P[g], data):
            gdef[g].append(s)
    for g in ('W', 'E', 'N'):
        print('group %s uncovered samples: %d' % (g, len(gdef[g])))

    # 微移搜索：只对有缺口的中继组做（其余组无缺口，不改动），最小位移达成全零
    POS = copy.deepcopy(P)
    for g in ('W', 'E', 'N'):
        gap_s = gdef[g]
        if not gap_s:
            continue
        bx, by_, bz = POS[g]
        coslat = math.cos(math.radians(by_))
        fixed = cov_bad_with(AREA_POS, POS, samples)[0] - (1 if gap_s else 0)
        best = None
        dlon_set = [-0.01, -0.008, -0.006, -0.004, -0.002, 0, 0.002, 0.004, 0.006, 0.008, 0.01]
        dlat_set = dlon_set[:]
        dz_set = [0, 60, -60, 120, -120, 180, -180, 240, -240, 300, -300]
        for dlon in dlon_set:
            for dlat in dlat_set:
                for dz in dz_set:
                    cand = dict(POS)
                    cand[g] = (bx + dlon, by_ + dlat, bz + dz)
                    nc = sum(1 for s in gap_s
                             if relay_link_ok(s['lon'], s['lat'], s['z'], cand[g], data))
                    bad_tasks = fixed + (1 if nc < len(gap_s) else 0)
                    disp = math.hypot(dlon * 111320.0 * coslat, dlat * 110540.0) + abs(dz) * 0.3
                    key = (bad_tasks, len(gap_s) - nc, disp)
                    if best is None or key < best[0]:
                        best = (key, bx + dlon, by_ + dlat, bz + dz)
        POS[g] = (best[1], best[2], best[3])
    c1 = cov_bad_with(AREA_POS, POS, samples)
    print('after micro-shift: bad_tasks=%d bad_samples=%d' % c1)

    # 中继-地面回程可行性检查
    from core import relay_backhaul_ok, relay_link_ok as _rl
    for g in ('W', 'E', 'N'):
        print('  relay %s backhaul_ok=%s' % (g, relay_backhaul_ok(POS[g], data)))

    # 归属重分配：仅当在全量采样上确实改善才采纳（防止局部误判恶化覆盖）
    reassign = {}
    by_sid = {}
    for s in [x for g in gdef.values() for x in g]:
        by_sid.setdefault(s['sid'], []).append(s)
    base_score = cov_bad_with(AREA_POS, POS, samples)
    for sid0, slist in by_sid.items():
        g0 = AREA_POS[sid0]
        best_g, best_cov = g0, 0
        for g in ('W', 'E', 'N'):
            rel = POS[g]
            cov = sum(1 for s in slist if relay_link_ok(s['lon'], s['lat'], s['z'], rel, data))
            if cov > best_cov:
                best_cov, best_g = cov, g
        if best_g != g0 and best_cov == len(slist):
            # 试切换，仅在全量覆盖统计变好时保留
            test = dict(AREA_POS)
            test[sid0] = best_g
            if cov_bad_with(test, POS, samples) < base_score:
                reassign[sid0] = best_g
    AP = dict(AREA_POS)
    for sid0, g in reassign.items():
        AP[sid0] = g
    c2 = cov_bad_with(AP, POS, samples)
    print('after reassign: bad_tasks=%d bad_samples=%d' % c2)
    print('reassigned areas:', reassign)

    os.makedirs(OUTD, exist_ok=True)
    out = {'baseline': {'bad_tasks': c0[0], 'bad_samples': c0[1]},
           'micro_shift': {'pos': POS, 'bad_tasks': c1[0], 'bad_samples': c1[1]},
           'reassign': {'areas': reassign, 'bad_tasks': c2[0], 'bad_samples': c2[1]},
           'relay_pos_final': POS}
    with open(os.path.join(OUTD, 'p3_coverfix.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('saved', os.path.join(OUTD, 'p3_coverfix.json'))


if __name__ == '__main__':
    main()