# C3 Exhaustive Sequence Protocol

Status: S2 exp-14 protocol, fixed before execution.

## Finite alphabet and bound

Exp-14 compiles all 126 frozen exp-07 scopes and explores every request/context
word of length zero through five over this five-symbol alphabet:

- `narrow`: a valid request plus a strict lower-half runtime envelope;
- `defer`: the valid request with incomplete context;
- `valid`: a complete authorized request;
- `rewrite`: a structurally valid request one unit above the active interval;
- `deny`: the valid request with an unregistered action.

The symbols are state-dependent: valid and rewrite values are derived from the
then-active capability, and repeated `narrow` symbols repeatedly attenuate that
capability. The exploration is seedless. With alphabet size 5 and horizon 5,
each scope has 3,906 words including the empty word and 3,905 tree transitions.

## Automaton state and properties

The abstract state is `(active parameter interval, physical state,
defer-pending flag)`. `write` adds its normalized value to the abstract physical
state; `read` is the registered stutter. Root scopes select `write` for ordinary
allow/rewrite requests when available, while delegated read-only scopes use
`read`. Every `DEFER` output is bound to `read` inside the active interval.

At every tree transition the checker verifies the expected effect, strict legal
attenuation, active-capability output membership, defer stutter, and immediate
parent realizability for depth-1/depth-2 scopes. `DENY` and `ATTENUATE` emit no
physical transition. A bounded state is a deadlock only if no alphabet symbol
has an enabled successor; reaching the horizon with pending external context is
not mislabeled as an enforcer deadlock.

## Hand-picked baseline and coverage

The baseline runs exactly one named path per compiled scope:

`narrow -> defer -> valid -> rewrite -> deny`.

Both suites report words, tree transitions, physical transitions, unique
abstract states, unique transition signatures, and all observed symbol/effect
unigrams, bigrams, and trigrams. The hand-picked suite is expected to reach all
five effects but only four ordered pairs and three ordered triples; exhaustive
enumeration must cover all 25 pairs and 125 triples. Effect coverage alone is
therefore not treated as sequence coverage.

Three trigger mutants are fixed before execution: a non-stuttering second
defer on `defer,defer`, a widened second attenuation on `narrow,narrow`, and an
unauthorized output on `rewrite,narrow`. A suite kills a mutant only if it
contains the exact triggering ordered pair and the ordinary property checker
would reject the injected behavior. Exhaustive enumeration must kill all three;
the named path is expected to kill none.

This bounded exhaustive check is falsification support for C3, not a substitute
for the compositional proof or an unbounded liveness result.
