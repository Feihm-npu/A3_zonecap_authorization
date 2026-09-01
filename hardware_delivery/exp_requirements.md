---
title: ZoneCap C5 Hardware Experiment Requirements
version: 1.0
date: 2026-09-02
experiments: [exp-22, exp-23, exp-24, exp-25]
execution_owner: hardware group
approved_target: NVIDIA Jetson Orin NX 8GB Developer Kit
status: protocol requirements frozen; implementation and corpus hashes must be frozen before confirmatory execution
---

# ZoneCap C5 Hardware Experiment Requirements

## 1. Objective and decision rule

The hardware group will execute exp-22 through exp-25 for C5:

> On the approved OpenPLC/Jetson testbed, ZoneCap's p99 decision latency is at
> most 1 ms and consumes at most 10% of a 10 ms PLC scan cycle while enforcing
> the registered policy set.

The registered thresholds apply to the **server-side ZoneCap decision path** on
the Jetson. That path excludes client/network transit but includes request
parsing, token-chain and signature verification, revocation lookup, context
lookup, policy decision, and audit enqueue. OpenPLC end-to-end latency, including
transport and PLC processing, must be measured and reported separately; it must
not be substituted for the decision-path metric.

C5 passes only if every one of the five exp-22 repetitions has:

- p99 decision latency no greater than `1,000 us`;
- p99 scan-cycle occupancy no greater than `10%`, calculated as
  `p99_decision_us / 10,000 us * 100`;
- zero decision mismatch against the frozen oracle/corpus; and
- every required check enabled and positively exercised.

Any failed repetition is reported. No repetition or seed may be selected,
discarded, or silently rerun.

## 2. Scope boundary and prerequisites

### 2.1 Approved hardware

- NVIDIA Jetson Orin NX 8GB Developer Kit, exactly as approved by the human.
- The S1 plan assumed an AGX Orin-class device. Orin NX 8GB is an explicit human
  replacement, not an equivalence claim. Record the exact module SKU, carrier
  board, storage, power supply, cooling, and memory size in every environment
  manifest.
- No GPU workload is required. Report GPU utilization to demonstrate that GPU
  acceleration was not silently introduced.

### 2.2 OpenPLC topology

One of the following must be selected before implementation freeze and retained
for all main/baseline measurements:

1. `split_host` (preferred): ZoneCap runs on the Jetson and communicates over a
   dedicated wired link with a separate OpenPLC v4-capable PLC or Raspberry Pi.
2. `single_host`: ZoneCap and OpenPLC v4 run as separate pinned processes on the
   Jetson. This remains a Jetson/OpenPLC software path, but the report must state
   that it does not measure a separate PLC or network hop.

Record the topology. Do not mix topologies within a repetition or pool results
across topologies. Wi-Fi is not permitted for confirmatory measurements.

### 2.3 Required software freeze

No confirmatory measurement may begin until all of the following are committed
and SHA-256 hashes are placed in the run configuration:

- ZoneCap source and hardware benchmark runner;
- exp-22/23/24/25 configuration files;
- exact request corpus and independent expected-decision oracle output;
- token/signature, revocation, context, and audit implementations;
- OpenPLC program/configuration and scan-period setting;
- SINT runner at commit
  `2461a911b8c3d7ed9da3f7662b33678f688eb826`;
- executable PLC ABAC/NGAC adapters, if available; and
- aggregation/percentile code and its unit tests.

The current repository has development decision timing but no frozen C5 hardware
runner. The hardware group may implement the adapter/harness from this document,
but must return it for code review and a clean pre-run freeze. Measurements made
while developing the harness are `development` only and cannot support C5.

## 3. Environment control and preflight

Capture these items before every fresh process launch:

- UTC timestamp; repository commit; `git status --porcelain`;
- JetPack, L4T, Ubuntu, kernel, Python, Node, OpenPLC, Redis (if used), and
  compiler/package versions;
- `/proc/cpuinfo`, `lscpu`, total RAM, storage type, and free space;
- exact `nvpmodel` mode, `jetson_clocks --show`, CPU governor, online cores,
  current/min/max frequencies, fan mode, and ambient temperature if available;
