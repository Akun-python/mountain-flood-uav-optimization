# -*- coding: utf-8 -*-
"""重建 p4_results.json（26 架冠军口径的分区核算），供 advanced_figures fig4_gap/fig4_load 使用。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Data

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
data = Data()

# 26 架冠军口径的逐组核算（来自 p4_partition_evolve_v10.json）
ALLOC = {
    '3': [
        {'name': 'G1', 'areas': ['S001','S002','S003','S005','S006','S007','S008','S009','S011','S015'],
         'uav': {'A': 3, 'B': 3, 'C': 3}, 'bat': {'A': 4, 'B': 4, 'C': 4}, 'relay': 3, 'comp': 5, 'mk': 8006},
        {'name': 'G2', 'areas': ['S010','S012','S013','S014'],
         'uav': {'A': 3, 'B': 2, 'C': 2}, 'bat': {'A': 4, 'B': 3, 'C': 3}, 'relay': 3, 'comp': 5, 'mk': 5182},
        {'name': 'G3', 'areas': ['S004'],
         'uav': {'A': 2, 'B': 2, 'C': 2}, 'bat': {'A': 2, 'B': 2, 'C': 2}, 'relay': 3, 'comp': 3, 'mk': 4007},
    ],
    '2': [
        {'name': 'G1', 'areas': ['S001','S002','S003','S004','S005','S006','S007','S008','S009','S011','S015'],
         'uav': {'A': 3, 'B': 3, 'C': 3}, 'bat': {'A': 4, 'B': 4, 'C': 4}, 'relay': 3, 'comp': 6, 'mk': 9258},
        {'name': 'G2', 'areas': ['S010','S012','S013','S014'],
         'uav': {'A': 3, 'B': 2, 'C': 2}, 'bat': {'A': 4, 'B': 3, 'C': 3}, 'relay': 3, 'comp': 5, 'mk': 5182},
    ],
}
INV = {'A': 4, 'B': 2, 'C': 2, 'A_bat': 6, 'B_bat': 4, 'C_bat': 4, 'relay': 2, 'comp': 6}


def group_mass(areas):
    return sum(bx['mass'] for bx in data.boxes.values() if bx['area'] in areas)


out = {'inventory': INV}
for K, gs in ALLOC.items():
    groups = []
    for g in gs:
        groups.append({
            'name': g['name'], 'areas': g['areas'],
            'nbox': sum(1 for bx in data.boxes.values() if bx['area'] in g['areas']),
            'mass': round(group_mass(g['areas']), 1),
            'alloc_uav': g['uav'], 'alloc_bat': g['bat'],
            'alloc_relay': g['relay'], 'alloc_comp': g['comp'],
            'makespan': g['mk'],
        })
    out[K] = {'groups': groups}
json.dump(out, open(os.path.join(RES, 'p4_results.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('p4_results.json rebuilt:')
for K in ('2', '3'):
    for g in out[K]['groups']:
        print('  K=%s %s nbox=%d mass=%.1f uav=%s relay=%d comp=%d mk=%d'
              % (K, g['name'], g['nbox'], g['mass'], g['alloc_uav'], g['alloc_relay'],
                 g['alloc_comp'], g['makespan']))