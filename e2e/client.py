#!/usr/bin/env python3
"""ZoneCap C5 end-to-end client (single_host).

Replays the ``main`` corpus steps as commands against the wrapper (or directly
against OpenPLC in ``--bypass`` mode), releasing one command per 10 ms scan
window at a seeded uniformly random phase within the window.  The phase is
logged relative to the PLC scan start, estimated from the program's heartbeat
register (%QW4, incremented every scan) observed on the same loopback link.

Emitted-action pattern: with the wrapper, the wrapper's own decisions decide
which commands produce a PLC write.  In bypass mode the corpus EXPECTED effect
plays that role (allow/rewrite emit; deny/defer/attenuate do not), so the PLC
write load matches the instrumented run like-for-like, as Section 6 requires
for the overrun comparison.

One JSON line per command on stdout:
  cmd_id, step, expected_effect, emitted, phase_us, t_send, t_receipt,
  t_response, t_ack, t_modbus_done, plc_cmd_seq, ack_timeout
"""

from __future__ import annotations

import argparse
import json
import random
import socket
import struct
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from zonecap.c5 import corpus as corpus_mod  # noqa: E402
from zonecap.c5 import harness  # noqa: E402

REQ_MAGIC = b"ZCE2"
REQ_HDR = struct.Struct("<4sQII")
RESP_HDR = struct.Struct("<4sQBQII")
EMIT_EFFECTS = frozenset(("allow", "rewrite"))
HEARTBEAT_ADDR = 4
CMD_ADDR = 0
ACK_ADDR = 2
SLAVE_ID = 1


def encode_value(value: float) -> int:
    return max(0, min(65535, round(value * 100)))


class ScanMonitor(threading.Thread):
    """Tight-polls the heartbeat register and records scan boundaries.

    All Modbus transactions in this process are serialized through ``lock``
    (pymodbus clients are not safe for concurrent transactions on one socket).
    """

    def __init__(self, client: Any, stop: threading.Event, lock: threading.Lock) -> None:
        super().__init__(daemon=True)
        self.client = client
        self.stop = stop
        self.lock = lock
        self.last_value = -1
        self.last_boundary = 0
        self.reads = 0

    def run(self) -> None:
        clock = time.perf_counter_ns
        while not self.stop.is_set():
            with self.lock:
                value = self.client.read_holding_registers(
                    address=HEARTBEAT_ADDR, count=1, slave=SLAVE_ID).registers[0]
            now = clock()
            self.reads += 1
            if value != self.last_value:
                self.last_value = value
                self.last_boundary = now
            time.sleep(0.0005)


