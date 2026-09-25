# -*- coding: utf-8 -*-
"""
v17 · P3 中继覆盖-能耗联合优化（26 架冠军口径，三框架对比）
============================================================
在"组归属样本零覆盖缺口 + 回程链路可行"约束下，为 W/E/N 三班中继搜索
使中继总能耗最低的悬停位置。对比三种框架：
  A. 基线固定位置（W 676.5 / E 842.3 / N 496.1，论文当前口径）
  B. 局域网格搜索（与 p3_relay_opt 同款，但服务窗口按 26 架冠军）
  C. 随机重启 + 局域爬山（200 随机初始点 × 局部下降）
输出对比表并保存至 结果/进化_v17/p3_relay_opt26.json。
"""
import sys, os, json, math, random

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (Data, direct_ok, relay_link_ok, relay_backhaul_ok,
                  relay_mission_energy, path_loss)
from p3_gaps import flight_trajectory
from p2_solve import Flight
from p3_co2 import P_W, P_E, P_N  # 官方位置（p3_co2.py 口径）

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v17')

# 26 架冠军的三班窗口（s）：W [1078,6802]=5724、E [1406,4074]=2668、N [5894,6446]=552
SERVE = {'W': 5724.0, 'E': 2668.0, 'N': 552.0}

POS0 = {'W': P_W, 'E': P_E, 'N': P_N}   # 与 p3_co2.py 完全一致

AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'

RNG = random.Random(20260925)


def h_over_terrain_ok(pos):
    """悬停离地高度不得超过 300 m（题目中继数据表上限）。"""
    t = data.dem_at(pos[0], pos[1])
    if math.isnan(t):
        return True  # DEM 外按回程/接入判定兜底
    return pos[2] - t <= 300.0 + 1e-6


def build_samples(data):
    """读 26 架冠军（surgical_fix 修复后的架次结构）+ p3_co2 偏移，沿航线 30m 采样需中继点。
    必须使用 Solver() 内部的修复后架次（与 p3_co2 官方判定同源），而非原始 p2_results 架次。"""
    from p3_co2 import Solver as _Solver
    sv = _Solver()
    samples = []
    for f in sv.flights:
        pts, _ = flight_trajectory(f, f.start0)
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            sid = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                              data.areas[s]['lon'], data.areas[s]['lat']))
            samples.append({'fid': f.fid, 't': pt['t'], 'sid': sid,
                            'lon': pt['lon'], 'lat': pt['lat'], 'z': pt['z']})
    by_g = {g: [s for s in samples if AREA_POS.get(s['sid']) == g] for g in 'WEN'}
    return samples, by_g


def subsample(ss, k=3):
    """搜索用抽样（每 k 个取 1）；最终验证仍用全量样本。"""
    return ss[::k]


def gap_of_group(g, pos, by_g, sample_pool=None):
    n = 0
    pool = by_g[g] if sample_pool is None else sample_pool
    for s in pool:
        if not relay_link_ok(s['lon'], s['lat'], s['z'], pos, data):
            n += 1
    return n


def e_at(g, pos):
    return relay_mission_energy(pos[0], pos[1], pos[2], data, SERVE[g])


def feasible(g, pos, by_g, sample_pool=None):
    return (h_over_terrain_ok(pos)
            and gap_of_group(g, pos, by_g, sample_pool) == 0
            and relay_backhaul_ok(pos, data))


# ---- 框架 B：局域网格搜索 ----
def grid_search(g, pos, by_g, sample_pool):
    bx, by_, bz = pos
    best = None
    for dlon in (-0.016, -0.012, -0.008, -0.004, 0, 0.004, 0.008, 0.012, 0.016):
        for dlat in (-0.016, -0.012, -0.008, -0.004, 0, 0.004, 0.008, 0.012, 0.016):
            for z in (450, 500, 550, 650, 750, 850, 950, 1050, 1150):
                cand = (bx + dlon, by_ + dlat, z)
                if not feasible(g, cand, by_g, sample_pool):
                    continue
                e = e_at(g, cand)
                if best is None or e < best[0]:
                    best = (e, cand)
    return best


