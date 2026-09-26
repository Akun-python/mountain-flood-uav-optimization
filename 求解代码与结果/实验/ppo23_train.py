# -*- coding: utf-8 -*-
"""ppo23_train.py —— PPO 训练 23 架 learn-to-improve（标准实现）。
网络：MLP(170→256→256)；actor=候选选择 logits（mask），critic=value。
GAE(lam=0.95, gamma=0.99)；PPO clip=0.2；4 epochs；批次更新。
起点：p2v46_23local.json（23架/7724.9/67.61）；保存训练中完工+能耗最优解。
参考：Schulman et al. 2017 (PPO)；Kool et al. 2019 (组合优化 DRL)。
"""
import sys, os, json, time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppo23_env import PPO23Env, K, eval_full, data, OUTD

torch.manual_seed(0)
np.random.seed(0)
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('device', DEV, flush=True)


class AC(nn.Module):
    def __init__(self, sdim, adim):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(sdim, 256), nn.ReLU(),
                                  nn.Linear(256, 256), nn.ReLU())
        self.pi = nn.Linear(256, adim)
        self.v = nn.Linear(256, 1)

    def forward(self, s, mask):
        h = self.body(s)
        logits = self.pi(h).masked_fill(mask < 0.5, -1e9)
        return torch.log_softmax(logits, dim=-1), self.v(h)


def gae(rews, vals, dones, gamma=0.99, lam=0.95):
    T = len(rews)
    adv = np.zeros(T)
    g = 0.0
    for t in reversed(range(T)):
        nv = 0.0 if t == T - 1 else vals[t + 1]
        delta = rews[t] + gamma * nv * (1 - dones[t]) - vals[t]
        g = delta + gamma * lam * (1 - dones[t]) * g
        adv[t] = g
    return adv


def main():
    n_ep = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    env = PPO23Env(os.path.join(OUTD, 'p2v46_23local.json'))
    net = AC(170, K).to(DEV)
    opt = optim.Adam(net.parameters(), lr=3e-4)
    best_fls = None
    best_key = None
    t0 = time.time()

    for ep in range(n_ep):
        s = env.reset()
        buf_s, buf_a, buf_old, buf_r, buf_d, buf_mask = [], [], [], [], [], []
        done = False
        while not done:
            mk = env.run_candidates()
            st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                lp, _ = net(st, mkv)
            probs = torch.exp(lp)
            dist = torch.distributions.Categorical(probs=probs)
            a = int(dist.sample().item())
            buf_s.append(s); buf_a.append(a); buf_old.append(float(lp[0, a].item()))
            buf_mask.append(mk)
            s, r, done, _ = env.step(a)
            buf_r.append(r); buf_d.append(done)
        # 本 ep 终点评估
        m, ss, v, nc = eval_full(data, env.fls)
        if m and v == 0 and nc == 0:
            key = (m['makespan'], m['energy'])
            if best_key is None or key < best_key:
                best_key = key
                best_fls = [type(f)(f.fid, [(s2, list(bs)) for s2, bs in f.route], f.model, data)
                            for f in env.fls]
                print('  ep%d best: mk=%.1f en=%.2f (%.0fs)' % (
                    ep + 1, m['makespan'], m['energy'], time.time() - t0), flush=True)
        if len(buf_s) < 2:
            continue
        S = torch.tensor(np.array(buf_s), dtype=torch.float32).to(DEV)
        A = torch.tensor(buf_a, dtype=torch.long).to(DEV)
        Old = torch.tensor(buf_old, dtype=torch.float32).to(DEV)
        M = torch.tensor(np.array(buf_mask), dtype=torch.float32).to(DEV)
        with torch.no_grad():
            _, vals = net(S, M)
        vals_np = vals.cpu().numpy().ravel()
        adv = gae(buf_r, vals_np, np.array(buf_d, np.float32))
        ret = adv + vals_np
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        Aadv = torch.tensor(adv, dtype=torch.float32).to(DEV)
        Rtr = torch.tensor(ret, dtype=torch.float32).to(DEV)
        for _ in range(4):
            lp, vnow = net(S, M)
            probs = torch.exp(lp)
            dist = torch.distributions.Categorical(probs=probs)
            logp = dist.log_prob(A)
            ratio = torch.exp(logp - Old)
            clip_r = torch.clamp(ratio, 1 - 0.2, 1 + 0.2)
            pobj = -torch.min(ratio * Aadv, clip_r * Aadv).mean()
            ent = dist.entropy().mean()
            vloss = ((vnow.ravel() - Rtr) ** 2).mean()
            loss = pobj - 0.01 * ent + 0.5 * vloss
            opt.zero_grad(); loss.backward(); opt.step()

    print('PPO %dep done. best=%s' % (n_ep, best_key), flush=True)
    if best_fls is not None:
        json.dump({'best': {'makespan': best_key[0], 'energy': best_key[1]},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in best_fls]},
                  open(os.path.join(OUTD, 'p2v48_ppo23.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved p2v48_ppo23.json (best=%s vs 基线 7724.9/67.61)' % (best_key,), flush=True)
    else:
        print('无可用 best', flush=True)


if __name__ == '__main__':
    main()