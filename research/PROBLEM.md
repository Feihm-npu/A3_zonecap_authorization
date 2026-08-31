# Problem

## Problem

Cross-zone industrial commands are increasingly issued not only by human operators but also by software and LFM-based agents. IEC 62443-3-2 requires an IACS to be partitioned into zones and conduits and assigns risk/security requirements at those boundaries, but it does not define a delegatable authorization object whose scope includes the physical effect of an actuation. OPC UA provides role/permission enforcement, while CPS runtime enforcers can suppress or edit unsafe events; neither interface by itself states what physical behavior a delegated authority may induce.

The research question is: **Can an IEC 62443 zone/conduit policy be compiled into an attenuable capability such that every valid attenuation provably reduces, or at least preserves, the set of physically reachable states—even when runtime enforcement may attenuate, rewrite, or defer a request?**

## Gap

Existing CPS capability systems, physics-aware access-control systems, and runtime enforcers achieve fine-grained delegation, physics-derived policy checks, or correction of unsafe traces, but fail to connect all three with a standards-grounded compiler and a syntactic-to-physical refinement theorem. This is because token attenuation is normally defined over digital scope, while physical reachability and edit effects remain outside the authorization semantics. We hypothesize that compiling zone, conduit, asset, action, parameter, time, operating mode, and pre-action sequence as conjunctive caveats—and constraining runtime edits to preserve the effective authority—makes syntactic attenuation imply physical trace and reachable-set inclusion.

This is a deliberately narrower gap than the one stated in the initial README. We must not claim “the first physics-aware access control” or “the first capability authorization for physical agents.” Both claims are contradicted by prior and concurrent work.

## Closest prior work

| Work | What it does | Delta from us |
|---|---|---|
| [Dodson, *Capability-based access control for cyber physical systems* (Cambridge TR-963, 2021)](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-963.pdf) and [CHERI Macaroons (EuroS&PW 2020)](https://doi.org/10.1109/EuroSPW51379.2020.00099) | Constructs, delegates, and enforces Macaroon/CHERI capabilities representing physical resources in robotics and ICS, including a Modbus demonstrator. | Already occupies “capabilities for CPS.” It does not compile IEC 62443 zones/conduits or relate attenuation to physical reachable sets and edit semantics. |
| [Etigowni et al., *CPAC: Securing Critical Infrastructure with Cyber-Physical Access Control* (ACSAC 2016)](https://doi.org/10.1145/2991079.2991126) | Uses a power-grid physical model and information-flow analysis to generate and enforce physics-aware access-control policies. | Already occupies “physics-aware access control.” It is centralized and grid-specific, without attenuable delegation or a reachability-refinement contract for runtime edits. |
| [Pearce et al., Smart I/O (TII 2020)](https://doi.org/10.1109/TII.2019.2945520), [Lanotte et al., ICS runtime enforcement (TOPS 2023)](https://doi.org/10.1145/3546579), and [Baird et al., scalable enforcement (IEEE Access 2024)](https://doi.org/10.1109/ACCESS.2024.3357714) | Formalizes and implements bidirectional/edit-automata enforcement, correction, and scalable composition for CPS/PLCs. | This line owns enforcer mechanism and scalability. ZoneCap treats authorization scope and delegation as primary, then proves which edits preserve that authority; it does not claim a faster or more scalable enforcer. |
| [Ranathunga et al., *When Agents Control Robots: A Zero Trust Policy Model for Agentic CPS* (arXiv:2605.25653, 2026)](https://arxiv.org/abs/2605.25653) | Introduces physical objects, live-context Physical Impact Tiers, parameter limits, sequence checks, narrowing delegation, and `PERMIT`/`DENY`/`DEFER` for LFM-controlled robots. | Direct overlap with physical-context policy and defer semantics. It has no cryptographic/standards compiler implementation or proof that delegated scope and edits refine physical behavior. |
| [SINT Protocol v0.2 (2026)](https://github.com/sint-ai/sint-protocol/blob/main/WHITEPAPER.md) | Implements Ed25519 capability tokens, attenuation-only delegation, physical constraints, revocation, approval tiers, dangerous-sequence checks, and industrial/robotics bridges. | Direct engineering competitor; “capabilities + physics + agents” is not novel. SINT cites IEC 62443 alignment but does not compile a zone/conduit risk model or prove reachable-set monotonicity. ZoneCap must beat it on formal assurance and standards traceability, not breadth. |

## Why the gap is real

- **Delta explicit:** no located work provides the combination of (i) IEC 62443 zone/conduit-to-capability compilation, (ii) a proof from syntactic caveat refinement to physical trace/reachable-set inclusion, and (iii) authority-preserving semantics for `ALLOW`, `DENY`, `ATTENUATE`, `REWRITE`, and `DEFER`.
- **Who cares:** IEC 62443 risk engineers need machine-enforceable policy artifacts; OT operators need revocable, bounded delegation across maintenance and control boundaries; agent developers need a physical authorization boundary independent of model behavior.
- **Not a trivial combination:** adding Macaroon caveats to an enforcer is insufficient. Non-conjunctive policy combination, context-dependent fallback, rewriting outside the effective token, or deferral without an admissible hold transition can invalidate physical trace inclusion. The compiler must discharge these proof obligations.
- **Kill criterion:** if C1 reduces to defining attenuation semantically as reachable-set inclusion, or if the syntactic compiler cannot establish transition inclusion without unrealistic assumptions, the contribution collapses to domain adaptation. If SINT or another work publishes the same compiler/theorem before submission, the gap also disappears.

## Canonical terminology and scope

- **Capability attenuation:** a child token may restrict but never widen the parent token's zone, conduit, asset, action, parameter, time, mode, or pre-action-sequence scope.
- **Capability-induced reachable set:** the union of states reachable under all physical actions emitted by the authorization/enforcement semantics, not the single trajectory of a fixed controller and not a probability distribution.
- **ZoneCap contribution boundary:** policy semantics, compiler, and proof obligations. Enforcer hardware scalability is out of scope; cryptographic token realization beyond a reference signature/token format belongs to the adjacent A4 direction.
- **Forbidden claims:** first physics-aware access control; first capability authorization for CPS/physical agents; IEC 62443 conformance based only on the development fixtures; safety under compromised sensors or an untrusted state estimator.
