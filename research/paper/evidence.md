# Evidence map

Only C1, C6, and C7 are accepted claims. C4 is included solely as a rejected claim/negative result, and C5 solely as an insufficient claim/deployment limitation. Internal evidence tags `E01`--`E26` are used in `draft.md`; they are drafting traceability marks, not citation numbers.

## Forward map: claim to displays and runs

### C1 [accepted]

> Under conjunctive ZoneCap caveats and authority-preserving runtime effects, if capability c' attenuates c, then for any fixed plant model, initial-state set, disturbance set, and finite horizon H, the physical reachable set induced by c' is a subset of that induced by c.

- Displays: F1, F2, T1.
- Direct runs: `exp01_exact_1d_20260831`, `exp02_caveat_mutation_20260831`, `exp03_mimo_history_20260831`, `exp04_effect_closure_20260831`, `exp05_common_subset_20260901`, `exp06_c1_sanity_20260901`.
- Formal source: `research/monotonicity_theorem.md`.
- Evidence tags: E01--E06.
- Mandatory scope text: all six registered obligations; request-abstracted rather than same-request emissions; fixed/common plant uncertainty; no model-mismatch or compromised-context guarantee.

### C6 [accepted; narrowed from C2]

> For the frozen CPwE/CIP Security matrix and ENISA landside-signalling zone/conduit subgraph, augmented with the preregistered source-independent action, parameter, time, mode, and pre-action-sequence overlay, ZoneCap is decision-equivalent to the separate table oracle over the complete generated corpus, and every registered depth-1 and depth-2 delegation preserves or narrows all eight authority dimensions.

- Displays: F1, F3, T2, T3.
- Direct runs: `exp07_heldout_equivalence_20260901`, `exp08_source_generation_ablation_20260901`, `exp09_depth_path_widening_20260901`, `exp10_c2_baselines_20260901`, `exp11_c2_sanity_20260901`.
- Source/protocol: `research/heldout/exp07/source_manifest.json`, `research/heldout/exp07/ENCODING_PROTOCOL.md`, and `research/heldout/exp07/policy_tables.json`.
- Evidence tags: E07--E11.
- Mandatory scope text: the five behavior/context dimensions are an evaluation overlay and target-asset identifiers are deterministic per-zone encoding fields; ENISA coverage is the landside-signalling subgraph; common-table source interpretation is not independently replicated; no IEC certification claim.

### C7 [accepted; narrowed from C3]

> The registered actuation-event runtime semantics with ALLOW, DENY, ATTENUATE, REWRITE, and DEFER preserves C1 when every emitted rewrite and hold is within the effective capability and parent-realizable, and every deferral is a parent-admissible stutter transition.

- Displays: F1, F4, T4, T5.
- Direct runs: `exp12_effect_automaton_20260901`, `exp13_deny_only_ablation_20260901`, `exp14_exhaustive_sequences_20260901`, `exp15_c3_baselines_20260901`, `exp16_effect_sanity_20260901`.
- Semantic sources: `research/c3_effect_automaton_protocol.md`, `research/effect_refinement_audit.md`, and `research/monotonicity_theorem.md`.
- Evidence tags: E12--E16.
- Mandatory scope text: actuation-event semantics; bounded resolution and sequence horizons; registered `read` hold; no fixed-tick, asynchronous distributed, or unbounded-liveness claim; constructed-corpus service fractions are not field prevalence.

### C4 [rejected; required negative result]

- Displays: F5, T6.
- Runs: `exp17_c4_interleavings_20260901`, `exp18_c4_convergence_20260902`, `exp19_c4_adversarial_scheduler_20260902`, `exp20_c4_sint_baseline_20260902`, `exp21_c4_sanity_20260902`.
- Evidence tags: E17--E21.
- Allowed statement: delivered-state safety, tuple ownership, deterministic ordering, and bounded progress remained clean in the registered exact model, but fair delayed delivery admitted eight issuance-relative stale executions and refuted original C4.
- Forbidden statement: that ZoneCap prevents post-revocation execution without an atomic delivery or freshness contract. The epoch-fence result is diagnostic only.

### C5 [insufficient; required limitation]

