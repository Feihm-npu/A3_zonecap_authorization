#!/usr/bin/env python3
"""Idle control: run only the ``ScanMonitor`` of an e2e ``client.py`` while the main thread sleeps.

Writes the same statistics, computed the same way, as ``client.py`` writes to its
``<out>.scan_stats.json``, so the idle row is comparable with the loaded rows.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import threading
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an e2e ScanMonitor alone")
    parser.add_argument("--client", required=True, help="path to the e2e client.py under review")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--core", type=int, default=None)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.core is not None:
        os.sched_setaffinity(0, {args.core})

    spec = importlib.util.spec_from_file_location("client_under_review", args.client)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    from pymodbus.client import ModbusTcpClient

    modbus = ModbusTcpClient("127.0.0.1", port=args.port)
    modbus.connect()
    stop = threading.Event()
    monitor = client.ScanMonitor(modbus, stop, threading.Lock())
    monitor.start()
    time.sleep(args.seconds)
    stop.set()
    monitor.join()

    deltas = sorted(monitor.deltas)
    stats = {
        "mode": "idle: ScanMonitor alone, main thread sleeping",
        "observed_scans": len(deltas),
        "monitor_reads": monitor.reads,
        "observation_gaps": monitor.multi_jumps,
        "late_ticks_over_12ms": monitor.late_ticks,
        "scan_period_ns": {
            "min": deltas[0] if deltas else 0,
            "p50": deltas[len(deltas) // 2] if deltas else 0,
            "p99": deltas[min(len(deltas) - 1, int(0.99 * len(deltas)))] if deltas else 0,
            "max": deltas[-1] if deltas else 0,
            "mean": int(sum(deltas) / len(deltas)) if deltas else 0,
        },
    }
    Path(args.out).write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
