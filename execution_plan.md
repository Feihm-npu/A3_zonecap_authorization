# ZoneCap C5 硬件实验执行计划（v1）

- 依据：`exp_requirements.md` v1.1（2026-11-02，冻结版）
- 角色：硬件组（执行 exp-22 ~ exp-25 + 端到端路径，返回数据包）
- 制定日期：2026-11-03，基于当日对板子的实测盘点
- 状态：**Phase 0 完成**（2026-11-03：仓库
  `https://github.com/Feihm-npu/A3_zonecap_authorization.git` 检出，
  建 `hardware-delivery` 分支，24/24 冻结哈希核验通过，合并由课题组负责）；
  拓扑已冻结 **single_host**；Phase 1 进行中
- 角色边界：仓库根的 `AGENTS.md`/`STATE.md` 是课题组研究循环
  （当前 `DONE`，C5 章节数字等硬件数据回填）；硬件组**不编辑**
  `research/*`、`STATE.md`，规程以 `hardware_delivery/exp_requirements.md` v1.1 为准

---

## 1. 项目理解（一页版）

**C5 注册主张**：在批准的 OpenPLC/Jetson 测试床上，ZoneCap PEP
（`zonecap.c5.pep.ReferencePEP.decide`）的 **p99 决策延迟 ≤ 1 ms**，
即 10 ms PLC 扫描周期占用的 **≤ 10%**（派生量），且**执行注册策略集**。

**计时区间**：`decide` 收到序列化 envelope 起 → 返回（审计入队成功）止，
覆盖全部 10 个阶段（parse → anchor → chain → signature → revocation →
context → policy → binding → response → audit）。排除网络、传输认证、
context 摄入、语料遍历、审计持久化。端到端路径（§6）单独测、单独报，
永不与服务器侧样本混合。

**判定规则（exp-22，§1.2）**：5 个种子重复**全部**满足 7 条 +
预检通过才算达标：p99 ≤ 1000 µs；派生占用 ≤ 10%；与独立 oracle 零不一致；
每个测量决策带完整十阶段激活掩码；签名验证数+缓存命中数 = 链长；
审计 drain 每决策恰一条记录且无 `audit_unavailable` 拒绝；无零/负样本。
- **A1 排除**（exp-23 `cache_miss`）：每次决策前清验证缓存 → 每个签名都真验。
- **A2 排除**（exp-24 千策略格子 `p1000_d{0,1,2}` 全过）。
- 规则由 harness 机械计算存入 `metrics.json` 的 `registered_checks`；解释权在研究方。

**四实验 + 端到端**：

| 实验 | 内容 | 规模/种子 | 预计时长（板端） |
|---|---|---|---|
| exp-22 | full path，`main` 语料（81,648 步，五种 effect） | 1 配置 × 5 种子 × (10k 预热 + 100k 测量) | ~10 min |
| exp-23 | 5 个诊断（cache_miss / cold_start / unsigned / remote_revocation / audit_disabled）+ Redis 撤销传播测量（1000 条） | 5 配置 × 5 种子 | ~30 min |
| exp-24 | 15 格子：`p{1,10,100,1000}_d{0,1,2}` full + `p1000_d{0,1,2}_cache_miss` | 15 配置 × 5 种子 | ~1 h |
| exp-25 | 对照 pinned SINT（Node.js 22+），`sint_subset`（27,216 步），3 配置（zonecap_full / zonecap_cache_miss / sint），同一子集同一顺序 | 3 配置 × 5 种子 | ~1–1.5 h |
| e2e（§6） | 硬件组自建 wrapper + client + 冻结 OpenPLC 程序（10 ms 任务），≥100k 命令/重复，随机相位，bypass 对照 | 自定 | 自定（大工程项） |

种子：`104729, 130363, 155921, 196613, 262147`；配置按 seed-major、
每种子轮转配置顺序（§5）。原始时序 = 小端 uint64 纳秒，gzip。
百分位用 nearest-rank（`ceil(p*N)`）。