- process CPU affinity, scheduler policy/niceness, and cgroup/container limits;
- OpenPLC topology, runtime commit/version, task period, and wired-network link
  speed when using `split_host`;
- background services intentionally left running; and
- `tegrastats` sampled throughout the run at no slower than 1 Hz.

Use a fixed sustained-performance power mode supported by the device and lock
clocks with the standard Jetson controls. Do not change the mode after seeing a
result. Connect stable external power and active cooling. Disable automatic
updates, screen blanking, and unrelated scheduled jobs for the measurement
window. Do not enable swap during a run.

Pin the benchmark worker to one named CPU core. Pin OpenPLC, Redis, audit drain,
and monitoring processes to other cores. Verify affinity from `/proc/<pid>/status`
after launch; merely requesting affinity is insufficient.

Before exp-22, run the timer sanity suite equivalent to exp-26 on the Jetson.
Abort confirmatory execution if any of these occur:

- requested affinity is not observed;
- timer resolution is greater than or equal to the reported p99;
- full-check timing is not slower than the empty-call lower bound;
- the forced-slow detector or disabled-check detector does not fire;
- thermal/power throttling occurs;
- the 10 ms OpenPLC task period is not observed;
- a required dependency, source hash, or commit differs; or
- a decision-equivalence check fails during preflight.

Retain the aborted run directory and reason. A replacement run requires a logged
infrastructure cause; it does not erase the aborted attempt.

## 4. Common workload and measurement contract

### 4.1 Repetitions and ordering

Use these five fixed repetition/order seeds, one fresh process launch per seed:

`104729, 130363, 155921, 196613, 262147`

For each standard configuration and seed:

1. start a fresh benchmark worker and verify environment/affinity;
2. execute `10,000` unrecorded warm-up decisions;
3. execute `100,000` measured decisions sequentially;
4. store every raw duration in integer nanoseconds;
5. store the request ID, expected decision, observed decision, and enabled-check
   bitmask for every measured decision; and
6. stop the process before the next seed.

The seed controls only deterministic request ordering. Report all seeds. Do not
use S1 development seed `7`.

### 4.2 Corpus

The corpus must be generated once from the frozen held-out IEC 62443 policy
tables used in exp-07. It must include allowed and denied cases and must exercise
zone, conduit, asset, action, parameter, time, operating mode, and pre-action
sequence decisions. The generator, corpus, and oracle must be independent of
the timed engine and hashed before use.

Cycle through the same frozen request-ID sequence for all comparable systems.
Do not regenerate, remove, or rebalance cases after observing performance.
Exp-25 uses the frozen **common expressible subset** for direct decision/latency
comparison and separately reports each baseline's unsupported dimensions as
`N/A`; it must not treat unsupported cases as allows or denies.

### 4.3 Timed region

Start the timer immediately before parsing the serialized request and stop it
after the audit record has been accepted by the bounded audit queue. The timed
region must include:

- serialized-request parse and schema checks;
- full token/delegation-chain validation;
- real Ed25519 signature verification on the full configuration;
- revocation and runtime-context lookup;
- policy evaluation/effect selection;
- exact response construction; and
- bounded audit enqueue with backpressure/failure handling.

It must exclude corpus iteration, sample serialization, percentile calculation,
client transit, OpenPLC transit, and offline audit persistence. Measure audit
drain/persistence separately. Prevent dead-code elimination by consuming and
hashing decisions after the timed region.

Use a monotonic high-resolution clock and integer nanoseconds. Percentiles use
nearest-rank on sorted samples (`ceil(p*N)`, one-indexed); do not interpolate.
Report per repetition and across the pooled 500,000 samples:

- p50, p95, p99, p99.9, maximum, arithmetic mean, and median absolute deviation;
- throughput from measured wall time, not the reciprocal of a percentile;
- p99 occupancy against the fixed 10 ms scan cycle;
- peak RSS and RSS after warm-up;
- serialized root/depth-1/depth-2 token bytes; and
- decision mismatch count and mismatch records.

