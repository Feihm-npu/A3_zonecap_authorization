#!/usr/bin/env python3
"""Fake OpenPLC endpoint whose heartbeat is exactly periodic by construction.

Research-side review tool (see ``hardware_delivery/review_hardware_delivery_20261109.md``).
The heartbeat register %QW4 is computed from the clock, ``floor((now - t0) / period)``,
so the endpoint has no scheduler, no jitter, and no overrun: every late tick an
observer reports against it is produced by the observer.  A write to %QW0/%QW1 is
applied at the next scan boundary, the way the frozen ST program applies a new
``cmd_seq``, so ack polling behaves as it does against OpenPLC.

The endpoint speaks a minimal binary protocol to ``pymodbus_shim``, not Modbus/TCP::

    b"R" u16 address u16 count             -> count * u16
    b"W" u16 address u16 count count*u16   -> b"K"

One single-threaded selector loop, pinned to its own core, serves every connection,
so the endpoint adds no lock or GIL contention of its own.  It prints ``t0_ns`` at
start (CLOCK_MONOTONIC nanoseconds, the clock behind ``time.perf_counter_ns`` on
Linux), so true tick times ``t0 + n * period`` can be compared with any observer's
timestamps taken on the same host.
"""

from __future__ import annotations

import argparse
import os
import selectors
import socket
import struct
import time

REGISTERS = 8
CMD_SEQ, CMD_VALUE, ACK_SEQ, APPLIED_VALUE, HEARTBEAT, APPLIED_COUNT = range(6)


class PerfectPLC:
    def __init__(self, period_ns: int) -> None:
        self.period_ns = period_ns
        self.clock = time.perf_counter_ns
        self.t0 = self.clock()
        self.registers = [0] * REGISTERS
        self.pending: tuple[int, int, int] | None = None  # (visible_at_ns, seq, value)

    def _settle(self, now: int) -> None:
        if self.pending is not None and now >= self.pending[0]:
            _, seq, value = self.pending
            self.registers[ACK_SEQ] = seq
            self.registers[APPLIED_VALUE] = value
            self.registers[APPLIED_COUNT] = (self.registers[APPLIED_COUNT] + 1) & 0xFFFF
            self.pending = None
        self.registers[HEARTBEAT] = ((now - self.t0) // self.period_ns) & 0xFFFF

    def read(self, address: int, count: int) -> list[int]:
        self._settle(self.clock())
        return self.registers[address:address + count]

    def write(self, address: int, values: list[int]) -> None:
        now = self.clock()
        self._settle(now)
        self.registers[address:address + len(values)] = values
        if address == CMD_SEQ:
            next_boundary = self.t0 + ((now - self.t0) // self.period_ns + 1) * self.period_ns
            self.pending = (next_boundary, self.registers[CMD_SEQ], self.registers[CMD_VALUE])


def serve(plc: PerfectPLC, port: int) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(8)
    selector = selectors.DefaultSelector()
    selector.register(server, selectors.EVENT_READ)
    buffers: dict[socket.socket, bytes] = {}
    print(f"fakeplc ready port {port} period_ns {plc.period_ns} t0_ns {plc.t0}", flush=True)
    while True:
        for key, _ in selector.select():
            if key.fileobj is server:
                conn, _ = server.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                conn.setblocking(False)
                selector.register(conn, selectors.EVENT_READ)
                buffers[conn] = b""
                continue
            conn = key.fileobj
            try:
                data = conn.recv(4096)
            except ConnectionError:
                data = b""
            if not data:
                selector.unregister(conn)
                conn.close()
                buffers.pop(conn, None)
                continue
            pending = buffers[conn] + data
            while len(pending) >= 5:
                operation = pending[:1]
                address, count = struct.unpack_from("<HH", pending, 1)
                if operation == b"R":
                    pending = pending[5:]
                    conn.sendall(struct.pack(f"<{count}H", *plc.read(address, count)))
                    continue
                size = 5 + 2 * count
                if len(pending) < size:
                    break
                plc.write(address, list(struct.unpack_from(f"<{count}H", pending, 5)))
                pending = pending[size:]
                conn.sendall(b"K")
            buffers[conn] = pending


def main() -> None:
    parser = argparse.ArgumentParser(description="Fake OpenPLC endpoint with an exactly periodic heartbeat")
    parser.add_argument("--port", type=int, default=25020)
    parser.add_argument("--core", type=int, default=None, help="pin the endpoint to this CPU")
    parser.add_argument("--period-us", type=int, default=10_000)
    args = parser.parse_args()
    if args.core is not None:
        os.sched_setaffinity(0, {args.core})
    serve(PerfectPLC(args.period_us * 1_000), args.port)


if __name__ == "__main__":
    main()
