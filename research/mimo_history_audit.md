# MIMO and History-Dependent Refinement Audit

Status: S2 exp-03 protocol, fixed before execution.

## MIMO polytope check

Each preregistered seed generates 24 two-state/two-input linear systems with
dense signed integer matrices. Initial, disturbance, and parent-input sets are
two-dimensional convex polytopes; the child input is a translated diamond
strictly contained in the parent rectangle. Reachable sets are propagated in
exact rational V-representation:

\[
R_{t+1}=\operatorname{conv}\{Ax+Bu+w:x\in V(R_t),u\in V(U),w\in V(W)\}.
\]

In two dimensions this is exact, not a bounding-box approximation. Child
inclusion is checked at every horizon by testing every child hull vertex against
the parent convex polygon. A deliberately widened child under an identity-input
plant must be detected as a negative control.

## State/history-dependent relation check

Each seed separately generates 16 finite plants. Enabled actions depend on the
current state, previous action, and an accumulated action-history residue. The
child relation is sampled only from the corresponding parent action set. Rather
than compare state marginals alone, the checker exhaustively enumerates complete
state/action/disturbance traces through the fixed horizon and checks both trace
inclusion and projected reachable-state inclusion at every depth.

A separate finite plant gives a mutant child one extra initial action leading to
a parent-unreachable state. The trace and state checkers must both detect it.

## Fixed execution

- Seeds: `104729`, `130363`, `155921`, `196613`, `262147`.
- MIMO horizon: 5; 24 models per seed.
- History-dependent horizon: 4; 16 models per seed.
- Finite history plant: 6 states, 3 actions, 2 disturbances; relation key is
  `(current state, previous action, sum(actions) mod 3)`.
- All per-seed and per-horizon results are reported. No seed may be removed.

This is a falsification audit supporting the general transition-system proof in
exp-01. It is not substituted for that proof and it does not use learned or
test-set-tuned parameters.
