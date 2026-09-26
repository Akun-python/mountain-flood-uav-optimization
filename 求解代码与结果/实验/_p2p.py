import json, os
for p in ['求解代码与结果/results/p2_results.json', '求解代码与结果/results/p3_final.json']:
    r = json.load(open(p, encoding='utf-8'))
    if 'met' in r and isinstance(r['met'], dict):
        print(p.split('/')[-1], 'met keys:', {k: (round(v,1) if isinstance(v,float) else v) for k,v in r['met'].items() if k in ('makespan','energy','hard_ok','tardy_w')})
    elif 'best' in r:
        print(p.split('/')[-1], 'best:', r['best'])
    else:
        print(p.split('/')[-1], 'keys:', list(r.keys())[:8])
