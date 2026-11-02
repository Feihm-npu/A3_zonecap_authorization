# ZoneCap TII Figure and Table Plan

Status: manuscript-wide display contract; Figure 1 is a generated schematic (`figures/build_overview_figure.py`); Figures 2--5 are data-bearing Python figures; Figure 6 is conditional on audited target-hardware data.

Target: IEEE Transactions on Industrial Informatics, regular paper, double-column layout.

## 1. Visual argument

The display sequence must answer five reader questions in order:

1. **What crosses the digital--physical boundary?** Figure 1 shows the compiler, capability lineage, five-effect enforcement point, and plant interface.
2. **Why can narrower authority imply narrower physical behavior?** Figure 2 couples the proof chain to exact reachable-set examples instead of leaving the theorem as text only.
3. **Does the compiler implement the intended scope, and were perfect results challenged?** Table II and Figure 3 report baseline scope, complete-corpus agreement, mutation adequacy, and delegation controls.
4. **Do the runtime effects compose, and what is lost by deny-only enforcement?** Table III and Figure 4 separate effect correspondence from quantitative sequence coverage and service loss.
5. **Where does the guarantee stop?** Figure 5 gives the delayed-revocation counterexample as a result, not as a prose caveat. Figure 6 later answers feasibility on the approved target if the hardware evidence passes audit.

Internal research-management objects are excluded from the manuscript displays. In particular, an experiment audit checklist and an evidence ledger are not paper tables. Protocol details remain in prose and the artifact; evidence identifiers, run directories, and acceptance status do not appear in submitted captions or cells.

## 2. Display inventory and page budget

| Display | Manuscript role | Format | Width | Status | Cut/merge rule |
|---|---|---|---:|---|---|
| Figure 1 | System and method overview | Schematic-led composite | 183 mm | Generated | Required; simplify labels before shrinking |
| Table I | Capability schema and attenuation semantics | Definition table | 183 mm | Retain | Required; keep to eight authority rows |
| Figure 2 | Formal refinement plus reachable-set instantiation | Schematic-led composite | 183 mm | Draft generated | Required; panels b--d may move to supplement only if the theorem remains visually understandable |
| Table II | Fair policy-projection comparison | Quantitative comparison table | 183 mm | Replace old Table II | Required baseline result |
| Figure 3 | Compiler validation and test adequacy | Quantitative grid | 183 mm | Draft generated | Required; merge panels a and b if page pressure is severe |
| Table III | Runtime effect correspondence | Qualitative comparison table | 183 mm | Replace old Table III | Preferred; move to supplement before removing Figure 4 |
| Figure 4 | Runtime composition, order coverage, and deny-only loss | Quantitative grid | 183 mm | Draft generated | Required result figure |
| Figure 5 | Issuance-relative revocation counterexample | Mixed schematic + quantitative | 89 mm | Draft generated | Required negative-result figure |
| Figure 6 | Jetson/OpenPLC feasibility | Quantitative grid | 183 mm | Conditional | Omit completely unless exp-22--25 pass the frozen audit |

The base paper therefore carries five figures and three tables. Figure 5 is single-column, and Figures 3--4 are intentionally shallow. If the IEEE render exceeds ten pages, remove repeated prose first, then move Table III to supplementary material. Do not remove the revocation counterexample or replace result figures with audit tables.

## 3. Global visual language

- ZoneCap/child/result of interest: dark blue.
- Parent/reference domain: neutral grey.
- External baselines or unrepresented scope: light grey.
- Unsafe, lost, or refuted behavior: muted red.
- Rewrite/correction: teal; attenuation: violet; defer/hold: muted gold. These effect colors must remain fixed between Figures 1 and 4.
- Use color plus position, outline, or labels; no conclusion may depend on red--green discrimination.
- White background, no decorative boxes around quantitative panels, no grid unless required to read a threshold.
- Figure text: 6--8 pt at final size; lowercase bold panel labels; editable SVG/PDF text.
- All figures export as SVG, PDF, EPS, TIFF, and PNG. The manuscript builds with pdflatex and embeds the PDF files; EPS is kept for a latex/dvips route, but that route turns the repeated DejaVuSans definitions into Type 3 fonts.
- Every quantitative panel has a panel-level source-data CSV. No observations are sampled or removed for presentation.

