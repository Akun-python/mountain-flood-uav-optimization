# -*- coding: utf-8 -*-
"""README 叙述行时间单位转化（表格行含 | 保持秒）。"""
import re

MAP = {'6960': '116 min', '5724': '95 min', '8378': '140 min',
       '8342': '139 min', '1382': '23 min', '7260': '121 min',
       '8006': '133 min', '5182': '86 min', '4007': '67 min', '9258': '154 min'}

for path in ['README.md', r'求解代码与结果/README.md']:
    lines = open(path, encoding='utf-8').read().split('\n')
    out, n = [], 0
    for ln in lines:
        new = ln
        if '|' not in ln:  # 叙述行才转
            for sec, repl in MAP.items():
                new = re.sub(r'(?<!\d)' + sec + r'\s?s\b', repl, new)
        if new != ln:
            n += 1
        out.append(new)
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
    print('%s: %d 行转化' % (path, n))
    for ln, new in zip(lines, out):
        if ln != new:
            print('  -', new.strip()[:100])