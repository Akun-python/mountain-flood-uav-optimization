# -*- coding: utf-8 -*-
"""marl23.py —— 多智能体强化学习（MARL）：5 个拆分 agent（参数共享 DQN，CTDE）。
动作：每个 agent 从"脆弱候选箱池"选 1 箱拆出（不重复）；恰好拆 5 箱 → 18 满载 + 5 拆出趟 = 23 趟。
奖励（全局共享，centralized）：-违规1e6 - 完工/60 - 能耗*1.5（+常数）。
参考：Betalo et al. 2025 MA-DDQN；Qin et al. 2023 MADDPG；Liu et al. 2022 SMADDPG（CTDE 范式）。
目标：学到的 5 箱拆分 ≥ 启发式 v34/v39（23架 7771/67.78 级别）。
"""
import sys, os, json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import eval_full

torch.manual_seed(0)
np.random.seed(0)
data = Data()
OUTD = os.path.abspath(r'求解代码与结果/结果/进化_v25')
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def load_p1():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                           'results', 'p1_results.json'), encoding='utf-8') as f:
        p1 = json.load(f)
    fls = []
    fid = 1
    for sid in sorted(p1['grouping']):
        for det in p1['grouping'][sid]['detail']:
            fls.append(Flight(fid, [(sid, list(det['boxes']))], det['model'], data))
            fid += 1
    return fls


# 候选箱池（期望 <= 7200 的及时箱——拆分窗口目标）
POOL = sorted(b for b in data.boxes if data.boxes[b]['deadline_exp'] <= 7200)
print('候选池 %d 箱' % len(POOL), flush=True)
POOL_IDX = {b: i for i, b in enumerate(POOL)}
N_POOL = len(POOL)


def box_feat(bid):
    bx = data.boxes[bid]
    return [bx['priority'] / 100.0, bx['mass'] / 20.0,
            bx['deadline_exp'] / 14400.0,
            1.0 if bx['type'] == '医疗物资' else 0.0,
            1.0 if bx['first_batch'] else 0.0,
            bx['vol'], bx.get('delivery_order', 0) / 20.0]


def state_vec(chosen):
    """全局箱特征 + 已选 one-hot。"""
    v = []
    for b in POOL:
        v += box_feat(b)
    v += [0.0 if b in chosen else 1.0 for b in POOL]
    return np.asarray(v, np.float32)


S_DIM = 7 * N_POOL + N_POOL


def assemble(chosen):
    """18 满载移除 chosen 箱 + 每候选拆出成独立 A 趟 → 23 趟。"""
    base = load_p1()
    rem = {f.fid: [(s, [b for b in bs if b not in chosen]) for s, bs in f.route] for f in base}
    out = []
    fid = 1
    for f in base:
        r = rem[f.fid]
        if all(not bs for _, bs in r):
            continue
        nf = Flight(fid, r, f.model, data)
        if not nf.is_feasible():
            return None
        out.append(nf)
        fid += 1
    for b in chosen:
        sid = b.split('-')[0]
        gm = None
        for g in ['A', 'B', 'C']:  # 最小可行机型
            t = Flight(fid, [(sid, [b])], g, data)
            if t.is_feasible():
                gm = g
                break
        if gm is None:
            return None
        nf = Flight(fid, [(sid, [b])], gm, data)
        out.append(nf)
        fid += 1
    return out


class QNet(nn.Module):
    def __init__(self, sdim, adim):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(sdim, 256), nn.ReLU(),
                                 nn.Linear(256, 256), nn.ReLU(),
                                 nn.Linear(256, adim))

    def forward(self, s, mask):
        q = self.net(s)
        return q.masked_fill(mask < 0.5, -1e9)


def main():
    n_ep = int(sys.argv[1]) if len(sys.argv) > 1 else 220
    q = QNet(S_DIM, N_POOL).to(DEV)
    qt = QNet(S_DIM, N_POOL).to(DEV)
    qt.load_state_dict(q.state_dict())
    opt = optim.Adam(q.parameters(), lr=5e-4)
    rep = []
    best = None
    best_key = None
    eps = 1.0
    for ep in range(n_ep):
        chosen = set()
        log = []
        for _ in range(5):  # 5 agents 依次决策
            s = state_vec(chosen)
            mk = np.array([0.0 if b in chosen else 1.0 for b in POOL], np.float32)
            st = torch.from_numpy(s).float().to(DEV).unsqueeze(0)
            mkv = torch.from_numpy(mk).to(DEV).unsqueeze(0)
            with torch.no_grad():
                qv = qt(st, mkv)
            idx = np.argwhere(mk > 0.5).ravel()
            if np.random.rand() < eps:
                a = int(np.random.choice(idx))
            else:
                a = int(qv.argmax().item())
            if mk[a] < 0.5:
                a = int(np.random.choice(idx))
            chosen.add(POOL[a])
            log.append((s, mk, a))
        eps = max(0.1, eps * 0.996)
        fls = assemble(chosen)
        if fls is None:
            r = -1e6
        else:
            m, s2, v2, nc = eval_full(data, fls)
            if m is None or v2 > 0 or (not m['hard_ok']):
                r = -1e6
            else:
                r = -nc * 1e5 - m['makespan'] / 60.0 - 1.5 * m['energy'] + 300.0
                key = (m['makespan'], m['energy'])
                if best_key is None or key < best_key:
                    best_key = key
                    best = fls
                    print('  ep%d best: mk=%.1f en=%.2f nc=%d' % (
                        ep + 1, m['makespan'], m['energy'], nc), flush=True)
        for (s, mk, a) in log:
            rep.append((np.asarray(s, np.float32), np.asarray(mk, np.float32), a, r, 1))
        if len(rep) > 3000:
            rep = rep[-3000:]
        if len(rep) >= 64:
            idxs = np.random.choice(len(rep), 64, replace=False)
            S = torch.tensor(np.array([rep[i][0] for i in idxs]), dtype=torch.float32).to(DEV)
            M = torch.tensor(np.array([rep[i][1] for i in idxs]), dtype=torch.float32).to(DEV)
            A = torch.tensor([rep[i][2] for i in idxs], dtype=torch.long).to(DEV)
            R = torch.tensor([rep[i][3] for i in idxs], dtype=torch.float32).to(DEV)
            qv = q(S, M).gather(1, A.unsqueeze(1)).squeeze(1)
            loss = ((qv - R) ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
        if (ep + 1) % 4 == 0:
            qt.load_state_dict(q.state_dict())
        if (ep + 1) % 50 == 0:
            print('ep%d eps=%.2f' % (ep + 1, eps), flush=True)
    print('MARL %dep done. best=%s' % (n_ep, best_key), flush=True)
    if best is not None:
        json.dump({'best': {'makespan': best_key[0], 'energy': best_key[1]},
                   'solution': [{'fid': f.fid, 'model': f.model,
                                 'route': [(s2, list(bs)) for s2, bs in f.route]} for f in best]},
                  open(os.path.join(OUTD, 'p2v49_marl23.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('saved p2v49_marl23.json (best=%s vs 启发式 23架 7771/67.78)' % (best_key,), flush=True)


if __name__ == '__main__':
    main()