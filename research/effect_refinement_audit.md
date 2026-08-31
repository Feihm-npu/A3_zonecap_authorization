# Runtime-Effect Refinement Audit

Status: S2 exp-04 protocol, fixed before execution.

## Effect contract

For an actuation-event horizon, `ALLOW` emits the authorized request,
`REWRITE` emits an operation/value inside the effective capability, and `DEFER`
emits a configured hold operation/value inside the same capability. `DENY` and
`ATTENUATE` emit no physical action and therefore create no actuation event. A
future fixed-tick adapter must map no-command behavior to a common
parent-admissible idle action; exp-04 does not silently equate no command with a
frozen physical plant.

The concrete `EffectBinding` validates every emitted operation and value against
the presented capability. Because a legal child is a subset of its parent, a
child-valid rewrite or hold is also parent-authorized and can be realized by an
identity request under the parent.

## Seedless bounded model

The parent action alphabet is `{0, 0.2, 0.4, 0.8, 1.0}` and the child alphabet
is `{0, 0.2, 0.4}`. Complete action traces are enumerated through horizon 4. An
injective trace-to-state transition distinguishes every finite action sequence,
so a child-only action trace is also a child-only reachable state at that
horizon.

Six configurations are fixed:

1. suppression-only baseline;
2. rewrite closure removed by emitting `1.5`;
3. rewrite closure restored by emitting `0.4`;
4. defer-stutter closure removed by emitting hold `-1`;
5. defer-stutter closure restored by emitting hold `0`;
6. all five effects with both obligations restored.

Configurations 2 and 4 must expose and retain minimal counterexamples.
Configurations 1, 3, 5, and 6 must have zero trace and reachable-state inclusion
violations. The actual policy engine must reach all five effect kinds, and the
restored physical binding must reject any output outside the effective child.

This experiment tests necessity and restoration of C1's registered effect
premise. Counterexamples produced by deliberately removing that premise are not
misclassified as counterexamples to the conditional claim.
