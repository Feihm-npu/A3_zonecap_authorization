# ZoneCap TII Writing Outline

Status: **full draft present; display plan revised after manuscript-wide figure audit**  
Target: **IEEE Transactions on Industrial Informatics, regular paper**  
Template: `tii-articles-template.tex`  
Submission constraint: **10 pages maximum in the IEEE double-column layout**  
Evidence freeze: C1, C6, and C7 are accepted; C4 is a required negative result; C5 remains conditional on audited exp-22--25 results.

This file is the writing contract for the TII manuscript. Paragraph identifiers are stable handles for later drafting and targeted revision. Internal claim and evidence identifiers are planning metadata and must not appear in the submitted paper.

## 1. Manuscript identity

### 1.1 Working title

**ZoneCap: Attenuable Capabilities Linking Industrial Zone/Conduit Policy to Physical Reachability**

Title decision:

- Retain as the working title until the hardware result is audited.
- Keep `ZoneCap`, `attenuable capabilities`, `zone/conduit policy`, and `physical reachability` searchable.
- Do not add `IEC 62443-compliant`, `real-time`, `low-latency`, or `safe` unless the exact claim is supported at submission time.
- Revisit the title only after Sections V and VII are stable.

### 1.2 Paper type and primary reader

- Paper type: formal-method and industrial-authorization method paper with compiler and runtime-semantics validation.
- Primary reader: a TII reviewer familiar with industrial control, industrial cyber-physical systems, networked embedded systems, and industrial security, but not necessarily capability theory or reachability analysis.
- Reader-question order:
  1. Relevance: why cross-zone delegated actuation creates an industrial authorization problem.
  2. Novelty: why digital attenuation and runtime correction do not already imply physical refinement.
  3. Trust: what is proved, what is exhaustively checked, and what is only bounded.
  4. Reuse: which compiler, capability fields, and runtime obligations another system can implement.
  5. Meaning: where the guarantee stops, especially at revocation delivery and untrusted physical context.

### 1.3 One-sentence argument

In cross-zone industrial control, ZoneCap compiles source-derived zone/conduit policy tables and explicit physical caveats into attenuable capabilities, and, under six inspectable operational obligations, connects syntactic attenuation to physical trace and reachable-set inclusion while preserving that refinement through a registered five-effect actuation-event semantics.

### 1.4 Storyline

`cross-zone software principals need delegatable actuation authority`

`-> zone/conduit models describe segmentation but are not runtime capability objects`

`-> existing capabilities narrow digital scope, while runtime enforcers edit commands`

`-> neither guarantee alone orders the induced physical behavior`

`-> ZoneCap inserts an explicit compiler-to-emission-to-plant refinement contract`

`-> positive conjunctive attenuation narrows authorization`

`-> sound and parent-realizable effects narrow request-abstracted emissions`

`-> a common plant relation lifts emission inclusion to finite-horizon trace and reachable-set inclusion`

`-> source-derived compiler tests and bounded five-effect tests validate the concrete realization`

`-> delayed revocation exposes freshness as an additional distributed execution contract`

`-> target-hardware measurements assess feasibility but do not create the formal guarantee`

### 1.5 Intended reader belief shift

- Before reading: attenuation is a digital least-privilege property, and physical safety must be checked separately by the controller or runtime shield.
- After reading: attenuation can induce a physically refining authority relation, but only when compilation, runtime effects, physical history, and the plant interface satisfy explicit obligations.
- Engineering consequence: capability and enforcer implementations should expose these obligations as interface contracts rather than treating physical refinement as an automatic consequence of token narrowing.

### 1.6 Contribution contract

The Introduction will present three contributions and one boundary finding:

1. **Formal bridge [C1].** A conditional refinement result from field-wise capability attenuation to request-abstracted physical trace and reachable-set inclusion under six named obligations.
2. **Industrial policy compiler [C6].** A compiler from two frozen, source-derived zone/conduit tables plus a declared source-independent overlay to attenuable capabilities, validated on the complete generated corpus and registered depth-1/depth-2 delegations.
3. **Runtime authorization semantics [C7].** An actuation-event semantics for `ALLOW`, `DENY`, `ATTENUATE`, `REWRITE`, and `DEFER` that preserves the refinement when every emitted action or hold is authorized and parent-realizable.
4. **Boundary finding [C4, rejected].** Local delivered-state revocation safety does not imply issuance-relative safety under delayed delivery; eight registered stale executions expose the need for freshness or atomic delivery.

The hardware study is supporting feasibility evidence, not a fourth conceptual contribution. It enters the paper only after exp-22--25 are frozen, returned, and audited.

## 2. Claim and boundary hierarchy

### 2.1 What leads the paper

