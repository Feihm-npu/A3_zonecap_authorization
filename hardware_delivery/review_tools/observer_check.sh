#!/usr/bin/env bash
# Run the e2e client (and wrapper) under review against fakeplc's exactly periodic
# heartbeat: idle control, bypass, and instrumented, then summarise.  Every late
# tick or phase error this reports is produced by the observer, not by a PLC.
# A separate-process reference observer runs alongside each mode under the same
# load, as the positive control for the observer the review asks for.
#
# Environment (defaults follow the Jetson single_host layout):
#   PYTHON        CPython 3.10 with PyNaCl 1.5.0 (client.py seeds random with a tuple,
#                 which CPython 3.11+ rejects)                       [python3]
#   E2E_DIR       directory holding client.py, wrapper.py, e2e_config.json   [<repo>/e2e]
#   CORPUS_DIR    built C5 corpus                                   [<repo>/build/c5_corpus]
#   OUT_DIR       output directory, must not exist                  [<repo>/build/observer_check]
#   COMMANDS      commands per loaded mode                          [3000]
#   IDLE_SECONDS  length of the idle control                        [20]
#   CLIENT_CORE PLC_CORE WRAPPER_CORE AUDIT_CORE OBSERVER_CORE      [1 2 3 4 5]
#   PLC_PORT WRAPPER_PORT                                           [25020 28600]
# On the Jetson, run it only when no measurement is in progress, and stop
# openplc-runtime or move PLC_CORE off core 2.
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
PYTHON=${PYTHON:-python3}
E2E_DIR=$(cd "${E2E_DIR:-$REPO/e2e}" && pwd)
CORPUS_DIR=${CORPUS_DIR:-$REPO/build/c5_corpus}
OUT_DIR=${OUT_DIR:-$REPO/build/observer_check}
COMMANDS=${COMMANDS:-3000}
IDLE_SECONDS=${IDLE_SECONDS:-20}
CLIENT_CORE=${CLIENT_CORE:-1}
PLC_CORE=${PLC_CORE:-2}
WRAPPER_CORE=${WRAPPER_CORE:-3}
AUDIT_CORE=${AUDIT_CORE:-4}
OBSERVER_CORE=${OBSERVER_CORE:-5}
PLC_PORT=${PLC_PORT:-25020}
WRAPPER_PORT=${WRAPPER_PORT:-28600}
SEED=104729

"$PYTHON" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 10))' \
  || { echo "observer_check: PYTHON must be CPython 3.10" >&2; exit 2; }
mkdir -p "$(dirname "$OUT_DIR")"
mkdir "$OUT_DIR"
export PYTHONPATH="$HERE/pymodbus_shim:$REPO/src"

"$PYTHON" - "$E2E_DIR/e2e_config.json" "$OUT_DIR/check_config.json" \
  "$PLC_PORT" "$WRAPPER_PORT" "$WRAPPER_CORE" "$AUDIT_CORE" "$CLIENT_CORE" "$PLC_CORE" <<'EOF'
import json, sys
source, target, plc_port, wrapper_port, wrapper_core, audit_core, client_core, plc_core = sys.argv[1:]
setting = json.load(open(source))
setting["modbus"]["port"] = int(plc_port)
setting["wrapper"]["port"] = int(wrapper_port)
setting["cpu"] = {"benchmark_core": int(wrapper_core), "audit_core": int(audit_core),
                  "monitor_core": int(client_core), "openplc_core": int(plc_core)}
json.dump(setting, open(target, "w"), indent=2)
EOF

{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host: $(uname -a)"
  echo "python: $("$PYTHON" --version 2>&1) ($PYTHON)"
  echo "e2e commit: $(git -C "$E2E_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
  (cd "$E2E_DIR" && sha256sum client.py wrapper.py e2e_config.json)
  (cd "$HERE" && sha256sum fakeplc.py pymodbus_shim/pymodbus/client.py idle_monitor.py \
    reference_observer.py summarize.py observer_check.sh)
  echo "commands per mode: $COMMANDS, idle seconds: $IDLE_SECONDS, seed: $SEED"
  echo "cores: client $CLIENT_CORE, fakeplc $PLC_CORE, wrapper $WRAPPER_CORE," \
    "audit drain $AUDIT_CORE, reference observer $OBSERVER_CORE"
} > "$OUT_DIR/run_info.txt"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT

wait_for() {  # file pattern seconds
  for _ in $(seq 1 $(( $3 * 5 ))); do
    grep -q "$2" "$1" 2>/dev/null && return 0
    sleep 0.2
  done
  echo "observer_check: timed out waiting for '$2' in $1" >&2
  exit 1
}

OBSERVER=
start_observer() {  # mode
  "$PYTHON" "$HERE/reference_observer.py" --port "$PLC_PORT" --core "$OBSERVER_CORE" \
    --out "$OUT_DIR/$1.observer.txt" &
  OBSERVER=$!
  sleep 0.5
}
stop_observer() {
  kill -TERM "$OBSERVER"
  wait "$OBSERVER"
}

"$PYTHON" "$HERE/fakeplc.py" --port "$PLC_PORT" --core "$PLC_CORE" > "$OUT_DIR/fakeplc.log" 2>&1 &
PIDS+=($!)
wait_for "$OUT_DIR/fakeplc.log" "fakeplc ready" 10

echo "observer_check: idle control (${IDLE_SECONDS} s)"
start_observer idle
"$PYTHON" "$HERE/idle_monitor.py" --client "$E2E_DIR/client.py" --port "$PLC_PORT" \
  --core "$CLIENT_CORE" --seconds "$IDLE_SECONDS" --out "$OUT_DIR/idle.json"
stop_observer

echo "observer_check: bypass (${COMMANDS} commands)"
start_observer bypass
"$PYTHON" "$E2E_DIR/client.py" --corpus-dir "$CORPUS_DIR" --e2e-config "$OUT_DIR/check_config.json" \
  --seed "$SEED" --warmup 0 --measured "$COMMANDS" --bypass --pin-core "$CLIENT_CORE" \
  --out "$OUT_DIR/bypass.jsonl" 2> "$OUT_DIR/bypass.client.log"
stop_observer

"$PYTHON" "$E2E_DIR/wrapper.py" --corpus-dir "$CORPUS_DIR" --e2e-config "$OUT_DIR/check_config.json" \
  --audit-log "$OUT_DIR/instrumented.audit.log" --pin-core "$WRAPPER_CORE" > "$OUT_DIR/wrapper.log" 2>&1 &
PIDS+=($!)
wait_for "$OUT_DIR/wrapper.log" "wrapper listening" 120

echo "observer_check: instrumented (${COMMANDS} commands)"
start_observer instrumented
"$PYTHON" "$E2E_DIR/client.py" --corpus-dir "$CORPUS_DIR" --e2e-config "$OUT_DIR/check_config.json" \
  --seed "$SEED" --warmup 0 --measured "$COMMANDS" --pin-core "$CLIENT_CORE" \
  --wrapper-port "$WRAPPER_PORT" --out "$OUT_DIR/instrumented.jsonl" 2> "$OUT_DIR/instrumented.client.log"
stop_observer

cleanup
trap - EXIT
"$PYTHON" "$HERE/summarize.py" "$OUT_DIR" | tee "$OUT_DIR/summary.md"
