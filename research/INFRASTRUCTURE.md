# S1 Infrastructure

## Quick check

```bash
pytest -q
PYTHONPATH=src python -m zonecap.run \
  --config configs/s1_smoke.json \
  --output results/<new_run_id> \
  --seed <development_seed>
```

The runner refuses to overwrite an existing run directory. Every run writes `config.json`, `command.txt`, `seed.txt`, `log.txt`, and `metrics.json`, plus compiled/derived capabilities, decisions, and any counterexamples.

## Pipeline

1. Load an architecture's zones, conduits, policies, plant, and request fixtures.
2. Compile each policy into a capability over zone endpoints, conduit, asset, action, parameter interval, time window, mode, and pre-action sequence.
3. Generate depth-1/2 attenuations and reject any widening.
4. Evaluate requests using `ALLOW`, `DENY`, `ATTENUATE`, `REWRITE`, or `DEFER`.
5. Propagate exact one-dimensional interval reachable sets and check child-set inclusion at every horizon.
6. Write all metrics and counterexamples to an immutable new run directory.

## Scope

- `examples/dev_tank.json` and `examples/dev_robot_cell.json` are development fixtures only. They are not IEC 62443 conformance evidence and are permanently excluded from confirmatory results.
- The current rewrite is a boundary clamp used to exercise the authority-preservation obligation. S2 must replace/extend it with registered plant-specific edit choices and compare against deny-only enforcement.
- The current defer decision does not yet advance the plant. S2 must model an explicit hold/stutter transition and refute the theorem when that transition is absent.
- The exact interval implementation is intentionally dependency-free because `casadi` is absent from the active environment. A MIMO set representation will be pinned before exp-03.

## Baseline status

The SINT baseline source, commands, pinned commit, full benchmark metrics, and limitations are archived in `results/s1_baseline_sint_20260831/`. CPAC and PLC-ABAC did not expose a complete runnable reported-number artifact on the located publication/project pages. The Lanotte/Merro artifact is public, but its full setup requires non-default licensed software and FPGA/PLC hardware; see `research/NOTEBOOK.md`.
