# S1 Foundation and Proposal QA

Date: 2026-08-31

This QA maps the researchwrite foundation sequence onto the project-native files rather than creating a second project structure:

- scope/canon: `README.md`, `research/PROBLEM.md`
- evidence and falsifiable contracts: `research/CLAIMS.md`
- argument/method map: `research/PLAN.md`, `research/monotonicity_theorem.md`
- gate draft: `research/PROPOSAL.md`

## Foundation review

| Dimension | Score / 10 | Finding |
|---|---:|---|
| Research-question clarity | 9.0 | The question is explicit and falsifiable: syntactic attenuation must imply physical trace/reachable-set inclusion. |
| Scientific tension | 9.0 | Direct competitors invalidate the broad original novelty and force a precise formal/standards delta. |
| Evidence matching | 8.0 | Prior-work claims link to primary papers or the competitor's repository; current implementation outputs are explicitly marked smoke-only. A systematic exhaustive search is still absent. |
| Logic chain | 8.5 | Gap → C1/C2 core claims → cheapest falsification → compiler/effect/runtime evaluation is connected end to end. |
| Feasibility | 7.5 | A runnable dependency-free core and a reproduced SINT source baseline exist; held-out source encoding, independent oracle, model checker, and hardware access remain open. |
| Novelty specificity | 7.5 | The remaining delta is specific, but SINT/ZTPM make it narrow and time-sensitive. It survives only if the compiler refinement lemma is substantive. |
| Risk boundary | 9.0 | Kill conditions, theorem assumptions, counterexamples, held-out discipline, and hardware fallback are explicit. |
| Language/precision | 8.5 | Forbidden firstness claims and unsupported intensifiers were removed; claims use threshold and counterexample language. |

Foundation score: **8.38 / 10 — passes the >7.5 drafting gate.**

## Proposal review

Proposal score: **8.25 / 10 — suitable for the S1 human gate, not a final submission document.**

The proposal is evidence-led and makes the newly discovered overlap visible rather than hiding it. It also preserves the required claim-verbatim English statements. The two main residual weaknesses are:

1. C4 is likely too broad for a ten-page TII paper whose intended spine is theorem + compiler + runtime overhead. It should remain secondary unless its counterexample materially affects C1/C3.
2. C5 cannot be assessed on the declared target without explicit approval for non-default Jetson/OpenPLC hardware. The x86 fallback cannot validate the hardware-specific wording.

Recommendation: **human review at S1_AWAIT.** If approved, begin S2 with exp-01 only; do not start held-out compiler or performance runs until the proof audit confirms that C1 is not tautological.
