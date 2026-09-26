# -*- coding: utf-8 -*-
"""ppo23_env.py —— PPO 环境：23 架解的 learn-to-improve。
状态：池统计 + 每趟特征（23x7）；动作：启发式预生成 top-K 候选邻域算子；奖励密集。
参考：Schulman et al. 2017 (PPO)；Bello et al. 2016 / Kool et al. 2019 (组合优化 RL)；
Cheng et al. 2025 (A2C+GAE 装箱)；Qu & Hu 2025 (注意力路由带时间窗多目标)。
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import eval_full

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, '..', '结果', '进化_v25')
data = Data()
MODELS = ['A', 'B', 'C']
K = 60  # 候选动作槽
W_EN = float(os.environ.get('W_EN', '1.5'))  # 能耗奖励权重（调整参数用）
ALL_SIDS = sorted(set(b.split('-')[0] for b in data.boxes))
SID_IDX = {s: i for i, s in enumerate(ALL_SIDS)}


def state_vec(fls, m):
    """解→特征向量。池统计(9) + 每趟(7) x 23 = 170 维。"""
    if m is None:
        return np.zeros(170, np.float32)
    try:
        sch, _ = dispatch_compliant(data, fls)
    except TypeError:
        sch = None
    pools = {'A': 4, 'B': 2, 'C': 2}
    pt = {g: 0.0 for g in pools}
    pc = {g: 0 for g in pools}
    for f in fls:
        pt[f.model] += f.duration()
        pc[f.model] += 1
    v = [m['makespan'] / 9000.0, m['energy'] / 90.0, len(fls) / 30.0,
         pt['A'] / (4 * 9000), pt['B'] / (2 * 9000), pt['C'] / (2 * 9000),
         pc['A'] / 20.0, pc['B'] / 20.0, pc['C'] / 20.0]
    srt = sorted(fls, key=lambda f: f.fid)
    for i in range(23):
        if i < len(srt):
            f = srt[i]
            mn = min(data.boxes[b]['deadline_exp'] for b in f.box_ids)
            sid = f.route[0][0] if f.route else 'S000'
            v += [f.duration() / 3000.0, f.energy() / 7.0, f.total_mass / 80.0,
                  len(f.box_ids) / 8.0, mn / 14400.0,
                  0.0 if f.model == 'A' else (0.5 if f.model == 'B' else 1.0),
                  SID_IDX.get(sid, 0.0) / 15.0]
        else:
            v += [0.0] * 7
    return np.asarray(v, np.float32)[:170]


def build_candidates(fls):
    """启发式生成候选操作：(type, fid_a, fid_b, box, aux)。"""
    cands = []
    m, s, v, nc = eval_full(data, fls)
    if m is None:
        return []
    grp = {}
    for f in fls:
        if len(f.route) == 1:
            grp.setdefault(f.route[0][0], []).append(f)
    for sid, fs in grp.items():
        for i in range(len(fs)):
            for j in range(len(fs)):
                if i == j:
                    continue
                for box in fs[i].box_ids:
                    nf = Flight(0, [(sid, list(fs[j].box_ids) + [box])], fs[j].model, data)
                    if nf.is_feasible():
                        cands.append(('mig', fs[i].fid, fs[j].fid, box, sid))
    for f in fls:
        for gm in MODELS:
            if gm != f.model:
                nf = Flight(0, f.route, gm, data)
                if nf.is_feasible():
                    cands.append(('ret', f.fid, -1, None, gm))
    np.random.shuffle(cands)
    return cands[:K]


def apply_cand(fls, c):
    t, a, b, box, x = c
    if t == 'mig':
        fa = next(u for u in fls if u.fid == a)
        fb = next(u for u in fls if u.fid == b)
        ra = [(sid2, [bb for bb in bs if bb != box]) for sid2, bs in fa.route]
        rb = [(sid2, list(bs) + [box]) for sid2, bs in fb.route]
        if not ra or not ra[0][1]:
            return None
        nfa = Flight(fa.fid, ra, fa.model, data)
        if not nfa.is_feasible():
            return None
        nfb = Flight(fb.fid, rb, fb.model, data)
        if not nfb.is_feasible():
            return None
        return [u for u in fls if u.fid not in (a, b)] + [nfa, nfb]
    if t == 'ret':
        f = next(u for u in fls if u.fid == a)
        nf = Flight(f.fid, f.route, x, data)
        if not nf.is_feasible():
            return None
        return [u for u in fls if u.fid != a] + [nf]
    return None


def eval_improve(fls, cand):
    nf = apply_cand(fls, cand)
    if nf is None:
        return None
    m0, s0, v0, nc0 = eval_full(data, fls)
    m1, s1, v1, nc1 = eval_full(data, nf)
    if m1 is None or v1 > 0 or nc1 > 0 or (not m1['hard_ok']):
        return None
    d_mk = m0['makespan'] - m1['makespan']
    d_en = m0['energy'] - m1['energy']
    r = d_mk / 60.0 + W_EN * d_en
    return r, nf


class PPO23Env:
    def __init__(self, start_json):
        d0 = json.load(open(start_json, encoding='utf-8'))
        self.base = [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
                     for f in d0['solution']]
        self.reset()

    def reset(self):
        self.fls = [Flight(f.fid, [(s, list(bs)) for s, bs in f.route], f.model, data)
                    for f in self.base]
        self.t = 0
        self.cur_cands = []
        return self.observe()

    def observe(self):
        m, s, v, nc = eval_full(data, self.fls)
        return state_vec(self.fls, m)

    def step(self, action_idx):
        nf_good = None
        if action_idx < len(self.cur_cands):
            imp = eval_improve(self.fls, self.cur_cands[action_idx])
            if imp is not None:
                r, nf = imp
                if nf is not None:
                    self.fls = nf
                    nf_good = True
        self.t += 1
        done = self.t >= 40
        if done:
            m, s, v, nc = eval_full(data, self.fls)
            r = -(m['makespan'] / 60.0 + W_EN * m['energy']) + 250.0
        elif nf_good is None:
            r = -1.0
        return self.observe(), r, done, {}

    def run_candidates(self):
        self.cur_cands = build_candidates(self.fls)
        mk = np.zeros(K, np.float32)
        for i in range(min(len(self.cur_cands), K)):
            mk[i] = 1.0
        return mk