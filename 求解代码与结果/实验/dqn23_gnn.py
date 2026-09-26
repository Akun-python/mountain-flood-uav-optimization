# -*- coding: utf-8 -*-
"""dqn23_gnn.py —— 图结构 DRL + 经验池 + 中心化 + 持续进化（消融实验 v60）。
机制设计：
1. **图结构状态编码**：趟图 G=(节点=趟, 边=同池机型/同区)，2 层 GCN（手写，无 torch_geometric 依赖）
   节点特征：机型/质量/时长/能耗/箱数/池负载/区编码；GNN readout = [mean, max] 节点嵌入
2. **中心化（CENTRAL）**：readout 显式拼接全局池统计（各池 T/台 + max/mean）——中心化全局感知
3. **经验池**：分类三桶（imp/term/rest 配额）+ PER + n-step + Double（沿用 v56），经验存图数据(X,A,pv)
4. **持续进化（EVOLVE）**：训练→greedy 解→更新起点→再训练（shell 层循环实现）
消融：A=无图基线(rainbow) B=GNN C=GNN+中心化 D=持续进化(GNN+C)
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
                            eval_improve_scene, build_candidates_f, make_mask, terminal_r, clone)
from p2_solve import Flight

torch.manual_seed(0)
np.random.seed(0)
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('device', DEV, flush=True)
NSTEP = int(os.environ.get('NSTEP', '3'))
IMP_R = float(os.environ.get('IMP_RATIO', '0.4'))
CENTRAL = int(os.environ.get('CENTRAL', '1'))  # 1=中心化池统计 readout
TAG = os.environ.get('TAG', '')
START = os.environ.get('START_JSON', 'p2v58_rainbow_greedy.json')
EPS0, EPS_END = 0.5, 0.05
GF = 12  # 图节点特征维
GH = 32  # GCN 隐层


def load_init():
    d0 = json.load(open(os.path.join(OUTD, START), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d0['solution']]


def build_graph(fls, m=None):
    """趟图：节点特征 (N,12) + 邻接 (N,N) 同池/同区 + 池统计向量 pv。"""
    N = len(fls)
    X = np.zeros((N, GF), np.float32)
    pt = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    np_ = {'A': 4, 'B': 2, 'C': 2}
    E_USE = {'A': 4.5, 'B': 4.0, 'C': 8.0}
    for f in fls:
        pt[f.model] += f.duration()
    mk = m['makespan'] if m is not None else 7200.0
    gm_i = {'A': 0, 'B': 1, 'C': 2}
    for i, f in enumerate(fls):
        g = gm_i[f.model]
        X[i, g] = 1.0
        X[i, 3] = f.total_mass / 80.0
        X[i, 4] = f.duration() / 3000.0
        X[i, 5] = f.energy() / E_USE[f.model]
        X[i, 6] = len(f.box_ids) / 8.0
        X[i, 7] = pt[f.model] / np_[f.model] / 7000.0
        X[i, 8] = 1.0 if f.model == 'A' else 0.0
        X[i, 9] = float(sum(ord(ch) for ch in f.route[0][0]) % 16) / 15.0  # 区编码
        X[i, 10] = mk / 8000.0
        X[i, 11] = f.duration() / 3000.0
    A = np.zeros((N, N), np.uint8)
    for i in range(N):
        A[i, i] = 1
        for j in range(i + 1, N):
            same_pool = fls[i].model == fls[j].model
            same_zone = fls[i].route[0][0] == fls[j].route[0][0]
            if same_pool or same_zone:
                A[i, j] = A[j, i] = 1
    d = A.sum(axis=1).astype(np.float32)
    d = np.where(d > 0, 1.0 / np.sqrt(d), 0.0)
    An = (A.astype(np.float32) * d[:, None] * d[None, :])
    pv = np.array([pt[g] / np_[g] / 7000.0 for g in 'ABC'], np.float32)
    return (torch.from_numpy(X).float(), torch.from_numpy(An).float(),
            torch.from_numpy(pv).float())


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


class GCNLayer(nn.Module):
    def __init__(self, fin, fout):
        super().__init__()
        self.w = nn.Parameter(torch.randn(fin, fout) * 0.1)
        self.b = nn.Parameter(torch.zeros(fout))

    def forward(self, x, a):
        return a @ x @ self.w + self.b


class GNNNet(nn.Module):
    def __init__(self, seed=0):
        super().__init__()
        torch.manual_seed(seed)
        np.random.seed(seed)
        self.g1 = GCNLayer(GF, GH)
        self.g2 = GCNLayer(GH, GH)
        self.readout = nn.Sequential(nn.Linear(GH * 2 + (5 if CENTRAL else 0), 128), nn.ReLU())
        self.senc = nn.Sequential(nn.Linear(S_DIM, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU())
        self.aenc = nn.Sequential(nn.Linear(FEAT_DIM, 64), nn.ReLU())
        self.a_head = NoisyLinear(128 + 128 + 64, 1)
        self.v = nn.Linear(128 + 128, 1)

    def enc(self, s, x, a, pv):
        h1 = F.relu(self.g1(x, a))
        h2 = F.relu(self.g2(h1, a))
        r = torch.cat([h2.mean(dim=1), h2.max(dim=1)[0]], dim=-1)  # 节点维 readout (B,2GH)
        if CENTRAL:
            r = torch.cat([r, pv, pv.max(dim=-1, keepdim=True).values,
                           pv.mean(dim=-1, keepdim=True)], dim=-1)  # 中心化全局池统计
        return self.readout(r)

    def q(self, s, x, a, pv, fa):
        hs = self.senc(s)
        hg = self.enc(s, x, a, pv)
        adv = self.a_head(torch.cat([hs, hg, self.aenc(fa)], dim=-1)).squeeze(-1)
        return self.v(torch.cat([hs, hg], dim=-1)).squeeze(-1) + adv


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


def exp_graph(fls):
    """经验用图数据：s(170) + X/A/pv（一次 eval 复用）。"""
    m, _, _, _ = eval_full(data, fls)
    x, a, pv = build_graph(fls, m)
    return state_vec(fls, m), x, a, pv


def train_seed(seed, n_ep=150):
    torch.manual_seed(seed)
    np.random.seed(seed)
    q = GNNNet(seed=seed).to(DEV)
    qt = GNNNet(seed=seed + 999).to(DEV)
    qt.load_state_dict(q.state_dict())
    opt = optim.Adam(q.parameters(), lr=5e-4)
    rp = ClassifiedReplay()
    init = clone(load_init())
    fls = clone(init)
    for _ in range(100):  # 预填（启发式改进 + STOP）
        c, feats, scores = build_candidates_f(fls)
        mk = make_mask(c)
        s, x, a, pv = exp_graph(fls)
        if not c:
            rp.push((s, x, a, pv, K, terminal_r(fls), s, x, a, pv, 1.0, mk, feats[K]), p=5.0)
            break
        best_imp = None
        bi = -1
        for i in range(min(len(c), K)):
            imp = eval_improve_scene(fls, c[i])
            if imp is not None and (best_imp is None or imp[0] > best_imp[0]):
                best_imp = imp
                bi = i
        if best_imp is None:
            rp.push((s, x, a, pv, K, terminal_r(fls), s, x, a, pv, 1.0, mk, feats[K]), p=5.0)
            continue
        r, nf = best_imp
        s2, x2, a2, pv2 = exp_graph(nf)
        rp.push((s, x, a, pv, bi, r, s2, x2, a2, pv2, 0.0, mk, feats[bi]), p=2.0)
        fls = nf
    print('[seed%d] 预填 %d 条' % (seed, rp.total()), flush=True)
    eps = EPS0
    best_fls = None
    best_key = None
    t0 = time.time()
    for ep in range(n_ep):
        fls = clone(init)
        q.train()
        ring = deque()
        for t in range(10):
            c, feats, scores = build_candidates_f(fls)
            mk = make_mask(c)
            s, x, adj, pv = exp_graph(fls)
            st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
            xt = x.to(DEV).unsqueeze(0)
            at = adj.to(DEV).unsqueeze(0)
            pvt = pv.to(DEV).unsqueeze(0)
            fmat = torch.from_numpy(feats).float().to(DEV)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qt.eval()
                qv = qt.q(st.expand(A_DIM, -1), xt.expand(A_DIM, -1, -1),
                          at.expand(A_DIM, -1, -1), pvt.expand(A_DIM, -1), fmat)
            qv = qv.masked_fill(mkv < 0.5, -1e9)
            idx_ok = np.argwhere(mk > 0.5).ravel()
            if np.random.rand() < eps and len(idx_ok):
                if np.random.rand() < 0.7:
                    a_i = int(np.argmax(scores[idx_ok]))
                    a = int(idx_ok[a_i])
                else:
                    a = int(np.random.choice(idx_ok))
            else:
                a = int(qv.argmax().item())
            if a == K:
                r = terminal_r(fls)
                done = True
                s2g = (s, x, adj, pv)
            elif a >= len(c) or mk[a] < 0.5:
                r = -0.2
                done = False
                s2g = (s, x, adj, pv)
            else:
                imp = eval_improve_scene(fls, c[a])
                if imp is None:
                    r = -0.2
                    done = False
                    s2g = (s, x, adj, pv)
                else:
                    r, nf = imp
                    fls = nf
                    done = False
                    s2g = exp_graph(fls)
            ring.append((s, x, adj, pv, a, r, done, mk, feats[a]))
            if len(ring) > NSTEP:
                s0, x0, adj0, pv0, a0, _, _, mk0, fa0 = ring[0]
                rn = sum((0.99 ** i) * ring[i][5] for i in range(NSTEP))
                dn = ring[NSTEP - 1][6]
                s2f, x2f, a2f, pv2f = s2g
                rp.push((s0, x0, adj0, pv0, a0, rn, s2f, x2f, a2f, pv2f, 1.0 if dn else 0.0, mk0, fa0))
                ring.popleft()
            if done:
                break
        while ring:
            s0, x0, adj0, pv0, a0, _, _, mk0, fa0 = ring[0]
            rn = sum((0.99 ** i) * ring[i][5] for i in range(len(ring)))
            s2f, x2f, a2f, pv2f = s2g
            rp.push((s0, x0, adj0, pv0, a0, rn, s2f, x2f, a2f, pv2f, 1.0, mk0, fa0))
            ring.popleft()
        if rp.total() >= 256:
            batch, w, refs = rp.sample(128)
            if len(batch) >= 32:
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
                FA = torch.tensor(np.array([e[12] for e in batch]), dtype=torch.float32).to(DEV)
                fnext = torch.zeros((len(batch), FEAT_DIM), dtype=torch.float32).to(DEV)
                fnext[:, 2] = 1.0
                with torch.no_grad():
                    qt.eval()
                    qs2 = qt.q(SP, Xp, Ap, Pvp, fnext)
                    y = R + 0.99 * qs2 * (1 - D)
                q.train()
                qcur = q.q(S, Xg, Ag, Pv, FA)
                td = qcur - y
                ww = torch.tensor(w[:len(batch)], dtype=torch.float32).to(DEV)
                loss = (ww * td ** 2).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()
                rp.update(refs, td.detach().cpu().numpy())
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
            c, feats, scores = build_candidates_f(fls)
            if not c:
                break
            mk = make_mask(c)
            s, x, adj, pv = exp_graph(fls)
            st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
            xt = x.to(DEV).unsqueeze(0)
            at = adj.to(DEV).unsqueeze(0)
            pvt = pv.to(DEV).unsqueeze(0)
            fmat = torch.from_numpy(feats).float().to(DEV)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qv = q.q(st.expand(A_DIM, -1), xt.expand(A_DIM, -1, -1),
                         at.expand(A_DIM, -1, -1), pvt.expand(A_DIM, -1), fmat).masked_fill(mkv < 0.5, -1e9)
            a = int(qv.argmax().item())
            if a == K:
                break
            if a < len(c):
                imp = eval_improve_scene(fls, c[a])
                if imp is not None:
                    fls = imp[1]
        # 启发式收尾（v46 优先序标准）
        while True:
            c2, _, _ = build_candidates_f(fls)
            if not c2:
                break
            m0c, _, _, _ = eval_full(data, fls)
            best_ls = None
            for i in range(min(len(c2), K)):
                imp2 = eval_improve_scene(fls, c2[i])
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
                          open(os.path.join(OUTD, 'p2v60_gnn%s_greedy.json' % TAG), 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
                saved_g[0] = True
    if best_fls is not None:
        json.dump({'best': {'makespan': best_key[0], 'energy': best_key[1]},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in best_fls]},
                  open(os.path.join(OUTD, 'p2v60_gnn%s_seed%d.json' % (TAG, seed)), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    return best_key, gkeys


def main():
    n_ep = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    seeds = [int(x) for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else ['0', '1', '2'])]
    all_best = []
    all_greedy = []
    t0 = time.time()
    for sd in seeds:
        bk, gk = train_seed(sd, n_ep=n_ep)
        print('[seed%d] train_best=%s greedy_10=%s' % (sd, bk, gk), flush=True)
        if bk:
            all_best.append((sd, bk))
        all_greedy.extend((sd, x) for x in gk)
    print('--- GNN-DRL(CENTRAL=%d) 汇总 ---' % CENTRAL, flush=True)
    for sd, k in all_best:
        print('  seed%d best: mk=%.1f en=%.2f' % (sd, k[0], k[1]), flush=True)
    if all_greedy:
        mks = [k[0] for _, k in all_greedy]
        ens = [k[1] for _, k in all_greedy]
        print('  greedy: mk=%.1f±%.1f, en=%.2f±%.3f (n=%d)' % (
            np.mean(mks), np.std(mks), np.mean(ens), np.std(ens), len(mks)), flush=True)
    json.dump({'summary': 'GNN-DRL(CENTRAL=%d,nstep%d,imp%d%%) 3seed×%dep' % (CENTRAL, NSTEP, int(IMP_R * 100), n_ep),
               'all_seed_best': {str(s): list(k) for s, k in all_best},
               'greedy_mean': [float(np.mean([k[0] for _, k in all_greedy])),
                               float(np.mean([k[1] for _, k in all_greedy]))] if all_greedy else None,
               'greedy_std': [float(np.std([k[0] for _, k in all_greedy])),
                              float(np.std([k[1] for _, k in all_greedy]))] if all_greedy else None},
              open(os.path.join(OUTD, 'p2v60_gnn%s.json' % TAG), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v60_gnn%s.json 用时 %.0fs' % (TAG, time.time() - t0), flush=True)


if __name__ == '__main__':
    main()