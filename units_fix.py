# -*- coding: utf-8 -*-
"""论文时间单位转化：正文大时间值 s -> min/h（秒级参数、服务时段窗口、
表格数据保持不变）。"""
import re, glob

# 秒 -> 分钟/小时 映射（仅正文叙述中的大值）
MAP = {
    '32661': '9.1\\,h',       # 累计作业时间
    '6960': '116\\,min',
    '7837': '131\\,min',
    '7920': '132\\,min',
    '8342': '139\\,min',
    '1382': '23\\,min',
    '7260': '121\\,min',
    '7259.8': '121\\,min',
    '7221': '120\\,min',
    '5724': '95\\,min',
    '8378': '140\\,min',
    '7616': '127\\,min',
    '8006': '133\\,min',
    '5182': '86\\,min',
    '4007': '67\\,min',
    '9258': '154\\,min',
}

FILES = ['main.tex'] + sorted(glob.glob('sections/*.tex'))
total = 0
for f in FILES:
    txt = open(f, encoding='utf-8').read()
    orig = txt
    for sec, repl in MAP.items():
        # 只匹配 "NUMBER\,s"（数字后直接跟 \,s），不碰无单位的表格数字
        pat = re.compile(r'(?<!\d)' + re.escape(sec) + r'\\,s')
        txt = pat.sub(repl, txt)
    if txt != orig:
        n = sum(1 for _ in re.finditer(r'(?<!\d)(?:32661|6960|7837|7920|8342|1382|7260|7259\.8|7221|5724|8378|7616|8006|5182|4007|9258)\\,s', txt))
        # 统计原始与替换后的差异行
        diff = [l1 for l1, l2 in zip(orig.split('\n'), txt.split('\n')) if l1 != l2]
        total += len(diff)
        print('== %s == (%d 行改动)' % (f, len(diff)))
        for d in diff:
            print('   ', d.strip()[:110])
        open(f, 'w', encoding='utf-8', newline='\n').write(txt)
print('total changed lines:', total)