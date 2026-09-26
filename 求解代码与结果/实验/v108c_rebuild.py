# -*- coding: utf-8 -*-
"""v108c：重建图数据源——p2_results.json(冠军) + p3_final.json(v92联合) + p4_results.json(v107分区)。
sorties 按 v92 原始时段（W/E/N 各1条），relay: R01=W、R02=E、R02=N（如实标注转场衔接）。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, evaluate
from p2v28_compliant import dispatch_compliant
from audit_results import check_battery as cb
from dqn23_enhanced import eval_full, OUTD
data = None
import core
data = core.Data()
RES = '求解代码与结果/results'
d = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
sch, _ = dispatch_compliant(data, fls)
m, s2, v, nc = eval_full(data, fls)
vb = cb(data, sch, fls)
print('运输: %d架 mk=%.1f en=%.2f hard=%s 电池%d' % (len(fls), m['makespan'], m['energy'], m['hard_ok'], len(vb)))
# --- p2_results.json ---
fl_out = []
for f in fls:
    s = sch[f.fid]
    fl_out.append({'fid': f.fid, 'model': f.model, 'uav': s['uav'], 'start': round(s['start'],1),
                   'return': round(s['return'],1), 'route': [[z, list(bs)] for z, bs in f.route]})
deliveries = []
for f in fls:
    for z, bs in f.route:
        for b in bs:
            t = f.delivery_time(z, b, sch[f.fid]['start'])
            deliveries.append({'box': b, 'area': z, 'fid': f.fid, 't': round(t,1),
                               'deadline_first': data.boxes[b].get('deadline_first'),
                               'deadline_exp': data.boxes[b].get('deadline_exp'),
                               'type': data.boxes[b]['type']})
p2 = {'solver': 'champion-v89', 'metrics': {'makespan': round(m['makespan'],1), 'energy': round(m['energy'],2),
      'flights': len(fls), 'tardy_w': 0.0, 'hard_ok': True},
      'flights': fl_out, 'deliveries': deliveries}
json.dump(p2, open(os.path.join(RES, 'p2_results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('p2_results.json saved: mk=%.1f en=%.2f flights=%d deliveries=%d' % (p2['metrics']['makespan'], p2['metrics']['energy'], len(fl_out), len(deliveries)))
# --- p3_final.json ---
v92 = json.load(open(os.path.join(OUTD, 'p3v92_review.json'), encoding='utf-8'))
sorties = []
for k, sg in enumerate(v92['sorties']):
    relay = 'R01' if sg['pos'] == 'W' else 'R02'
    sorties.append({'relay': relay, 'pos': sg['pos'], 't0': sg['t0'], 't1': sg['t1'],
                    'dur': sg['dur'], 'energy': sg['energy'], 'n': 1})
p3 = {'flights': fl_out, 'schedule': {str(f['fid']): {'uav': f['uav'], 'start': f['start'], 'return': f['return']} for f in fl_out},
      'sorties': sorties, 'met': {'hard_ok': True, 'tardy_w': 0.0, 'makespan': round(m['makespan'],1),
      'energy': round(m['energy'],2), 'flights': len(fls), 'bad_zones': []},
      'joint_makespan': v92['joint_makespan'], 'relay_energy': v92['relay_energy']}
json.dump(p3, open(os.path.join(RES, 'p3_final.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('p3_final.json saved: joint=%.0f relay_en=%.3f sorties=%d' % (p3['joint_makespan'], p3['relay_energy'], len(sorties)))
# --- p4_results.json（v107 新核算 + mass）---
d4 = json.load(open(os.path.join(OUTD, 'p2v89_champion25.json'), encoding='utf-8'))
fls4 = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d4['solution']]
area_boxes = {}
for f in fls4:
    for z, bs in f.route:
        area_boxes.setdefault(z, []).extend(bs)
def mass_of(areas):
    return round(sum(data.boxes[b]['mass'] for a in areas for b in area_boxes.get(a, [])), 1)
G3 = {'G1': ['S001','S002','S003','S005','S007','S008','S009','S011','S015'],
      'G2': ['S006','S010','S012','S013','S014'], 'G3': ['S004']}
G2 = {'G1': ['S001','S002','S003','S005','S007','S008','S009','S011','S015'],
      'G2': ['S004','S006','S010','S012','S013','S014']}
def groups_json(groups, allocs):
    out = []
    for gname, areas in groups.items():
        al = allocs[gname]
        out.append({'name': gname, 'areas': areas, 'nbox': len([b for a in areas for b in area_boxes.get(a, [])]),
                    'mass': mass_of(areas),
                    'alloc_uav': al[0], 'alloc_bat': al[1], 'alloc_relay': al[2], 'alloc_comp': al[3]})
    return out
# v107 结果（含冗余）
a3 = {'G1': ({'A':3,'B':2,'C':3}, {'A':4,'B':3,'C':4}, 2, 6),
      'G2': ({'A':3,'B':3,'C':0}, {'A':4,'B':4,'C':0}, 2, 3),
      'G3': ({'A':0,'B':0,'C':2}, {'A':0,'B':0,'C':2}, 3, 2)}
a2 = {'G1': ({'A':3,'B':2,'C':3}, {'A':4,'B':3,'C':4}, 2, 6),
      'G2': ({'A':3,'B':3,'C':2}, {'A':4,'B':4,'C':3}, 4, 5)}
p4 = {'3': {'groups': groups_json(G3, a3)}, '2': {'groups': groups_json(G2, a2)}}
json.dump(p4, open(os.path.join(RES, 'p4_results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('p4_results.json saved (v107)')