## 4. Figure contracts

### Figure 1 — ZoneCap compilation and enforcement path

**Core conclusion:** ZoneCap turns directed zone/conduit policy into attenuable runtime authority and exposes three explicit interfaces that must hold before physical refinement follows.

**Archetype:** schematic-led composite.

**Final size:** 183 mm × approximately 55 mm.

**Panel map:** one left-to-right panel with three visual bands.

- Policy band: source-derived zone/conduit topology and the declared physical/context overlay use visibly different fills.
- Capability band: root issuance, child attenuation, lineage, and the eight checked authority dimensions.
- Runtime/plant band: five effects feed three physical outcomes—authorized emission, registered hold, or no actuation event—before the common plant relation.

**Interface labels:** positive conjunctive compilation; sound and parent-realizable emission; common history/plant/uncertainty.

**Evidence hierarchy:** conceptual mechanism only. It must not contain evaluation counts or imply that source documents define overlay fields.

**Reviewer risk:** a reviewer may interpret the diagram as a full IEC 62443 toolchain or as fixed-tick PLC semantics. The artwork and caption must state “source-derived topology plus declared overlay” and “actuation-event semantics.”

### Figure 2 — From attenuated authority to physical reachability

**Core conclusion:** Under the named interface obligations, field-wise attenuation induces physical trace and reachable-set inclusion; exact representative plants instantiate the relation for positive, signed, and negative input dynamics.

**Archetype:** schematic-led composite.

**Final size:** 183 mm × approximately 78 mm.

**Panel map:** 

- **a:** the four-level chain from `c' <= c` to authorization/emission inclusion, trace inclusion, and reachable-set inclusion.
- **b:** parent and child exact reachable intervals through horizon six for the positive-input integrator.
- **c:** the same for the signed coupled response.
- **d:** the same for the stable negative-input plant.

**Evidence hierarchy:** panel a carries the theorem logic; panels b--d are representative executable instantiations. Parent intervals are grey and child intervals blue. The child band must be visibly contained at every horizon.

**Source data:** exact common-subset reachability records; all three registered plants and all horizons 0--6 are included. The plotted adapter is ZoneCap because all three adapters produced identical intervals on the common scope.

**Statistics:** seedless exact rational arithmetic; no sampling interval or error bar applies. The caption must not imply that the three examples prove the theorem.

**Reviewer risk:** representative curves can be mistaken for the universal result. The caption must say that the theorem supplies the conditional general result, whereas panels b--d are executable checks.

### Figure 3 — Compiler agreement survived adequacy and delegation controls

**Core conclusion:** Complete-corpus compiler/oracle agreement is not explained by a small happy-path fixture or a disabled attenuation checker.

**Archetype:** quantitative grid.

**Final size:** 183 mm × approximately 65 mm.

**Panel map:**

- **a:** case counts for the two frozen source structures, annotated with zero compiler/oracle mismatch.
- **b:** complete-corpus composition: 4,536 valid cases and 54,432 single-field mutations.
- **c:** four registered controls: generated-corpus mutant kills, six-happy-path mutant kills, legal delegation checks, and localized widening rejections. Each bar prints numerator and denominator.

**Evidence hierarchy:** panel c is the hero evidence because it challenges the perfect agreement; panels a and b define evaluation scale and composition.

**Source data:** exp-07 complete corpus, exp-08 source-generation ablation, and exp-09 path/delegation/widening study. All records are seedless exact checks.

**Statistics:** no inferential statistics. Denominators and exact counts appear in panel labels and caption.

**Reviewer risk:** “0/10 happy-path mutant kills” is an intentionally weak-fixture control, not a failure of the proposed generated corpus. The caption must make this direction explicit. Zero mismatches must remain bounded to the frozen source interpretation.

### Figure 4 — Runtime effects compose and preserve service unavailable to deny-only enforcement

**Core conclusion:** The five-effect semantics covers interaction orders missed by named traces while retaining authorized corrections and holds that a deny-only policy removes.

**Archetype:** quantitative grid.

**Final size:** 183 mm × approximately 69 mm.

**Panel map:**