**冻结边界（§2.11）**：SUT（PEP、wire format、语料、oracle、harness）
全部冻结，configs 存 SHA-256，harness 对不上哈希直接拒跑。
硬件组**只**可改：① configs 里的核号；② `ZONECAP_C5_SINT_REPO` 路径；
③ `ZONECAP_C5_REDIS_HOST/PORT`；④ 环境采集命令；⑤ §6 端到端三件套
（wrapper/client/OpenPLC 程序）。其他一切改动 = 偏差，须记录、可能作废运行。
**不得改** `research/PLAN.md`、`CLAIMS.md`、`NOTEBOOK.md`、`STATE.md`。

**过程纪律（§1.5, §8, §10）**：先 `--development` 干跑（全量规模）→
返回研究方评审 → 从评审过的干净提交跑确认性运行。每个重复都报告，
不得挑选/丢弃/静默重跑；中止的运行保留目录并记原因；
替换运行需记录基础设施原因。SINT 加速 >10x = bug 信号，先审计后解释。

---

## 2. 平台与环境盘点（2026-11-03 实测）

### 2.1 板卡身份澄清（重要）

用户口中的 "jetson nano" **实际是 Jetson Orin NX Engineering Reference
Developer Kit**（`ssh jetson` → `169.254.226.10`，直连网线，RTT ~0.6 ms）。
真 Nano 是上一轮 ScanCap H1/H2 项目（`~/llm-fei/jetsonNano/`）的目标板，
与本轮无关。**C5 需求 §4.1 批准的正是 Orin NX 8GB —— 当前板卡即为批准平台，
无硬件缺口。** 需在执行记录中按 §4.1 记录确切 SKU/载板/电源/散热（照片或
控制台截屏 + `/proc/device-tree/model` 等命令输出代替）。

### 2.2 环境核对表

| 项 | 要求 | 实测（2026-11-03） | 状态 |
|---|---|---|---|
| 板卡 | Orin NX 8GB DevKit | Orin NX ERDK，6×A78AE | ✅ |
| JetPack/L4T | 6.x / R36.x | R36.3.0（`nv_tegra_release`） | ✅ |
| 系统/Python | Ubuntu 22.04 / CPython 3.10.x | 22.04.5 / 3.10.12 | ✅ |
| PyNaCl | 1.5.0（自带 libsodium 1.0.18） | 系统 Python 已装 1.5.0 | ✅（仍按 Appendix B 建 venv） |
| `fs.pipe-max-size` | ≥ 1 MiB（审计队列） | 1,048,576 | ✅ |
| 核数/核号 | 默认表用到核 0–5 | 6 核，核 3 已 `isolcpus` 隔离 | ✅ 默认核号表可直接用 |
| 电源模式 | 固定持续性能模式 | MAXN（`nvpmodel -m 0`）+ `jetson_clocks` 锁频 1984 MHz 当前已生效 | ✅（**重启会丢，每阶段前重验**） |
| 内存/盘 | 语料 ~250 MB + 运行 | 7.4 GB RAM（可用 5.7 GB）/ NVMe 233 GB（余 169 GB） | ✅ |
| swap | **必须关** | ❌ **开启**：zram×6（各 635M）+ /swapfile 8G | ⛔ 测量前 `swapoff` |
| Redis | exp-23 remote_revocation + 传播测量 | ✅ 已装 6.0.16（系统服务停用，按注册命令手动拉起） | ✅ |
| Node.js 22+ | exp-25 SINT runner | ✅ v22.23.4 + npm 10.9.9（官方 arm64 tarball） | ✅ |
| SINT 仓库 | pinned commit `2461a911b8c3d7ed9da3f7662b33678f688eb826` | ✅ 构建/配置/x86 记录三方哈希一致（Nov 5 复核；Nov 3 报的"配置笔误"系我方手抄期望值时的转录错误，已正式撤回，见 F-1R） | ✅ |
| 交付代码 | `src/zonecap/c5/`、`configs/c5/`、`tests/test_c5_*.py`、`research/heldout/exp07/policy_tables.json`、`results/exp07_heldout_equivalence_20260901/cases.jsonl.gz`、`scripts/exp25_sint_runner.mjs` 等 | ✅ 2026-11-03 从 GitHub 检出（交付链 `23a68de`→`f7e164b`→`1be503b`），**24/24 冻结哈希核验通过** | ✅ |
| tegrastats | 1 Hz 采样 | 板上有 | ✅ |

