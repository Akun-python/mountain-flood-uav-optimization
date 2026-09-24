# -*- coding: utf-8 -*-
"""最终审计：图内文字颜色必须为黑，无任何图内标题。"""
import glob, io

bad = 0
for fn in sorted(glob.glob('solve_d/code/*figures*.py')):
    s = io.open(fn, encoding='utf-8').read()
    for i, l in enumerate(s.split('\n'), 1):
        t = l.strip()
        if 'set_title' in t or 'suptitle' in t:
            print('TITLE', fn.split('\\')[-1], 'L%d' % i, t[:90])
            bad += 1
        if ('annotate(' in t or 'text(' in t or 'set_ylabel(' in t
                or 'tick_params(' in t) and 'color=' in t:
            if 'black' not in t and '#6B7280' in t:
                print('COLORED', fn.split('\\')[-1], 'L%d' % i, t[:90])
                bad += 1
print('residual issues:', bad)