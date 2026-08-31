# Proposal

## Gap

IEC 62443-3-2 能把工业控制系统划分为 zone 与 conduit，也要求在边界上形成风险与安全级别，但它没有给出一种可委托、可撤销、且能约束物理动作后果的授权对象。另一方面，CPS 能力系统已经能把 Macaroon/CHERI 能力绑定到物理资源，CPAC 已经做过 physics-aware access control，ZTPM 与 SINT 在 2026 年又进一步覆盖了 agent 委托收缩、物理参数边界、运行时上下文和人工升级。因此，本项目不能再把“物理感知能力授权”本身当作 novelty。仍可能成立的 gap 是：**从 IEC 62443 zone/conduit 风险模型编译出能力，并从令牌的句法衰减证明到运行时物理轨迹/可达集包含；同时说明 `REWRITE` 与 `DEFER` 在什么条件下不会破坏该包含关系。** 这不是把 Macaroon 换到 OT 域，因为非单调策略组合、越界 rewrite、或没有合法 hold 动作的 defer 都能直接构造反例；编译器必须逐项解除这些证明义务。若 C1 最终只是通过定义“衰减 = 可达集包含”而成立，或 SINT 抢先补齐同一编译器与定理，则 gap 消失。

## 最接近的工作

| 工作 | 做了什么 | 我们的 delta |
|---|---|---|
| [Dodson 2021 / CHERI Macaroons 2020](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-963.pdf) | 在机器人与 ICS 中构造、委托并执行代表物理资源的 Macaroon/CHERI 能力。 | 不再主张“CPS capability”新颖；只主张 62443 编译与句法衰减到物理行为的 refinement theorem。 |
| [CPAC, ACSAC 2016](https://doi.org/10.1145/2991079.2991126) | 用电网物理模型生成并执行 physics-aware access-control policy。 | 不再主张“physics-aware access control”新颖；我们研究去中心化衰减及 edit effect 的组合条件。 |
| [Smart I/O / Lanotte–Merro / Baird–Roop runtime-enforcement 线](https://doi.org/10.1145/3546579) | 用 edit automata、双向 I/O 修正和硬件组合执行 CPS 安全策略。 | 他们解决 enforcer 机制与扩展性；我们解决授权语义及其对物理行为的 refinement，不做更快 enforcer 的贡献。 |
| [ZTPM, arXiv:2605.25653, 2026](https://arxiv.org/abs/2605.25653) | 已有物理对象、实时风险分级、参数限制、序列检查、委托收缩和 `PERMIT/DENY/DEFER`。 | 直接重叠很大，但尚无 62443 编译、密码能力实现和可达集证明。 |
| [SINT Protocol v0.2, 2026](https://github.com/sint-ai/sint-protocol/blob/main/WHITEPAPER.md) | 已实现 Ed25519 能力、衰减委托、物理约束、撤销、审批、危险序列和工业 bridge。 | 最直接工程对手；ZoneCap 只能靠 standards traceability 与 formal assurance 区分，不能靠功能列表。 |

## Claims

### C1 [core] "Under conjunctive ZoneCap caveats and authority-preserving runtime effects, if capability c' attenuates c, then for any fixed plant model, initial-state set, disturbance set, and finite horizon H, the physical reachable set induced by c' is a subset of that induced by c."

- 一句话：从独立定义的 token 句法偏序，证明到 emitted-transition、trace、reachable-set 三层包含。
- 为真 / 为假的观察：证明在一维、通用 transition system 与 MIMO lifting 上闭合，所有注册检查零违反；任一合法 child 产生 parent 不可能产生的物理状态，或必须用可达集反过来定义衰减，即为假。
- 替代解释：A1 只是定义造成的 tautology → exp-01/02；A2 只对标量区间成立 → exp-03；A3 因为省略 rewrite/defer 才成立 → exp-04。

### C2 [core] "For two held-out IEC 62443-aligned reference architectures, ZoneCap compilation is decision-equivalent to an independent zone/conduit policy oracle while every depth-1 and depth-2 delegation preserves or narrows zone, conduit, asset, action, parameter, time, mode, and pre-action-sequence authority."

- 一句话：证明编译器既忠实于 zone/conduit policy，又不会让多级委托扩权。
- 为真 / 为假的观察：两个冻结架构的合法请求与全部单字段 mutation 均与独立 oracle 一致，八个权限维度的扩权 mutation 全被拒绝；任一不一致、漏表达或扩权即为假。
- 替代解释：A1 fixture 与编译器同源所以“完美一致” → exp-08；A2 只测 depth 0 或单 conduit → exp-09。

### C3 "A runtime enforcement semantics with ALLOW, DENY, ATTENUATE, REWRITE, and DEFER preserves C1 whenever rewrites remain within the effective capability and deferrals are modeled as parent-admissible stutter transitions."

- 一句话：把 edit automaton 的物理输出约束成授权语义的一部分。
- 为真 / 为假的观察：五类 effect 均可达，组合证明闭合，bounded checking 无越权输出、包含违反或死锁；出现任一 child-only transition 即为假。
- 替代解释：A1 deny-only 已足够 → exp-13；A2 只在手选 trace 安全 → exp-14。

### C4 "ZoneCap revocation and deterministic conflict resolution prevent post-revocation execution, privilege union across concurrent holders, and deadlock in the preregistered bounded multi-principal model."

- 一句话：多主体并发时不把各自局部权限意外合并，也不因撤销/审批进入死锁。
- 为真 / 为假的观察：注册的全部 interleaving 中三类 safety violation 与 deadlock 均为零；任一反例或隐藏的公平调度假设即为假。
- 替代解释：A1 检查 bound 太浅 → exp-18；A2 依赖善意中心调度器 → exp-19。

### C5 "On the approved OpenPLC/Jetson testbed, ZoneCap's p99 decision latency is at most 1 ms and consumes at most 10% of a 10 ms PLC scan cycle while enforcing the registered policy set."

- 一句话：完整 token 校验、撤销、上下文与审计路径仍能进入预注册 OT 预算。
- 为真 / 为假的观察：五次独立进程重复全部满足两个阈值，且优化前后决策完全一致；任一重复超阈值或优化改变决策即为假。
- 替代解释：A1 只因 warm cache 或关闭检查 → exp-23；A2 只因策略数量过少 → exp-24。

## 实验计划

| exp | claim | 目的 | 预计 GPU-h |
|---|---|---|---|
| exp-01–06 | C1 | 先完成一维证明与反例搜索，再检查 MIMO、state/history dependence、rewrite/defer 条件及 SINT/Dodson 对照 | 0 |
| exp-07–11 | C2 | 在冻结的 Cisco CPwE 与 ENISA railway 架构上做独立 oracle、全 cross-product、mutation、多级委托和基线比较 | 0 |
| exp-12–16 | C3 | 五类 effect 的组合证明、bounded model checking、deny-only ablation 与已知反例 sanity | 0 |
| exp-17–21 | C4 | 枚举多主体 interleaving，增加 bound，改用 adversarial scheduler，并与 SINT 撤销/审批对照 | 0 |
| exp-22–26 | C5 | 在获批 Jetson/OpenPLC 上做五次全路径性能重复、cache/检查消融、策略规模扩展和 timer sanity | 0 |

总计：**0 GPU-h，约 85 CPU-h，另需最多 2 天 Jetson/OpenPLC 测试窗口**；超出默认算力的：**exp-22–25 使用非默认硬件，尚未获批**。S2 固定五个 seeds：`104729, 130363, 155921, 196613, 262147`，全部报告，不选 seed。开发 fixtures 与 held-out 架构已经分开；S1 smoke seed `7` 永不作为 claim 证据。

## 基础设施

- smoke test：**通过**。`data/config → zone/conduit compile → depth-1/2 attenuation → five-effect decision → 1D reachability → results/<run_id>/` 已贯通；8/8 单测通过。开发 run `s1_smoke_20260831_seed7` 中 8 个 decision fixtures 与预期 effect 全部一致，36 个区间包含检查和 200 个随机反例检查均为零违反。以上仅是 S1 bug check，不是 evidence。
- baseline 复现：SINT 固定 commit `2461a911b8c3d7ed9da3f7662b33678f688eb826`，源码 build 成功，工业 conformance 11/11 tests 通过。其代码内 T0 目标为 p99 < 1 ms；当前共享 AMD EPYC 主机单次 run 得到 16.6542 ms，未复现目标。该 run 未绑核、样本小且 reporter 重复输出，只作为方法学警报，不作为 SINT 性能结论。
- 其余 baseline：Lanotte/Merro 有公开 artifact，但需要 MATLAB/Simulink、NetFPGA/ModelSim 与多台 OpenPLC/Raspberry Pi；CPAC 与 PLC-ABAC 的出版页未找到可直接执行的完整 artifact。未在未经批准的硬件/许可条件下伪造“复现数字”，原因已登记在 NOTEBOOK/PLAN。
- 环境偏差：README 称 `casadi` 已安装，但当前 Python 环境中不可用；S1 采用可审计的精确一维区间运算，S2 若需多面体工具将在运行前固定依赖并记录。

## 需要你决定

- 是否接受已经显著收窄的 novelty：不再主张“physics-aware capability authorization”，只保留“IEC 62443 编译 + 句法衰减到物理行为的 refinement theorem + authority-preserving effects”。若不接受，应返回 S1，而不是进入大规模实现。
- 是否批准 S2 的 exp-22–25 使用一台 Jetson AGX Orin 级设备和一台 OpenPLC-capable PLC/Raspberry Pi，最长 2 天；若不批准，fallback 为隔离 x86 software-in-the-loop，并删除/改写 Jetson-specific C5。
- 若批准进入 S2_RUN，严格先跑 exp-01；C1 出现反例或只能得到 tautological theorem 时立即 early handoff 到 S3_REVIEW，不继续堆系统功能。
