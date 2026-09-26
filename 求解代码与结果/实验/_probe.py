import json, os
for p in ['求解代码与结果/结果/进化_v25/p2v25e_pareto_7600.json',
          '求解代码与结果/结果/进化_v25/p2v25e_pareto_7800.json',
          '求解代码与结果/结果/进化_v25/p2v25e_pareto_8000.json',
          '求解代码与结果/结果/进化_v25/p2v25e_pareto.json']:
    if not os.path.exists(p): continue
    d = json.load(open(p, encoding='utf-8'))
    print(p.split('/')[-1], list(d.keys())[:8])
    if 'solutions' in d:
        for s in d['solutions'][:10]:
            print('   flights=%s mk=%s en=%s' % (s.get('flights'), round(s.get('makespan', 0),1) if isinstance(s.get('makespan'), float) else s.get('makespan'), s.get('energy')))