1. The conditional theorem, not the enumeration count.
2. The compiler and runtime semantics as the concrete mechanism that discharges the theorem obligations.
3. Exact, mutation, seeded, and bounded-exhaustive evidence as falsification and implementation checks.
4. The revocation counterexample as an engineering boundary.
5. Hardware performance as conditional feasibility evidence.

### 2.2 Mandatory boundaries

- The theorem concerns request-abstracted emissions, not same-request output inclusion.
- Parent and child share the same physical-history projection, plant transition relation, initial set, disturbance set, and horizon.
- Authorization-relevant context and mode are trusted.
- The source documents ground zone/conduit topology; action, parameter, time, mode, and required-event sequence are a declared evaluation overlay.
- The ENISA case is limited to the landside-signalling subgraph.
- Compiler and oracle are separate code paths but share one human-authored source-table interpretation.
- Runtime results concern the registered actuation-event semantics, not fixed-tick PLC semantics, asynchronous distributed execution, or unbounded liveness.
- Original issuance-relative revocation claim C4 is refuted.
- The x86 exp-26 timer result is not target-hardware performance evidence.

### 2.3 Language guardrails

- Use `prove` or `establish` only for the conditional theorem with its obligations adjacent.
- Use `matched` or `agreed` only for the complete frozen compiler corpus.
- Use `preserved in the registered bounded actuation-event semantics` for the five-effect result.
- Use `refuted` for the original issuance-relative revocation claim.
- Use `source-derived` or `IEC 62443-aligned`; never use `IEC 62443-compliant` or `certified`.
- Use `prototype testbed` for Jetson/OpenPLC; never use `production deployment`.
- Avoid `first`, `comprehensive`, `universal`, `always`, `never`, and unqualified `guarantee`.

## 3. Terminology ledger

| Canonical term | First-use definition or notation | Required distinction |
|---|---|---|
| ZoneCap | Proposed compiler and runtime authorization semantics | Not a generic framework, shield, or full IEC toolchain |
| capability | Scoped authorization object over structural and behavioral dimensions | Use `token` only for a serialized realization |
| attenuation, $c' \preceq c$ | Field-wise narrowing of physical authority dimensions | Different from the delegation lifecycle operation |
| effective capability | Capability remaining after static and runtime attenuation | Not an active policy or controller state |
| zone/conduit policy table | Frozen directed table derived from selected source topology | Not the complete IEC 62443 standard |
| source-independent overlay | Added action, parameter, time, mode, and required-event-sequence fields | Must not be attributed to the source documents |
| physical history, $\eta$ | Shared authorization-relevant projection of state, emitted events, trusted mode, and time | Distinct from token-internal decisions and raw denied requests |
| authorization relation, $\operatorname{Adm}_c(\eta)$ | Physical inputs authorized by capability $c$ | Distinct from emitted behavior |
| request-abstracted emission relation, $\overline E_c(\eta)$ | Union of physical outputs over raw requests | Distinct from same-request behavior |
| parent realizability | Every child output or hold can also be emitted by the parent | Stronger than membership in the parent authorization set |
| actuation-event semantics | Semantics in which no-command effects do not advance the plant | Not fixed-tick PLC semantics |
| parent-admissible stutter | Registered parent-realizable hold that leaves the abstract physical state unchanged | Do not call the physical plant frozen |
| revocation issuance | Authority-service event expressing revocation intent | Must be distinguished from delivery |
| revocation delivery | Resolver-local state update that removes the holder and pending command | The boundary at which local safety remained clean |

## 4. TII page and display budget

Budgets are provisional until the first real IEEE render. Page counts include local figures and tables but exclude spill caused by float placement.

| Manuscript component | Target words | Target pages | Planned displays |
|---|---:|---:|---|
| Title, abstract, keywords | 190--220 abstract words | 0.55 | None |
| I. Introduction | 520--600 | 0.80 | Fig. 1 may start at the end |
| II. Related Work and Design Gap | 300--360 | 0.45 | None |
| III. System Model and Problem Statement | 430--500 | 0.70 | Table I |
| IV. ZoneCap Design | 550--650 | 1.00 | Fig. 1 |
| V. Physical Refinement Guarantee | 560--650 | 1.00 | Fig. 2 |
| VI. Evaluation Methodology | 300--380 | 0.55 | None; protocol is prose/artifact material |
| VII. Results | 850--1050 | 2.55 | Fig. 3, Fig. 4, Table II, Table III |
| VIII. Revocation Boundary and Discussion | 420--520 | 0.90 | Fig. 5 |
| IX. Conclusion and availability line | 100--140 | 0.20 | None |
| References | N/A | 0.90 | None |
| Float/layout reserve | N/A | 0.85 | N/A |
| **Total** | **approximately 4,700--5,100 body words** | **10.00** | **five figures and three tables; one additional figure conditional on hardware** |

Compression rule: cut repeated explanation and low-priority display detail before removing a premise, negative result, failed control, or scope limitation.

### 4.1 Display plan

