# -*- coding: utf-8 -*-
"""dqn23_gat.py —— 图注意力 DRL + 边级动作表征 + 中心化V/局部A分解 + 自模仿持续进化（v61）。
v60 无增益根因修复（对照文献）：
1. **边级动作表征**（SAGE edge-gated message passing, Xue 2026; Khalil 2017 S2V 局部动作; Yu 2019 图嵌入）：
   迁移动作 (src趟→dst趟) 用 GAT 节点嵌入的"边表征" g(e_src, e_dst) 而非索引——图结构真正作用于动作。
2. **中心化 V + 局部 A 分解**（QMIX/VDN value decomposition; Wang 2016 Dueling 图级化）：
   V=全局图 readout（瓶颈池/C链势），A=动作边表征——中心化价值、去中心化优势。
3. **跨区迁移动作**（新算子，图边表达）：箱可迁往任一含其属区的趟（原启发式仅同区）——图归纳偏置的用武之地。
4. **自模仿持续进化**（Oh et al. 2018 Self-Imitation Learning）：每轮 greedy 改进路径注入经验池 imp 桶；
   经验池跨轮保留（持续学习），起点滚动。
"""
import sys, os, json, time, math
from collections import deque
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dqn23_enhanced import (data, OUTD, K, A_DIM, FEAT_DIM, S_DIM, state_vec, eval_full,
                            pool_stats, make_mask, terminal_r, clone)
from p2v35_mk import split_into_ab
from p2_solve import Flight

torch.manual_seed(0)
np.random.seed(0)
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('device', DEV, flush=True)
NSTEP = int(os.environ.get('NSTEP', '3'))
IMP_R = float(os.environ.get('IMP_RATIO', '0.4'))
TAG = os.environ.get('TAG', '')
START = os.environ.get('START_JSON', 'p2v54_mk_rettype.json')
ROUNDS = int(os.environ.get('ROUNDS', '1'))  # 持续进化轮数（跨轮经验池保留）
EPS0, EPS_END = 0.5, 0.05
GF = 12
GH = 32
S_DIM_X = 224  # 增强状态：170(23趟) + 电池4 + 余量3 + 超额趟6×7 + 额外趟统计2 = 221→224
FA_X = 16  # 增强动作特征：12 + 约束余量3 + 时限差1


