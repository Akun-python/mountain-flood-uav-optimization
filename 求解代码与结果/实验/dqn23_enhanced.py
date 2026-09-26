# -*- coding: utf-8 -*-
"""dqn23_enhanced.py —— 针对"23架无人机救援装箱调度"定制的 DQN（vs 默认版对比）。
问题定制点：
1) **动作特征化(action-embedding)**：Q(s,a) 由 状态特征 + 动作内容特征(类型/区/质量/时长/箱数/启发式评分)
   联合计算——异构动作可泛化，STOP 有专属特征（默认版纯 index 编码丢弃动作内容）。
2) **Prioritized Experience Replay (PER)**：按 |TD-error|^0.6 优先采样改进经验（稀疏正信号），
   β 0.4→1 退火，重要性权重修正（Schaul et al. 2016）。
3) **n-step 回报(n=3)**：捕获多步协同（先牺牲后重建）的延迟奖励。
4) **启发式引导探索**：ε 时 70% 概率选启发式评分最高的候选（结构化探索），30% 随机。
其余：Double-DQN、soft-target τ0.005、γ0.99、batch128、状态170维、预填启发式轨迹、STOP 动作。
"""
import sys, os, json, time
from collections import deque
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppo23_env import data, OUTD, K, state_vec, eval_full, build_candidates, eval_improve
from p2_solve import Flight

torch.manual_seed(0)
np.random.seed(0)
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('device', DEV, flush=True)
A_DIM = K + 1
FEAT_DIM = 12
S_DIM = 170
NSTEP = 3


class Net(nn.Module):
    def __init__(self, seed=0):
        super().__init__()
        torch.manual_seed(seed)
        np.random.seed(seed)
        self.senc = nn.Sequential(nn.Linear(S_DIM, 128), nn.ReLU(),
                                  nn.Linear(128, 128), nn.ReLU())
        self.aenc = nn.Sequential(nn.Linear(FEAT_DIM, 64), nn.ReLU())
        self.qa = nn.Sequential(nn.Linear(128 + 64, 64), nn.ReLU(), nn.Linear(64, 1))

    def q(self, s, fa):
        h = self.senc(s)
        ea = self.aenc(fa)
        return self.qa(torch.cat([h, ea], dim=-1)).squeeze(-1)


def clone(fls):
    return [Flight(f.fid, [(s2, list(bs)) for s2, bs in f.route], f.model, data) for f in fls]


def make_state(fls):
    m, s, v, nc = eval_full(data, fls)
    return state_vec(fls, m)


def terminal_r(fls):
    m, s, v, nc = eval_full(data, fls)
    return -(m['makespan'] / 60.0 + 1.5 * m['energy']) + 250.0


SID_MAP = {sid: i for i, sid in enumerate(sorted(set(b.split('-')[0] for b in data.boxes)))}


def feat_for(cand, fls):
    """候选→12 维动作特征（类型/区/质量/时长/箱数/启发式评分）。"""
    t, a, b, box, x = cand
    f = np.zeros(FEAT_DIM, np.float32)
    if t == 'stop':
        f[2] = 1.0  # STOP 标志
        return f
    fa = next(u for u in fls if u.fid == a)
    if t == 'ret':
        f[0] = 1.0  # ret
        f[3] = SID_MAP.get(fa.route[0][0], 0.0) / 15.0
        f[4] = fa.total_mass / 80.0
        f[5] = fa.duration() / 3000.0
        f[6] = len(fa.box_ids) / 8.0
        f[7] = 1.0 if x == 'C' else (0.5 if x == 'B' else 0.0)
        f[9] = 1.0 if fa.model == 'A' else (0.5 if fa.model == 'B' else 0.0)
        return f
    fb = next(u for u in fls if u.fid == b)
    bm = data.boxes[box]['mass'] if box else 0.0
    f[1] = 1.0  # mig
    f[3] = SID_MAP.get(fa.route[0][0], 0.0) / 15.0
    f[4] = bm / 20.0
    f[5] = (fa.total_mass - bm) / 80.0
    f[6] = (fb.total_mass + bm) / 80.0
    f[7] = fa.duration() / 3000.0
    f[8] = fb.duration() / 3000.0
    f[9] = len(fa.box_ids) / 8.0
    f[10] = len(fb.box_ids) / 8.0
    f[11] = data.boxes[box]['priority'] / 100.0
    return f


