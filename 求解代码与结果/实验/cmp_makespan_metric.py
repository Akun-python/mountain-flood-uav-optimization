# -*- coding: utf-8 -*-
"""按两种口径重算问题二冠军完工时间：
口径 A = 最后架次返场 O01（论文口径）；
口径 B = 最后投送完成（多数优秀项目口径），= 到达最后服务区 + 该区交接。
对比后给出同口径差值，用于与 23架/94.897min/67.14kWh 项目公平对比。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data, segment_geometry, flight_time_with_handover

data = Data()
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', 'p2_results.json'), encoding='utf-8'))
fls = d['flights']

max_return = 0.0
max_deliver = 0.0
last_rows = []
for f in fls:
    p = data.uav_types[f['model']]
    route = f['route']
    # 返场口径：用计算出的 return 与字段 return 取 max
    ret_f = f['return']
    max_return = max(max_return, ret_f)
    # 投送完成口径：最后服务区的到达+交接完成时刻 = ret_f - (最后服务区→O01 返场飞行)
    sid, boxes = route[-1]
    c = data.areas[sid]
    o = data.centers[data.OID]
    ret_geo = segment_geometry(c['lon'], c['lat'], data.op_alt[sid], o['lon'], o['lat'], o['alt'], data)
    t_back = ret_geo[1] / p['v_c'] + ret_geo[2] / p['v_up'] + ret_geo[3] / p['v_down']
    deliver_done = ret_f - t_back
    max_deliver = max(max_deliver, deliver_done)
    last_rows.append((f['fid'], f['model'], round(ret_f, 1), round(deliver_done, 1), len(route), f['nbox']))

last_rows.sort(key=lambda r: -r[2])
print('口径A 最后返场 = %.1f s (%.2f min)' % (max_return, max_return / 60.0))
print('口径B 最后投送完成 = %.1f s (%.2f min)' % (max_deliver, max_deliver / 60.0))
print('口径差 = %.1f s (%.2f min)' % (max_return - max_deliver, (max_return - max_deliver) / 60.0))
print('最晚 5 架次:', last_rows[:5])
print('架次数=%d 能耗=%.2f kWh' % (len(fls), sum(f['energy'] for f in fls)))
print('对方参考: 23 架 / 94.897 min / 67.14 kWh')