def snapshot_json(step: dict) -> bytes:
    context = step["context"]
    envelope = context["envelope"]
    snap = {
        "tick": context["tick"], "mode": context["mode"],
        "history": list(context["history"]), "complete": context["complete"],
        "high_risk": context["high_risk"],
        "envelope": None if envelope is None else [envelope[0], envelope[1]],
        "zd": step["request"]["zd"], "asset": step["request"]["a"],
    }
    return json.dumps(snap, separators=(",", ":")).encode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--e2e-config", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--measured", type=int, default=None)
    parser.add_argument("--bypass", action="store_true",
                        help="skip the wrapper; write the PLC directly")
    parser.add_argument("--wrapper-port", type=int, default=None)
    parser.add_argument("--pin-core", type=int, default=None)
    parser.add_argument("--out", default="-", help="jsonl output path ('-' stdout)")
    args = parser.parse_args()

    setting = json.loads(Path(args.e2e_config).read_text())
    warmup = args.warmup if args.warmup is not None else int(setting["warmup"])
    measured = args.measured if args.measured is not None else int(setting["measured"])
    period_ns = int(setting["scan_period_us"]) * 1_000

    core = args.pin_core if args.pin_core is not None else setting["cpu"]["monitor_core"]
    harness.pin(core)

    corpus_dir = Path(args.corpus_dir)
    corpus_mod.verify(corpus_dir)
    envelopes, steps = corpus_mod.load_variant(corpus_dir, setting["variant"])
    order = harness._order(steps, args.seed)
    positions = [order[index % len(order)] for index in range(warmup + measured)]

    from pymodbus.client import ModbusTcpClient

    modbus = ModbusTcpClient(setting["modbus"]["host"], port=int(setting["modbus"]["port"]))
    if not modbus.connect():
        raise RuntimeError("cannot connect to the OpenPLC Modbus slave")
    modbus_lock = threading.Lock()
    clock = time.perf_counter_ns

    bypass = args.bypass
    plc_seq = 0
    if bypass:
        # anchor the PLC-side sequence to the seed so every bypass repetition
        # starts from the same state
        plc_seq = args.seed & 0xFF or 1
        modbus.write_registers(address=CMD_ADDR, values=[0, 0], slave=SLAVE_ID)  # noqa (single-threaded here)
        time.sleep(0.02)

    monitor = ScanMonitor(modbus, threading.Event(), modbus_lock)
    if not bypass:
        monitor.start()
        # wait for the first observed boundary
        while monitor.last_boundary == 0:
            time.sleep(0.001)

    out = sys.stdout if args.out == "-" else open(args.out, "w", buffering=1)
    if bypass:
        rng = random.Random(args.seed)
        phases = [rng.uniform(0, period_ns) for _ in range(warmup + measured)]

    sock = None
    if not bypass:
        port = args.wrapper_port if args.wrapper_port is not None else int(setting["wrapper"]["port"])
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((setting["wrapper"]["host"], port))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    ack_timeouts = 0
    try:
        for cmd_id, step_index in enumerate(positions):
            step = steps[step_index]
            expected_effect = step["expected"][0]
            if bypass:
                emitted = expected_effect in EMIT_EFFECTS
            else:
                emitted = None  # decided by the wrapper; known after the response
            if not bypass:
                boundary = monitor.last_boundary
                # next window after the latest observed scan start
                k = (clock() - boundary) // period_ns + 1
                phase = random.Random((args.seed, cmd_id)).uniform(0, period_ns)
                target = boundary + k * period_ns + int(phase)
                while clock() < target:
                    pass
            else:
                boundary = clock()
                target = clock() + phases[cmd_id]
                while clock() < target:
                    pass
            phase_us = 0 if bypass else (clock() - boundary) / 1_000

            t_send = clock()
            if bypass:
                if emitted:
                    plc_seq = (plc_seq + 1) & 0xFFFF or 1
                    with modbus_lock:
                        modbus.write_registers(
                            address=CMD_ADDR,
                            values=[plc_seq, encode_value(float(step["expected"][2]))],
                            slave=SLAVE_ID)
                    t_modbus = clock()
                else:
                    t_modbus = t_send
                t_receipt = t_modbus
                t_response = t_modbus
                record = {
                    "cmd_id": cmd_id, "step": step_index,
                    "expected_effect": expected_effect, "emitted": 1 if emitted else 0,
                    "phase_us": phase_us, "t_send": t_send, "t_receipt": t_receipt,
                    "t_response": t_response, "t_modbus_done": t_modbus,
                    "plc_cmd_seq": plc_seq if emitted else 0, "ack_timeout": 0,
                }
            else:
                snap = snapshot_json(step)
                subject = step["subject"].encode("ascii")
                frame = REQ_HDR.pack(
                    REQ_MAGIC, cmd_id, len(envelopes[step_index]), 0) \
                    + envelopes[step_index] \
                    + struct.pack("<II", len(subject), len(snap)) + subject + snap
                sock.sendall(frame)
                header = bytearray()
                while len(header) < RESP_HDR.size:
                    chunk = sock.recv(RESP_HDR.size - len(header))
                    if not chunk:
                        raise ConnectionError("wrapper closed the link")
                    header.extend(chunk)
                magic, rid, emitted_u8, body_len, _ = RESP_HDR.unpack(header)
                body = bytearray()
                while len(body) < body_len:
                    chunk = sock.recv(body_len - len(body))
                    body.extend(chunk)
                t_response = clock()
                record = json.loads(bytes(body))
                record["t_send"] = t_send
                record["t_response"] = t_response
                record["expected_effect"] = expected_effect
                record["step"] = step_index
                record["phase_us"] = phase_us
                emitted = emitted_u8

            if record.get("emitted"):
                want = record["plc_cmd_seq"]
                t_ack = 0
                deadline = clock() + int(setting["ack_timeout_ms"]) * 1_000_000
                while clock() < deadline:
                    with modbus_lock:
                        ack = modbus.read_holding_registers(
                            address=ACK_ADDR, count=1, slave=SLAVE_ID).registers[0]
                    if ack == want:
                        t_ack = clock()
                        break
                record["t_ack"] = t_ack
                record["ack_timeout"] = 0 if t_ack else 1
                ack_timeouts += 0 if t_ack else 1
            else:
                record["t_ack"] = 0
                record["ack_timeout"] = 0
            out.write(json.dumps(record, separators=(",", ":")) + "\n")
    finally:
        if sock is not None:
            sock.close()
        if args.out != "-":
            out.close()
        sys.stderr.write(json.dumps({
            "commands": warmup + measured, "ack_timeouts": ack_timeouts,
            "monitor_reads": monitor.reads if not bypass else 0,
        }) + "\n")


if __name__ == "__main__":
    main()