### 2.3 板卡既有配置的处置决定（记入执行记录）

- **`isolcpus=3`（extlinux 既有）**：保留。默认核号表恰好把 benchmark worker
  放核 3（隔离核，OS 噪声最小），harness 自己显式绑核不受影响
  （注意 `nproc` 显示 5，非 6，属正常）。作为平台事实写入
  environment_manifest + 执行记录披露，不改 SUT。
- **`sched_rt_runtime_us`**：保持默认 950000。harness 只做亲和绑核
  （§4.4），不注册 SCHED_FIFO，不适用 chrt；RT 限流只影响实时任务。
  本机技能里 "-1" 的忠告仅适用于我们自己用 chrt 的测量——本轮不用。
- **sudo 经 `chrt`/锁频产生的 root 属主产物**：取回前 `chown -R fei:fei`。

---

## 3. 分阶段执行计划

### Phase 0 —— 获取并核验交付（阻塞，外部依赖）

1. 从研究方拿到交付（git 仓库 / patch / 归档，含全部冻结文件与 SHA-256）。
2. 在板子上建仓库目录（暂定 `~/zonecap-c5-repo`），或本机中转后
   `rsync`/`scp` 过直连网线。
3. 核验：交付自带 checksum 全对；`git status` 干净（确认性运行要求干净提交）。
4. **通过判据**：每个冻结文件 SHA-256 与交付清单一致（harness 之后也会自检）。

### Phase 1 —— 板端环境准备（~1 h，可与 Phase 0 并行）

```bash
# venv（Appendix B）
python3 -m venv ~/zonecap-c5 && . ~/zonecap-c5/bin/activate
pip install pynacl==1.5.0 pytest

# Redis 与 Node（板子 WiFi 可出网）
sudo apt update && sudo apt install -y redis-server
# Node.js 22+：NodeSource 或官方 tarball，node --version >= 22

# SINT（exp-25）：按交付包 exp-25 配置里的 prepare_command 准备，
# pinned commit 2461a911b8c3d7ed9da3f7662b33678f688eb826；不要猜仓库 URL。
#   export ZONECAP_C5_SINT_REPO=<交付指定的 checkout 路径>   # 写入运行脚本

# OpenPLC v4（single_host 拓扑，e2e 用）：部署在本板，
# 作为独立进程绑核 2（§2.11 默认核号表），安装方式在 Phase 3 定稿并随适配提交返回评审

# 电源/热/杂项（每次测量阶段前重验，重启后必丢锁频）
sudo nvpmodel -m 0 && sudo jetson_clocks
sudo swapoff -a && swapon --show   # 必须为空
sudo systemctl stop apt-daily.timer apt-daily-upgrade.timer fstrim.timer
```

- 板卡身份采集：`/proc/device-tree/model`、`nv_tegra_release`、`nvpmodel -q`、
  温区快照、`df -h`、`free -h`、电源/散热照片或截屏；记录常驻后台服务、
  环境温度（拿不到则记 N/A）。
- 拓扑已冻结（2026-11-03）：**single_host**，OpenPLC v4 与 PEP 同板分核；
  之后不可更换、不可混用（§4.2）。

### Phase 2 —— 语料与测试（板端，几分钟 + ~250 MB 盘）

```bash
PYTHONPATH=src python3 -m zonecap.c5.corpus build --output-dir build/c5_corpus
PYTHONPATH=src python3 -m pytest tests/test_c5_*.py
```

**通过判据**：语料指纹 =
`52971a47b69a6c252461570366cbe52234b7164dd66beb9b8da3a24568bb97ab`；
全部测试在板子上通过。

