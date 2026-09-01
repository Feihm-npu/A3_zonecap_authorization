# C3 Five-Effect Automaton Protocol

Status: S2 exp-12 protocol, fixed before execution.

## Frozen input and finite bound

Exp-12 reuses the frozen exp-07 policy table, all 58,968 exp-07 request
records, and the 126 compiled scopes at delegation depths 0, 1, and 2. It does
not redraw source zones, discard denied cases, or add a new held-out policy.
The check is seedless and exhaustive over that finite corpus.

Every original request is treated as a one-request policy trace. In addition,
every one of the 4,536 valid requests is extended into one five-step composed
trace with the fixed effect order

`ATTENUATE -> DEFER -> ALLOW -> REWRITE -> DENY`.

The bound is five policy transitions and at most three physical transitions.
An `ATTENUATE` or `DEFER` obligation must reach an `ALLOW` or `REWRITE`
physical outcome within two later policy transitions. This bound is fixed
before execution and is a bounded liveness check, not an unbounded liveness
proof.

## Transition semantics

The automaton state contains the active capability, any unresolved safe
request, and the authorization-relevant physical trace.

1. `ATTENUATE` intersects the active parameter interval with a strict interval
   that still contains the registered valid value. It emits no action and
   replaces the active capability with the returned child.
2. `DEFER` is forced by incomplete context. It leaves the active capability
   unchanged and emits the registered hold action `read` at the valid request
   value. The held-out overlay contains `read` in every scope. In this abstract
   plant binding, `read` is observational and therefore leaves physical state
   unchanged; this is the registered parent-admissible stutter transition.
3. `ALLOW` resubmits the original valid request with complete context under the
   active capability.
4. `REWRITE` submits a structurally valid request one unit above the active
   upper parameter bound. The emitted value must be the active upper bound.
5. `DENY` submits the same request with an unregistered action and emits no
   physical action.

`DENY` and `ATTENUATE` do not advance the physical trace. This experiment does
not equate their no-command behavior with a frozen fixed-tick plant. Only the
explicit `read` binding used by `DEFER` is classified as a stutter.

For the original 58,968 one-request traces, valid cases must produce `ALLOW`,
the two parameter-bound mutations must produce `REWRITE`, and the other ten
registered mutation categories must produce `DENY`. The composed traces add
one occurrence of every effect for every valid request.

## Checked properties

For every emitted action, the checker independently verifies operation and
value membership in the then-active capability. For every depth-1 or depth-2
trace, it also constructs a parent-subject identity request for each child
output. The declared parent must `ALLOW` that same physical operation and
value; consequently every child physical prefix must be reproducible by the
parent. This is the request-abstracted parent-realizability relation registered
by C1, not the known-false same-raw-request relation.

The pass conditions are:

- all frozen input counts and all expected effect counts match;
- all five effects are reached;
- zero effect-order, attenuation, unauthorized-output, non-stutter,
  parent-realizability, trace-inclusion, and bounded-deadlock violations;
- all registered negative controls are detected.

## Negative controls and baseline boundary

Five checker mutants are fixed: an out-of-capability rewrite, a non-stuttering
defer output, an unresolved defer, an output after deny, and a widened
attenuation. Every mutant must be killed. This is the too-good-result audit for
the zero-violation main check.

The Lanotte/Roop edit-automaton and pinned SINT tier comparison remains the
separately registered exp-15 experiment. Exp-12 neither fabricates runnable
hardware/licensed-tool results for Lanotte/Roop nor attributes ZoneCap's
five-effect refinement contract to SINT.