- **a:** observed counts of `ALLOW`, `DENY`, `ATTENUATE`, `REWRITE`, and `DEFER` over all 81,648 registered policy steps.
- **b:** effect 1-, 2-, and 3-gram coverage for one named path per scope versus exhaustive enumeration through horizon five. The caption also reports 0/3 versus 3/3 sequence-mutant kills.
- **c:** partition of the 27,216 rich-effect physical outputs into 9,072 outputs retained by deny-only, 13,608 lost rewrites, and 4,536 lost defer holds. The caption separately reports 9,072 removed attenuation/defer recovery decisions.

**Evidence hierarchy:** panel b establishes composition coverage; panel c establishes engineering value beyond fail-closed safety; panel a prevents the reader from treating the corpus as effect-balanced.

**Source data:** exp-12 runtime automaton, exp-13 deny-only ablation, and exp-14 exhaustive-sequence study. No sequence or effect category is omitted.

**Statistics:** seedless exhaustive counts; no error bars. “60%” is a rate over the constructed safe-service opportunities, not field prevalence.

**Reviewer risk:** counts from overlapping concepts must not be stacked together. Physical-output loss and recovery-decision loss remain separately worded. “Exhaustive” always includes the horizon-five and five-symbol alphabet boundary.

### Figure 5 — Delayed delivery refutes issuance-relative revocation safety

**Core conclusion:** Resolver-local post-delivery safety does not prevent stale execution between authority-side revocation issuance and resolver delivery.

**Archetype:** asymmetric mixed-modality figure.

**Final size:** 89 mm × approximately 85 mm.

**Panel map:**

- **a:** exact stale-execution counts at delivery delays 0, 1, and 2; each condition contains five fixed fair schedules. The post-hoc epoch-fence replay is hatched and explicitly labeled diagnostic.
- **b:** event timeline identifying the issuance-relative stale window and the narrower clean post-delivery boundary.

**Evidence hierarchy:** the 0/4/4 registered-semantics bars are the negative result. The epoch fence is a design clue, not confirmatory evidence for ZoneCap.

**Source data:** exp-19 adversarial scheduler. All 15 schedules are retained; all deliver revocation and satisfy the registered fairness condition.

**Statistics:** fixed exact schedules, `n = 5` per delay, no seed selection and no error bars.

**Reviewer risk:** the figure must not imply unfair scheduling or permanent non-delivery. It must also keep the post-hoc fence visually distinct from the registered system.

### Figure 6 — Conditional target-hardware feasibility

**Core conclusion:** On the approved Jetson/OpenPLC path, every registered repetition must satisfy the 1 ms p99 decision-latency and 10% scan-occupancy thresholds while preserving exact decisions.

**Archetype:** quantitative grid.

**Activation gate:** only after exp-22--25 return with raw samples, environment manifests, enabled-check evidence, and all five repetitions, and after the research audit and S3 review. A refuted threshold is still reported. The display does not exist in the manuscript while `\zonecaphardwarefalse` is set.

**Insertion kit (built 2026-11-02, switched off):**

- `sections/07d_hardware.tex` contains Section VII-D, Table IV, and this figure.
- Conditional passages live in the evaluation, abstract, discussion, and conclusion sections.
- Each conditional passage has five preregistered outcome wordings, selected by `\cfiveoutcomecase`:

  | Case | Outcome |
  |---|---|
  | 0 | supported |
  | 1 | warm cache only |
  | 2 | policy-count limited |
  | 3 | both limitations |
  | 4 | refuted |

- `figures/build_c5_results.py --exp22 ... --exp25 ... --testbed figures/c5_testbed.json` audits the returned directories, then writes three outputs:
  - `generated/c5_numbers.tex`, holding every quoted number, the Table IV rows, and the case;
  - this figure;
  - the panel source data.

  The audit covers manifest hashes, the confirmatory role, preflight, frozen hashes, the corpus fingerprint, and raw-sample recomputation. Development directories are refused, except with `--preview`, which writes watermarked output outside the manuscript.
- A preview build with development data ran at ten pages, and all five cases compiled with no missing number.
- Because the figure floats before the revocation figure, it is numbered Fig. 5 when active. Labels keep every reference correct.

**Final size:** 183 mm × approximately 85--95 mm.