### Phase 3 —— 平台适配提交 + 端到端三件套（工程量主要在这）

1. **核号**：默认表（worker=3、drain=4、SINT=3+4、Redis=5、
   authority/resolver=1/4、tegrastats=1、OpenPLC single_host=2、OS=0）
   与本板 6 核 + isolcpus=3 相容，**预计零改动**；如有变化只改
   configs 核号并提交。
2. **环境采集命令**（§2.11 第 4 项）：把 §2.2/Phase 1 的采集命令加进
   各 config 的 `environment_commands`。
3. **端到端实现（§6，single_host，硬件组交付评审物）**：
   - **同板分核**：OpenPLC v4 独立进程绑核 2（§2.11 默认表），
     PEP wrapper 按基准核绑核（核 3），审计 drain 核 4，OS/中断核 0；
     同一主机 → 全部时戳共用 `CLOCK_MONOTONIC`，无需 PTP/往返测量；
   - **报告披露（强制）**：single_host 既未测独立 PLC、也未测网络跳，
     此声明必须出现在 e2e 报告里（§4.2）；
   - server wrapper：不改动 `ReferencePEP.decide`，收 envelope（本机回环传输，
     记录传输方式与是否认证——无认证可以，但必须声明）、发布该步 context
     快照（ingest）、调 `decide`、把 emitted action 转发 OpenPLC；
   - client：≥100k 命令/重复（同规模预热），10 ms 扫描周期内按种子随机相位
     释放命令；每条记录打相位戳（相对 PLC 扫描起点）；
   - 冻结 OpenPLC 程序：10 ms 周期任务；
   - 测量段：client 发送→PEP 收到 / PEP 决策时长（同 §1.1）/ 决策→OpenPLC
     收到 / 收到→应用或 ack / 总计；扫描周期分布 + 超期/漏扫计数；
   - bypass 对照：同一命令流再跑一遍（PEP 旁路），报告有无 ZoneCap 的 overrun；
   - 产物目录 `results/exp22_c5_e2e_<YYYYMMDD>/`（原始逐命令记录、config、
     命令、种子、环境、SHA-256 manifest）。
4. **通过判据**：适配提交完成；e2e 三件套 + 设计说明送研究方评审
   （确认性运行前必须返回评审，§6/§10）。

#### 3.1 e2e 具体设计（2026-11-05 定稿，送审材料）

**组件版本锁定**（全部记入 e2e config 与 environment manifest）：

| 组件 | 版本 | 位置 |
|---|---|---|
| OpenPLC Runtime | **v4.3.2**（git tag） | 板端原生安装（`install.sh --native`），绑核 2 |
| OpenPLC Editor | **v4.3.4**（AppImage，SHA-256 `b8186372…c75fa0`） | **仅主机侧**，无头 CLI 生成程序，不装板 |
| strucpp ABI | v0.4.5（runtime 镜像头） | 程序 zip 由 Editor 管线生成，无需手写 |
| modbus_slave 插件 | 随 runtime v4.3.2 | `127.0.0.1:5020`，pymodbus |

**冻结 OpenPLC 程序**（源码 + 生成的 program.zip 均入仓库、SHA-256 登记）：
- 生成路径（主机、完全可复现）：`openplc-cli create --from-json` 脚手架
  → ST 源码 → `openplc-cli compile <project> --target "OpenPLC Runtime v4"`
  （Editor CLI 与 GUI 走同一代码路径，`--ozone-platform=headless`）；
- 任务：`TASK task0(INTERVAL := T#10ms)`（周期写在程序里，随程序冻结）；
- ST 逻辑（寄存器经 Modbus Holding Registers ↔ int_output 映射）：
  `%QW0` cmd_seq、`%QW1` cmd_value（wrapper 写）；`%QW2` ack_seq、
  `%QW3` applied_value、`%QW4` heartbeat（每扫描 +1）、`%QW5` applied_count
  （程序写）。新 seq → 锁存 applied_value、回 ack_seq——
  "application/acknowledgement" 由 ack_seq 翻转定义，扫描活性由 heartbeat 观测。

