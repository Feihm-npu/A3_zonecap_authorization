# Attenuation Mutation Audit

Status: S2 exp-02 protocol and interpretation boundary.

## Purpose

Exp-02 tests whether the exp-01 refinement result depends on a semantic
definition of attenuation or on unchecked compiler defaults. The model is
finite and seedless. It abstracts every physical authority field as a typed
coordinate with values `{0, 1, 2}`. The registered parent admits `{0, 1}` in
each coordinate, and a legal child admits `{0}`. An injective one-step plant
maps each complete action tuple to a distinct state, so any child-only action is
also a concrete child-only reachable state.

The nine coordinates are source zone, target zone, conduit, asset, operation,
parameter, time, mode, and pre-action history-language class. Issuer and subject
identity are not plant-input coordinates: issuer must remain unchanged, while a
subject may change under delegation. Identity/provenance checks remain security
requirements but are not falsely counted as distinct physical dynamics here.

## Preregistered mutation classes

1. Omit each of the nine subset checks independently and present an amplifying
   child. Each mutant is unsafe and must yield a minimal child-only action/state.
2. Interpret an empty child caveat, a missing materialized child caveat, or an
   unknown delegated value as unrestricted/default-allow. Each is unsafe and
   must yield a child-only state.
3. Replace positive conjunction with XOR. This is non-monotone and must yield a
   child-only state.
4. Define attenuation from reachable-set inclusion. The same token pair is
   evaluated on an input-ignoring plant and an injective plant; plant-dependent
   classification kills the mutation because ZoneCap attenuation must be
   syntax-only.
5. Replace conjunction with positive OR or first-applicable evaluation. These
   mutations are expected to change policy decisions but may survive the C1
   inclusion property because positive set inclusion remains monotone. They are
   retained rather than mislabeled as C1 counterexamples; C2 decision-equivalence
   experiments are responsible for killing them.

This audit does not inject defects into SINT or Dodson/CHERI Macaroons. Their
documented restriction-only delegation is the fair schema baseline; exp-02 tests
ZoneCap's additional bridge from that syntax to physical transition inclusion.
The deeper common-subset instantiation remains exp-05.
