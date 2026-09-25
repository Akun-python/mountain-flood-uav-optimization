# -*- coding: utf-8 -*-
"""重建 p4_results.json（v25 分区核算，来自 p4_partition_compare26.json），
供 advanced_figures fig4_gap/fig4_load 使用。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
EVO17 = os.path.join(HERE, '..', '结果', '进化_v17')
data = Data()

com = json.load(open(os.path.join(EVO17, 'p4_partition_compare26.json'), encoding='utf-8'))
K2 = next(r for r in com['ranking'] if r['name'] == 'K2_v25')
K3 = next(r for r in com['ranking'] if r['name'] == 'K3_v25')

def to_groups(kr):
    out = []
    for i, g in enumerate(kr['groups_detail']):
        uv = {t: g['uav'].get(t, 0) for t in 'ABC'}
        bt = {t: g['bat'].get(t, 0) for t in 'ABC'}
        out.append({'name': 'G%d' % (i + 1), 'areas': g['areas'],
                    'nbox': g['nbox'], 'mass': 0.0,
                    'alloc_uav': uv, 'alloc_bat': bt,
                    'alloc_relay': g['relay'], 'alloc_comp': g['comp'],
                    'makespan': round(g['makespan'])})
    return out

INV = {'A': 4, 'B': 2, 'C': 2, 'A_bat': 6, 'B_bat': 4, 'C_bat': 4, 'relay': 2, 'comp': 6}
out = {'inventory': INV, '2': {'groups': to_groups(K2)}, '3': {'groups': to_groups(K3)}}
for K, kr in (('2', K2), ('3', K3)):
    for g, gd in zip(out[K]['groups'], kr['groups_detail']):
        g['mass'] = round(sum(bx['mass'] for bx in data.boxes.values()
                              if bx['area'] in gd['areas']), 1)
json.dump(out, open(os.path.join(RES, 'p4_results.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('p4_results.json rebuilt (v25):')
for K in ('2', '3'):
    for g in out[K]['groups']:
        print('  K=%s %s nbox=%d mass=%.1f uav=%s relay=%d comp=%d mk=%d'
              % (K, g['name'], g['nbox'], g['mass'], g['alloc_uav'], g['alloc_relay'],
                 g['alloc_comp'], g['makespan']))