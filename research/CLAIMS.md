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

Status: proposed

## C2 [core] [S1]

Statement: For two held-out IEC 62443-aligned reference architectures, ZoneCap compilation is decision-equivalent to an independent zone/conduit policy oracle while every depth-1 and depth-2 delegation preserves or narrows zone, conduit, asset, action, parameter, time, mode, and pre-action-sequence authority.

If true: The compiler and independent oracle agree on every valid request and every registered single-field mutation; all legal delegations pass and every attempted widening is rejected across both held-out architectures.

If false: Any oracle/compiler decision mismatch, accepted privilege widening, or architecture element that cannot be represented by the registered capability schema refutes the claim.

Alternatives:
- A1: Agreement comes from hand-authored fixtures mirroring compiler code. → ruled out by: exp-08
- A2: Non-amplification is trivial because delegation chains or cross-zone paths are not exercised. → ruled out by: exp-09

Status: proposed

## C3 [S1]

Statement: A runtime enforcement semantics with ALLOW, DENY, ATTENUATE, REWRITE, and DEFER preserves C1 whenever rewrites remain within the effective capability and deferrals are modeled as parent-admissible stutter transitions.

If true: The effect-level proof composes with C1, bounded model checking reports no trace-inclusion or safety violations, and all five effects are reachable on registered scenarios without deadlock or unauthorized output.

If false: An effect emits an action outside the effective capability, introduces a child-only physical transition, deadlocks a registered safe request, or cannot be given compositional semantics.

Alternatives:
- A1: Any apparent improvement is achievable by deny-only enforcement, so new effects add no policy value. → ruled out by: exp-13
- A2: Safety holds only on hand-picked traces. → ruled out by: exp-14

Status: proposed

## C4 [S1]

Statement: ZoneCap revocation and deterministic conflict resolution prevent post-revocation execution, privilege union across concurrent holders, and deadlock in the preregistered bounded multi-principal model.

If true: Model checking and adversarial schedules find zero post-revocation executions, unauthorized permission unions, or deadlocks; liveness holds within the registered approval timeout.

If false: Any registered interleaving admits one of those violations or requires an unstated trusted coordinator/fairness assumption.

Alternatives:
- A1: Bounded verification hides longer deadlock cycles. → ruled out by: exp-18
- A2: Safety depends on a benign centralized scheduler rather than the protocol. → ruled out by: exp-19

Status: proposed

## C5 [S1]

Statement: On the approved OpenPLC/Jetson testbed, ZoneCap's p99 decision latency is at most 1 ms and consumes at most 10% of a 10 ms PLC scan cycle while enforcing the registered policy set.

If true: Every registered repetition on the approved hardware meets both thresholds, with all seeds/repetitions reported and decision-equivalence checks passing.

If false: Any registered repetition exceeds either threshold, or the optimized path changes policy decisions.

Alternatives:
- A1: The threshold is met only through warm caches or omitted signature/revocation checks. → ruled out by: exp-23
- A2: The threshold is met only for a toy policy count. → ruled out by: exp-24

Status: proposed
