# Review

日期：2026-09-02  
Reviewer 模型：OpenAI GPT-5 Codex  
类型：常规

## 总判断

完成的本地证据可以形成一项范围明确的方法贡献：把冻结的 zone/conduit 策略表编译为可衰减 capability，并在明示的 effect contract 下，把语法上的 attenuation 连接到物理 trace/reachable-set inclusion。C1 的条件定理可接受；核心 C2 的零 mismatch 结果可信度较高，但原表述会让读者误以为八个授权维度都直接来自 IEC 62443 案例，实际 action/parameter/time/mode/history 是统一的评测 overlay，因此必须缩窄。C3 也应限定为已注册的 actuation-event 语义。C4 的原命题被公平延迟调度下 8 次 issuance-relative stale execution 实质性反驳；C5 没有任何获批 Jetson/OpenPLC 测量。核心贡献不依赖 C4/C5，因此硬件组未回传不应阻止进入写作，但论文不得宣称原 C4 或 C5 已成立。

**建议：S4**，以 C1、缩窄后的 C2/C3 为主线，把 C4 写成边界/负结果，并暂时移除 C5 性能结论。硬件结果回传后只能经独立审计再补入。

## 逐条 claim

### C1 [core] "Under conjunctive ZoneCap caveats and authority-preserving runtime effects, if capability c' attenuates c, then for any fixed plant model, initial-state set, disturbance set, and finite horizon H, the physical reachable set induced by c' is a subset of that induced by c."

- 证据：`exp01_exact_1d_20260831` 在 `metrics.json` 中记录 8/8 proof obligations closed、393,750 个一维模型上的 2,756,250 次 exact horizon checks、0 inclusion violation；同时保留了 1 个不属于 C1 的 stronger same-request counterexample。`exp02_caveat_mutation_20260831` 杀死 14/14 unsafe mutants。`exp03_mimo_history_20260831` 完整报告五个预注册 seeds（104729、130363、155921、196613、262147），各 seed 的 MIMO 与 history violation 都为 0；合计 720 次 MIMO horizon checks、400 次 history horizon checks、8,854 次 child-trace membership checks，并检出 2/2 widening controls。`exp04_effect_closure_20260831` 在分别去掉 rewrite closure 与 defer/hold obligation 时得到 2 个 horizon-1 counterexamples，恢复后为 0 violation。`exp05_common_subset_20260901` 的 72 个 request pairs 与 63 个 adapter/plant/horizon checks 为 0 mismatch/violation；`exp06_c1_sanity_20260901` 的 9/9 预期模式一致。除 exp-03 外均为 seedless exact/proof runs，故无抽样方差可报。
- 替代解释：
  - A1（attenuation 被按 reachable set 语义定义而成为同义反复）：基本排除。`monotonicity_theorem.md` 先给出 field-wise syntactic order，exp-02 的 14/14 mutation kill 表明 checker 不是空的；但 parent realizability 本身是较强的 operational premise，论文必须显著陈述。
  - A2（仅因 scalar interval 成立）：在注册范围内由 exp-03 的 coupled MIMO/history checks 和两个 negative controls 排除；随机有限模型不是一般定理的依据，一般性来自归纳证明。
  - A3（仅因省略 REWRITE/DEFER）：由 exp-04 的 premise removal/restoration counterexamples 排除。
- baseline 公平性：三系统只比较共同可表达的 resource/action/upper-bound 子集，输入相同且无调参。SINT 使用固定 commit 的实际 token 行为；Dodson/CHERI 部分是 schema adapter，不是完整原系统执行，因此只支持语义边界，不能支持实现优越性或性能比较。
- 证据蕴含的范围：定理对任意固定 transition system 成立，但前提是 parent/child 使用相同 physical-history projection、plant、initial/disturbance sets，compiler 为 positive conjunctive monotone，child output 在 effective authority 内且 parent 能 realize child rewrite/hold。它不蕴含 same-request output inclusion、错误模型下安全、概率风险单调性或固定 tick adapter 的正确性。
- **判定：ACCEPT**；写作时必须把六项 proof obligations 和 actuation-event/idle 解释放在 claim 附近，不能只保留一句宽泛口号。
- 把握：中。归纳链条简洁、反例与 mutants 完整，但尚无 mechanized proof 或外部形式化复核。

