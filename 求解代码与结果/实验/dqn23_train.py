# -*- coding: utf-8 -*-
"""dqn23_train.py —— Double DQN + 经验回放（experience replay）训练 23 架 learn-to-improve。
- off-policy：replay buffer（cap=60000）+ 预填启发式改进轨迹；target soft update τ=0.005；γ=0.99；batch=128。
- 动作空间：候选邻域算子(0..K-1) + **STOP(K)**——学会识别无改进点并保持最优解。
- 多 seed 独立训练，保存每 seed 最优解 JSON + 分布统计。
- 奖励：违规硬罚 + Δ完工/60 + 1.5*Δ能耗；STOP 终局奖励 = -(完工/60+1.5*能耗)+250。
参考：Mnih et al. 2015 Nature DQN(replay)；Hasselt et al. 2016 Double DQN。
"""
import sys, os, json, time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppo23_env import build_candidates, eval_improve, eval_full, data, OUTD, K, state_vec
from p2_solve import Flight

torch.manual_seed(0)
np.random.seed(0)
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('device', DEV, flush=True)
A_DIM = K + 1  # 0..K-1 候选 + K=STOP


class QNet(nn.Module):
    def __init__(self, sdim, adim, seed=0):
        super().__init__()
        torch.manual_seed(seed)
        np.random.seed(seed)
        self.net = nn.Sequential(nn.Linear(sdim, 256), nn.ReLU(),
                                 nn.Linear(256, 256), nn.ReLU(),
                                 nn.Linear(256, adim))

    def forward(self, s, mask):
        return self.net(s).masked_fill(mask < 0.5, -1e9)


def load_init():
    d0 = json.load(open(os.path.join(OUTD, 'p2v46_23local.json'), encoding='utf-8'))
    return [Flight(f['fid'], [(s, list(bs)) for s, bs in f['route']], f['model'], data)
            for f in d0['solution']]


def make_state(fls):
    m, s, v, nc = eval_full(data, fls)
    return state_vec(fls, m)


def terminal_r(fls):
    m, s, v, nc = eval_full(data, fls)
    return -(m['makespan'] / 60.0 + 1.5 * m['energy']) + 250.0


def clone(fls):
    return [Flight(f.fid, [(s2, list(bs)) for s2, bs in f.route], f.model, data) for f in fls]


def make_mask(c):
    mk = np.zeros(A_DIM, np.float32)
    for i in range(min(len(c), K)):
        mk[i] = 1.0
    mk[K] = 1.0  # STOP 恒合法
    return mk


class Replay:
    def __init__(self, cap=60000):
        self.buf = []
        self.cap = cap

    def push(self, e):
        self.buf.append(e)
        if len(self.buf) > self.cap:
            self.buf.pop(0)

    def sample(self, n):
        idx = np.random.choice(len(self.buf), n, replace=False)
        return [self.buf[i] for i in idx]


def prefilled(fls0, n=100, seed=0):
    np.random.seed(seed)
    fls = clone(fls0)
    exp = []
    for _ in range(n):
        c = build_candidates(fls)
        if not c:
            exp.append((make_state(fls), K, terminal_r(fls), make_state(fls), 1.0, make_mask(c)))
            break
        mk = make_mask(c)
        s = make_state(fls)
        best_imp = None
        best_i = -1
        for i, cand in enumerate(c[:min(len(c), K)]):
            imp = eval_improve(fls, cand)
            if imp is not None and (best_imp is None or imp[0] > best_imp[0]):
                best_imp = imp
                best_i = i
        if best_imp is None:
            # 无改进 → 学 STOP
            exp.append((s, K, terminal_r(fls), s, 1.0, mk))
            continue
        r, nf = best_imp
        fls = nf
        exp.append((s, best_i, r, make_state(fls), 0.0, mk))
        if len(exp) % 10 == 0 and len(c) > 1:
            a = int(np.random.randint(min(len(c), K)))
            exp.append((s, a, -0.2, make_state(fls), 0.0, mk))
    return exp


