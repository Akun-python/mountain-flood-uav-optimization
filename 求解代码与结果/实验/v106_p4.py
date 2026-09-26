# -*- coding: utf-8 -*-
"""v106：问题四重做——基于25架冠军(+v92中继)的 2/3 组分区 × 独立资源核算 × 库存缺口。
每组独立配置：运输机(同时占用峰值)、电池(该组机型周转)、中继(该组服务时段)、组件。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from p2v28_compliant import dispatch_compliant
from collections import Counter
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
sch, _ = dispatch_compliant(data, fls)
pv = json.load(open(os.path.join(OUTD, 'p3v92_review.json'), encoding='utf-8'))
relay_times = {s['pos']: (s['t0'], s['t1']) for s in pv['sorties']}
print('中继时段:', relay_times)
STOCK = {'A': {'uav': 4, 'bat': 6}, 'B': {'uav': 2, 'bat': 4}, 'C': {'uav': 2, 'bat': 4}}
RELAY_STOCK = {'uav': 2, 'comp': 6}

def zone_of(f):
    return [z for z, _ in f.route]

def group_resources(zones, name):
    gfl = [f for f in fls if any(z in zones for z in zone_of(f))]
    # 运输机：该组趟按机型单独排时间轴，同时占用峰值（同机不能同时飞——用时间轴重叠：全部趟重叠即并行需求——保守：独立调度时无跨组——组内并行 = 组内趟最大重叠数）
    need = {}
    for gm in 'ABC':
        tlist = sorted((sch[f.fid]['start'], sch[f.fid]['return']) for f in gfl if f.model == gm)
        peak = 0
        import heapq
        h = []
        for st, rt in tlist:
            while h and h[0] <= st: heapq.heappop(h)
            heapq.heappush(h, rt)
            peak = max(peak, len(h))
        need[gm] = {'flights': len(tlist), 'peak': max(peak, 1) if tlist else 0}
    # 电池：组内该机型趟的重叠+周转——简化用"同时峰值 × 该机型电池链"估算：每组独立时电池组数 = max(同时使用) + 周转缓冲
    bat_need = {gm: (need[gm]['peak'] + (1 if need[gm]['flights'] > need[gm]['peak'] else 0)) for gm in 'ABC'}
    # 中继：该组区覆盖的 W/E/N 时段（区含 S004 或 S010/S012/S013/S014 等）
    rz = set()
    for z in zones:
        for g, (t0, t1) in relay_times.items():
            # 简化：S004→N, E区(S010/S012/S013/S014)→E, W区→W
            if z == 'S004' and g == 'N': rz.add(g)
            elif z in ('S010', 'S012', 'S013', 'S014') and g == 'E': rz.add(g)
            elif g == 'W' and z not in ('S004', 'S010', 'S012', 'S013', 'S014', 'S006'): rz.add(g)
    # 中继同时段重叠
    rl = [(relay_times[g][0], relay_times[g][1]) for g in rz]
    hp = 0; hh = []
    for st, rt in sorted(rl):
        while hh and hh[0] <= st: heapq.heappop(hh)
        heapq.heappush(hh, rt); hp = max(hp, len(hh))
    n_relay = max(hp, 1) if rz else 0
    n_comp = n_relay * 1  # 每架中继1满充组件在役（6组件库内）
    # 工作负载
    boxes = sum(len(f.box_ids) for f in gfl)
    tspan = max((sch[f.fid]['return'] for f in gfl), default=0)
    return {'flights': len(gfl), 'boxes': boxes, 'tspan': round(tspan),
            'uav': need, 'bat': bat_need, 'relay': n_relay, 'comp': n_comp}

# 2 组（满足 f37/f38 约束）
g2A = ['S001','S002','S003','S005','S007','S008','S009','S011','S015']  # W + S011(随S005)
g2B = ['S004','S006','S010','S012','S013','S014']                        # E + N + S006(随S014)
# 3 组
g3W = ['S001','S002','S003','S005','S007','S008','S009','S011','S015']
g3E = ['S006','S010','S012','S013','S014']
g3N = ['S004']
for name, zones, cfg in [('2组A(W)', g2A, 'g2'), ('2组B(E+N)', g2B, 'g2'), ('3组W', g3W, 'g3'), ('3组E', g3E, 'g3'), ('3组N', g3N, 'g3')]:
    r = group_resources(zones, name)
    print('%s: 趟%d 箱%d 活动时长%.0fs | 运输机需求 A%d B%d C%d | 电池 A%d B%d C%d | 中继%d 组件%d' % (
        name, r['flights'], r['boxes'], r['tspan'],
        r['uav']['A']['peak'], r['uav']['B']['peak'], r['uav']['C']['peak'],
        r['bat']['A'], r['bat']['B'], r['bat']['C'], r['relay'], r['comp']))
print()
# 库存缺口核算
def gap(part, label):
    print('== %s ==' % label)
    tot_uav = Counter(); tot_bat = Counter(); tot_rel = 0; tot_comp = 0
    for name, zones in part:
        r = group_resources(zones, name)
        for gm in 'ABC':
            tot_uav[gm] += r['uav'][gm]['peak']; tot_bat[gm] += r['bat'][gm]
        tot_rel += r['relay']; tot_comp += r['comp']
    for gm in 'ABC':
        print('  %s机: 需求%d 库存%d %s' % (gm, tot_uav[gm], STOCK[gm]['uav'], '超%d' % (tot_uav[gm]-STOCK[gm]['uav']) if tot_uav[gm]>STOCK[gm]['uav'] else 'OK'))
    for gm in 'ABC':
        print('  %s电池: 需求%d 库存%d %s' % (gm, tot_bat[gm], STOCK[gm]['bat'], '超%d' % (tot_bat[gm]-STOCK[gm]['bat']) if tot_bat[gm]>STOCK[gm]['bat'] else 'OK'))
    print('  中继: 需求%d 库存%d %s' % (tot_rel, RELAY_STOCK['uav'], '超%d' % (tot_rel-RELAY_STOCK['uav']) if tot_rel>RELAY_STOCK['uav'] else 'OK'))
    print('  组件: 需求%d 库存%d %s' % (tot_comp, RELAY_STOCK['comp'], '超%d' % (tot_comp-RELAY_STOCK['comp']) if tot_comp>RELAY_STOCK['comp'] else 'OK'))
gap([('2组A', g2A), ('2组B', g2B)], '2组')
gap([('3组W', g3W), ('3组E', g3E), ('3组N', g3N)], '3组')