### C2 [core] "For two held-out IEC 62443-aligned reference architectures, ZoneCap compilation is decision-equivalent to an independent zone/conduit policy oracle while every depth-1 and depth-2 delegation preserves or narrows zone, conduit, asset, action, parameter, time, mode, and pre-action-sequence authority."

- 证据：`exp07_heldout_equivalence_20260901` 的两个冻结案例分别有 42,120 与 16,848 cases，总计 58,968，其中 54,432 为单字段 mutations；compiler-oracle mismatch 为 0，84 条 delegation edges 上 672 次 dimension checks 的 failure 为 0。该 run 为 perfect result 执行了 hash、dependency separation、mutation 与 disabled-check audit。`exp08_source_generation_ablation_20260901` 中 generated corpus 杀死 10/10 check-removal mutants，六个 handwritten happy paths 杀死 0/10，4/4 source-provenance probes 通过。`exp09_depth_path_widening_20260901` 的 24 个 multi-conduit/depth cases 为 0 mismatch，32/32 widening attempts 被拒绝，672 次 legal checks 为 0 failure。`exp11_c2_sanity_20260901` 为 22/22。所有 run 都是 seedless 完整枚举，无抽样方差。
- 替代解释：
  - A1（fixtures 镜像 compiler）：由 exp-08 的 generated-versus-handwritten mutant 差异与四个 provenance probes 大幅削弱。
  - A2（未覆盖 delegation chain/cross-zone path）：由 exp-09 的 depth 0/1/2、两条 multi-conduit paths、八维 widening checks 排除。
  - 未列入原 claim、但仍存在：oracle 与 compiler 虽为独立代码，却共享同一份人工转写的 `policy_tables.json`；二者可同时忠实实现一个错误的 source interpretation。没有第二名盲法 encoder 或 OT/IEC 专家 adjudication。
- baseline 公平性：exp-10 对所有系统复用 58,968 cases，并只在各自 fully expressible subset 上判 mismatch，这一点公平；OPC UA role、PLC ABAC 是 functional projections，SINT 只执行其可表达 profile。40,824/18,144/28,728 个 full-policy unrestricted mutations 反映 schema coverage，不等同于相应真实产品的 false-allow rate，也不是端到端 baseline benchmark。
- 证据蕴含的范围：source-grounded 的只有 CPwE matrix 与 ENISA signalling 子图的 zone/conduit/topology。action、parameter、time、mode、pre-action-sequence 是统一的 source-independent overlay；ENISA 也只选取 landside signalling 子图。`unsupported_decision_constructs=0` 只针对编码后的 decision table，另有 7 个 nondecision metadata items 被排除。这些结果不构成 IEC 62443 certification，也不证明对任意 IEC architecture 可编译。
- **判定：NARROW → "For the frozen CPwE/CIP Security matrix and ENISA landside-signalling zone/conduit subgraph, augmented with the preregistered source-independent action, parameter, time, mode, and pre-action-sequence overlay, ZoneCap is decision-equivalent to the separate table oracle over the complete generated corpus, and every registered depth-1 and depth-2 delegation preserves or narrows all eight authority dimensions."**
- 把握：中高。完整 corpus、provenance probes、mutants 和 hash freeze 很强；主要不确定性是单人 source encoding 与标准外 overlay。

### C3 [S1] "A runtime enforcement semantics with ALLOW, DENY, ATTENUATE, REWRITE, and DEFER preserves C1 whenever rewrites remain within the effective capability and deferrals are modeled as parent-admissible stutter transitions."

- 证据：`exp12_effect_automaton_20260901` 覆盖 58,968 条 one-request traces 与 4,536 条五步 composed traces（22,680 composed policy steps），五种 effect 全部到达，authority-safety、parent-realizability、trace-inclusion、defer-stutter 与 bounded-deadlock violation 均为 0，且 5/5 negative mutants 被杀死。`exp13_deny_only_ablation_20260901` 在相同 81,648 policy steps 上保持 0 safety violation，但产生 13,608 false blocks，即全部 steps 的 16.67%、构造的 safe-service opportunities 的 60%，并失去 9,072 个 recoverable attenuation/defer decisions；3/3 mutants 被杀死。`exp14_exhaustive_sequences_20260901` 穷举 horizon 5、126 scopes 上的 492,156 words/492,030 transitions，覆盖 25 个 bigrams 与 125 个 trigrams，0 registered violations/deadlocks，3/3 sequence mutants 被检出。`exp16_effect_sanity_20260901` 为 5/5，并在单独绕过 rewrite membership 时恢复预期 counterexample。均为 seedless bounded/exact runs，无抽样方差。
- 替代解释：
  - A1（deny-only 足够）：exp-13 在相同构造 corpus 上排除“policy value 完全相同”；但 16.67%/60% 是该平衡评测语料的比例，不能外推为实际工厂 workload 的 prevalence 或收益。
  - A2（仅 hand-picked traces 安全）：exp-14 相对 named path 的 n-gram 与 mutant 差异在注册 horizon 内排除；不排除 horizon >5、异步分布式执行或连续时间语义的问题。
