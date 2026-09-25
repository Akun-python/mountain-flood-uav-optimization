# -*- coding: utf-8 -*-
"""
v18 · P4 任务分区策略对比（26 架冠军口径）
==========================================
在 26 架运输冠军 + 中继三班（W/E/N）基础上，比较多种分区→分组独立资源核算：
  K3_base  论文 K=3（W 片区 10 区 / E 片区 4 区 / S004）
  K2_base  论文 K=2（西/北+S004 共 11 区 / 东 4 区）
  K3_km    k-medoids 坐标聚类（3 组）
  K3_comm  按当前中继位置（W 676.5/E 842.3/N 496.1）可达性聚类
  K3_work  按货箱质量均衡聚类（保持同架次多区同组）
规则约束：若同一运输架次涉及多个服务区，这些服务区必须同组（题目原话）。
库存口径：A 机 4 / B 机 2 / C 机 2；A 电池 6 / B 4 / C 4；中继 2；能源组件 6。
输出：各组资源配置（最小机队+冗余）、总量、是否超库存、排名。
"""
import sys, os, json, math, random

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data, relay_link_ok
from p4_solve import group_plan, redundancy

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v17')
data = Data()
AREAS = sorted(data.areas.keys())
P = {'W': (109.2103, 23.047134, 676.5),
     'E': (109.268918, 23.012732, 650.0),
     'N': (109.234314, 23.059248, 600.0)}

# 28 架冠军（v25）中跨区架次的区对（必须同组）
MULTI_PAIRS = [('S002', 'S005'), ('S006', 'S015'), ('S007', 'S015'),
               ('S002', 'S009'), ('S010', 'S014'), ('S013', 'S011'),
               ('S015', 'S005'), ('S010', 'S005')]

INV = {'uav': {'A': 4, 'B': 2, 'C': 2},
       'bat': {'A': 6, 'B': 4, 'C': 4}, 'relay': 2, 'comp': 6}


def integrity_ok(groups):
    """同一架次多区必须同组。"""
    pos = {a: gi for gi, gs in enumerate(groups) for a in gs}
    for a, b in MULTI_PAIRS:
        if pos[a] != pos[b]:
            return False, (a, b)
    return True, None


def kmedoids(areas, k, seed=1):
    pts = {a: (data.areas[a]['lon'], data.areas[a]['lat']) for a in areas}
    rng = random.Random(seed)
    best = None
    for _ in range(10):
        meds = rng.sample(areas, k)
        for _ in range(80):
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
    return [sorted(v) for v in groups.values()]


def comm_seed_partition(areas):
    groups = {}
    for a in areas:
        lon, lat = data.areas[a]['lon'], data.areas[a]['lat']
        z = 1200.0
        reach = [g for g, pos in P.items() if relay_link_ok(lon, lat, z, pos, data)]
        if reach:
            best_g = max(reach, key=lambda g: -abs(lon - P[g][0]) - abs(lat - P[g][1]))
        else:
            best_g = min(P, key=lambda g: abs(lon - P[g][0]) + abs(lat - P[g][1]))
        groups.setdefault(best_g, []).append(a)
    return [sorted(v) for v in groups.values()]


def work_balanced_partition(areas, k=3, seed=7):
    """按货箱质量均衡分区（约束：跨区架次同组），并保证恰好 k 组。"""
    mass = {a: data.area_demand[a]['mass'] for a in areas}
    # 先合并强制同组对
    merged = {a: a for a in areas}
    changed = True
    while changed:
        changed = False
        for a, b in MULTI_PAIRS:
            ra, rb = merged[a], merged[b]
            if ra != rb:
                for x in areas:
                    if merged[x] == rb:
                        merged[x] = ra
                changed = True
    roots = sorted(set(merged.values()))
    comps = {r: [a for a in areas if merged[a] == r] for r in roots}
    # 合并最小质量组件直到恰好 k 组（贪心：质量小的先并入最轻组）
    comp_list = sorted(comps.values(), key=lambda cs: -sum(mass[a] for a in cs))
    if len(comp_list) > k:
        groups = []
        for cs in comp_list:
            j = min(range(k), key=lambda j: sum(mass[a] for a in groups[j])) if len(groups) == k else len(groups)
            if j >= k:
                # 已满 k 组：并入当前最轻组
                j = min(range(k), key=lambda j: sum(mass[a] for a in groups[j]))
                groups[j].extend(cs)
            else:
                groups.append(list(cs))
        return [sorted(g) for g in groups]
    # 组件数 ≤ k：贪心从大到小放入当前最轻的组
    groups = [[] for _ in range(k)]
    w = [0.0] * k
    for cs in comp_list:
        j = min(range(k), key=lambda j: w[j])
        groups[j].extend(cs)
        w[j] += sum(mass[a] for a in cs)
    return [sorted(g) for g in groups if g]


