# Story

## Working title

**ZoneCap: Attenuable capabilities linking industrial zone/conduit policy to physical reachability**

The title names the method, the policy object, and the formal consequence without claiming IEC 62443 conformance, universal architecture coverage, or target-hardware performance.

Target format: IEEE Transactions on Industrial Informatics regular issue. This evidence-complete Markdown draft is the source manuscript; page-budget compression should be performed after figures and the journal template are rendered.

## One-sentence contribution

For cross-zone industrial control, ZoneCap compiles frozen zone/conduit policy tables and explicit physical caveats into attenuable capabilities, establishes under explicit operational premises that syntactic attenuation implies physical trace and reachable-set inclusion, and preserves that refinement under a registered five-effect actuation-event semantics, as tested on two frozen reference-derived policy tables and bounded exhaustive models.

## Reader belief shift

**Before.** Capability systems can narrow digital permissions, and cyber-physical runtime enforcers can suppress or correct actuator commands, but neither fact alone tells an OT engineer whether delegated authority induces a subset of the parent's possible physical behavior. A zone/conduit diagram also does not by itself provide a delegatable runtime authorization object.

**After.** The physical monotonicity question can be reduced to six inspectable obligations: syntax independent of reachability, conjunctive monotone compilation, history-language refinement, sound and parent-realizable effects, common plant uncertainty, and a request-abstracted reachable-set definition. ZoneCap discharges these obligations for its registered semantics, matches a separate oracle on the complete generated corpus from two frozen source-derived tables plus a declared overlay, and exposes delayed revocation delivery as a boundary that requires an additional freshness contract.

## Contribution type

- **Primary:** method -- a zone/conduit-policy-to-capability compiler plus a five-effect runtime authorization semantics.
- **Formal finding:** conditional syntactic-attenuation-to-physical-reachability refinement.
- **Empirical validation:** exact, seeded, mutation, baseline, and bounded-exhaustive checks for the accepted claims.
- **Negative boundary:** issuance-relative revocation is not guaranteed by the unfenced bounded protocol under delayed delivery.

## Accepted claim spine

1. **C1:** field-wise conjunctive attenuation implies physical trace and reachable-set inclusion for any fixed plant transition system when all registered refinement obligations hold.
2. **C6:** on the frozen CPwE/CIP Security matrix and ENISA landside-signalling subgraph, with the declared source-independent overlay, ZoneCap matches the separate table oracle over the complete generated corpus and rejects every registered depth-1/depth-2 widening.
3. **C7:** the registered actuation-event semantics for `ALLOW`, `DENY`, `ATTENUATE`, `REWRITE`, and `DEFER` preserves C1 when rewrites and holds are both authorized and parent-realizable and deferrals are parent-admissible stutters.

## Required negative and limitation statements

- **C4 is rejected, not silently dropped.** Eight issuance-relative stale executions occurred under fair one- and two-turn revocation delivery delays. Delivered-state safety remained clean, but that narrower observation does not rescue the original claim.
- **C5 is insufficient, not treated as a local success.** The 19.326 us x86 full-sanity p99 is a timer/check harness diagnostic only. There is no accepted OpenPLC/Jetson performance result until external exp-22--25 are frozen, returned, and audited.
- The held-out sources ground zone/conduit topology only. Target-asset identifiers are deterministic per-zone encoding fields; action, parameter, time, mode, and pre-action-sequence fields are a preregistered evaluation overlay.
- The proof assumes trusted authorization-relevant context and a correct/common plant relation; it does not establish safety under compromised sensors, model mismatch, asynchronous distributed execution, or a fixed-tick adapter.

## Terminology ledger

| Canonical term | First-use definition | Do not substitute with | Decision |
|---|---|---|---|
| ZoneCap | The proposed compiler and runtime authorization semantics | framework, platform, shield | Use `ZoneCap` throughout |
| capability | A scoped authorization object over issuer/subject, zone endpoints, conduit, asset, action, parameter, time, mode, and required physical-event history | permission token, policy ticket | Use `capability`; use `token` only for a concrete serialized realization |
| attenuation, `c' \preceq c` | Field-wise narrowing that preserves issuer and zone binding and narrows all remaining authority dimensions | restriction, reduction, delegation | Use `attenuation` for the formal relation; `delegation` for the lifecycle operation |
| effective capability | The capability presented after all static and runtime attenuation | active policy, current token | Use only for the current enforceable scope |
| zone/conduit policy table | A frozen directed table derived from selected source topology | IEC policy, standard policy | Never imply that the full standard supplied all fields |
| source-independent overlay | The common action, parameter, time, mode, and required-sequence fields added for evaluation | source policy | State on first mention in every relevant section |
| target-asset identifier | A deterministic identifier assigned to each encoded target zone for corpus construction | source-listed device | Do not imply that the source documents enumerate these identifiers |
| authorization relation, `Adm_c(eta)` | Physical inputs authorized by capability `c` at physical history `eta` | permission set | Use this notation in the theorem |
| request-abstracted emission relation, `Ebar_c(eta)` | Union of physical outputs over all raw requests at history `eta` | output set | Distinguish from same-request behavior |
| physical history, `eta` | Authorization-relevant projection of states, emitted events, trusted mode, and time | context | Use `context` only for runtime inputs, not the theorem object |
| actuation-event semantics | Semantics in which `DENY` and `ATTENUATE` emit no physical transition and `DEFER` emits only the registered hold | scan-cycle semantics, fixed-tick semantics | Never imply that fixed-tick execution was tested |
| parent realizability | Every child-emitted action or hold can also be emitted under the parent at the related physical history | parent authorization | Keep distinct from mere membership in the parent scope |
| parent-admissible stutter | A registered hold action available to the parent that leaves the abstract physical state unchanged | no-op, frozen plant | Use only for the registered `read` hold binding |
| revocation issuance | Authority-service event that creates the intent to revoke | revocation | Always contrast with delivery when discussing C4 |
| revocation delivery | Resolver-local event that atomically marks the holder revoked and removes pending commands | revocation propagation | The zero-violation delivered-state boundary |
| IEC 62443-aligned | Consistent with the selected source zone/conduit structures | IEC 62443-compliant, certified | Avoid in headline claims when the narrower source description is available |

## Narrative rule

Lead with the authorization-to-physics gap, not with agent novelty or hardware speed. Present C1 as a conditional theorem, C6 as a bounded source-derived validation, and C7 as a registered semantic composition. Use C4 to demonstrate why freshness is an explicit assumption rather than a footnote, and leave C5 outside the contribution until target-hardware evidence exists.
