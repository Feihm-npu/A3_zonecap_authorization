# C4 Multi-Principal Interleaving Protocol

Status: S2 exp-17 protocol, fixed before execution.

## State and event alphabet

The seedless model is instantiated with 2, 3, and 4 holders. Holder `i` owns
one indivisible command `(action_i, value=10(i+1))` and only its own capability
authorizes that tuple. Holder 0's command is high-risk; all others are ordinary.
All commands target one shared asset and therefore conflict when pending
together.

For `n` holders, the alphabet is every `submit_i`, `revoke_i`, and `approve_i`
event plus `resolve` and `tick`, for `3n+2` symbols. Every word of length zero
through five is enumerated. Invalid/repeated events remain explicit no-ops; no
interleaving is discarded after observation.

The finite state contains the revoked-holder set and an atomic pending command
per holder with approval set and timeout age. Revocation removes an existing
pending command, and a revoked holder cannot submit again. `approve_i` adds that
principal's approval to all pending high-risk commands. High-risk execution
requires `min(2,n)` distinct approvals. Two unresolved `tick` events terminate
the high-risk command as denied/timeout.

## Deterministic resolution and properties

`resolve` considers only non-revoked commands satisfying their approval rule
and chooses the smallest holder ID. It executes the selected command as one
atomic tuple; fields from concurrent commands are never combined. If holder 0
is waiting for approval, the resolver may execute an eligible lower-priority
command rather than blocking the queue.

Every transition checks:

1. **post-revocation execution:** no executed command belongs to the current
   revoked set;
2. **permission union:** the exact executed tuple is authorized by the one
   holder attached to that command;
3. **deadlock:** every pending state has an enabled resolution, a missing
   approval, a revocation, or a timeout tick;
4. **determinism:** an execution equals the fixed minimum-ID eligible winner.

The main check reports all words/transitions, unique states, conflict states,
approval-wait states, executions, timeouts, and resolution depths. The three
C4 safety/deadlock violation counts and deterministic mismatches must be zero,
while conflicts, approvals, executions, revocation-after-submit prefixes, and
timeouts must all be reachable.

Four trigger mutants are fixed: execute a revoked retained command, combine
holder 0's action with holder 1's value, choose the maximum-ID eligible winner,
and remove both approval and timeout progress from a high-risk pending state.
The exhaustive language must contain and kill all four. Exp-17 is bounded
falsification; exp-18 extends the bound/state graph and exp-19 changes scheduler
assumptions.
