# -*- coding: utf-8 -*-
"""由 p3v42_final.json（29 架基线，无偏移）生成 results/p3_final.json（图脚本输入）。
flights/schedule 来自 29 行；sorties 为 3 班（R01 西点，R02 东点/北点）。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
EVO = os.path.join(HERE, '..', '结果', '进化_v42')
p2 = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
fin = json.load(open(os.path.join(EVO, 'p3v42_final.json'), encoding='utf-8'))

flights = []
schedule = {}
for r in fin['rows']:
    fj = next(x for x in p2['flights'] if x['fid'] == r['fid'])
    flights.append({'fid': r['fid'], 'model': r['model'],
                    'route': fj['route']})
    schedule[str(r['fid'])] = {'start': r['start'], 'return': r['return'],
                               'uav': r['uav']}

seg = fin['seg']
sorties = []
for s in fin['sorties']:
    ns = sum(1 for ss in seg.get(s['pos'], []) if s['t0'] <= ss[0] < s['t1'])
    sorties.append({'relay': s['relay'], 'pos': s['pos'], 't0': s['t0'], 't1': s['t1'],
                    'energy': s['energy'], 'missions': ['x'] * max(1, ns),
                    'n': ns})

out = {'flights': flights, 'schedule': schedule, 'sorties': sorties,
       'met': {k: (round(v, 2) if isinstance(v, float) else v)
               for k, v in fin['met'].items() if k != 'box_time'}}
json.dump(out, open(os.path.join(RES, 'p3_final.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved p3_final.json  flights=%d sorties=%d' % (len(flights), len(sorties)))
for s in sorties:
    print('  %s %s [%d, %d] e=%.3f 段=%d' % (s['relay'], s['pos'], s['t0'], s['t1'],
                                            s['energy'], s['n']))