**server wrapper**（不改动 `ReferencePEP.decide`）：
- 回环 TCP 收 envelope（**未认证传输，报告必须声明**）；发布该步
  context 快照（ingest）；调 `decide`；**仅当决策产生 emitted action**
  （ALLOW/REWRITE）时写 `%QW0/%QW1`（Modbus FC16）；DENY/DEFER/ATTENUATE
  不写 PLC（DEFER 的 read hold 不产生 PLC 写入）；
- 每条命令记录 `CLOCK_MONOTONIC` 时戳：client send、PEP receipt、
  decision start/stop、Modbus write 完成（OpenPLC receipt）、ack 观测、
  总计；未发射动作的命令记录到 decision 返回为止。

**client**：同一 main 语料、种子序（与 exp-22 同种子集）；每个 10 ms
扫描窗口内按种子均匀随机相位释放一条命令（≈100 Hz）；相位戳相对
PLC 扫描起点（heartbeat 寄存器观测推算）；≥10,000 预热 + ≥100,000
测量命令/重复。

**bypass 对照**：同一命令流、同相位过程，client 直写 Modbus（PEP 旁路），
报告有无 ZoneCap 的扫描 overrun 对比。

**扫描周期分布与 overrun**：runtime 自带 stats（每 5 s 记录
min/max/avg scan、cycle time、latency、overruns；经 `/api/runtime-logs`
采集）+ heartbeat 外部观测交叉验证；同板单时钟，无需 PTP。

**产物**：`results/exp22_c5_e2e_<YYYYMMDD>/`（逐命令原始记录 jsonl.gz、
config、command、seeds、environment、SHA-256 manifest），与服务器侧
样本**永不混合**；报告必须声明 single_host 既非独立 PLC 也无网络跳。

### Phase 4 —— 开发干跑（`--development`，全量规模）

```bash
# exp-23 前先起 Redis（注册命令原样）：
taskset -c 5 redis-server --port 6379 --save "" --appendonly no

PYTHONPATH=src python3 -m zonecap.c5.matrix --config configs/c5/exp22_c5_main.json \
    --corpus-dir build/c5_corpus --output-dir results/dev_exp22_c5_main_<YYYYMMDD> --development
# 同样跑 exp23 / exp24 / exp25 + e2e 开发运行
```

- 长任务脱离终端（直连网线 ssh 一抖就断）：
  `setsid nohup <cmd> > run.log 2>&1 < /dev/null &`，
  等待用一条阻塞远端 `while pgrep …; do sleep 20; done`。
- 每次运行前重验：锁频（cpu3 min=max=1984000）、swap 关、语料指纹。
- **通过判据**：preflight 全过、四实验目录 + e2e 目录完整、
  无未解释的中止；连同适配提交送研究方评审。

### Phase 5 —— 确认性运行（从评审过的干净提交）

- 顺序：exp-22 → exp-23（含 repetitions 之后的传播测量，
  此时无 benchmark worker 活动）→ exp-24 → exp-25 → e2e。
- 每配置 × 种子一个新进程；`results/` 下未跟踪目录允许，四实验可背靠背。
- Run ID：`exp22_c5_main_<YYYYMMDD>`、`exp23_c5_ablation_<YYYYMMDD>`、
  `exp24_c5_scaling_<YYYYMMDD>`、`exp25_c5_baselines_<YYYYMMDD>`、
  `exp22_c5_e2e_<YYYYMMDD>`。
- 纪律：exp-23 的 `full` 就是 exp-22，不得重跑替换；一切中止/无效重复
  保留并记录；降频中止规则由 harness 依据 tegrastats + 前后频率自动判。
- 检查表：§9 acceptance checklist 逐项核对（五种子五新进程、
  10k+100k、全掩码、15 格子、exp-25 三配置同序、e2e 数据分离等）。

### Phase 6 —— 打包返回

