# Plan

## Protocol — fixed before any confirmatory run

### Metrics

- **C1:** proof obligations discharged; trace/reachable-set inclusion violations (must be 0); counterexamples with full model/token/seed retained; exact reachable-set containment at every horizon.
- **C2:** compiler–oracle decision agreement; accepted privilege-widening mutations (must be 0); unsupported architecture constructs; per-dimension attenuation coverage.
- **C3:** trace-inclusion and safety violations (must be 0); deadlocks; effect coverage; raw-request false-block rate and edit distance relative to deny-only enforcement.
- **C4:** post-revocation executions, permission-union violations, deadlocks (all must be 0); resolution steps and timeout rate.
- **C5:** decision latency p50/p99/max, scan-cycle occupancy, throughput, memory, token bytes, and exact decision agreement before/after optimization.

### Splits (no learned component)

- **Development only:** `examples/dev_tank.json` and `examples/dev_robot_cell.json`. These may be changed to debug infrastructure and can never support a claim.
- **Validation:** a synthetic three-zone packaging cell used to debug the compiler/oracle interface. Results are exploratory.
- **Held-out test A:** Cisco CPwE/CIP Security zone-and-conduit architecture, source frozen to the public design guide available at `https://www.cisco.com/c/en/us/td/docs/solutions/Verticals/CPwE/5-1/CIP_Security/DIG/` on 2026-08-31.
- **Held-out test B:** ENISA, *Zoning and Conduits for Railways*, February 2022, source frozen to `https://www.enisa.europa.eu/sites/default/files/publications/Zoning%20and%20Conduits%20for%20Railways%20-%20Security%20Architecture.pdf` on 2026-08-31.
- Test policies will be encoded once from the frozen sources, hashed, and then locked. The oracle is a separate implementation over the source policy table, not a call to the ZoneCap compiler. Test requests are the full valid cross-product plus every single-field boundary mutation; no case is removed after execution.

### Seeds and repetitions

- S1 smoke seed `7` is development-only and must not appear as confirmatory evidence.
- S2 property/model checks use all five preregistered seeds: `104729`, `130363`, `155921`, `196613`, `262147`. No seed selection.
- Exact enumeration/proof runs are seedless and must be marked `seed: none`.
- Performance uses five fresh process launches per configuration, 10,000 warm-up decisions followed by 100,000 measured decisions. Report every repetition and the aggregate; pin CPU affinity and record clock/power settings.

### Evaluation procedure

1. Freeze code, test-source snapshots, generated policy tables, request generator, oracle, metrics, and environment manifest before any held-out run; record hashes in the run directory.
2. Run development and validation only until infrastructure is stable. Any protocol change after a held-out result is a `deviation` in `NOTEBOOK.md`; the affected result becomes exploratory and requires fresh cases/seeds.
3. C1/C3 are not accepted from randomized testing alone: a reviewed proof or mechanized proof is required, with counterexample search used only as falsification support.
4. Baselines receive identical requests and physical context. Compare static RBAC, PLC ABAC, CPAC-style model-derived policy, Lanotte/Roop-style runtime enforcement, and SINT at pinned versions where runnable. Do not equate their different threat models; mark unavailable dimensions `N/A`.
5. Latency excludes client network transit but includes parsing, token verification, revocation lookup, context lookup, decision, and audit enqueue. Also report end-to-end OpenPLC measurements separately.
6. “Too good” triggers: perfect held-out agreement before mutation audit, p99 below timer resolution, or >10× baseline speedup. Stop and check leakage, dead-code elimination, disabled checks, and clock methodology.

### Compute and hardware

- Default compute remains at most 4×A100-80G, GPUs 0–3. No planned experiment requires a GPU; every row estimates `0 GPU-h`.
- CPU/model-checking budget is approximately 85 CPU-h. It is guidance, not a hard limit.
- C5 needs one Jetson AGX Orin-class target and one OpenPLC-capable PLC/Raspberry Pi target for at most two days. This is non-default hardware and requires human approval. Fallback: isolated x86 OpenPLC software-in-the-loop; the Jetson-specific C5 claim would then be untestable.

## Matrix

Rows run top to bottom. The first row is the cheapest experiment able to refute the first core claim.