Also report worst-repetition p99. The C5 threshold is evaluated per repetition,
not only on pooled samples.

### 4.4 End-to-end OpenPLC path

Use a frozen OpenPLC program with a 10 ms periodic task. The request carries a
monotonic correlation ID; the PEP response and PLC acknowledgement must retain
it. Measure at least `100,000` end-to-end commands per repetition after the same
warm-up, recording:

- client-send to PEP-decision;
- PEP-decision to OpenPLC receipt;
- OpenPLC receipt to application/acknowledgement;
- total client-send to acknowledgement; and
- observed OpenPLC scan-period distribution and missed/overrun cycles.

If clocks cross hosts, use hardware/PTP synchronization or measure round trips
from one clock. NTP-only one-way subtraction is not acceptable. Do not combine
end-to-end durations with server-side decision samples.

## 5. Experiment matrix

### exp-22 — full-path main experiment

Run the common contract for all five seeds with:

- signature verification enabled;
- complete delegation-chain validation enabled;
- revocation lookup enabled and populated with both hit/miss probes outside the
  timed main request mix;
- runtime-context lookup enabled;
- audit enqueue enabled and its consumer active;
- all compiler-generated policy dimensions enabled; and
- OpenPLC fixed at a 10 ms task period.

Required outputs are per-repetition and pooled decision latency, occupancy,
throughput, memory, token bytes, exact decision agreement, enabled-check proof,
and separately measured OpenPLC end-to-end timing.

### exp-23 — check/cache/revocation diagnostics

Use the same corpus and five seeds. The `full` configuration is exp-22 and must
not be rerun or replaced merely because a diagnostic is faster. Run:

| Configuration | Change from full | Evidence role |
|---|---|---|
| `cache_miss` | invalidate only policy/token/context application caches before each timed decision; do not drop the OS page cache | cold-cache diagnostic |
| `unsigned` | bypass only signature verification and set an explicit disabled-check bit | diagnostic only; cannot support C5 |
| `remote_revocation` | replace local lookup with pinned Redis on the selected topology | propagation/lookup diagnostic |
| `audit_disabled` | bypass only audit enqueue and set an explicit disabled-check bit | diagnostic only; cannot support C5 |

For `cache_miss`, use five launches and 10,000 measured decisions per seed with
no warm-up; report it separately and do not pool with warm results. For every
other configuration use the standard 10,000/100,000 contract. Verify that all
variants preserve exact decisions. Report component-level deltas without
claiming that unsigned or audit-disabled latency is the deployable result.

For remote revocation, additionally issue 1,000 revocations and record
authority-issuance to resolver-visible propagation delay, including p50/p99/max.
The issuer-relative stale-execution finding from exp-19 remains a safety result;
delivery-time measurements do not redefine it.

### exp-24 — policy-count and delegation-depth scaling

Run the Cartesian product:

- policy count: `1, 10, 100, 1000`;
- delegation depth: `0, 1, 2`; and
- all five seeds/repetitions.

Use full checks and the standard 10,000/100,000 contract for all 12
configurations. The matching policy and request semantics remain fixed; extra
policies are deterministic nonmatching policies generated before the freeze.
Record how policies are indexed and do not change the indexing algorithm after
results are seen. Each delegation level must contain real signed parent/child
tokens and validate the complete chain.

Report latency, throughput, peak/RSS memory, serialized token bytes, and exact
decision agreement for every cell. Do not report only a fitted trend line.

### exp-25 — baseline comparison

Run ZoneCap and each available baseline on the identical common-subset corpus,
request order, topology, affinity policy, warm-up, measured count, and five
seeds:

- ZoneCap full path;
- SINT at commit `2461a911b8c3d7ed9da3f7662b33678f688eb826`;
- a versioned executable PLC ABAC/NGAC implementation, if supplied and frozen.

Do not call the repository's functional projections an external implementation
benchmark. If no executable PLC ABAC/NGAC artifact is supplied before the
freeze, report its performance as `N/A` with the availability reason. Never copy
published numbers into measured-result columns.

