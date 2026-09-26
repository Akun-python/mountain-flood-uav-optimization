# -*- coding: utf-8 -*-
"""v114-fix：24架冠军(v113)综合审计。"""
import sys, os, json
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight, Data
from p2v28_compliant import dispatch_compliant
from dqn23_enhanced import eval_full
from audit_results import check_battery as cb
data = Data()
def audit(name, path):
    dd = json.load(open(path, encoding='utf-8'))
    sol = dd['solution'] if 'solution' in dd else dd
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data) for f in sol]
    sch, _ = dispatch_compliant(data, fls)
    mm, s, vv, nn = eval_full(data, fls)
    vb = cb(data, sch, fls)
    multi = [(f.fid, f.model, [z for z, _ in f.route]) for f in fls if len(set(z for z, _ in f.route)) > 1]
    print('%s: %d架 mk=%.1f en=%.2f hard=%s bat=%d | 多区趟: %s' % (name, len(fls), mm['makespan'], mm['energy'], mm['hard_ok'], len(vb), multi), flush=True)
    return fls, sch
fls1, sch1 = audit('25架冠军', '求解代码与结果/结果/进化_v25/p2v89_champion25.json')
fls2, sch2 = audit('24架v113', '求解代码与结果/结果/进化_v25/v113_best.json')
for tag, fls, sch in (('25架', fls1, sch1), ('24架', fls2, sch2)):
    pools = {}
    for f in fls:
        pools.setdefault(f.model, []).append((sch[f.fid]['start'], sch[f.fid]['return']))
    pl = {m: 'n=%d max_ret=%.0f' % (len(v), max(r for _, r in v)) for m, v in pools.items()}
    print('%s 池: %s' % (tag, pl), flush=True)
    for f in sorted(fls, key=lambda x: sch[x.fid]['return'])[-3:]:
        print('  尾趟 f%02d %s %s ret=%.0f' % (f.fid, f.model, [z for z,_ in f.route], sch[f.fid]['return']), flush=True)
