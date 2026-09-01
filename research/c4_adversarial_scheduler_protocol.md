# C4 Adversarial Scheduler and Delayed-Revocation Protocol

Status: S2 exp-19 protocol, fixed before execution.

Exp-19 distinguishes revocation **issuance** at the authority service from
revocation **delivery** to the resolver. Exp-17/18 modeled only the latter: a
delivered `revoke_i` atomically marks holder `i` revoked and removes its pending
command. The delayed model starts after issuance, with an authorized command
already pending at a resolver whose local revoked set is stale.

Each scenario queues three resolver events in FIFO order: delivery of the
issued revocation, `resolve`, and `tick`. The central-FIFO baseline delivers
them in that order. The adversarial scheduler may defer only the revocation by
exactly 0, 1, or 2 delivery turns while preserving the order of `resolve` and
`tick`. Thus the three schedules are:

1. `revoke, resolve, tick`;
2. `resolve, revoke, tick`;
3. `resolve, tick, revoke`.

All schedules are bounded-fair: every queued event is delivered exactly once,
and revocation is delivered within the registered two-turn bound. This isolates
revocation delay rather than reordering command submission or approval causality.

The five fixed scenarios use three holders and cover an ordinary pending
command, an approved high-risk command, a conflict whose revoked holder would
win, a conflict whose revoked holder would lose, and an approved high-risk
winner conflicting with an ordinary command. Every command remains an atomic
holder-owned `(action, value)` tuple and exact minimum-ID resolution is retained.

The primary property is strict and issuer-relative: after issuance, no command
from that holder may execute, even before the resolver receives the revocation.
The delivered-state property from exp-17/18 is reported separately. C4 is
supported under this ablation only if post-issuance and post-delivery execution,
permission-union violations, deterministic-order violations, and deadlocks are
all zero at every delay. Any post-issuance execution at delay greater than zero
is a registered C4 counterexample and exposes a required freshness/epoch fence;
it must not be relabeled as safe merely because delivery was late.

As a mitigation diagnostic, the same attempted stale executions are checked
against an issuer-side epoch fence that rejects holders in the issued-revoked
set. The diagnostic is not part of the tested protocol: if it removes a
counterexample, that records the additional trusted freshness assumption rather
than rescuing the unfenced result.

