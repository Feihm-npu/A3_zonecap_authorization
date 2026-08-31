# Exp-07 held-out encoding protocol

This document was fixed after source-byte freezing and before policy-table encoding or any held-out execution.

## Source-grounded decisions

- Held-out A uses the six-zone IACS Security Matrix in CPwE Figure 2-24 (PDF page 57, printed page 2-40). Every `Permit` or `Default - Permit` cell becomes a directed root grant; every `Deny` cell and every zone/conduit mismatch remains fail-closed. Figure 2-23 and its accompanying text define the zone-, device-, and trusted-IP-conduit interpretations.
- Held-out B uses the landside signalling portion of the individual railway zone model in ENISA Figure 10 (PDF page 30, printed page 29). Only directly drawn adjacent conduits among Business Network, Industrial/Plant DMZ, Rail OP/Control Centre, Automation/Interlock System Head, Interlock, RBC, and Rail Crossing are encoded. Each drawn conduit is represented in both directions because the selected table uses the report's `+` interpretation: data flow allowed in both directions. Skipped-layer communication is denied. The report's communication-matrix rules on printed pages 27-28 remain the fail-closed basis.
- No topology edge is inferred merely from physical proximity. Ambiguous, optional, external, redundant, or out-of-scope branches in a figure are recorded as unsupported constructs rather than silently granted.

## Evaluation-only dimensions

The source documents fix zone/conduit topology but do not fully specify ZoneCap's action, scalar parameter, time, mode, or pre-action-sequence dimensions. Exp-07 therefore applies one common, source-independent evaluation overlay to every source-grounded root grant:

- actions: `read` and `write`;
- normalized parameter interval: `[0, 100]`;
- tick window: `[100, 200]`;
- modes: `normal` and `maintenance`;
- required pre-action sequence: `authenticate`;
- one target asset per encoded target zone.

These overlay fields test representability and attenuation but are not attributed to Cisco/Rockwell or ENISA. They are identical across all grants and are locked in `policy_tables.json`.

## Independent decisions and delegation

- The oracle reads `policy_tables.json` directly and contains no import from `zonecap.compiler`, `zonecap.engine`, or `zonecap.models`.
- The ZoneCap path independently converts the same frozen table into `Architecture` input, calls the compiler, and evaluates the compiled capabilities.
- Requests comprise the complete valid cross-product for every grant over target asset, action, valid parameter boundary/interior values, valid time boundary/interior values, mode, and two satisfying histories. Each valid request produces one mutation for each registered single-field invalid value; no generated case is removed.
- Depth-1 and depth-2 delegation specifications are produced before either evaluator runs. Both evaluators receive the same explicit specifications. Every relation is checked independently for zone, conduit, asset, action, parameter, time, mode, and required-sequence refinement.
- Attempted widenings are reserved for exp-09; exp-07 records legal depth-1/depth-2 preservation/narrowing and decision equivalence only.
