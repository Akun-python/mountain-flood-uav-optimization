# D 题代码全面 Bug 审查报告（v28 合规口径）

**审查范围**：core.py / p2_solve.py / p1_solve.py / p3_co2.py，对照题目附录 2（时间/能耗/充电）与附录 3（通信），并复核数据文件数值。
**方法**：逐行阅读 + 公式对照 + 独立复验（dispatch_compliant / check_battery / verify_opponent 自测）。
**结论总览**：**1 个关键正确性 Bug（电池周转口径）**，**1 个中继简化**，**3 个次要问题**；其余核心公式（两阶段充电、等效航程、LOS、FSPL、中继能耗）与题意一致。

---

## A. Bug 清单（按严重度）

### B1【关键·影响全部结果】p2_solve.py dispatch() 电池起充漏掉交接时间
- **位置**：`求解代码与结果/代码/p2_solve.py` dispatch()（约 L339）：`bat_end = start + f.prep + f.flight_time()`
- **问题**：`flight_time()` 只含飞行（爬/巡/降），**不含各服务区交接 handover**。电池被允许在架次"飞行返场"后立即开始充电，而架次任务实际结束于"返回 O01"= `start + f.duration()`（= prep + flight + handover）。
- **正确口径**（题意"任务结束后的剩余 SOC…再次投入任务前应充至 100%"）：`bat['ready'] = start + f.duration() + charge_time(1 - energy/E_use, T_full)`，且电池须在下一架次**开始时刻 start** 前就绪（`ready <= start`）。
- **影响**：电池可提前 ready 一段 handover（约 180~400 s/趟），使**调度偏乐观**。合规口径重调度后：28 架 7394.9→**7666.1 s（+271）**、25 架 7639→**7790.5 s（+151）**、24 架 7889.9→**8041.5 s（+152）**；且**24 架能耗冠军在合规口径下出现 103.85 s 普通箱迟到**（EDF 下电池等待不可消，见 v28c）。
- **波及**：所有基于 `dispatch()` 的数字（P2 冠军 7394.9/7889.9、P3 联合 9305/7939、tabu/SA/merge 全部）均在此口径下得出，需按合规口径重做。
- **修法**：见 `实验/p2v28_compliant.py` 的 `dispatch_compliant()`（已实现 ready<=start + return+charge 口径）与 `check_battery()`（独立逐电池串验证 0 违规）。

### B2【中继简化】p3_co2.py 中继悬停位置固定 W/E/N
- **位置**：`p3_co2.py` L22-32（`P_W/P_E/P_N`、`AREA_POS`）。
- **问题**：题意允许中继悬停于 **DEM 覆盖范围内任意位置**（离地 ≤300 m）；现实现固定 3 个点位，把"位置"从决策变量降为常量。
- **影响**：中继覆盖/能耗/换位冲突（E→N 接力、W 拖尾）都受固定点约束，P3 联合完工 9305/7939 可能非最优；同时**固定点位是"简化假设"而非题意**，论文需声明。
- **修法**：在 DEM 上做位置搜索（可先固定 3 类位置按区聚类，再对每类内做小范围邻域搜索）。

### B3【次要】p2_solve.py normalize_flight() 区序排序无效
- **位置**：`p2_solve.py` L394：`f.route.sort(key=lambda x: flight_critical_time(data, f))`
- **问题**：排序键**忽略 x（区）**，对 route 内所有区键值相同 → Python 稳定排序保持原序，**区序未按紧急度/时限重排**。
- **对比**：`try_merge()` L223 用 `Flight(0, [x], 'A', data)` 逐区算 critical（正确做法）。
- **影响**：多区架次的服务区访问顺序可能不优（紧急区不保证先服务）；对架次时长/能耗影响较小（route 顺序改变仅影响航程与爬升组合），但属实现缺陷。
- **修法**：键改为 `key=lambda x: flight_critical_time(data, Flight(0, [x], 'A', data))`。

### B4【次要】core.py dem_at_many() nodata 检查失效
- **位置**：`core.py` L214 已把 `dem[nodata]` 替换为 nan；L252 又用 `a == self.dem_nodata` 检查——数组内已无 nodata 值，该比较**恒为 False**，形同虚设。
- **影响**：nan 值会经 `vals` 传播到 `out[valid]`，调用方（corridor_max/通信 LOS）已用 `isnan` 处理，无实际破坏；但代码意图失效、冗余。
- **修法**：删除 L252 检查或改为 `np.isnan(a)|...`。

