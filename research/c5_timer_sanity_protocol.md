# C5 Local Timer and Check-Activation Sanity Protocol

Status: S2 exp-26 protocol, fixed before execution.

Exp-26 is a seedless x86 infrastructure sanity run. It cannot support the
Jetson-specific C5 latency claim and must not be pooled with exp-22–25. Its
purpose is to validate the timing, affinity, and disabled-check detection
contract that the hardware group must reproduce on the Jetson.

The run pins its single worker process to logical CPU 0, verifies both
`os.sched_getaffinity` and `/proc/self/status`, and restores the original
affinity on exit. It records Python's `perf_counter` clock declaration and
100,000 consecutive empirical clock deltas. The clock must be monotonic,
non-adjustable, have no backwards transition, and have empirical resolution
below the median empty-call duration.

After 10,000 warm-ups, the run stores 100,000 integer-nanosecond samples for an
empty Python function and 100,000 samples for an instrumented local sanity
pipeline. The pipeline parses a serialized request, verifies a frozen token
integrity digest, checks a revocation set, validates runtime context, evaluates
the real ZoneCap `PolicyEngine`, and enqueues a bounded audit record. This is a
timing-control workload, not the not-yet-frozen cryptographic C5 full path.

The forced-slow configuration adds a 5 ms sleep inside the same timed pipeline
and stores 100 samples after five warm-ups. Its minimum observed time must be at
least 4 ms. Both median and p99 ordering must be:

`empty call < full sanity pipeline < forced-slow pipeline`.

The check-activation detector first observes all six required stages. It then
disables exactly one stage at a time and must identify the missing stage for all
six mutants. The decision can remain unchanged; detection is based on the
stage-activation record, which prevents a disabled check from being hidden by a
happy-path request.

Every raw duration and empirical timer delta is retained in compressed JSON.
Percentiles use nearest-rank (`ceil(p*N)`, one-indexed) without interpolation.
Any affinity, clock, ordering, forced-slow, sample-count, full-activation, or
mutant-detection failure invalidates exp-26.

