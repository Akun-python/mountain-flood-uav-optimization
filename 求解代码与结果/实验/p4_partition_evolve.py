# -*- coding: utf-8 -*-
"""
问题四：任务分区变体实验
在同样运输方案（results/p2_results.json）下，比较多种"分区→分组资源配置"，
按总资源与保障性能排序选择最优分区，突破论文固定 W/E/N 分区的局限。
候选分区：
  K3_base    论文 K=3 分区（W11含S006 / E4 / N1）
  K2_base    论文 K=2 分区（11 / 4）
  K3_km      k-medoids 坐标聚类（3 组，按面积质心）
  K3_comm    通信可达种子分区（各区归可达性最好的中继组）
  K4_km      k-medoids 坐标聚类（4 组）
"""
import sys, os, json, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data, relay_link_ok
from p4_solve import group_plan, redundancy

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v10')
data = Data()
AREAS = sorted(data.areas.keys())
P = {'W': (109.2103, 23.047134, 676.5),
     'E': (109.276017, 23.019401, 542.3),
     'N': (109.238171, 23.077841, 496.1)}


def kmedoids(areas, k, seed=1, iters=80):
    """k-medoids：以 (lon,lat) 坐标聚类（10 个随机初始 + 迭代指派/更新 medoid）。"""
    pts = {a: (data.areas[a]['lon'], data.areas[a]['lat']) for a in areas}
    rng = random.Random(seed)
    best = None
    for _ in range(10):
        meds = rng.sample(areas, k)
        for _ in range(iters):
            assign = {a: min(meds, key=lambda m: (pts[a][0] - pts[m][0]) ** 2
                             + (pts[a][1] - pts[m][1]) ** 2) for a in areas}
            nmed = []
            for m in meds:
                members = [a for a in areas if assign[a] == m]
                if not members:
                    nmed.append(m)
                    continue
                cent = (sum(pts[a][0] for a in members) / len(members),
                        sum(pts[a][1] for a in members) / len(members))
                nmed.append(min(members, key=lambda a: (pts[a][0] - cent[0]) ** 2
                                + (pts[a][1] - cent[1]) ** 2))
            if nmed == meds:
                break
            meds = nmed
        cost = sum(min((pts[a][0] - pts[m][0]) ** 2 + (pts[a][1] - pts[m][1]) ** 2
                       for m in meds) for a in areas)
        if best is None or cost < best[0]:
            best = (cost, {a: assign[a] for a in areas})
    groups = {}
    for a, m in best[1].items():
        groups.setdefault(m, []).append(a)
    return list(groups.values())


def comm_seed_partition(areas):
    """通信种子：各区质心对 3 个中继位置的可达性（Lmax_uav2relay）。"""
    groups = {}
    for a in areas:
        lon = data.areas[a]['lon']
        lat = data.areas[a]['lat']
        z = 1200.0  # 巡航代表高度
        best_g, best = None, -1
        for g, pos in P.items():
            if relay_link_ok(lon, lat, z, pos, data):
                score = 1.0
            else:
                score = 0.0
            # 用接收质量近似（可达优先，退而求其次取最近）
            if score > best:
                best, best_g = score, g
        if best_g is None:
            best_g = min(P, key=lambda g: abs(lon - P[g][0]) + abs(lat - P[g][1]))
        groups.setdefault(best_g, []).append(a)
    return list(groups.values())


CANDIDATES = [
    ('K3_base', [
        ['S001', 'S002', 'S003', 'S005', 'S006', 'S007', 'S008', 'S009', 'S011', 'S015'],
        ['S010', 'S012', 'S013', 'S014'],
        ['S004']]),
    ('K2_base', [
        ['S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007', 'S008', 'S009', 'S011', 'S015'],
        ['S010', 'S012', 'S013', 'S014']]),
]


