#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LOCAL_AGENT_BRIDGE_PORT:-43170}"

cd "$ROOT_DIR"

echo "Starting AetherLink Runtime dev server on port $PORT"
echo "This process serves paired clients; model providers stay behind AetherLink Runtime."

if [[ -z "${AETHERLINK_DEV_RUNTIME_IDENTITY_FILE:-}" ]]; then
  export AETHERLINK_DEV_RUNTIME_IDENTITY_FILE="$HOME/.aetherlink/runtime-dev-identity.json"
fi
echo "Runtime identity file: $AETHERLINK_DEV_RUNTIME_IDENTITY_FILE"

if [[ -n "${AETHERLINK_RELAY_HOST:-}" ]]; then
  export AETHERLINK_RELAY_PORT="${AETHERLINK_RELAY_PORT:-43171}"
  if [[ -z "${AETHERLINK_RELAY_SECRET:-}" ]]; then
    if command -v openssl >/dev/null 2>&1; then
      AETHERLINK_RELAY_SECRET="$(openssl rand -base64 32)"
    else
      AETHERLINK_RELAY_SECRET="$(uuidgen)-$(uuidgen)"
    fi
    export AETHERLINK_RELAY_SECRET
  fi
  echo "Remote relay route enabled: $AETHERLINK_RELAY_HOST:$AETHERLINK_RELAY_PORT"
  echo "Pairing QR will include relay metadata and will not default to 127.0.0.1 unless AETHERLINK_DEV_PAIRING_HOST is set."
fi

if [[ -n "${AETHERLINK_BOOTSTRAP_RELAY_HOST:-}" ]]; then
  export AETHERLINK_BOOTSTRAP_RELAY_PORT="${AETHERLINK_BOOTSTRAP_RELAY_PORT:-43171}"
  echo "Remote relay allocation enabled: $AETHERLINK_BOOTSTRAP_RELAY_HOST:$AETHERLINK_BOOTSTRAP_RELAY_PORT"
  echo "Runtime will request relay route material before printing the development pairing QR."
fi

swift build --product RuntimeDevServer
RUNTIME_BIN="$(swift build --show-bin-path)/RuntimeDevServer"
"$RUNTIME_BIN"
