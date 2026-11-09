# review_tools：e2e 扫描观测方法的检查与校准

研究方审阅工具，配合 `../review_hardware_delivery_20261109.md` 使用。核心是一个**周期绝对精确的假 PLC**：
心跳寄存器的值直接由时钟算出，`floor((now - t0) / 10 ms)`，没有调度器、抖动或超期。
拿任何观测方法去测它，报出来的"迟到 tick"和相位误差都只能来自观测者自己。

| 文件 | 作用 |
|---|---|
| `fakeplc.py` | 假 PLC。寄存器布局与冻结 ST 程序一致：%QW0 cmd_seq … %QW5 applied_count；写入的命令在下一个扫描边界被 ack。单线程 selector、绑核，启动时打印 `t0_ns` |
| `pymodbus_shim/pymodbus/` | pymodbus 的轻量替身，只实现 `e2e/` 用到的 `connect`、`read_holding_registers`、`write_registers`，与 `fakeplc.py` 通信。**它会遮蔽真正的 pymodbus，只能在本检查里放上 `PYTHONPATH`，绝不能出现在测量运行里。** 每次调用的 Python 开销比真实 pymodbus 小，所以测出的饥饿只会偏轻 |
| `idle_monitor.py` | 空闲对照：只运行被审 `client.py` 的 `ScanMonitor`，主线程睡眠 |
| `reference_observer.py` | 参考观测者：独立进程、独立核、独立连接，轮询间隔同为 0.5 ms，记录每次心跳变化的 `t_ns heartbeat`。审阅要求的观测方式；用的是 pymodbus 3.16 的调用签名，也能直接对真实 OpenPLC 使用 |
| `observer_check.sh` | 一键运行：空闲、bypass、instrumented 三种模式。被审的 `client.py`/`wrapper.py` 原样运行，冻结 PEP 在环；参考观测者在每种模式下同时运行 |
| `summarize.py` | 汇总：观测到的扫描周期统计，记录相位对比真实相位的误差，参考观测者的观测滞后 |
| `evidence_20261109/` | 研究方 2026-11-09 在 x86 开发机上对 `841914f` 的运行输出，附 `SHA256SUMS` |

## 运行

在含 `e2e/` 的检出根目录运行（例如 `hardware-delivery` 合并 main 之后），需要已构建的语料：

```bash
PYTHON=~/zonecap-c5-e2e/bin/python OUT_DIR=build/observer_check_$(date +%Y%m%d) \
  hardware_delivery/review_tools/observer_check.sh
```

- 解释器必须是 CPython 3.10 并装有 PyNaCl 1.5.0。`client.py:189` 用元组给 `random.Random` 做种子，3.11 起会直接报错。
- 默认核号按 Jetson single_host 布局：client 1、fakeplc 2、wrapper 3、audit drain 4、参考观测者 5。可用
  `CLIENT_CORE`、`PLC_CORE`、`WRAPPER_CORE`、`AUDIT_CORE`、`OBSERVER_CORE` 覆盖。
- 端口默认用 25020/28600，与 OpenPLC 的 5020 不冲突。但核 2 和 OpenPLC 共用，在板上运行时请先停掉 `openplc-runtime`，或者把 `PLC_CORE` 换到别的核，并且只在没有测量进行时运行。
- 每个负载模式默认 3,000 条命令（`COMMANDS`），整个检查约 3 分钟。

## 用它校准新的观测方法

新的观测者正式使用前，先在**完整客户端负载下**对 `fakeplc.py` 做校准，标准如下：

- 迟到 tick（>12 ms）接近 0%，观测间隙接近 0%；
- 观测滞后的 p99 不超过一次轮询加往返（研究方的参考观测者约 0.65 ms）；
- 事后计算出的每条命令相位，与真实相位 `(t_send - t0) mod 10 ms` 的误差在同一量级。

如果新观测者能输出 `t_ns heartbeat` 原始序列（`time.perf_counter_ns`，每行一对，可 gzip），用
`summarize.py <OUT_DIR> --observer-log <文件>` 就能得到同样的指标。把校准输出放进对应的 e2e 运行目录。
