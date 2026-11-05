#!/usr/bin/env python3
"""ZoneCap C5 end-to-end orchestrator (Section 6 path, single_host).

Per repetition: starts the wrapper (pinned benchmark core), runs the client
(warm-up + measured commands, seeded random phase per scan window), then the
bypass run of the same command stream with the PEP bypassed, and collects the
OpenPLC runtime logs (scan statistics and overruns), tegrastats, the wrapper
audit log, and the environment capture into an immutable result directory:

    results/exp22_c5_e2e_<YYYYMMDD>/
      config.json  command.txt  seed.txt  log.txt
      environment_manifest.json  manifest.json
      repetitions/<seed>.log
      repetitions/<seed>/metrics.json  client_records.jsonl.gz
      bypass/<seed>/client_records.jsonl.gz
      openplc_runtime_logs.txt  tegrastats.log  [audit.log + summary]

Server-side decision samples are NOT pooled with the matrix runs; this
directory is returned separately (exp_requirements.md Section 6/7).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUN_TEMPLATE = "exp22_c5_e2e_{date}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", default="build/c5_corpus")
    parser.add_argument("--e2e-config", default="e2e/e2e_config.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seeds", default=None, help="comma list; default from config")
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--measured", type=int, default=None)
    parser.add_argument("--python", default=sys.executable,
                        help="interpreter for wrapper/client (e2e venv)")
    args = parser.parse_args()

    repo = REPO
    setting = json.loads(Path(args.e2e_config).read_text())
    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else setting["seeds"]
    warmup = args.warmup if args.warmup is not None else int(setting["warmup"])
    measured = args.measured if args.measured is not None else int(setting["measured"])
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=False)

    (out_dir / "config.json").write_text(json.dumps(setting, indent=2) + "\n")
    (out_dir / "seed.txt").write_text("\n".join(str(s) for s in seeds) + "\n")
    log_lines: list[str] = []

    def log(message: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{stamp} {message}"
        log_lines.append(line)
        print(line, flush=True)

    # environment capture (same commands the matrix configs record, plus the
    # OpenPLC facts specific to this path)
    env_commands = [
        "date -u +%Y-%m-%dT%H:%M:%SZ", "uname -a",
        "cat /etc/nv_tegra_release | head -1", "cat /proc/device-tree/model",
        "nvpmodel -q | head -2", "cat /proc/cmdline",
        "for c in /sys/devices/system/cpu/cpu[0-9]*; do echo $c $(cat $c/cpufreq/scaling_cur_freq); done",
        "swapon --show", "free -m", "df -h .",
        "python3 --version",
        "systemctl show openplc-runtime -p CPUAffinity,MainPID,ActiveState",
        "git -C /opt/zonecap/openplc-runtime-v4.3.2 rev-parse HEAD",
        "sha256sum /opt/zonecap/openplc-runtime-v4.3.2/build/libplc_*.so | head -2",
    ]
    env_out: dict[str, str] = {}
    for command in env_commands:
        done = subprocess.run(command, shell=True, capture_output=True, text=True)
        env_out[command] = done.stdout.strip() + done.stderr.strip()
    (out_dir / "environment_manifest.json").write_text(
        json.dumps({"environment_commands": env_out}, indent=2) + "\n")

    python = args.python
    for seed in seeds:
        rep_dir = out_dir / "repetitions" / str(seed)
        byp_dir = out_dir / "bypass" / str(seed)
        rep_dir.mkdir(parents=True)
        byp_dir.mkdir(parents=True)
        log(f"seed {seed}: starting wrapper")

        wrapper_cmd = [
            python, str(repo / "e2e" / "wrapper.py"),
            "--corpus-dir", args.corpus_dir, "--e2e-config", args.e2e_config,
            "--audit-log", str(rep_dir / "audit.log"),
        ]
        wrapper_env = dict(os.environ, PYTHONPATH=str(repo / "src"))
        tegrastats = subprocess.Popen(
            ["tegrastats", "--interval", "1000"],
            stdout=open(rep_dir / "tegrastats.log", "w"), stderr=subprocess.DEVNULL)
        wrapper = subprocess.Popen(
            wrapper_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            env=wrapper_env)
        ready = False
        deadline = time.time() + 120
        while time.time() < deadline:
            line = wrapper.stderr.readline().decode(errors="replace") if wrapper.stderr else ""
            if "wrapper listening" in line:
                ready = True
                break
            if wrapper.poll() is not None:
                break
        if not ready:
            log(f"seed {seed}: wrapper failed to start; aborting repetition")
            tegrastats.terminate()
            (rep_dir / "wrapper.log").write_text(
                wrapper.stderr.read().decode(errors="replace") if wrapper.stderr else "")
            continue

        try:
            client_cmd = [
                python, str(repo / "e2e" / "client.py"),
                "--corpus-dir", args.corpus_dir, "--e2e-config", args.e2e_config,
                "--seed", str(seed), "--warmup", str(warmup), "--measured", str(measured),
                "--out", str(rep_dir / "client_records.jsonl"),
            ]
            started = time.time()
            done = subprocess.run(client_cmd, capture_output=True, text=True,
                                  env=wrapper_env)
            seconds = time.time() - started
            (rep_dir / "client.log").write_text(done.stderr)
            with gzip.open(rep_dir / "client_records.jsonl.gz", "wb") as sink:
                sink.write((rep_dir / "client_records.jsonl").read_bytes())
            (rep_dir / "client_records.jsonl").unlink()
            log(f"seed {seed}: instrumented run returncode={done.returncode} seconds={seconds:.1f}")

            log(f"seed {seed}: bypass run")
            bypass_cmd = [
                python, str(repo / "e2e" / "client.py"),
                "--corpus-dir", args.corpus_dir, "--e2e-config", args.e2e_config,
                "--seed", str(seed), "--warmup", "0", "--measured", str(measured),
                "--bypass", "--out", str(byp_dir / "client_records.jsonl"),
            ]
            done_b = subprocess.run(bypass_cmd, capture_output=True, text=True,
                                    env=wrapper_env)
            (byp_dir / "client.log").write_text(done_b.stderr)
            with gzip.open(byp_dir / "client_records.jsonl.gz", "wb") as sink:
                sink.write((byp_dir / "client_records.jsonl").read_bytes())
            (byp_dir / "client_records.jsonl").unlink()
            log(f"seed {seed}: bypass returncode={done_b.returncode} "
                f"seconds={time.time() - started - seconds:.1f}")
        finally:
            wrapper.terminate()
            try:
                wrapper.wait(timeout=15)
            except subprocess.TimeoutExpired:
                wrapper.kill()
            tegrastats.terminate()
            time.sleep(2)  # let the audit drain see EOF and write its summary

    # OpenPLC runtime logs (scan statistics and overruns)
    done = subprocess.run(
        [python, "-c",
         "import json,ssl,urllib.request\n"
         "ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE\n"
         "def call(path, payload=None, token=None):\n"
         "    req = urllib.request.Request('https://127.0.0.1:8443' + path,\n"
         "        data=json.dumps(payload).encode() if payload else None,\n"
         "        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token if token else ''})\n"
         "    return urllib.request.urlopen(req, context=ctx, timeout=30).read().decode()\n"
         "token = json.loads(call('/api/login', {'username': 'hardware', 'password': 'zonecap-e2e-2026'}))['access_token']\n"
         "print(call('/api/status', token=token))\n"
         "print(call('/api/runtime-logs', token=token)[-20000:])\n"],
        capture_output=True, text=True)
    (out_dir / "openplc_runtime_logs.txt").write_text(done.stdout + done.stderr)

    (out_dir / "log.txt").write_text("\n".join(log_lines) + "\n")
    (out_dir / "command.txt").write_text(
        f"PYTHONPATH=src {python} e2e/run_e2e.py --corpus-dir {args.corpus_dir} "
        f"--e2e-config {args.e2e_config} --output-dir {args.output_dir}\n")

    manifest = {
        "files": {
            str(path.relative_to(out_dir)): sha256(path)
            for path in sorted(out_dir.rglob("*")) if path.is_file()
        }
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    log(f"run directory complete: {out_dir}")


if __name__ == "__main__":
    main()