def main():
    os.makedirs(OUTD, exist_ok=True)
    reports = []
    km3 = kmedoids(AREAS, 3)
    km4 = kmedoids(AREAS, 4)
    comm = comm_seed_partition(AREAS)
    cands = CANDIDATES + [('K3_km', km3), ('K4_km', km4), ('K3_comm', comm)]
    for name, groups in cands:
        plans = []
        for gi, areas in enumerate(groups):
            gp = group_plan('%s_g%d' % (name, gi + 1), areas)
            alloc = redundancy(gp)
            plans.append({'plan': gp, 'alloc': alloc})
            print('  [%s] g%d areas=%d nbox=%d hard=%s tardy=%.1f makespan=%.0f e=%.2f fl=%d uav=%s bats=%s relay=%s sorties=%d'
                  % (name, gi + 1, len(areas), gp['nbox'], gp['hard_ok'], gp['tardy_w'],
                     gp['makespan'], gp['energy'], gp['flights'],
                     gp['uav_by_model'], gp['bat_by_model'],
                     gp['relay_positions'], gp['relay_sorties']))
        # 汇总
        tot = {'uav': {'A': 0, 'B': 0, 'C': 0}, 'bat': {'A': 0, 'B': 0, 'C': 0},
               'relay': 0, 'comp': 0, 'uav12': 0, 'bat12': 0}
        max_tardy = 0.0
        max_mk = 0.0
        ok = True
        for p in plans:
            gu, gb, gr, gc = p['alloc']
            for m in tot['uav']:
                tot['uav'][m] += gu.get(m, 0)
                tot['bat'][m] += gb.get(m, 0)
            tot['relay'] += gr
            tot['comp'] += gc
            tot['uav12'] += sum(gu.values())
            tot['bat12'] += sum(gb.values())
            max_tardy = max(max_tardy, p['plan']['tardy_w'])
            max_mk = max(max_mk, p['plan']['makespan'])
            ok = ok and p['plan']['hard_ok'] and p['plan']['tardy_w'] < 1e-6
        # 库存校验：A4 B2 C2
        budget_ok = (tot['uav']['A'] <= 4 and tot['uav']['B'] <= 2 and tot['uav']['C'] <= 2
                     and tot['bat']['A'] <= 12 and tot['bat']['B'] <= 8 and tot['bat']['C'] <= 8)
        # 逐组明细（含冗余备份后的资源配置），供论文 tab:p4 使用
        groups_detail = []
        for gi, (areas_g, p) in enumerate(zip(groups, plans)):
            gu, gb, gr, gc = p['alloc']
            groups_detail.append({
                'name': '%s_g%d' % (name, gi + 1),
                'areas': [a for a in areas_g],
                'nbox': p['plan']['nbox'],
                'makespan': round(p['plan']['makespan'], 1),
                'energy': round(p['plan']['energy'], 2),
                'flights': p['plan']['flights'],
                'uav': gu, 'bat': gb, 'relay': gr, 'comp': gc,
            })
        reports.append({
            'name': name, 'groups': [g for g in groups],
            'ok': ok, 'budget_ok': budget_ok,
            'max_tardy': round(max_tardy, 1), 'max_makespan': round(max_mk, 1),
            'total_uav_after_redundancy': sum(tot['uav'].values()),
            'total_bat_after_redundancy': sum(tot['bat'].values()),
            'uav_by': tot['uav'], 'bat_by': tot['bat'],
            'relay_machines': tot['relay'], 'energy_components': tot['comp'],
            'groups_detail': groups_detail,
        })
        print('  [%s] TOTAL uav(A%dB%dC%d)/bat(A%dB%dC%d) relay=%d comp=%d ok=%s budget=%s'
              % (name, tot['uav']['A'], tot['uav']['B'], tot['uav']['C'],
                 tot['bat']['A'], tot['bat']['B'], tot['bat']['C'],
                 tot['relay'], tot['comp'], ok, budget_ok))
    reports.sort(key=lambda r: (not r['ok'], r['total_uav_after_redundancy'],
                                r['total_bat_after_redundancy'],
                                r['relay_machines'], r['max_makespan']))
    print('\n== ranking ==')
    for r in reports:
        print('  %-10s ok=%s budget=%s uav=%d bat=%d relay=%d mk_max=%.0f'
              % (r['name'], r['ok'], r['budget_ok'], r['total_uav_after_redundancy'],
                 r['total_bat_after_redundancy'], r['relay_machines'], r['max_makespan']))
    with open(os.path.join(OUTD, 'p4_partition_evolve_v10.json'), 'w', encoding='utf-8') as fh:
        json.dump({'ranking': reports}, fh, ensure_ascii=False, indent=1)
    print('saved', os.path.join(OUTD, 'p4_partition_evolve_v10.json'))


if __name__ == '__main__':
    main()