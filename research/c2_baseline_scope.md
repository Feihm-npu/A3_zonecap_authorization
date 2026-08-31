# C2 baseline scope

Status: exp-10 protocol, fixed before execution.

The exp-07 corpus is replayed without changing any request. Baselines are compared in two ways: overall fail-open/false-block behavior on the full ZoneCap corpus, and agreement only on scenarios whose mutated field the baseline can express. A baseline is not penalized as an implementation error for an explicitly `N/A` dimension; the unrestricted projection is still reported as a false allow on the full policy.

- **OPC UA role projection:** subject/role, target asset/node, and action/permission. Zone, conduit, physical parameter, time, mode, and pre-action sequence are `N/A` in this functional projection. This is not a claim that an OPC UA server implementation was benchmarked.
- **PLC ABAC projection:** subject, source and target zone attributes, asset, action, time, and mode. Conduit identity, physical parameter interval, and pre-action sequence are `N/A`. No complete runnable artifact was located in S1, so this remains the preregistered functional reference.
- **SINT pinned profile:** subject/holder, invariant resource, action subset, non-negative physical maximum, expiry upper bound, and delegation depth, grounded in the executable token instance from pinned commit `2461a911b8c3d7ed9da3f7662b33678f688eb826`. Zone, conduit, mode, and sequence are `N/A`; bilateral parameter and time windows are `partial` because the profile supplies a non-negative upper maximum and expiry, not arbitrary raised lower bounds.

For every baseline, the same held-out valid and mutation records are retained. The fair expressible-scenario subset includes valid cases and only mutation categories fully enforced by that projection. Both the full-corpus outcome and the subset outcome are reported.
