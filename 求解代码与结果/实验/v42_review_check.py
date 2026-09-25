# -*- coding: utf-8 -*-
"""v42 合规性复核：29 架完工冠军（p2v41_mk_tol6_0.json）官方严格管线审查。
D 节：可行性/返航余量/80箱唯一/区一致/硬时限/电池满充（修复版语义）。
输出 JSON 到 结果/进化_v42/v42_compliance_review.json。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.stdout.reconfigure(encoding='utf-8')
from core import Data, charge_time
from p2_solve import Flight, dispatch, evaluate

report = {'verdicts': []}
def verdict(name, ok, detail=''):
    report['verdicts'].append({'item': name, 'ok': bool(ok), 'detail': detail})

data = Data()
sol = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                  '结果', '进化_v25', 'p2v41_mk_tol6_0.json'),
                     encoding='utf-8'))['solution']
fl = [Flight(f['fid'], [(s, list(b)) for s, b in f['route']], f['model'], data)
      for f in sol]
flmap = {f.fid: f for f in fl}
verdict('架次数（29）', len(fl) == 29, '%d' % len(fl))

bad_feas = [(f.fid, f.model, f.total_mass, f.total_vol, f.energy()) for f in fl
            if not f.is_feasible()]
verdict('每架质量/体积/返航能量可行', not bad_feas, str(bad_feas[:3]))
margin_ok = all(f.energy() <= (1 - data.uav_types[f.model]['rho']) * data.uav_types[f.model]['E_use'] + 1e-9
                for f in fl)
margin_min = min((1 - data.uav_types[f.model]['rho']) * data.uav_types[f.model]['E_use'] - f.energy()
                 for f in fl)
verdict('返航安全余量 E <= (1-rho)E_use', margin_ok, '最小余量=%.3f kWh' % margin_min)

sch, _ = dispatch(data, fl)
met = evaluate(data, fl, sch)
allb = [b for f in fl for b in f.box_ids]
verdict('80箱唯一无缺', len(allb) == 80 and len(set(allb)) == 80, '%d' % len(set(allb)))
verdict('投递位置=箱属区（零跨区）', not met['bad_zones'], str(met['bad_zones'][:5]))
verdict('首飞批/医疗时限硬约束', met['hard_ok'], 'tardy_w=%.1f' % met['tardy_w'])
verdict('官方口径 makespan/能耗', True, 'mk=%.1f en=%.2f flights=%d'
        % (met['makespan'], met['energy'], met['flights']))

# ---------- 电池满充复核（修复版语义） ----------
# 同一电池的连续使用架次：上一趟返场时刻 = start + duration()（含交接），
# 充电从返场开始，下一趟 start 前须充满（两阶段 charge_time）。
use = {}
for fid, s in sch.items():
    use.setdefault(s['battery'], []).append(
        (fid, s['uav'], s['start'], s['return']))
chg_strict = []
for b, segs in use.items():
    segs.sort(key=lambda x: x[2])
    for k in range(1, len(segs)):
        pfid, p_uav, p_start, _ = segs[k - 1]
        cfid, c_uav, c_start, _ = segs[k]
        p = flmap[pfid]
        c = flmap[cfid]
        t_back = p_start + p.duration()          # 返场（交接完成）
        soc_back = max(0.0, 1.0 - p.energy() / data.uav_types[p.model]['E_use'])
        need = charge_time(soc_back, data.batteries[p.model]['T_full'])
        # dispatch 语义：充电完成时刻 <= 下一趟起飞+prep（prep=t_prep+nbox*t_load，期间装机）
        need_ok = need - c.prep
        gap = c_start - t_back
        if gap + 1e-6 < need_ok:
            chg_strict.append((pfid, cfid, round(t_back), round(c_start),
                               round(gap, 1), round(need_ok, 1)))
verdict('电池满充（间隔>=充电时长，修复版语义）', not chg_strict, str(chg_strict[:3]))

json.dump(report, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                                    '结果', '进化_v42', 'v42_compliance_review.json'),
                       'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n================ v42 复核结果 ================')
for v in report['verdicts']:
    print('%s %s : %s' % ('[OK]' if v['ok'] else '[!!]', v['item'], v['detail']))
n_ok = sum(1 for v in report['verdicts'] if v['ok'])
print('通过 %d/%d' % (n_ok, len(report['verdicts'])))