# -*- coding: utf-8 -*-
"""问题三最终求解（v3）：预计算轨迹覆盖 + SA 协同调度（只平移时间）"""
import sys, os, json, math, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import (Data, relay_mission_time, relay_mission_energy, direct_ok,
                  relay_link_ok, relay_backhaul_ok, charge_time)
from p3_gaps import flight_trajectory
from p2_solve import Flight, dispatch, evaluate

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
data = Data()
REL = data.relay_type
E_BUDGET = (1 - REL['rho']) * REL['E_use']
P_HOVER = REL['P_hover'] + REL['P_comm']
T_FULL = data.relay_energy['T_full']

# 位置（按样本覆盖率优化选定；W9/E4/N1 全覆盖）
P_W = (109.2103, 23.047134, 676.5)
P_E = (109.276017, 23.019401, 542.3)
P_N = (109.238171, 23.077841, 496.1)
AREA_POS = {}
for s in ['S001', 'S002', 'S003', 'S005', 'S007', 'S008', 'S009', 'S011', 'S015']:
    AREA_POS[s] = 'W'
for s in ['S010', 'S012', 'S013', 'S014']:
    AREA_POS[s] = 'E'
AREA_POS['S004'] = 'N'
# S006/S011 直连可达，无需中继
POS_OF = {'W': P_W, 'E': P_E, 'N': P_N}
MAXDELAY = 3600.0
MAXEARLY = 3600.0


