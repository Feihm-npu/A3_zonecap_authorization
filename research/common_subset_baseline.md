# Common-Subset Capability Baseline

Status: S2 exp-05 protocol and source boundary, fixed before execution.

## Fair common subset

The comparison uses only three authority dimensions supported without inventing
semantics for any system:

1. invariant exact resource binding (`modbus://cell/valve`);
2. action-set attenuation from `{set, read}` to `{set}`;
3. a non-negative physical parameter upper bound from `1.0` to `0.4`.

ZoneCap can express richer zone, conduit, asset-set, bilateral interval, mode,
and history constraints, but those are excluded here. At pinned commit
`2461a911b8c3d7ed9da3f7662b33678f688eb826`, SINT delegation preserves the
parent `resource`, filters requested actions to the parent action set, computes
numeric physical maxima with the more restrictive minimum, and clamps a later
requested expiry to the parent expiry. Its geofence and other non-common fields
are excluded. The executable SINT instance is created by the pinned implementation,
not by the Python comparison adapter.

The Dodson/CHERI Macaroons baseline is a schema adapter rather than a claimed
runnable reproduction: root first-party caveats remain in the token, and child
delegation appends resource/action/value restrictions evaluated conjunctively.
No physical reachability theorem or rewrite/hold contract is attributed to that
work without a corresponding artifact.

## Identical evaluation

All three adapters receive the same complete request cross-product over two
resources, three actions, and six non-negative parameter values, for both parent
and child tokens. Any cross-adapter decision mismatch or child permission absent
from its parent is retained.

The induced control intervals are then applied to three fixed signed 1D plants
through horizon 6 using exact rational interval propagation. Every adapter,
plant, and horizon is reported. This experiment asks whether the common digital
attenuation subset induces the same physical inclusion; it does not claim that
the baselines provide ZoneCap's compiler-to-reachability proof.

## Source evidence

- SINT repository and fixed commit:
  `https://github.com/sint-ai/sint-protocol.git`,
  `2461a911b8c3d7ed9da3f7662b33678f688eb826`.
- SINT source files hashed in the run manifest: `WHITEPAPER.md`,
  `packages/capability-tokens/src/delegator.ts`, and
  `packages/capability-tokens/src/validator.ts`.
- Dodson, *Capability-based access control for cyber physical systems*,
  Cambridge Technical Report UCAM-CL-TR-963 (2021). The report was identified
  during S1; no new PDF was downloaded in exp-05.
