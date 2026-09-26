# -*- coding: utf-8 -*-
"""rl_env.py —— 23 趟槽装箱 RL 环境（架次锁定 23）。
状态：箱特征 + 槽占用；动作：box->slot 分配（同区+容量合法）。
评估：dispatch_compliant 确定性调度 → 奖励按优先级（违规硬罚 > 完工 > 能耗 > 趟数偏差）。
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '代码'))
from core import Data
from p2_solve import Flight
from p2v28_compliant import dispatch_compliant, check_battery
from p2v34_timely import tardy_boxes, eval_full

N_SLOTS = 23
N_MODELS = 3
MODELS = ['A', 'B', 'C']


def pick_model(data, sid, boxes):
    """最小能耗可行机型。"""
    best = None
    for gm in MODELS:
        f = Flight(0, [(sid, boxes)], gm, data)
        if f.is_feasible():
            if best is None or f.energy() < best[1]:
                best = (gm, f.energy())
    return best


class Env23:
    def __init__(self, data):
        self.data = data
        self.boxes = list(data.boxes.keys())
        self.nb = len(self.boxes)
        self.feat = []
        for bid in self.boxes:
            bx = data.boxes[bid]
            self.feat.append([bx['priority'], bx['mass'], bx['vol'],
                              min(bx['deadline_first'], bx['deadline_exp']) / 3600.0,
                              1.0 if bx['type'] == '医疗物资' else 0.0,
                              1.0 if bx['first_batch'] else 0.0,
                              float(bx['type'] == '饮用水')])
        self.feat = np.array(self.feat, dtype=np.float32)
        self.reset()

    def reset(self):
        self.slots = [[] for _ in range(N_SLOTS)]      # 每槽 box list
        self.slot_sid = [None] * N_SLOTS               # 每槽区
        self.assigned = np.zeros(self.nb, dtype=np.int64)
        self.done = False
        self.t = 0
        return self.obs()

    def _slot_ok(self, j, bi):
        if self.assigned[bi]:
            return False
        if self.slot_sid[j] is None:
            return True
        if self.slots[j][0][0] != self.slots[j][0][0]:
            return False
        sid = self.slot_sid[j]
        if self.boxes[bi].split('-')[0] != sid:
            return False
        bs = [self.boxes[k] for k in self.slots[j]] + [self.boxes[bi]]
        return pick_model(self.data, sid, bs) is not None

    def mask(self):
        m = np.zeros((self.nb, N_SLOTS), dtype=np.float32)
        for bi in range(self.nb):
            if self.assigned[bi]:
                continue
            for j in range(N_SLOTS):
                if self._slot_ok(j, bi):
                    m[bi, j] = 1.0
        if m.sum() == 0:
            # 无合法动作：强开空槽（若还有空槽）
            for bi in range(self.nb):
                if self.assigned[bi]:
                    continue
                for j in range(N_SLOTS):
                    if self.slot_sid[j] is None:
                        m[bi, j] = 1.0
        return m

    def step(self, bi, j):
        if self.assigned[bi] or not (self.slot_sid[j] is None or self.boxes[bi].split('-')[0] == self.slot_sid[j]):
            return self.obs(), -1e6, self.done, {}
        if self.slot_sid[j] is None:
            self.slot_sid[j] = self.boxes[bi].split('-')[0]
        self.slots[j].append(bi)
        self.assigned[bi] = 1
        self.t += 1
        if self.t >= self.nb:
            self.done = True
            r = self.final_reward()
            return self.obs(), r, True, {}
        return self.obs(), 0.0, False, {}

    def final_reward(self):
        # 构造 23 趟 Flight
        fls = []
        used = 0
        for j in range(N_SLOTS):
            if not self.slots[j]:
                continue
            used += 1
            sid = self.slot_sid[j]
            bs = [self.boxes[k] for k in self.slots[j]]
            gm = pick_model(self.data, sid, bs)
            if gm is None:
                return -1e7
            fls.append(Flight(j + 1, [(sid, bs)], gm[0], self.data))
        m, s, v, nc = eval_full(self.data, fls)
        if m is None or v > 0:
            return -1e7
        r = -1e7 if (not m['hard_ok']) else 0.0
        r -= 1e5 * abs(used - N_SLOTS)   # 恰好 23 趟
        r -= nc * 1e6                     # 紧时限违规
        r -= m['makespan'] * 1.0          # 完工（第二优先）
        r -= m['energy'] * 6.0            # 能耗（第三）
        return float(r)

    def obs(self):
        # 状态：箱已分配标志 + 每区完成度 + 每槽使用度
        part = []
        # 每区剩余质量/箱数（15 区）
        sids = sorted(set(b.split('-')[0] for b in self.boxes))
        rem = []
        for sd in sids:
            ms = 0.0; ct = 0
            for bi, b in enumerate(self.boxes):
                if b.split('-')[0] == sd and not self.assigned[bi]:
                    ms += self.data.boxes[b]['mass']; ct += 1
            rem += [ms / 100.0, ct / 10.0]
        slot_use = [min(len(x) / 6.0, 1.0) for x in self.slots]
        slot_sid_o = [0.0 if s is None else 1.0 for s in self.slot_sid]
        return np.concatenate([self.assigned.astype(np.float32), np.array(rem, np.float32),
                               np.array(slot_use, np.float32), np.array(slot_sid_o, np.float32)])


if __name__ == '__main__':
    data = Data()
    env = Env23(data)
    # 随机策略 sanity
    np.random.seed(0)
    for ep in range(5):
        env.reset()
        while not env.done:
            mk = env.mask()
            idx = np.argwhere(mk.ravel() > 0).ravel()
            c = idx[np.random.randint(len(idx))]
            bi, j = divmod(c, N_SLOTS)
            env.step(bi, j)
        print('ep%d done' % ep)
    print('env ok')