| Display | Purpose | Priority | Compression/cut rule |
|---|---|---|---|
| Fig. 1 | End-to-end ZoneCap path: source table -> compiler -> root capability -> attenuation -> five-effect PEP -> physical emission -> plant | Required | One full-width architecture figure; no decorative components |
| Table I | Capability fields, source/overlay origin, attenuation rule, runtime check | Required | Merge notation and provenance so the text does not repeat field definitions |
| Fig. 2 | Refinement chain plus exact reachable intervals for three signed 1D plants | Required | Keep the theorem as the hero panel and the executable intervals as validation panels |
| Table II | Policy-projection scope, fair-subset agreement, and unrepresented full-corpus cases | Required | This is a conventional quantitative baseline table, not an experiment inventory |
| Fig. 3 | Source-level compiler cases, corpus composition, mutation adequacy, and delegation controls | Required | Merge source and corpus panels if page pressure is severe |
| Table III | Five-effect correspondence for ZoneCap, Lanotte/Roop, and pinned SINT | Preferred | Move to supplementary material before removing a quantitative result figure |
| Fig. 4 | Effect mix, exhaustive sequence coverage, and deny-only service loss | Required | Keep physical-output loss distinct from recovery-decision loss |
| Fig. 5 | Revocation delay counts plus issuance/delivery timeline | Required | Single-column negative-result figure; do not omit |
| Fig. 6 | Per-repetition latency, tail distribution, scaling, and executable baselines | Conditional | Activate only after exp-22--25 pass raw-data and equivalence audits |

Detailed run inventories, raw sample descriptions, complete mutation matrices, and per-seed values belong in the public artifact, not as additional main-paper tables. Every seed must still be reported in the artifact and summarized without selection in the manuscript.

## 5. Front matter design

### 5.1 Abstract: one paragraph, 150--250 words

Draft last. Target 190--220 words and eight sentence roles.

| Sentence | Job | Planned content | Evidence/boundary |
|---|---|---|---|
| A1 | Context | Cross-zone industrial commands are increasingly issued by delegated software principals and require authority bounded by physical consequence. | Industrial motivation only |
| A2 | Gap | Digital capability attenuation and command-editing enforcement do not independently imply that child authority induces a subset of parent physical behavior. | Exact research gap |
| A3 | Approach | Introduce ZoneCap as a source-table compiler, attenuation relation, and five-effect runtime authorization semantics. | No `IEC-compliant` claim |
| A4 | Formal result | State conditional syntax-to-emission-to-trace/reachable-set refinement and name the dependence on explicit obligations. | C1; no same-request claim |
| A5 | Compiler result | Give the 58,968-case agreement and 672 delegation-dimension checks at the frozen source-plus-overlay scope. | C6/E07; identify bounded corpus |
| A6 | Runtime result | Give one-request, composed, and bounded-exhaustive evidence with all five effects reached and no registered violation. | C7/E12/E14; actuation-event semantics |
| A7 | Boundary result | State that delayed delivery produced eight issuance-relative stale executions and therefore requires freshness or atomic delivery. | C4/E19; explicit refutation |
| A8 | Feasibility/implication | If audited hardware evidence exists, give p99 and scan occupancy; otherwise omit performance and close with the inspectable-contract implication. | Conditional exp-22--25 only |

Abstract exclusions:

- No references, equations, undefined abbreviations, implementation inventory, or x86 exp-26 latency.
- No detailed baseline counts.
- No claim that enumeration proves the theorem.

### 5.2 Keywords

Select four or five terms after title stabilization, in alphabetical order. Candidate pool:

- authorization
- capability-based security
- cyber-physical systems
- industrial control systems
- runtime enforcement

## 6. Section-level and paragraph-level outline

## I. Introduction

Section job: establish the industrial problem, isolate the missing physical-refinement relation, and state the bounded contribution set.

### I-P1 — Cross-zone actuation creates an authority problem

- Job: context.
- Target: 95--115 words.
- Lead idea: zone/conduit segmentation controls communication paths, but delegated software principals ultimately request physical actions.
- Include: multi-organizational or autonomous software principals; asset, action, parameter, time, mode, and history dimensions; consequence of over-broad delegated scope.
- Cite: IEC 62443-3-2 for zone/conduit risk decomposition; industrial CPS context sources as needed.
- End condition: motivate a delegatable authorization object whose meaning reaches beyond packet admission.
- Exclude: agent hype, detailed threat examples, and claims that IEC 62443 specifies ZoneCap fields.

### I-P2 — Capability attenuation narrows digital scope but not automatically physical behavior

- Job: comparison.
- Target: 95--115 words.
- Include: CPS capabilities, CHERI Macaroons/Dodson, SINT, and delegation-time narrowing.
- Explain: a syntactic subset of fields is not yet a physical reachable-set relation because runtime emission and plant evolution intervene.
- Cite: closest capability systems, using their own contribution language.
- Transition: physical consequences depend on what the enforcement layer actually emits.

