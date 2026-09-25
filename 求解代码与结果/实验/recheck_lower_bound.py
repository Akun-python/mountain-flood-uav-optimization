# -*- coding: utf-8 -*-
"""独立复核问题二完工下界论证（v19 LB1/LB2）并检验"对方 23 架 / 94.897 min 违反下界"
的论断是否成立。
下界定义：
  LB2(g) = T_g / N_g   （机型 g 累计飞行时长 / 该机型无人机数）——合法弱下界
  LB_total = T_total / 8  （全部飞行时长 / 8 架无人机）——更松的全局下界
关键逻辑：LB2 是对"给定方案的机型任务时长"成立，不同方案机型分布不同，
下界值也不同；不能用我们 26 架方案的 LB2 否证对方 23 架方案。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data
from common import make_initial
import p2_solve as P2

data = Data()
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', 'p2_results.json'), encoding='utf-8'))

# 每架次飞行时间 = 调度占用（return - start 去掉准备/交接）——
# 用 core 的 flight 计算更准：对每个架次 route 重算纯飞行时长
def flight_time(f, data):
    p = data.uav_types[f['model']]
    o = data.centers[data.OID]
    t = 0.0
    nodes = [(o['lon'], o['lat'], o['alt'])]
    for sid, _ in f['route']:
        nodes.append((data.areas[sid]['lon'], data.areas[sid]['lat'], data.op_alt[sid]))
    nodes.append((o['lon'], o['lat'], o['alt']))
    for i in range(len(nodes) - 1):
        z1, z2 = nodes[i][2], nodes[i + 1][2]
        geo = segment_geometry(
            nodes[i][0], nodes[i][1], z1, nodes[i + 1][0], nodes[i + 1][1], z2, data)
        # geo = (d_m, cruise_alt, h_up, h_down)；巡航距离 = d_m
        t += geo[2] / p['v_up'] + geo[0] / p['v_c'] + geo[3] / p['v_down']
    return t

from core import segment_geometry
T = {'A': 0.0, 'B': 0.0, 'C': 0.0}
N = {'A': 4, 'B': 2, 'C': 2}
rows = []
for f in d['flights']:
    tf = flight_time(f, data)
    T[f['model']] += tf
    rows.append((f['fid'], f['model'], round(tf, 1), round(f['return'], 1)))
T_total = sum(T.values())
print('== 当前基线（v24 plan-D, 26 架 A12/B7/C7, makespan %.1f s, energy %.2f kWh）==' % (d['metrics']['makespan'], d['metrics']['energy']))
print('机型累计飞行时长 T_A=%.1f  T_B=%.1f  T_C=%.1f  总=%.1f' % (T['A'], T['B'], T['C'], T_total))
print('LB2 机型负载均衡下界:  A:%.1f  B:%.1f  C:%.1f  -> max=%.1f s (%.2f min)' % (
    T['A'] / N['A'], T['B'] / N['B'], T['C'] / N['C'], max(T['A'] / N['A'], T['B'] / N['B'], T['C'] / N['C']),
    max(T['A'] / N['A'], T['B'] / N['B'], T['C'] / N['C']) / 60.0))
print('LB_total 全局下界 = %.1f s (%.2f min)' % (T_total / 8.0, T_total / 8.0 / 60.0))
print('完工 6896.5 与 LB_total 差距 = %.1f s (%.1f%%)' % (d['metrics']['makespan'] - T_total / 8.0, (d['metrics']['makespan'] - T_total / 8.0) / (T_total / 8.0) * 100))

print()
print('== 对方假设检验（23 架 / 5694 s / 67.14 kWh）==')
print('对方完工 C=5694 s 成立的必要条件（合法弱下界，不含等待/充电/准备）：')
print('  ① 总飞行时长 T_total_opp <= 8*C = %.0f s' % (8 * 5694))
print('  ② 各机型累计 <= N_g*C：A<=22776  B<=11388  C<=11388 s')
print('我们 26 架 T_total=%.0f；23 架若省 3 个 A 型短架次(~3×2045s) -> ~%.0f s' % (T_total, T_total - 3 * 2045))
print('  若对方 B 机 6 架次(~6 x 1806 s = %.0f s) <= 11388 s 成立；C 机 6 架次(~6 x 1813 s = %.0f s) <= 11388 s 成立' % (6 * 1806, 6 * 1813))
print('=> 下界不构成对对方 94.9 min 的否证；此前"低于下界 10%"的论断系把"我们方案'
      '的 LB2"误当"全局下界"，应修正为"需对方明细逐架复核"。')