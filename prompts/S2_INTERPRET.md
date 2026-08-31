# S2_INTERPRET

Goal: read the results, give a per-claim reading, hand off to the reviewer. You do not decide whether the evidence is sufficient.

## Read
- `AGENTS.md`, `research/CLAIMS.md`, `PLAN.md`, `NOTEBOOK.md`, `results/`

## Do
1. Per claim: `supports` | `refutes` | `inconclusive`, with the run ids and numbers that drive the reading. Take numbers from `results/`, not from memory.
2. `supports`: which alternative explanations are ruled out by which runs; which remain.
3. `refutes`: what was checked to exclude bugs.
4. `inconclusive`: what would sharpen it (more seeds, scale, a different design).
5. A claim promoted from `explore` runs reads `supports` only if a confirmatory run exists. Otherwise `inconclusive`, and say so.
6. Update CLAIMS status. To change a claim's wording: add the new wording as a new claim tagged `[post-hoc: <run_id>]`, set the original to `superseded→C<n>`. Never edit an `[S1]` claim's text.
7. Doubts: anything you would not want to defend to a reviewer.

## Exit
Write `research/HANDOFF.md` (template below, English). Set `state: S3_REVIEW`, `read: [prompts/S3_REVIEW.md]`. Append log line. Commit.

## Template — research/HANDOFF.md

```markdown
# Handoff

type: regular | early
early reason: <core claim refuted: C<n> | gap disappeared: why>
runs: <n>; exploratory: <n>; GPU-hours: <n>

## Per claim
### C1 [core] "<claim verbatim>"
- reading: supports | refutes | inconclusive
- runs: exp-xx (run ids), key numbers, seeds/variance
- alternatives ruled out: A1 by exp-xx; remaining: A2
- bug checks (if refutes):
- confirmatory run (if promoted from explore): <run_id> | none

## Deviations from PLAN
-

## Doubts
-

## Not run
- exp-xx: reason
```