# ---- 框架 C：随机重启 + 局域爬山 ----
def hill_climb(g, pos, by_g, sample_pool, iters=120):
    cur = pos
    cur_e = e_at(g, cur)
    if not feasible(g, cur, by_g, sample_pool):
        cur_e = float('inf')
    for _ in range(iters):
        lon, lat, z = cur
        cand = (round(lon + RNG.uniform(-0.004, 0.004), 6),
                round(lat + RNG.uniform(-0.004, 0.004), 6),
                z + RNG.choice((-150, -50, 0, 50, 150)))
        if not feasible(g, cand, by_g, sample_pool):
            continue
        e = e_at(g, cand)
        if e < cur_e:
            cur, cur_e = cand, e
    return (cur_e, cur) if math.isfinite(cur_e) else None


def random_restart_search(g, pos, by_g, sample_pool, restarts=40, iters=120):
    best = None
    bx, by_, bz = pos
    for _ in range(restarts):
        start = (round(bx + RNG.uniform(-0.015, 0.015), 6),
                 round(by_ + RNG.uniform(-0.015, 0.015), 6),
                 RNG.choice((500, 650, 800, 950, 1100)))
        r = hill_climb(g, start, by_g, sample_pool, iters)
        if r is not None and (best is None or r[0] < best[0]):
            best = r
    return best


def build_original_samples(data):
    """按 margin_stats 口径（原始 26 架 + 偏移）构建需中继采样点，用于余量门限。"""
    p2 = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
    flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
               for fj in p2['flights']]
    base = {fj['fid']: float(fj['start']) for fj in p2['flights']}
    off = {}
    off_p = os.path.join(RES, 'p3_co2.json')
    if os.path.exists(off_p):
        r3 = json.load(open(off_p, encoding='utf-8'))
        off = {int(k): float(v) for k, v in r3.get('offsets', {}).items()}
    samples = []
    for f in flights:
        pts, _ = flight_trajectory(f, base[f.fid] + off.get(f.fid, 0.0))
        for pt in pts:
            if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                continue
            sid = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                              data.areas[s]['lon'], data.areas[s]['lat']))
            samples.append({'fid': f.fid, 'sid': sid,
                            'lon': pt['lon'], 'lat': pt['lat'], 'z': pt['z']})
    by_g = {g: [s for s in samples if AREA_POS.get(s['sid']) == g] for g in 'WEN'}
    return samples, by_g


def min_margin_db(g, pos, orig_pool):
    """该组原始采样点最紧接入余量 = 116 - max(path_loss)。
    注意：路径损耗越大余量越小，必须取 path_loss 的最大值（最初
    取最小值的写法返回的是最松余量，曾导致 D 框架约束失效）。"""
    ml = -1e9
    for s in orig_pool:
        l = path_loss(s['lon'], s['lat'], s['z'], pos[0], pos[1], pos[2], data)
        if l > ml:
            ml = l
    return 116.0 - ml


# ---- 框架 D：余量约束（min margin >= MARGIN_MIN）爬山 ----
MARGIN_MIN = 1.0

def hill_climb_margin(g, pos, by_g, orig_by_g, sample_pool, iters=150):
    cur = pos
    cur_e = e_at(g, cur)
    if not (feasible(g, cur, by_g, sample_pool)
            and min_margin_db(g, cur, orig_by_g[g]) >= MARGIN_MIN):
        cur_e = float('inf')
    for _ in range(iters):
        lon, lat, z = cur
        cand = (round(lon + RNG.uniform(-0.003, 0.003), 6),
                round(lat + RNG.uniform(-0.003, 0.003), 6),
                z + RNG.choice((-100, -50, 0, 50, 100)))
        if not (feasible(g, cand, by_g, sample_pool)
                and min_margin_db(g, cand, orig_by_g[g]) >= MARGIN_MIN):
            continue
        e = e_at(g, cand)
        if e < cur_e:
            cur, cur_e = cand, e
    return (cur_e, cur) if math.isfinite(cur_e) else None


def random_restart_margin(g, pos, by_g, orig_by_g, sample_pool, restarts=30, iters=150):
    best = None
    bx, by_, bz = pos
    for _ in range(restarts):
        start = (round(bx + RNG.uniform(-0.006, 0.006), 6),
                 round(by_ + RNG.uniform(-0.006, 0.006), 6),
                 RNG.choice((450, 500, 550, 650, 750, 850)))
        r = hill_climb_margin(g, start, by_g, orig_by_g, sample_pool, iters)
        if r is not None and (best is None or r[0] < best[0]):
            best = r
    return best