- Display: T7.
- Run: `exp26_c5_timer_sanity_20260902` only; exp-22--25 have no result directories.
- Evidence tag: E26.
- Allowed statement: the x86 harness distinguished timer, empty, full-sanity, and forced-slow paths; pinned/restored CPU affinity; and detected every registered disabled-check mutant.
- Forbidden statement: any Jetson/OpenPLC latency, scan-cycle occupancy, throughput, memory, or C5 threshold conclusion.

## Reverse map: display to claim and evidence

| Display | Planned message | Claim/boundary served | Run or formal source |
|---|---|---|---|
| F1 | Zone/conduit table -> compiler -> root capability -> depth-1/2 attenuation -> five-effect decision -> physical emission -> plant trace, with proof obligations marked at interfaces | C1, C6, C7 | exp-01, exp-07, exp-12; theorem and protocols |
| F2 | Three-step refinement: syntactic scope inclusion -> request-abstracted emission inclusion -> trace/reachable-set inclusion; exact parent/child reachable intervals for three plants from the common-subset pair (premise-removal counterexamples are reported in text) | C1 | exp-01--06 |
| F3 | Frozen-source corpus generation and independent compiler/oracle paths, with case, mutation, delegation, and widening outcomes | C6 | exp-07--11 |
| F4 | Five-effect actuation-event automaton and bounded composed trace, annotated with emitted/no-output/stutter behavior | C7 | exp-12--16 |
| F5 | Revocation issuance/delivery timeline for delays 0, 1, and 2, showing the stale-execution window | C4 negative result | exp-17--21, principally exp-19 |
| T1 | C1 proof/audit, alternatives, controls, and scope | C1 | exp-01--06 |
| T2 | Frozen architecture-derived corpus, oracle agreement, delegation, and mutation results | C6 | exp-07--09, exp-11 |
| T3 | Fair expressible-subset baseline comparison and N/A dimensions | C6 context | exp-05, exp-10 |
| T4 | Five-effect safety/composition and sequence coverage | C7 | exp-12, exp-14, exp-16 |
| T5 | Deny-only ablation and source-grounded effect mapping | C7 | exp-13, exp-15 |
| T6 | Exact delivered-state results versus delayed issuance-relative schedules | C4 negative result | exp-17--21 |
| T7 | Evidence status and deployment boundary for C5 | C5 limitation | exp-26; exp-22--25 not run locally |

There is no orphan display: every planned figure/table serves an accepted claim or a mandatory rejected/insufficient boundary. There is no orphan reported S2 run: exp-01--16 serve accepted claims, exp-17--21 serve the required negative result, and exp-26 serves the required performance limitation.

## Quantitative evidence ledger

### C1

| Tag | Quantitative statement allowed in draft | Source field(s) |
|---|---|---|
| E01 | 8/8 proof obligations closed; 393,750 one-dimensional models and 2,756,250 horizon checks; 0 exact inclusion violations; 1 stronger same-request counterexample retained | `results/exp01_exact_1d_20260831/metrics.json`: `proof_obligations_*`, `exact_1d_models`, `exact_1d_horizon_checks`, `exact_1d_inclusion_violations`, `unregistered_same_request_counterexamples` |
| E02 | 14/14 unsafe mutants killed; 2 semantics-changing monotone mutants survived C1 but were routed to decision equivalence | `results/exp02_caveat_mutation_20260831/metrics.json` |
| E03 | Five seeds all had 0 MIMO/history violations; 720 MIMO horizon checks, 400 history horizon checks, 8,854 membership checks; 2/2 negative controls detected | `results/exp03_mimo_history_20260831/metrics.json` |
| E04 | 2/2 removed obligations produced counterexamples; 0 restored trace/reachable-set violations; 5/5 effects observed | `results/exp04_effect_closure_20260831/metrics.json` |
| E05 | 72 common-subset request pairs and 63 adapter/plant/horizon checks; 0 cross-adapter or inclusion mismatch | `results/exp05_common_subset_20260901/metrics.json` |
| E06 | 9/9 sanity cases matched; deliberate widening rejected and physically detected | `results/exp06_c1_sanity_20260901/metrics.json` |

### C6

