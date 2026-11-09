Scan-period statistics reported by the observer (fakeplc is exactly periodic):

| mode | late ticks >12 ms | observation gaps | p50 | p99 | min | max | mean |
|---|---|---|---|---|---|---|---|
| idle | 0.05% | 0.05% | 10.0 ms | 10.43 ms | 2.48 ms | 15.0 ms | 9.99 ms |
| bypass | 23.64% | 2.1% | 10.75 ms | 20.81 ms | 0.61 ms | 21.56 ms | 10.09 ms |
| instrumented | 29.49% | 1.78% | 10.76 ms | 20.97 ms | 0.6 ms | 22.15 ms | 10.04 ms |

Logged phase_us against the true scan phase (nearest-rank):

| mode | error p50 | p90 | p99 | max | true phase, 1 ms bins |
|---|---|---|---|---|---|
| bypass | 2.15 ms | 4.44 ms | 4.93 ms | 5.0 ms | [303, 317, 302, 287, 322, 305, 263, 299, 334, 268] |
| instrumented | 2.56 ms | 4.57 ms | 4.94 ms | 5.0 ms | [314, 304, 308, 289, 309, 284, 278, 321, 308, 285] |
| random guess | 2.5 ms | 4.5 ms | 4.95 ms | 5.0 ms | |

Separate-process reference observer under the same load (nearest-rank):

| mode | boundaries | late ticks >12 ms | lag p50 | lag p99 | lag max |
|---|---|---|---|---|---|
| idle | 2057 | 0.15% | 0.329 ms | 0.628 ms | 6.221 ms |
| bypass | 4596 | 0.37% | 0.335 ms | 0.66 ms | 8.333 ms |
| instrumented | 4833 | 0.23% | 0.335 ms | 0.649 ms | 8.675 ms |

Sanity: {"bypass": {"commands": 3000, "ack_timeouts": 0, "emitted": 848}, "instrumented": {"commands": 3000, "ack_timeouts": 0, "emitted": 848, "effect_mismatches": 0}}
