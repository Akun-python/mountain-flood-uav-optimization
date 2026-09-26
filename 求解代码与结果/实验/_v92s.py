import json, os
p = '求解代码与结果/结果/进化_v25/p3v92_review.json'
r = json.load(open(p, encoding='utf-8'))
print('v92 keys:', list(r.keys()))
for k in r:
    v = r[k]
    if isinstance(v, dict): print(' ', k, '->', list(v.keys())[:10])
    elif isinstance(v, list): print(' ', k, '-> list len', len(v), '| first:', v[0] if v else None)
    else: print(' ', k, '=', v)
