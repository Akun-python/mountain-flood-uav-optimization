# -*- coding: utf-8 -*-
"""rl_train.py —— 23 趟装箱 REINFORCE 训练（torch）。
策略：MLP(state156 -> logits 80x23)，mask 后 softmax 采样。
奖励：稀疏（episode 末 dispatch 评估）：-违规硬罚 -|趟数-23|罚 -完工 -6*能耗。
对照：随机策略同 episode 数 best；RL 训练 600ep，保存优于基线（23架/7771/67.78）的解。
"""
import sys, os, json, time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from rl_env import Env23, N_SLOTS, pick_model, eval_full
from p2_solve import Flight

torch.manual_seed(0)
np.random.seed(0)
OUTD = os.path.abspath(r'求解代码与结果/结果/进化_v25')


class Policy(nn.Module):
    def __init__(self, sdim, adim):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(sdim, 256), nn.ReLU(),
                                 nn.Linear(256, 256), nn.ReLU(),
                                 nn.Linear(256, adim))

    def forward(self, obs, mask):
        logits = self.net(obs)
        logits = logits.masked_fill(mask.view(-1) < 0.5, -1e9)
        return torch.log_softmax(logits, dim=-1)


def run_episode(env, policy, data, greedy=False):
    obs = env.reset()
    logps = []
    acts = []
    while not env.done:
        mk = env.mask()
        if policy is None:
            idx = np.argwhere(mk.ravel() > 0).ravel()
            a = int(idx[np.random.randint(len(idx))])
            bi, j = divmod(a, N_SLOTS)
            acts.append((bi, j))
            obs, _, done, _ = env.step(bi, j)
            env.done = done
            continue
        o = torch.from_numpy(obs).float()
        mkv = torch.from_numpy(mk.ravel())
        with torch.no_grad():
            lp = policy(o, mkv)
        if greedy:
            a = int(lp.argmax().item())
        else:
            dist = torch.exp(lp)
            a = int(torch.multinomial(dist, 1).item())
        bi, j = divmod(a, N_SLOTS)
        if mk[bi, j] < 0.5:
            # 非法回退到随机合法
            idx = np.argwhere(mk.ravel() > 0).ravel()
            a = int(idx[np.random.randint(len(idx))])
            bi, j = divmod(a, N_SLOTS)
        acts.append((bi, j))
        logps.append(lp[a])
        obs, _, done, _ = env.step(bi, j)
        env.done = done
    # 评估
    fls = []
    used = 0
    for j in range(N_SLOTS):
        if not env.slots[j]:
            continue
        used += 1
        sid = env.slot_sid[j]
        bs = [env.boxes[k] for k in env.slots[j]]
        gm = pick_model(data, sid, bs)
        if gm is None:
            return None, None, None, None, None
        fls.append(Flight(j + 1, [(sid, bs)], gm[0], data))
    m, s, v, nc = eval_full(data, fls)
    R = -1e7
    if m is not None and v == 0:
        R = 0.0
        if m['hard_ok']:
            R -= 1e5 * abs(used - N_SLOTS)
            R -= nc * 1e6
            R -= m['makespan'] * 1.0
            R -= m['energy'] * 6.0
    return R, np.array(logps), fls, (used, m, nc), None


def main():
    data = Data()
    env = Env23(data)
    sdim = len(env.obs())
    adim = env.nb * N_SLOTS
    print('sdim=%d adim=%d' % (sdim, adim), flush=True)
    n_ep = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    policy = Policy(sdim, adim)
    opt = optim.Adam(policy.parameters(), lr=1e-4)
    best = None
    best_key = None
    # 随机基线（同预算，先跑 60ep）
    rb = None
    for ep in range(60):
        R, _, fls, info, _ = run_episode(env, None, data)
        if R is not None and R > -1e6:
            used, m, nc = info
            if nc == 0 and used == N_SLOTS and m['hard_ok']:
                key = (m['makespan'], m['energy'])
                if rb is None or key < rb[0]:
                    rb = (key, fls, R)
    print('随机基线60ep best: %s' % (rb[0] if rb else None), flush=True)
    # 训练
    t0 = time.time()
    baseline = None
    for ep in range(n_ep):
        R, logps, fls, info, _ = run_episode(env, policy, data)
        if R is None:
            continue
        if R > -1e6:
            used, m, nc = info
            if nc == 0 and used == N_SLOTS and m['hard_ok']:
                key = (m['makespan'], m['energy'])
                if best is None or key < best_key:
                    best = fls
                    best_key = key
                    print('  ep%d 新best: mk=%.1f en=%.2f R=%.0f (%.0fs)' % (
                        ep + 1, m['makespan'], m['energy'], R, time.time() - t0), flush=True)
        if baseline is None:
            baseline = R
        else:
            baseline = 0.95 * baseline + 0.05 * R
        adv = R - baseline
        if logps is not None and adv != 0:
            loss = -sum(logps) * adv / max(len(logps), 1)
            opt.zero_grad()
            loss.backward()
            opt.step()
        if (ep + 1) % 100 == 0:
            print('  ep%d R=%.0f base=%.0f (%.0fs)' % (ep + 1, R, baseline, time.time() - t0), flush=True)
    print('RL %dep best: %s' % (n_ep, best_key), flush=True)
    # 贪心 rollouts 确认
    gbest = None
    for ep in range(30):
        R, _, fls, info, _ = run_episode(env, policy, data, greedy=True)
        if R is not None and R > -1e6:
            used, m, nc = info
            if nc == 0 and used == N_SLOTS and m['hard_ok']:
                key = (m['makespan'], m['energy'])
                if gbest is None or key < gbest[0]:
                    gbest = (key, fls)
    print('RL 贪心30ep best: %s' % (gbest[0] if gbest else None), flush=True)
    # 对比基线（23架/7771/67.78）并保存若更好
    BL = (7771.0, 67.78)
    cand = gbest or (best_key, best)
    if cand and cand[0] is not None and cand[0] < BL:
        mk, en = cand[0]
        fls = cand[1]
        json.dump({'best': {'makespan': mk, 'energy': en},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in fls]},
                  open(os.path.join(OUTD, 'p2v43_rl23.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('>>> RL 优于启发式基线 23架/7771/67.78 -> saved p2v43_rl23.json', flush=True)
    else:
        print('RL 未优于基线 (best=%s vs 7771/67.78)' % (cand[0] if cand and cand[0] else 'none'), flush=True)


if __name__ == '__main__':
    main()