# Capability Attenuation and Physical Reachability

Status: **S1 proof skeleton and executable sanity check, not confirmatory evidence.**

## 1. Objects

Let a discrete-time plant be a transition system

\[
\mathcal{P}=(X,U,W,F), \qquad x_{t+1}=F(x_t,u_t,w_t),
\]

with initial set \(X_0\subseteq X\) and a fixed disturbance set \(W\). A history \(h_t\) contains the observed states, issued requests, enforcement effects, and emitted physical actions through time \(t\).

A ZoneCap token \(c\) contains conjunctive caveats over

\[
(Z_s,Z_d,K,A,O,I_u,I_t,M,L),
\]

where \(K\) is a conduit set, \(A\) an asset set, \(O\) an action set, \(I_u\) a parameter set, \(I_t\) a time window, \(M\) an operating-mode set, and \(L\) a pre-action history language. The compiler and runtime semantics induce a set \(E_c(h_t)\subseteq U\) of physical actions that may be emitted at history \(h_t\).

Syntactic attenuation \(c'\preceq c\) requires unchanged zone binding and issuer, with

\[
K'\subseteq K,\;A'\subseteq A,\;O'\subseteq O,\;I'_u\subseteq I_u,\;
I'_t\subseteq I_t,\;M'\subseteq M,\;L'\subseteq L.
\]

The prototype represents \(L'\subseteq L\) by extending an ordered required-event sequence and interpreting sequence satisfaction as subsequence membership.

## 2. Proof obligations

The theorem needs all of the following; omitting any item is a candidate counterexample, not an implementation detail.

1. **Conjunctive monotone compilation.** Adding a caveat intersects the enabled request/action set. Default grants, negated exceptions, or non-monotone policy-combining algorithms are excluded unless separately proved monotone.
2. **Common trusted context.** Parent and child decisions use the same plant/context observation. Security under a compromised sensor or state estimator is outside A3.
3. **Authority-preserving effects.** `ALLOW` emits the requested authorized action; `DENY` emits none; `ATTENUATE` emits none and returns a child token; `REWRITE` emits only an action in the effective token; `DEFER` emits a designated hold/stutter transition that is also available under the parent semantics.
4. **Common plant uncertainty.** Parent and child use identical \(F\), \(X_0\), disturbance sets, and horizon.
5. **Reachable-set meaning.** Reachability is the union over all action/disturbance sequences admitted by the semantics. It is not a claim about a particular controller's selected trajectory or its probability distribution.

## 3. Compiler refinement lemma

**Lemma 1.** Under obligations 1–3, \(c'\preceq c\) implies

\[
\forall h:\;E_{c'}(h)\subseteq E_c(h).
\]

**Argument.** Every primitive child domain is a subset of its parent domain. Conjunctive compilation takes their intersection, which preserves subset order. `DENY` and `ATTENUATE` add no physical output. The output obligation on `REWRITE` and the shared stutter obligation on `DEFER` ensure that these effects do not add a child-only output. Therefore every child-emitted physical action is parent-admissible at the same history.

This lemma is the non-trivial bridge: defining attenuation directly as \(E_{c'}\subseteq E_c\) would make the result tautological and would not support C1.

## 4. Trace and reachability theorem

Define \(\mathrm{Tr}_H(c)\) as all length-at-most-\(H\) physical traces starting from \(X_0\), using disturbances in \(W\) and actions in \(E_c(h)\). Define

\[
\mathrm{Reach}_t(c)=\{x_t\mid (x_0,\ldots,x_t)\in\mathrm{Tr}_H(c)\}.
\]

**Theorem 1 (attenuation monotonicity).** Under obligations 1–5, for every finite \(H\),

\[
c'\preceq c \Longrightarrow
\mathrm{Tr}_H(c')\subseteq\mathrm{Tr}_H(c)
\Longrightarrow
\forall t\leq H:\mathrm{Reach}_t(c')\subseteq\mathrm{Reach}_t(c).
\]

**Proof.** Induct on trace length. The empty trace and every \(x_0\in X_0\) are common. Assume a child trace through history \(h_t\) is also a parent trace. By Lemma 1, its next child-emitted action \(u_t\) is in \(E_c(h_t)\). The same disturbance \(w_t\in W\) and fixed transition function give the same successor \(F(x_t,u_t,w_t)\), hence the extended child trace is a parent trace. Projection onto state \(x_t\) gives reachable-set inclusion. ∎

## 5. One-dimensional linear corollary

For

\[
x_{t+1}=a x_t+b u_t+w_t,
\]

with interval sets \(R_t\), \(U_c\), and \(W\), exact interval propagation is

\[
R_{t+1}(c)=aR_t(c)\oplus bU_c\oplus W.
\]

If \(U_{c'}\subseteq U_c\), linear images and Minkowski addition preserve inclusion for any signs of \(a\) and \(b\). Thus \(R_t(c')\subseteq R_t(c)\) by induction. The executable S1 smoke checks this formula for signed dynamics and randomly generated nested intervals; it is a bug detector, not evidence for the theorem.

## 6. MIMO lifting and what remains

For \(x_{t+1}=Ax_t+Bu_t+w_t\), the same argument uses monotonicity of linear images and Minkowski sums over sets. The theorem itself does not require linearity; the hard S2 work is to show that the concrete compiler and five-effect enforcer satisfy Lemma 1 for state/history-dependent policies, then mechanize or independently audit the result.

## 7. Registered failure cases

- A child token activates a default/fallback rule that the parent cannot activate.
- A conflict-combining rule turns two restrictions into a permission union.
- `REWRITE` selects a globally “safe” command that is outside the effective parent token.
- `DEFER` advances a drifting plant but is modeled as no transition, or its hold action is unavailable to the parent.
- Parent and child use different context estimates or disturbance sets.
- The reported object is a selected controller trajectory rather than the union of authorized trajectories.

Any such behavior outside an explicitly narrowed theorem statement refutes C1 or C3.