| Tag | Quantitative statement allowed in draft | Source field(s) |
|---|---|---|
| E07 | 58,968 total cases (42,120 CPwE and 16,848 ENISA), including 54,432 mutations; 0 compiler-oracle mismatches; 672 delegation-dimension checks with 0 failures; 84 delegation edges | `results/exp07_heldout_equivalence_20260901/metrics.json` |
| E08 | Generated corpus killed 10/10 check-removal mutants; six handwritten fixtures killed 0/10; 4/4 provenance probes passed | `results/exp08_source_generation_ablation_20260901/metrics.json` |
| E09 | 24 multi-conduit path cases had 0 mismatch; 32/32 widening attempts across 8 dimensions rejected; 672 legal checks had 0 failures | `results/exp09_depth_path_widening_20260901/metrics.json` |
| E10 | On fully expressible subsets, OPC UA role, PLC ABAC, and pinned-SINT projections each had 0 mismatch; on the full corpus they left 40,824, 18,144, and 28,728 mutations unrestricted | `results/exp10_c2_baselines_20260901/metrics.json` |
| E11 | 22/22 sanity cases matched, including 9 expected compile rejections | `results/exp11_c2_sanity_20260901/metrics.json` |

### C7

| Tag | Quantitative statement allowed in draft | Source field(s) |
|---|---|---|
| E12 | 58,968 one-request traces and 4,536 five-step composed traces; all five effects reached; 0 registered safety/refinement/deadlock violations; 5/5 mutants killed | `results/exp12_effect_automaton_20260901/metrics.json` |
| E13 | Deny-only falsely blocked 13,608 registered rewrites: 16.67% of 81,648 policy steps and 60% of constructed safe-service opportunities; lost 9,072 recoverable decisions; 0 safety violations; 3/3 mutants killed | `results/exp13_deny_only_ablation_20260901/metrics.json` |
| E14 | 492,156 words and 492,030 transitions through horizon 5 over 126 scopes; all 25 bigrams/125 trigrams; 0 registered violations; exhaustive 3/3 versus named path 0/3 mutants | `results/exp14_exhaustive_sequences_20260901/metrics.json` |
| E15 | Lanotte/Roop maps 3/5 effects exactly; pinned SINT maps 2/5 exactly, 2/5 partially, 1/5 absent; all 13,608 ZoneCap rewrites project to SINT denial | `results/exp15_c3_baselines_20260901/metrics.json` |
| E16 | 5/5 effect sanity cases matched; 5 authorized defer holds; 1 rewrite-membership premise-removal counterexample | `results/exp16_effect_sanity_20260901/metrics.json` |

### Required negative and limitation evidence

| Tag | Quantitative statement allowed in draft | Source field(s) |
|---|---|---|
| E17 | Bound-5 model: 793,800 words, 793,797 transitions, 26,038 executions, 4,534 conflict resolutions, 1,590 timeouts, 0 delivered-state/union/order/deadlock violations, 4/4 mutants killed | `results/exp17_c4_interleavings_20260901/metrics.json` |
| E18 | Exact graphs closed at depths 6/8/10 with 1,110 states, 10,576 cycle edges, and 461 post-bound-5 states; 0 registered violations; deadlock control detected | `results/exp18_c4_convergence_20260902/metrics.json` |
| E19 | 15 fair schedules all delivered revocation; delay 0 had 0 issuance-relative stale executions, delays 1 and 2 had 4 each (8 total); 0 post-delivery/union/order/deadlock violations; diagnostic fence blocked 8/8 | `results/exp19_c4_adversarial_scheduler_20260902/metrics.json` |
| E20 | Pinned SINT: 1 pre-delivery allow, 1 revoked queued request approved, 1 post-delivery deny, and 1 fresh gateway-recheck deny; two same-resource approvals produced 0 cross-request winners | `results/exp20_c4_sint_baseline_20260902/metrics.json` |
| E21 | 4/4 concurrency sanity cases matched; 0 registered violations | `results/exp21_c4_sanity_20260902/metrics.json` |
| E26 | x86-only: empirical timer minimum 90 ns; empty/full/forced-slow p99 210/19,326/6,639,755 ns; 100,000/100,000/100 samples; CPU affinity verified/restored; 6/6 check mutants killed | `results/exp26_c5_timer_sanity_20260902/metrics.json` |

## External references used for positioning, not project evidence

- Dodson/CHERI Macaroons: CPS capability construction, delegation, and enforcement.
- CPAC: physical-model-derived access control for smart grids.
- Smart I/O and Lanotte/Roop/Baird: runtime edit enforcement and scalable composition.
- ZTPM, SINT, and DARC: agent/physical authorization, attenuation, delegation, and revocation.
- IEC 62443 risk-assessment automation and zone/conduit DSL work: standards modeling and automation.

