#!/usr/bin/env python3
"""ZoneCap C5 end-to-end server wrapper (single_host, secondary descriptive path).

Receives envelopes over a loopback TCP link (UNAUTHENTICATED transport -- this
must be stated in every report, per exp_requirements.md Section 6), publishes
the step's context snapshot (ingest), calls the unmodified
``zonecap.c5.pep.ReferencePEP.decide``, and forwards an emitted action to
OpenPLC over its Modbus slave (holding registers = the %QW image).

Emitted-action rule (frozen in e2e_config.json): effects ``allow`` and
``rewrite`` write ``(cmd_seq, value_u16)`` to %QW0/%QW1; ``deny``, ``defer``
and ``attenuate`` emit nothing.  The value is encoded as
``clamp(round(value * 100), 0, 65535)`` (centi-units).

Timed segments share one host clock (time.perf_counter_ns, CLOCK_MONOTONIC
based): t_receipt (frame complete), t_decide_start/stop (the same boundary the
matrix harness uses), t_modbus_done (FC16 write returned).  One JSON line per
command goes to stdout; the client correlates ids.

Runs inside the hardware group's e2e virtualenv (pynacl + pymodbus); the
system-under-test code path itself is unmodified.
"""

from __future__ import annotations

import argparse
import gc
import json
import socket
import struct
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from zonecap.c5 import audit as audit_queue  # noqa: E402
from zonecap.c5 import corpus as corpus_mod  # noqa: E402
from zonecap.c5 import harness  # noqa: E402
from zonecap.c5.pep import ContextSnapshot, ReferencePEP  # noqa: E402

REQ_MAGIC = b"ZCE2"
RESP_MAGIC = b"ZCD2"
REQ_HDR = struct.Struct("<4sQII")
RESP_HDR = struct.Struct("<4sQBQII")
EMIT_EFFECTS = frozenset(("allow", "rewrite"))


def encode_value(value: float) -> int:
    return max(0, min(65535, round(value * 100)))


class Wrapper:
    def __init__(self, args: argparse.Namespace) -> None:
        setting = json.loads(Path(args.e2e_config).read_text())
        corpus_dir = Path(args.corpus_dir)
        manifest = corpus_mod.verify(corpus_dir)
        if manifest["fingerprint"] != setting["corpus_fingerprint"]:
            raise RuntimeError("corpus fingerprint differs from the frozen e2e configuration")
        anchors = {
            issuer: bytes.fromhex(key)
            for issuer, key in json.loads((corpus_dir / "anchors.json").read_text()).items()
        }
        registry = harness.load_registry(corpus_dir, setting)
        revocation = harness.build_revocation(setting)
        self.context = ContextStore()
        options = harness.pep_options(setting)
        read_fd, write_fd, granted = audit_queue.open_queue(int(setting["audit_queue_bytes"]))
        if granted < int(setting["audit_queue_bytes"]):
            raise RuntimeError(f"audit queue capacity {granted} below the registered size")
        audit_queue.start_drain(read_fd, Path(args.audit_log), int(setting["cpu"]["audit_core"]))
        sink = audit_queue.PipeAuditSink(write_fd)
        self.pep = ReferencePEP(
            anchors=anchors, registry=registry, revocation=revocation,
            context=self.context, audit=sink, options=options,
        )
        self.publish = self.context.publish
        self.decide = self.pep.decide
        self.clock = time.perf_counter_ns
        self.setting = setting
        self.cmd_seq = 0
        self.modbus: Any = None
        self._modbus_connect()

    def _modbus_connect(self) -> None:
        from pymodbus.client import ModbusTcpClient

        host = self.setting["modbus"]["host"]
        port = int(self.setting["modbus"]["port"])
        self.modbus = ModbusTcpClient(host, port=port)
        if not self.modbus.connect():
            raise RuntimeError(f"cannot connect to the OpenPLC Modbus slave at {host}:{port}")

    def handle(self, payload: bytes) -> bytes:
        magic, cmd_id, env_len, _ = REQ_HDR.unpack_from(payload, 0)
        if magic != REQ_MAGIC:
            raise RuntimeError("bad frame magic")
        envelope = payload[REQ_HDR.size:REQ_HDR.size + env_len]
        tail = payload[REQ_HDR.size + env_len:]
        subj_len, snap_len = struct.unpack_from("<II", tail, 0)
        subject = tail[8:8 + subj_len].decode("ascii")
        snap = json.loads(tail[8 + subj_len:8 + subj_len + snap_len])
        snapshot = ContextSnapshot(
            tick=snap["tick"], mode=snap["mode"], history=tuple(snap["history"]),
            complete=snap["complete"], high_risk=snap["high_risk"],
            envelope=None if snap["envelope"] is None else tuple(snap["envelope"]),
        )
        t_receipt = self.clock()
        self.publish((snap["zd"], snap["asset"]), snapshot)
        t0 = self.clock()
        result = self.decide(subject, envelope)
        t1 = self.clock()
        effect, operation, value = result[0], result[1], result[2]
        reason, stage_mask, verified, hits = result[5], result[6], result[7], result[8]
        emitted = 0
        t_modbus = 0
        if effect in EMIT_EFFECTS:
            self.cmd_seq = (self.cmd_seq + 1) & 0xFFFF
            if self.cmd_seq == 0:
                self.cmd_seq = 1
            self.modbus.write_registers(
                address=0, values=[self.cmd_seq, encode_value(float(value))], slave=1)
            t_modbus = self.clock()
            emitted = 1
        record = {
            "cmd_id": cmd_id, "effect": effect, "operation": operation,
            "value": value, "reason": reason, "stage_mask": stage_mask,
            "signatures_verified": verified, "cache_hits": hits, "emitted": emitted,
            "plc_cmd_seq": self.cmd_seq if emitted else 0,
            "t_receipt": t_receipt, "t_decide_start": t0, "t_decide_stop": t1,
            "t_modbus_done": t_modbus,
        }
        body = json.dumps(record, separators=(",", ":")).encode("ascii")
        return RESP_HDR.pack(RESP_MAGIC, cmd_id, emitted, len(body), 0) + body


def recv_exactly(conn: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = conn.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("client closed the link")
        chunks.extend(chunk)
    return bytes(chunks)


def serve_forever(wrapper: Wrapper, host: str, port: int) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    sys.stderr.write(f"wrapper listening on {host}:{port}\n")
    sys.stderr.flush()
    while True:
        conn, _ = server.accept()
        try:
            while True:
                header = recv_exactly(conn, REQ_HDR.size)
                _, _, env_len, _ = REQ_HDR.unpack(header)
                tail = recv_exactly(conn, env_len + 8)
                subj_len, snap_len = struct.unpack_from("<II", tail, env_len)
                payload = header + tail + recv_exactly(conn, subj_len + snap_len)
                conn.sendall(wrapper.handle(payload))
        except (ConnectionError, OSError):
            conn.close()
            continue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--e2e-config", required=True)
    parser.add_argument("--listen-port", type=int, default=None)
    parser.add_argument("--audit-log", default="audit.log")
    parser.add_argument("--pin-core", type=int, default=None)
    args = parser.parse_args()

    setting = json.loads(Path(args.e2e_config).read_text())
    core = args.pin_core if args.pin_core is not None else setting["cpu"]["benchmark_core"]
    harness.pin(core)
    wrapper = Wrapper(args)
    gc.collect()
    gc.freeze()
    serve_forever(wrapper, setting["wrapper"]["host"],
                  args.listen_port if args.listen_port is not None else int(setting["wrapper"]["port"]))


if __name__ == "__main__":
    main()