- baseline 公平性：deny-only ablation 使用同一请求与 context，公平。Lanotte/Roop 与 SINT 的 exp-15 是 source-grounded effect mapping：前者 3/5 exact，后者 2/5 exact、2/5 partial、1/5 absent；没有伪造未能运行的硬件结果。该比较只支撑机制差异，不能支撑吞吐、时延或总体系统优越性。
- 证据蕴含的范围：已证明/检查的是注册的 actuation-event semantics，其中 DENY/ATTENUATE 不推进物理 step，DEFER 只能发 parent-realizable hold。没有实现并验证 fixed-tick idle adapter，也没有处理 stale/malicious context、distributed approval/revocation 或 unbounded liveness。
- **判定：NARROW → "The registered actuation-event runtime semantics with ALLOW, DENY, ATTENUATE, REWRITE, and DEFER preserves C1 when every emitted rewrite and hold is within the effective capability and parent-realizable, and every deferral is a parent-admissible stutter transition."**
- 把握：中高。条件语义的证据链完整；实际系统边界仍比原句容易让读者理解的范围窄。

### C4 [S1] "ZoneCap revocation and deterministic conflict resolution prevent post-revocation execution, privilege union across concurrent holders, and deadlock in the preregistered bounded multi-principal model."

- 证据：`exp17_c4_interleavings_20260901` 穷举 bound 5 下 2--4 holders 的 793,800 words/793,797 transitions，含 26,038 executions、4,534 conflict resolutions 与 1,590 timeouts，所有 violation 为 0，4/4 mutants 被杀死。`exp18_c4_convergence_20260902` 闭合 depths 6/8/10 的 exact graphs，共 1,110 states、10,576 cycle edges，且 bound 5 以后仍有 461 个 states；delivered-state safety/deadlock violation 为 0，negative deadlock control 被检出。然而 `exp19_c4_adversarial_scheduler_20260902` 的 15 个固定公平 schedules 均完成 revocation delivery：delay 0 为 0 次 post-issuance execution，delay 1 与 2 各出现 4 次，共 8 次。`exp20_c4_sint_baseline_20260902` 的实际 pinned SINT modules 也在 delivery 前允许一次 stale use，并让一个已入队 revoked request 获批；fresh gateway recheck 才拒绝。所有 C4 runs 为 seedless exact/fixed schedule，无抽样方差。
- 替代解释：
  - A1（bound 5 隐藏更长 deadlock cycle）：对当前有限状态模型由 exp-18 exact graph closure 排除。
  - A2（依赖 benign centralized scheduler）：未排除，反而被 exp-19 支持。零 violation 只在 atomic delivered-state 或 FIFO delivery boundary 下成立。
- baseline 公平性：SINT 使用固定 commit 的真实模块并明确区分“approval”与“physical execution”，这是公平的语义审计。SINT 没有提供 ZoneCap 同构的跨请求 deterministic winner，不能因该项 `N/A` 判其失败；它只能佐证 freshness/integration boundary 是真实工程问题。
- 证据蕴含的范围：exp-17/18/19 支持“revocation 已原子送达 resolver 之后”的较窄 safety，以及 tuple ownership、固定 winner、bounded timeout progress。exp-19 的额外 issuer epoch fence 挡住 8/8 stale executions，但它是 diagnostic，不是预注册 protocol 的 confirmatory evidence。
- **判定：REJECT。** 原 claim 的预注册解释是 issuance-relative；8 个经 bug checks 保留的 counterexamples 已满足 false criterion。可把 delivered-state 结果写成 limitation 或另立 post-hoc claim，但不得改写原 `[S1]` statement 来掩盖反例。
- 把握：高。反例与 fairness/delivery checks 清晰，SINT 行为提供了独立工程一致性。