Their claims are cited to primary reports, papers, preprints, or pinned official project sources in `draft.md`; none is used as a substitute for a missing ZoneCap result.

## Citation support audit

Search date: 2026-09-02. Scope: direct primary/official sources in CPS capabilities, runtime enforcement, agent authorization, and IEC 62443 modeling; no Nature/CNS-only filter was imposed because it would exclude the relevant technical literature.

| Segment | Draft claim | Primary source(s) | Support grade | Boundary |
|---|---|---|---|---|
| S001 | IEC 62443-3-2 uses zones/conduits for system security-risk design | IEC 62443-3-2 [1] | Strong/background | Standard text is not evidence that ZoneCap is compliant |
| S002 | CPS capabilities can scope and delegate physical-resource authority | Dodson TR-963 and CHERI Macaroons [2,3] | Strong | No reachable-set theorem attributed |
| S003 | CPAC derives access-control policies from a physical grid model | CPAC [4] | Strong | Grid-specific centralized model |
| S004 | Smart I/O and Lanotte/Roop/Baird enforce or compose CPS event corrections | [5,8,9] | Strong | Their mechanism and scalability claims remain theirs |
| S005 | ZTPM adds typed physical-impact/runtime policy for LFM-controlled robots | ZTPM [10] | Strong | Based on checked arXiv abstract; no ZoneCap theorem inferred |
| S006 | SINT supplies signed capabilities, physical constraints, attenuation, revocation, and approvals | Pinned SINT whitepaper/code [11] | Strong | Pinned lifecycle and threat-model boundary retained |
| S007 | DARC supplies delegation-aware runtime contracts with attenuation and revocation closure | DARC [12] | Strong | Open LLM-agent IO, not IEC/physical reachability |
| S008 | Recent work automates IEC 62443-3-2 risk analysis and formalizes zone/conduit models | [13,14] | Strong | Neither is described as a capability runtime compiler |
| S009 | TwinGridShield performs consequence-aware grid authorization and reports sensitivity to model mismatch | TwinGridShield [17] | Strong | No capability-delegation refinement attributed |
| S010 | Held-out topology was derived from the named CPwE and ENISA documents | Official source documents [15,16] | Strong for source identity | The evaluation encoding remains author-produced |

## Cut list

- Development seed 7 and `s1_smoke_20260831_seed7` are infrastructure only and are not reported as evidence.
- The failed/empty `exp05_common_subset_20260831` attempt is not reported; only the completed 2026-09-01 run is used.
- SINT shared-host latency from the S1 baseline is not reported because the published target did not reproduce and no fair target-hardware comparison exists.
- No number is assigned to exp-22--25 until hardware result directories pass freeze and raw-data audit.
- No field-workload utility, IEC certification, unbounded liveness, fixed-tick safety, model-mismatch robustness, or compromised-sensor claim is inferred from the accepted evidence.

## Cold-read outcome

Cold read date: 2026-09-02. Inputs were restricted to `draft.md` and this evidence map.

- **Accepted-claim scope:** pass. The main contribution uses only C1, C6, and C7; C6 names the frozen sources and overlay, and C7 names the actuation-event and parent-realizability premises.
- **Rejected/insufficient visibility:** pass. C4 has a dedicated negative-result section and is explicitly refuted; C5 has a dedicated evidence-status table and no target-hardware conclusion.
- **Quantitative traceability:** pass. Every result number in prose is followed by an `E##` marker, and every numeric table row names its evidence tag. The draft uses exactly E01--E21 and E26, all defined above.
- **Display traceability:** pass. The draft and reverse map contain the same five figures (F1--F5) and seven tables (T1--T7); each serves an accepted claim or a mandatory negative/limitation boundary.
- **Overclaim sweep:** pass after revision. The source documents are limited to zone/conduit topology, target-asset identifiers are identified as deterministic encoding fields, the five behavior/context fields are identified as a source-independent overlay, and the x86 timer number is not used as Jetson/OpenPLC evidence.
- **Missing evidence decision:** no S4_PATCH is required for the accepted storyline. Exp-22--25 remain desirable external evidence for C5 but are not required by C1, C6, or C7 and are not written around.