### I-P3 — Runtime enforcement edits commands but lacks delegation refinement

- Job: gap.
- Target: 105--125 words.
- Include: physics-aware access control, Smart I/O, edit automata, Lanotte/Roop, and scalable enforcement.
- Credit: their correction, suppression, soundness, progress, or scalability contributions.
- Distinguish: these mechanisms do not define a field-wise delegated authority relation connected to parent/child physical traces.
- Add IEC modeling boundary: zone/conduit design tools model risk/topology rather than producing this runtime refinement contract.
- Transition: identify the missing compiler-to-emission interface.

### I-P4 — Core insight and ZoneCap approach

- Job: approach.
- Target: 100--120 words.
- Include the three-step refinement:
  1. conjunctive attenuation -> authorization inclusion;
  2. sound and parent-realizable effects -> request-abstracted emission inclusion;
  3. common plant uncertainty -> trace and reachable-set inclusion.
- Introduce Fig. 1.
- State that physical history is shared and authorization-relevant.
- Exclude validation numbers; those belong in Results.

### I-P5 — Contributions and boundary preview

- Job: approach.
- Target: 125--145 words.
- Use a compact numbered list or one paragraph with three parallel contribution sentences.
- State C1, C6, and C7 at accepted scope.
- Add one final sentence previewing the delayed-revocation counterexample.
- Add hardware feasibility only if exp-22--25 pass audit; do not call it a conceptual contribution.
- Final transition: Section II positions the work, followed by system model, method, theorem, and validation.

## II. Related Work and Design Gap

Section job: credit the closest mechanisms and make the exact combination delta visible without a literature catalogue.

### II-P1 — Capabilities and delegated authorization for CPS and agents

- Job: comparison.
- Target: 95--115 words.
- Group: Dodson/CHERI Macaroons, SINT, ZTPM, and DARC.
- Compare dimensions: physical-resource scope, signed tokens, attenuation, physical constraints, approval/revocation, and formal contracts.
- End with the remaining gap: no demonstrated syntax-to-request-abstracted-physical-reachability refinement tied to a zone/conduit compiler.
- Do not claim that these systems lack safety or formal guarantees outside this specific relation.

### II-P2 — Physics-aware authorization and runtime enforcement

- Job: comparison.
- Target: 100--120 words.
- Group: CPAC/TwinGridShield as model-informed authorization; Smart I/O and Lanotte/Roop/Baird as enforcement mechanisms.
- Preserve their ownership of controller mediation, correction, soundness/progress, and implementation scalability.
- State ZoneCap's complementary role: define delegated authorization scope and the obligations an effect engine must satisfy.
- Avoid performance superiority language.

### II-P3 — Industrial zone/conduit modeling

- Job: comparison.
- Target: 95--115 words.
- Group: IEC 62443-3-2 risk assessment, automated risk workflows, and zone/conduit DSLs.
- Distinguish: design-time topology/risk representation versus a runtime attenuable capability connected to physical behavior.
- Close with one exact delta sentence covering compiler + theorem + five effects, without `first` language.

## III. System Model and Problem Statement

Section job: define the objects needed to state the problem and make every trust boundary inspectable before the method.

### III-P1 — System actors and trust boundary

- Job: context.
- Target: 75--90 words.
- Define: policy authority, compiler, issuer/delegator, software principal, policy decision/enforcement point, plant, trusted context provider, and revocation channel.
- State trusted components and explicitly untrusted or out-of-scope components.
- State that the physical plant relation is fixed and common for the theorem.
- Refer to Fig. 1.

### III-P2 — Capability object

- Job: context.
- Target: 75--90 words plus one compact equation.
- Define the capability tuple over issuer/subject, source/destination zone, conduit, asset, operation, parameter, time, mode, and required physical-event history.
- Use Table I to record field origin and runtime check.
- Clarify that subject identity may change under delegation while physical authority narrows.

### III-P3 — Syntactic attenuation

- Job: context.
- Target: 75--90 words plus the subset/prefix relation.
- Define $c' \preceq c$ independently of plant reachability.
- State zone/issuer preservation and subset relations for positive conjunctive caveats.
- Define sequence extension as the implementation rule sufficient for history-language refinement.
- Exclude default grants, negated exceptions, and non-monotone conflict combiners from the theorem scope.

### III-P4 — Physical history, emissions, traces, and reachability

- Job: context.
- Target: 105--125 words plus compact definitions.
- Define $\eta$, $\operatorname{Adm}_c(\eta)$, $\operatorname{Emit}_c(\eta,q)$, $\overline E_c(\eta)$, $\mathrm{Tr}_H(c)$, and $\mathrm{Reach}_t(c)$.
- Explicitly contrast request-abstracted emission inclusion with false same-request inclusion.
- State actuation-event interpretation of no-command effects.

