#!/usr/bin/env python3
"""Reference scan observer: a separate process that polls the heartbeat and records every change.

It is the kind of observer the review asks for: its own process, core, and Modbus
connection, so no busy-wait, lock, or GIL in the client can delay it.  It pauses
0.5 ms between polls, as ``client.py``'s ``ScanMonitor`` does, so its request load
is about the same; keep that load identical in every mode and in the idle baseline.
On SIGTERM it writes one ``t_ns heartbeat`` line per observed change, the format
``summarize.py --observer-log`` reads.  It uses the pymodbus 3.16 call signatures
of ``e2e/``, so it runs against OpenPLC as well as against fakeplc.
"""

from __future__ import annotations

import argparse
import os
import signal
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Separate-process heartbeat observer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--core", type=int, default=None)
    parser.add_argument("--address", type=int, default=4, help="heartbeat holding register")
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--pause-us", type=int, default=500)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.core is not None:
        os.sched_setaffinity(0, {args.core})

    from pymodbus.client import ModbusTcpClient

    client = ModbusTcpClient(args.host, port=args.port)
    if not client.connect():
        raise RuntimeError(f"cannot connect to {args.host}:{args.port}")
    stopping = False

    def stop(signum: int, frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    clock = time.perf_counter_ns
    pause = args.pause_us / 1e6
    times: list[int] = []
    values: list[int] = []
    last = None
    while not stopping:
        value = client.read_holding_registers(
            address=args.address, count=1, device_id=args.device_id).registers[0]
        now = clock()
        if value != last:
            times.append(now)
            values.append(value)
            last = value
        time.sleep(pause)
    client.close()
    Path(args.out).write_text("".join(f"{t} {v}\n" for t, v in zip(times, values)), encoding="utf-8")


if __name__ == "__main__":
    main()