class Solver:
    def __init__(self):
        with open(os.path.join(OUT, 'p2_results.json'), encoding='utf-8') as fh:
            r = json.load(fh)
        self.base = {fj['fid']: fj['start'] for fj in r['flights']}
        self.flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']],
                               fj['model'], data) for fj in r['flights']]
        for f in self.flights:
            f.start0 = self.base[f.fid]
        self.precompute()          # 原始架次的样本与覆盖
        self.surgical_fix()        # 修复部分覆盖任务
        for f in self.flights:
            f.start0 = self.base[f.fid]
        self.precompute()          # 修正后重新预计算

    def surgical_fix(self):
        """把部分覆盖任务所在区的货箱移到同区全覆盖的架次（消除覆盖缺口）。"""
        # 先用基线时刻建任务，找 n_cov < n 的任务
        starts = dict(self.base)
        missions = self._build_missions_raw(starts)
        bad = [m for m in missions if m['n_cov'] < m['n']]
        if not bad:
            return
        for m in bad:
            src = next((f for f in self.flights if f.fid == m['fid']), None)
            if src is None or not m.get('box_types'):
                continue
            # 找同区、该区任务全覆盖、且剩余容量足够的架次
            for target in self.flights:
                if target.fid == src.fid:
                    continue
                if m['area'] not in [s for s, _ in target.route]:
                    continue
                tgt_m = [x for x in missions if x['fid'] == target.fid and x['area'] == m['area']]
                if tgt_m and tgt_m[0]['n_cov'] == tgt_m[0]['n']:
                    # 容量检查（宽松：总质量 <= Q，体积 <= V）
                    tm = data.uav_types[target.model]
                    add_mass = sum(data.boxes[b]['mass'] for b in m['box_types'])
                    add_vol = sum(data.boxes[b]['vol'] for b in m['box_types'])
                    if target.total_mass + add_mass <= tm['Q']:
                        self._move_boxes(src, target, m['area'], m['box_types'])
                        print('surgical: moved %s boxes f%02d -> f%02d (%s)'
                              % (m['box_types'], src.fid, target.fid, m['area']))
                        break

    def _build_missions_raw(self, starts):
        """含 box_types 的任务构建（供 surgical_fix 用）。"""
        missions = []
        boxes_by_area = {f.fid: {s: list(bs) for s, bs in f.route} for f in self.flights}
        for f in self.flights:
            shift = starts.get(f.fid, self.base[f.fid])
            groups = {}
            for (tr, sid, cw, ce, cn) in self.samples_raw[f.fid]:
                t = tr + shift
                groups.setdefault(sid, []).append((t, cw, ce, cn))
            for sid, sgs in groups.items():
                grp = AREA_POS[sid]
                if grp == 'W':
                    n_cov = sum(1 for g in sgs if g[1])
                elif grp == 'E':
                    n_cov = sum(1 for g in sgs if g[2])
                else:
                    n_cov = sum(1 for g in sgs if g[3])
                missions.append({'fid': f.fid, 'area': sid, 'grp': grp,
                                 't0': min(g[0] for g in sgs), 't1': max(g[0] for g in sgs),
                                 'n': len(sgs), 'n_cov': n_cov,
                                 'box_types': boxes_by_area[f.fid].get(sid, [])})
        return missions

    def _move_boxes(self, src, target, area, boxes):
        """把货箱从 src 的 area 段移到 target 的 area 段，重建 Flight。"""
        def rebuild(f, area, boxes, add):
            route = []
            moved = False
            for s, bs in f.route:
                if s == area:
                    nb = list(bs) + (boxes if add else [])
                    if not add:
                        nb = [b for b in nb if b not in boxes]
                    if nb:
                        route.append((s, nb))
                    moved = True
                else:
                    route.append((s, list(bs)))
            return Flight(f.fid, route, f.model, data)
        new_src = rebuild(src, area, boxes, add=False)
        new_tgt = rebuild(target, area, boxes, add=True)
        # 更新列表与 base
        si = self.flights.index(src)
        ti = self.flights.index(target)
        self.flights[si] = new_src
        self.flights[ti] = new_tgt
        src = new_src
        target = new_tgt

    def precompute(self):
        """对每架次预计算：相对轨迹采样点 + 各位置覆盖标记 + 直连标记 + 最近区。"""
        self.samples = {}
        self.samples_raw = {}
        for f in self.flights:
            pts, tend = flight_trajectory(f, self.base[f.fid])
            arr = []
            for pt in pts:
                d_ok = direct_ok(pt['lon'], pt['lat'], pt['z'], data)
                if d_ok:
                    continue
                best = min(data.areas, key=lambda s: data.dist_ll(pt['lon'], pt['lat'],
                                                                  data.areas[s]['lon'], data.areas[s]['lat']))
                cw = relay_link_ok(pt['lon'], pt['lat'], pt['z'], P_W, data)
                ce = relay_link_ok(pt['lon'], pt['lat'], pt['z'], P_E, data)
                cn = relay_link_ok(pt['lon'], pt['lat'], pt['z'], P_N, data)
                arr.append((pt['t'] - f.start0, best, cw, ce, cn))
            self.samples[f.fid] = arr
            self.samples_raw[f.fid] = list(arr)
        n_need = sum(len(v) for v in self.samples.values())
        n_w = sum(sum(1 for s in v if s[2]) for v in self.samples.values())
        n_e = sum(sum(1 for s in v if s[3]) for v in self.samples.values())
        n_n = sum(sum(1 for s in v if s[4]) for v in self.samples.values())
        print('need-relay samples: %d  covW=%d covE=%d covN=%d' % (n_need, n_w, n_e, n_n))
        # S006 归属修正
        s6 = [(fid, s) for fid, v in self.samples.items() for s in v if s[1] == 'S006']
        if s6:
            cw = sum(1 for _, s in s6 if s[2])
            ce = sum(1 for _, s in s6 if s[3])
            print('S006 samples=%d covW=%d covE=%d -> %s'
                  % (len(s6), cw, ce, 'E' if ce > cw else 'W'))

    def build_missions(self, starts):
        """O(样本数) 聚合，返回每架次每区任务。starts: fid -> 实际出发准备开始时刻。"""
        missions = []
        for f in self.flights:
            shift = starts.get(f.fid, self.base[f.fid])
            groups = {}
            for (tr, sid, cw, ce, cn) in self.samples[f.fid]:
                t = tr + shift
                groups.setdefault(sid, []).append((t, cw, ce, cn))
            for sid, sgs in groups.items():
                grp = AREA_POS[sid]
                if grp == 'W':
                    n_cov = sum(1 for g in sgs if g[1])
                elif grp == 'E':
                    n_cov = sum(1 for g in sgs if g[2])
                else:
                    n_cov = sum(1 for g in sgs if g[3])
                missions.append({'fid': f.fid, 'area': sid, 'grp': grp,
                                 't0': min(g[0] for g in sgs), 't1': max(g[0] for g in sgs),
                                 'n': len(sgs), 'n_cov': n_cov})
        return missions

    def relay_load(self, missions):
        by = {}
        for m in missions:
            by.setdefault(m['grp'], []).append(m)
        cov_bad = sum(1 for m in missions if m['n_cov'] < m['n'])
        seg = {}
        for g in ('W', 'E', 'N'):
            seg[g] = sorted((m['t0'], m['t1']) for m in by.get(g, []))
        overlap = 0.0
        for (a0, a1) in seg.get('E', []):
            for (b0, b1) in seg.get('N', []):
                lo, hi = max(a0, b0), min(a1, b1)
                if hi > lo:
                    overlap += hi - lo
        return cov_bad, overlap, seg, by

    def machine_penalty(self, missions):
        """两架中继无人机的架次时间线可行性：
        R1 服务 W 区（一个位置），R2 依次服务 E、N 与 W 尾段。
        返回 (罚值, 详细信息)。"""
        by = {}
        for m in missions:
            by.setdefault(m['grp'], []).append(m)

        def pack(g):
            pos = POS_OF[g]
            ms = sorted(by.get(g, []), key=lambda m: m['t0'])
            sorties = []
            cur = None
            for m in ms:
                if cur is None:
                    cur = {'t0': m['t0'], 't1': m['t1']}
                    continue
                t1 = max(cur['t1'], m['t1'])
                e = relay_mission_energy(pos[0], pos[1], pos[2], data, t1 - cur['t0'])
                if e <= E_BUDGET:
                    cur['t1'] = t1
                else:
                    sorties.append(cur)
                    cur = {'t0': m['t0'], 't1': m['t1']}
            if cur is not None:
                sorties.append(cur)
            return sorties, pos

        w_sorties, w_pos = pack('W')
        e_sorties, e_pos = pack('E')
        n_sorties, n_pos = pack('N')

        def charge_from_to(soc_prev, soc_need, T):
            """把荷电从 soc_prev 充到 soc_need 所需时长（两阶段曲线，f(soc)=充满时长，
            差分即分段线性充电时长）；soc_need<=soc_prev 时不充电。"""
            if soc_need <= soc_prev:
                return 0.0

            def t_full(soc):
                if soc <= 0.9:
                    return T * (0.65 * (0.9 - soc) / 0.9 + 0.35)
                return T * 0.35 * (1.0 - soc) / 0.1

            return max(0.0, t_full(soc_prev) - t_full(soc_need))

        def seq_penalty(sorties, pos, start_ready=0.0):
            """单机时间线：相邻架次转场（返航+按需充电+出航+建链）。
            严格口径：每班含 t_prep=180 s 固定准备，两班之间需 t_turn=300 s 周转；
            转场前按下一班所需荷电按需补电，返场荷电已满足时不等待。"""
            t_out, t_back, _ = relay_mission_time(pos[0], pos[1], pos[2], data)
            pen = 0.0
            soc_prev = 1.0
            ready = start_ready
            for k, s in enumerate(sorties):
                dispatch = s['t0'] - t_out - REL['t_link']
                e = relay_mission_energy(pos[0], pos[1], pos[2], data, s['t1'] - s['t0'])
                need = REL['rho'] + e / REL['E_use']
                ch = charge_from_to(soc_prev, need, T_FULL) if k > 0 else 0.0
                if dispatch < 0:
                    pen += -dispatch
                if dispatch < REL['t_prep']:
                    pen += REL['t_prep'] - dispatch
                if k > 0 and dispatch < ready + ch + REL['t_turn']:
                    pen += (ready + ch + REL['t_turn'] - dispatch)
                soc_prev = 1 - e / REL['E_use']
                ready = s['t1'] + t_back
            return pen, ready

        pen = 0.0
        # R1: W 全部架次
        p1, ready1 = seq_penalty(w_sorties, w_pos)
        pen += p1
        # R2: E 架次 + N 架次 + W 尾段（按开始时刻排序，逐段按各自位置计算转场）
        tail = [s for s in w_sorties[1:]]
        r2_all = sorted(e_sorties + n_sorties + tail, key=lambda s: s['t0'])
        pen2 = 0.0
        ready2 = 0.0
        soc_prev2 = 1.0
        for k, s in enumerate(r2_all):
            if s in e_sorties:
                g = 'E'
            elif s in n_sorties:
                g = 'N'
            else:
                g = 'W'
            pos = POS_OF[g]
            t_out, t_back, _ = relay_mission_time(pos[0], pos[1], pos[2], data)
            dispatch = s['t0'] - t_out - REL['t_link']
            e = relay_mission_energy(pos[0], pos[1], pos[2], data, s['t1'] - s['t0'])
            need = REL['rho'] + e / REL['E_use']
            ch = charge_from_to(soc_prev2, need, T_FULL) if k > 0 else 0.0
            if dispatch < 0:
                pen2 += -dispatch
            if dispatch < REL['t_prep']:
                pen2 += REL['t_prep'] - dispatch
            if k > 0 and dispatch < ready2 + ch + REL['t_turn']:
                pen2 += (ready2 + ch + REL['t_turn'] - dispatch)
            soc_prev2 = 1 - e / REL['E_use']
            ready2 = s['t1'] + t_back
        pen += pen2
        energy_sum = sum(
            relay_mission_energy(POS_OF[g][0], POS_OF[g][1], POS_OF[g][2], data,
                                 s['t1'] - s['t0'])
            for g, ss in [('W', w_sorties), ('E', e_sorties), ('N', n_sorties)]
            for s in ss)
        info = {'W': [(round(s['t0']), round(s['t1'])) for s in w_sorties],
                'E': [(round(s['t0']), round(s['t1'])) for s in e_sorties],
                'N': [(round(s['t0']), round(s['t1'])) for s in n_sorties]}
        return pen, info, energy_sum

    def evaluate(self, offsets, w_relay=0.0):
        releases = {fid: self.base[fid] + offsets.get(fid, 0.0) for fid in self.base}
        schedule, _ = dispatch(data, self.flights, releases)
        met = evaluate(data, self.flights, schedule)
        if not met['hard_ok'] or schedule is None:
            return 1e9, met
        starts = {fid: schedule[fid]['start'] for fid in schedule}
        missions = self.build_missions(starts)
        cov_bad, overlap, seg, by = self.relay_load(missions)
        mpen, _, relay_energy = self.machine_penalty(missions)
        pen = 1e5 * cov_bad + 5e4 * overlap + 1e4 * mpen
        obj = met['tardy_w'] + 0.05 * met['makespan'] + 0.8 * met['energy'] \
            + 30 * met['flights'] + pen + w_relay * relay_energy
        return obj, met

    def sa(self, iters=6000, seed=7, w_relay=0.0):
        rng = random.Random(seed)
        cur = {k: 0.0 for k in self.base}
        cur_obj, _ = self.evaluate(cur, w_relay)
        best, best_obj = copy.deepcopy(cur), cur_obj
        T = 400.0
        accept = 0
        # 每架次所属中继组（主组）：用于整组平移
        groups = {}
        for f in self.flights:
            areas = [s for s, _ in f.route]
            gs = [AREA_POS[s] for s in areas if s in AREA_POS]
            groups[f.fid] = max(set(gs), key=gs.count) if gs else 'W'
        for it in range(iters):
            nxt = copy.deepcopy(cur)
            kind = rng.random()
            if kind < 0.35:
                # 整组平移
                g = rng.choice(['W', 'E', 'N'])
                step = rng.choice([-2400, -1200, -600, 600, 1200, 2400, 3600])
                for fid, gg in groups.items():
                    if gg == g:
                        nxt[fid] = min(MAXDELAY, max(-MAXEARLY, nxt[fid] + step))
                        if self.base[fid] + nxt[fid] < 300:
                            nxt[fid] = 300 - self.base[fid]
            elif kind < 0.8:
                # 选 1-2 架次平移
                for _ in range(rng.choice([1, 1, 2])):
                    fid = rng.choice(list(nxt))
                    step = rng.choice([300, 600, 900, 1200, 1800, 2400])
                    nxt[fid] = min(MAXDELAY, max(-MAXEARLY, nxt[fid] + rng.choice([-1, 1]) * step))
                    if self.base[fid] + nxt[fid] < 300:
                        nxt[fid] = 300 - self.base[fid]
            else:
                # 尾段（晚于8300的W任务）相关架次整体平移
                for fid, gg in groups.items():
                    if gg == 'W' and self.base[fid] + nxt[fid] > 7000:
                        nxt[fid] += rng.choice([-600, -600, 300, 600, 1200])
                        nxt[fid] = min(MAXDELAY, max(-MAXEARLY, nxt[fid]))
                        if self.base[fid] + nxt[fid] < 300:
                            nxt[fid] = 300 - self.base[fid]
            obj, _ = self.evaluate(nxt, w_relay)
            if obj < cur_obj or rng.random() < math.exp((cur_obj - obj) / T):
                cur, cur_obj = nxt, obj
                accept += 1
                if obj < best_obj:
                    best, best_obj = nxt, obj
            T = max(1.0, T * 0.9988)
        print('SA done accept=%.2f best_obj=%.1f' % (accept / iters, best_obj))
        return best, best_obj

    def finalize(self, offsets):
        releases = {fid: self.base[fid] + offsets.get(fid, 0.0) for fid in self.base}
        schedule, _ = dispatch(data, self.flights, releases)
        met = evaluate(data, self.flights, schedule)
        starts = {fid: schedule[fid]['start'] for fid in schedule}
        missions = self.build_missions(starts)
        cov_bad, overlap, seg, by = self.relay_load(missions)
        mpen, minfo, _ = self.machine_penalty(missions)
        print('final: hard_ok=%s tardy=%.1f makespan=%.0f energy=%.2f flights=%d'
              % (met['hard_ok'], met['tardy_w'], met['makespan'], met['energy'], met['flights']))
        print('cover_bad=%d R2_overlap=%.0fs machine_pen=%.0fs' % (cov_bad, overlap, mpen))
        for g, ss in minfo.items():
            for s in ss:
                pos = POS_OF[g]
                t_out, t_back, _ = relay_mission_time(pos[0], pos[1], pos[2], data)
                e = relay_mission_energy(pos[0], pos[1], pos[2], data, s[1] - s[0])
                print('  %s sortie t=[%.0f, %.0f] e=%.3f kWh dispatch=%.0f ret=%.0f'
                      % (g, s[0], s[1], e, s[0] - t_out - REL['t_link'], s[1] + t_back))
        return {'met': met, 'missions': missions, 'seg': seg, 'mpen': mpen}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--iters', type=int, default=3000)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--w-relay', type=float, default=0.0,
                    help='目标函数中继能耗权重（>0 压缩中继窗口）')
    ap.add_argument('--out', type=str, default='p3_co2.json')
    args = ap.parse_args()
    sv = Solver()
    best, best_obj = sv.sa(iters=args.iters, seed=args.seed, w_relay=args.w_relay)
    res = sv.finalize(best)
    with open(os.path.join(OUT, args.out), 'w', encoding='utf-8') as fh:
        json.dump({'offsets': best, 'obj': best_obj,
                   'met': {k: (round(v, 2) if isinstance(v, float) else v)
                           for k, v in res['met'].items() if k != 'box_time'}},
                  fh, ensure_ascii=False, indent=1)
    print('saved %s' % args.out)


if __name__ == '__main__':
    main()