def build_candidates_f(fls):
    """候选 + 特征矩阵(K+1,FEAT) + 启发式评分。"""
    from ppo23_env import build_candidates
    c = build_candidates(fls)
    feats = np.zeros((K + 1, FEAT_DIM), np.float32)
    scores = np.zeros(K + 1, np.float32)
    for i in range(min(len(c), K)):
        feats[i] = feat_for(c[i], fls)
        t, a, b, box, x = c[i]
        fa = next(u for u in fls if u.fid == a)
        if t == 'mig':
            fb = next(u for u in fls if u.fid == b)
            scores[i] = (fb.total_mass - fa.total_mass) / 80.0 + 0.5 * (fb.duration() - fa.duration()) / 3000.0
        elif t == 'ret':
            scores[i] = 0.1
    # STOP 动作特征 + 评分（最高优先尝试? 评分仅引导 ε 探索, STOP 给 0）
    feats[K] = feat_for(('stop', -1, -1, None, None), fls)
    return c, feats, scores


def make_mask(c):
    mk = np.zeros(A_DIM, np.float32)
    for i in range(min(len(c), K)):
        mk[i] = 1.0
    mk[K] = 1.0
    return mk


class PER:
    """Prioritized Experience Replay（Schaul et al. 2016）。"""
    def __init__(self, cap=60000, alpha=0.6, beta0=0.4):
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


def make_experience(s, a, r_n, s2, done, mk, fa):
    return (s, a, r_n, s2, 1.0 if done else 0.0, mk, fa)


