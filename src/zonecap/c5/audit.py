from __future__ import annotations

"""Bounded audit queue and its out-of-process drain.

The queue is a pipe whose capacity is fixed with ``F_SETPIPE_SZ``.  The PEP
writes each record with one non-blocking ``write`` (see ``PipeAuditSink``);
this module owns pipe creation and the drain process, which runs pinned to a
different core, persists records, and reports throughput and peak backlog.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import termios
import time
from typing import Any


DEFAULT_QUEUE_BYTES = 1_048_576


def open_queue(
    capacity_bytes: int = DEFAULT_QUEUE_BYTES, *, attempts: int = 30, delay_s: float = 1.0
) -> tuple[int, int, int]:
    """Return ``(read_fd, write_fd, granted_capacity_bytes)``.

    An unprivileged resize fails with ``EPERM`` while the user's pipe buffers
    exceed ``fs.pipe-user-pages-soft``.  Setup retries; it never shrinks the
    registered capacity.
    """

    for attempt in range(1, attempts + 1):
        read_fd, write_fd = os.pipe()
        try:
            granted = fcntl.fcntl(write_fd, fcntl.F_SETPIPE_SZ, capacity_bytes)
        except PermissionError:
            os.close(read_fd)
            os.close(write_fd)
            print(f"audit queue reservation refused (attempt {attempt}/{attempts})", file=sys.stderr)
            time.sleep(delay_s)
            continue
        return read_fd, write_fd, granted
    raise RuntimeError(
        f"kernel refused a {capacity_bytes}-byte audit queue; check fs.pipe-max-size and "
        "fs.pipe-user-pages-soft, or stop other pipe-heavy processes of this user"
    )


def start_drain(read_fd: int, output_path: Path, cpu_core: int | None) -> subprocess.Popen:
    command = [
        sys.executable,
        "-m",
        "zonecap.c5.audit",
        "--fd",
        str(read_fd),
        "--output",
        str(output_path),
    ]
    if cpu_core is not None:
        command.extend(["--cpu-core", str(cpu_core)])
    process = subprocess.Popen(command, pass_fds=(read_fd,), env=dict(os.environ))
    os.close(read_fd)
    return process


def finish_drain(process: subprocess.Popen, write_fd: int, output_path: Path) -> dict[str, Any]:
    os.close(write_fd)
    process.wait(timeout=120)
    if process.returncode != 0:
        raise RuntimeError(f"audit drain exited with {process.returncode}")
    summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _drain(read_fd: int, output_path: Path, cpu_core: int | None) -> dict[str, Any]:
    if cpu_core is not None:
        os.sched_setaffinity(0, {cpu_core})
    affinity = sorted(os.sched_getaffinity(0))
    records = 0
    total_bytes = 0
    peak_backlog = 0
    digest = hashlib.sha256()
    pending = bytearray(4)
    started = None
    finished = None
    with output_path.open("wb") as sink:
        while True:
            fcntl.ioctl(read_fd, termios.FIONREAD, pending)
            backlog = int.from_bytes(pending, sys.byteorder)
            peak_backlog = max(peak_backlog, backlog)
            chunk = os.read(read_fd, 65536)
            if not chunk:
                break
            if started is None:
                started = time.monotonic_ns()
            finished = time.monotonic_ns()
            sink.write(chunk)
            digest.update(chunk)
            records += chunk.count(b"\n")
            total_bytes += len(chunk)
    summary = {
        "records": records,
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
        "peak_backlog_bytes": peak_backlog,
        "active_ns": 0 if started is None else finished - started,
        "drain_affinity": affinity,
    }
    summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="C5 audit-queue drain process.")
    parser.add_argument("--fd", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-core", type=int)
    arguments = parser.parse_args()
    _drain(arguments.fd, arguments.output, arguments.cpu_core)


if __name__ == "__main__":
    main()
