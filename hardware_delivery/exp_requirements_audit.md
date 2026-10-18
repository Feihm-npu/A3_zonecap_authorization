# 硬件实验需求审计（exp-22–25）

日期：2026-10-19
对象：`hardware_delivery/exp_requirements.md` v1.0（2026-09-02 交付硬件组）
对照：C5 原文、`research/PLAN.md` 中的 exp-22–26、S1 文档、`src/zonecap/` 实现、exp-26 结果
行号 `Lnn` 均指 `exp_requirements.md`。

C5 原文：

> On the approved OpenPLC/Jetson testbed, ZoneCap's p99 decision latency is at most 1 ms and consumes at most 10% of a 10 ms PLC scan cycle while enforcing the registered policy set.

## 结论

v1.0 的测量纪律是严谨的：按每次重复判定、保留原始纳秒样本、逐决策记录检查位、注入负对照、中止的尝试留档、不可执行的基线标 N/A。问题在于它没有定义要测的对象。计时路径上的核心组件在仓库里不存在，文档把它们交给硬件组去实现。此外还缺缓存规则和替代解释的判定标准，occupancy 判据也与时延判据同义反复。照 v1.0 执行，C5 无论通过还是失败，S3 都无法解读。

下面 B1–B4 应在硬件组冻结 harness 之前修正，发布为 v1.1。目前 `results/` 里没有任何 exp-22–25 的回传，现在修正成本最低。

## 阻断性问题

### B1. 被测系统没有定义，也没有实现

- **文档要求**：计时区包含序列化请求解析、完整 token/委托链校验、真实 Ed25519 验签、撤销查询、上下文查询，以及带背压的有界审计队列（L23、L167–173）；另外要报告根/深度 1/深度 2 token 的字节数（L188），每一层都是真实签名的 token（L266）。
- **仓库现状**：
  - `src/zonecap/models.py:53` 的 `Capability` 只是内存里的 dataclass，没有序列化格式、签名或委托链。
  - exp-26 的 "token_integrity" 只是对 26 字节常量做一次 SHA-256（`src/zonecap/exp26.py:122-123,172`）。
  - 撤销是 Python `set` 查找（`exp26.py:124,176`）。
  - 审计是 `deque(maxlen=2048)`，满了会静默丢掉最旧记录，没有背压（`exp26.py:125,206`）。
  - S1 只写了 "token verification"（`PLAN.md:34`），从未定义 token 格式或签名算法；Ed25519 是 v1.0 才引入的。
- **问题**：L80–82 允许硬件组 "implement the adapter/harness from this document"，但缺的不是 harness，而是被测系统本身。实现语言、加密库、token 编码、每条链要验几次签、验签结果能否缓存，这些选择基本决定 p99 能否 ≤1 ms。如果由硬件组在开跑前临时决定，C5 的结论就取决于一套未经研究侧冻结的工程设计。
- **建议**：研究侧交付规范和参考实现，内容包括：
  - token 编码，以及每层的 Ed25519 签名；
  - 链验证算法；
  - 撤销存储的结构和规模；
  - 上下文来源；
  - 审计队列容量和队列满时的行为（fail-closed）；
  - 实现语言、运行时和库的版本。

  参考实现附单元测试，并在 x86 上用同一 harness 做一次 development 运行。冻结后再交给硬件组，硬件组只负责平台适配和测量。

### B2. 缓存和"优化"规则缺失

- L237 规定 `cache_miss` 只 "invalidate only policy/token/context application caches"。言下之意，full 配置允许跨请求缓存这些结果，但文档没有规定哪些可以缓存。
- 如果 full 路径缓存了已验证的 token，而 100,000 次请求只复用少量 token，验签开销几乎会被全部摊掉，exp-22 实际上就不是每个请求都验签。这正是 C5 的替代解释 A1："The threshold is met only through warm caches or omitted signature/revocation checks."
- `PLAN.md:11` 要求报告 "exact decision agreement before/after optimization"，C5 的 false 判据也提到 "the optimized path"。但 v1.0 没有定义什么是优化、允许哪些优化。
- **建议**：预先写明 full 路径的缓存语义，在下面两种中二选一：
  - 不允许跨请求缓存验签结果；
  - 允许缓存不可变 token 的验签结果，但每次请求都查撤销和上下文，并把这一点作为可部署语义写进论文。

  同时规定计时语料中不同 token/委托链的数量，并定义允许的优化，以及"优化前后决策一致"如何检验。

### B3. 替代解释 A1/A2 没有判定标准

- CLAIMS 中 C5 的 A1 由 exp-23 排除，A2 由 exp-24 排除。但 v1.0 把 exp-23 全部写成 diagnostic（L235–246），exp-24 只要求报告（L268–269），都没有规定什么结果算排除了 A1/A2。
- 没有预注册判据，就只能看完结果再决定，这违反 AGENTS.md 中"先固定评估协议"的原则。
- **建议预注册**，例如：
  - A1 排除 ⇔ 5 个 seed 的 `cache_miss` p99 全部 ≤1,000 µs；或者按 B2 规定 full 路径不缓存验签。
  - A2 排除 ⇔ exp-24 中 1000 policies × depth 2 单元格的 5 个 seed，p99 全部 ≤1,000 µs。
  - 同时写清：A1/A2 未被排除时，C5 的结论如何降级表述。

### B4. occupancy 判据与时延判据同义反复

