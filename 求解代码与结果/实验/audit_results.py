# -*- coding: utf-8 -*-
"""audit_results.py —— 关键结果全面审计（合规 + 箱覆盖完整性 + 数字一致性）。
对每个解 JSON：eval_full（零违规/hard/临界）+ 电池独立检查 + 箱覆盖（每箱恰好一趟，无遗漏/重复/越界）。
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import eval_full

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()
ALL_KEYS = set(data.boxes.keys())

FILES = [
    ('p2v37_merge.json', '22架 8172.1/66.58'),
    ('p2v42_23base.json', '23架 7771.0/67.78'),
    ('p2v46_23local.json', '23架 7724.9/67.61'),
    ('p2v47_23deep.json', '23架 v47'),
    ('p2v40_mk_tol6_0.json', '29架 7168.5/74.56'),
    ('p2v54_mk_rettype.json', '29架 7148.2/75.25'),
    ('p2v58_rainbow_greedy.json', '29架 6990.1/75.22'),
    ('p3v28_compliant_v40mk.json', '29架 P3 7779.2'),
    ('p3v28_compliant_v58rb.json', '29架 P3 7845.2'),
]


def audit(fn, note):
    p = os.path.join(OUTD, fn)
    if not os.path.exists(p):
        print('%-32s 缺失!' % fn)
        return None
    d = json.load(open(p, encoding='utf-8'))
    if 'solution' not in d:
        print('%-32s 无 solution 字段（汇总类）' % fn)
        return None
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d['solution']]
    m, s, v, nc = eval_full(data, fls)
    # 电池独立检查
    try:
        sch, _ = dispatch_compliant(data, fls)
        vb = len(check_battery(data, sch, fls))
    except Exception as e:
        vb = 'ERR(%s)' % e
    # 箱覆盖
    covered = set()
    dup = []
    extra = []
    for f in fls:
        for b in f.box_ids:
            if b in covered:
                dup.append(b)
            covered.add(b)
            if b not in ALL_KEYS:
                extra.append(b)
    missing = ALL_KEYS - covered
    # 质量/体积/能量逐趟
    infeas = []
    for f in fls:
        if not f.is_feasible():
            infeas.append(f.fid)
    ok = (m is not None and v == 0 and nc == 0 and m['hard_ok'] and vb == 0
          and not dup and not missing and not extra and not infeas)
    print('%-32s %s' % (fn, note))
    print('   %2d架 mk=%-8.1f en=%-7.2f hard=%s 违规=%d 临界=%d 电池=%s | 箱:缺%d 重%d 越界%d 趟不可行%s | %s' % (
        len(fls), m['makespan'] if m else -1, m['energy'] if m else -1,
        m['hard_ok'] if m else '?', v, nc, vb, len(missing), len(dup), len(extra), infeas,
        'PASS' if ok else '<<< FAIL'))
    return ok


def main():
    print('=== 关键结果全面审计 ===')
    print('箱总数: %d' % len(ALL_KEYS))
    allok = True
    for fn, note in FILES:
        r = audit(fn, note)
        if r is False:
            allok = False
    print('=== 审计 %s ===' % ('全部通过' if allok else '存在FAIL'))


if __name__ == '__main__':
    main()