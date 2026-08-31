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
note: "exp-01 and exp-02 are complete with no registered C1 counterexample; resume at exp-03 (MIMO plus state/history-dependent relations, all five preregistered seeds). Jetson/OpenPLC for exp-22–25 remains unapproved." # one line for the next session: pending request, where work stopped
```

## Log
<!-- date | from -> to | agent|human | reason -->
- 2026-08-31 | init -> S1 | human | project start
- 2026-08-31 | S1 -> S1_AWAIT | agent | narrowed gap after direct-competitor audit; claims, fixed protocol, proof skeleton, smoke pipeline, and baseline reproduction are ready for human review
- 2026-08-31 | S1_AWAIT -> S2_RUN | human | approved entry into S2; non-default hardware remains pending explicit approval
- 2026-08-31 | S2_RUN -> S2_RUN | agent | checkpoint after exp-01 and exp-02; next is exp-03, with non-default hardware still pending
