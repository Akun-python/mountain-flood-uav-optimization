# -*- coding: utf-8 -*-
"""p3v29_relayfree.py —— B2 中继悬停位置自由化：替换 POS_OF 后重跑合规 P3 联合。
对照组 = 原固定位置（应复现 9369.0）；实验组 = 侦察搜索的新位置。
对 28 架(makespan) 与 25 架(energy) 各跑 seed 7/77、SA 3500、零迟到硬罚。
用法: python p3v29_relayfree.py [--pos orig|new] [--iters 3500]
"""
import sys, os, json, io, contextlib, re, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
import p3_co2
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()
POS_ORIG = {'W': (109.2103, 23.047134, 676.5), 'E': (109.268918, 23.012732, 650.0),
            'N': (109.234314, 23.059248, 600.0)}
POS_NEW = {'W': (109.206749, 23.044585, 710.8), 'E': (109.268187, 23.003900, 675.5),
           'N': (109.245951, 23.059755, 565.8)}


def run(src_json, tag, pos, pos_name, seeds=(7, 77), iters=3500):
    d = json.load(open(os.path.join(OUTD, src_json), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d['solution']]
    sch, _ = dispatch_compliant(data, fls)
    if sch is None:
        print('[%s/%s] compliant dispatch 失败' % (tag, pos_name), flush=True)
        return None
    base = {fid: sch[fid]['start'] for fid in sch}
    p3in = os.path.join(OUTD, 'p3in_v29_%s_%s' % (tag, pos_name))
    os.makedirs(p3in, exist_ok=True)
    p3_co2.OUT = p3in
    flights_json = [{'fid': f.fid, 'start': base[f.fid],
                     'route': [[s, list(bs)] for s, bs in f.route], 'model': f.model}
                    for f in fls]
    json.dump({'flights': flights_json},
              open(os.path.join(p3in, 'p2_results.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    # 替换中继位置（模块级全局在 precompute 中引用）
    for g in ('W', 'E', 'N'):
        setattr(p3_co2, 'P_' + g, pos[g])
    p3_co2.POS_OF = dict(pos)
    p3_co2.dispatch = dispatch_compliant
    from p2_solve import evaluate as p2_evaluate

    def safe_evaluate(self, offsets, w_relay=0.0):
        releases = {fid: self.base[fid] + offsets.get(fid, 0.0) for fid in self.base}
        schedule, _ = dispatch_compliant(data, self.flights, releases=releases)
        if schedule is None:
            return 1e9, None
        met = p2_evaluate(data, self.flights, schedule)
        if not met['hard_ok']:
            return 1e9, met
        starts = {fid: schedule[fid]['start'] for fid in schedule}
        missions = self.build_missions(starts)
        cov_bad, overlap, seg, by = self.relay_load(missions)
        mpen, _, relay_energy = self.machine_penalty(missions)
        pen = 1e5 * cov_bad + 5e4 * overlap + 1e4 * mpen
        tardy_pen = 1e7 if met['tardy_w'] > 1e-6 else 0.0
        obj = tardy_pen + pen + 0.05 * met['makespan'] + 0.8 * met['energy'] \
            + 30 * met['flights'] + w_relay * relay_energy
        return obj, met

    def safe_finalize(self, offsets):
        releases = {fid: self.base[fid] + offsets.get(fid, 0.0) for fid in self.base}
        schedule, _ = dispatch_compliant(data, self.flights, releases=releases)
        if schedule is None:
            return None
        met = p2_evaluate(data, self.flights, schedule)
        starts = {fid: schedule[fid]['start'] for fid in schedule}
        missions = self.build_missions(starts)
        cov_bad, overlap, seg, by = self.relay_load(missions)
        mpen, minfo, _ = self.machine_penalty(missions)
        print('final: hard_ok=%s tardy=%.1f makespan=%.0f energy=%.2f flights=%d'
              % (met['hard_ok'], met['tardy_w'], met['makespan'], met['energy'], met['flights']))
        print('cover_bad=%d R2_overlap=%.0fs machine_pen=%.0fs' % (cov_bad, overlap, mpen))
        for g, ss in minfo.items():
            for s in ss:
                pp = pos[g]
                t_out, t_back, _ = p3_co2.relay_mission_time(pp[0], pp[1], pp[2], data)
                e = p3_co2.relay_mission_energy(pp[0], pp[1], pp[2], data, s[1] - s[0])
                print('  %s sortie t=[%.0f, %.0f] e=%.3f kWh dispatch=%.0f ret=%.0f'
                      % (g, s[0], s[1], e, s[0] - t_out - p3_co2.REL['t_link'], s[1] + t_back))
        return {'met': met, 'missions': missions, 'seg': seg, 'mpen': mpen}

    p3_co2.Solver.evaluate = safe_evaluate
    p3_co2.Solver.finalize = safe_finalize
    sv = p3_co2.Solver()
    results = []
    for seed in seeds:
        best, obj = sv.sa(iters=iters, seed=seed, w_relay=0.0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = sv.finalize(best)
        if res is None:
            with contextlib.redirect_stdout(buf):
                res = sv.finalize({k: 0.0 for k in sv.base})
        txt = buf.getvalue()
        m = res['met']
        rets = [float(x) for x in re.findall(r'ret=([\d.]+)', txt)]
        es = [float(x) for x in re.findall(r'e=([\d.]+) kWh', txt)]
        cov_bad = int(re.search(r'cover_bad=(\d+)', txt).group(1))
        overlap = float(re.search(r'R2_overlap=([\d.]+)s', txt).group(1))
        mpen = float(re.search(r'machine_pen=([\d.]+)s', txt).group(1))
        relay_e = sum(es)
        joint = max(m['makespan'], max(rets)) if rets else m['makespan']
        releases = {fid: sv.base[fid] + best.get(fid, 0.0) for fid in sv.base}
        sch2, _ = dispatch_compliant(data, sv.flights, releases=releases)
        viol = check_battery(data, sch2, sv.flights)
        r = {'seed': seed, 'tag': tag, 'pos': pos, 'joint': round(joint, 1),
             'joint_min': round(joint / 60, 1), 'transport_mk': round(m['makespan'], 1),
             'transport_energy': round(m['energy'], 2), 'flights': m['flights'],
             'tardy_w': round(m['tardy_w'], 3), 'hard_ok': m['hard_ok'],
             'relay_energy': round(relay_e, 3), 'cover_bad': cov_bad, 'overlap': round(overlap, 1),
             'mpen': round(mpen, 1), 'battery_violations': len(viol),
             'relay_ret_max': round(max(rets), 1) if rets else None}
        results.append(r)
        print('\n== %s %s seed=%d ==' % (tag, pos, seed), flush=True)
        print('联合完工: %.1f s (%.1f min) 运输完工: %.1f 中继最晚返场: %.0f' % (
            joint, joint / 60, m['makespan'], max(rets) if rets else -1))
        print('运输能耗 %.2f 中继能耗 %.3f 迟到 %.3f 硬 %s' % (
            m['energy'], relay_e, m['tardy_w'], m['hard_ok']))
        print('cover_bad=%d R2_overlap=%.0f machine_pen=%.0f 电池违规=%d' % (
            cov_bad, overlap, mpen, len(viol)))
    out = {'input': src_json, 'pos_name': pos_name,
           'pos': {k: list(v) for k, v in pos.items()}, 'results': results}
    p = os.path.join(OUTD, 'p3v29_%s_%s.json' % (tag, pos_name))
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p3v29_%s_%s.json' % (tag, pos_name))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pos', default='orig', choices=['orig', 'new'])
    ap.add_argument('--iters', type=int, default=3500)
    args = ap.parse_args()
    pos = POS_ORIG if args.pos == 'orig' else POS_NEW
    run('p2v28_compliant_makespan.json', 'makespan', pos, args.pos, seeds=(7, 77), iters=args.iters)
    run('p2v28d_compliant_energy.json', 'energy', pos, args.pos, seeds=(7, 77), iters=args.iters)


if __name__ == '__main__':
    main()