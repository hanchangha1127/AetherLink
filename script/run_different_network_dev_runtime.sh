#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LOCAL_AGENT_BRIDGE_PORT:-43170}"
RELAY_PORT="${AETHERLINK_RELAY_PORT:-43171}"
START_LOCAL_RELAY=0

usage() {
  cat <<'USAGE'
Usage:
  script/run_different_network_dev_runtime.sh --relay-host <host> [--relay-port <port>] [--start-local-relay]

Starts the AetherLink development runtime with relay metadata so a client on a
different network can connect after scanning the generated relay QR.

Requirements:
  - <host>:<port> must be reachable from both the runtime host and the client.
  - --start-local-relay starts script/aetherlink_relay.py on this machine. That
    only works across networks when this machine is publicly reachable or the
    port is forwarded by another tunnel/VPN you control.

This is connection infrastructure only. The client still talks to the paired
AetherLink runtime protocol; Ollama and LM Studio are never exposed directly.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --relay-host)
      shift
      AETHERLINK_RELAY_HOST="${1:-}"
      ;;
    --relay-port)
      shift
      RELAY_PORT="${1:-}"
      ;;
    --start-local-relay)
      START_LOCAL_RELAY=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -z "${AETHERLINK_RELAY_HOST:-}" ]]; then
  echo "Missing --relay-host. The relay host must be reachable from both devices." >&2
  usage >&2
  exit 2
fi

if ! [[ "$RELAY_PORT" =~ ^[0-9]+$ ]] || (( RELAY_PORT < 1 || RELAY_PORT > 65535 )); then
  echo "Invalid relay port: $RELAY_PORT" >&2
  exit 2
fi

if [[ -z "${AETHERLINK_RELAY_SECRET:-}" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    AETHERLINK_RELAY_SECRET="$(openssl rand -base64 32)"
  else
    AETHERLINK_RELAY_SECRET="$(uuidgen)-$(uuidgen)"
  fi
fi

export AETHERLINK_RELAY_HOST
export AETHERLINK_RELAY_PORT="$RELAY_PORT"
export AETHERLINK_RELAY_SECRET
export AETHERLINK_DEV_PAIRING="${AETHERLINK_DEV_PAIRING:-1}"

RELAY_PID=""
cleanup() {
  if [[ -n "$RELAY_PID" ]]; then
    kill "$RELAY_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$ROOT_DIR"

if [[ "$START_LOCAL_RELAY" == "1" ]]; then
  echo "Starting local development relay on 0.0.0.0:$RELAY_PORT"
  echo "This is only cross-network reachable if $AETHERLINK_RELAY_HOST:$RELAY_PORT reaches this machine."
  python3 script/aetherlink_relay.py --host 0.0.0.0 --port "$RELAY_PORT" &
  RELAY_PID="$!"
  sleep 0.5
fi

echo "Starting AetherLink runtime on local port $PORT"
echo "Relay route: $AETHERLINK_RELAY_HOST:$AETHERLINK_RELAY_PORT"
echo "Relay frame secret is set and will be embedded in the development pairing QR."
echo "Scan the printed relay QR payload from the client, or use the macOS app Pairing panel if using the GUI runtime."

LOCAL_AGENT_BRIDGE_PORT="$PORT" ./script/run_runtime_dev_server.sh
