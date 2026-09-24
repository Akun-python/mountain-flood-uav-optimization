# -*- coding: utf-8 -*-
"""从 results/p2_results.json 生成论文 Q2 架次明细 LaTeX 行（21 架次冠军方案）。"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')

MODEL_ORDER = {'C': 0, 'B': 1, 'A': 2}


def main():
    r = json.load(open(os.path.join(RES, 'p2_results.json'), encoding='utf-8'))
    fl = r['flights']
    fl.sort(key=lambda f: (MODEL_ORDER[f['model']], f['start']))
    out = []
    prev_model = None
    for f in fl:
        route = '至'.join(s for s, _ in f['route'])
        if f['model'] != prev_model:
            if prev_model is not None:
                out.append(r'\midrule')
            prev_model = f['model']
        out.append('f%02d & %s & %s & %.0f & %.0f & %.2f & %s \\\\'
                   % (f['fid'], f['model'], f['uav'], f['start'], f['return'],
                      f['energy'], route))
    body = '\n'.join(out)
    print(body)
    with open(os.path.join(HERE, 'samples', 'p2_flights_tabular.tex'), 'w', encoding='utf-8') as fh:
        fh.write(body)
    print('\n# rows:', len(fl), '| makespan=%.1f energy=%.3f'
          % (r['metrics']['makespan'], r['metrics']['energy']))


if __name__ == '__main__':
    main()