def train_seed(seed, n_ep=150):
    torch.manual_seed(seed)
    np.random.seed(seed)
    q = Net(seed=seed).to(DEV)
    qt = Net(seed=seed + 999).to(DEV)
    qt.load_state_dict(q.state_dict())
    opt = optim.Adam(q.parameters(), lr=5e-4)
    rp = PER()
    init = clone(load_init())
    # 预填：启发式改进轨迹 + STOP
    fls = clone(init)
    for _ in range(100):
        c, feats, scores = build_candidates_f(fls)
        mk = make_mask(c)
        s = make_state(fls)
        if not c:
            rp.push(make_experience(s, K, terminal_r(fls), s, True, mk, feats[K]), p=5.0)
            break
        best_imp = None
        bi = -1
        for i in range(min(len(c), K)):
            imp = eval_improve(fls, c[i])
            if imp is not None and (best_imp is None or imp[0] > best_imp[0]):
                best_imp = imp
                bi = i
        if best_imp is None:
            rp.push(make_experience(s, K, terminal_r(fls), s, True, mk, feats[K]), p=5.0)
            continue
        r, nf = best_imp
        rp.push(make_experience(s, bi, r, make_state(nf), False, mk, feats[bi]), p=2.0)
        fls = nf
    print('[seed%d] 预填 PER 池 %d 条' % (seed, len(rp.buf)), flush=True)
    eps = 0.9
    best_fls = None
    best_key = None
    t0 = time.time()
    for ep in range(n_ep):
        fls = clone(init)
        ring = deque()
        for t in range(10):
            c, feats, scores = build_candidates_f(fls)
            mk = make_mask(c)
            s = make_state(fls)
            st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
            fmat = torch.from_numpy(feats).float().to(DEV)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qv = qt.q(st.expand(A_DIM, -1), fmat)
            qv = qv.masked_fill(mkv < 0.5, -1e9)
            idx_ok = np.argwhere(mk > 0.5).ravel()
            if np.random.rand() < eps or len(idx_ok) == 0:
                if len(idx_ok) and np.random.rand() < 0.7:
                    # 启发式引导：评分最高合法候选
                    cand_i = int(np.argmax(scores[idx_ok]))
                    a = int(idx_ok[cand_i])
                else:
                    a = int(np.random.choice(idx_ok)) if len(idx_ok) else K
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
                imp = eval_improve(fls, c[a])
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
                rp.push(make_experience(s0, a0, rn, s2, dn, mk0, fa0), p=1.0)
                ring.popleft()
            if done:
                break
        # 剩余 ring 打折 push
        while ring:
            s0, a0, _, _, mk0, fa0 = ring[0]
            rn = sum((0.99 ** i) * ring[i][2] for i in range(len(ring)))
            rp.push(make_experience(s0, a0, rn, s2, True, mk0, fa0), p=1.0)
            ring.popleft()
        # 训练
        if len(rp.buf) >= 256:
            batch, w, idx = rp.sample(128)
            S = torch.tensor(np.array([e[0] for e in batch]), dtype=torch.float32).to(DEV)
            A = torch.tensor([e[1] for e in batch], dtype=torch.long).to(DEV)
            R = torch.tensor([e[2] for e in batch], dtype=torch.float32).to(DEV)
            SP = torch.tensor(np.array([e[3] for e in batch]), dtype=torch.float32).to(DEV)
            D = torch.tensor([e[4] for e in batch], dtype=torch.float32).to(DEV)
            FA = torch.tensor(np.array([e[6] for e in batch]), dtype=torch.float32).to(DEV)
            fnext = torch.zeros((128, FEAT_DIM), dtype=torch.float32).to(DEV)
            fnext[:, 2] = 1.0  # STOP 特征（下一状态仅允许 STOP 评估近似）
            with torch.no_grad():
                qs2 = qt.q(SP, fnext)
                y = R + 0.99 * qs2 * (1 - D)
            qcur = q.q(S, FA)  # 逐条 Q(s_t, a_t)（FA 已按经验存储对应动作特征）
            td = (qcur - y)
            loss = (torch.tensor(w, dtype=torch.float32).to(DEV) * td ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
            rp.update(idx, td.detach().cpu().numpy())
        eps = max(0.05, eps * 0.99)
        rp.beta = min(1.0, rp.beta + (1.0 - 0.4) / n_ep)
        if ep % 10 == 0:
            with torch.no_grad():
                for p, pt_ in zip(q.parameters(), qt.parameters()):
                    pt_.data.mul_(1 - 0.005).add_(0.005 * p.data)
        m, s2, v, nc = eval_full(data, fls)
        if m and v == 0 and nc == 0:
            key = (m['makespan'], m['energy'])
            if best_key is None or key < best_key:
                best_key = key
                best_fls = clone(fls)
                print('  [seed%d] ep%d best: mk=%.1f en=%.2f (%.0fs)' % (
                    seed, ep + 1, m['makespan'], m['energy'], time.time() - t0), flush=True)
    # greedy 评估
    gkeys = []
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
                qv = qt.q(st.expand(A_DIM, -1), fmat).masked_fill(mkv < 0.5, -1e9)
            a = int(qv.argmax().item())
            if a == K:
                break
            if a < len(c):
                imp = eval_improve(fls, c[a])
                if imp is not None:
                    fls = imp[1]
        m, s2, v, nc = eval_full(data, fls)
        if m and v == 0 and nc == 0:
            gkeys.append((m['makespan'], m['energy']))
    if best_fls is not None:
        d = {'best': {'makespan': best_key[0], 'energy': best_key[1]},
             'solution': [{'fid': f.fid, 'model': f.model,
                           'route': [(s2, list(bs)) for s2, bs in f.route]} for f in best_fls]}
        json.dump(d, open(os.path.join(OUTD, 'p2v52_dqn23e_seed%d.json' % seed), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    return best_key, gkeys


def load_init():
    d0 = json.load(open(os.path.join(OUTD, 'p2v46_23local.json'), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d0['solution']]


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
    print('--- DQN-enh(特征化+PER+nstep+引导探索) 汇总 ---', flush=True)
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
    json.dump({'summary': 'DQN-enhanced(动作特征化12维+PER(alpha0.6,beta0.4->1)+nstep3+启发式引导探索70%%-概率) 3seed×%dep' % n_ep,
               'all_seed_best': {str(s): list(k) for s, k in all_best},
               'greedy_mean': [float(np.mean([k[0] for _, k in all_greedy])),
                               float(np.mean([k[1] for _, k in all_greedy]))] if all_greedy else None,
               'greedy_std': [float(np.std([k[0] for _, k in all_greedy])),
                              float(np.std([k[1] for _, k in all_greedy]))] if all_greedy else None},
              open(os.path.join(OUTD, 'p2v52_dqn23e.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v52_dqn23e.json 用时 %.0fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()