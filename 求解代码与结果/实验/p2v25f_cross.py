# -*- coding: utf-8 -*-
"""v25f 跨机型链优化（严格口径）：28 架解完工瓶颈 = C 机链（8 架次/2 机 = 7395s）。
算子：
  1) C 满载近区架次拆箱 -> A 机早班多趟（A 25kg 上限，早班 0 时段有空闲）
  2) B 轻载单区架次（<=25kg）-> A 机（A 早班吸收）
  3) C 轻载单区架次（<=30kg）-> B 机（B 链有余量时）
接受：完工下降 且 hard True 零迟到（能耗不设限，先攻完工）。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight, dispatch, evaluate, normalize_flight, clone_flights

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()

d = json.load(open(os.path.join(OUTD, 'p2v25b_compress26.json'), encoding='utf-8'))
fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
       for f in d['solution']]


def eval_full(data, fl):
    sch, _ = dispatch(data, fl)
    if sch is None:
        return None, None
    return evaluate(data, fl, sch), sch


def split_to_A(data, fl, f, sid, bs):
    """把 f 的 (sid, bs) 拆成 A 机多趟（每趟 <= 25kg）。返回新 fl 或 None。"""
    aq = data.uav_types['A']['Q']
    fl = clone_flights(fl)
    fa = next(x for x in fl if x.fid == f.fid)
    batches = []
    cur, cur_m = [], 0.0
    for b in sorted(bs, key=lambda x: -data.boxes[x]['mass']):
        m = data.boxes[b]['mass']
        if cur_m + m <= aq + 1e-9:
            cur.append(b)
            cur_m += m
        else:
            if cur:
                batches.append(cur)
            cur, cur_m = [b], m
    if cur:
        batches.append(cur)
    # 移除原箱（保留 f 其它区）
    for i, (s2, b2) in enumerate(fa.route):
        if s2 == sid and set(bs) <= set(b2):
            for b in bs:
                b2.remove(b)
            if not b2:
                del fa.route[i]
            break
    normalize_flight(fa, data)
    if not fa.route:          # 架次被拆空 -> 删除
        fl = [x for x in fl if x.fid != fa.fid]
    elif not fa.is_feasible():
        return None
    fid = max(x.fid for x in fl if x.fid is not None) + 1
    for k, bt in enumerate(batches):
        nf = Flight(fid + k, [(sid, list(bt))], 'A', data)
        if not nf.is_feasible():
            return None
        fl.append(nf)
    return fl


def main():
    m0, s0 = eval_full(data, fls)
    print('起点: %d 架 / mk %.1f / %.2f kWh / hard %s' % (
        len(fls), m0['makespan'], m0['energy'], m0['hard_ok']))
    cur, cur_met, cur_sch = fls, m0, s0
    log = []
    for rnd in range(20):
        improved = False
        # 1) C 满载近区拆 A 早班（质量 > 30kg 的单区 C 架次优先）
        cfs = [f for f in cur if f.model == 'C' and len(f.route) == 1 and f.total_mass > 30]
        cfs.sort(key=lambda f: cur_sch[f.fid]['return'], reverse=True)
        for f in cfs[:6]:
            sid, bs = f.route[0]
            cand = split_to_A(data, cur, f, sid, bs)
            if cand is None:
                continue
            m, s = eval_full(data, cand)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if m['makespan'] < cur_met['makespan'] - 1e-6:
                log.append({'round': rnd + 1, 'op': 'splitCtoA', 'flight': f.fid,
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur, cur_met, cur_sch = cand, m, s
                improved = True
                break
        if improved:
            continue
        # 2) C 轻载（<=30kg）单区架次 -> B 机
        for f in [x for x in cur if x.model == 'C' and len(x.route) == 1 and x.total_mass <= 30]:
            fl = clone_flights(cur)
            fa = next(x for x in fl if x.fid == f.fid)
            fa.model = 'B'
            normalize_flight(fa, data)
            if not fa.is_feasible():
                continue
            m, s = eval_full(data, fl)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if m['makespan'] < cur_met['makespan'] - 1e-6:
                log.append({'round': rnd + 1, 'op': 'retype_CtoB', 'flight': f.fid,
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur, cur_met, cur_sch = fl, m, s
                improved = True
                break
        if improved:
            continue
        # 3) B 轻载（<=25kg）单区架次 -> A 机（A 早班吸收，缩短 B 链）
        for f in [x for x in cur if x.model == 'B' and len(x.route) == 1 and x.total_mass <= 25]:
            fl = clone_flights(cur)
            fa = next(x for x in fl if x.fid == f.fid)
            fa.model = 'A'
            normalize_flight(fa, data)
            if not fa.is_feasible():
                continue
            m, s = eval_full(data, fl)
            if m is None or not (m['hard_ok'] and m['tardy_w'] < 1e-6):
                continue
            if m['makespan'] < cur_met['makespan'] - 1e-6:
                log.append({'round': rnd + 1, 'op': 'retype_BtoA', 'flight': f.fid,
                            'mk': round(m['makespan'], 1), 'en': round(m['energy'], 3)})
                cur, cur_met, cur_sch = fl, m, s
                improved = True
                break
        print('round %d: mk=%.1f en=%.2f n=%d improved=%s' % (
            rnd + 1, cur_met['makespan'], cur_met['energy'], cur_met['flights'], improved), flush=True)
        if not improved:
            break
    print('\n结果: %d 架 / mk %.1f s (%.1f min) / %.2f kWh / hard %s' % (
        cur_met['flights'], cur_met['makespan'], cur_met['makespan'] / 60,
        cur_met['energy'], cur_met['hard_ok']))
    # 链输出
    sch, _ = dispatch(data, cur)
    chains = {}
    for f in cur:
        chains.setdefault(sch[f.fid]['uav'], []).append((f, sch[f.fid]))
    for uid in sorted(chains):
        ch = chains[uid]
        last = max(c['return'] for _, c in ch)
        print('  %s (%s): %d 架次, 最后返场 %7.0f' % (uid, ch[0][0].model, len(ch), last))
    json.dump({'best': {k: v for k, v in cur_met.items() if k != 'box_time'}, 'moves_log': log,
               'solution': [{'fid': f.fid, 'model': f.model,
                             'route': [(s, list(bs)) for s, bs in f.route]} for f in cur]},
              open(os.path.join(OUTD, 'p2v25f_cross.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p2v25f_cross.json')


if __name__ == '__main__':
    main()