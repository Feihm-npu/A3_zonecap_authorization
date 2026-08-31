# C1 Sanity Matrix

Status: S2 exp-06 protocol, fixed before execution.

The seedless sanity matrix checks the expected edge pattern rather than adding
another random search:

- an identity child has exactly the parent's reachability;
- a child with an empty physical action scope has the common initial set at
  horizon 0 and an empty exact-horizon reachable set thereafter under
  actuation-event semantics;
- all four sign combinations of nonzero scalar `A` and `B` preserve inclusion;
- zero and asymmetric nonzero disturbance both preserve inclusion when common;
- a deliberately widened parameter interval is rejected by token syntax and,
  if that check is bypassed, produces a one-step physical inclusion violation.

Before the recorded run, this audit exposed an infrastructure error: the legacy
1D helper propagated `capability.parameter` even when a structural scope set was
empty. The helper now represents exact postinitial reachability as empty (`None`)
when conduit, asset, action, or mode has no member. This is a semantics fix, not
a change to the registered C1 protocol. Fixed-tick idle dynamics remain an
explicit plant/effect-adapter obligation rather than being silently frozen.