def train_seed(seed, n_ep=150):
    torch.manual_seed(seed)
    np.random.seed(seed)
    q = QNet(170, A_DIM, seed=seed).to(DEV)
    qt = QNet(170, A_DIM, seed=seed + 999).to(DEV)
    qt.load_state_dict(q.state_dict())
    opt = optim.Adam(q.parameters(), lr=5e-4)
    rp = Replay()
    init = load_init()
    for e in prefilled(init, seed=seed):
        rp.push(e)
    print('[seed%d] 预填经验池 %d 条' % (seed, len(rp.buf)), flush=True)
    eps = 0.9
    best_fls = None
    best_key = None
    t0 = time.time()
    for ep in range(n_ep):
        fls = clone(init)
        for t in range(10):
            c = build_candidates(fls)
            mk = make_mask(c)
            s = make_state(fls)
            st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qv = qt(st, mkv)
            idx = np.argwhere(mk > 0.5).ravel()
            if np.random.rand() < eps or len(idx) == 0:
                a = int(np.random.choice(idx)) if len(idx) else K
            else:
                a = int(qv.argmax().item())
            if a == K:
                r = terminal_r(fls)
                done = True
            elif a >= len(c) or mk[a] < 0.5:
                r = -0.2
                done = False
            else:
                imp = eval_improve(fls, c[a])
                if imp is None:
                    r = -0.2
                    done = False
                else:
                    r, nf = imp
                    fls = nf
                    done = False
            rp.push((s, a, r, make_state(fls), 1.0 if done else 0.0, mk))
            rp.push((s, K, terminal_r(fls), s, 1.0, mk))  # STOP 经验（教 Q 识别收敛点）
            if done:
                break
            if len(rp.buf) >= 128:
                batch = rp.sample(128)
                S = torch.tensor(np.array([e[0] for e in batch]), dtype=torch.float32).to(DEV)
                A = torch.tensor([e[1] for e in batch], dtype=torch.long).to(DEV)
                R = torch.tensor([e[2] for e in batch], dtype=torch.float32).to(DEV)
                SP = torch.tensor(np.array([e[3] for e in batch]), dtype=torch.float32).to(DEV)
                D = torch.tensor([e[4] for e in batch], dtype=torch.float32).to(DEV)
                M = torch.tensor(np.array([e[5] for e in batch]), dtype=torch.float32).to(DEV)
                with torch.no_grad():
                    qsp = qt(SP, M)
                    y = R + 0.99 * qsp.max(1)[0] * (1 - D)
                qv = q(S, M).gather(1, A.unsqueeze(1)).squeeze(1)
                loss = ((qv - y) ** 2).mean()
                opt.zero_grad(); loss.backward(); opt.step()
        eps = max(0.05, eps * 0.99)
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
    gkeys = []
    for _ in range(10):
        fls = clone(init)
        for t in range(10):
            c = build_candidates(fls)
            mk = make_mask(c)
            st = torch.from_numpy(make_state(fls)).float().to(DEV).unsqueeze(0)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qv = qt(st, mkv)
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
        json.dump(d, open(os.path.join(OUTD, 'p2v51_dqn23_seed%d.json' % seed), 'w', encoding='utf-8'),
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
    print('--- DQN+replay(STOP) 汇总 ---', flush=True)
    for sd, k in all_best:
        print('  seed%d best: mk=%.1f en=%.2f' % (sd, k[0], k[1]), flush=True)
    if all_best:
        sd, bk = min(all_best, key=lambda x: x[1])
        print('  --- 跨 seed 最优: seed%d mk=%.1f en=%.2f (基线 7724.9/67.61)' % (sd, bk[0], bk[1]), flush=True)
    if all_greedy:
        mks = [k[0] for _, k in all_greedy]
        ens = [k[1] for _, k in all_greedy]
        print('  greedy 策略（10ep×%dseed, 训练后）: mk=%.1f±%.1f, en=%.2f±%.3f' % (
            len(set(s for s, _ in all_greedy)), np.mean(mks), np.std(mks),
            np.mean(ens), np.std(ens)), flush=True)
    json.dump({'summary': 'DoubleDQN+replay+STOP 多seed训练（%dep/seed, seeds=%s, 预填启发式经验, soft-target τ0.005, γ0.99, batch128, ε衰减0.99）' % (n_ep, seeds),
               'all_seed_best': {str(s): list(k) for s, k in all_best},
               'greedy_after_train_mean': [float(np.mean([k[0] for _, k in all_greedy])),
                                           float(np.mean([k[1] for _, k in all_greedy]))
                                           ] if all_greedy else None,
               'greedy_after_train_std': [float(np.std([k[0] for _, k in all_greedy])),
                                          float(np.std([k[1] for _, k in all_greedy]))
                                          ] if all_greedy else None},
              open(os.path.join(OUTD, 'p2v51_dqn23.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2v51_dqn23.json (+seed 最优解) 用时 %.0fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()