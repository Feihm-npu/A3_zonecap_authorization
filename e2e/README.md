# ZoneCap C5 end-to-end OpenPLC path (hardware group, Section 6)

Secondary, descriptive measurement of the full command path with OpenPLC v4 on
the same Jetson (`single_host` topology, frozen 2026-11-03).  These data are
**never** pooled with the server-side matrix samples; they live in their own
result directory `results/exp22_c5_e2e_<YYYYMMDD>/`.

> **Mandatory disclosure (exp_requirements.md §4.2/§6):** the `single_host`
> topology measures neither a separate PLC nor a network hop, and the loopback
> transport is **unauthenticated**.

## Components

| File | Role |
|---|---|
| `e2e_config.json` | Frozen knobs: counts, seeds, cores, ports, register map, emit rule, disclosures |
| `wrapper.py` | Server wrapper around the **unmodified** `ReferencePEP.decide`: loopback TCP in, context ingest, `decide`, Modbus forward, per-command timestamps |
| `client.py` | Replays `main` corpus steps; releases one command per 10 ms scan window at a seeded uniform random phase (phase logged relative to the observed scan start); `--bypass` writes the PLC directly with the same emit pattern |
| `run_e2e.py` | Per-seed orchestrator: instrumented run + bypass run + tegrastats + runtime logs + environment capture + SHA-256 manifest |
| `openplc_program/` | The frozen OpenPLC program (project + Editor-CLI build + provenance) — see its `PROVENANCE.md` |

## Measurement segments (one host clock, `time.perf_counter_ns`)

Per command: `client send` → `PEP receipt` → `decide start/stop` (identical
boundary to the matrix harness) → `OpenPLC receipt` (FC16 write returned) →
`acknowledgement` (ack_seq observed == plc_cmd_seq, tight-poll on the same
loopback) → `total`.  Commands whose decision emits nothing (`deny`, `defer`,
`attenuate` — per the frozen emit rule) record the path only up to the decision
return.  The bypass run records the same fields without the PEP for the
overrun comparison (same emit pattern: corpus expected allow/rewrite).

Scan-period distribution and overruns come from two independent sources:
the OpenPLC runtime's own statistics (its per-5 s stats: scan time, cycle
time, latency, overruns — collected into `openplc_runtime_logs.txt`) and the
client's heartbeat observation.

## How to run (on the Jetson, from the repo root)

```bash
# once: e2e virtualenv (kept separate from the measurement venv)
python3 -m venv ~/zonecap-c5-e2e && ~/zonecap-c5-e2e/bin/pip install pynacl==1.5.0 pymodbus

PYTHONPATH=src ~/zonecap-c5-e2e/bin/python e2e/run_e2e.py \
    --corpus-dir build/c5_corpus --e2e-config e2e/e2e_config.json \
    --output-dir results/exp22_c5_e2e_<YYYYMMDD> \
    --python ~/zonecap-c5-e2e/bin/python
```

## Process placement (single_host)

| Process | Core |
|---|---|
| OpenPLC runtime (systemd `openplc-runtime`, `CPUAffinity=2`) | 2 |
| wrapper (`decide` worker + audit drain child on 4) | 3 |
| client + tegrastats | 1 |
| OS / interrupts | 0 |

## Deliberate limitations (returned for review)

- One command per scan window (≈100 Hz release), warm-up 10,000 then 100,000
  measured commands per repetition, five seeds — same discipline as the
  registered matrix.
- The wrapper's audit drain writes `audit.log` per repetition; the drain is
  finalised by wrapper termination (EOF), matching the bounded-queue
  fail-closed semantics exercised by the matrix runs.
- Phase anchoring uses the heartbeat register observed over loopback Modbus;
  the monitor thread and ack polls serialise on one Modbus transaction lock.
  During ack polls (emitting commands only) boundary observations may stall up
  to the ack timeout; the released phase is computed against the latest
  estimate and the residual error is bounded by one scan period.
