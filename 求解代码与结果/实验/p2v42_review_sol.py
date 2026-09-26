# -*- coding: utf-8 -*-
"""v42-γ：任意解文件官方严格复核（8 项，与 v42_review_check 同口径）。
用法: python p2v42_review_sol.py <解JSON路径> [输出名]
解 JSON 结构: {"flights":[{"fid":int,"model":"A","route":[["Sxxx",[bid,...]],...]}]}
（兼容 mk29_best.json / s23_search.json.final.routes）"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data, charge_time
from p2_solve import Flight, dispatch, evaluate

data = Data()
src = sys.argv[1]
outname = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(src).replace('.json', '')
obj = json.load(open(src, encoding='utf-8'))
fls_data = obj['flights'] if 'flights' in obj else obj['final']['routes']
fl = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
      for f in fls_data]
flmap = {f.fid: f for f in fl}

verdicts = []
def verdict(name, ok, detail=''):
    verdicts.append({'item': name, 'ok': bool(ok), 'detail': detail})

verdict('架次数', len(fl) in (23, 24, 25, 26, 27, 28, 29), '%d' % len(fl))
bad_feas = [(f.fid, f.model, f.total_mass, f.total_vol, round(f.energy(), 2)) for f in fl
            if not f.is_feasible()]
verdict('每架质量/体积/返航能量可行', not bad_feas, str(bad_feas[:3]))
margin_ok = all(f.energy() <= (1 - data.uav_types[f.model]['rho']) * data.uav_types[f.model]['E_use'] + 1e-9
                for f in fl)
margin_min = min((1 - data.uav_types[f.model]['rho']) * data.uav_types[f.model]['E_use'] - f.energy()
                 for f in fl)
verdict('返航安全余量', margin_ok, '最小余量=%.3f kWh' % margin_min)
sch, _ = dispatch(data, fl)
met = evaluate(data, fl, sch)
allb = [b for f in fl for b in f.box_ids]
verdict('80箱唯一无缺', len(allb) == 80 and len(set(allb)) == 80, '%d' % len(set(allb)))
verdict('区一致零跨区', not met['bad_zones'], str(met['bad_zones'][:5]))
verdict('硬时限/零迟到', met['hard_ok'] and met['tardy_w'] < 1e-6, 'tardy=%.2f' % met['tardy_w'])
verdict('口径 makespan/能耗', True, 'mk=%.1f en=%.2f fl=%d'
        % (met['makespan'], met['energy'], met['flights']))
use = {}
for fid, s in sch.items():
    use.setdefault(s['battery'], []).append((fid, s['uav'], s['start']))
chg = []
for b, segs in use.items():
    segs.sort(key=lambda x: x[2])
    for k in range(1, len(segs)):
        pfid, pu, ps = segs[k - 1]
        cfid, cu, cs = segs[k]
        p = flmap[pfid]; c = flmap[cfid]
        t_back = ps + p.duration()
        soc = max(0.0, 1.0 - p.energy() / data.uav_types[p.model]['E_use'])
        need = charge_time(soc, data.batteries[p.model]['T_full']) - c.prep
        if cs - t_back + 1e-6 < need:
            chg.append((pfid, cfid, round(t_back), round(cs), round(cs - t_back, 1),
                        round(need, 1)))
verdict('电池满充', not chg, str(chg[:3]))
print('\n===== 复核 %s (fl=%d) =====' % (outname, len(fl)))
for v in verdicts:
    print('%s %s : %s' % ('[OK]' if v['ok'] else '[!!]', v['item'], v['detail']))
n = sum(1 for v in verdicts if v['ok'])
print('通过 %d/%d  mk=%.1f en=%.2f' % (n, len(verdicts), met['makespan'], met['energy']))
# 机型配比
print('机型:', {m: sum(1 for f in fl if f.model == m) for m in 'ABC'})
cross = sorted(set(s for f in fl for s, _ in f.route if len(f.route) > 1))
print('多区架次区集合:', cross[:10])
json.dump({'name': outname, 'verdicts': verdicts,
           'met': {'flights': met['flights'], 'makespan': round(met['makespan'], 1),
                   'energy': round(met['energy'], 2)}},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '结果',
                            '进化_v42', 'review_%s.json' % outname),
               'w', encoding='utf-8'), ensure_ascii=False, indent=1)