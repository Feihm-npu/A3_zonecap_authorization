# Claims

Tags: `core` (project fails if this fails); `[S1]` | `[post-hoc: <run_id | review | S4>]`.
Status, by who sets it:
- `proposed` S1 · `testing` S2_RUN · `supports` | `refutes` | `inconclusive` S2_INTERPRET
- `accepted` | `insufficient` | `rejected` applied after S3_AWAIT · `superseded→C<n>` when rewritten
Never edit an `[S1]` claim's statement; supersede it.

## C1 [core] [S1]

Statement: Under conjunctive ZoneCap caveats and authority-preserving runtime effects, if capability c' attenuates c, then for any fixed plant model, initial-state set, disturbance set, and finite horizon H, the physical reachable set induced by c' is a subset of that induced by c.

If true: A syntactic refinement proof closes for the one-dimensional linear system and the general transition-system/MIMO lifting; exhaustive and seeded checks find zero child-reachable states outside the parent set at every registered horizon.

If false: A valid compiled child capability produces at least one physical trace/state not induced by its parent, or the proof requires defining attenuation itself in terms of reachable sets rather than the registered caveat order.

Alternatives:
- A1: Inclusion is a tautology caused by defining attenuation semantically rather than proving it from token syntax. → ruled out by: exp-01, exp-02
- A2: Inclusion is an artifact of scalar interval arithmetic and fails for coupled, state/history-dependent MIMO systems. → ruled out by: exp-03
- A3: Inclusion holds only because the prototype omits meaningful `REWRITE`/`DEFER` behavior. → ruled out by: exp-04

Status: accepted

## C2 [core] [S1]

Statement: For two held-out IEC 62443-aligned reference architectures, ZoneCap compilation is decision-equivalent to an independent zone/conduit policy oracle while every depth-1 and depth-2 delegation preserves or narrows zone, conduit, asset, action, parameter, time, mode, and pre-action-sequence authority.

If true: The compiler and independent oracle agree on every valid request and every registered single-field mutation; all legal delegations pass and every attempted widening is rejected across both held-out architectures.

If false: Any oracle/compiler decision mismatch, accepted privilege widening, or architecture element that cannot be represented by the registered capability schema refutes the claim.

Alternatives:
- A1: Agreement comes from hand-authored fixtures mirroring compiler code. → ruled out by: exp-08
- A2: Non-amplification is trivial because delegation chains or cross-zone paths are not exercised. → ruled out by: exp-09

Status: superseded→C6

## C3 [S1]

Statement: A runtime enforcement semantics with ALLOW, DENY, ATTENUATE, REWRITE, and DEFER preserves C1 whenever rewrites remain within the effective capability and deferrals are modeled as parent-admissible stutter transitions.

If true: The effect-level proof composes with C1, bounded model checking reports no trace-inclusion or safety violations, and all five effects are reachable on registered scenarios without deadlock or unauthorized output.

If false: An effect emits an action outside the effective capability, introduces a child-only physical transition, deadlocks a registered safe request, or cannot be given compositional semantics.

Alternatives:
- A1: Any apparent improvement is achievable by deny-only enforcement, so new effects add no policy value. → ruled out by: exp-13
- A2: Safety holds only on hand-picked traces. → ruled out by: exp-14

Status: superseded→C7

## C4 [S1]

Statement: ZoneCap revocation and deterministic conflict resolution prevent post-revocation execution, privilege union across concurrent holders, and deadlock in the preregistered bounded multi-principal model.

If true: Model checking and adversarial schedules find zero post-revocation executions, unauthorized permission unions, or deadlocks; liveness holds within the registered approval timeout.

If false: Any registered interleaving admits one of those violations or requires an unstated trusted coordinator/fairness assumption.

Alternatives:
- A1: Bounded verification hides longer deadlock cycles. → ruled out by: exp-18
- A2: Safety depends on a benign centralized scheduler rather than the protocol. → ruled out by: exp-19

Status: rejected

## C5 [S1]

Statement: On the approved OpenPLC/Jetson testbed, ZoneCap's p99 decision latency is at most 1 ms and consumes at most 10% of a 10 ms PLC scan cycle while enforcing the registered policy set.

If true: Every registered repetition on the approved hardware meets both thresholds, with all seeds/repetitions reported and decision-equivalence checks passing.

If false: Any registered repetition exceeds either threshold, or the optimized path changes policy decisions.

Alternatives:
- A1: The threshold is met only through warm caches or omitted signature/revocation checks. → ruled out by: exp-23
- A2: The threshold is met only for a toy policy count. → ruled out by: exp-24

Status: insufficient

## C6 [core] [post-hoc: review]

Statement: For the frozen CPwE/CIP Security matrix and ENISA landside-signalling zone/conduit subgraph, augmented with the preregistered source-independent action, parameter, time, mode, and pre-action-sequence overlay, ZoneCap is decision-equivalent to the separate table oracle over the complete generated corpus, and every registered depth-1 and depth-2 delegation preserves or narrows all eight authority dimensions.

If true: The compiler and separate oracle agree on every generated valid request and single-field mutation from the frozen tables and overlay; every legal registered delegation passes all eight dimension checks and every registered attempted widening is rejected.

If false: Any retained compiler-oracle mismatch, legal-delegation failure, or accepted registered widening refutes the claim within this frozen corpus. A disagreement between independent source encodings would separately invalidate the assumption that the frozen table accurately represents the cited source architecture.

Alternatives:
- A1: Perfect agreement is caused by compiler fixtures or a disabled evaluator. → ruled out by: exp-07, exp-08
- A2: Non-amplification is an artifact of omitting chain depth or multi-conduit paths. → ruled out by: exp-09
- A3: Compiler and oracle share a human source-interpretation error through `policy_tables.json`. → not ruled out; bounded explicitly in the accepted wording and REVIEW

Status: accepted

## C7 [post-hoc: review]

Statement: The registered actuation-event runtime semantics with ALLOW, DENY, ATTENUATE, REWRITE, and DEFER preserves C1 when every emitted rewrite and hold is within the effective capability and parent-realizable, and every deferral is a parent-admissible stutter transition.

If true: The effect-refinement argument composes with C1; all registered one-request and bounded composed traces preserve authority and parent realizability, reach all five effects, and terminate or fail closed within the registered bound.

If false: A registered effect emits an action outside effective authority, introduces a child-only physical transition, violates parent realizability/stutter, or leaves a request unresolved beyond the registered bound.

Alternatives:
- A1: Deny-only enforcement provides the same registered safe-service behavior. → ruled out by: exp-13 for the fixed evaluation corpus
- A2: Preservation appears only on hand-picked effect sequences. → ruled out by: exp-14 through horizon 5
- A3: The result extends automatically to fixed-tick, asynchronous, or unbounded execution. → not claimed and not tested

Status: accepted
