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
note: "S2 approved. This decision does not explicitly approve the non-default Jetson/OpenPLC request for exp-22–25; start with exp-01 and other work within the default compute envelope." # one line for the next session: pending request, where work stopped
```

## Log
<!-- date | from -> to | agent|human | reason -->
- 2026-08-31 | init -> S1 | human | project start
- 2026-08-31 | S1 -> S1_AWAIT | agent | narrowed gap after direct-competitor audit; claims, fixed protocol, proof skeleton, smoke pipeline, and baseline reproduction are ready for human review
- 2026-08-31 | S1_AWAIT -> S2_RUN | human | approved entry into S2; non-default hardware remains pending explicit approval