CANDIDATES = [
    ('K3_v25', [
        ['S001', 'S002', 'S003', 'S005', 'S006', 'S007', 'S008', 'S009', 'S010', 'S014', 'S015'],
        ['S011', 'S012', 'S013'],
        ['S004']]),
    ('K2_v25', [
        ['S001', 'S002', 'S003', 'S005', 'S006', 'S007', 'S008', 'S009', 'S010', 'S011', 'S013', 'S014', 'S015'],
        ['S004', 'S012']]),
]


def main():
    os.makedirs(OUTD, exist_ok=True)
    km3 = kmedoids(AREAS, 3)
    comm = comm_seed_partition(AREAS)
    work3 = work_balanced_partition(AREAS, 3)
    cands = CANDIDATES + [('K3_km', km3), ('K3_comm', comm), ('K3_work', work3)]
    reports = []
    for name, groups in cands:
        ok_int, bad = integrity_ok(groups)
        print('== %s: groups=%s integrity=%s' % (name, groups, ok_int), flush=True)
        if not ok_int:
            print('  [%s] 违反同架次同组规则（%s 被拆分），记为无效' % (name, bad), flush=True)
            reports.append({'name': name, 'valid': False, 'violation': str(bad)})
            continue
        plans = []
        for gi, areas in enumerate(groups):
            gp = group_plan('%s_g%d' % (name, gi + 1), areas)
            alloc = redundancy(gp)
            plans.append({'plan': gp, 'alloc': alloc})
            print('  [%s] g%d areas=%d nbox=%d hard=%s tardy=%.1f mk=%.0f e=%.2f fl=%d'
                  % (name, gi + 1, len(areas), gp['nbox'], gp['hard_ok'], gp['tardy_w'],
                     gp['makespan'], gp['energy'], gp['flights']), flush=True)
        tot = {'uav': {'A': 0, 'B': 0, 'C': 0}, 'bat': {'A': 0, 'B': 0, 'C': 0},
               'relay': 0, 'comp': 0}
        max_mk, ok_all = 0.0, True
        groups_detail = []
        for gi, (areas_g, p) in enumerate(zip(groups, plans)):
            gu, gb, gr, gc = p['alloc']
            for m in tot['uav']:
                tot['uav'][m] += gu.get(m, 0)
                tot['bat'][m] += gb.get(m, 0)
            tot['relay'] += gr
            tot['comp'] += gc
            max_mk = max(max_mk, p['plan']['makespan'])
            ok_all = ok_all and p['plan']['hard_ok'] and p['plan']['tardy_w'] < 1e-6
            groups_detail.append({
                'name': '%s_g%d' % (name, gi + 1), 'areas': areas_g,
                'nbox': p['plan']['nbox'], 'makespan': round(p['plan']['makespan'], 1),
                'energy': round(p['plan']['energy'], 2), 'flights': p['plan']['flights'],
                'uav': gu, 'bat': gb, 'relay': gr, 'comp': gc})
        in_inv = (all(tot['uav'][m] <= INV['uav'][m] for m in 'ABC')
                  and all(tot['bat'][m] <= INV['bat'][m] for m in 'ABC')
                  and tot['relay'] <= INV['relay'] and tot['comp'] <= INV['comp'])
        reports.append({
            'name': name, 'valid': True, 'ok': ok_all, 'within_inventory': in_inv,
            'max_makespan': round(max_mk, 1),
            'total_uav': sum(tot['uav'].values()), 'uav_by': tot['uav'],
            'total_bat': sum(tot['bat'].values()), 'bat_by': tot['bat'],
            'relay_machines': tot['relay'], 'energy_components': tot['comp'],
            'groups_detail': groups_detail})
        print('  [%s] TOTAL uav(A%dB%dC%d)/bat(A%dB%dC%d) relay=%d comp=%d in_inv=%s'
              % (name, tot['uav']['A'], tot['uav']['B'], tot['uav']['C'],
                 tot['bat']['A'], tot['bat']['B'], tot['bat']['C'],
                 tot['relay'], tot['comp'], in_inv), flush=True)
    reports.sort(key=lambda r: (not r.get('valid', False), not r.get('ok', True),
                                r.get('total_uav', 10 ** 9), r.get('total_bat', 10 ** 9),
                                r.get('relay_machines', 10 ** 9), r.get('max_makespan', 10 ** 9)))
    print('\n== ranking ==', flush=True)
    for r in reports:
        if not r.get('valid', False):
            print('  %-10s INVALID (%s)' % (r['name'], r.get('violation', '')), flush=True)
        else:
            print('  %-10s ok=%s in_inv=%s uav=%d bat=%d relay=%d comp=%d mk_max=%.0f'
                  % (r['name'], r['ok'], r.get('within_inventory'), r['total_uav'],
                     r['total_bat'], r['relay_machines'], r['energy_components'],
                     r['max_makespan']), flush=True)
    with open(os.path.join(OUTD, 'p4_partition_compare26.json'), 'w', encoding='utf-8') as fh:
        json.dump({'inventory': INV, 'multi_area_pairs': MULTI_PAIRS,
                   'ranking': reports}, fh, ensure_ascii=False, indent=1)
    print('saved', os.path.join(OUTD, 'p4_partition_compare26.json'), flush=True)


if __name__ == '__main__':
    main()