1. 四个 matrix 目录 + e2e 目录（含全部原始数据与 manifest）；
2. 平台适配 + e2e 三件套的一个 commit/patch；
3. 一页执行记录：每次中止/无效尝试、每个偏差（日期 + 原因）；
4. §4.3 的照片/截屏；
5. 传输归档的 SHA-256 checksum 文件。

---

## 4. 风险与注意清单

1. **交付缺失 = 全局阻塞**（已全盘搜索本机与板子，均无）。
2. **重启丢配置**：`jetson_clocks` 锁频重启即失效 → 降频中止规则会作废
   重复。每阶段前脚本化验证 `min==max==1984000`；swap 重启会回来，同样重验。
3. **swap 违规**：zram + swapfile 当前全开，忘记关 = 偏差。
4. **直连网线 ssh 脆弱**：两小时的活必须 `setsid nohup` 脱离；
   不要本机起轮询循环（OOM 风险），用阻塞远端等待。
5. **root 属主产物**：sudo/chrt 产物取回前先 chown。
6. **exp-25 工程依赖**：Node 22+、SINT pinned commit、`prepare_command`、
   `dist/` 树哈希校验——留足排障时间；SINT 毫秒级/决策，是时长大头。
7. **>10x 加速 = bug 信号**：先完成 §8 审计（逐阶段归因：
   `zonecap_cache_miss` vs `zonecap_full`、JS 签名验证 vs libsodium）
   再谈解释；开发干跑已超该比值，属预期。
8. **拓扑一旦冻结不可换、不可混**；Wi-Fi 禁止用于 e2e 链路。
9. **不得改** `research/PLAN.md`、`CLAIMS.md`、`NOTEBOOK.md`、`STATE.md`；
   解释权归研究方，harness 只机械产出 `registered_checks`。
10. **内存压力**：main 语料 + 110k 决策/进程，7.4 GB RAM 足够；
    exp-24 千策略格子额外 1000 根权限，仍在余量内；关注 RSS 分阶段记录。

---

## 5. 时间预算（板端计算，不含人审往返）

| 项 | 估计 |
|---|---|
| Phase 0 交付获取 | 外部依赖，不可控 |
| Phase 1 环境准备 | ~1 h |
| Phase 2 语料 + 测试 | 几分钟（~250 MB 盘） |
| Phase 3 e2e 实现 + 适配提交 | **0.5–2 天（最大不确定项）** |
| Phase 4 开发干跑（四实验 + e2e） | ~3–4 h 板端 + 检查 |
| 研究方评审窗口 | 外部依赖 |
| Phase 5 确认性运行 | ~3–4 h 板端（exp-22 10 min / exp-23 30 min / exp-24 1 h / exp-25 1–1.5 h / e2e 自定） |
| Phase 6 打包 | ~0.5 h |

---

## 6. 决定记录与发现

- **2026-11-03 板卡确认**：本机直连的即 Orin NX（批准平台）；
  "jetsonNano" 是上一轮 ScanCap 项目的命名惯性，本轮无关。
- **2026-11-03 拓扑冻结**：`single_host` —— OpenPLC v4 与 PEP 同板分核
  （OpenPLC 核 2）；报告必须声明该测量既非独立 PLC、也无网络跳（§4.2）。
  之后不可更换、不可混用。
- **2026-11-03 交付代码**：仓库 `github.com/Feihm-npu/A3_zonecap_authorization`
  （`main` @ `2dd5c0b`），硬件组在 `hardware-delivery` 分支工作，
  **合并由课题组负责**；SINT 按配置内 `sint.prepare_command`
  （clone sint-ai/sint-protocol → checkout `2461a91…` → pnpm build）准备。
- **2026-11-03 Phase 0 通过**：24/24 冻结文件 SHA-256 与 `configs/c5/*.json`
  登记值一致（含需求书引用的两个 exp-07 冻结输入）。