| exp | claim | type | design | strongest fair baseline | metric | est. GPU-h / other cost | tag | status |
|---|---|---|---|---|---|---|---|---|
| exp-01 | C1 | main | Audit and complete the syntactic-caveat → emitted-transition → trace/reachable-set proof; start with exact 1D LTI intervals. | Semantic subset lemma (to expose tautology risk) | proof obligations; counterexample or closed proof | 0 / 4 CPU-h | [S1] | done: closed conditional proof; exact 1D audit passed; same-request strengthening refuted and excluded from C1 |
| exp-02 | C1 | ablation:A1 | Keep token syntax independent of reachability; mutate each caveat combiner/default and seek minimal counterexamples. | SINT/Dodson documented attenuation rules | mutation kills; inclusion violations | 0 / 3 CPU-h | [S1] | done: all unsafe mutants killed; positive OR/first-applicable remained monotone but changed policy semantics |
| exp-03 | C1 | ablation:A2 | Lift to MIMO polytopes and state/history-dependent enabled-action relations; all five seeds. | Scalar interval result | per-seed/per-horizon inclusion | 0 / 10 CPU-h | [S1] | done: exact 2D polytopes and exhaustive history-dependent traces passed for every seed/horizon; both widening controls detected |
| exp-04 | C1 | ablation:A3 | Remove rewrite closure and defer-stutter obligations one at a time; then restore them. | Suppression-only semantics | minimal counterexamples; restored violations=0 | 0 / 3 CPU-h | [S1] | done: both removed obligations produced horizon-1 counterexamples; all restored configurations and suppression-only had zero violations |
| exp-05 | C1 | baseline | Instantiate the common expressible subset of ZoneCap, Dodson/CHERI Macaroons, and SINT token scope on the same plants. | SINT v0.2; Dodson schema | proof-obligation coverage; reachable inclusion | 0 / 4 CPU-h | [S1] | done: invariant-resource/action-subset/upper-bound common subset agreed on all requests and exact plant horizons; proof-only dimensions remain ZoneCap delta |
| exp-06 | C1 | sanity | Identity child, empty action set, signed A/B, zero/nonzero disturbance, and deliberately widened child. | N/A | expected pass/fail pattern | 0 / 1 CPU-h | [S1] | done: all nine expected patterns matched; legal cases passed and widened child was rejected plus physically detected |
| exp-07 | C2 | main | Compile held-out A/B and compare every request/mutation with independent oracle. | OPC UA roles + PLC ABAC | agreement; unsupported constructs | 0 / 8 CPU-h | [S1] | done: 58,968 table-generated decisions had zero compiler-oracle mismatches; all 672 depth-1/2 dimension checks passed; the frozen-hash/dependency/check-removal audit passed |
| exp-08 | C2 | ablation:A1 | Generate full cross-product and single-field mutations from frozen source tables, not hand-written compiler fixtures. | Hand-authored fixtures | decision agreement; mutation coverage | 0 / 4 CPU-h | [S1] | done: the 58,968-case table corpus killed 10/10 check-removal mutants while six happy-path fixtures killed 0/10 despite both having zero decision mismatches; all four source-grant provenance probes passed |
| exp-09 | C2 | ablation:A2 | Exercise depths 0/1/2, multi-conduit paths, and one attempted widening per authority dimension. | Depth-0 only | accepted widenings; dimension coverage | 0 / 3 CPU-h | [S1] | done: both direct-denied multi-conduit paths matched the oracle in all 24 depth-0/1/2 cases; all 32 dimension-localized widening attempts were rejected and all 672 legal-delegation checks passed |
| exp-10 | C2 | baseline | Expressiveness and decision comparison against PLC ABAC, OPC UA roles, and SINT industrial profiles. | SINT pinned commit; PLC ABAC | agreement by scenario; N/A dimensions | 0 / 5 CPU-h | [S1] | done: all projections had zero false denies and 100% agreement on their fully expressible scenario subsets; on the full 58,968-case policy, OPC UA roles, PLC ABAC, and pinned-SINT projections left 40,824, 18,144, and 28,728 N/A-dimension mutations unrestricted |
| exp-11 | C2 | sanity | Duplicate/unknown zones, wrong conduit endpoints, empty scopes, boundary values, expired windows. | N/A | expected compile rejection/decision | 0 / 1 CPU-h | [S1] | done: all 22 compile/decision cases matched, including nine fail-closed compile rejections, zero-authority empty scopes, inclusive parameter/time boundaries, and expired-window denial |
| exp-12 | C3 | main | Compose the five-effect automaton with compiled capabilities and bounded-check all held-out traces. | Lanotte edit automaton; SINT tiers | inclusion/safety/deadlock; effect coverage | 0 / 6 CPU-h | [S1] | done: all 58,968 held-out one-request traces and 4,536 five-step composed traces reached the expected effects with zero safety, parent-realizability, trace-inclusion, stutter, or bounded-deadlock violations; all five negative controls were killed |
| exp-13 | C3 | ablation:A1 | Replace attenuate/rewrite/defer with deny-only behavior under identical requests. | Deny-only enforcer | false-block rate; safety; edit distance | 0 / 3 CPU-h | [S1] | done: deny-only had zero safety violations but falsely blocked 13,608 safe rewrites (16.67% of all 81,648 policy steps; 60% of safe-service opportunities), affected every composed trace, and lost 9,072 recoverable attenuate/defer decisions |
| exp-14 | C3 | ablation:A2 | Exhaustive bounded request/context sequences rather than named attack traces. | Hand-picked traces | states/transitions covered; violations | 0 / 6 CPU-h | [S1] | done: 492,156 words and 492,030 transitions covered all 25 effect bigrams and 125 trigrams with zero registered violation; the named path covered only 4 bigrams/3 trigrams and missed all three sequence-trigger mutants |
| exp-15 | C3 | baseline | Re-express common properties in Lanotte/Roop enforcement and SINT decision tiers. | Lanotte artifact; SINT | property/effect coverage; decision delta | 0 / 5 CPU-h | [S1] | done: Lanotte/Roop exactly maps pass/suppress/correct but has no capability-attenuate/defer analogue; pinned SINT exactly maps allow/deny, partially maps delegation-time attenuation/approval escalation, and maps 13,608 runtime rewrites to constraint-violation deny; unavailable hardware runtime metrics remain N/A |
| exp-16 | C3 | sanity | Force unauthorized rewrite, missing hold action, lost context, and approval timeout; require known counterexamples/fail-closed behavior. | N/A | expected counterexample/decision | 0 / 1 CPU-h | [S1] | done: all five fixed patterns matched; invalid rewrite/hold failed closed, lost context and approval timed out as DEFER/DEFER/DENY, timely recovery produced DEFER/ALLOW, and bypassing rewrite membership retained the expected counterexample |
| exp-17 | C4 | main | Model revocation plus deterministic conflict order for 2–4 holders under all bounded interleavings. | SINT revocation + M-of-N approval | 3 safety violations; deadlocks; steps | 0 / 5 CPU-h | [S1] | done: 793,800 words/793,797 transitions across 2-4 holders produced 26,038 executions, 4,534 conflict resolutions, and 1,590 approval timeouts with zero post-revocation execution, permission union, deterministic-order, or deadlock violation; 4/4 mutants killed |
| exp-18 | C4 | ablation:A1 | Increase bound until state graph repeats or resource limit; exploit symmetry reduction. | Initial bound | new cycles/deadlocks | 0 / 4 CPU-h | [S1] | done: exact 2/3/4-holder graphs converged by depths 6/8/10 at 30/162/918 states; ordinary-holder symmetry reduced 1,110 exact states to 370 classes; 10,576 cycle edges and 461 post-bound-5 states introduced zero registered safety, determinism, or deadlock violation |
| exp-19 | C4 | ablation:A2 | Replace benign scheduler with adversarial fair schedules and delayed revocation delivery. | Central FIFO scheduler | violations by schedule/delay | 0 / 4 CPU-h | [S1] | done: registered C4 counterexample—FIFO had 0 issuer-relative post-revocation executions, but one- and two-turn fair delivery delays each exposed 4 stale executions (8 total); delivered-state safety, tuple ownership, determinism, and deadlock checks remained clean, while an additional issuer-side epoch fence blocked all 8 |
| exp-20 | C4 | baseline | Same conflict/revocation traces against SINT's pinned implementation. | SINT pinned commit | decision/state-machine delta | 0 / 3 CPU-h | [S1] | done: pinned SINT directly provided delivered-store revocation denial, 2-of-3 approval, duplicate-vote suppression, timeout, and fresh gateway recheck; its stale local store allowed pre-delivery use, an enqueued revoked request still resolved approved, and two same-resource approvals had no cross-request winner, so atomic execution safety requires a consumer recheck/integration contract |
| exp-21 | C4 | sanity | Immediate revoke, duplicate revoke, simultaneous equal-priority commands, and permanent missing approval. | N/A | expected terminal state | 0 / 1 CPU-h | [S1] | todo |
| exp-22 | C5 | main | Five isolated repetitions on approved Jetson/OpenPLC path with full checks enabled. | SINT; PLC ABAC | p50/p99/max; occupancy; equivalence | 0 / 2 hardware-days | [S1] | todo |
| exp-23 | C5 | ablation:A1 | Cold/warm cache, signed/unsigned diagnostic, local/remote revocation, audit enabled/disabled diagnostic. | Full path | latency breakdown; equivalence | 0 / included above | [S1] | todo |
| exp-24 | C5 | ablation:A2 | Scale 1/10/100/1000 policies and delegation depth 0/1/2. | Single-policy path | latency/memory/token bytes | 0 / included above | [S1] | todo |
| exp-25 | C5 | baseline | Same request corpus on SINT, PLC ABAC/NGAC, and ZoneCap. | SINT pinned commit | latency and decision coverage | 0 / 1 hardware-day | [S1] | todo |
| exp-26 | C5 | sanity | Timer calibration, empty function, forced slow check, disabled-check detector, CPU affinity verification. | Empty-call lower bound | expected timing order | 0 / 1 CPU-h | [S1] | todo |

Total estimated GPU-h: **0**. Beyond default compute: **exp-22–exp-25 require non-default Jetson/OpenPLC hardware approval; all other work fits CPU/default resources.**
