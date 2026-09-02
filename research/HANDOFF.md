# Handoff

type: regular
early reason: N/A
runs: 22 S2 claim runs (+2 S1 infrastructure/baseline runs); exploratory: 3 logged activities, none used as claim evidence; GPU-hours: 0

The completed subset is exp-01 through exp-21 plus local exp-26. Exp-22 through exp-25 remain external pending with the hardware group and are intentionally excluded so that hardware scheduling does not block review. Consequently, this handoff can read C1--C4 and the C5 infrastructure sanity, but cannot read the Jetson/OpenPLC performance claim.

## Per claim

### C1 [core] "Under conjunctive ZoneCap caveats and authority-preserving runtime effects, if capability c' attenuates c, then for any fixed plant model, initial-state set, disturbance set, and finite horizon H, the physical reachable set induced by c' is a subset of that induced by c."

- reading: supports
- runs: `exp01_exact_1d_20260831` closed 8/8 registered proof obligations and found 0 inclusion violations over 2,756,250 exact horizon checks on 393,750 one-dimensional models; it retained one counterexample to the stronger, unregistered same-raw-request relation. `exp02_caveat_mutation_20260831` killed 14/14 unsafe syntax/combiner/default mutants with retained counterexamples and found 0 registered C1 counterexamples. `exp03_mimo_history_20260831` used all five preregistered seeds (104729, 130363, 155921, 196613, 262147): every seed had 0 violations, for 720 MIMO horizon checks, 400 history horizon checks, and 8,854 child-trace membership checks in aggregate; 2/2 widening controls were detected. `exp04_effect_closure_20260831` found both expected horizon-1 counterexamples when the rewrite/defer obligations were removed, then 0 restored trace/reachable-set violations while observing all five effects. `exp05_common_subset_20260901` found 0 cross-adapter decision/reachable-set mismatches over 72 request pairs and 63 adapter/plant/horizon checks. `exp06_c1_sanity_20260901` matched 9/9 expected sanity patterns and detected both syntactic and physical widening.
- seeds/variance: exp-03 reports every one of five seeds separately, all at zero violations; the proof, exact enumeration, baseline, and sanity runs are seedless, so sampling variance is not applicable to them.
- alternatives ruled out: A1 by exp-01's syntax-to-emission argument and exp-02's 14/14 unsafe-mutant kill; A2 by exp-03's exact coupled MIMO and history-dependent checks across all five seeds; A3 by exp-04's removal/restoration counterexamples with all five effects observed. Remaining: the general theorem is a reviewed argument and executable finite-model audit, not a mechanized proof; its conclusion is conditional on the registered effective-authority, rewrite-closure, trusted-context, and parent-admissible-stutter premises.
- bug checks: the same-request REWRITE counterexample was retained rather than hidden; both MIMO/history widening controls fired; empty-action reachability was repaired before exp-06 freeze and then covered by a regression sanity case.
- confirmatory run (if promoted from explore): N/A; no exploratory result was promoted.

### C2 [core] "For two held-out IEC 62443-aligned reference architectures, ZoneCap compilation is decision-equivalent to an independent zone/conduit policy oracle while every depth-1 and depth-2 delegation preserves or narrows zone, conduit, asset, action, parameter, time, mode, and pre-action-sequence authority."

- reading: supports
- runs: `exp07_heldout_equivalence_20260901` evaluated 58,968 seedless cases (42,120 CPwE/CIP Security; 16,848 ENISA railway), including 54,432 single-field mutations, with 0 compiler-oracle mismatches and 0 failures across 672 delegation-dimension checks; the perfect-result audit passed. `exp08_source_generation_ablation_20260901` retained 0 mismatches, killed 10/10 check-removal mutants with the generated corpus versus 0/10 with six handwritten happy paths, and passed 4/4 source-provenance probes. `exp09_depth_path_widening_20260901` matched all 24 depth/path cases, rejected all 32 widening attempts across eight authority dimensions, and repeated 672 legal checks with 0 failures. `exp10_c2_baselines_20260901` found 0 mismatch on each baseline's expressible subset, while the OPC UA role, PLC ABAC, and pinned-SINT projections left 40,824, 18,144, and 28,728 full-policy mutations unrestricted. `exp11_c2_sanity_20260901` matched all 22 compile/decision boundary cases, including 9 expected fail-closed compile rejections.
- seeds/variance: all C2 runs are exact, table-generated, seedless enumerations; sampling variance is not applicable.
- alternatives ruled out: A1 by exp-08's generated-versus-handwritten mutation contrast and source-provenance probes; A2 by exp-09's depth-0/1/2 multi-conduit cases, 32 localized widening attempts, and 672 legal-delegation checks. Remaining: compiler and oracle are separate implementations but consume a common human-authored policy-table transcription, so a shared source-interpretation error is not ruled out; the two case studies show alignment with the encoded source policies, not IEC 62443 certification or completeness.
- bug checks: because agreement was perfect, exp-07 audited source/table/code hashes, dependency separation, mutation-category coverage, and check-removal mutants. Exp-08 changed source grants and regenerated outputs; exp-09 independently localized each rejected dimension.
- confirmatory run (if promoted from explore): N/A; the held-out runs were preregistered, not promoted exploration.

