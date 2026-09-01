# C3 Baseline Effect and Property Mapping

Status: S2 exp-15 protocol and source audit, fixed before execution.

## Comparison rule

The comparison separates three notions that must not be collapsed:

1. **exact effect mechanism**: the baseline has a request-time mechanism with
   the same operational role;
2. **partial analogue**: the baseline has related behavior at another lifecycle
   stage or without ZoneCap's registered physical contract;
3. **absent/N/A**: no source-grounded analogue was located.

The 81,648 exp-12 policy-step outcomes are projected through this fixed mapping
to report workload-weighted exact, partial, and absent coverage. This is a
source-grounded semantic projection, not a fabricated execution of the
Lanotte/Roop hardware artifact or a claim that SINT accepts all ZoneCap fields.

## Lanotte/Roop runtime-enforcement family

Primary effect evidence is Lanotte, Merro, and Munteanu, *Industrial Control
Systems Security via Runtime Enforcement*, TOPS 26(1), Article 4, DOI
`10.1145/3546579`; the author preprint is arXiv `2105.10668`. Its synthesized
edit automata pass correct actions, suppress incorrect actions, correct outputs,
and emit actions autonomously when a controller fails to provide a correct one.
The paper proves transparency/soundness and deadlock-/divergence-freedom for the
monitored-controller semantics.

Baird et al., *Scalable Security Enforcement for Cyber Physical Systems*, IEEE
Access 12, 14385-14410, DOI `10.1109/ACCESS.2024.3357714`, supports the family
boundary for bidirectional parallel hardware composition. It is not used to
infer capability attenuation, approval deferral, or ZoneCap's physical
authorization theorem.

Accordingly, `ALLOW`, `DENY`, and the edit mechanism of `REWRITE` are exact
mechanism matches. `ATTENUATE` and `DEFER` are absent: timed edit-automaton
suppression/autonomous output is not relabeled as capability derivation or a
pending approval with a parent-admissible stutter. The papers' formal soundness
and deadlock-freedom are credited in their own specification-compliance threat
model; output-within-effective-capability and syntactic-attenuation-to-physical-
reachability refinement are not attributed.

The full published Lanotte hardware case study requires Simulink/MATLAB,
ModelSim/FPGA tooling, connected FPGAs, OpenPLC, and Raspberry Pi targets. That
matching environment is unavailable and non-default, so runtime numbers remain
`N/A` rather than a partial reproduction.

## Pinned SINT v0.2

SINT is fixed at commit
`2461a911b8c3d7ed9da3f7662b33678f688eb826`. The whitepaper records
`allow`, `deny`, or `escalate` decisions, T0-T3 approval tiers, attenuation-only
delegation, and physical constraints. The pinned delegator takes restrictive
action subsets and minima for numeric physical maxima; the pinned validator
returns `CONSTRAINT_VIOLATION` for exceeded force/velocity rather than editing
the outgoing command. Exp-05 already executed the pinned token delegation and
retains its exact source hashes.

Thus `ALLOW` and `DENY` are exact. `ATTENUATE` is partial because SINT performs
it while creating a delegated token, not as a live request effect. `DEFER` is
partial because `escalate`/approval withholds execution, but no pinned source
establishes ZoneCap's registered hold/stutter and parent-realizability contract.
`REWRITE` is absent: delegation-time numeric normalization is not a runtime
command edit. Physical constraint enforcement and syntactic attenuation are
credited; a physical reachable-set refinement theorem, the five-effect
composition proof, and an IEC 62443 zone/conduit compiler are not.

## Primary source anchors

- Lanotte/Merro/Munteanu author preprint:
  `https://arxiv.org/abs/2105.10668` (abstract and full paper); published DOI
  `https://doi.org/10.1145/3546579`.
- Baird et al. published DOI:
  `https://doi.org/10.1109/ACCESS.2024.3357714`.
- SINT pinned whitepaper and code:
  `https://github.com/sint-ai/sint-protocol/tree/2461a911b8c3d7ed9da3f7662b33678f688eb826`.

The academic-search MCP was unavailable in this session. Following the
registered fallback, bibliographic identity was checked against DOI/arXiv/DBLP,
effect claims against the author preprint, and SINT behavior against raw files
at the pinned commit. The accessible ResearchGate copy of Baird et al. was used
only as a T3 full-text fallback for the already DOI-verified composition scope.
