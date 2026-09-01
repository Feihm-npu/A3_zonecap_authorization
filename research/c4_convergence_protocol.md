# C4 State-Graph Convergence and Symmetry Protocol

Status: S2 exp-18 protocol, fixed before execution.

Exp-18 uses the exact exp-17 transition relation but explores each newly
reachable state once with breadth-first search. For 2, 3, and 4 holders, the
bound starts at zero and increases until a layer adds no new state or the fixed
maximum depth 20 is reached. Convergence requires a final closure pass in which
every event successor is already in the reachable set.

The exact graph retains holder identities and continues to check
post-revocation execution, atomic permission ownership, deterministic minimum-ID
resolution, and deadlock on every edge. Self-loops and edges to previously
visited states are reported as cycle edges; their presence is expected and is
not itself a deadlock.

For symmetry reduction, holder 0 remains distinguished because it is the sole
high-risk principal. Ordinary holders 1..n-1 are canonicalized by the multiset
of `(revoked, pending)` statuses. The high-risk pending state retains age,
whether holder 0 approved, and each ordinary holder's approval bit is retained
beside that holder's revoked/pending status. The quotient is used to report the
state-count reduction and audit invariant state classifications. All safety and
deadlock checks, and especially deterministic winner IDs, remain on the exact
graph.

Every canonical bucket must agree on deadlock, pending-conflict, and
approval-wait classifications. Exp-18 passes only if all exact graphs converge
before depth 20, closure adds zero states, no new safety/deadlock/determinism
violation appears, the quotient is no larger than the exact graph, and the
classification audit has zero mismatches. A deliberately unreachable pending
high-risk state at timeout age is injected to ensure the deadlock predicate
fires; that negative control must be detected.

The exact unique-state counts reached by exp-17 at bound five are frozen as an
input. Exp-18 reports the additional reachable states beyond that bound, plus
cycle edges and deadlocks, rather than silently replacing the original bound.
