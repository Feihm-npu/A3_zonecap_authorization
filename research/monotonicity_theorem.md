# Capability Attenuation and Physical Reachability

Status: **S2 exp-01 closed conditional proof and exact 1D audit.** The concrete
hold/idle bindings remain registered work for exp-04 and exp-12.

## 1. Plant, token syntax, and the observable history

Let a discrete-time plant be a transition system

\[
\mathcal{P}=(X,U,W,F), \qquad x_{t+1}=F(x_t,u_t,w_t),
\]

with initial set \(X_0\subseteq X\) and a fixed disturbance set \(W\). Let
\(\eta_t\) be the authorization-relevant **physical projection** of a history:
observed plant states, emitted action labels and values, trusted mode, and time.
It excludes token-internal decisions and raw requests that emitted no physical
action. Parent and child use the same \(\eta_t\). This distinction is necessary:
request-synchronous behavior is not the object claimed by C1.

A ZoneCap token \(c\) contains positive conjunctive caveats over

\[
(Z_s,Z_d,K,A,O,I_u,I_t,M,L),
\]

where \(K\) is a conduit set, \(A\) an asset set, \(O\) an operation set,
\(I_u\) a parameter set, \(I_t\) a time window, \(M\) an operating-mode set,
and \(L\) a language of admissible physical event histories. Compilation gives
an authorization relation

\[
\operatorname{Adm}_c(\eta)\subseteq U.
\]

The notation suppresses the structural fields of an action tuple; \(U\) may be
read as conduit × asset × operation × parameter. The implementation represents
\(L\) with an ordered required-event sequence and accepts a history when that
sequence is a subsequence of the emitted-event history.

