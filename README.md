# 小方向：ZoneCap（A3 · 跨 IEC 62443 zone 的可衰减能力授权 + 运行时强制语义）

**用途**：把"物理状态感知的命令仲裁"从**机制**提升为**授权语义**——统一 access-control 形式化（主体/客体/策略/PDP-PEP/委托/撤销/冲突）与 runtime-enforcement 形式化（edit automata / safety shield），并把 IEC 62443-3-2 的 zones & conduits 编译成**可衰减的能力**。

**判定**：🟡 **OPEN，但速度是关键**。

## 缝的来源
- **两个圈子互不引用**：access-control 圈与 runtime-enforcement 圈从不互相引用 → 统一无人做。
- **2024 USENIX SoK on PLCs (arXiv 2403.00280)** 的 "Authorization Enforcement" 类目下**只有一篇**（Gowdanakatte/Ray/Houmb, *ABAC Model for Protecting PLCs*, SAT-CPS@CODASPY 2022）。
- **CPAC (ACSAC 2016) 之后无后继**；McLaughlin 2020 后离场（转 TrustZone）；Ray 已休眠。
- 关键词 **"physics-aware access control" 未被占用**（dblp 上 "physics-aware security" 仅 1 条命中）。

## ⚠️ 头号竞争对手
**Roop / Pinisetty / Pearce / Baird（Auckland + IIT Bhubaneswar + NYU）——他们就在 TII / IEEE Access 上持续发这类工作**：
*Smart I/O Modules* (**IEEE TII 16(7), 2020**)、*Incremental Security Enforcement for CPS* (**IEEE Access 11, 2023**)、*Scalable Security Enforcement for CPS* (**IEEE Access 12, 2024**)、*Secure Function Blocks* (MEMOCODE 2025)。
**差异化**：他们做 enforcer 的**机制**（可扩展性、增量性、I/O 模块内实现）；我们做**授权语义**。

## 设计
- 能力**可衰减（attenuable）**：委托给子 agent 只能收缩不能扩张（macaroon/biscuit 式）。
- 能力绑定 **zone/conduit（IEC 62443-3-2）+ 资产 + 参数区间 + 时窗 + 工况模式 + 前置动作序列**。
- 撤销与冲突消解（多操作员 / 多 agent 并发持有能力）。
- 把 edit-automaton 的"编辑"升为策略一等公民：不只 allow/deny，还有 **attenuate / rewrite / defer**。

## 必须证的定理（把"macaroon 换域"变成真贡献的关键）
**能力衰减与物理安全包络的可组合性**：衰减后的能力集合所诱导的**物理可达集单调收缩**。

## 其它须引
Schneider 的 security automata、Ligatti 的 edit automata；shielded RL；SA4P *Sensing and Actuation as a Privilege* (AsiaCCS 2024)；Leander 等的 OPC UA 访问控制执行架构（ICSA'23 / ESORICS-W'23）——注意 Leander 的"动态上下文"是**生产配方/模块重构状态，不是物理工况**。

## 前置假设（先证伪）
能力衰减 → 物理可达集**单调收缩**的定理成立 —— 先在线性系统上证一维版本。

## Kill risks
① **Roop 组抢先**（同 venue）→ 速度。② 被说成"macaroon 换到工业域" → 靠上面的定理。③ 与 A2 抢 contribution → **A3 管"策略该是什么"，A2 管"任何策略在不可信状态下是否还成立"**。

## Venue
**IEEE TII 普通 issue** 主投 —— Roop 组主场也在这里（既是竞技场，也说明该刊 AE 熟悉这一领域）；10 页正好容下"单调性定理 + 62443 编译器 + OpenPLC 实测开销"三件套。TDSC / ACM TCPS 备选。

## 相关/交叉方向
`../A2_monitor_blindspot/`（A2）、`../A4_ot_command_capability/`（A4，本篇策略的密码学落地）。

---

# Stage-3 启动包（在本目录起 agent 时读这一节）

## 任务边界
**做**：本目录内的文献精读、建模/实现、实验、论文草稿。**不做**：不读其它方向目录；`../shared_testbed_IAST.md` 只读。
**上下文**：本 README + 本目录产出 + 按需 `../../../raw_materials/`。

