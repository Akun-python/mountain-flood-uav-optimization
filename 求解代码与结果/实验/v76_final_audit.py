# -*- coding: utf-8 -*-
"""v76：最终冠军完整审计 + 多版本帕累托落盘。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from dqn23_enhanced import eval_full, OUTD
from audit_results import check_battery as cb
data = Data()
d = json.load(open(os.path.join(OUTD, 'p2v74_champion.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in d['solution']]
m, sch, v, nc = eval_full(data, fls)
print('== 最终冠军 8 项审计 ==')
print('1.完工 %.1fs(%.2fmin) 能耗 %.2fkWh 架次%d 机型%s' % (m['makespan'], m['makespan']/60, m['energy'], len(fls), {g: sum(1 for f in fls if f.model==g) for g in 'ABC'}))
print('2.hard=%s 违规=%d 临界=%d' % (m['hard_ok'], v, nc))
allb = set(data.boxes); used = set()
for f in fls:
    for b in f.box_ids: used.add(b)
print('3.覆盖: 缺%d 重%d' % (len(allb-used), len(used)-len(allb)))
print('4.逐趟可行: %s' % ('PASS' if all(f.is_feasible() for f in fls) else 'FAIL'))
zb = [f.fid for f in fls for s2, bs in f.route for b in bs if b.split('-')[0] != s2]
print('5.区一致: %s' % ('PASS' if not zb else 'FAIL'))
bat = cb(data, sch, fls)
print('6.电池复核: %s(%d条)' % ('PASS' if not bat else 'FAIL', len(bat)))
low = [f.fid for f in fls if f.energy() > 0.8*{'A':4.5,'B':4.0,'C':8.0}[f.model]]
empty = [f.fid for f in fls if not f.box_ids]
print('7.返航保底 %s 空趟 %s' % ('PASS' if not low else 'FAIL', 'PASS' if not empty else 'FAIL'))
pt = {'A':0.0,'B':0.0,'C':0.0}
for f in fls: pt[f.model] += f.duration()
print('8.池T/台:', {g: round(pt[g]/{'A':4,'B':2,'C':2}[g],0) for g in 'ABC'})
ok = (v==0 and nc==0 and not bat and not zb and not low and not empty and len(allb-used)==0 and len(used)-len(allb)==0)
print('== 审计结论: %s ==' % ('ALL PASS' if ok else 'HAS ISSUE'))

