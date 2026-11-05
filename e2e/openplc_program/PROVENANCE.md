# OpenPLC program (frozen artifact)

The frozen OpenPLC program for the Section 6 end-to-end path: a 10 ms cyclic
task that latches commanded values and acknowledges them over Modbus holding
registers.

| File | Meaning |
|---|---|
| `project/` | OpenPLC Editor v4 project (`project.json`, `pous/programs/main.st`, `devices/`) — the authoritative source |
| `editor_build/` | The build directory the Editor CLI produced for target "OpenPLC Runtime v4" (STruC++ generated C++ sources + `strucpp_runtime` headers + `conf/modbus_slave.json`) — exactly what `openplc-cli upload` sends to the runtime |

## Program behaviour

- `TASK task0(INTERVAL := T#10ms, PRIORITY := 1)` — the 10 ms periodic task
  required by Section 6, frozen inside the program configuration.
- Located variables (mapped by the runtime's `modbus_slave` plugin onto Modbus
  holding registers, `%QW` image):
  - `%QW0 cmd_seq` — command sequence, written by the wrapper (or the bypass
    client); the program applies a command when `cmd_seq` changes.
  - `%QW1 cmd_value` — commanded value (centi-units encoding).
  - `%QW2 ack_seq` — set to the applied `cmd_seq`.
  - `%QW3 applied_value` — the latched command value.
  - `%QW4 heartbeat` — incremented every scan; observed externally to estimate
    scan boundaries and the scan-period distribution.
  - `%QW5 applied_count` — number of applied commands.
- No retention, no network I/O, no timing dependence beyond the task interval.

## Provenance

| Item | Value |
|---|---|
| Generated with | OpenPLC Editor CLI v4.3.4 (`OpenPLC.Editor-4.3.4.AppImage`, SHA-256 `b81863722d65eaa786f53234472601b649ea34a3f2f790f931beedaa7ec75fa0`), host-side, headless (`--cli`) |
| Compiled against | "OpenPLC Runtime v4" target; runs on OpenPLC Runtime v4.3.2 (git tag `v4.3.2`, commit `9fb5e1a29b574806f5aea3a4e78202c7a5d658ee`, native build at `/opt/zonecap/openplc-runtime-v4.3.2`) |
| Recreate | `APPDIR=<extracted AppImage> AppRun --cli create zonecap-e2e --path <parent> --language st --time "T#10ms"`; replace `pous/programs/main.st` with `project/pous/programs/main.st`; add the `servers` block from `project/project.json`; then `AppRun --cli compile <project> --target "OpenPLC Runtime v4"` |
| Upload | `AppRun --cli upload <project> --target "OpenPLC Runtime v4" --host <runtime> --credentials <user:pass> --yes` |

The compiled per-program library on the runtime (`build/libplc_<timestamp>.so`)
is timestamp-named; its SHA-256 is captured per run in
`environment_manifest.json` of every e2e result directory.