def load_init():
    d0 = json.load(open(os.path.join(OUTD, START), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d0['solution']]


def zone_of(bid):
    return bid.split('-')[0]


def build_graph(fls, m=None, mig_edges=None):
    """趟图：节点特征 (NP=32,12) + 邻接（同池/同区/可行迁移对），pad 固定节点数（拆分改变趟数）。"""
    NP = 48
    N = len(fls)
    X = np.zeros((NP, GF), np.float32)
    pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    np_ = {'A': 4, 'B': 2, 'C': 2}
    E_USE = {'A': 4.5, 'B': 4.0, 'C': 8.0}
    for f in fls:
        pt[f.model] += f.duration()
    mk = m['makespan'] if m is not None else 7200.0
    gm_i = {'A': 0, 'B': 1, 'C': 2}
    zones = [f.route[0][0] for f in fls]
    for i, f in enumerate(fls):
        g = gm_i[f.model]
        X[i, g] = 1.0
        X[i, 3] = f.total_mass / 80.0
        X[i, 4] = f.duration() / 3000.0
        X[i, 5] = f.energy() / E_USE[f.model]
        X[i, 6] = len(f.box_ids) / 8.0
        X[i, 7] = pt[f.model] / np_[f.model] / 7000.0
        X[i, 8] = 1.0 if f.model == 'A' else 0.0
        X[i, 9] = float(sum(ord(ch) for ch in f.route[0][0]) % 16) / 15.0
        X[i, 10] = mk / 8000.0
        X[i, 11] = f.duration() / 3000.0
    A = np.zeros((NP, NP), np.uint8)
    for i in range(N):
        A[i, i] = 1
        for j in range(i + 1, N):
            if fls[i].model == fls[j].model or zones[i] == zones[j]:
                A[i, j] = A[j, i] = 1
    if mig_edges:
        for (i, j) in mig_edges:
            A[i, j] = A[j, i] = 1
    d = A.sum(axis=1).astype(np.float32)
    d = np.where(d > 0, 1.0 / np.sqrt(d), 0.0)
    An = (A.astype(np.float32) * d[:, None] * d[None, :])
    pv = np.array([pt[g] / np_[g] / 7000.0 for g in 'ABC'], np.float32)
    return (torch.from_numpy(X).float(), torch.from_numpy(An).float(),
            torch.from_numpy(pv).float())


def apply_cand_x(fls, c):
    """跨区安全 apply：box 只加到目标趟的属区段（原 apply_cand 对多区趟逐段加箱，错误）。"""
    t, a, b, box, x = c
    if t == 'mig':
        fa = next(u for u in fls if u.fid == a)
        fb = next(u for u in fls if u.fid == b)
        ra = [(s2, [bb for bb in bs if bb != box]) for s2, bs in fa.route]
        rb = [(s2, list(bs) + ([box] if s2 == zone_of(box) else [])) for s2, bs in fb.route]
        if not ra or not ra[0][1]:
            return None
        nfa = Flight(fa.fid, ra, fa.model, data)
        if not nfa.is_feasible():
            return None
        nfb = Flight(fb.fid, rb, fb.model, data)
        if not nfb.is_feasible():
            return None
        return [u for u in fls if u.fid not in (a, b)] + [nfa, nfb]
    if t == 'sp':
        f = next(u for u in fls if u.fid == a)
        parts = split_into_ab(fls, f, data)
        if not parts:
            return None
        return [u for u in fls if u.fid != a] + parts
    if t == 'ret':
        f = next(u for u in fls if u.fid == a)
        nf = Flight(f.fid, f.route, x, data)
        if not nf.is_feasible():
            return None
        return [u for u in fls if u.fid != a] + [nf]
    return None


def eval_improve_scene_x(fls, cand):
    """场景奖励（同 enhanced）+ 跨区安全 apply（v61）。"""
    w_en = float(os.environ.get('W_EN', '0.3'))
    w_pool = float(os.environ.get('W_POOL', '0.05'))
    w_chg = float(os.environ.get('W_CHG', '0.02'))
    nf = apply_cand_x(fls, cand)
    if nf is None:
        return None
    m0, s0, v0, nc0 = eval_full(data, fls)
    m1, s1, v1, nc1 = eval_full(data, nf)
    if m1 is None or v1 > 0 or nc1 > 0 or (not m1['hard_ok']):
        return None
    d_mk = m0['makespan'] - m1['makespan']
    d_en = m0['energy'] - m1['energy']
    ps0, ch0 = pool_stats(fls)
    ps1, ch1 = pool_stats(nf)
    r = d_mk / 60.0 + w_en * d_en + w_pool * (ps0 - ps1) - w_chg * (ch1 - ch0)
    return r, nf


def build_candidates_x(fls):
    """扩展候选：同区/跨区迁移（box→任一含属区的趟）+ 换型 + 池均衡近似评分。
    返回 (c, feats, scores, sidx, didx)；c 仅真实候选（≤K），STOP 由索引 K 隐式表示（同 enhanced）。"""
    c = []
    fa = []
    sc = []
    sidx = []
    didx = []
    N = len(fls)
    pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    np_ = {'A': 4, 'B': 2, 'C': 2}
    for f in fls:
        pt[f.model] += f.duration()
    for i, fi in enumerate(fls):
        zz = set(route_s for route_s, _ in fi.route)
        for b in fi.box_ids:
            zb = zone_of(b)
            for j, fj in enumerate(fls):
                if j == i or not any(route_s == zb for route_s, _ in fj.route):
                    continue
                if b in fj.box_ids:
                    continue
                nb = data.boxes[b]
                if fj.total_mass + nb['mass'] > {'A': 25, 'B': 30, 'C': 80}[fj.model] + 1e-9:
                    continue
                if fj.total_vol + nb['vol'] > {'A': 0.058, 'B': 0.071, 'C': 0.25}[fj.model] + 1e-9:
                    continue
                if zb not in zz:
                    continue
                pi = pt[fi.model] / np_[fi.model]
                pj = pt[fj.model] / np_[fj.model]
                sc_ = (pi - pj) / 7000.0
                Qj = {'A': 25.0, 'B': 30.0, 'C': 80.0}[fj.model]
                Vj = {'A': 0.058, 'B': 0.071, 'C': 0.25}[fj.model]
                Ejm = (1.0 - 0.2) * {'A': 4.5, 'B': 4.0, 'C': 8.0}[fj.model] - fj.energy()
                csrc = min(data.boxes[bb]['deadline_exp'] for bb in fi.box_ids)
                cdst = min(data.boxes[bb]['deadline_exp'] for bb in fj.box_ids)
                c_ = (csrc - cdst) / 14400.0
                c.append(('mig', fi.fid, fj.fid, b, zb))
                fa.append([0.0, 1.0, 0.0, pi / 7000.0, pj / 7000.0,
                          nb['mass'] / 80.0, fj.duration() / 3000.0, len(fj.box_ids) / 8.0,
                          fi.duration() / 3000.0, 0.0, sc_, 1.0,
                          (Qj - fj.total_mass) / Qj, (Vj - fj.total_vol) / Vj,
                          max(0.0, Ejm / 2.0), c_])
                sc.append(sc_)
                sidx.append(i)
                didx.append(j)
    for i, fi in enumerate(fls):
        for gm in ['A', 'B', 'C']:
            if gm == fi.model:
                continue
            nf = Flight(fi.fid, fi.route, gm, data)
            if not nf.is_feasible():
                continue
            pi = pt[fi.model] / np_[fi.model]
            pj = pt[gm] / np_[gm]
            sc_ = (pi - pj) / 7000.0 + 0.02
            Qg = {'A': 25.0, 'B': 30.0, 'C': 80.0}[gm]
            Vg = {'A': 0.058, 'B': 0.071, 'C': 0.25}[gm]
            Egm = (1.0 - 0.2) * {'A': 4.5, 'B': 4.0, 'C': 8.0}[gm] - nf.energy()
            c.append(('ret', fi.fid, -1, None, gm))
            fa.append([1.0, 0.0, 0.0, pi / 7000.0, pj / 7000.0,
                      fi.total_mass / 80.0, nf.duration() / 3000.0, len(fi.box_ids) / 8.0,
                      fi.duration() / 3000.0, 0.0, sc_, 0.0,
                      (Qg - nf.total_mass) / Qg, (Vg - nf.total_vol) / Vg,
                      max(0.0, Egm / 2.0), 0.0])
            sc.append(sc_)
            sidx.append(i)
            didx.append(i)
    # 拆分（动作完备性：满载单区趟(≥3箱) → A/B 子趟；≥3 保证每趟至多拆 1 次）
    if not os.environ.get('DISABLE_SPLIT'):
        for i, fi in enumerate(fls):
            if len(fi.route) != 1 or len(fi.box_ids) < 3:
                continue
            parts = split_into_ab(fls, fi, data)
            if not parts:
                continue
            pi = pt[fi.model] / np_[fi.model]
            sc_ = 0.01  # 拆分偏好低（完工优先下多为反效果，留给 RL 判断）
            c.append(('sp', fi.fid, -1, None, None))
            fa.append([0.0, 0.0, 0.0, pi / 7000.0, pi / 7000.0,
                      fi.total_mass / 80.0, parts[0].duration() / 3000.0, len(fi.box_ids) / 8.0,
                      fi.duration() / 3000.0, 0.0, sc_, 2.0,
                      (25.0 - parts[0].total_mass) / 25.0, (0.058 - parts[0].total_vol) / 0.058,
                      max(0.0, (1.0 - 0.2) * 4.5 - parts[0].energy()) / 2.0, 0.0])
            sc.append(sc_)
            sidx.append(i)
            didx.append(i)
    if len(c) > K:
        ord_ = np.argsort(-np.array(sc))[:K]
        c = [c[o] for o in ord_]
        fa = [fa[o] for o in ord_]
        sc = [sc[o] for o in ord_]
        sidx = [sidx[o] for o in ord_]
        didx = [didx[o] for o in ord_]
    # pad 到 K+1（STOP 在 K，特征/评分/节点索引对齐）
    F = np.zeros((K + 1, FA_X), np.float32)
    S = np.zeros(K + 1, np.float32)
    SI = np.zeros(K + 1, np.int64)
    DI = np.zeros(K + 1, np.int64)
    n = min(len(fa), K)
    for i in range(n):
        F[i] = fa[i]
        S[i] = sc[i]
        SI[i] = sidx[i]
        DI[i] = didx[i]
    F[K] = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    S[K] = -10.0
    if os.environ.get('DISABLE_FA_X'):  # 消融：关闭动作约束余量/时限差增强（fa 12 维等效）
        F[:, 12:] = 0.0
    return c, F, S, SI, DI


def mig_edges_of(fls):
    """图增强：可行迁移对边（供 GAT 邻域聚合）。"""
    es = []
    N = len(fls)
    for i, fi in enumerate(fls):
        zz = set(route_s for route_s, _ in fi.route)
        for b in fi.box_ids:
            zb = zone_of(b)
            for j, fj in enumerate(fls):
                if j == i or not any(route_s == zb for route_s, _ in fj.route):
                    continue
                if b in fj.box_ids:
                    continue
                nb = data.boxes[b]
                if fj.total_mass + nb['mass'] > {'A': 25, 'B': 30, 'C': 80}[fj.model] + 1e-9:
                    continue
                if fj.total_vol + nb['vol'] > {'A': 0.058, 'B': 0.071, 'C': 0.25}[fj.model] + 1e-9:
                    continue
                if zb not in zz:
                    continue
                es.append((i, j))
    return es


class NoisyLinear(nn.Module):
    def __init__(self, in_f, out_f, std_init=0.5):
        super().__init__()
        self.in_f = in_f
        self.out_f = out_f
        self.mu_w = nn.Parameter(torch.zeros(out_f, in_f))
        self.mu_b = nn.Parameter(torch.zeros(out_f))
        self.sigma_w = nn.Parameter(torch.full((out_f, in_f), std_init / math.sqrt(in_f)))
        self.sigma_b = nn.Parameter(torch.full((out_f,), std_init / math.sqrt(in_f)))
        self.reset_noise()

    def _f(self, x):
        return torch.sign(x) * torch.sqrt(torch.abs(x))

    def reset_noise(self):
        dev = self.mu_w.device
        self.ei = self._f(torch.randn(self.in_f, device=dev))
        self.ej = self._f(torch.randn(self.out_f, device=dev))

    def forward(self, x):
        if self.training:
            self.reset_noise()
            w = self.mu_w + self.sigma_w * self.ej.unsqueeze(1) * self.ei.unsqueeze(0)
            b = self.mu_b + self.sigma_b * self.ej
        else:
            w, b = self.mu_w, self.mu_b
        return F.linear(x, w, b)


class GATLayer(nn.Module):
    """多头图注意力（手写，无 torch_geometric）：alpha_ij = softmax(LeakyReLU(a_l·Wh_i + a_r·Wh_j))。"""

    def __init__(self, fin, fout, heads=4):
        super().__init__()
        self.W = nn.Parameter(torch.randn(heads, fin, fout) * 0.1)
        self.al = nn.Parameter(torch.randn(heads, fout) * 0.1)
        self.ar = nn.Parameter(torch.randn(heads, fout) * 0.1)

    def forward(self, x, adj):
        B, N, _ = x.shape
        wx = torch.einsum('bnf,hfd->bhnd', x, self.W)  # (B,H,N,fout)
        el = torch.einsum('bhnd,hd->bhn', wx, self.al).unsqueeze(-1)  # (B,H,N,1)
        er = torch.einsum('bhnd,hd->bhn', wx, self.ar).unsqueeze(-2)  # (B,H,1,N)
        e = F.leaky_relu(el + er, 0.2)  # (B,H,N,N)
        e = e.masked_fill(adj.unsqueeze(1) < 0.5, -1e9)
        alpha = torch.softmax(e, dim=-1)
        h = torch.einsum('bhnn,bhnd->bhnd', alpha, wx)  # (B,H,N,fout)
        return h.mean(dim=1)  # 多头平均 (B,N,fout)


class GATNet(nn.Module):
    def __init__(self, seed=0):
        super().__init__()
        torch.manual_seed(seed)
        np.random.seed(seed)
        self.g1 = GATLayer(GF, GH)
        self.g2 = GATLayer(GH, GH)
        self.senc = nn.Sequential(nn.Linear(S_DIM_X, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU())
        self.aenc = nn.Sequential(nn.Linear(FA_X, 64), nn.ReLU())
        # 边级动作表征：g(e_src, e_dst, e_dst-e_src, fa) → 64
        self.edge = nn.Sequential(nn.Linear(GH * 3 + 64, 64), nn.ReLU())
        self.v = nn.Sequential(nn.Linear(GH * 2 + 5, 128), nn.ReLU(), nn.Linear(128, 1))  # 中心化 V：readout→标量
        self.adv = NoisyLinear(128 + 64 + 64, 1)  # 局部 A：senc ⊕ edge ⊕ aenc

    def embed(self, x, adj):
        h1 = F.relu(self.g1(x, adj))
        h2 = F.relu(self.g2(h1, adj))
        return h2  # (B,N,GH)

    def readout(self, x, adj, pv):
        emb = self.embed(x, adj)
        valid = (x.sum(dim=-1, keepdim=True) > 0).float()  # (B,N,1) pad 掩码
        r = torch.cat([(emb * valid).sum(dim=1) / valid.sum(dim=1).clamp(min=1e-3),
                       ((emb * valid) + (1 - valid) * (-1e9)).max(dim=1)[0],
                       pv, pv.max(dim=-1, keepdim=True).values, pv.mean(dim=-1, keepdim=True)], dim=-1)
        return self.v(r), emb  # (B,1), (B,N,GH)

    def q(self, s, x, adj, pv, fa, sidx, didx):
        hs = self.senc(s)  # (B,128)
        vg, emb = self.readout(x, adj, pv)  # (B,1), (B,N,GH)
        e1 = emb.gather(1, sidx.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, GH))[:, 0, :]  # (B,GH)
        e2 = emb.gather(1, didx.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, GH))[:, 0, :]
        aemb = self.aenc(fa)  # (B,64)
        eg = self.edge(torch.cat([e1, e2, e2 - e1, aemb], dim=-1))  # (B,64) 边表征
        adv = self.adv(torch.cat([hs, eg, aemb], dim=-1)).squeeze(-1)  # (B,)
        return vg.squeeze(-1) + adv  # 中心化 V + 局部 A


