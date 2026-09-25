# -*- coding: utf-8 -*-
"""
v19b · P3 端到端评估：27 架尾部修复解（候选冠军）
=================================================
用 p3_co2 官方管线（Solver → SA 偏移优化 → finalize）对 27 架候选解做
端到端联合调度评估，与官方 26 架冠军（联合 7260 s / 中继 3.417 kWh）
对比。方法：把候选解写成临时 p2_results.json，重定向 p3_co2.OUT，
其余判定链（cover_bad / R2 重叠 / machine_penalty / 中继能耗 / 联合完工）
与官方完全一致。
"""
import sys, os, json, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import p3_co2
from p3_co2 import Solver, P_W, P_E, P_N, POS_OF

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
OUTD = os.path.join(HERE, '..', '结果', '进化_v20')
TMP = os.path.join(HERE, '_p2v19_tmp')

champ = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
cand_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUTD, 'p2_solution27.json')
cand = json.load(open(cand_path, encoding='utf-8'))
print('candidate file:', cand_path, flush=True)

# 官方基线端到端（results/p3_co2.json 记录的偏移 + finalize 复算）
def e2e_offsets(offsets):
    sv = Solver()          # 读 p3_co2.OUT 指向的 p2_results.json
    res = sv.finalize(offsets)
    met = res['met']
    latest = max(s['t1'] + 0.0 for ss in res['seg'].values() for s in ss)  # 占位，下面重算
    return sv, res, met

print('==== 官方 26 架（现有偏移，复核）====', flush=True)
p3_co2.OUT = RES
sv0 = Solver()
off0 = json.load(open(os.path.join(RES, 'p3_co2.json'), encoding='utf-8'))['offsets']
res0 = sv0.finalize({int(k): v for k, v in off0.items()})

print('\n==== 候选（SA 重寻偏移 + finalize）====', flush=True)
os.makedirs(TMP, exist_ok=True)
shutil.copy(cand_path, os.path.join(TMP, 'p2_results.json'))
p3_co2.OUT = TMP
sv1 = Solver()
iters = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
best, best_obj = sv1.sa(iters=iters, seed=7, w_relay=0.0)
res1 = sv1.finalize(best)

# 汇总
def pack(sv, res, name):
    met = res['met']
    seg = res['seg']
    pos = POS_OF
    dd = sv.flights[0].data
    from core import relay_mission_time, relay_mission_energy
    # 官方口径：中继能耗 = machine_penalty 班次打包后的 sum(班次能耗)
    pen, minfo, energy_sum = sv.machine_penalty(res['missions'])
    latest = 0.0
    for g in ('W', 'E', 'N'):
        for (t0, t1) in minfo[g]:
            t_out, t_back, _ = relay_mission_time(pos[g][0], pos[g][1], pos[g][2], dd)
            latest = max(latest, t1 + t_back)
    return {'name': name,
            'transport': {'makespan': round(float(met['makespan']), 2),
                          'energy': round(float(met['energy']), 3),
                          'flights': met['flights'],
                          'hard_ok': met['hard_ok'],
                          'tardy_w': round(float(met['tardy_w']), 2)},
            'cover_bad': sum(1 for m in res['missions'] if m['n_cov'] < m['n']),
            'machine_pen': round(float(res['mpen']), 1),
            'relay_sorties': {g: [(round(a), round(b)) for a, b in minfo[g]] for g in minfo},
            'relay_energy_sortie_kwh': round(float(energy_sum), 3),
            'latest_relay_return': round(latest, 1),
            'joint_makespan': round(max(float(met['makespan']), latest), 1),
            'seg': {g: [(round(a), round(b)) for a, b in seg[g]] for g in seg}}

r0 = pack(sv0, res0, 'official26')
r1 = pack(sv1, res1, 'candidate')
print('\n== 官方 26 ==', flush=True)
print(json.dumps(r0, ensure_ascii=False, indent=1), flush=True)
print('\n== 候选 27 ==', flush=True)
print(json.dumps(r1, ensure_ascii=False, indent=1), flush=True)
os.makedirs(OUTD, exist_ok=True)
with open(os.path.join(OUTD, 'p2v19_p3_e2e.json'), 'w', encoding='utf-8') as fh:
    json.dump({'official26': r0, 'candidate': r1}, fh, ensure_ascii=False, indent=1)
print('\nsaved p2v19_p3_e2e.json', flush=True)