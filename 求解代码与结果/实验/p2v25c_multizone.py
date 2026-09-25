# -*- coding: utf-8 -*-
"""v25c 多区化修复：26 架冠军（v24, afc4405）有 14 箱单区架次错投。
修复：给错区箱所在架次 route 追加真实区条目（无人机真实经过该区=顺路合法投送），
或移到同架次已有真实区条目的位置；严格 evaluate 验证 hard True。
目标：保持 26 架结构、完工尽量贴近 6959.8。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

d = json.load(open(os.path.join(HERE, 'p2_v24_afc4405.json'), encoding='utf-8'))
fls = [Flight(fj['fid'], [(s, list(bs)) for s, bs in fj['route']], fj['model'], data)
       for fj in d['flights']]


def mismatches(fls):
    bad = []
    for f in fls:
        for s, bs in f.route:
            for b in bs:
                if b.split('-')[0] != s:
                    bad.append((f, s, b))
    return bad


def eval_full(data, fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None, None
    return evaluate(data, fl, sch), sch


def main():
    bad = mismatches(fls)
    print('修复前错区箱:', len(bad))
    cur = fls
    moves = []
    for rnd in range(5):
        bad = mismatches(cur)
        if not bad:
            break
        fixed = False
        for (f, s_mount, b) in list(bad):
            real = b.split('-')[0]
            if any(s2 == real for s2, _ in f.route):
                # 架次已访问真实区：把箱挪进真实区条目即可（仅 list 重排）
                fl = clone_flights(cur)
                fa = next(x for x in fl if x.fid == f.fid)
                for i, (s2, bs2) in enumerate(fa.route):
                    if s2 == s_mount and b in bs2:
                        bs2.remove(b)
                        if not bs2:
                            del fa.route[i]
                        break
                for i, (s2, bs2) in enumerate(fa.route):
                    if s2 == real:
                        bs2.append(b)
                        fa.route[i] = (s2, bs2)
                        break
                normalize_flight(fa, data)
            else:
                # 架次不去真实区：追加真实区条目（多区化，真实经过）
                fl = clone_flights(cur)
                fa = next(x for x in fl if x.fid == f.fid)
                for i, (s2, bs2) in enumerate(fa.route):
                    if s2 == s_mount and b in bs2:
                        bs2.remove(b)
                        if not bs2:
                            del fa.route[i]
                        break
                fa.route.append((real, [b]))
                normalize_flight(fa, data)
            if not fa.route or not fa.is_feasible():
                continue
            m, s = eval_full(data, fl)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if m['makespan'] <= 8200:
                moves.append((b, f.fid, real))
                cur = fl
                fixed = True
                break
        print('round %d: 已修复 %d 箱, 当前 %d 架 / mk %.1f / %.2f kWh / hard %s' % (
            rnd + 1, len(moves), len(cur), m['makespan'], m['energy'], m['hard_ok']))
        if not fixed and not bad:
            break
        if not fixed:
            print('  本轮无法修复，剩余 %d 箱' % len(bad))
            break
    bad = mismatches(cur)
    m, s = eval_full(data, cur)
    print('\n修复后: 错区箱=%d  架=%d  mk=%.1f (%.1f min)  kWh=%.2f  hard=%s  tardy=%.3f' % (
        len(bad), len(cur), m['makespan'], m['makespan'] / 60, m['energy'], m['hard_ok'], m['tardy_w']))
    if not bad and m['hard_ok']:
        json.dump({'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s, list(bs)) for s, bs in f.route]} for f in cur],
                   'metrics': {'flights': len(cur), 'makespan': round(m['makespan'], 1),
                               'energy': round(m['energy'], 3), 'hard_ok': True, 'tardy_w': 0.0},
                   'moves': moves},
                  open(os.path.join(OUTD, 'p2v25c_multizone.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved -> 结果/进化_v25/p2v25c_multizone.json')
    else:
        print('未完全修复，剩余:')
        for (f, sm, b) in bad[:14]:
            print('  f%-3d %-16s 真实=%s 挂载=%s' % (f.fid, b, b.split('-')[0], sm))


if __name__ == '__main__':
    main()