For each system report p50/p99/max, throughput, memory, exact agreement on its
expressible subset, number/fraction of full-corpus cases expressible, and an
explicit feature-scope table. A speedup greater than 10x over SINT is a bug
signal requiring the audit in Section 7 before interpretation.

## 6. Required result layout

Return one immutable directory per experiment:

```text
results/<run_id>/
  config.json
  command.txt
  seeds.txt
  log.txt
  metrics.json
  repetitions/<seed>/metrics.json
  repetitions/<seed>/raw_samples_ns.bin.gz
  repetitions/<seed>/decisions.jsonl.gz
  repetitions/<seed>/environment.json
  repetitions/<seed>/tegrastats.log
  decision_mismatches.jsonl
  environment_manifest.json
  source_manifest.json
  check_activation.json
  timer_sanity.json
  manifest.json
```

Use run IDs `exp22_c5_main_<YYYYMMDD>`, `exp23_c5_ablation_<YYYYMMDD>`,
`exp24_c5_scaling_<YYYYMMDD>`, and `exp25_c5_baselines_<YYYYMMDD>`. Every reported
number must be derivable from returned raw samples. `manifest.json` contains
SHA-256 for every input and output, including empty logs. Record the exact shell
command; a prose description is insufficient.

The hardware group returns:

1. the four complete result directories;
2. all harness/config/OpenPLC changes as a commit or patch;
3. a one-page execution note listing invalid/aborted attempts and deviations;
4. photographs or console captures sufficient to identify the Jetson module,
   power/cooling mode, and OpenPLC topology; and
5. a SHA-256 checksum file for the transfer archive.

Do not edit `research/PLAN.md`, `research/CLAIMS.md`, `research/NOTEBOOK.md`, or
`STATE.md`. The research-loop executor will audit and integrate returned data.

## 7. Mandatory bug and integrity audits

Stop interpretation and retain the run if any result is unexpectedly strong,
including p99 below measured timer resolution or a greater-than-10x SINT
speedup. Before any rerun, check and record:

- raw sample count and uniqueness;
- clock source/resolution and unit conversion;
- process affinity actually applied;
- thermal/power throttling and frequency drift;
- request parsing and output consumption were inside/after the correct boundary;
- signature, revocation, context, and audit checks were called and their
  negative probes failed closed;
- corpus/oracle independence and request-ID completeness;
- no compiled-out checks, memoized final decisions, replayed timestamps, or
  dead-code elimination;
- identical common-subset request order across baselines; and
- manifest/source hashes against the pre-run clean commit.

Inject and detect at least these controls before accepting any latency result:

1. a forced `>=5 ms` sleep inside the timed check;
2. an invalid signature;
3. a revoked token;
4. an out-of-scope parameter/action;
5. a stale/missing runtime context;
6. an unavailable/full audit queue; and
7. a deliberately wrong oracle decision.

The full path must fail closed on controls 2–6, the evaluation must detect
control 7, and the timer must expose control 1. Diagnostic variants may disable
only their named check; all other controls remain active.

## 8. Acceptance checklist

The handoff is ready for research review only when all items are true:

- [ ] exact Orin NX 8GB and OpenPLC topology recorded;
- [ ] clean frozen commit and all input/source hashes recorded;
- [ ] Jetson timer/affinity/check sanity passed;
- [ ] five seeds and five fresh launches present for every standard cell;
- [ ] 10,000 warm-up plus 100,000 raw measured decisions per standard launch;
- [ ] raw server-side and end-to-end samples kept separate;
- [ ] all exp-22 full checks enabled and positively exercised;
- [ ] exp-23 diagnostic disablement explicitly labeled;
- [ ] all 12 exp-24 scale/depth cells present;
- [ ] exp-25 baselines use the identical expressible corpus or are `N/A`;
- [ ] per-seed, pooled, and worst-repetition metrics reported;
- [ ] every decision mismatch and invalid/aborted attempt retained;
- [ ] thermal/power/affinity/scan-period evidence included; and
- [ ] manifests and transfer checksums verify.

