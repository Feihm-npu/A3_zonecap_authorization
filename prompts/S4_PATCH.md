# S4_PATCH

Goal: fill the evidence gap named in `STATE.md` `note`. Nothing else.

## Read
- `AGENTS.md`, `STATE.md` `note`, `research/PLAN.md` (`[post-hoc: S4]` rows), `CLAIMS.md`, `REVIEW.md`, `paper/evidence.md`

## Do
1. Run only the listed experiments under `S2_RUN` rules: `results/`, NOTEBOOK, no evaluation changes.
2. Light review: does the result support the statement the draft needs, at the accepted scope? Record the reading in NOTEBOOK.
3. Route:
   - Fits within an accepted claim's scope → update `paper/evidence.md`; set `state: S4`, `read: [prompts/S4.md]`.
   - Would widen, narrow, or contradict an accepted claim → append a section "Patch review" to `research/REVIEW.md` (Chinese, same per-claim format); set `state: S3_AWAIT`, `awaiting: human`, `read: [research/REVIEW.md]`, `options: [S4, S2_RUN, S1]`.

Append log line. Commit.
