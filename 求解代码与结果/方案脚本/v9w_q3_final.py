# -*- coding: utf-8 -*-
"""v9w：v9v 修复——
① f14(B) 只留 S010×3（25kg/0.067/1.82），S013-FOD-01 → f12（19kg/0.068/2.59 ✓）
② f30(A) 由 NEW_FLIGHTS 直接装载（消除与 MOVES 的重复装载）
③ S003-WAT-02 → f10（S003×5：MED+FOD-01+WAT-03+WAT-01+WAT-02，p58 领先 f7）
   f6 只留 S015×2+S011（p22/10800），尾部任务缩短
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'code'))
sys.stdout.reconfigure(encoding='utf-8')
from core import (relay_mission_time, relay_mission_energy, direct_ok,
                  relay_link_ok, charge_time)
from p3_gaps import flight_trajectory
from p2_solve import Flight, dispatch, evaluate
from v8_q3_auto import POS_OF, AREA_POS, data, REL, T_FULL, make_sorties

AREA_POS = dict(AREA_POS)
AREA_POS['S006'] = 'W'

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')

MOVES = [('S007-HYG-01', 10, None),
         ('S013-FOD-01', 23, 12), ('S014-FOD-01', 23, 13),
         ('S010-FOD-01', 13, 14),
         ('S003-WAT-02', 6, 10),
         ('S001-MED-01', 1, 30),
         ('S001-WAT-08', 5, None), ('S009-FOD-01', 5, 24)]
NEW_FLIGHTS = {30: ('A', [('S001', ['S001-WAT-08'])]),
               200: ('A', [('S007', ['S007-HYG-01'])])}
MODEL_CHANGES = {14: 'B', 24: 'A'}
FLOORS = {20: 2485.0, 15: 1857.0}


class PlanCache:
    def __init__(self, flights):
        self.points = {}
        for f in flights:
            pts, _ = flight_trajectory(f, 0.0)
            arr = []
            for pt in pts:
                if direct_ok(pt['lon'], pt['lat'], pt['z'], data):
                    continue
                sid = min(data.areas, key=lambda s: data.dist_ll(
                    pt['lon'], pt['lat'], data.areas[s]['lon'], data.areas[s]['lat']))
                cov = tuple(relay_link_ok(pt['lon'], pt['lat'], pt['z'], POS_OF[g], data)
                            for g in 'WEN')
                arr.append((pt['t'], sid, cov))
            self.points[f.fid] = arr

    def missions(self, flights, starts):
        ms = []
        for f in flights:
            s0 = starts[f.fid]
            groups = {}
            for rel_t, sid, cov in self.points[f.fid]:
                groups.setdefault(sid, []).append((s0 + rel_t, cov))
            for sid, lst in groups.items():
                if sid not in AREA_POS:
                    continue
                tlist = [t for t, _ in lst]
                covs = [cov for _, cov in lst]
                best = None
                for c in [AREA_POS[sid]] + [g for g in 'WEN' if g != AREA_POS[sid]]:
                    gi = 'WEN'.index(c)
                    if all(cov[gi] for cov in covs):
                        best = c
                        break
                if best is None:
                    gi = max(range(3), key=lambda i: sum(1 for cov in covs if cov[i]))
                    best = 'WEN'[gi]
                gi = 'WEN'.index(best)
                n_cov = sum(1 for cov in covs if cov[gi])
                ms.append({'fid': f.fid, 'area': sid, 'grp': best,
                           't0': min(tlist), 't1': max(tlist),
                           'n': len(lst), 'n_cov': n_cov})
        return ms

    def relay_pen(self, flights, starts):
        ms = self.missions(flights, starts)
        by = {}
        for m in ms:
            by.setdefault(m['grp'], []).append(m)
        w = make_sorties('W', by)
        e = make_sorties('E', by)
        n = make_sorties('N', by)
        tail = [s for s in w[1:]]
        r2 = sorted(e + n + tail, key=lambda s: s['t0'])
        p1 = timeline_penalty(w, 'R1')
        p2 = timeline_penalty(r2, 'R2')
        return p1 + p2, ms, w, e, n


def timeline_penalty(sorties, label):
    pen = 0.0
    ready = 0.0
    for k, s in enumerate(sorties):
        pos = POS_OF[s['g']]
        t_out, t_back, _ = relay_mission_time(pos[0], pos[1], pos[2], data)
        dt = s['t0'] - t_out - REL['t_link']
        if k > 0 and dt < ready:
            pen += ready - dt
        e = relay_mission_energy(pos[0], pos[1], pos[2], data, s['t1'] - s['t0'])
        ch = charge_time(1 - e / REL['E_use'], T_FULL)
        ready = s['t1'] + t_back + ch
    return pen


def rebuild_route(route, box, tgt_area, remove=False):
    out = []
    added = False
    for s, bs in route:
        if remove and box in bs:
            bs = [b for b in bs if b != box]
        if not remove and s == tgt_area:
            bs = list(bs) + [box]
            added = True
        if bs:
            out.append((s, bs))
    if not remove and not added:
        out.append((tgt_area, [box]))
    return out


def build(flights):
    for fid, (model, route) in NEW_FLIGHTS.items():
        flights.append(Flight(fid, [(s, list(b)) for s, b in route], model, data))
        print('new f%02d (%s) %s' % (fid, model, route), flush=True)
    for box, src, tgt in MOVES:
        f_src = next(f for f in flights if f.fid == src)
        flights[flights.index(f_src)] = Flight(f_src.fid,
                                               rebuild_route(f_src.route, box, None, remove=True),
                                               f_src.model, data)
        print('move %s f%02d -> %s' % (box, src, 'REMOVE' if tgt is None else 'f%02d' % tgt),
              flush=True)
        if tgt is None:
            continue
        f_tgt = next(f for f in flights if f.fid == tgt)
        flights[flights.index(f_tgt)] = Flight(f_tgt.fid,
                                               rebuild_route(f_tgt.route, box,
                                                             data.boxes[box]['area'],
                                                             remove=False), f_tgt.model, data)
    for fid, model in MODEL_CHANGES.items():
        f = next(x for x in flights if x.fid == fid)
        flights[flights.index(f)] = Flight(f.fid, [(s, list(b)) for s, b in f.route],
                                           model, data)
        print('model f%02d -> %s' % (fid, model), flush=True)
    flights = [f for f in flights if f.box_ids]
    return flights


def run(floors=None):
    floors = dict(FLOORS if floors is None else floors)
    r = json.load(open(os.path.join(OUT, 'p2_results.json'), encoding='utf-8'))
    base = {fj['fid']: fj['start'] for fj in r['flights']}
    flights = [Flight(fj['fid'], [(s, list(b)) for s, b in fj['route']], fj['model'], data)
               for fj in r['flights']]
    flights = build(flights)
    rel_all = {f.fid: max(0.0, base.get(f.fid, 0.0) + floors.get(f.fid, 0.0))
               for f in flights}
    infeas = [(f.fid, f.model, round(f.energy(), 2), round(f.total_mass, 1),
               round(f.total_vol, 3)) for f in flights if not f.is_feasible()]
    print('infeasible flights:', infeas, flush=True)
    schedule, _ = dispatch(data, flights, rel_all)
    met = evaluate(data, flights, schedule)
    cache = PlanCache(flights)
    starts = {f.fid: schedule[f.fid]['start'] for f in flights}
    pen, missions, w_s, e_s, n_s = cache.relay_pen(flights, starts)
    cov_bad = [m for m in missions if m['n_cov'] < m['n']]
    bad = []
    for fid, s in schedule.items():
        for sid, bid, t in s['deliveries']:
            bx = data.boxes[bid]
            for tag, dl in (('first', bx['deadline_first']), ('exp', bx['deadline_exp'])):
                if dl != float('inf') and t > dl + 1e-6:
                    bad.append((bid, fid, tag, round(float(t), 1), dl))
    print('transport:', {k: (round(v, 1) if isinstance(v, float) else v)
                         for k, v in met.items() if k != 'box_time'})
    print('pen=%.1f cover_bad=%d missions=%d violations=%d' %
          (pen, len(cov_bad), len(missions), len(bad)))
    for b in bad:
        print('  违规: %s f%02d %s t=%.1f dl=%.0f' % b)
    for m in cov_bad:
        print('  覆盖缺口: %s f%02d %s t0=%.0f t1=%.0f %d/%d' %
              (m['area'], m['fid'], m['grp'], m['t0'], m['t1'], m['n_cov'], m['n']))
    for g, ss in (('W', w_s), ('E', e_s), ('N', n_s)):
        pos = POS_OF[g]
        for k, s in enumerate(ss):
            e = relay_mission_energy(pos[0], pos[1], pos[2], data, s['t1'] - s['t0'])
            print('  %s sortie%d [%.0f,%.0f] e=%.2f ms=%s' % (g, k, s['t0'], s['t1'], e,
                                                              [m['fid'] for m in s['ms']]))
    print('S003 deliveries:')
    for d in schedule.values():
        for sid, bid, t in d['deliveries']:
            if sid == 'S003':
                bx = data.boxes[bid]
                dl = min(v for v in (bx['deadline_first'], bx['deadline_exp'])
                         if v != float('inf'))
                print('   %s t=%.1f (dl %s) %s' % (bid, t, dl, 'VIOL' if t > dl else ''))
    print('S015/S011 deliveries:')
    for d in schedule.values():
        for sid, bid, t in d['deliveries']:
            if sid in ('S015', 'S011'):
                print('   %s t=%.1f' % (bid, t))
    def sjson(relay, g, ss):
        pos = POS_OF[g]
        return [{'relay': relay, 'pos': g, 't0': round(s['t0'], 1), 't1': round(s['t1'], 1),
                 'energy': round(relay_mission_energy(pos[0], pos[1], pos[2], data,
                                                      s['t1'] - s['t0']), 3),
                 'missions': [m['fid'] for m in s['ms']]} for s in ss]
    out = {
        'transport': {k: (float(v) if hasattr(v, 'item') else v)
                      for k, v in met.items() if k != 'box_time'},
        'releases': {str(k): round(v, 1) for k, v in rel_all.items()
                     if v != base.get(k, 0.0)},
        'box_moves': [list(m) for m in MOVES],
        'flights': [{'fid': f.fid, 'model': f.model, 'mass': round(f.total_mass, 1),
                     'energy': round(f.energy(), 3), 'route': [[s, b] for s, b in f.route]}
                    for f in flights],
        'schedule': {str(k): {'uav': v['uav'], 'battery': v['battery'],
                              'start': round(v['start'], 1), 'return': round(v['return'], 1),
                              'energy': round(v['energy'], 3),
                              'deliveries': [[d[0], d[1], round(d[2], 1)] for d in v['deliveries']]}
                     for k, v in schedule.items()},
        'missions': missions,
        'sorties': sjson('R01', 'W', w_s) + sjson('R02', 'E', e_s) + sjson('R02', 'N', n_s),
    }
    with open(os.path.join(OUT, 'p3_final.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('saved p3_final.json (v9w)', flush=True)
    return met['hard_ok'] and not cov_bad and pen <= 1e-6 and not bad


if __name__ == '__main__':
    ok = run()
    print('v9w ok =', ok, flush=True)