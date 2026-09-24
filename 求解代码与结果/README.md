# 求解代码与结果说明（D题 山区洪涝灾害下无人机运输与通信协同优化）

本目录为论文所用确定性求解程序的完整副本与最终结果文件。

## 问题描述

镇龙乡山区洪涝灾害后道路损毁，需在时限内将 80 箱应急物资从调度中心 O01
运送至 15 个服务区，运输无人机全程须与调度中心保持通信。题目原文示意图
（30 m DEM 与调度节点位置关系）：

![题目图1：30 m DEM 与调度节点](../问题描述图片/问题描述图.png)

- 矢量版：[问题描述图.svg](../问题描述图片/问题描述图.svg)
- 提取脚本：`方案脚本/extract_problem_imgs.py`（从题目 docx 中抽取附图）

## 目录结构

```
求解代码与结果/
├── 代码/          求解程序（solve_d/code 全量：物理核心、调度器、图件脚本等）
├── 方案脚本/      最终方案复现脚本
│   ├── v9w_q3_final.py   问题三最终协同方案（24 架次 + 3 中继时段）
│   ├── verify_result.py  独立实证校验器（重算调度、核对时限/资源/货箱）
│   ├── v9v_dbg.py        排程核查辅助脚本
│   └── extract_problem_imgs.py  题目附图提取脚本
├── 结果/          最终结果 JSON
│   ├── p1_results.json   问题一：单点组批（18 班次）
│   ├── p2_results.json   问题二：均衡运输（24 架次，makespan 8342.1 s）
│   ├── p2_pareto.json    问题二 Pareto 前沿（均衡方案细节）
│   ├── p3_final.json     问题三：运输+中继联合调度（24 架次 + R1/R2 三时段）
│   └── p4_results.json   问题四：分区配置（K=3 / K=2）
└── README.md
```

## 运行方式

程序的数据路径为相对路径，需在原始工作区
`华为杯latex模板/` 下运行（该目录下含
`第二十三届中国研究生数学建模竞赛 - 中文题目/中文题目/D题/数据`）：

```bash
# 1. 复现问题三最终方案并生成 p3_final.json
python -X utf8 solve_d/versions/v9w_q3_final.py

# 2. 独立实证校验
python -X utf8 solve_d/versions/verify_result.py check_p3

# 3. 重绘论文图件（甘特图、中继时间线、通信保障时间线等）
python -X utf8 solve_d/code/p3_figures.py
python -X utf8 -c "import advanced_figures as af; af.fig3_relay_tl(); af.fig3_comm_tl()"

# 4. 填写《结果提交模板.xlsx》
python -X utf8 solve_d/code/export_excel.py
```

## 问题三最终结果（p3_final.json）

- 运输：24 架次（A×11、B×6、C×7），8 架无人机，14 组能源组件；
  makespan 8356.3 s，总能耗 74.95 kWh，三档时限零违反，加权迟到为零。
- 通信：38 个需中继任务段全部覆盖（西点 28、东点 7、北点 3），盲区为零；
  中继 1 全天驻西点 [715, 7941] s（2.44 kWh，返航荷电 23.8%）；
  中继 2 先东点 [760, 4049] s（1.24 kWh）后北点 [6520, 7126] s（0.54 kWh），
  转场衔接无冲突（时间线惩罚为零）。
- 独立校验：80 箱无重复无缺失；无不可行架次；硬时限零违反。

## 关键版本说明

问题三方案经历了 v9p→v9t→v9u→v9v→v9w 多轮迭代，最终采纳 v9w（见
`v9w_q3_final.py`）：在问题二 24 架次基础上执行 8 项货箱重排、2 项机型调整
（f14 A→B、f24 B→A）、2 项释放时刻微调（f20 +2485 s、f15 +1857 s），
取消 f5、f23，新增 f30、f200，总架次保持 24。
