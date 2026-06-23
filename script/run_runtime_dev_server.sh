#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LOCAL_AGENT_BRIDGE_PORT:-43170}"

cd "$ROOT_DIR"

echo "Starting AetherLink runtime dev server on port $PORT"
echo "This server is the Android-facing Mac runtime. It is not Ollama."
swift build --product RuntimeDevServer
RUNTIME_BIN="$(swift build --show-bin-path)/RuntimeDevServer"
"$RUNTIME_BIN"