**Planned panel map:**

- **a:** per-repetition p99 decision latency with a horizontal 1,000 microsecond threshold; show all five fixed order seeds.
- **b:** upper-tail empirical CDF or complementary CDF from all raw latency samples, with p95/p99/p99.9 markers; do not substitute a smoothed distribution.
- **c:** exp-24 p99 heatmap over policy counts 1/10/100/1000 and delegation depths 0/1/2, retaining every cell.
- **d:** common-subset same-target comparison of p99 latency and throughput for available executable baselines; unsupported/unavailable systems remain N/A.

**Statistics:** nearest-rank percentiles, five fresh-process repetitions, per-repetition points plus pooled descriptive values. The C5 decision is based on every repetition, not the pooled curve.

**Reviewer risk:** client/network/OpenPLC latency must not be mixed with server-side decision latency; diagnostic configurations with disabled checks must not be displayed as deployable variants; a missing executable baseline remains N/A.

## 5. Table contracts

### Table I — Capability fields and attenuation rules

**Purpose:** compact method definition.

**Rows:** the eight authority dimensions. **Columns:** field, meaning, provenance, child rule/runtime check.

**Keep:** the source-derived versus source-independent-overlay distinction.

**Remove:** evidence status, experiment identifiers, and validation counts.

### Table II — Policy-projection scope and full-corpus outcome

**Purpose:** fair quantitative baseline comparison.

**Rows:** ZoneCap, OPC UA role projection, PLC ABAC projection, pinned SINT profile.

**Columns:** exactly represented mutation categories (of 12), fair-subset cases, fair-subset agreement, and cases unrestricted because the projection did not represent the mutated dimension.

**Required values:**

| System/profile | Exact categories | Fair-subset cases | Agreement on fair subset | Unrestricted outside represented scope |
|---|---:|---:|---:|---:|
| ZoneCap | 12/12 | 58,968 | 100% | 0 |
| OPC UA role projection | 3/12 | 18,144 | 100% | 40,824 |
| PLC ABAC projection | 8/12 | 40,824 | 100% | 18,144 |
| Pinned SINT profile | 5/12 | 27,216 | 100% | 28,728 |

The last column is not labeled “false allow” in the manuscript because the baseline projections did not claim to represent those dimensions. The caption must say that these are projection-scope outcomes, not deployed-product error rates.

### Table III — Runtime effect correspondence

**Purpose:** compare operational roles without manufacturing unavailable runtime numbers.

**Rows:** ZoneCap, Lanotte/Roop edit-automata family, pinned SINT profile.

**Columns:** allow, deny, live attenuation, runtime rewrite, and approval defer/hold.

**Cell vocabulary:** Exact = same request-time role; Partial = related behavior at another lifecycle stage or without the registered physical contract; dash = no source-grounded analogue located.

This table is qualitative by design. Quantitative effect counts and service loss belong in Figure 4. Hardware latency never appears here.

## 6. Caption and cross-reference rules

- Figure captions follow: finding-oriented noun phrase, panel-by-panel description, exact `n`/denominator and scope, then the critical interpretation boundary.
- Do not put result numbers in the short title phrase; put them in panel descriptions.
- Exact/exhaustive experiments state that no inferential statistics or error bars apply.
- Seeded or repeated experiments show every seed/repetition. No mean-only bars are permitted.
- Main text introduces the question before the display and states the inference after it; it does not narrate every plotted value.
- Zero-violation counts remain in prose/captions rather than being drawn as empty bar charts.
- Internal claim/evidence identifiers and file paths never appear in submitted captions.

## 7. Current QA status

- Figures 2--5 read their values from frozen experiment outputs and emit panel-level source-data tables.
- The plotting source passes the publication preflight with no warning or failure.
- SVG and PDF preserve editable text; the pdflatex build has no Type 3 fonts and embeds every font; TIFF is 600 dpi with lossless compression.
- Visual QA checked title/panel-label separation, the narrow valid-case segment, zero-value revocation bars, and timeline label collisions.
- With all five base figures and three tables inserted, the IEEE render is nine pages. Remaining display work is conditional Figure 6 activation after the target-hardware audit; its insertion kit is built and switched off, and a preview with development data renders at ten pages.