### C5 [S1] "On the approved OpenPLC/Jetson testbed, ZoneCap's p99 decision latency is at most 1 ms and consumes at most 10% of a 10 ms PLC scan cycle while enforcing the registered policy set."

- 证据：exp-22--25 没有结果。`exp26_c5_timer_sanity_20260902` 明确标记为 x86 infrastructure-only：100,000 个 timer pairs 的 empirical minimum 为 90 ns；empty/full/forced-slow p99 分别为 210 ns、19,326 ns、6,639,755 ns；CPU-0 affinity/restore 通过，6/6 disabled-check mutants 被检测，所有 raw samples 保留。该 run 是单次 seedless 本机 harness sanity，不是五次 fresh-process Jetson repetitions，也不测 OpenPLC path，所以不能用于 C5 threshold。
- 替代解释：
  - A1（只在 warm cache 或省略 signature/revocation checks 时快）：未排除；需要 exp-23。
  - A2（只在 toy policy count 时快）：未排除；需要 exp-24。
- baseline 公平性：没有 target-hardware baseline 数据。SINT/PLC ABAC/NGAC 若无可执行同环境实现必须保留 N/A，不能拿论文数字或 x86 数字横比。
- 证据蕴含的范围：仅说明当前 harness 能分辨时钟、强制慢路径、CPU pinning 和缺失 stage；不蕴含任何 Jetson latency、10 ms scan occupancy、throughput、memory 或优化前后 equivalence。
- **判定：INSUFFICIENT → 需要按 `hardware_delivery/exp_requirements.md` 回传并审计 exp-22 的五次 full-path repetitions、exp-23 ablations、exp-24 scaling matrix 与 exp-25 fair baselines/N/A。**
- 把握：高。缺失的正是 claim 指定平台上的主证据。

## 相对 S1 计划的偏离

- exp-07 的 source bytes 在 2026-09-01 才首次冻结，不是 S1 文字记载的 2026-08-31；Cisco CLI 返回 403 后，CPwE 同一指南改从 Rockwell Automation 官方镜像冻结。该动作发生在 encoding/execution 前，但日期与端点应在论文中披露。
- exp-07 的五个非 topology 维度采用 source-independent overlay；这不是运行中改 protocol，但必须限制 C2 的 standards-grounded 叙述。
- exp-15 因 academic-search MCP 不可用而使用注册的 DOI/arXiv/作者 preprint/raw pinned-code fallback，runtime metrics 保留 N/A。
- 获批硬件从 S1 的 AGX Orin-class 假设变成 Jetson Orin NX 8GB，且交由硬件组执行；不可声称两者等价。
- 在人工指令下先运行 exp-26，并以“本地子集完成”进入 review；exp-22--25 仍为 external pending。此偏离不污染 C1--C4，但使 C5 必然 insufficient。
- 所有证据仍标记 `[S1]`，没有把 exploratory result 晋升为支持性证据，也没有 post-hoc claim。C4 的 epoch-fence 仅为 diagnostic。

## Novelty

