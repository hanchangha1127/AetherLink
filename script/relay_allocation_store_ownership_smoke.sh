#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-owner.XXXXXX")"
STORE_PATH="$WORK_DIR/allocations.json"
FIRST_PID=""
SECOND_PID=""
SUCCESSOR_PID=""
RACE_A_PID=""
RACE_B_PID=""
WAIT_STATUS=""

terminate_process() {
  local pid="$1"
  local deadline=$((SECONDS + 5))

  kill -TERM "$pid" 2>/dev/null || true
  while kill -0 "$pid" 2>/dev/null; do
    if ((SECONDS >= deadline)); then
      kill -KILL "$pid" 2>/dev/null || true
      break
    fi
    sleep 0.05
  done
  wait "$pid" 2>/dev/null || true
}

cleanup() {
  for pid in "$FIRST_PID" "$SECOND_PID" "$SUCCESSOR_PID" "$RACE_A_PID" "$RACE_B_PID"; do
    if [[ -n "$pid" ]]; then
      terminate_process "$pid"
    fi
  done
  rm -rf "$WORK_DIR"
}

wait_for_exit() {
  local pid="$1"
  local log_path="$2"
  local deadline=$((SECONDS + 5))
  while kill -0 "$pid" 2>/dev/null; do
    if ((SECONDS >= deadline)); then
      cat "$log_path" >&2 || true
      echo "Competing relay did not exit before the ownership-check deadline." >&2
      return 1
    fi
    sleep 0.05
  done
  set +e
  wait "$pid"
  WAIT_STATUS=$?
  set -e
}
trap cleanup EXIT INT TERM

free_port() {
  python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

wait_for_listening() {
  local pid="$1"
  local log_path="$2"
  local port="$3"
  for _ in $(seq 1 100); do
    if grep -q "development relay listening" "$log_path" 2>/dev/null \
      && process_is_listening "$pid" "$port"; then
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      cat "$log_path" >&2 || true
      return 1
    fi
    sleep 0.05
  done
  cat "$log_path" >&2 || true
  return 1
}

process_is_listening() {
  local pid="$1"
  local port="$2"
  kill -0 "$pid" 2>/dev/null && python3 - "$port" <<'PY'
import socket
import sys

try:
    with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=0.2):
        pass
except OSError:
    raise SystemExit(1)
PY
}

wait_for_exactly_one_listener() {
  local first_pid="$1"
  local first_log="$2"
  local first_port="$3"
  local second_pid="$4"
  local second_log="$5"
  local second_port="$6"
  local deadline=$((SECONDS + 5))
  while ((SECONDS < deadline)); do
    local first_listening=0
    local second_listening=0
    grep -q "development relay listening" "$first_log" 2>/dev/null && first_listening=1
    grep -q "development relay listening" "$second_log" 2>/dev/null && second_listening=1
    if ((first_listening + second_listening == 1)); then
      if ((first_listening == 1)) \
        && ! kill -0 "$second_pid" 2>/dev/null \
        && process_is_listening "$first_pid" "$first_port"; then
        return 0
      fi
      if ((second_listening == 1)) \
        && ! kill -0 "$first_pid" 2>/dev/null \
        && process_is_listening "$second_pid" "$second_port"; then
        return 0
      fi
    fi
    if ((first_listening + second_listening > 1)); then
      echo "Both first-start relay processes acquired one allocation store." >&2
      return 1
    fi
    sleep 0.05
  done
  cat "$first_log" >&2 || true
  cat "$second_log" >&2 || true
  echo "First-start ownership race did not converge to one relay." >&2
  return 1
}

file_mode() {
  local path="$1"
  if stat -f '%Lp' "$path" >/dev/null 2>&1; then
    stat -f '%Lp' "$path"
  else
    stat -c '%a' "$path"
  fi
}

cd "$ROOT_DIR"
if [[ -n "${AETHERLINK_RELAY_BIN:-}" ]]; then
  RELAY_BIN="$AETHERLINK_RELAY_BIN"
else
  swift build --product AetherLinkRelay >/dev/null
  RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
fi

FIRST_PORT="$(free_port)"
SECOND_PORT="$(free_port)"
"$RELAY_BIN" \
  --host 127.0.0.1 \
  --port "$FIRST_PORT" \
  --allocation-store "$STORE_PATH" \
  >"$WORK_DIR/first.log" 2>&1 &
FIRST_PID=$!
wait_for_listening "$FIRST_PID" "$WORK_DIR/first.log" "$FIRST_PORT"

"$RELAY_BIN" \
  --host 127.0.0.1 \
  --port "$SECOND_PORT" \
  --allocation-store "$STORE_PATH" \
  >"$WORK_DIR/second.log" 2>&1 &
