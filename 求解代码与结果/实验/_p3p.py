import json, os
p = '求解代码与结果/results/p3_final.json'
if os.path.exists(p):
    r = json.load(open(p, encoding='utf-8'))
    print('p3_final keys:', list(r.keys())[:12])
    fl = r.get('flights') or r.get('sorties') or []
    print('flights:', len(fl) if fl else None)
    if fl: print('first:', fl[0] if isinstance(fl[0], dict) else type(fl[0]))
else:
    print('p3_final.json 不存在')
