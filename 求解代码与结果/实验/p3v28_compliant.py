# -*- coding: utf-8 -*-
"""p3v28_compliant.py —— 合规电池口径下的 P3 联合调度重算。
- 输入：结果/进化_v25/p2v28_compliant_makespan.json（28架）与 p2v28d_compliant_energy.json（25架）
- monkey-patch p3_co2.OUT 到临时目录（不碰工作区 results/p2_results.json）
- monkey-patch p3_co2.dispatch = dispatch_compliant（支持 releases），使 Solver 的
  evaluate/sa/finalize 全部走合规电池调度
- 联合完工 = max(运输合规完工, 中继班次最晚返场 ret)；SA seed 7/77，PYTHONHASHSEED=0
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


def run(src_json, tag, seeds=(7, 77), iters=2500):
    d = json.load(open(os.path.join(OUTD, src_json), encoding='utf-8'))
    fls = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
           for f in d['solution']]
    # 合规调度得到 base start
    sch, _ = dispatch_compliant(data, fls)
    if sch is None:
        print('[%s] compliant dispatch 失败' % tag, flush=True)
        return None
    base = {fid: sch[fid]['start'] for fid in sch}
    # 写 p3 输入（临时目录）
    p3in = os.path.join(OUTD, 'p3in_v28')
    os.makedirs(p3in, exist_ok=True)
    p3_co2.OUT = p3in
    flights_json = [{'fid': f.fid, 'start': base[f.fid],
                     'route': [[s, list(bs)] for s, bs in f.route], 'model': f.model}
                    for f in fls]
    json.dump({'flights': flights_json}, open(os.path.join(p3in, 'p2_results.json'), 'w',
                                              encoding='utf-8'), ensure_ascii=False)
    # 关键：让 P3 全部用合规调度（自实现 evaluate/finalize：单次 dispatch，无二次调用不一致）
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
        # 零迟到硬罚优先：任何迟到(期望口径)为大惩罚，先于中继惩罚权衡
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
                pos = p3_co2.POS_OF[g]
                t_out, t_back, _ = p3_co2.relay_mission_time(pos[0], pos[1], pos[2], data)
                e = p3_co2.relay_mission_energy(pos[0], pos[1], pos[2], data, s[1] - s[0])
                print('  %s sortie t=[%.0f, %.0f] e=%.3f kWh dispatch=%.0f ret=%.0f'
                      % (g, s[0], s[1], e, s[0] - t_out - p3_co2.REL['t_link'], s[1] + t_back))
        return {'met': met, 'missions': missions, 'seg': seg, 'mpen': mpen}

    p3_co2.Solver.evaluate = safe_evaluate
    p3_co2.Solver.finalize = safe_finalize
    sv = p3_co2.Solver()
    results = []
    for seed in seeds:
        best, obj = sv.sa(iters=iters, seed=seed, w_relay=0.0)
        # finalize 安全回退
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = sv.finalize(best)
        if res is None:
            with contextlib.redirect_stdout(buf):
                res = sv.finalize({k: 0.0 for k in sv.base})
        txt = buf.getvalue()
        m = res['met']
        # 中继班次最晚返场 / 中继能耗 / 覆盖（从 finalize 打印解析）
        rets = [float(x) for x in re.findall(r'ret=([\d.]+)', txt)]
        es = [float(x) for x in re.findall(r'e=([\d.]+) kWh', txt)]
        cov_bad = int(re.search(r'cover_bad=(\d+)', txt).group(1))
        overlap = float(re.search(r'R2_overlap=([\d.]+)s', txt).group(1))
        mpen = float(re.search(r'machine_pen=([\d.]+)s', txt).group(1))
        relay_e = sum(es)
        joint = max(m['makespan'], max(rets)) if rets else m['makespan']
        # 电池违规复核（finalize 的 releases）
        releases = {fid: sv.base[fid] + best.get(fid, 0.0) for fid in sv.base}
        sch2, _ = dispatch_compliant(data, sv.flights, releases=releases)
        viol = check_battery(data, sch2, sv.flights)
        r = {'seed': seed, 'tag': tag, 'joint': round(joint, 1), 'joint_min': round(joint / 60, 1),
             'transport_mk': round(m['makespan'], 1), 'transport_min': round(m['makespan'] / 60, 1),
             'transport_energy': round(m['energy'], 2), 'flights': m['flights'],
             'tardy_w': round(m['tardy_w'], 3), 'hard_ok': m['hard_ok'],
             'relay_energy': round(relay_e, 3), 'cover_bad': cov_bad, 'overlap': round(overlap, 1),
             'mpen': round(mpen, 1), 'battery_violations': len(viol),
             'relay_ret_max': round(max(rets), 1) if rets else None}
        results.append(r)
        print('\n== %s seed=%d ==' % (tag, seed), flush=True)
        print('联合完工: %.1f s (%.1f min)  运输完工: %.1f s (%.1f min)  中继最晚返场: %.0f' % (
            joint, joint / 60, m['makespan'], m['makespan'] / 60, max(rets) if rets else -1))
        print('运输能耗: %.2f kWh  中继能耗: %.3f kWh  迟到: %.3f  硬: %s' % (
            m['energy'], relay_e, m['tardy_w'], m['hard_ok']))
        print('cover_bad=%d R2_overlap=%.0fs machine_pen=%.0fs 电池违规=%d' % (
            cov_bad, overlap, mpen, len(viol)))
    out = {'input': src_json, 'base_flights': len(fls), 'results': results}
    p = os.path.join(OUTD, 'p3v28_compliant_%s.json' % tag)
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved -> 结果/进化_v25/p3v28_compliant_%s.json' % tag)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iters', type=int, default=2500)
    args = ap.parse_args()
    run('p2v28_compliant_makespan.json', 'makespan', seeds=(7, 77), iters=args.iters)
    run('p2v28d_compliant_energy.json', 'energy', seeds=(7, 77), iters=args.iters)


if __name__ == '__main__':
    main()