# C3 Effect Failure Sanity Protocol

Status: S2 exp-16 protocol, fixed before execution.

## Execution boundary

`PolicyEngine` remains a stateless one-request decision function. Exp-16 binds
it to a `BoundedEffectExecutor`, which owns consecutive-deferral state, the
physical `EffectBinding`, and fail-closed conversion. The registered bound is
two legal `DEFER` holds. A third unresolved context/approval step returns
terminal `DENY` with no output. Any invalid rewrite or hold binding also returns
`DENY` with no output.

This adapter makes the timeout assumption explicit; the pure decision engine is
not retroactively described as stateful.

## Fixed sanity cases

1. **Unauthorized rewrite.** Inject a synthetic `REWRITE` value `1.5` into a
   child interval `[0, 0.4]` whose parent interval is `[0, 1]`. The executor must
   reject it and emit nothing. If the binding check is bypassed, the action must
   be retained as a child-only/parent-only-outside counterexample.
2. **Missing hold action.** Configure `DEFER` with operation `hold`, which is in
   neither the child nor parent action set. The executor must convert the
   binding error to `DENY` and emit nothing.
3. **Lost context.** Submit three consecutive incomplete-context requests. The
   expected effects are `DEFER, DEFER, DENY`; the first two outputs are
   authorized `read` stutters and the timeout output is empty.
4. **Approval timeout.** Submit three consecutive high-risk requests with no
   approval. The expected pattern is again `DEFER, DEFER, DENY`.
5. **Recovery control.** Submit one incomplete-context request followed by the
   same request with complete context. The expected effects are `DEFER, ALLOW`,
   proving the bound does not block a request that recovers in time.

Every expected pattern must match, executor-authorized emissions must remain
inside both child and parent, and no terminal case may leave an enabled pending
request. This sanity experiment requires the deliberately bypassed unauthorized
rewrite counterexample; its presence is not a counterexample to conditional C3,
because it removes C3's registered output-membership premise.