- L31–32 定义 occupancy = `p99_decision_us / 10,000 us * 100`。于是 "≤10%" 和 "p99 ≤1 ms" 是同一个条件，C5 的后半句没有得到独立检验。S1 只把 occupancy 列为指标（`PLAN.md:11`），没有定义；这个定义是 v1.0 引入的。
- 在首选的 `split_host` 拓扑下（L56），决策在 Jetson 上运行，根本不占 PLC 的扫描时间。真正与扫描周期相关的是两件事：端到端路径能否在一个扫描周期内完成，以及是否造成 overrun。§4.4 测了这些量，但它们不进入判定。
- **建议二选一**：
  - (a) 保留现有定义，但在需求文档和论文中写明 occupancy 是由 p99/10 ms 推出的比值，不是独立测量；同时把 §4.4 的端到端时延和 overrun 预注册为次要描述指标。
  - (b) 改用可测量的定义。例如在声明的请求速率下，取每个扫描周期内决策时间的总和；或者要求端到端 p99 不超过一个扫描周期，且不新增 overrun。(b) 会改变 C5 的可操作含义，需要记一条 deviation。

  我推荐 (a)：不动 C5 的陈述，只消除误导。

## 重要问题

### I1. 计时负载的构成没有规定

- exp-07 的单请求语料共 58,968 条：allow 4,536 条（7.7%），deny 45,360 条（76.9%），rewrite 9,072 条（15.4%）。DEFER 和 ATTENUATE 只出现在 exp-12 的组合轨迹里（见 `results/exp12_effect_automaton_20260901/metrics.json` 的 `corpus_effect_counts`）。
- 如果按 L155 循环 exp-07 语料，DEFER（上下文缺失/高风险）和 ATTENUATE（运行时包络）两条路径都不会被计时。
- **建议**：
  - 写明计时语料是哪一份：exp-07 单请求语料，还是 exp-12 的 81,648 步。
  - 按 effect 分层报告 p50/p99。
  - 规定 token/链的多样性和撤销表的规模，例如 0 / 1k / 100k 条。

### I2. 上下文来源的位置没有规定

- L170 把 "runtime-context lookup" 放进了计时区，但没说上下文（模式、物理历史）从哪里读：进程内存、Redis，还是 OpenPLC/OPC UA。
- 如果从 PLC 读，计时区就跨了网络，与 L22 的 "excludes client/network transit" 冲突。
- **建议**：明确上下文的提供者和位置。需要跨网络的读取归入端到端测量。

### I3. exp-25 两边的计时区不对等

- SINT 跑在 Node/TypeScript 上，ZoneCap 参考实现跑在 CPython 上（exp-26 环境为 Python 3.10.12）。
- v1.0 要求语料、顺序和亲和性一致（L273–275），但没有要求两边的计时区逐阶段对应，即解析、验签、撤销、审计这些阶段各自是否存在。
- **建议**：要求提交一张阶段对照表，缺失的阶段标 N/A，不直接比较总时延，并说明两边运行时的差异。

### I4. 撤销传播延迟的跨主机计时

- L248–249 要测 1,000 次撤销从签发到 resolver 可见的延迟。如果 authority 和 resolver 不在同一台主机上，同样需要 §4.4 的 PTP 或单时钟往返规则，但 v1.0 没有写。

### I5. 端到端测量的到达过程

- L196–205：命令若在随机时刻到达，"PEP→PLC 接收→应用" 会包含 0–10 ms 的扫描相位等待，并主导整个分布。
- **建议**：规定命令的到达过程（与扫描对齐，或随机相位），并逐条记录相位。

### I6. 运行时设置

- 若实现为 Python，应禁止仅为测量而关闭 GC 或改用其他不可部署的设置；如果可部署配置本身就这样做，需要如实记录。

## 次要问题

- `raw_samples_ns.bin.gz` 没有定义二进制格式，例如 little-endian uint64（L303）。
- `seeds.txt`（L299）与仓库惯例 `seed.txt` 不一致。
- "frozen held-out IEC 62443 policy tables"（L149）与 REVIEW 收窄后的措辞不一致。应改为"exp-07 冻结表（源文献拓扑 + 声明的 overlay）"。
- 因降频/节流而中止的条件（L118）缺少可操作的定义。例如以 tegrastats 显示频率低于锁定值，或出现节流标志为准。
- exp-23/24 各配置的执行顺序没有规定，热漂移可能混入结果。
- 签名私钥的生成和存放位置没有规定；私钥不应放在 PEP 上。

## 应保留的部分

- 按每次重复判定，不得挑选 seed（L28–37）。
- 保留原始纳秒样本，百分位用 nearest-rank（L139、L180–181）。
- 服务端时延与端到端时延分开报告（L24–26、L209）。
- 逐决策记录检查位，并注入 7 种负对照（L140、L352–364）。
- 中止的尝试留档，不被替换掉（L123–124）。
- 不同拓扑不混合（L62–63）。
- 用 Orin NX 替代 AGX 时不声称两者等价（L44–47）。
- 不可执行的基线标 N/A，不抄论文中的数字（L281–284）。
- 相对 SINT 加速超过 10 倍视为 bug 信号（L288–289）。

## 流程

- v1.0 交付已 47 天（2026-09-02 → 2026-10-19）。`results/` 下没有 exp-22–25 的目录，仓库里也没有提交过 harness 评审。v1.0 没有写联系人、评审负责人和截止日期。
- **若硬件组尚未冻结 harness**：按 B1–B4 发布 v1.1，成本最低。
- **若已冻结或已开始测量**：修订须记为 deviation。已有的测量按 v1.0 第 2.3 节归为 development，再在 v1.1 下重跑。
- 无论哪种情况，修订都应包括：v1.1 加 changelog；在 NOTEBOOK 记一条 `deviation`（在产生数据之前修订协议及其原因）；硬件组书面确认。