- **2026-11-03 Phase 1 完成**：venv（PyNaCl 1.5.0 + pytest）、Redis 6.0.16、
  Node v22.23.4、SINT 构建就绪；swap 已关（注意 `nvzramconfig.service`
  开机重建 zram，**每次重启后重跑 `swapoff -a`**）；MAXN + 核 3 锁频
  1984 MHz；apt/fstrim 定时器已停。板端仓库 `~/zonecap-c5-repo`
  （`hardware-delivery` @ `160361a`，干净树）。
- **2026-11-03 Phase 2 通过**：语料 45 s 构建完成，指纹
  `52971a47…97ab` 一致；`pytest tests/test_c5_*.py` 36/36 全绿（板端）。
- **2026-11-05 Phase 3/4（e2e）完成**：OpenPLC Runtime v4.3.2 原生安装并
  绑核 2；冻结程序经 Editor v4.3.4 无头 CLI 生成并上传（10ms 任务实测
  99.9 Hz）；wrapper/client/编排器就绪；e2e 全量干跑 5 种子全过（§3.2）。
  11 个开发运行目录（~400 MB）已回传主机 `results/`（按 §5 保持未跟踪，
  返回时归档 + SHA-256）。**全部开发干跑完成，具备送审条件。**

### F-1R（**撤回**，2026-11-05）：Nov 3 报告的"SINT dist 树哈希配置笔误"为误报

Nov 3 我报告 `configs/c5/exp25_c5_baselines.json` 登记的
`packages/policy-gateway/dist` 树哈希为 `…6d17bd…`、与实算 `…6d17cd…`
差一字符，判为冻结配置笔误并请求课题组修复。**2026-11-05 复核证明该
报告错误，正式撤回**：

- 配置文件（工作树与 Nov 3 基线 commit `2dd5c0b` 的 blob）登记的
  **从来都是 `…cd…`**；
- 全仓库检索 `6d17bd` **零命中**——该字符串只存在于我 Nov 3 验证脚本里
  **手抄的期望值**（及据其写成的本计划文件）。笔误出在我方转录，
  不在冻结配置；
- 板端三次构建（含强制干净重建）与课题组 x86 运行记录实算值均为
  `…cd…`，三方一致，**exp-25 从未被阻塞**。

教训（即刻生效）：验证脚本的期望值一律从源文件程序化读取，禁止手抄；
"63/64 位相同"这种形态本身就该先怀疑自己这端的抄写。
**对课题组的修复请求撤回：main 无需任何改动。**

### 开发干跑结果（2026-11-03，板端，`--development` 全量规模）

| 运行 | 时长 | 结果 |
|---|---|---|
| `dev_exp22_c5_main_20261103`（第 1 次） | 2.5 min | **中止（preflight）**：`pin(3)` 报 CPU 3 不可用——`isolcpus=3` 遗留配置把核 3 移出默认亲和掩码。目录按 §1.5 保留 |
| `dev_exp22_c5_main_20261103_r2` | 2.0 min | ✅ 五种子全过注册检查；p50≈92µs，p99≈259–261µs，占用≈2.6%，零不一致，每种子 100,000 样本（已独立复核计数） |
| `dev_exp23_c5_ablation_20261103` | 9.7 min | ✅ 25 重复 + 传播测量全过；cache_miss p99 590µs（**A1 排除成立**）、cold_start 291µs、unsigned 177µs、remote_revocation 352µs、audit_disabled 248µs |
| `dev_exp24_c5_scaling_20261103` | 25.6 min | ✅ 15 格子全过；p1000 全路径 p99：d0 93µs / d1 127µs / d2 159µs（**A2 在 1000 策略下排除成立**）；策略数 1→1000 影响 ≈5µs；cache_miss 每深度签名成本 ~130µs/令牌 |
| `dev_exp25_c5_baselines_20261105` | 24.9 min | ✅ 15/15 重复全过；p99：zonecap_full 154µs / cache_miss 471µs / sint 3071µs；**bug 信号归因**：同类可比（cache_miss vs sint，双方每请求验签）6.53x < 10x，成本差=JS @noble/ed25519 vs libsodium + zod；full 的 20.02x = 验证缓存收益（Δ≈317µs）叠加，与 x86 开发运行形态一致（§5 预期内，§8 审计归因已记录） |
| `dev_exp22_c5_main_20261103` | 2.5 min | **中止（preflight）**：isolcpus 遗留（见平台适配 1），目录按 §1.5 保留 |
| `dev_exp22_c5_e2e_20261105`（v3） | 3.4 h | ✅ 5 种子 × (instrumented + bypass) 全过；见 §3.1 结果摘要 |
| `dev_exp22_c5_e2e_20261105_shakeout1` | 3.4 h | 留档：第一轮试跑，暴露 bypass 未锚定 / 端点无统计，已修正（客户端无缺陷数据） |

