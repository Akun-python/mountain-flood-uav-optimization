import json
r = json.load(open('求解代码与结果/results/p2_results.json', encoding='utf-8'))
print('metrics:', r['metrics'])
print('flights:', len(r['flights']))
deliv = r.get('deliveries', [])
print('deliveries:', len(deliv) if deliv else None)
