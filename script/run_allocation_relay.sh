#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${AETHERLINK_RELAY_BIND_HOST:-0.0.0.0}"
PORT="${AETHERLINK_RELAY_PORT:-43171}"
ALLOCATION_STORE="${AETHERLINK_RELAY_ALLOCATION_STORE:-}"
ALLOCATION_TOKEN="${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}"
REQUIRE_ALLOCATION=1
DRY_RUN=0
EPHEMERAL_ALLOCATIONS=0

usage() {
  cat <<'USAGE'
Usage:
  script/run_allocation_relay.sh [--host <bind-host>] [--port <port>] [--allocation-token <token>] [--allocation-store <path>] [--ephemeral-allocations] [--allow-legacy] [--dry-run]

Starts the AetherLink development relay. By default it requires route allocation,
which is the path used by QR pairing across different networks.
Allocation tickets are persisted by AetherLinkRelay by default so issued QR
relay ids can survive relay process restarts.

This relay forwards encrypted AetherLink runtime frames only. It is not an AI
backend and does not expose Ollama, LM Studio, prompts, chat history, or files.
Use --allocation-token, or AETHERLINK_RELAY_ALLOCATION_TOKEN, when the relay is
reachable outside the runtime host. Runtime bootstrap scripts can send the same
value with AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN.

For a no-USB different-network smoke, run this on a host/port reachable by both
the runtime machine and the Android device, then run:

  script/no_adb_external_relay_pairing_smoke.sh --relay-host <public-or-vpn-host> --relay-port <port>

To check relay/bootstrap readiness before starting RuntimeDevServer, run:

  script/run_different_network_dev_runtime.sh --relay-host <public-or-vpn-host> --relay-port <port> --preflight-only

For a USB-assisted app/deeplink regression check that still avoids adb reverse
for the relay, run:

  script/android_pairing_deeplink_smoke.sh --relay --external-relay-host <public-or-vpn-host> --external-relay-port <port>

USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      if [[ $# -lt 2 ]]; then
        echo "--host requires a value." >&2
        exit 2
      fi
      HOST="$2"
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        echo "--port requires a value." >&2
        exit 2
      fi
      PORT="$2"
      shift 2
      ;;
    --allow-legacy)
      REQUIRE_ALLOCATION=0
      shift
      ;;
    --allocation-store)
      if [[ $# -lt 2 ]]; then
        echo "--allocation-store requires a value." >&2
        exit 2
      fi
      ALLOCATION_STORE="$2"
      shift 2
      ;;
    --allocation-token)
      if [[ $# -lt 2 ]]; then
        echo "--allocation-token requires a value." >&2
        exit 2
      fi
      ALLOCATION_TOKEN="$2"
      shift 2
      ;;
    --ephemeral-allocations)
      EPHEMERAL_ALLOCATIONS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Invalid relay port: $PORT" >&2
  exit 2
fi

cd "$ROOT_DIR"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "AetherLink relay dry run"
  echo "Bind address: $HOST:$PORT"
  if [[ "$REQUIRE_ALLOCATION" == "1" ]]; then
    echo "Allocation required: yes"
  else
    echo "Allocation required: no (--allow-legacy)"
    echo "WARNING: legacy mode can mask QR-only relay/bootstrap allocation failures."
  fi
  if [[ "$EPHEMERAL_ALLOCATIONS" == "1" ]]; then
    echo "Allocation store: disabled (--ephemeral-allocations)"
  elif [[ -n "$ALLOCATION_STORE" ]]; then
    echo "Allocation store: $ALLOCATION_STORE"
  else
    echo "Allocation store: AetherLinkRelay default (~/.aetherlink-relay/allocations.json)"
  fi
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    echo "Allocation token: required"
  else
    echo "Allocation token: not required"
  fi
  echo "After the relay is running, verify the advertised host with:"
  echo "  script/run_different_network_dev_runtime.sh --relay-host <public-or-vpn-host> --relay-port $PORT --preflight-only"
  echo "Do not use the bind address as the QR relay host unless the trusted device can actually reach it."
  exit 0
fi

swift build --product AetherLinkRelay >/dev/null
RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
ARGS=("$RELAY_BIN" --host "$HOST" --port "$PORT")
if [[ "$REQUIRE_ALLOCATION" == "1" ]]; then
  ARGS+=(--require-allocation)
fi
if [[ "$EPHEMERAL_ALLOCATIONS" == "1" ]]; then
  ARGS+=(--ephemeral-allocations)
elif [[ -n "$ALLOCATION_STORE" ]]; then
  ARGS+=(--allocation-store "$ALLOCATION_STORE")
fi
if [[ -n "$ALLOCATION_TOKEN" ]]; then
  ARGS+=(--allocation-token "$ALLOCATION_TOKEN")
fi

echo "Starting AetherLink development relay on $HOST:$PORT"
if [[ "$REQUIRE_ALLOCATION" == "1" ]]; then
  echo "Allocation is required. Unknown relay ids will be rejected."
else
  echo "Legacy mode enabled. Unknown relay ids are allowed for compatibility."
fi
if [[ "$EPHEMERAL_ALLOCATIONS" == "1" ]]; then
  echo "Allocation tickets are not persisted."
elif [[ -n "$ALLOCATION_STORE" ]]; then
  echo "Allocation tickets persist at: $ALLOCATION_STORE"
else
  echo "Allocation tickets persist at the AetherLinkRelay default store."
fi
if [[ -n "$ALLOCATION_TOKEN" ]]; then
  echo "Allocation token is required for route allocation."
else
  echo "WARNING: no allocation token is required. Use this only on a private development relay."
fi
echo "Use a public, VPN, tunnel, or overlay address that both paired devices can reach."
echo "Preflight that advertised address with: script/run_different_network_dev_runtime.sh --relay-host <public-or-vpn-host> --relay-port $PORT --preflight-only"

exec "${ARGS[@]}"