Syntactic attenuation \(c'\preceq c\) preserves issuer and zone binding and
requires

\[
K'\subseteq K,\;A'\subseteq A,\;O'\subseteq O,\;I'_u\subseteq I_u,\;
I'_t\subseteq I_t,\;M'\subseteq M,\;L'\subseteq L.
\]

A delegated subject may differ from its parent: the theorem compares physical
authority, not principal identity. Sequence extension is a sufficient syntactic
rule for \(L'\subseteq L\): if the parent's required sequence is a prefix of the
child's, every history satisfying the child sequence also satisfies the parent.
This definition contains no plant dynamics or reachable-set predicate.

## 2. Runtime emissions and the exact claim boundary

For raw request \(q\), let
\(\operatorname{Emit}_c(\eta,q)\subseteq U\) be the physical input emitted by
the runtime effect. The request-abstracted emission relation is

\[
\overline E_c(\eta)=\bigcup_{q\in Q}\operatorname{Emit}_c(\eta,q).
\]

This union is the operational action relation used by physical reachability. It
does **not** assert
\(\operatorname{Emit}_{c'}(\eta,q)\subseteq
\operatorname{Emit}_c(\eta,q)\) for the same raw request. For example, with a
parent interval \([0,1]\), child interval \([0,0.4]\), and request \(0.8\), the
parent may `ALLOW` \(0.8\) while the child `REWRITE`s it to \(0.4\). The stronger
same-request statement is false, although \(0.4\) remains an action that the
parent can emit from an authorized identity request.

An authority-preserving effect interface has two parts:

1. **Sound emission:** `ALLOW` emits the authorized request; `REWRITE` emits
   only an action in \(\operatorname{Adm}_c(\eta)\); `DENY` and `ATTENUATE` emit
   no command; `DEFER` emits only a registered hold action.
2. **Parent realizability:** every child-emitted authorized action can be issued
   as an identity request under the parent, and every child hold/idle action is
   available in the parent semantics at the related physical history.

The second clause prevents a merely sound but arbitrarily restrictive parent
enforcer (for example, one that always rewrites to a single value) from breaking
trace inclusion. For an actuation-event horizon, no-command effects create no
plant step. For a fixed-tick horizon, the plant interface must map no command to
a common idle input; that idle input is covered by parent realizability.

## 3. Proof obligations

The result needs all of the following. Omitting an item is a candidate
counterexample, not an implementation detail.

1. **Syntax independent of reachability.** Attenuation is the registered
   field-wise order above, not a definition in terms of \(\overline E\) or
   reachable sets.
2. **Conjunctive monotone compilation.** Each positive caveat intersects the
   authorization relation. Default grants, negated exceptions, or non-monotone
   conflict combiners are excluded unless separately proved monotone.
3. **History-language refinement.** The child's accepted physical histories
   are a subset of the parent's. Parent and child evaluate the same physical
   projection \(\eta\).
4. **Authority-preserving and realizable effects.** Runtime effects satisfy
   both clauses in Section 2, including hold/idle closure.
5. **Common plant uncertainty.** Parent and child use identical \(F\),
   \(X_0\), disturbance sets, and horizon.
6. **Reachable-set meaning.** Reachability is the union over all emitted
   physical-action and disturbance sequences admitted by the semantics. It is
   not a same-request noninterference claim, a selected controller trajectory,
   or a statement about probability distributions.

## 4. Syntactic compiler-to-emission refinement

**Lemma 1 (compiler refinement).** Under obligations 1–3,

\[
c'\preceq c \Longrightarrow
\forall\eta:\operatorname{Adm}_{c'}(\eta)
\subseteq\operatorname{Adm}_c(\eta).
\]

**Proof.** Zone binding is unchanged. Every other primitive child domain is a
subset of its parent domain. Membership in the child conjunction therefore
implies membership in every corresponding parent caveat. Sequence extension
implies history-language inclusion: matching the longer child sequence as a
subsequence also matches its parent prefix. No semantic reachability premise is
used. ∎

**Lemma 2 (emission refinement).** Under Lemma 1 and obligation 4,

\[
\forall\eta:\overline E_{c'}(\eta)
\subseteq\overline E_c(\eta).
\]

**Proof.** Take any child-emitted action. Sound emission places an ordinary
output in \(\operatorname{Adm}_{c'}(\eta)\), hence in
\(\operatorname{Adm}_c(\eta)\) by Lemma 1; parent realizability supplies a raw
parent request that emits it. A hold/idle output is directly covered by the
common baseline-action clause. Effects with no plant step contribute no action
to the relation. ∎

The semantic-subset baseline assumes Lemma 2 as its definition of attenuation
and makes the remaining proof immediate. ZoneCap instead discharges Lemma 2
from token syntax, conjunction, history refinement, and the effect contract;
this is the non-tautological bridge tested by exp-01 and mutated by exp-02.

## 5. Trace and reachable-set theorem

Define \(\mathrm{Tr}_H(c)\) as all physical traces of length at most \(H\)
starting from \(X_0\), with disturbances in \(W\) and controls in
\(\overline E_c(\eta_t)\). Define

\[
\mathrm{Reach}_t(c)=\{x_t\mid
(x_0,u_0,w_0,\ldots,x_t)\in\mathrm{Tr}_H(c)\}.
\]

**Theorem 1 (attenuation monotonicity).** Under obligations 1–6, for every
finite \(H\),

\[
c'\preceq c \Longrightarrow
\mathrm{Tr}_H(c')\subseteq\mathrm{Tr}_H(c)
\Longrightarrow
\forall t\leq H:\mathrm{Reach}_t(c')
\subseteq\mathrm{Reach}_t(c).
\]

**Proof.** Induct on the number of physical transitions. The length-zero trace
and every \(x_0\in X_0\) are common. Assume a child trace through physical
history \(\eta_t\) is also a parent trace. Lemma 2 places its next emitted input
\(u_t\) in the parent relation at the same physical history. Choose the same
\(w_t\in W\). The common transition function produces the same successor
\(F(x_t,u_t,w_t)\), so the extended child trace is a parent trace. Projection
onto \(x_t\) gives reachable-set inclusion. ∎

## 6. Exact one-dimensional linear corollary

For

\[
x_{t+1}=a x_t+b u_t+w_t,
\]

with interval sets \(R_t\), \(U_c\), and \(W\), and no additional
state-dependent restriction inside the interval, exact interval propagation is

\[
R_{t+1}(c)=aR_t(c)\oplus bU_c\oplus W.
\]

If \(U_{c'}\subseteq U_c\), multiplication by any signed scalar preserves set
inclusion: \(bU_{c'}\subseteq bU_c\). The induction hypothesis gives
\(aR_t(c')\subseteq aR_t(c)\), also for negative or zero \(a\). Minkowski
addition is monotone in both operands, so
\(R_{t+1}(c')\subseteq R_{t+1}(c)\). The common base set closes induction for
all finite horizons.

The exp-01 executable audit uses rational arithmetic, not floating-point
tolerance, over the full registered coefficient/interval grid. That exhaustive
finite audit is a falsification and implementation check; the algebraic argument
above carries the universal result.

## 7. Scope of the general lifting

For \(x_{t+1}=Ax_t+Bu_t+w_t\), linear images and Minkowski sums preserve
inclusion for arbitrary sets, so the same corollary lifts to MIMO systems. For
nonlinear or state/history-dependent systems, Theorem 1 applies directly when
Lemma 2 holds at every related physical history; a convex interval/polytope
approximation is not itself a proof of exact trace inclusion. Exp-03 tests that
lifting, while exp-04 and exp-12 bind and falsify the concrete rewrite,
defer/hold, and no-command semantics.

## 8. Registered failure cases

- A child token activates a default/fallback grant that its parent cannot.
- A conflict combiner turns restrictions into a permission union.
- `REWRITE` emits outside the effective token, or the parent cannot realize the
  child rewrite output.
- `DEFER`, `DENY`, or `ATTENUATE` advances a tick with a child-only hold/idle
  input, or no-command is incorrectly treated as a frozen physical plant.
- Parent and child use different context projections, plant models, initial
  sets, disturbance sets, or horizons.
- The reported object is a same-request output relation, a selected controller
  trajectory, or an over-approximation without an inclusion-preserving
  simulation argument.

Any such behavior outside an explicitly narrowed theorem statement refutes C1
or C3. The exp-01 record is
`results/exp01_exact_1d_20260831/`; later experiments must not erase its retained
same-request counterexample.
