import json, os
for p in ['求解代码与结果/结果/进化_v25/p2v25e_pareto_7600.json',
          '求解代码与结果/结果/进化_v25/p2v25e_pareto_7800.json',
          '求解代码与结果/结果/进化_v25/p2v25e_pareto_8000.json']:
    d = json.load(open(p, encoding='utf-8'))
    b = d.get('best', {})
    sol = d.get('solution', [])
    print(p.split('/')[-1], 'best=', b, 'flights=%d' % len(sol))
