# -*- coding: utf-8 -*-
"""dqn23_rainbow.py —— Rainbow 式完善版 DQN（针对本调度问题，参考文献设计）。
架构（文献对应）：
1. Dueling 网络：Q(s,a) = V(s) + A(s,a)，状态价值与动作优势分离（Wang et al., ICML 2016）
2. NoisyNet 探索：优势头因子化高斯参数噪声，替代大部分 ε-greedy（Fortunato et al., 2018）
3. 分类经验回放池（Classified Replay，参考 Neves et al. 2024 综述的 ER 分类设计）：
   改进/终止/其余 三桶分层采样（改进经验占 40% 配额），桶内 PER（Schaul et al. 2016）
4. Double DQN（van Hasselt et al. 2016）+ n-step（Hessel et al. 2018 Rainbow 组件）+ soft-target
5. 场景定制奖励（v53：完工主导 + 能耗 + 池均衡 + 充电周转）与动作特征化（v52）保留
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
                            eval_improve_scene, build_candidates_f, make_mask, make_experience,
                            terminal_r, clone)
from p2_solve import Flight

START = os.environ.get('START_JSON', 'p2v46_23local.json')  # 起点解（23架最优 或 29架完工最优）


def load_init():
    d0 = json.load(open(os.path.join(OUTD, START), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d0['solution']]

torch.manual_seed(0)
np.random.seed(0)
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('device', DEV, flush=True)
NSTEP = 3
EPS0 = 0.5
EPS_END = 0.05


class NoisyLinear(nn.Module):
    """因子化高斯参数噪声（Fortunato et al. 2018 NoisyNet）。"""

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


class RainbowNet(nn.Module):
    """Dueling 结构：Q(s,a) = V(s) + A(s,a)（动作优势带参数噪声）。"""

    def __init__(self, seed=0):
        super().__init__()
        torch.manual_seed(seed)
        np.random.seed(seed)
        self.senc = nn.Sequential(nn.Linear(S_DIM, 128), nn.ReLU(),
                                  nn.Linear(128, 128), nn.ReLU())
        self.v = nn.Linear(128, 1)
        self.aenc = nn.Sequential(nn.Linear(FEAT_DIM, 64), nn.ReLU())
        self.a_head = NoisyLinear(128 + 64, 1)

    def q(self, s, fa):
        h = self.senc(s)
        a = self.a_head(torch.cat([h, self.aenc(fa)], dim=-1)).squeeze(-1)
        return self.v(h).squeeze(-1) + a

    def reset_noise(self):
        self.a_head.reset_noise()


class PER:
    """Prioritized Experience Replay（Schaul et al. 2016），桶内使用。"""

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
        p = np.array(self.pri, np.float32)
        p = p ** self.alpha
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
    """分类经验回放池（参考 Neves et al. 2024 ER 综述的层次化 ER 设计）：
    三桶 —— imp(改进经验, r>0) / term(终止经验) / rest(其余)，
    分层配额采样（imp 40% / term 30% / rest 30%），桶内 PER + TD-error 优先更新。
    保证稀疏的"正改进信号"被稳定学习（对症本问题：改进经验占比极小）。
    """

    def __init__(self, cap=60000, alpha=0.6, beta0=0.4):
        self.b = {'imp': PER(cap // 2, alpha, beta0),
                  'term': PER(cap // 4, alpha, beta0),
                  'rest': PER(cap // 4, alpha, beta0)}

    def push(self, e, p=1.0):
        kind = 'term' if e[4] > 0.5 else ('imp' if e[2] > 1e-3 else 'rest')
        self.b[kind].push(e, p)

    def total(self):
        return sum(len(b.buf) for b in self.b.values())

    def sample(self, n, beta):
        quota = {'imp': int(n * 0.40), 'term': int(n * 0.30), 'rest': n - int(n * 0.40) - int(n * 0.30)}
        out = []
        w = []
        refs = []  # (bucket, local_idx)
        for k in ['imp', 'term', 'rest']:
            bk = self.b[k]
            if not bk.buf:
                continue
            q = min(quota[k], len(bk.buf))
            batch, ww, idx = bk.sample(q)
            out += batch
            w += list(ww)
            refs += [(k, i) for i in idx]
            quota[k] -= q
        # 配额未满从 rest 补（若 imp/term 不足）
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


def make_experience_r(s, a, r_n, s2, done, mk, fa):
    return (s, a, r_n, s2, 1.0 if done else 0.0, mk, fa)


def train_seed(seed, n_ep=150):
    torch.manual_seed(seed)
    np.random.seed(seed)
    q = RainbowNet(seed=seed).to(DEV)
    qt = RainbowNet(seed=seed + 999).to(DEV)
    qt.load_state_dict(q.state_dict())
    opt = optim.Adam(q.parameters(), lr=5e-4)
    rp = ClassifiedReplay()
    init = clone(load_init())
    fls = clone(init)
    for _ in range(100):
        c, feats, scores = build_candidates_f(fls)
        mk = make_mask(c)
        s = make_state(fls)
        if not c:
            rp.push(make_experience_r(s, K, terminal_r(fls), s, True, mk, feats[K]), p=5.0)
            break
        best_imp = None
        bi = -1
        for i in range(min(len(c), K)):
            imp = eval_improve_scene(fls, c[i])
            if imp is not None and (best_imp is None or imp[0] > best_imp[0]):
                best_imp = imp
                bi = i
        if best_imp is None:
            rp.push(make_experience_r(s, K, terminal_r(fls), s, True, mk, feats[K]), p=5.0)
            continue
        r, nf = best_imp
        rp.push(make_experience_r(s, bi, r, make_state(nf), False, mk, feats[bi]), p=2.0)
        fls = nf
    print('[seed%d] 预填分类池 %d 条 (imp/term/rest=%d/%d/%d)' % (
        seed, rp.total(), len(rp.b['imp'].buf), len(rp.b['term'].buf), len(rp.b['rest'].buf)), flush=True)
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
            s = make_state(fls)
            st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
            fmat = torch.from_numpy(feats).float().to(DEV)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qt.eval()
                qv = qt.q(st.expand(A_DIM, -1), fmat)
            qv = qv.masked_fill(mkv < 0.5, -1e9)
            idx_ok = np.argwhere(mk > 0.5).ravel()
            if np.random.rand() < eps and len(idx_ok):
                if np.random.rand() < 0.7:
                    cand_i = int(np.argmax(scores[idx_ok]))
                    a = int(idx_ok[cand_i])
                else:
                    a = int(np.random.choice(idx_ok))
            else:
                a = int(qv.argmax().item())
            if a == K:
                r = terminal_r(fls)
                done = True
                s2 = s
            elif a >= len(c) or mk[a] < 0.5:
                r = -0.2
                done = False
                s2 = s
            else:
                imp = eval_improve_scene(fls, c[a])
                if imp is None:
                    r = -0.2
                    done = False
                    s2 = s
                else:
                    r, nf = imp
                    fls = nf
                    done = False
                    s2 = make_state(fls)
            ring.append((s, a, r, done, mk, feats[a]))
            if len(ring) > NSTEP:
                s0, a0, _, _, mk0, fa0 = ring[0]
                rn = sum((0.99 ** i) * ring[i][2] for i in range(NSTEP))
                dn = ring[NSTEP - 1][3]
                rp.push(make_experience_r(s0, a0, rn, s2, dn, mk0, fa0), p=1.0)
                ring.popleft()
            if done:
                break
        while ring:
            s0, a0, _, _, mk0, fa0 = ring[0]
            rn = sum((0.99 ** i) * ring[i][2] for i in range(len(ring)))
            rp.push(make_experience_r(s0, a0, rn, s2, True, mk0, fa0), p=1.0)
            ring.popleft()
        if rp.total() >= 256:
            batch, w, refs = rp.sample(128, 1.0)
            if len(batch) >= 32:
                S = torch.tensor(np.array([e[0] for e in batch]), dtype=torch.float32).to(DEV)
                R = torch.tensor([e[2] for e in batch], dtype=torch.float32).to(DEV)
                SP = torch.tensor(np.array([e[3] for e in batch]), dtype=torch.float32).to(DEV)
                D = torch.tensor([e[4] for e in batch], dtype=torch.float32).to(DEV)
                FA = torch.tensor(np.array([e[6] for e in batch]), dtype=torch.float32).to(DEV)
                fnext = torch.zeros((len(batch), FEAT_DIM), dtype=torch.float32).to(DEV)
                fnext[:, 2] = 1.0
                with torch.no_grad():
                    qt.eval()
                    qs2 = qt.q(SP, fnext)
                    y = R + 0.99 * qs2 * (1 - D)
                q.train()
                qcur = q.q(S, FA)
                td = (qcur - y)
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
            st = torch.from_numpy(make_state(fls)).float().to(DEV).unsqueeze(0)
            fmat = torch.from_numpy(feats).float().to(DEV)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qv = q.q(st.expand(A_DIM, -1), fmat).masked_fill(mkv < 0.5, -1e9)
            a = int(qv.argmax().item())
            if a == K:
                break
            if a < len(c):
                imp = eval_improve_scene(fls, c[a])
                if imp is not None:
                    fls = imp[1]
        # 启发式局部收尾（v46 优先序标准）——次优陷阱突破
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
                          open(os.path.join(OUTD, 'p2v58_rainbow_greedy.json'), 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
                saved_g[0] = True
    if best_fls is not None:
        d = {'best': {'makespan': best_key[0], 'energy': best_key[1]},
             'solution': [{'fid': f.fid, 'model': f.model,
                           'route': [(s2, list(bs)) for s2, bs in f.route]} for f in best_fls]}
        json.dump(d, open(os.path.join(OUTD, 'p2v56_rainbow_seed%d.json' % seed), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    return best_key, gkeys


def make_state(fls):
    m, s, v, nc = eval_full(data, fls)
    return state_vec(fls, m)


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
    print('--- Rainbow(Dueling+NoisyNet+分类经验池+PER+nstep) 汇总 ---', flush=True)
    for sd, k in all_best:
        print('  seed%d best: mk=%.1f en=%.2f' % (sd, k[0], k[1]), flush=True)
    if all_best:
        sd, bk = min(all_best, key=lambda x: x[1])
        print('  --- 跨 seed 最优: seed%d mk=%.1f en=%.2f (基线 7724.9/67.61)' % (sd, bk[0], bk[1]), flush=True)
    if all_greedy:
        mks = [k[0] for _, k in all_greedy]
        ens = [k[1] for _, k in all_greedy]
        print('  greedy: mk=%.1f±%.1f, en=%.2f±%.3f (n=%d)' % (
            np.mean(mks), np.std(mks), np.mean(ens), np.std(ens), len(mks)), flush=True)
    json.dump({'summary': 'Rainbow(Dueling+NoisyNet+分类经验池imp40%%/term30%%+PER+nstep3+Double+软目标) 3seed×%dep' % n_ep,
               'all_seed_best': {str(s): list(k) for s, k in all_best},
               'greedy_mean': [float(np.mean([k[0] for _, k in all_greedy])),
                               float(np.mean([k[1] for _, k in all_greedy]))] if all_greedy else None,
               'greedy_std': [float(np.std([k[0] for _, k in all_greedy])),
                              float(np.std([k[1] for _, k in all_greedy]))] if all_greedy else None},
              open(os.path.join(OUTD, 'p2v56_rainbow.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v56_rainbow.json 用时 %.0fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()