# C4 Terminal-State Sanity Protocol

Status: S2 exp-21 protocol, fixed before execution.

Exp-21 runs four seedless, hand-checkable terminal traces against the same
three-holder transition relation used by exp-17–19:

1. `submit_1, revoke_1, resolve`: immediate local revocation removes the pending
   command; the resolver executes nothing.
2. `submit_1, revoke_1, revoke_1, resolve`: the second revoke is an idempotent
   no-op and the terminal state is identical to case 1.
3. Two ordinary commands are installed simultaneously with the same primary
   priority. Two `resolve` events must execute holders 1 then 2, using holder ID
   as the fixed secondary order, and leave no pending command.
4. `submit_0, tick, tick, resolve`: a permanently missing two-of-three approval
   reaches the registered timeout, executes nothing, and leaves no pending
   high-risk command.

The exact revoked set, pending holders, execution order, timeout count, and
per-event changed flags are fixed in the run configuration before execution.
Every transition also retains the post-delivery revocation, permission-union,
deterministic-order, and deadlock checks. All four cases and all expected
terminal fields must match. Immediate revocation here means delivery to the
local resolver; it does not weaken or overwrite exp-19's separate
issuance-before-delivery counterexample.