### III-P5 — Research question and non-goals

- Job: gap.
- Target: 75--95 words.
- Formal question: when does field-wise child attenuation imply parent/child physical trace and reachable-set inclusion?
- Engineering question: can a zone/conduit compiler and runtime effect engine satisfy those premises on frozen industrial cases?
- Non-goals: universal IEC compilation, compromised-context robustness, controller synthesis, enforcer speed/scalability leadership, and production deployment.
- Transition: ZoneCap is designed to discharge the syntactic and runtime obligations.

## IV. ZoneCap Design

Section job: explain a reimplementable compiler and runtime path, with each module tied to the refinement contract.

### IV-P1 — End-to-end design overview

- Job: approach.
- Target: 75--90 words.
- Walk through Fig. 1 once: source table -> normalized grants -> root capability -> delegated child -> runtime decision/effect -> physical emission -> audit/plant.
- Identify which stages enforce syntactic inclusion and which stages enforce effect soundness/realizability.
- Do not repeat the theorem.

### IV-P2 — Source-table normalization and provenance

- Job: mechanism.
- Target: 85--105 words.
- Describe directed zone/conduit grants, deterministic target-asset identifiers, and source-independent overlay.
- State rejection behavior for unsupported or malformed decision constructs.
- Require provenance fields so source-derived and overlay fields remain distinguishable.
- Link to C6 evaluation without giving results.

### IV-P3 — Capability compilation

- Job: mechanism.
- Target: 90--110 words.
- Describe positive conjunctive intersection across structural and behavioral fields.
- State compiler inputs, output capability, default-deny behavior, and normalization of intervals/windows/sequences.
- Explain why conjunction is necessary for Lemma 1.
- Use Table I rather than a long field-by-field prose list.

### IV-P4 — Delegation and attenuation validation

- Job: mechanism.
- Target: 85--105 words.
- Describe root, depth-1, and depth-2 delegation; issuer/zone binding; set/interval/window subset checks; sequence-prefix rule.
- State rejection of any widening and preservation of lineage.
- Emphasize that the validator does not call plant reachability, avoiding a tautological definition.

### IV-P5 — Five-effect decision semantics

- Job: mechanism.
- Target: 105--125 words.
- Define effect roles without results:
  - `ALLOW`: emit the authorized request;
  - `DENY`: emit no actuation event;
  - `ATTENUATE`: return a narrower capability and emit no actuation event;
  - `REWRITE`: emit an authorized, parent-realizable corrected command;
  - `DEFER`: emit only the registered parent-admissible hold while awaiting resolution.
- State timeout/fail-closed behavior.
- Introduce the runtime panel in Fig. 3.

### IV-P6 — Enforcement, audit, and revocation interface

- Job: mechanism.
- Target: 85--105 words.
- Describe final pre-emission membership check, parent-realizability obligation, audit enqueue, and resolver-local revocation state.
- Distinguish issuance from delivery at the interface level without yet reporting the counterexample.
- State that distributed freshness is not silently assumed by the local engine.
- Transition to the formal result.

## V. Physical Refinement Guarantee

Section job: state the non-tautological theorem chain compactly and keep proof premises adjacent to the claim.

### V-P1 — Why syntax alone is insufficient

- Job: gap.
- Target: 65--80 words.
- Use the parent `[0,1]`, child `[0,0.4]`, raw request `0.8` example to show failure of same-request output inclusion under rewriting.
- Motivate request abstraction and parent realizability.
- Point to Fig. 2.

### V-P2 — Obligations 1--3: syntactic side

- Job: context.
- Target: 80--95 words.
- Name exactly:
  1. syntax independent of reachability;
  2. conjunctive monotone compilation;
  3. history-language refinement on the same physical projection.
- State their role: establish authorization inclusion.

### V-P3 — Obligations 4--6: runtime and plant side

- Job: context.
- Target: 90--105 words.
- Name exactly:
  4. authority-preserving and parent-realizable effects, including hold/idle closure;
  5. common plant uncertainty, initial set, disturbance set, and horizon;
  6. reachable-set meaning as a union over admitted emissions and disturbances.
- State the excluded interpretations next to the obligations.

### V-P4 — Lemma 1: compiler refinement

- Job: result.
- Target: 75--90 words plus equation.
- State $c' \preceq c \Rightarrow \operatorname{Adm}_{c'}(\eta) \subseteq \operatorname{Adm}_c(\eta)$.
- Proof skeleton: field-wise subset, positive conjunction, and history-language inclusion.
- Explicitly state that no reachability predicate is used.

### V-P5 — Lemma 2: emission refinement