class PER:
    def __init__(self, cap=30000, alpha=0.6, beta0=0.4):
        self.cap = cap
        self.alpha = alpha
        self.beta = beta0
        self.buf = []
        self.pri = []

    def push(self, e, p=1.0):
        self.buf.append(e)
        self.pri.append(p)
        if len(self.buf) > self.cap:
            self.buf.pop(0)
            self.pri.pop(0)

    def sample(self, n):
        p = np.array(self.pri, np.float32) ** self.alpha
        p = p / p.sum()
        idx = np.random.choice(len(self.buf), n, replace=False, p=p)
        N = len(self.buf)
        w = (N * p[idx]) ** (-self.beta)
        w = w / w.max()
        return [self.buf[i] for i in idx], w, idx

    def update(self, idx, td):
        for i, d in zip(idx, td):
            self.pri[i] = max(float(abs(d)) + 1e-6, 1e-3)


class ClassifiedReplay:
    def __init__(self, cap=60000, alpha=0.6, beta0=0.4):
        self.b = {'imp': PER(cap // 2, alpha, beta0),
                  'term': PER(cap // 4, alpha, beta0),
                  'rest': PER(cap // 4, alpha, beta0)}

    def push(self, e, p=1.0):
        kind = 'term' if e[10] > 0.5 else ('imp' if e[5] > 1e-3 else 'rest')  # e[10]=done, e[5]=r
        self.b[kind].push(e, p)

    def total(self):
        return sum(len(b.buf) for b in self.b.values())

    def sample(self, n):
        q_imp = int(n * IMP_R)
        q_term = int(n * 0.30)
        quota = {'imp': q_imp, 'term': q_term, 'rest': n - q_imp - q_term}
        out, w, refs = [], [], []
        for k in ['imp', 'term', 'rest']:
            bk = self.b[k]
            if not bk.buf:
                continue
            q = min(quota[k], len(bk.buf))
            batch, ww, idx = bk.sample(q)
            out += batch
            w += list(ww)
            refs += [(k, i) for i in idx]
        if len(out) < n:
            bk = self.b['rest']
            q = n - len(out)
            if len(bk.buf) >= q:
                batch, ww, idx = bk.sample(q)
                out += batch
                w += list(ww)
                refs += [('rest', i) for i in idx]
        return out, np.array(w, np.float32), refs

    def update(self, refs, td):
        for (k, i), d in zip(refs, td):
            self.b[k].update([i], [d])


def state_x(fls, m):
    """增强状态：170(23趟标准) + 电池周转4 + 约束余量3 + 超额趟特征(29架全编码, 6趟×7)。
    修复 v58-v61 缺口：29 架时 state_vec 仅编码 23 趟，第 24-29 趟状态丢失。"""
    v = list(state_vec(fls, m))
    # 电池周转特征（4）：各池充电小时近似（隐性容量，dispatch 硬约束的软感知）
    T_FULL = {'A': 1800.0, 'B': 2400.0, 'C': 3000.0}
    E_USE = {'A': 4.5, 'B': 4.0, 'C': 8.0}
    ch = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    for f in fls:
        ch[f.model] += T_FULL[f.model] * (1.0 - min(1.0, f.energy() / E_USE[f.model])) / 3600.0
    v += [ch['A'] / 8.0, ch['B'] / 8.0, ch['C'] / 10.0, (ch['A'] + ch['B'] + ch['C']) / 26.0]
    # 约束余量（3）：全局 min 质量/体积/能量余量（感知约束紧度）
    Q = {'A': 25.0, 'B': 30.0, 'C': 80.0}
    V = {'A': 0.058, 'B': 0.071, 'C': 0.25}
    qm, vm, em = 1.0, 1.0, 1.0
    for f in fls:
        qm = min(qm, (Q[f.model] - f.total_mass) / Q[f.model])
        vm = min(vm, (V[f.model] - f.total_vol) / V[f.model])
        em = min(em, (1.0 - 0.2) * E_USE[f.model] - f.energy())
    v += [qm, vm, min(1.0, em / 2.0)]
    # 超额趟（29 架时第 24-29 趟特征）
    srt = sorted(fls, key=lambda f: f.fid)
    for i in range(23, 29):
        if i < len(srt):
            f = srt[i]
            mn = min(data.boxes[b]['deadline_exp'] for b in f.box_ids)
            sid = f.route[0][0] if f.route else 'S000'
            v += [f.duration() / 3000.0, f.energy() / 7.0, f.total_mass / 80.0,
                  len(f.box_ids) / 8.0, mn / 14400.0,
                  0.0 if f.model == 'A' else (0.5 if f.model == 'B' else 1.0),
                  float(sum(ord(c) for c in sid) % 16) / 15.0]
        else:
            v += [0.0] * 7
    # 额外趟统计（拆分后 >29 趟折叠：趟数 + 总时长）
    extra = srt[29:]
    v += [len(extra) / 10.0, sum(f.duration() for f in extra) / 9000.0]
    if os.environ.get('DISABLE_STATE_X'):  # 消融：关闭增强段（电池/余量/超趟/额外趟）→ 等价 170 维
        v = v[:170] + [0.0] * (S_DIM_X - 170)
    v = np.asarray(v, np.float32)
    if len(v) < S_DIM_X:
        v = np.concatenate([v, np.zeros(S_DIM_X - len(v), np.float32)])
    return v[:S_DIM_X]


def exp_graph(fls, m=None):
    if m is None:
        m, _, _, _ = eval_full(data, fls)
    x, adj, pv = build_graph(fls, m, mig_edges_of(fls))
    return state_x(fls, m), x, adj, pv


def rollout_step(qnet, fls, eps, rp, ring, cnt):
    """单步：候选+图+Q → 动作 → 执行/经验。返回 (s, x, adj, pv, a, r, done, s2g)。"""
    c, feats, scores, sidx, didx = build_candidates_x(fls)
    mk = make_mask(c)
    s, x, adj, pv = exp_graph(fls)
    st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
    xt = x.to(DEV).unsqueeze(0)
    at = adj.to(DEV).unsqueeze(0)
    pvt = pv.to(DEV).unsqueeze(0)
    fmat = torch.from_numpy(feats).float().to(DEV)
    si = torch.from_numpy(sidx).to(DEV)  # (A_DIM,)
    di = torch.from_numpy(didx).to(DEV)
    mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
    with torch.no_grad():
        qv = qnet.q(st.expand(A_DIM, -1), xt.expand(A_DIM, -1, -1),
                    at.expand(A_DIM, -1, -1), pvt.expand(A_DIM, -1),
                    fmat, si, di).masked_fill(mkv < 0.5, -1e9)
    idx_ok = np.argwhere(mk > 0.5).ravel()
    if np.random.rand() < eps and len(idx_ok):
        if np.random.rand() < 0.7:
            a = int(idx_ok[int(np.argmax(scores[idx_ok]))])
        else:
            a = int(np.random.choice(idx_ok))
    else:
        a = int(qv.argmax().item())
    if a == K:
        r = terminal_r(fls)
        done = True
        s2g = (s, x, adj, pv)
        nf = None
    elif a >= len(c) or mk[a] < 0.5:
        r = -0.2
        done = False
        s2g = (s, x, adj, pv)
        nf = None
    else:
        imp = eval_improve_scene_x(fls, c[a])
        if imp is None:
            r = -0.2
            done = False
            s2g = (s, x, adj, pv)
            nf = None
        else:
            r, nf = imp
            done = False
            s2g = exp_graph(nf)
    ring.append((s, x, adj, pv, a, r, done, mk, feats[a], sidx[a], didx[a]))
    if len(ring) > NSTEP:
        s0, x0, a0, pv0, a0i, _, _, mk0, fa0, si0, di0 = ring[0]
        rn = sum((0.99 ** i) * ring[i][6] for i in range(NSTEP))
        dn = ring[NSTEP - 1][5]
        s2f, x2f, a2f, pv2f = s2g
        rp.push((s0, x0, a0, pv0, a0i, rn, s2f, x2f, a2f, pv2f, 1.0 if dn else 0.0, mk0, fa0, si0, di0))
        ring.popleft()
    return nf, done, s2g


def flush_ring(ring, s2g, rp):
    while ring:
        s0, x0, a0, pv0, a0i, _, _, mk0, fa0, si0, di0 = ring[0]
        rn = sum((0.99 ** i) * ring[i][6] for i in range(len(ring)))
        s2f, x2f, a2f, pv2f = s2g
        rp.push((s0, x0, a0, pv0, a0i, rn, s2f, x2f, a2f, pv2f, 1.0, mk0, fa0, si0, di0))
        ring.popleft()


def train_batch(q, qt, opt, rp):
    if rp.total() < 256:
        return
    batch, w, refs = rp.sample(128)
    if len(batch) < 32:
        return
    S = torch.tensor(np.array([e[0] for e in batch]), dtype=torch.float32).to(DEV)
    Xg = torch.stack([e[1].to(DEV) for e in batch])
    Ag = torch.stack([e[2].to(DEV) for e in batch])
    Pv = torch.stack([e[3].to(DEV) for e in batch])
    R = torch.tensor([e[5] for e in batch], dtype=torch.float32).to(DEV)
    SP = torch.tensor(np.array([e[6] for e in batch]), dtype=torch.float32).to(DEV)
    Xp = torch.stack([e[7].to(DEV) for e in batch])
    Ap = torch.stack([e[8].to(DEV) for e in batch])
    Pvp = torch.stack([e[9].to(DEV) for e in batch])
    D = torch.tensor([e[10] for e in batch], dtype=torch.float32).to(DEV)
    FA = torch.tensor(np.array([e[12] for e in batch]), dtype=torch.float32).to(DEV)  # e[12]=fa
    SI = torch.tensor([e[13] for e in batch], dtype=torch.int64).to(DEV)
    DI = torch.tensor([e[14] for e in batch], dtype=torch.int64).to(DEV)
    fnext = torch.zeros((len(batch), FA_X), dtype=torch.float32).to(DEV)
    fnext[:, 2] = 1.0  # STOP 特征
    with torch.no_grad():
        qt.eval()
        qs2 = qt.q(SP, Xp, Ap, Pvp, fnext, torch.zeros(len(batch), dtype=torch.int64).to(DEV),
                   torch.zeros(len(batch), dtype=torch.int64).to(DEV))
        y = R + 0.99 * qs2 * (1 - D)
    q.train()
    qcur = q.q(S, Xg, Ag, Pv, FA, SI, DI)
    td = qcur - y
    ww = torch.tensor(w[:len(batch)], dtype=torch.float32).to(DEV)
    loss = (ww * td ** 2).mean()
    opt.zero_grad()
    loss.backward()
    opt.step()
    rp.update(refs, td.detach().cpu().numpy())


def train_seed(seed, n_ep=150, rp=None):
    torch.manual_seed(seed)
    np.random.seed(seed)
    q = GATNet(seed=seed).to(DEV)
    qt = GATNet(seed=seed + 999).to(DEV)
    qt.load_state_dict(q.state_dict())
    opt = optim.Adam(q.parameters(), lr=5e-4)
    if rp is None:
        rp = ClassifiedReplay()
    init = clone(load_init())
    fls = clone(init)
    # 预填：启发式改进 + STOP（分类池：稀疏正信号）
    for _ in range(100):
        c, feats, scores, sidx, didx = build_candidates_x(fls)
        mk = make_mask(c)
        s, x, adj, pv = exp_graph(fls)
        if not c:
            rp.push((s, x, adj, pv, K, terminal_r(fls), s, x, adj, pv, 1.0, mk, feats[K], sidx[K], didx[K]), p=5.0)
            break
        best_imp = None
        bi = -1
        for i in range(min(len(c), K)):
            imp = eval_improve_scene_x(fls, c[i])
            if imp is not None and (best_imp is None or imp[0] > best_imp[0]):
                best_imp = imp
                bi = i
        if best_imp is None:
            rp.push((s, x, adj, pv, K, terminal_r(fls), s, x, adj, pv, 1.0, mk, feats[K], sidx[K], didx[K]), p=5.0)
            continue
        r, nf = best_imp
        s2, x2, a2, pv2 = exp_graph(nf)
        rp.push((s, x, adj, pv, bi, r, s2, x2, a2, pv2, 0.0, mk, feats[bi], sidx[bi], didx[bi]), p=2.0)
        fls = nf
    print('[seed%d] 预填 %d 条 (imp/term/rest=%d/%d/%d)' % (
        seed, rp.total(), len(rp.b['imp'].buf), len(rp.b['term'].buf), len(rp.b['rest'].buf)), flush=True)
    eps = EPS0
    best_fls = None
    best_key = None
    t0 = time.time()
    for ep in range(n_ep):
        fls = clone(init)
        q.train()
        ring = deque()
        s2g = None
        for t in range(10):
            nf, done, s2g = rollout_step(q, fls, eps, rp, ring, t)
            if nf is not None:
                fls = nf
            if done:
                break
        flush_ring(ring, s2g, rp)
        train_batch(q, qt, opt, rp)
        eps = max(EPS_END, eps - (EPS0 - EPS_END) / n_ep)
        for p_, pt_ in zip(q.parameters(), qt.parameters()):
            pt_.data.mul_(1 - 0.005).add_(0.005 * p_.data)
        m, s2, v, nc = eval_full(data, fls)
        if m and v == 0 and nc == 0:
            key = (m['makespan'], m['energy'])
            if best_key is None or key < best_key:
                best_key = key
                best_fls = clone(fls)
                print('  [seed%d] ep%d best: mk=%.1f en=%.2f (%.0fs)' % (
                    seed, ep + 1, m['makespan'], m['energy'], time.time() - t0), flush=True)
    q.eval()
    gkeys = []
    saved_g = [False]
    for _ in range(10):
        fls = clone(init)
        for t in range(10):
            c, feats, scores, sidx, didx = build_candidates_x(fls)
            if not c:
                break
            mk = make_mask(c)
            s, x, adj, pv = exp_graph(fls)
            st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
            xt = x.to(DEV).unsqueeze(0)
            at = adj.to(DEV).unsqueeze(0)
            pvt = pv.to(DEV).unsqueeze(0)
            fmat = torch.from_numpy(feats).float().to(DEV)
            si = torch.from_numpy(sidx).to(DEV)
            di = torch.from_numpy(didx).to(DEV)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qv = q.q(st.expand(A_DIM, -1), xt.expand(A_DIM, -1, -1),
                         at.expand(A_DIM, -1, -1), pvt.expand(A_DIM, -1),
                         fmat, si, di).masked_fill(mkv < 0.5, -1e9)
            a = int(qv.argmax().item())
            if a == K:
                break
            if a < len(c):
                imp = eval_improve_scene_x(fls, c[a])
                if imp is not None:
                    fls = imp[1]
        # 启发式收尾（v46 优先序标准）
        while True:
            c2, _, _, _, _ = build_candidates_x(fls)
            if not c2:
                break
            m0c, _, _, _ = eval_full(data, fls)
            best_ls = None
            for i in range(min(len(c2), K)):
                imp2 = eval_improve_scene_x(fls, c2[i])
                if imp2 is None:
                    continue
                _, nf2 = imp2
                m2c, _, v2c, nc2c = eval_full(data, nf2)
                if m2c is None or v2c > 0 or nc2c > 0 or (not m2c['hard_ok']):
                    continue
                ok = (m2c['makespan'] < m0c['makespan'] - 1e-6) or \
                     (abs(m2c['makespan'] - m0c['makespan']) < 1e-6 and
                      m2c['energy'] < m0c['energy'] - 0.02)
                if ok and (best_ls is None or
                           (m2c['makespan'], m2c['energy']) < (best_ls[0]['makespan'], best_ls[0]['energy'])):
                    best_ls = (m2c, nf2)
            if best_ls is None:
                break
            fls = best_ls[1]
        m, s2, v, nc = eval_full(data, fls)
        if m and v == 0 and nc == 0:
            gkeys.append((m['makespan'], m['energy']))
            if not saved_g[0]:
                json.dump({'best': {'makespan': m['makespan'], 'energy': m['energy']},
                           'solution': [{'fid': f.fid, 'model': f.model,
                                         'route': [(s2, list(bs)) for s2, bs in f.route]} for f in fls]},
                          open(os.path.join(OUTD, 'p2v61_gat%s_greedy.json' % TAG), 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
                saved_g[0] = True
    if best_fls is not None:
        json.dump({'best': {'makespan': best_key[0], 'energy': best_key[1]},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in best_fls]},
                  open(os.path.join(OUTD, 'p2v61_gat%s_seed%d.json' % (TAG, seed)), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    return best_key, gkeys


def main():
    n_ep = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    seeds = [int(x) for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else ['0', '1', '2'])]
    t0 = time.time()
    rp = None
    all_best = []
    all_greedy = []
    for rnd in range(ROUNDS):
        print('=== 持续进化轮 %d/%d ===' % (rnd + 1, ROUNDS), flush=True)
        for sd in seeds:
            bk, gk = train_seed(sd, n_ep=n_ep, rp=rp)  # rp 跨轮保留（持续学习）
            print('[seed%d] train_best=%s greedy_10=%s' % (sd, bk, gk), flush=True)
            if bk:
                all_best.append((rnd, sd, bk))
            all_greedy.extend((sd, x) for x in gk)
        # 自模仿：轮末 greedy 解作为下一轮起点（更新 START 文件）
        gp = os.path.join(OUTD, 'p2v61_gat%s_greedy.json' % TAG)
        if os.path.exists(gp) and rnd + 1 < ROUNDS:
            global START
            START = 'p2v61_gat%s_greedy.json' % TAG
            print('  下一轮起点 = 本轮 greedy 解 (自模仿)', flush=True)
    print('--- GAT-DRL 汇总 (rounds=%d) ---' % ROUNDS, flush=True)
    for rnd, sd, k in all_best:
        print('  r%d seed%d best: mk=%.1f en=%.2f' % (rnd, sd, k[0], k[1]), flush=True)
    if all_greedy:
        mks = [k[0] for _, k in all_greedy]
        ens = [k[1] for _, k in all_greedy]
        print('  greedy: mk=%.1f±%.1f, en=%.2f±%.3f (n=%d)' % (
            np.mean(mks), np.std(mks), np.mean(ens), np.std(ens), len(mks)), flush=True)
    json.dump({'summary': 'GAT-DRL(边表征+中心V/局部A+跨区迁移+自模仿r%d) %dseed×%dep' % (ROUNDS, len(seeds), n_ep),
               'all_seed_best': {str(s): list(k) for _, s, k in all_best},
               'greedy_mean': [float(np.mean([k[0] for _, k in all_greedy])),
                               float(np.mean([k[1] for _, k in all_greedy]))] if all_greedy else None,
               'greedy_std': [float(np.std([k[0] for _, k in all_greedy])),
                              float(np.std([k[1] for _, k in all_greedy]))] if all_greedy else None},
              open(os.path.join(OUTD, 'p2v61_gat%s.json' % TAG), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v61_gat%s.json 用时 %.0fs' % (TAG, time.time() - t0), flush=True)


if __name__ == '__main__':
    main()