### B5【次要·口径说明】P3 联合调度仍用宽松 dispatch
- **位置**：`p3_co2.py` L298 `schedule, _ = dispatch(data, self.flights, releases)`
- **问题**：P3 的运输部分调度复用 `p2_solve.dispatch()`（含 B1 的宽松电池口径）。
- **影响**：P3 联合完工/迟到（9305/7939/7639）同样建立在宽松电池上；合规重算后需同步更新。
- **修法**：P3 evaluate 改用 `dispatch_compliant`（v28）。

---

## B. 已核对正确（与题意一致）的正面清单

| 项 | 位置 | 结论 |
|---|---|---|
| 两阶段充电 `charge_time(s,T)` | core.py L399-404 | ✅ 与附录2 逐项一致（90% 阈值、65/35 分段） |
| 等效航程 `Lg(q)=L0-(L0-LF)(q/Q)^1.5`、`E_hor=E_use·d/Lg` | core.py route_profile_fast | ✅ |
| 爬升附加 `E_up=(m0+q)·g·h/(eta_up·3.6e6)`，eta=0.72 | core.py | ✅（与数据文件爬升效率 0.72 一致） |
| 巡航海拔=航段 DEM 最高+50m；`t=h_up/v_up+d/v_c+h_down/v_down` | core.py | ✅ |
| 返航安全余量 `E≤(1-ρ)E_use` | p2_solve.Flight.is_feasible | ✅ |
| 工位准备+装载 `prep=t_prep+nbox·t_load`、逐区交接 `handover=base+nbox·box` | p2_solve.Flight | ✅ |
| 投送位置=箱属区（L362-365）、首批/医疗硬时限（L366-369）、其余加权迟到 | p2_solve.evaluate | ✅ |
| 电池数量 A6/B4/C4、同型电池不可混用、逐架次电池分配 | p2_solve.dispatch/make_resources | ✅（仅起充时刻 B1 例外） |
| 共享电池周转（下一趟 start 需 ≥ 返场+充电） | p2v28_compliant.check_battery | ✅ 0 违规（严格口径下） |
| 中继能源组件 n=6、满充复用、SOC=1-e/E_use | p3_co2.CompPool | ✅ |
| 通信：LOS 遮挡 + FSPL + Lobs + 双向门限 min | core.py | ✅ |
| 运输/中继链路参数（f2400/Psens-98/M8/Pt20/Pt19…） | core.py load_comm | ✅ 与数据一致 |
| DEM 分辨率 30m（1/3600°）、双线性插值 | core.py | ✅ |
| P1 最大安全载荷二分 + ILP 组批（质量/体积/机型） | p1_solve | ✅ |
| 中继出/返航时间与能耗（巡航+爬升+悬停服务） | core.py relay_mission_* | ✅ |

---

## C. 合规口径重求解结果（PYTHONHASHSEED=0，确定性）

| 方案 | 架次 | 旧(宽松)完工 | **合规完工** | 能耗 kWh | 迟到 | 电池违规 |
|---|---|---|---|---|---|---|
| v25b（完工优先） | 28 | 7394.9 | **7666.1** (127.8min) | 83.12 | 0 | 0 |
| v25i（能耗冠军·合规） | 25 | 7639.0 | **7790.5** (129.8min) | **78.88** | 0 | 0 |
| v25j（能耗最优·合规不合格） | 24 | 7889.9 | 8041.5 | 77.41 | **103.85** | 0 |
| v28b/v28d 合规口径再 merge | — | — | 无改善（结构已紧） | — | — | — |

**合规双冠军**：
- **完工优先**：28 架 / **7666.1 s（127.8 min）** / 83.12 kWh / 零迟到 / 0 电池违规
- **能耗优先**：25 架 / **7790.5 s（129.8 min）** / **78.88 kWh** / 零迟到 / 0 电池违规

**重要说明**：24 架/77.41 kWh 在严格口径下不可行（普通箱迟到 103.85 s，v28c 两种电池选择策略均不可消）——**旧能耗冠军作废**，能耗冠军改为 25 架/78.88。
