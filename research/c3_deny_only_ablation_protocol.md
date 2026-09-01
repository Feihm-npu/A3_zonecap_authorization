# C3 Deny-Only Ablation Protocol

Status: S2 exp-13 protocol, fixed before execution.

## Counterfactual and frozen inputs

Exp-13 consumes the immutable exp-12 one-request and composed-trace records.
For each recorded policy step, the deny-only counterfactual receives the same
active capability, raw request, physical context, and history as the five-effect
semantics. It preserves `ALLOW` and `DENY`, and replaces `ATTENUATE`, `REWRITE`,
and `DEFER` with `DENY`. The replacement emits no action, returns no derived
capability, and retains no pending request.

This is a local trace intervention. It isolates the value of the three richer
effects without confounding the comparison with later state divergence caused
by removing `ATTENUATE`. It is not claimed to be an independently optimized or
stateful deny-only controller.

## Fixed metrics

A raw request is **safely served** when the five-effect semantics produces
`ALLOW` or `REWRITE`. A deny-only **false block** occurs only when that same
request is safely served by `REWRITE` but the counterfactual emits nothing.
`ATTENUATE` and `DEFER` do not complete the requested operation at their current
step, so they are reported separately as lost recoverable decisions rather than
inflating the raw-request false-block count.

The experiment reports:

- raw-request false blocks divided by all policy steps;
- false blocks divided by five-effect safe-service opportunities;
- composed traces containing at least one false block;
- lost `ATTENUATE` and `DEFER` recovery decisions;
- categorical effect distance (one for each replaced effect);
- physical-output delta, separating lost rewrite outputs from lost defer
  stutters;
- numeric L1 edit distance for five-effect rewrites.

All exp-12 rewrite scenarios place the raw value exactly one normalized unit
outside the then-active interval. Therefore the registered five-effect rewrite
distance is `1`; deny-only has no numeric output, so its numeric edit distance is
`N/A`, not zero.

Safety is checked by subset: deny-only may emit only a recorded `ALLOW` output,
which must already have passed exp-12's active-capability and parent-realizability
checks. Any output on a replaced effect, any missing `ALLOW` output, or any input
record carrying an exp-12 safety/inclusion violation fails the ablation audit.

## Interpretation boundary

Exp-13 can show that deny-only sacrifices registered safe service and recovery
while preserving safety. It cannot establish workload-level utility, human
preference, or unbounded liveness. Those are outside C3. A zero false-block
count, a surviving pass-through-rewrite mutant, or any deny-only unauthorized
output contradicts the registered expectation and triggers a bug audit.