### C3 [S1] "A runtime enforcement semantics with ALLOW, DENY, ATTENUATE, REWRITE, and DEFER preserves C1 whenever rewrites remain within the effective capability and deferrals are modeled as parent-admissible stutter transitions."

- reading: supports
- runs: `exp12_effect_automaton_20260901` checked 58,968 held-out one-request traces plus 4,536 five-step composed traces (22,680 composed policy steps), reached all five effects, and recorded 0 authority-safety, parent-realizability, trace-inclusion, defer-stutter, or bounded-deadlock violations; 5/5 negative-control mutants were killed. `exp13_deny_only_ablation_20260901` used the same 81,648 policy steps: deny-only had 0 safety violations but falsely blocked 13,608 bounded rewrites (16.67% of all steps; 60% of rich-semantics safe-service opportunities) and lost 9,072 recoverable attenuation/deferral decisions; 3/3 mapping mutants were killed. `exp14_exhaustive_sequences_20260901` enumerated 492,156 words and 492,030 transitions through horizon 5 over 126 scopes, covering all 25 effect bigrams and 125 trigrams with 0 registered violations/deadlocks and killing 3/3 sequence mutants; the named-path baseline covered only 4 bigrams and 3 trigrams and killed 0/3. `exp15_c3_baselines_20260901` mapped 3/5 Lanotte/Roop effects exactly and, at pinned SINT commit `2461a911b8c3d7ed9da3f7662b33678f688eb826`, 2/5 exactly, 2/5 partially, and 1/5 not at all; all 13,608 ZoneCap rewrites projected to SINT constraint-violation denial. `exp16_effect_sanity_20260901` matched 5/5 failure/recovery patterns, retained five authorized holds, and exposed the expected unauthorized-output counterexample when rewrite membership alone was bypassed.
- seeds/variance: these are seedless corpus enumerations, bounded exhaustive checks, and exact sanity cases; sampling variance is not applicable.
- alternatives ruled out: A1 by exp-13, which shows equal safety but a measured loss of bounded safe service under deny-only; A2 by exp-14's full length-0-through-5 word enumeration and sequence-mutant contrast. Remaining: the checks establish the registered bounded semantics, not unbounded progress, asynchronous distributed execution, sensor integrity, or correctness of the physical model/context provider; the preservation statement remains conditional on rewrite membership and admissible holds.
- bug checks: exp-12 independently recounted unique trace IDs and killed one mutant for each critical effect premise; exp-14 audited full n-gram coverage; exp-16 removed only the rewrite-membership premise and recovered the expected counterexample.
- confirmatory run (if promoted from explore): N/A; no exploratory result was promoted.

### C4 [S1] "ZoneCap revocation and deterministic conflict resolution prevent post-revocation execution, privilege union across concurrent holders, and deadlock in the preregistered bounded multi-principal model."

- reading: refutes
- runs: `exp17_c4_interleavings_20260901` enumerated 793,800 words/793,797 transitions through bound 5 for 2--4 holders, with 26,038 executions, 4,534 conflict resolutions, 1,590 timeouts, 0 registered violations, and 4/4 mutants killed. `exp18_c4_convergence_20260902` then closed the exact graphs at depths 6/8/10 (1,110 states, 10,576 cycle edges, 461 states beyond bound 5), with 0 post-delivery revocation, union, determinism, or deadlock violations and a detected deadlock control. However, `exp19_c4_adversarial_scheduler_20260902` found 8 post-issuance revocation executions: delay 0 had 0, while each fair delay-1 and delay-2 set had 4 across five scenarios. All 15 schedules were fair and delivered every revocation. `exp20_c4_sint_baseline_20260902` independently showed the same freshness boundary in pinned SINT: one pre-delivery use was allowed and an enqueued revoked request resolved approved, although a fresh gateway recheck denied. `exp21_c4_sanity_20260902` matched 4/4 local terminal-state cases but does not erase the exp-19 counterexample.
- seeds/variance: all C4 runs are seedless exact enumerations or fixed schedules; sampling variance is not applicable.
- alternatives ruled out: A1 is ruled out within the modeled state machine by exp-18's exact graph closure. A2 is not ruled out; exp-19 instead demonstrates that the zero-violation result depends on a centralized/delivery-relative freshness boundary. The issuer-side epoch-fence diagnostic blocked all 8 stale executions, but it is an unregistered mitigation diagnostic, not evidence for the original claim.
- bug checks (refutation): exp-19 separated issuance-time from delivery-time predicates; verified all schedules were fair, all revocations were delivered within the bound, terminal revoked requests were not pending, and post-delivery/union/determinism/deadlock counters stayed zero; it also matched frozen hashes. The epoch-fence diagnostic killed exactly the 8 stale executions, and exp-20 reproduced the boundary in actual pinned SINT modules. These checks localize the negative result to revocation freshness rather than a disabled checker or scheduler nontermination.
- confirmatory run (if promoted from explore): N/A; exp-19 was preregistered.