SECOND_PID=$!
wait_for_exit "$SECOND_PID" "$WORK_DIR/second.log"
SECOND_STATUS="$WAIT_STATUS"
SECOND_PID=""
SECOND_OUTPUT="$(<"$WORK_DIR/second.log")"
if [[ "$SECOND_STATUS" -eq 0 ]]; then
  printf '%s\n' "$SECOND_OUTPUT" >&2
  echo "Second relay unexpectedly acquired the same durable allocation store." >&2
  exit 1
fi
if [[ "$SECOND_OUTPUT" != *"allocation store is already owned by another relay process"* ]]; then
  printf '%s\n' "$SECOND_OUTPUT" >&2
  echo "Second relay did not report the store ownership conflict." >&2
  exit 1
fi
if ! kill -0 "$FIRST_PID" 2>/dev/null; then
  echo "The original relay stopped after the competing ownership attempt." >&2
  exit 1
fi

for lock_path in "$STORE_PATH.transaction.lock"; do
  if [[ ! -f "$lock_path" ]] || [[ "$(file_mode "$lock_path")" != "600" ]]; then
    echo "Relay allocation lock file is missing or not mode 600: $lock_path" >&2
    exit 1
  fi
done

python3 - "$STORE_PATH" <<'PY'
import json
import pathlib
import sys

store = pathlib.Path(sys.argv[1])
payload = json.loads(store.read_text())
token = payload.get("coordination_token")
marker = pathlib.Path(str(store) + ".transaction.lock").read_text()
if not isinstance(token, str) or len(token) != 64:
    raise SystemExit("Allocation store is missing its coordination token.")
if f"state=E\ntoken={token}\n" not in marker:
    raise SystemExit("Allocation store token does not match its established lock marker.")
PY

terminate_process "$FIRST_PID"
FIRST_PID=""

"$RELAY_BIN" \
  --host 127.0.0.1 \
  --port "$SECOND_PORT" \
  --allocation-store "$STORE_PATH" \
  >"$WORK_DIR/successor.log" 2>&1 &
SUCCESSOR_PID=$!
wait_for_listening "$SUCCESSOR_PID" "$WORK_DIR/successor.log" "$SECOND_PORT"

terminate_process "$SUCCESSOR_PID"
SUCCESSOR_PID=""

RACE_STORE_PATH="$WORK_DIR/race-allocations.json"
RACE_A_PORT="$(free_port)"
RACE_B_PORT="$(free_port)"
"$RELAY_BIN" \
  --host 127.0.0.1 \
  --port "$RACE_A_PORT" \
  --allocation-store "$RACE_STORE_PATH" \
  >"$WORK_DIR/race-a.log" 2>&1 &
RACE_A_PID=$!
"$RELAY_BIN" \
  --host 127.0.0.1 \
  --port "$RACE_B_PORT" \
  --allocation-store "$RACE_STORE_PATH" \
  >"$WORK_DIR/race-b.log" 2>&1 &
RACE_B_PID=$!
wait_for_exactly_one_listener \
  "$RACE_A_PID" "$WORK_DIR/race-a.log" "$RACE_A_PORT" \
  "$RACE_B_PID" "$WORK_DIR/race-b.log" "$RACE_B_PORT"

if grep -q "development relay listening" "$WORK_DIR/race-a.log"; then
  RACE_WINNER_PID="$RACE_A_PID"
  RACE_LOSER_PID="$RACE_B_PID"
  RACE_LOSER_LOG="$WORK_DIR/race-b.log"
else
  RACE_WINNER_PID="$RACE_B_PID"
  RACE_LOSER_PID="$RACE_A_PID"
  RACE_LOSER_LOG="$WORK_DIR/race-a.log"
fi
if ! grep -q "allocation store is already owned by another relay process" "$RACE_LOSER_LOG"; then
  cat "$RACE_LOSER_LOG" >&2 || true
  echo "First-start race loser did not report an ownership conflict." >&2
  exit 1
fi
terminate_process "$RACE_LOSER_PID"
terminate_process "$RACE_WINNER_PID"
RACE_A_PID=""
RACE_B_PID=""

SUCCESSOR_PORT="$(free_port)"
"$RELAY_BIN" \
  --host 127.0.0.1 \
  --port "$SUCCESSOR_PORT" \
  --allocation-store "$RACE_STORE_PATH" \
  >"$WORK_DIR/race-successor.log" 2>&1 &
SUCCESSOR_PID=$!
wait_for_listening "$SUCCESSOR_PID" "$WORK_DIR/race-successor.log" "$SUCCESSOR_PORT"

echo "Relay allocation store cross-process ownership smoke passed."