## RQ 分解
| RQ | 问题 | 成功标准（可判定） | 失败即意味着 |
|---|---|---|---|
| **RQ1** | 能力衰减是否蕴含物理可达集单调收缩？ | 先在**一维线性系统**上给出并证明该命题；再推广到线性 MIMO | 定理不成立 → 退化为"macaroon 换域"，价值大降，**必须先做这条** |
| **RQ2** | 如何把 IEC 62443-3-2 的 zone/conduit 编译成能力？ | 给出编译器：`(zone, conduit, asset, 参数区间, 时窗, 工况, 前置序列) → 能力令牌`；对 ≥2 个 62443 参考架构可跑通 | 只剩概念，无系统贡献 |
| **RQ3** | edit-automaton 的 attenuate/rewrite/defer 能否成为策略一等公民？ | 给出四类判定（allow/deny/attenuate/defer）的语义，并证明与运行时强制语义**可组合**（组合后仍满足 RQ1 的单调性） | 与 Roop 组的 enforcer 工作无差异 |
| **RQ4** | 多 agent/多操作员并发持有能力时如何消解冲突？ | 给出撤销与冲突消解协议，并给出**无死锁/无越权**的证明或反例 | 落回单主体 RBAC |
| **RQ5** | 开销能否进入 OT 预算？ | 在 OpenPLC/Jetson 上实测策略决策延迟；给出与扫描周期的关系 | 工程可行性存疑 |

## 实验矩阵
- **因子 A 参考架构**：IEC 62443-3-2 的 2–3 个 zone/conduit 划分实例
- **因子 B 任务**：诊断 / 有界控制 / 维护模式切换 / 联锁旁路请求
- **因子 C 工况模式**：正常运行 / 维护 / 紧急（同一命令在三种模式下判定不同 —— 这是核心演示）
- **因子 D 委托深度**：0（直接）/1（子 agent）/2（多级）—— 验证衰减单调性
- **因子 E 对照**：静态 RBAC / ABAC-for-PLC (SAT-CPS'22) / CPAC 式策略引擎 / Roop 式 enforcer / **ZoneCap**
- **指标**：越权率、误阻率、决策延迟 p50/p99、扫描周期占用率、可达集体积（数值计算）

## 必跑基线
Gowdanakatte/Ray/Houmb *ABAC for PLC* (**SAT-CPS@CODASPY 2022**，SoK 里唯一的授权强制条目)｜CPAC (**ACSAC 2016**)｜Pearce *Smart I/O* (**IEEE TII 2020**)｜Baird *Scalable Security Enforcement* (**IEEE Access 2024**)｜Merro (**ACM TOPS 2023**)｜SA4P (**AsiaCCS 2024**)｜Leander OPC UA 执行架构 (ICSA'23 / ESORICS-W'23，注意其"动态"是生产配方状态不是物理工况)
理论侧必引：Schneider security automata、Ligatti edit automata、shielded RL。

## 数据与工具
OpenPLC v4 + `asyncua`（OPC UA 角色权限模型）+ `pymodbus`；策略引擎可选 OPA/Rego 或 Cedar 做对照；能力令牌用 macaroon/biscuit 参考实现；可达集用 `casadi`（已装）做数值计算。

## 里程碑与交付物
1. **W2**：`monotonicity_theorem.md` —— 一维版本的证明（**门控**）
2. **W4**：`zone_capability_compiler.py` + 62443 参考架构映射
3. **W6**：`edit_automaton_semantics.md` —— 四类判定 + 可组合性
4. **W8**：基线对照实验 + 开销实测
5. **W10**：论文草稿

## ⚠️ 速度警告
**Roop / Pinisetty / Pearce（Auckland）就在 TII / IEEE Access 持续发这条线。** 本方向的差异化只有"授权语义 + 单调性定理"，若定理拿不出来就与他们无异。**RQ1 是生死线，两周内必须有结论。**

## 明确不要做的事
- ❌ 不要做 enforcer 的性能/可扩展性优化（那是 Roop 组的地盘）
- ❌ 不要写成"Agent RBAC"（太 generic）
- ❌ 不要让策略元素来自不可信 RAG 上下文（那条已被 2607.04379 与 2606.28679 占）

## Venue
**IEEE TII 普通 issue** 主投。10 页版只留**单调性定理 + 62443 编译器 + OpenPLC 实测开销**三件套。
⚠️ **与最可能抢先的 Roop 组投同一刊**——好处是 AE 熟悉领域，风险是他们可能是审稿人；差异化陈述（授权语义 vs enforcer 机制）必须在摘要里就说清楚。TDSC / ACM TCPS 备选。

## 共享语料 raw_materials（所有子项目通用，重要）
本子项目**不复制论文数据**。原始论文与统计信息统一放在**项目根目录的 `raw_materials/`**：
- `raw_materials/TDSC/`、`raw_materials/TIFS/`、`raw_materials/top4/`：各 venue 的 `paper_table_*.md`、`research_report_*.md`、原始导出 CSV。
- 引用编号约定：`TDSC-[n]` → `raw_materials/TDSC/paper_table_TDSC.md`；`TIFS-[n]` → `raw_materials/TIFS/...`；`top4-[n]` → `raw_materials/top4/...`。

在本目录启动 agent 任务时：默认只读本目录内容；**需要查论文/统计时再去访问 `raw_materials/`**，不要读其它方向目录。

## 项目级规则
见根目录 `brainstorm_rules.md`。本方向完整核验报告见 `../brainstorm_round7_ai_industrial_journals.md`。

