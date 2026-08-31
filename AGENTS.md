# Research Loop

This project runs a state-driven research loop. Every session:

1. Read `STATE.md`. It is the only source of truth for where the project is.
2. Read `prompts/<state>.md` and the files it lists.
3. Resume. Do not redo completed work. Do not re-derive the project from scratch.
4. On exit, update `STATE.md` exactly as the prompt specifies.

`CLAUDE.md` should point here.

## Principles

- The unit of work is the claim. Each claim in `research/CLAIMS.md` is falsifiable and states, before any experiment runs: what is observed if true, what is observed if false, and what else could produce the "true" observation.
- Fix the evaluation protocol before seeing results. If it must change, log why in `research/NOTEBOOK.md`.
- Never tune on the test set.
- Keep pre-registered and post-hoc apart. Claims and experiments may be added or changed after seeing results; each carries a tag: `[S1]` (approved in S1) or `[post-hoc: <run_id>]`.
- Exploratory results are not evidence. A claim promoted from exploration needs a confirmatory run with fresh seeds/splits.
- Report every seed. Never select seeds.
- Results that look too good are a bug signal (leakage, evaluation error). Check before proceeding.
- Negative results are valid outputs.
- The executor (S1/S2/S4) does not judge whether its own evidence is sufficient. S3 and the human do.
- Compute: default 4×A100-80G (GPUs 0–3) of 8. To use more, or other hardware: write a request in `STATE.md` `note` (what, why, expected duration, fallback within default), continue with work that fits the default, and never exceed it without approval. Budgets in `PLAN.md` are guidance, not hard limits.
- Language: research artifacts in English. Reports for the human in Chinese, quoting claims verbatim in English.

## States

| State | Work | Exit |
|---|---|---|
| `S1` | Understand project; define problem, gap, closest prior work + delta; write CLAIMS and PLAN; build infra; smoke-test end to end; reproduce baselines | agent → `S1_AWAIT` |
| `S1_AWAIT` | Human reviews PROPOSAL (digest of PROBLEM / CLAIMS / PLAN) | human → `S2_RUN`, or `S1` with comments |
| `S2_RUN` | Execute PLAN; fix infra; record every run in `results/` and `NOTEBOOK.md` | agent → `S2_INTERPRET` when the matrix, or a subset justified in HANDOFF, is done. If a core claim is refuted or the gap disappears: write HANDOFF marked `early`, agent → `S3_REVIEW` |
| `S2_INTERPRET` | Read results; per-claim reading (supports / refutes / inconclusive); list doubts; write HANDOFF | agent → `S3_REVIEW` |
| `S3_REVIEW` | Independent review; calibrate each claim's scope; write REVIEW | agent → `S3_AWAIT` |
| `S3_AWAIT` | Human decides | human → `S4`, `S2_RUN` with listed experiments, or `S1` |
| `S4` | Storyline, logic line, evidence map, draft | agent → `DONE`; agent → `S4_PATCH` if writing exposes missing evidence |
| `S4_PATCH` | Run only the missing experiment(s); light review | agent → `S4`. If an accepted claim's scope changes: agent → `S3_AWAIT` |
| `DONE` | — | — |

Rules:
- Agent sets only: `S1_AWAIT`, `S2_INTERPRET`, `S3_REVIEW`, `S3_AWAIT`, `S4_PATCH`, `S4` (from `S4_PATCH`), `DONE`.
- Human sets every exit from `*_AWAIT`.
- Core claim = tagged `core` in CLAIMS.md. Refuting one, or finding the gap does not exist, triggers early `S3_REVIEW`. Never a self-initiated return to `S1`.
- Every transition: append one log line to `STATE.md`, then `git commit -am "state: FROM -> TO"`.

## Files

```
STATE.md               routing only: current state, pending decision, log
AGENTS.md              this file
prompts/<STATE>.md     instructions per state
research/PROBLEM.md    problem, gap, closest prior work, delta
research/CLAIMS.md     claims: statement, true/false observations, alternatives, tag, status
research/PLAN.md       experiment matrix: claim × experiment × baseline × metric × est. cost
research/NOTEBOOK.md   append-only: runs, deviations, reasons
research/PROPOSAL.md   S1 gate document (Chinese) for the human
research/HANDOFF.md    S2_INTERPRET → S3: per-claim reading, doubts, `early` reason if any
research/REVIEW.md     S3 report (Chinese) for the human
research/paper/        S4: story.md, logic.md, evidence.md, draft.md
results/<run_id>/      config, command, seed, log, metrics — every reported number lives here
```
