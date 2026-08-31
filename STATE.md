# STATE

Routing only. Content lives in `research/`. Read this, then `prompts/<state>.md`.
Human decision: set `state`, set `awaiting: none`, clear `options`, put any override of REVIEW verdicts or comments for the agent in `note`, append a log line, commit.

```yaml
state: S1_AWAIT
awaiting: human           # none | human
since: 2026-08-31
read:                     # what the next session must read first
  - research/PROPOSAL.md
options: [S2_RUN, S1]     # when awaiting human: allowed next states
note: "Hardware request for S2 exp-22–25: one Jetson AGX Orin-class target plus one OpenPLC-capable PLC/Raspberry Pi for at most 2 days; needed for C5, fallback is isolated x86 software-in-the-loop and removal/rewording of the Jetson-specific claim." # one line for the next session: pending request, where work stopped
```

## Log
<!-- date | from -> to | agent|human | reason -->
- 2026-08-31 | init -> S1 | human | project start
- 2026-08-31 | S1 -> S1_AWAIT | agent | narrowed gap after direct-competitor audit; claims, fixed protocol, proof skeleton, smoke pipeline, and baseline reproduction are ready for human review