def main():
    global data
    data = Data()
    samples, by_g = build_samples(data)
    orig_samples, orig_by_g = build_original_samples(data)
    print('need-relay samples:', len(samples), flush=True)
    for g in 'WEN':
        print('  group %s samples=%d  serve=%.0f s' % (g, len(by_g[g]), SERVE[g]), flush=True)

    cur_e = sum(e_at(g, POS0[g]) for g in 'WEN')
    cur_gap = 0
    for g in 'WEN':
        gg = gap_of_group(g, POS0[g], by_g)
        cur_gap += gg
        print('  baseline %s gaps=%d e=%.3f  mmargin=%.2f dB'
              % (g, gg, e_at(g, POS0[g]), min_margin_db(g, POS0[g], orig_by_g[g])), flush=True)
    print('A. baseline: total_e=%.3f kWh  gaps=%d' % (cur_e, cur_gap), flush=True)

    out = {'frameworkA_baseline': {'pos': POS0, 'energy': round(cur_e, 3), 'gaps': cur_gap},
           'frameworkB_grid': {}, 'frameworkC_restart_hill': {},
           'frameworkD_margin1dB': {}}

    grid_total = 0.0
    hill_total = 0.0
    margin_total = 0.0
    for g in 'WEN':
        pool = subsample(by_g[g], k=3)
        rg = grid_search(g, POS0[g], by_g, pool)
        rh = random_restart_search(g, POS0[g], by_g, pool)
        rd = random_restart_margin(g, POS0[g], by_g, orig_by_g, pool)
        for name, r in (('B', rg), ('C', rh), ('D', rd)):
            if r is None:
                continue
            e, cand = r
            # 用全量样本复核零缺口
            full_gap = gap_of_group(g, cand, by_g)
            if full_gap > 0:
                print('  WARN %s.%s full-gap=%d, reject' % (name, g, full_gap), flush=True)
                continue
            mm_db = min_margin_db(g, cand, orig_by_g[g])
            if name == 'B':
                grid_total += e
                out['frameworkB_grid'][g] = {'pos': cand, 'energy': round(e, 3),
                                             'min_margin_db': round(mm_db, 2),
                                             'backhaul': bool(relay_backhaul_ok(cand, data))}
                print('  B.%s -> %s e=%.3f (was %.3f) mmargin=%.2f'
                      % (g, tuple(round(x, 3) for x in cand), e, e_at(g, POS0[g]), mm_db), flush=True)
            elif name == 'C':
                hill_total += e
                out['frameworkC_restart_hill'][g] = {'pos': cand, 'energy': round(e, 3),
                                                     'min_margin_db': round(mm_db, 2),
                                                     'backhaul': bool(relay_backhaul_ok(cand, data))}
                print('  C.%s -> %s e=%.3f mmargin=%.2f'
                      % (g, tuple(round(x, 3) for x in cand), e, mm_db), flush=True)
            else:
                if mm_db < MARGIN_MIN - 1e-9:
                    print('  WARN D.%s margin=%.2f < %g, reject' % (g, mm_db, MARGIN_MIN), flush=True)
                    continue
                margin_total += e
                out['frameworkD_margin1dB'][g] = {'pos': cand, 'energy': round(e, 3),
                                                  'min_margin_db': round(mm_db, 2),
                                                  'backhaul': bool(relay_backhaul_ok(cand, data))}
                print('  D.%s -> %s e=%.3f mmargin=%.2f (>=1dB)'
                      % (g, tuple(round(x, 3) for x in cand), e, mm_db), flush=True)

    out['frameworkB_grid']['total_energy'] = round(grid_total, 3)
    out['frameworkC_restart_hill']['total_energy'] = round(hill_total, 3)
    out['frameworkD_margin1dB']['total_energy'] = round(margin_total, 3)
    out['summary'] = {
        'baseline_kwh': round(cur_e, 3),
        'grid_kwh': round(grid_total, 3),
        'restart_hill_kwh': round(hill_total, 3),
        'margin1dB_kwh': round(margin_total, 3),
        'grid_saving_kwh': round(cur_e - grid_total, 3),
        'hill_saving_kwh': round(cur_e - hill_total, 3),
        'margin1dB_saving_kwh': round(cur_e - margin_total, 3),
        'note': '服务窗口按 26 架冠军：W 5724 / E 2668 / N 552 s；框架 D 要求最紧接入余量 >= 1 dB（margin_stats 口径）',
    }
    print('summary:', json.dumps(out['summary'], ensure_ascii=False), flush=True)
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'p3_relay_opt26.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('saved', os.path.join(OUTD, 'p3_relay_opt26.json'), flush=True)


if __name__ == '__main__':
    main()