- Job: result.
- Target: 80--100 words plus equation.
- State $\overline E_{c'}(\eta) \subseteq \overline E_c(\eta)$.
- Proof skeleton: child soundness -> child authorization -> parent authorization -> parent-realizable raw request; separately cover hold and no-command effects.
- Explain in one phrase why membership alone is insufficient.

### V-P6 — Theorem 1: trace and reachable-set inclusion

- Job: result.
- Target: 100--120 words plus boxed theorem.
- State finite-horizon trace inclusion followed by reachable-set inclusion.
- Proof skeleton: induction on physical transitions, same history, same disturbance, same transition function.
- Separate theorem from exact 1D audit; the audit does not prove universality.

### V-P7 — Corollary and failure conditions

- Job: limitation.
- Target: 80--100 words.
- Give the 1D linear interval corollary and short MIMO lifting statement.
- Name the decisive failure classes: non-monotone grants/combiners, unauthorized or parent-unrealizable rewrite/hold, mismatched context/plant, and false fixed-tick interpretation.
- Transition: Evaluation tests the implementation and registered alternatives rather than re-proving the theorem statistically.

## VI. Evaluation Methodology

Section job: freeze the evidence protocol before results and distinguish exact, seeded, bounded, source-derived, and hardware evidence.

### VI-P1 — Evaluation questions and evidence classes

- Job: mechanism.
- Target: 65--80 words.
- Map three questions to C1, C6, and C7 without exposing internal IDs in final prose.
- Define exact enumeration, seeded falsification, mutation analysis, bounded exhaustive checking, and target-hardware measurement.
- Introduce Table II.

### VI-P2 — Formal and implementation checks

- Job: mechanism.
- Target: 70--85 words.
- Describe rational-arithmetic 1D grid, MIMO/history seeds, caveat mutants, premise removal/restoration, and sanity controls.
- State every registered seed is reported and no seed is selected.
- State too-good-result triggers.

### VI-P3 — Frozen compiler corpus and oracle separation

- Job: mechanism.
- Target: 85--100 words.
- Name CPwE/CIP Security matrix and ENISA landside-signalling subgraph.
- Explain complete cross-product, one mutation per registered invalid field, delegation chains, and widening attempts.
- State compiler/oracle code separation and the shared human-table limitation.
- Do not call this a statistically sampled test set.

### VI-P4 — Runtime composition and baselines

- Job: mechanism.
- Target: 80--95 words.
- Describe one-request, five-step composed, and horizon-5 exhaustive effect traces.
- State baseline fairness: identical requests; common expressible subsets; unavailable dimensions and hardware metrics marked `N/A`.
- Name OPC UA role, PLC ABAC, pinned SINT, deny-only, and source-grounded Lanotte/Roop mapping.

### VI-P5 — Conditional Jetson/OpenPLC protocol

- Job: mechanism.
- Target: 70--85 words.
- Keep only if hardware evidence is available at submission.
- State five fresh processes, fixed seeds, 100,000 measured decisions after warm-up, complete check path, 10 ms OpenPLC period, environment/thermal control, raw sample retention, and equivalence checks.
- State registered pass criteria: per-repetition p99 <= 1 ms, scan occupancy <= 10%, and zero mismatch.
- Do not include results here.

## VII. Results

Section job: climb the evidence ladder from the formal bridge to compiler realization, runtime composition, and conditional feasibility.

### VII-A. Syntactic attenuation refined request-abstracted physical reachability

#### VII-A-P1 — Proof obligations and exact audit closed together

- Job: result.
- Target: 75--90 words.
- Report: 8/8 obligations closed; 393,750 exact 1D models; 2,756,250 horizon checks; zero inclusion violations.
- Immediately state that the theorem rests on induction and the audit is a finite executable falsification check.
- Evidence: E01.

#### VII-A-P2 — Alternative explanations were actively falsified

- Job: result.
- Target: 85--105 words.
- Report: 14/14 unsafe mutants killed; all five seeds; 720 MIMO and 400 history horizon checks; 8,854 membership checks; two widening controls detected.
- Report that removing rewrite or hold premises produced the two expected counterexamples and restoration removed registered violations.
- Evidence: E02--E04, E06.

#### VII-A-P3 — Common-subset comparison and exact scope

- Job: comparison.
- Target: 70--90 words.
- Report common-subset agreement with pinned SINT and the Dodson schema adapter only at invariant resource/action/upper-bound scope.
- Preserve `N/A` for proof-only dimensions and avoid system-level superiority.
- Close with the request-abstracted/common-plant boundary.
- Evidence: E05.

### VII-B. The compiler matched the frozen source-derived corpus and rejected widening

#### VII-B-P1 — Complete corpus agreement

- Job: result.
- Target: 75--90 words.
- Report 42,120 CPwE and 16,848 ENISA cases, 58,968 total, including 54,432 mutations and zero compiler-oracle mismatch.
- Repeat `source-derived topology plus source-independent overlay` in compressed form.
- Evidence: E07.

#### VII-B-P2 — Delegation, path, mutation, and provenance checks

- Job: result.
- Target: 80--100 words.
- Report 84 delegation edges, 672 dimension checks, 32/32 widening rejections, path/depth cases, 10/10 generated-corpus mutant kills, and 4/4 provenance probes.
- Contrast six handwritten happy paths killing 0/10 mutants to justify generated mutation coverage.
- Evidence: E08, E09, E11.

#### VII-B-P3 — Fair policy baselines show expressiveness boundaries

- Job: comparison.
- Target: 85--105 words.
- Report zero mismatch only on fully expressible subsets.
- Report full-corpus unrestricted mutation counts for OPC UA roles, PLC ABAC, and pinned SINT as missing modeled dimensions, not false-allow rates.
- State that the comparison supports complementarity and coverage differences, not universal dominance.
- Evidence: E10.

### VII-C. Five runtime effects preserved the registered refinement while avoiding deny-only service loss

#### VII-C-P1 — One-request and composed traces

- Job: result.
- Target: 75--95 words.
- Report 58,968 one-request traces, 4,536 five-step composed traces, all five effects reached, zero registered safety/refinement/deadlock violations, and 5/5 mutants killed.
- Keep `registered actuation-event semantics` in the topic sentence.
- Evidence: E12.

#### VII-C-P2 — Exhaustive sequence coverage

- Job: result.
- Target: 75--95 words.
- Report 492,156 words, 492,030 transitions, all 25 bigrams and 125 trigrams, zero registered violations, and 3/3 exhaustive versus 0/3 named-path mutant kills.
- State horizon 5 and 126 scopes adjacent to the counts.
- Evidence: E14, E16.

#### VII-C-P3 — Deny-only and effect-family comparisons

- Job: comparison.
- Target: 95--115 words.
- Report 13,608 blocked registered rewrites, 16.67% of constructed steps, 60% of constructed safe-service opportunities, and 9,072 lost recoverable decisions.
- Explicitly prohibit field-prevalence interpretation.
- Map Lanotte/Roop and SINT effect coverage without claiming missing mechanisms are system failures.
- Evidence: E13, E15.

### VII-D. Prototype hardware feasibility [conditional]

Activation rule: include only after every returned exp-22--25 directory passes protocol, raw-data, environment, equivalence, and disabled-check audit. If no accepted evidence exists, remove this subsection and Table IV. If the threshold is refuted, report the result and revise the abstract/conclusion rather than selecting repetitions.

#### VII-D-P1 — Testbed and measurement validity

- Job: context.
- Target: 55--70 words.
- Identify exact Jetson Orin NX 8GB configuration, JetPack/L4T, power mode, CPU affinity, OpenPLC version/topology, 10 ms task period, and full enabled decision path.
- Report timer calibration and absence/presence of throttling without substituting exp-26 x86 data.

#### VII-D-P2 — Registered C5 decision

- Job: result.
- Target: 65--85 words.
- Report all five repetition p50/p99/max, worst-repetition p99, scan occupancy, throughput, peak RSS, and mismatch count.
- State pass or refutation against the preregistered per-repetition thresholds.
- Never report pooled p99 alone.

#### VII-D-P3 — Ablation, scaling, and baseline boundary

- Job: comparison.
- Target: 65--85 words.
- Report cold/warm, signature, revocation lookup, audit, policy-count, and delegation-depth effects.
- Report SINT or other executable baselines only under the same target and scope; retain `N/A` otherwise.
- Treat any greater-than-10x speedup as audited, not celebratory.

## VIII. Revocation Boundary and Discussion

Section job: use the negative result to interpret the guarantee and then state the broader engineering meaning and limitations.

### VIII-P1 — Local delivered-state model initially appeared safe

- Job: context.
- Target: 70--85 words.
- Report bound-5 and exact graph closure only as the local baseline: delivered-state, permission-union, deterministic-order, and bounded-deadlock checks remained clean.
- Include enough scale to show the model was not a trivial path test, but do not repeat every E17/E18 count.
- Evidence: E17, E18.

### VIII-P2 — Delayed delivery refuted issuance-relative revocation safety

- Job: result.
- Target: 80--100 words.
- Report all 15 fair schedules delivered revocation; delay 0 produced zero stale execution; delays 1 and 2 produced four each, eight total.
- State clearly that this satisfies the registered false criterion for original C4.
- Refer to Fig. 4.
- Evidence: E19.

### VIII-P3 — Freshness is an execution-interface contract

- Job: implication.
- Target: 80--100 words.
- Use the diagnostic epoch fence and pinned-SINT fresh gateway recheck to identify possible repair directions.
- State that the fence is post-hoc diagnostic evidence and is not promoted to a supported claim.
- Explain the design lesson: local resolver invariants cannot establish issuer-relative safety without delivery/freshness semantics.
- Evidence: E19, E20, E21.

### VIII-P4 — What ZoneCap changes relative to prior work

- Job: implication.
- Target: 80--100 words.
- Interpret ZoneCap as an authorization-refinement interface complementary to capability systems and runtime enforcers.
- Explain reuse: another compiler/effect engine can claim the physical refinement only after discharging the six obligations.
- Avoid stating that ZoneCap replaces controller safety, network security, or runtime-enforcement synthesis.

### VIII-P5 — Limitations and validity threats

- Job: limitation.
- Target: 105--125 words.
- Cover, in this order:
  1. shared human source-table encoding and source-independent overlay;
  2. bounded actuation-event semantics and no fixed-tick/distributed/unbounded-liveness result;
  3. trusted context and correct/common plant relation;
  4. baseline projections rather than full competing deployments;
  5. hardware status and prototype-only generality.
- If hardware evidence is absent, say so directly. If present, limit it to the exact prototype configuration.

## IX. Conclusion

Section job: contribution -> decisive evidence -> engineering implication -> boundary. One compact paragraph only.

### IX-P1 — Bounded close

- Job: implication.
- Target: 100--140 words.
- Sentence 1: restate the compiler-to-runtime-to-physical-refinement contribution.
- Sentence 2: name the decisive evidence classes, not every count.
- Sentence 3: state the reusable design principle of inspectable compilation, emission, and freshness contracts.
- Sentence 4: bound the result by trusted/common physical semantics and explicit revocation delivery.
- Add hardware feasibility only if audited evidence exists; no future-performance promise.

### Unnumbered data and code availability line

- Give the public repository/archive URL and immutable artifact identifier once available.
- State that configurations, commands, all seeds, raw metrics, and result manifests are included.
- Do not expose an author-identifying URL during double-blind review.

## 7. Section transition map

| From | Transition question answered by the next section |
|---|---|
| Introduction -> Related Work | Why do existing capabilities, enforcers, and zone/conduit tools not already supply this relation? |
| Related Work -> System Model | What exact objects and trust assumptions are needed to state the missing relation? |
| System Model -> ZoneCap Design | How does the concrete compiler and effect engine satisfy those objects? |
| ZoneCap Design -> Formal Guarantee | Which obligations turn the mechanism into a physical refinement result? |
| Formal Guarantee -> Evaluation | How were the implementation, alternatives, and bounded semantics challenged? |
| Evaluation -> Results | Which registered observations support each accepted claim? |
| Results -> Revocation/Discussion | Where does the local refinement contract fail under distributed lifecycle semantics? |
| Discussion -> Conclusion | What can an industrial system designer reuse without inheriting unsupported claims? |

## 8. Claim-evidence-placement map

| Claim/status | Formal statement location | Method location | Evidence location | Required boundary location |
|---|---|---|---|---|
| C1 accepted | III-P3/P4; V-P4--P6 | IV-P3--P5 | VII-A-P1--P3; E01--E06 | V-P1/P3/P7; VIII-P5 |
| C6 accepted, narrowed | Introduction contribution; no universal formula | IV-P2--P4 | VII-B-P1--P3; E07--E11 | VI-P3; VII-B-P1/P3; VIII-P5 |
| C7 accepted, narrowed | V-P3/P5 | IV-P5/P6 | VII-C-P1--P3; E12--E16 | IV-P5; VII-C-P2/P3; VIII-P5 |
| C4 rejected | None as a positive theorem | IV-P6 | VIII-P1--P3; E17--E21 | Abstract A7; VIII-P2/P3; Conclusion |
| C5 insufficient/conditional | None | VI-P5 | VII-D and Table IV only after audit | Activation rule; VIII-P5 |

No result number may enter prose unless it maps to an immutable result directory and an evidence tag. No accepted claim may appear in the abstract, introduction, or conclusion with broader scope than its formal/result paragraph.

## 9. Planned drafting order after outline approval

1. Build the LaTeX skeleton with section headings, labels, display placeholders, and bibliography keys only.
2. Draft Section VII Results from immutable evidence records.
3. Draft Sections III--V so definitions, mechanism, and theorem match the Results vocabulary.
4. Draft Section VI Evaluation Methodology and freeze all scope language.
5. Draft Sections I, II, VIII, and IX around the actual evidence.
6. Draft title and abstract last.
7. Render in the TII template, measure page use, and compress by the cut rules in Section 4.
8. Run a paragraph-job, terminology, claim-evidence, citation, and overclaim audit before any submission package is prepared.

## 10. Inputs still pending

- Audited exp-22--25 hardware directories from the hardware group.
- Final public artifact/repository URL suitable for double-blind review or archival release.
- Author list, affiliations, funding, and acknowledgments; these are outside the scientific outline and must remain absent from the anonymized review manuscript.
- Final TII subject-category selection and any submission-system metadata requested at submission time.
