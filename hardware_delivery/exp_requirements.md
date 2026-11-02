---
title: ZoneCap C5 Hardware Experiment Requirements
version: 1.1
date: 2026-11-02
supersedes: 1.0 (2026-09-02); no v1.0 harness was frozen and no v1.0 data exist
experiments: [exp-22, exp-23, exp-24, exp-25]
execution_owner: hardware group
approved_target: NVIDIA Jetson Orin NX 8GB Developer Kit
status: >-
  protocol, system under test, corpus, oracle, harness, and decision rules are
  frozen at the delivery commit; the hardware group adapts only the platform
  items in Section 2.11 and builds the end-to-end OpenPLC path in Section 6
---

# ZoneCap C5 Hardware Experiment Requirements (v1.1)

Version 1.1 replaces version 1.0 in full. Appendix A lists every change and the
audit finding it resolves (`hardware_delivery/exp_requirements_audit.md`). The
hardware group starts from this version; nothing from version 1.0 is reused.

## 1. Objective and registered decision rules

The hardware group executes exp-22 through exp-25 for C5:

> On the approved OpenPLC/Jetson testbed, ZoneCap's p99 decision latency is at
> most 1 ms and consumes at most 10% of a 10 ms PLC scan cycle while enforcing
> the registered policy set.

### 1.1 What is measured

The registered thresholds apply to the **server-side decision path of the frozen
reference policy enforcement point (PEP)**, `zonecap.c5.pep.ReferencePEP.decide`,
running on the Jetson. The timer starts immediately before `decide` receives the
serialized envelope and stops when `decide` returns, after the decision record
has been accepted by the bounded audit queue. The timed region therefore
contains all ten stages of Section 2.3: parsing and schema checks, root
anchoring, delegation-chain validation, Ed25519 verification, revocation lookup,
context lookup, policy evaluation, effect binding, response construction, and
audit enqueue. It excludes client and network transit, transport-session
authentication, context ingest, corpus iteration, and audit persistence. The
end-to-end OpenPLC path (Section 6) is measured and reported separately; it never
replaces the decision-path metric.

### 1.2 C5 rule (exp-22)

C5's registered thresholds are met only if **every one of the five exp-22
repetitions** satisfies all of the following, and the run's preflight passed:

1. p99 decision latency at most `1,000 us`;
2. derived scan occupancy at most `10%` (see the disclosure below);
3. zero decision mismatches against the separate oracle;
4. every measured decision carries the full ten-stage activation mask;
5. for every measured decision, Ed25519 verifications plus verification-cache
   hits equal the presented chain length;
6. the audit drain received exactly one record per decision (warm-up plus
   measured) and no decision was denied for audit unavailability; and
7. no zero or negative timing sample.

**Occupancy disclosure.** Occupancy is defined, as in version 1.0, as
`p99_decision_us / 10,000 us * 100`. It is a ratio derived from item 1, not an
independent measurement; items 1 and 2 are the same condition. The result files
name it `derived_p99_scan_occupancy_percent`, and any report must describe it as
derived. In the preferred `split_host` topology the decision does not execute on
the PLC and consumes no PLC scan time. Quantities that do involve the scan cycle
(end-to-end latency, observed scan period, and overruns) are registered as
secondary descriptive metrics in Section 6 and do not enter this rule.

Items 3 to 6 make "while enforcing the registered policy set" checkable: the
decisions must match the oracle, and every check must have run on every measured
decision.

### 1.3 Alternative A1 (exp-23)

A1: *"The threshold is met only through warm caches or omitted
signature/revocation checks."*

- The omitted-check part is excluded by items 4 and 5 of Section 1.2 together
  with negative controls 2 and 3 (Section 8).
- The warm-cache part is ruled out only if **every** `cache_miss` repetition
  (verification cache cleared before each timed decision, so every token
  signature is verified) has p99 at most `1,000 us`, zero mismatches, the full
  stage mask, verification count equal to chain length, complete audit, and no
  non-positive sample.
- If the exp-22 rule holds but this criterion fails, the result may be stated
  only as holding with a warm verification cache, and the `cache_miss` result must
  be reported next to it.

### 1.4 Alternative A2 (exp-24)

A2: *"The threshold is met only for a toy policy count."*

- A2 is ruled out only if **every** repetition of the 1,000-policy cells
  `p1000_d0`, `p1000_d1`, and `p1000_d2` (full path) has p99 at most `1,000 us`,
  zero mismatches, the full stage mask, consistent verification counts, complete
  audit, and no non-positive sample.
- If this criterion fails, the result must be restricted to the largest
  registered policy count (1, 10, or 100) at which all three depths pass.

### 1.5 Reporting discipline

The harness computes these rules mechanically and stores them under
`registered_checks` in `metrics.json`. Interpretation belongs to the research
review, not to the executor.

- Report every repetition.
- No repetition or seed may be selected, discarded, or silently rerun.
- An aborted or failed repetition stays in the returned data.
- A replacement run requires a logged infrastructure cause.

## 2. System under test

### 2.1 Identity

The system under test is the Python package `src/zonecap/c5/` at the delivery
commit, together with the modules it imports (`compiler.py`, `effects.py`,
`engine.py`, `exp07_generator.py`, `models.py`).