### C5 [S1] "On the approved OpenPLC/Jetson testbed, ZoneCap's p99 decision latency is at most 1 ms and consumes at most 10% of a 10 ms PLC scan cycle while enforcing the registered policy set."

- reading: inconclusive
- runs: the approved-testbed main, ablation, scaling, and baseline runs exp-22--25 have not returned. `exp26_c5_timer_sanity_20260902` is explicitly x86 infrastructure-only: it retained 100,000 samples each for timer calibration, empty calls, and the full sanity path, plus 100 forced-slow samples; empirical timer resolution was 90 ns, empty/full/forced-slow p99 was 210 ns/19,326 ns/6,639,755 ns in the required order, CPU-0 pin and restoration were verified, and 6/6 disabled-check mutants were killed. Those numbers do not measure the approved Jetson/OpenPLC path and therefore do not test either C5 threshold.
- seeds/variance: exp-26 is a single seedless local process sanity, not the five fresh target-hardware process launches required by C5; no target repetition variance exists yet.
- alternatives ruled out: neither A1 (cache/check omission) nor A2 (toy policy count) is ruled out on the approved hardware. Exp-26 only establishes that the local harness can resolve the clock, retain samples, detect a forced delay, verify affinity, and flag disabled registered stages.
- what would sharpen it: return and audit exp-22's five full-path Jetson/OpenPLC repetitions, exp-23's cache/signature/revocation/audit configurations, exp-24's 1/10/100/1000-policy by depth-0/1/2 scaling matrix, and exp-25's fair baseline measurements or explicit N/A entries, all under the frozen `hardware_delivery/exp_requirements.md` contract.
- confirmatory run (if promoted from explore): none; no approved-testbed confirmatory result exists.

## Deviations from PLAN

- S1's active environment lacked CasADi, so the registered exact reachability work used dependency-free interval/polytope enumeration; this did not change the claim protocol.
- The held-out public source bytes were first persisted on 2026-09-01 rather than 2026-08-31. Direct Cisco CLI retrieval returned HTTP 403, so the same CPwE/CIP Security guide was frozen from Rockwell Automation's official literature server before encoding or execution.
- Academic-search tooling was unavailable for exp-15; the registered DOI/arXiv/DBLP and author-preprint/raw-pinned-source fallback was used, with unavailable runtime metrics retained as N/A.
- The human approved an NVIDIA Jetson Orin NX 8GB Developer Kit and hardware-team execution, replacing S1's AGX Orin-class target assumption. Exact model/topology reporting is required and no AGX equivalence will be claimed.
- At human direction, local exp-26 ran before external exp-22--25. This handoff interprets the completed local subset and leaves C5 inconclusive rather than waiting for the hardware team.

## Doubts

- C1's general result is conditional and not mechanized. The executable checks cover large but finite registered classes; they cannot rescue an omitted theorem premise or an inaccurate plant/context model.
- C2's independent implementations share one manually encoded source-policy table. Mutation/provenance audits reduce implementation leakage, but no second policy encoder or domain-expert adjudication rules out a shared interpretation error. “IEC 62443-aligned” must not become an IEC conformance claim.
- The seven held-out source items excluded as nondecision metadata need a defensible appendix-level mapping, even though `unsupported_decision_constructs` is zero for the encoded decision tables.
- C3's exhaustive result is exhaustive only for the abstract five-symbol alphabet, 126 scopes, and horizon 5. It does not establish unbounded/distributed liveness or safety under stale/malicious context.
- C4 as written is false under issuance-relative revocation. A defensible successor would need an explicit atomic freshness contract or issuer epoch fence and a fresh confirmatory run; the diagnostic fence in exp-19 must not be promoted as confirmatory evidence.
- C2/C3 baselines are fair projections/source-grounded semantic mappings on shared inputs, not equivalent end-to-end industrial deployments. Performance comparisons remain absent.
- C5 has no approved-hardware evidence. Exp-26 must remain a harness sanity result regardless of its sub-millisecond local number.

## Not run

- exp-22: external pending; five target-hardware full-path repetitions await hardware-team harness freeze and execution.
- exp-23: external pending; cache/check-path ablations await the same target.
- exp-24: external pending; policy-count/delegation-depth scaling awaits the same target.
- exp-25: external pending; target-hardware baseline measurements await the same target, with unavailable executable baselines required to remain N/A.
