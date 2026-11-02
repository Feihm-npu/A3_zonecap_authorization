from __future__ import annotations

"""Exp-23 revocation propagation: authority issuance to resolver visibility.

The authority (this process) and the resolver (a child process) run on the
same host, pinned to different non-benchmark cores, so both read the same
system-wide ``CLOCK_MONOTONIC``.  For each revocation the resolver first
confirms that it is polling, the authority waits a seeded 1-10 ms delay,
records ``t_issue`` immediately before ``SADD``, and the resolver records
``t_visible`` when its next ``SISMEMBER`` returns 1.  The delay is
``t_visible - t_issue``; its resolution is one resolver round trip.
"""

import argparse
from array import array
import gzip
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from .harness import distribution, write_json
from .resp import RespConnection


KEY = "zonecap:c5:propagation"


def resolver(host: str, port: int, core: int | None) -> None:
    if core is not None:
        os.sched_setaffinity(0, {core})
    connection = RespConnection(host, port)
    for line in sys.stdin:
        token_id = line.strip()
        if not token_id:
            break
        polls = 0
        print("ready", flush=True)
        while True:
            polls += 1
            if connection.command("SISMEMBER", KEY, token_id) == 1:
                print(f"{time.monotonic_ns()} {polls}", flush=True)
                break
    connection.close()


def measure(host: str, port: int, count: int, seed: int, authority_core: int | None,
            resolver_core: int | None, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    if authority_core is not None:
        os.sched_setaffinity(0, {authority_core})
    authority = RespConnection(host, port)
    authority.command("DEL", KEY)
    command = [sys.executable, "-m", "zonecap.c5.propagation", "--resolver", "--host", host,
               "--port", str(port)]
    if resolver_core is not None:
        command.extend(["--resolver-core", str(resolver_core)])
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                             env=dict(os.environ))
    rng = random.Random(seed)
    delays = array("Q")
    issue_calls = array("Q")
    polls = []
    for index in range(count):
        token_id = f"propagation:{seed}:{index:05d}"
        child.stdin.write(token_id + "\n")
        child.stdin.flush()
        if child.stdout.readline().strip() != "ready":
            raise RuntimeError("resolver did not confirm polling")
        time.sleep(rng.uniform(0.001, 0.010))
        issued = time.monotonic_ns()
        authority.command("SADD", KEY, token_id)
        returned = time.monotonic_ns()
        visible, poll_count = child.stdout.readline().split()
        delays.append(int(visible) - issued)
        issue_calls.append(returned - issued)
        polls.append(int(poll_count))
    child.stdin.write("\n")
    child.stdin.flush()
    child.wait(timeout=30)
    authority.command("DEL", KEY)
    (output_dir / "propagation_delay_ns.bin.gz").write_bytes(gzip.compress(delays.tobytes(), mtime=0))
    metrics = {
        "revocations": count,
        "seed": seed,
        "issuance_to_visibility_ns": distribution(delays),
        "issue_call_round_trip_ns": distribution(issue_calls),
        "resolver_polls_maximum": max(polls),
        "clock": "CLOCK_MONOTONIC on one host",
        "authority_core": authority_core,
        "resolver_core": resolver_core,
    }
    write_json(output_dir / "metrics.json", metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Revocation propagation timing.")
    parser.add_argument("--resolver", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--resolver-core", type=int)
    parser.add_argument("--authority-core", type=int)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output-dir", type=Path)
    arguments = parser.parse_args()
    if arguments.resolver:
        resolver(arguments.host, arguments.port, arguments.resolver_core)
        return
    metrics = measure(arguments.host, arguments.port, arguments.count, arguments.seed,
                      arguments.authority_core, arguments.resolver_core, arguments.output_dir)
    print(json.dumps(metrics["issuance_to_visibility_ns"], sort_keys=True))


if __name__ == "__main__":
    main()