| Component | Registered version |
|---|---|
| Interpreter | CPython 3.10.x (JetPack 6.x / Ubuntu 22.04 system Python) |
| Ed25519 | PyNaCl 1.5.0, whose wheel bundles libsodium 1.0.18 |
| Everything else | Python standard library |
| Baseline runtime | Node.js 22 or later (SINT's declared engine), used only to run pinned SINT in exp-25 |

`configs/c5/*.json` store the SHA-256 of every frozen file. The harness refuses
to run when any hash differs.

No other implementation is registered. A port to another language, another
cryptographic library, or any other change to the decision path is a different
system and requires a new requirements version. Version 1.1 registers no
optimized path. PLAN's "decision agreement before/after optimization" is
therefore checked between two paths:

- the pre-serialization reference path, `PolicyEngine` plus `EffectBinding` on
  in-memory capabilities, which must agree with the oracle on every corpus step
  when the corpus is built (`reference_engine_mismatches = 0`); and
- the timed PEP, which must agree with the oracle on every measured decision.

### 2.2 Wire format and tokens

An envelope is
`"ZCE1" | u8 n | n x (u16 len | token payload | 64-byte Ed25519 signature) | u16 len | request payload`,
with big-endian integers. Limits:

| Item | Limit |
|---|---|
| Chain length `n` | 1 to 8 |
| One payload | 4,096 bytes |
| One envelope | 65,536 bytes |

Payloads are canonical JSON: ASCII, sorted keys, no insignificant whitespace,
and no NaN or infinity. Every number is a finite float or an integer within
±2^53, and the version `v` is the integer 1.

A token payload carries:

- version `v`, identifier `id`, policy identifier `pol`, issuer `iss`, depth `d`;
- subject `sub` and the subject's Ed25519 public key `spk`;
- zones `zs`/`zd`;
- conduits `K`, assets `A`, operations `O`, parameter interval `Iu`, tick
  window `It`, modes `M`, required event sequence `L`;
- `prev`, the hex SHA-256 of the parent's signed bytes (payload plus
  signature), which is `null` for a root.

Who signs what:

- A **root** is signed by the issuer's trust-anchor key.
- A **child** is signed by its parent's subject key (`spk`).
- The **request payload** (`v`, `zs`, `zd`, conduit `k`, asset `a`, operation
  `o`, value `u`, request identifier `rid`) is not signed. Request origin is authenticated by the transport
  session (CIP Security, an OPC UA secure channel, or mutual TLS), which hands
  the authenticated subject to the PEP. Transport authentication is outside the
  decision path.

Serialized token sizes in the frozen corpus, including the 1,000 synthetic
exp-24 grants (Section 3):

| Depth | Tokens | Bytes (minimum to maximum) |
|---|---|---|
| 0 (root) | 1,042 | 472–544 |
| 1 | 4,066 | 516–614 |
| 2 | 1,798 | 525–599 |
| 3 | 756 | 535–609 |

Depth 3 occurs only for runtime-attenuated children of depth-2 grants (Section 3).

### 2.3 Decision path

`decide(authenticated_subject, envelope)` runs these stages in a fixed order.
Each stage sets one bit in the per-decision activation mask. Stages 1 to 5 deny
on failure. Stage 1 denies on any exception, including oversized integers and
deep nesting, so hostile input can never crash the PEP.