#### 3.2 e2e 开发运行结果（`dev_exp22_c5_e2e_20261105`，v3，2026-11-05）

**instrumented（550,000 命令，5 种子）**：65.0–65.1/s；零 oracle 不一致、
零 ack 超时；total(send→ack) **p50 = 5.76 ms，p99 = 10.74 ms**（max ≤ 14 ms，
≤ 1.1 个扫描周期——扫描相位等待 0–10 ms 可分离）；decide 段（环内）
p50 = 140 µs / p99 = 312 µs；审计恰 110,000 条/种子（10k 预热 + 100k 测量）、
峰值积压 0 字节、drain 绑核 4。

**bypass（同一命令流、同锚定、含预热）**：total p50 = 5.53 ms / p99 = 10.45 ms。
**ZoneCap 端到端边际 ≈ +0.23 ms（p50）/ +0.29 ms（p99）**，且总数被扫描
节奏（0–10 ms 相位等待）支配。

**扫描周期分布（心跳外部观测）+ 空闲基线对照**：

| 场景 | 均值 | p50 | >12ms 迟到 tick |
|---|---|---|---|
| **空闲基线**（30 s，无任何客户端负载） | **10.00 ms** | 10.00 ms | **0.0%** |
| bypass 负载（Client 直写 PLC） | 10.13 ms | 10.33 ms | 20.1–20.3% |
| instrumented（PEP 在环） | 10.05 ms | 10.96 ms | 27.3–27.5% |

结论：runtime v4.3.2 调度器空闲时完美锁频 10 ms；负载下的"拉伸 + 追赶
突发"（p99 ≈ 21 ms、最大 22 ms、突发 0.8 ms、均值守恒）由 Python
modbus_slave 插件与调度器同核竞争引入；**ZoneCap 在环的边际 = 迟到比例
+7.3 pp（20.1%→27.4%），均值偏移 +0.08 ms**——无丢周期（追赶保持均值），
观测间隙 2.1–2.9% 单列不计 overrun。观测粒度（Modbus 轮询 ~0.7 ms）与
负载依赖均已披露。

### 平台适配记录（§2.11 之外的平台事实，写入执行记录）

1. **移除 `isolcpus=3`**（`/boot/extlinux/extlinux.conf` 主 APPEND 行，
   备份 `extlinux.conf.bak-pre-c5-20261103`，已重启生效）。原因：上轮
   ScanCap 项目的遗留配置使冻结 harness 的 `pin(3)` 失败（"requested
   CPU 3 is unavailable"）。移除后板卡恢复出厂 JetPack 形态（6 核默认
   掩码），注册命令逐字可跑；`/proc/cmdline` 逐重复采集留痕。
   `nohz_full=3 rcu_nocbs=3` 为该内核上的无效残留（未编
   `CONFIG_NO_HZ_FULL`），未动、在此注明。
2. swap：测量期 `swapoff -a`；`nvzramconfig.service` + `swapfile.swap`
   开机重建，**每次重启后须重跑**（已列入每阶段前检查）。
3. apt/fstrim 定时器 `systemctl disable --now`（§4.3 授权的"禁用计划任务"）。
4. Redis 常驻（绑核 5，注册命令拉起）；Node v22.23.4 官方 arm64 tarball
   装入 `/usr/local`；SINT 在 `/opt/zonecap/sint-protocol`（pinned commit）。