- 最接近的工作：
  - Dodson/CHERI Macaroons 已实现 CPS 中可构造、委托的物理资源 capabilities；[TR-963](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-963.html) 与 [EuroS&PW 2020 paper](https://doi.org/10.1109/EuroSPW51379.2020.00099) 已占据“capabilities for CPS”。
  - [CPAC](https://doi.org/10.1145/2991079.2991126) 已占据 physical-model-derived access control；[Lanotte et al.](https://doi.org/10.1145/3546579) 与 [Baird et al.](https://doi.org/10.1109/ACCESS.2024.3357714) 已占据可纠正/抑制物理事件的 runtime enforcement 与 scalable composition。
  - 2026-05 的 [ZTPM](https://arxiv.org/abs/2605.25653) 已提出 agentic CPS 的 Physical Impact Tiers 和 typed runtime policy；SINT v0.2 已提供签名 capability、attenuation、physical constraints、revocation 与 approvals，是最接近的工程竞争者。
  - S1 未列出的 2026-08 [DARC](https://doi.org/10.21203/rs.3.rs-10533072/v1) 已提出 delegation-aware runtime contracts、capability attenuation、revocation closure 与 formal guarantees；它显著压缩“一般 agent delegation contract”的新颖性，但对象是 open LLM multi-agent IO，不包含 IEC zone/conduit compiler 或 physical reachable-set theorem。
  - [Safety-security convergence: Automation of IEC 62443-3-2](https://doi.org/10.1016/j.cose.2025.104477) 已自动化 IEC 62443-3-2 风险评估；[IEC 62443-oriented DSL](https://doi.org/10.1145/3664476.3670938) 已形式化 zone/conduit 建模；2026 的 [zones/conduits article](https://doi.org/10.3390/jcp6020052) 进一步细化 conduit 实施。它们都限制“首次自动化/形式化 IEC 62443”的说法。
  - [TwinGridShield](https://doi.org/10.2139/ssrn.7290820) 已展示 consequence-aware pre-execution authorization，并明确量化 model mismatch 下 unsafe acceptance；这加强了本项目必须把 trusted/correct plant/context model 写成威胁模型边界，而非隐藏假设。
- delta 是否成立：在本次 Crossref/OpenAlex、arXiv、作者/项目官方页面与 DOI primary-source 检索中，尚未找到同时给出“冻结的 IEC 62443 zone/conduit policy → attenuable capability compiler”、“syntactic attenuation → physical trace/reachable-set refinement”及“五 effect authority-preserving semantics”的工作。因此缩窄后的组合 delta 仍成立，类型是 method + formal finding，不是“首个 physics-aware access control”或“首个 CPS capability”。由于标准 web-search 接口认证失效，本次改用公开索引 API 与 primary-source 页面；对 2026 最新预印本的检索完整性把握仅为中等。

## 红旗

- 多个 run 在大规模枚举上均为 0 violation/perfect agreement。mutants、negative controls、raw hashes 和 too-good audits 降低了 disabled-check/leakage 风险，但不能排除共享 specification/encoding error。
- C1 的 universal language 来自一个人工书写的条件证明，不是由百万级测试外推；若稿件把测试规模当作 theorem 的依据，会被拒稿。
- C2 的 oracle/code independence 不等于 source interpretation independence；统一 overlay 与 ENISA 子图选择必须显式披露。
- C3 的 60% safe-service figure 是构造 corpus 比例，不是现实效益估计。
- C4 原命题已被反驳。任何只报告 exp-17/18 零违例而弱化 exp-19 的写法都属于选择性报告。
- C5 完全缺少 claim 平台证据；exp-26 的 19.326 us p99 很容易被误写成 C5 成功，必须禁止。
- baseline 多为 common-subset projection 或 source mapping；没有公平的端到端性能或部署复杂度比较。

## 若回 S2_RUN，补充实验

1. 目的：排除 C2 的共享人工转写错误。设计：由第二名不看现有 `policy_tables.json` 的编码者，根据冻结 PDF 盲法重建 zone/conduit grants；预先固定 disagreement adjudication，再生成 fresh corpus 复核。预计成本：1--2 人日 + 2 CPU-h。
2. 目的：把 C4 的负结果转化为可支持的新 revocation claim。设计：先冻结 issuer epoch/fresh gateway recheck contract，再在 fresh exact schedules 上覆盖 delay 0--2、queued approvals、conflicts 和 duplicate delivery；新增 claim 必须标 `[post-hoc: review]`，原 C4 保持 rejected/superseded。预计成本：4--6 CPU-h。
3. 目的：完成 C5。设计：按已交付文档执行 exp-22--25，先回传 hardware harness/config/OpenPLC patch 做 clean freeze，再运行五次 fresh processes 并回传 raw nanosecond samples、tegrastats、environment 与 manifests。预计成本：2 hardware-days；不应阻塞当前 S4 主线。
4. 目的：提高 C1 的形式化可信度。设计：把 Lemma 1、Lemma 2 和 finite-horizon induction 机械化，并把 parent realizability/hold premise 做成显式 type/interface obligation。预计成本：2--4 人日；属于强化项，不是当前进入 S4 的必要条件。

## 需要你决定

- 是否接受：C1 `ACCEPT`；C2/C3 按上述文字 `NARROW`；C4 `REJECT`；C5 `INSUFFICIENT`。
- 是否按建议立即进入 S4，以 C1 + narrowed C2/C3 为主线，并把 C4 作为负结果、C5 暂不进入结论。
- 硬件结果回传后，是作为补充性能证据进入一次受控 patch，还是保持 C5 完全出稿外。
