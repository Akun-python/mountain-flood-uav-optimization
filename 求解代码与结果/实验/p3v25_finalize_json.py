# -*- coding: utf-8 -*-
"""由 p3v25_final.json（偏移派单）生成 results/p3_final.json（图脚本输入格式）。
flights/schedule 来自偏移后 28 行；sorties 为 4 班（R01 西点 W1，R02 东/北/西尾段）。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
EVO = os.path.join(HERE, '..', '结果', '进化_v25')
p2 = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
fin = json.load(open(os.path.join(EVO, 'p3v25_final.json'), encoding='utf-8'))

flights = []
schedule = {}
for r in fin['rows']:
    fj = next(x for x in p2['flights'] if x['fid'] == r['fid'])
    flights.append({'fid': r['fid'], 'model': r['model'],
                    'route': fj['route']})
    schedule[str(r['fid'])] = {'start': r['start'], 'return': r['return'],
                               'uav': r['uav']}

BANDS = [('R01', 'W', 1058, 7453, 2.184),
         ('R02', 'E', 1060, 5498, 1.549),
         ('R02', 'N', 6565, 7308, 0.488),
         ('R02', 'W', 8605, 9072, 0.372)]
seg = fin['seg']
sorties = []
for relay, pos, t0, t1, energy in BANDS:
    ns = sum(1 for s in seg.get(pos, []) if t0 <= s[0] < t1)
    sorties.append({'relay': relay, 'pos': pos, 't0': t0, 't1': t1,
                    'energy': energy, 'missions': ['x'] * max(1, ns),
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