| # | Stage | Check |
|---|---|---|
| 1 | parse | envelope framing; JSON decoding of every payload; exact key sets, types, and finite numbers |
| 2 | anchor | root issuer is a trust anchor; root names a registered policy; root depth 0; root subject equals the policy subject; root ⪯ registered compiled policy |
| 3 | chain | every link: depth = index; `prev` equals the parent digest; same policy; child ⪯ parent (issuer and zone endpoints equal; K, A, O, M subsets; Iu, It subintervals; L extends the parent's sequence as a prefix) |
| 4 | signature | every token: Ed25519 verification, or a hit in the verification cache (Section 2.4) |
| 5 | revocation | every token identifier in the chain is looked up |
| 6 | context | snapshot lookup by (target zone, asset) and freshness check (Section 2.6) |
| 7 | policy | presenter binding, then the five effects in the registered `PolicyEngine` order (below) |
| 8 | binding | the emitted action is re-checked against the effective capability before emission; deferrals are bounded (Section 2.8) |
| 9 | response | exact canonical-JSON decision record |
| 10 | audit | non-blocking enqueue of that record; failure turns the decision into a DENY (Section 2.7) |

The policy stage evaluates, in order:

1. an authenticated subject that differs from the leaf subject gives `DENY`;
2. missing, stale, or incomplete context gives `DEFER`;
3. a registered high-risk flag gives `DEFER`;
4. a failed source-zone, target-zone, conduit, asset, operation, time, mode, or
   event-sequence check gives `DENY`;
5. a runtime envelope that strictly narrows `Iu` gives `ATTENUATE`, carrying the
   narrowed child interval and executing nothing; a runtime envelope disjoint
   from `Iu` gives `DENY`;
6. a value outside `Iu` gives `REWRITE` to the nearest boundary;
7. otherwise `ALLOW`.

**Why presenter binding comes first.** `PolicyEngine` evaluates context before
the subject because its requests carry an already authenticated subject. The PEP
must first establish that the presenter holds the leaf. Otherwise, a non-holder
who replays a valid chain against missing context would receive the `read` hold
and could change the holder's deferral count. The two orders give identical
decisions on every corpus step, which the corpus build checks
(`reference_engine_mismatches = 0`).

**Hold value.** The registered hold for `DEFER` is the operation `read` at the
lower bound of the effective `Iu`, as in exp-12's one-request binding. exp-12's
composed traces held at the request value, so C5's composed `DEFER` steps differ
from exp-12 only in the hold value (1,512 of 4,536 traces).

**Exact comparisons.** The PEP and the oracle compare intervals exactly.
`PolicyEngine` tolerates `1e-12`. No corpus value lies within `1e-12` of a bound.

### 2.4 Verification cache

The PEP keeps one cross-request cache. It maps the SHA-256 digest of a token
whose signature, linkage, and attenuation have been verified to "verified".

- Tokens are immutable signed data, and a child's `prev` field binds its parent.
- The capacity is 65,536 entries with first-in, first-out eviction.
- A digest is still computed for every token on every request.

Never cached, and evaluated on every request:

- parsing;
- root anchoring and registration;
- revocation;
- context;
- policy;
- binding;
- the response; and
- the audit enqueue.

No parsed token, decision, or response is reused across requests.

Static configuration loaded at start-up is not a cache: trust-anchor keys, the
registered policy index, the revocation set, and the context store.

The `cache_miss` diagnostic (exp-23 and exp-24) clears the cache before every
timed decision, outside the timed region. Every token is then verified on every
request. Changing trust-anchor keys requires clearing the cache.

### 2.5 Revocation

- The full path uses an in-process set of revoked token identifiers, preloaded
  with 10,000 synthetic identifiers that match no corpus token.
- Every token identifier in the presented chain is checked, so revoking a parent
  revokes all of its descendants.
- The `remote_revocation` diagnostic replaces the set with a Redis set on the
  same Jetson. The PEP sends one pipelined batch of `SISMEMBER` commands per
  decision, which is one round trip on any Redis version. A Redis error, or a
  reply slower than the registered 100 ms timeout, denies the request
  (fail-closed). The client then reconnects on the next lookup, and the number
  of reconnects is recorded.
- Revocation delivery into the local set is not part of the decision path. The
  exp-19 finding (issuance-relative stale execution) remains a safety result, and
  delivery-time measurements do not redefine it.

### 2.6 Runtime context

Context is an in-process, versioned snapshot keyed by (target zone, asset). A
snapshot holds:

- trusted tick, operating mode, and physical event history;
- a completeness flag and a high-risk flag; and
- an optional runtime parameter envelope.

The context-ingest component publishes snapshots. The decision path performs one
dictionary lookup and checks freshness against a maximum age of `50 ms` (five
scan periods). A missing, stale, or incomplete snapshot yields `DEFER`.

Reading PLC or plant state over a network belongs to ingest, not to the decision
path. In the harness, the client publishes each corpus step's snapshot outside
the timed region immediately before the decision. In the end-to-end path
(Section 6), the server wrapper publishes it.

### 2.7 Audit queue

- **Queue.** The bounded audit queue is a pipe resized with `F_SETPIPE_SZ` to
  1,048,576 bytes. The PEP writes each record plus a newline with one non-blocking
  `write` of at most 4,096 bytes. POSIX makes such a write atomic: the whole
  record is enqueued, or the write fails.
- **Fail-closed.** A full queue (`EAGAIN`), a closed drain (`EPIPE`), or an
  oversized record turns the decision into `DENY` with reason
  `audit_unavailable`, emits nothing, and leaves the audit bit clear.
- **Drain.** A separate drain process, pinned to another core, persists the
  records. It reports the record count, bytes, SHA-256, and peak backlog, all
  measured outside the timed region.
- **Kernel limits.** The resize needs `fs.pipe-max-size` of at least 1,048,576
  bytes (the Linux default). It also needs room under the per-user pipe budget
  `fs.pipe-user-pages-soft`. If the kernel refuses, setup retries and then aborts
  the repetition; the capacity is never reduced. Preflight checks that the
  registered capacity can be granted. On a dedicated Jetson the defaults
  suffice; any sysctl change must be recorded.

### 2.8 Deferral bound

The PEP denies the third consecutive `DEFER` for the same holder (`max_deferrals
= 2`). Only decisions that reach the binding stage, and whose presenter is the
holder, count toward or reset the holder's bound. Any other holder effect resets
it. Denials in stages 1 to 5, and presenter-binding denials, neither count nor
reset. Composed corpus traces never contain consecutive deferrals for one holder,
so a timeout in a measured run
appears as a decision mismatch.

### 2.9 Runtime settings

- Garbage collection stays enabled with default thresholds.
- After loading the corpus and building the PEP, the harness calls
  `gc.freeze()`. This moves start-up objects out of collection. It is ordinary
  deployment practice for long-running services and is recorded in every
  repetition's metrics.
- No other garbage-collector, interpreter, or allocator setting may be changed
  for measurement. This includes disabling the collector, changing thresholds,
  running `python -O`, and using a non-default allocator.
- Swap stays off.

### 2.10 Key material

- Corpus keys are derived deterministically from public strings (domain
  `zonecap-c5-test-keys-v1`). They are measurement fixtures and must never
  authorize a real plant.
- In a deployment, the PEP holds only trust-anchor public keys. No signing key
  resides on the PEP.
- An `ATTENUATE` response carries the narrowed interval. The holder signs the
  runtime child itself.

### 2.11 Platform items the hardware group may adapt

Only the following may differ from the delivery commit. Each adaptation is
committed before the confirmatory run and listed in the execution note.

1. CPU core numbers in `configs/c5/*.json`. The defaults are:

   | Use | Core |
   |---|---|
   | Benchmark worker | 3 |
   | Audit drain | 4 |
   | Pinned SINT process (exp-25) | 3 and 4, its two-core budget |
   | Redis server | 5 |
   | Propagation authority / resolver (exp-23) | 1 / 4 |
   | `tegrastats` | 1 |
   | OpenPLC under `single_host` | 2 |
   | OS and interrupts | 0 |

   The benchmark core must not be core 0. The harness pins its own processes.
   Redis is started by the hardware group pinned to its core (Section 5,
   exp-23).
2. The SINT checkout path, through `ZONECAP_C5_SINT_REPO`.
3. The Redis host and port, through `ZONECAP_C5_REDIS_HOST` and
   `ZONECAP_C5_REDIS_PORT`.
4. Additional environment-capture commands.
5. The end-to-end server wrapper, client, and OpenPLC program of Section 6, which
   the hardware group implements and returns for review.

Any other change is a deviation. It must be reported, and it may invalidate the
run.

## 3. Corpus and oracle

### 3.1 Building and checking the corpus

Build the corpus on the Jetson with
`PYTHONPATH=src python3 -m zonecap.c5.corpus build --output-dir build/c5_corpus`.

- The build is deterministic. Its fingerprint must equal
  `52971a47b69a6c252461570366cbe52234b7164dd66beb9b8da3a24568bb97ab`.
- `PYTHONPATH=src python3 -m pytest tests/test_c5_*.py` checks the fingerprint
  and must pass on the Jetson.
- The builder reads only frozen inputs:
  - `research/heldout/exp07/policy_tables.json`, SHA-256 `62af1979…7345`; and
  - `results/exp07_heldout_equivalence_20260901/cases.jsonl.gz`, SHA-256
    `46197806…33b6`.
- The registered policy set is the frozen exp-07 table: a source-derived
  zone/conduit topology plus the declared, source-independent evaluation overlay.
  It is not a complete IEC 62443 policy and implies no conformance claim. The
  compiler turns it into 42 registered root capabilities. exp-24 additionally
  uses 1,000 synthetic grants (below).

### 3.2 Variants

| Variant | Used by | Steps | Units | Expected effects | Chain depth (steps) |
|---|---|---|---|---|---|
| `main` | exp-22, exp-23 | 81,648 | 63,504 | allow 9,072; attenuate 4,536; defer 4,536; deny 49,896; rewrite 13,608 | d0 42,336; d1 22,680; d2 13,608; d3 3,024 |
| `scale_p{P}_d0` (P = 1, 10, 100, 1000) | exp-24 | 9,360 each | 9,360 | allow 720; deny 7,200; rewrite 1,440 | d0 9,360 |
| `scale_p{P}_d1` | exp-24 | 2,340 each | 2,340 | allow 180; deny 1,800; rewrite 360 | d1 2,340 |
| `scale_p{P}_d2` | exp-24 | 2,340 each | 2,340 | allow 180; deny 1,800; rewrite 360 | d2 2,340 |
| `sint_subset` | exp-25 | 27,216 | 27,216 | ZoneCap: allow 4,536; deny 18,144; rewrite 4,536. SINT: allow 4,536; deny 22,680 | d0 18,144; d1 4,536; d2 4,536 |

**`main`.** This is the exp-12 policy-step corpus:

- the 58,968 exp-07 one-request cases (every valid request and every
  single-field mutation); plus
- 4,536 five-step composed traces, `ATTENUATE, DEFER, ALLOW, REWRITE, DENY`.

The composed traces are the only source of `DEFER` and `ATTENUATE`. Their steps
2 to 5 present the holder-signed runtime child, which adds one level of depth.

**`scale_p{P}_d{D}`.** The corpus adds one synthetic architecture,
`synthetic_scale`. It has 1,000 disjoint one-way grants under the anchored issuer
`issuer:synthetic_scale`, all with the frozen overlay. The compiler turns them
into registered roots, and each has depth-1 and depth-2 delegations of exactly
the exp-07 shape.

Cell (P, D) contains ten passes over the exp-07 case template at depth D. Step
`j` uses template case `j mod T_D` (T_0 = 936, T_1 = T_2 = 234) of grant
`j mod P`. As a result:

- every cell has the same effect mix;
- every one of the P registered policies is requested; and
- the 1,000-policy cells reach 1,000 distinct roots and chains.

**`sint_subset`.** This contains the valid cases plus the subject, asset,
operation, parameter-high, and tick-high mutations that pinned SINT can express.
It is the fair subset of exp-10.

### 3.3 Oracle

`zonecap.c5.oracle` imports only the Python standard library. It computes each
step's expected decision `[effect, operation, value, child_low, child_high]` from
plain table data, as well as SINT's expected allow or deny. Expected decisions
are fixed when the corpus is built and are included in the fingerprint.

### 3.4 Order

The seed controls only the order. The units of a variant are shuffled with
Python's `random.Random(seed)`; a unit is one step, or one five-step composed
trace kept contiguous. The flattened sequence is repeated cyclically to fill the
warm-up and measured positions. Each repetition stores
`measured_step_sequence_sha256`.

### 3.5 Stratified reporting

Every repetition also reports p50, p99, and maximum by expected effect and by
chain depth.

## 4. Hardware, topology, and environment

### 4.1 Approved hardware

- Use the NVIDIA Jetson Orin NX 8GB Developer Kit, exactly as approved by the
  human, running JetPack 6.x (L4T R36.x, Ubuntu 22.04).
- The S1 plan assumed an AGX Orin-class device. Orin NX 8GB is an explicit human
  replacement, not an equivalence claim.
- Record the exact module SKU, carrier board, storage, power supply, cooling, and
  memory size.
- No GPU workload is used. Report GPU utilization to show that no GPU
  acceleration was introduced.

### 4.2 OpenPLC topology

Select one topology before the freeze and keep it for every measurement:

1. `split_host` (preferred): the PEP runs on the Jetson and talks over a
   dedicated wired link to a separate OpenPLC v4-capable PLC or Raspberry Pi.
2. `single_host`: the PEP and OpenPLC v4 run as separate pinned processes on the
   Jetson. The report must state that this measures neither a separate PLC nor a
   network hop.

Do not mix topologies or pool across them. Wi-Fi is not permitted.

### 4.3 Power, thermal, and environment control

**Power and thermal setup.**

- Use a fixed sustained-performance `nvpmodel` mode, applied with
  `jetson_clocks`. Never change it after seeing a result.
- Use stable external power and active cooling.
- Disable automatic updates, screen blanking, and scheduled jobs.
- Keep swap off.

**Environment capture.** `environment_manifest.json` records the
`environment_commands` of each configuration, and every repetition records:

- interpreter and library versions, including the SHA-256 of the libsodium
  binary;
- the CPU model and load average;
- the benchmark core's governor and frequencies before and after the measured
  loop;
- the activation mask and observed affinity; and
- RSS at every phase.

The hardware group adds:

- photographs or console captures identifying the module, power and cooling
  mode, and topology;
- the background services intentionally left running; and
- the ambient temperature, if available.

`tegrastats` is sampled at 1 Hz throughout each repetition when available.

**Throttling abort (operational definition).** A repetition is invalid if, during
its measured loop, either of the following occurs:

- `tegrastats` reports a benchmark-core frequency below the locked value, or a
  thermal or power throttle flag; or
- the benchmark core's `scaling_cur_freq` before or after the loop differs from
  the locked frequency.

Retain the invalid repetition and record the cause. A replacement requires that
logged cause.

### 4.4 Affinity

- The benchmark worker pins itself and verifies both `sched_getaffinity` and
  `/proc/self/status`.
- The audit drain, Redis, the propagation processes, `tegrastats`, and (under
  `single_host`) OpenPLC run on other cores.
- The SINT runner receives the benchmark and audit-drain cores. This is the
  same two-core budget as ZoneCap's worker plus drain, so V8's helper threads do
  not compete with its main thread on one core. The harness verifies the child
  process's `Cpus_allowed_list` after launch, and aborts on a mismatch.

### 4.5 Preflight

`zonecap.c5.matrix` runs the preflight automatically in a fresh process before
any repetition. Execution aborts, with the run directory retained, if any of the
following occurs:

- the requested affinity is not observed;
- the clock is not monotonic, or moves backwards;
- the empirical timer resolution is not below the empty-call median;
- the full probe is not slower than an empty call, at both p50 and p99;
- the 5 ms forced-slow probe is not detected (minimum at least 4 ms) or is not
  the slowest;
- any of the ten single-stage disabled-check mutants is not detected;
- any negative control of Section 8 fails;
- the kernel cannot grant the registered 1 MiB audit queue;
- the corpus fingerprint or any frozen source hash differs; or
- the 10 ms OpenPLC task period is not observed (end-to-end preflight,
  Section 6).

## 5. Experiment matrix

**Common contract.**

- Seeds `104729, 130363, 155921, 196613, 262147`, one fresh process per
  configuration and seed.
- 10,000 unrecorded warm-up decisions, then 100,000 measured decisions.
- Raw durations stored as integer nanoseconds.
- One decision record per measured decision.
- Percentiles use nearest rank (`ceil(p*N)`, one-indexed) without interpolation.

**Execution order.** Configurations run seed-major. For seed index `i`, the
registered configuration list is rotated by `i`, which spreads thermal drift
across configurations.

**Run commands.** One `matrix` invocation per experiment:

```text
PYTHONPATH=src python3 -m zonecap.c5.matrix --config configs/c5/<exp>.json \
    --corpus-dir build/c5_corpus --output-dir results/<run_id>
```

Confirmatory runs require a clean, committed tree. Untracked directories under
`results/` are allowed, so the four experiments can run back to back. The
`--development` flag marks a dry run that can never support C5.

### exp-22: full path (`configs/c5/exp22_c5_main.json`)

- One configuration, `full`, on `main` with every stage enabled.
- The verification cache is on; the local revocation set holds 10,000 entries.
- The audit drain is active, and its log is retained as `audit.jsonl.gz`.
- Decision rule: Section 1.2.

### exp-23: diagnostics (`configs/c5/exp23_c5_ablation.json`)

The `full` configuration is exp-22. It must not be rerun or replaced because a
diagnostic is faster.

| Configuration | Change from full | Evidence role |
|---|---|---|
| `cache_miss` | verification cache cleared before every timed decision | A1 rule (Section 1.3) |
| `cold_start` | fresh process, no warm-up, first 10,000 decisions measured | descriptive; reported separately, never pooled |
| `unsigned` | signature stage disabled; its mask bit stays clear | diagnostic only; cannot support C5 |
| `remote_revocation` | Redis set on the Jetson (pinned, loopback), 100 ms timeout | diagnostic only |
| `audit_disabled` | audit stage disabled; its mask bit stays clear | diagnostic only; cannot support C5 |

Report component deltas, such as full minus unsigned, as descriptive values. Do
not present them as deployable results.

**Redis.** Before exp-23, start Redis pinned to its core, without persistence,
and record the command and `redis-server --version`:
`taskset -c 5 redis-server --port 6379 --save "" --appendonly no`. The harness
loads the 10,000-identifier set itself. It reads the host and port from
`ZONECAP_C5_REDIS_HOST` and `ZONECAP_C5_REDIS_PORT`, which also drive the
propagation step.

**Revocation propagation.** `zonecap.c5.propagation` issues 1,000 revocations:

- The measurement runs after the exp-23 repetitions. The authority (core 1),
  the resolver (core 4), and Redis (core 5) run on the Jetson and read the same
  system-wide `CLOCK_MONOTONIC`. No benchmark worker is active at that point.
- For each revocation, the authority waits a seeded 1–10 ms delay, records
  `t_issue` immediately before `SADD`, and the resolver records `t_visible` on its
  first `SISMEMBER` hit.
- Report p50, p99, and maximum of `t_visible - t_issue`. The resolution is one
  resolver round trip.
- If the authority must run on another host, use PTP hardware timestamping or a
  single-clock round-trip measurement. NTP-only one-way subtraction is not
  acceptable.

### exp-24: policy count and delegation depth (`configs/c5/exp24_c5_scaling.json`)

- The 12 full-path cells are `p{1,10,100,1000}_d{0,1,2}` on the variants
  `scale_p{P}_d{D}` (Section 3.2). The registry holds the first P synthetic
  grants. All of them are anchored, registered, issued, and requested, and the
  requests rotate across them.
- Three diagnostic `cache_miss` cells `p1000_d{0,1,2}_cache_miss` expose the
  signature cost of each depth when all 1,000 policies are requested.
- The registered policy index is a hash map keyed by policy identifier (one
  lookup per request). It must not change after results are seen.
- Report every cell. Do not report only a fitted trend.
- Decision rule: Section 1.4.

### exp-25: baseline comparison (`configs/c5/exp25_c5_baselines.json`)

- **Workload.** Three configurations run on the same `sint_subset` steps, in
  the same per-seed order, with the same warm-up, measured count, seeds, and
  benchmark core:
  - `zonecap_full`, the full path;
  - `zonecap_cache_miss`, with the verification cache cleared before every timed
    decision, so that ZoneCap verifies every chain signature on every request,
    as SINT verifies its leaf signature on every request; and
  - `sint`.
- **SINT.** SINT is pinned at commit
  `2461a911b8c3d7ed9da3f7662b33678f688eb826`, prepared with the
  `prepare_command` in the configuration. Before each repetition the harness
  verifies the recorded source hashes and the tree hashes of the four built
  `dist` directories that SINT loads at run time. `dist/` is not versioned, so a
  stale build is refused. The Node process receives the two-core budget of
  Section 4.4. `scripts/exp25_sint_runner.mjs` times one
  `await PolicyGateway.intercept(request)` per measured step. It uses the exp-20
  gateway configuration (an in-memory token resolver and a local
  `RevocationStore` preloaded with 10,000 identifiers). Tokens are issued and
  delegated before the run.
- **Mapping.** A tick-high mutation uses an already-expired twin token, because
  SINT expresses time only as wall-clock expiry. The parameter is mapped to
  `maxVelocityMps` and `currentVelocityMps`.
- **Agreement.** Each system is compared with its own expected decisions:
  - ZoneCap: allow, deny, or rewrite;
  - SINT: allow or deny, together with the registered denial code for each
    mutation kind:

    | Mutation | SINT denial code |
    |---|---|
    | subject | `TOKEN_SUBJECT_MISMATCH` |
    | asset | `INSUFFICIENT_PERMISSIONS` |
    | operation | `INSUFFICIENT_PERMISSIONS` |
    | parameter-high | `CONSTRAINT_VIOLATION` |
    | tick-high | `TOKEN_EXPIRED` |

    A SINT denial for any other reason is a mismatch.

  The 4,536 parameter-high cases are registered as a semantic difference
  (ZoneCap rewrites them; SINT denies them), not as mismatches.
- **PLC ABAC/NGAC.** Report it as `N/A` with the availability reason unless a
  versioned executable artifact is supplied and frozen before the run. Never
  copy published numbers into measured-result columns.

Stage correspondence (report this table with the results; never report a single
like-for-like speedup without it):

| Stage | ZoneCap reference PEP | Pinned SINT gateway |
|---|---|---|
| Request parse and schema | envelope framing, JSON, schema checks | zod request-schema validation |
| Token acquisition | parsed from the request envelope | in-memory map lookup by `tokenId` (no deserialization) |
| Delegation chain | linkage and attenuation of every link | not re-verified per request; leaf token only |
| Signatures | every chain token, or a verification-cache hit; libsodium (C) | leaf token on every request, no cache; `@noble/ed25519` (JavaScript) |
| Subject binding | authenticated subject equals leaf subject | `agentId` equals token subject |
| Revocation | every chain token identifier, local set | leaf token identifier, `RevocationStore` |
| Context | trusted snapshot lookup and freshness | N/A: physical context is taken from the request |
| Policy | five effects | allow, deny, or escalate tiers; constraint checks |
| Audit | bounded queue enqueue inside the timed region | N/A: no ledger configured, events only |
| Runtime | CPython 3.10 | Node.js (version recorded) |

A ZoneCap speedup greater than 10x over SINT is a bug signal. The audit of
Section 8 must be completed before the result is interpreted. The aggregator
computes pooled p50 and p99 ratios for both ZoneCap configurations and records
`speedup_bug_signal` in `metrics.json`. The development
runs already exceed this ratio. The audit must attribute it stage by stage
before any interpretation: compare `zonecap_cache_miss` with `zonecap_full`,
and the JavaScript signature verification with libsodium.

## 6. End-to-end OpenPLC path (secondary, descriptive)

**Who builds what.** The hardware group implements a server wrapper around the
unmodified `ReferencePEP.decide`, a client, and a frozen OpenPLC program with a
10 ms periodic task. All three are returned for review before the confirmatory
run.

- The wrapper receives envelopes over a wired link, publishes the step's context
  snapshot (ingest), calls `decide`, and forwards an emitted action to OpenPLC.
- Record the transport and whether it is authenticated (for example TLS). An
  unauthenticated transport is acceptable for this descriptive measurement, but
  must be stated.

**Each command** carries a monotonic correlation identifier. Measure at least
100,000 commands per repetition after the same warm-up. Record:

- client send to PEP receipt;
- the PEP decision duration (as in Section 1.1);
- PEP decision to OpenPLC receipt;
- OpenPLC receipt to application or acknowledgement;
- the total, from client send to acknowledgement; and
- the observed OpenPLC scan-period distribution and missed or overrun cycles.

**Arrival process.** The client releases commands at a seeded, uniformly random
phase within the 10 ms scan period. Each record logs its phase relative to the
PLC scan start, so that scan-phase waiting (0 to 10 ms) can be separated from
processing.

**Overrun comparison.** Run the same command stream once with the PEP bypassed.
Report overruns with and without ZoneCap. These quantities are secondary
descriptive metrics. They do not enter the C5 rule and are never combined with
server-side samples.

**Clocks.** If clocks cross hosts, use hardware/PTP synchronization or measure
round trips on one clock. NTP-only one-way subtraction is not acceptable.

Return the end-to-end data as `results/exp22_c5_e2e_<YYYYMMDD>/`. It must
contain the raw per-command records, the configuration, the command, the seeds,
the environment, and a manifest of SHA-256 hashes.

## 7. Result layout and return package

`zonecap.c5.matrix` writes one immutable directory per experiment:

```text
results/<run_id>/
  config.json  command.txt  seed.txt  log.txt  metrics.json
  timer_sanity.json  check_activation.json  negative_controls.json  preflight_stdout.log
  environment_manifest.json  source_manifest.json  decision_mismatches.jsonl  manifest.json
  configurations/<configuration>/repetitions/<seed>.log
  configurations/<configuration>/repetitions/<seed>/
    metrics.json  environment.json  raw_samples_ns.bin.gz  decisions.jsonl.gz
    decision_mismatches.jsonl  audit_summary.json  tegrastats.log  [audit.jsonl.gz]
  configurations/sint/repetitions/<seed>/                                 (exp-25)
    metrics.json  environment.json  raw_samples_ns.bin.gz  sint_decisions.jsonl.gz
    sint_meta.json  runner.log  decision_mismatches.jsonl  tegrastats.log
  propagation/metrics.json  propagation/propagation_delay_ns.bin.gz       (exp-23)
```

An aborted run keeps its directory, including `log.txt` with the `aborted=`
reason.

**File formats.**

- `raw_samples_ns.bin.gz` is the gzip of consecutive little-endian unsigned
  64-bit integers, one per measured decision, in measured order.
- Each line of `decisions.jsonl.gz` is
  `[measured_index, step, expected_effect, [effect, operation, value, child_low, child_high, reason], stage_mask, signatures_verified, cache_hits, all_checks_passed]`.
- The aggregator recomputes every repetition's percentiles from the raw samples
  and refuses to proceed if they differ. Pooled statistics come from the
  concatenated raw samples.

**Run identifiers.** Use `exp22_c5_main_<YYYYMMDD>`, `exp23_c5_ablation_<YYYYMMDD>`,
`exp24_c5_scaling_<YYYYMMDD>`, `exp25_c5_baselines_<YYYYMMDD>`, and
`exp22_c5_e2e_<YYYYMMDD>`.

**The hardware group returns:**

1. the four matrix directories and the end-to-end directory;
2. one commit or patch containing the platform adaptations (Section 2.11), the
   end-to-end wrapper, the client, and the OpenPLC program;
3. a one-page execution note listing every aborted or invalid attempt and every
   deviation;
4. the photographs or console captures of Section 4.3; and
5. a SHA-256 checksum file for the transfer archive.

Do not edit `research/PLAN.md`, `research/CLAIMS.md`, `research/NOTEBOOK.md`, or
`STATE.md`. The research side audits and integrates the returned data.

## 8. Integrity audits and negative controls

**Stop conditions.** Stop interpretation, and retain the run, if any result is
unexpectedly strong. This includes a p99 below the measured timer resolution and
a more-than-10x speedup over SINT.

**Audit before any rerun.** Check and record:

- the raw sample count and its uniqueness;
- the clock source, resolution, and unit conversion;
- the affinity actually applied;
- throttling and frequency drift;
- that the timer boundary is placed as in Section 1.1;
- the activation masks and the signature/cache counts;
- corpus/oracle independence and request-identifier completeness;
- that there are no compiled-out checks, memoized decisions, or replayed
  timestamps;
- the identical common-subset order across baselines; and
- the manifest and source hashes against the pre-run commit.

**Automated preflight controls.** Each must behave as stated before any latency
result is accepted:

1. a forced 5 ms sleep inside `decide` is exposed by the timer;
2. an invalid leaf signature gives `DENY` (`bad_signature`);
3. a revoked chain token gives `DENY` (`revoked`);
4. an out-of-scope parameter gives `REWRITE` inside the leaf interval, and an
   out-of-scope operation gives `DENY`;
5. a stale, missing, or high-risk context gives `DEFER` with only the
   registered `read` hold;
6. a full or a closed audit queue gives `DENY` (`audit_unavailable`) with no
   emission;
7. a deliberately wrong oracle decision is detected as exactly one mismatch; and
8. a non-holder presenting a valid chain gets `DENY` (`subject`) with no hold,
   even against stale context, and leaves the holder's deferral count unchanged.

Diagnostic configurations disable only their named stage, which is visible in
the stage mask. Every other control remains active.

## 9. Acceptance checklist

The handoff is ready for research review only when all items are true:

- [ ] exact Orin NX 8GB, JetPack/L4T, power mode, and topology recorded;
- [ ] `pytest tests/test_c5_*.py` passed on the Jetson, and the corpus
      fingerprint matches;
- [ ] a development dry run (`--development`) of each experiment on the Jetson
      was sent for review before the confirmatory runs;
- [ ] confirmatory runs were made from a clean commit with all frozen hashes
      matching;
- [ ] preflight passed for every experiment;
- [ ] five seeds and five fresh launches are present for every registered
      configuration;
- [ ] each standard launch has 10,000 warm-up decisions plus 100,000 raw measured
      decisions;
- [ ] every exp-22 decision carries the full stage mask and consistent
      signature/cache counts;
- [ ] exp-23 diagnostics are labelled, and the propagation measurement is present;
- [ ] all 15 exp-24 cells are present;
- [ ] exp-25 uses the identical subset and order for all three configurations,
      and its stage table is reported;
- [ ] end-to-end data are kept separate from server-side samples;
- [ ] every mismatch and every invalid or aborted attempt is retained; and
- [ ] manifests and transfer checksums verify.

## 10. Process and review

**Before confirmatory execution:**

1. Build the corpus, run the tests, and execute every experiment once with
   `--development` on the Jetson.
2. Return those directories together with the platform-adaptation commit for
   review.
3. Execute the confirmatory runs from the reviewed commit.

**Execution note.** Record every deviation from this document in the execution
note, with its date and reason.

**Contacts.** The project lead names the research-side reviewer and the hardware
contact when issuing this version. Questions about the protocol go to the
research-side reviewer before execution, not after results are seen.

**Indicative cost on the target:**

| Item | Estimate |
|---|---|
| Corpus build | a few minutes; about 250 MB of disk |
| exp-22 | about 10 minutes |
| exp-23 | about 30 minutes |
| exp-24 | about 1 hour (15 configurations) |
| exp-25 | about 1–1.5 hours; pinned SINT dominates, at milliseconds per decision |
| End-to-end path | as designed by the hardware group |

## Appendix A. Changes from version 1.0

| Item | v1.0 | v1.1 | Audit finding |
|---|---|---|---|
| System under test | not defined; hardware group could implement it (v1.0 L80–82) | frozen reference PEP, wire format, stores, and harness delivered (Sections 2 and 5) | B1 |
| Caching and optimization | `cache_miss` implied caches without defining them | one verification cache defined; nothing else reused; `cache_miss` clears it; no optimized path registered (Sections 2.1 and 2.4) | B2 |
| A1/A2 decision rules | diagnostics without criteria | preregistered criteria and restricted wording (Sections 1.3 and 1.4) | B3 |
| Occupancy | p99/10 ms presented as a second threshold | kept, but disclosed as derived; scan-cycle quantities registered as secondary (Sections 1.2 and 6) | B4 (option a) |
| Timing workload | "cycle the corpus"; DEFER/ATTENUATE never timed | exp-12 corpus with all five effects; stratified reporting (Section 3) | I1 |
| Context source | unspecified | in-process snapshot; ingest outside the timed path (Section 2.6) | I2 |
| SINT comparison | totals only | stage table, runner, and mapping delivered (Section 5) | I3 |
| Propagation timing | clock rule missing | same-host monotonic method, or PTP/round trip (Section 5) | I4 |
| End-to-end arrival | unspecified | seeded random phase with phase logged; bypass overrun comparison (Section 6) | I5 |
| Runtime settings | unspecified | GC rules, `gc.freeze()` recorded, no measurement-only settings (Section 2.9) | I6 |
| Binary format | unspecified | little-endian uint64 (Section 7) | minor |
| Seed file | `seeds.txt` | `seed.txt`, the repository convention (Section 7) | minor |
| Policy wording | "IEC 62443 policy tables" | frozen exp-07 table: source-derived topology plus declared overlay (Section 3) | minor |
| Throttling | undefined | operational definition (Section 4.3) | minor |
| Configuration order | unspecified | seed-major with rotation (Section 5) | minor |
| Keys | unspecified | deterministic test keys; no signing key on the PEP (Section 2.10) | minor |
| Process | no review step | development dry run on the Jetson, review, then confirmatory runs (Section 10) | process |
| Policy-count scaling | extra policies never requested | 1,000 anchored, registered synthetic grants; requests rotate across all P (Sections 3.2 and 5) | B3, pre-delivery review |
| Presenter binding | not specified | authenticated subject bound before context; deferral bound scoped to the holder (Sections 2.3 and 2.8) | B1, pre-delivery review |
| SINT controls | none | two-core budget, enforced affinity, denial-code and `dist` tree-hash checks (Sections 4.4 and 5) | I3, pre-delivery review |

## Appendix B. Quick start on the Jetson

```text
# 1. Environment (JetPack 6.x, Python 3.10)
python3 -m venv ~/zonecap-c5 && . ~/zonecap-c5/bin/activate
pip install pynacl==1.5.0 pytest
# 2. Corpus and tests
PYTHONPATH=src python3 -m zonecap.c5.corpus build --output-dir build/c5_corpus
PYTHONPATH=src python3 -m pytest -q tests/test_c5_pep.py tests/test_c5_harness.py tests/test_c5_corpus.py
# 3. SINT (exp-25) and Redis (exp-23)
#    run the prepare_command in configs/c5/exp25_c5_baselines.json (Node.js 22+)
#    install redis-server, then: taskset -c 5 redis-server --port 6379 --save "" --appendonly no
export ZONECAP_C5_SINT_REPO=/opt/zonecap/sint-protocol
# 4. Development dry run, then review, then the confirmatory runs from a clean commit
PYTHONPATH=src python3 -m zonecap.c5.matrix --config configs/c5/exp22_c5_main.json \
    --corpus-dir build/c5_corpus --output-dir results/dev_exp22_c5_main_<YYYYMMDD> --development
```

Dry runs on the Jetson use the full registered counts, so that memory,
thermal, and audit-backpressure behavior is exercised at full scale. The
`--development-scale` option divides the decision counts for quick
research-side checks only, and is refused without `--development`.
