# STATE

Routing only. Content lives in `research/`. Read this, then `prompts/<state>.md`.
Human decision: set `state`, set `awaiting: none`, clear `options`, put any override of REVIEW verdicts or comments for the agent in `note`, append a log line, commit.

```yaml
state: S2_RUN
awaiting: none            # none | human
since: 2026-08-31
read:                     # what the next session must read first
  - prompts/S2_RUN.md
options: []               # when awaiting human: allowed next states
note: "The human approved NVIDIA Jetson Orin NX 8GB for exp-22–25, delegated execution to the hardware group, and directed local work to continue. Requirements are in hardware_delivery/exp_requirements.md; hardware harness freeze/results remain external:pending. Resume locally at exp-26 timer sanity, then wait for the hardware return without interpreting C5." # one line for the next session: pending request, where work stopped
```

## Log
<!-- date | from -> to | agent|human | reason -->
- 2026-08-31 | init -> S1 | human | project start
- 2026-08-31 | S1 -> S1_AWAIT | agent | narrowed gap after direct-competitor audit; claims, fixed protocol, proof skeleton, smoke pipeline, and baseline reproduction are ready for human review
- 2026-08-31 | S1_AWAIT -> S2_RUN | human | approved entry into S2; non-default hardware remains pending explicit approval
- 2026-08-31 | S2_RUN -> S2_RUN | agent | checkpoint after exp-01 and exp-02; next is exp-03, with non-default hardware still pending
- 2026-09-01 | S2_RUN -> S2_RUN | agent | checkpoint after completing the full C1 matrix exp-01 through exp-06; next is held-out C2 exp-07
- 2026-09-01 | S2_RUN -> S2_RUN | agent | checkpoint after completing the C2 matrix exp-07 through exp-11 with no compiler-oracle mismatch or accepted widening; next is exp-12
- 2026-09-01 | S2_RUN -> S2_RUN | agent | checkpoint after exp-12 exercised all five runtime effects on every frozen held-out request and composed trace with zero registered violation; next is exp-13 deny-only ablation
- 2026-09-01 | S2_RUN -> S2_RUN | agent | checkpoint after exp-13 showed deny-only preserves safety but blocks registered safe rewrites and removes recovery decisions; next is exp-14 exhaustive-sequence ablation
- 2026-09-01 | S2_RUN -> S2_RUN | agent | checkpoint after exp-14 exhaustive request/context enumeration covered every effect bigram/trigram with zero registered violation and exposed hand-picked coverage gaps; next is exp-15 baseline mapping
- 2026-09-01 | S2_RUN -> S2_RUN | agent | checkpoint after exp-15 source-grounded baseline mapping preserved lifecycle/proof boundaries and left unavailable Lanotte runtime metrics N/A; next is exp-16 sanity
- 2026-09-01 | S2_RUN -> S2_RUN | agent | checkpoint after completing C3 exp-12 through exp-16 with bounded five-effect composition, exhaustive sequences, baseline boundaries, and fail-closed timeout sanity; next is exp-17 C4
- 2026-09-01 | S2_RUN -> S2_RUN | agent | checkpoint after exp-17 exhausted the registered bound-five 2-4-holder interleavings with zero C4 safety/deadlock violation; next is exp-18 bound/convergence ablation
- 2026-09-02 | S2_RUN -> S2_RUN | agent | checkpoint after exp-18 closed every 2-4-holder graph with symmetry reduction and zero new cycle/deadlock violation; next is exp-19 adversarial scheduling
- 2026-09-02 | S2_RUN -> S2_RUN | agent | exp-19 found issuer-relative stale execution under fair delayed revocation delivery; C4 is non-core, so continue to exp-20 baseline and exp-21 sanity to bound the counterexample
- 2026-09-02 | S2_RUN -> S2_RUN | agent | exp-20 bounded the pinned-SINT comparison to delivered revocation, independent quorum, timeout, and consumer-side recheck; next is exp-21 C4 sanity
- 2026-09-02 | S2_RUN -> S2_RUN | agent | exp-21 matched all local C4 terminal-state sanity checks; pausing at the exp-22 non-default Jetson/OpenPLC hardware gate for human approval or fallback selection
- 2026-09-02 | S2_RUN -> S2_RUN | human | approved NVIDIA Jetson Orin NX 8GB for exp-22–25, delegated hardware execution, and directed the agent to continue with local exp-26
