# S2_RUN

Goal: execute `research/PLAN.md` in order and record every run.

## Read
- `AGENTS.md`, `research/PLAN.md`, `CLAIMS.md`, `NOTEBOOK.md`; `results/` for what is already done.
- If returning from `S3_AWAIT`: apply the human's decision (REVIEW verdicts, overridden by `STATE.md` `note`) to CLAIMS status; add REVIEW's listed experiments to PLAN tagged `[post-hoc: review]`. They are the plan now.

## Rules
- Every run: `results/<run_id>/` with config, exact command, seed, log, metrics. A number not in `results/` does not exist.
- NOTEBOOK: one line per run; one entry per deviation from PLAN (what, why).
- Adding an experiment is fine, tagged `[post-hoc: <run_id that motivated it>]`. Claim wording changes belong to `S2_INTERPRET`; note the proposal in NOTEBOOK.
- Exploratory runs are allowed, labelled `explore` in NOTEBOOK. They are not evidence.
- When a run contradicts expectation in either direction, check implementation and evaluation before recording the outcome.
- Compute: stay within the default. Requests go in `STATE.md` `note`; meanwhile run what fits.

## Exit
- Matrix done, or the rest cannot run (PLAN status `skipped:<reason>`): set `state: S2_INTERPRET`, `read: [prompts/S2_INTERPRET.md]`.
- Early: a core claim is refuted after bug checks, or a baseline/sanity check shows the gap does not exist: write `research/HANDOFF.md` per `prompts/S2_INTERPRET.md` with `type: early`; set `state: S3_REVIEW`, `read: [prompts/S3_REVIEW.md]`.
- Runs still in progress: keep `state: S2_RUN`; `note` = run ids and what to do when they finish.

Append log line. Commit.
