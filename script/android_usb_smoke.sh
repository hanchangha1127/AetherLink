#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LOCAL_AGENT_BRIDGE_PORT:-43170}"
LOG_FILE="${LOCAL_AGENT_BRIDGE_RUNTIME_LOG:-/tmp/aetherlink-runtime.log}"

cd "$ROOT_DIR"

swift build --product RuntimeDevServer
RUNTIME_BIN="$(swift build --show-bin-path)/RuntimeDevServer"
"$RUNTIME_BIN" >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  wait "$SERVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Waiting for Mac runtime dev server on 127.0.0.1:$PORT"
for _ in {1..40}; do
  if nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if ! nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1; then
  echo "Runtime dev server did not start. Log:" >&2
  cat "$LOG_FILE" >&2
  exit 2
fi

echo "Running unauthenticated runtime security smoke"
./script/runtime_smoke_test.py 127.0.0.1 "$PORT"
./script/android_usb_install.sh

echo "Runtime log: $LOG_FILE"
echo "Keep this script running while testing the Android app."
while true; do
  sleep 3600
done
