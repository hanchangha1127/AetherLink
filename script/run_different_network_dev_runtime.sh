#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LOCAL_AGENT_BRIDGE_PORT:-43170}"
RELAY_HOST="${AETHERLINK_BOOTSTRAP_RELAY_HOST:-${AETHERLINK_RELAY_HOST:-}}"
RELAY_PORT="${AETHERLINK_BOOTSTRAP_RELAY_PORT:-${AETHERLINK_RELAY_PORT:-43171}}"
RELAY_ENDPOINTS="${AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS:-}"
ALLOCATION_TOKEN="${AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN:-${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}}"
START_LOCAL_RELAY=0
ALLOW_PRIVATE_RELAY=0
PREFLIGHT_ONLY=0

usage() {
  cat <<'USAGE'
Usage:
  script/run_different_network_dev_runtime.sh --relay-host <host> [--relay-port <port>] [--allocation-token <token>] [--start-local-relay] [--preflight-only]
  script/run_different_network_dev_runtime.sh --relay-endpoint <host[:port]> [--relay-endpoint <host[:port]> ...]

Starts the AetherLink development runtime with relay metadata so a trusted
device on a different network can connect after scanning the generated relay QR.
RuntimeDevServer prints both AETHERLINK_DEV_PAIRING_INFO JSON and
AETHERLINK_DEV_PAIRING_URI for no-ADB optical QR or diagnostics-payload testing.

Requirements:
  - <host>:<port> must be reachable from both the runtime host and the trusted device.
  - AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS may contain a comma-separated endpoint
    list. --relay-endpoint appends to that list and may be passed more than once.
  - --start-local-relay starts AetherLinkRelay in allocation-required mode on
    the runtime host. That only works across networks when the runtime host is
    publicly reachable or the port is forwarded by another tunnel/VPN you control.
  - Loopback, .local, unspecified, link-local, and private RFC1918 relay hosts
    are rejected by default because they are usually unreachable from a trusted
    device on an unrelated network.

This is connection infrastructure only. The trusted device still talks to the
paired AetherLink runtime protocol; Ollama and LM Studio are never exposed directly.

Options:
  --preflight-only       Validate endpoint shape and allocation reachability,
                         then exit before starting RuntimeDevServer.
  --allocation-token <token>
                         Send an allocation token to the development relay.
                         Required when the relay was started with
                         --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN.
  --allow-private-relay  Allow private/link-local relay hosts for an explicit
                         VPN, tunnel, or private overlay you control.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --relay-host)
      shift
      RELAY_HOST="${1:-}"
      RELAY_ENDPOINTS=""
      ;;
    --relay-port)
      shift
      RELAY_PORT="${1:-}"
      ;;
    --relay-endpoint)
      shift
      if [[ -z "${1:-}" ]]; then
        echo "--relay-endpoint requires a value." >&2
        exit 2
      fi
      if [[ -n "${RELAY_ENDPOINTS:-}" ]]; then
        RELAY_ENDPOINTS="$RELAY_ENDPOINTS,$1"
      else
        RELAY_ENDPOINTS="$1"
      fi
      ;;
    --allocation-token)
      shift
      ALLOCATION_TOKEN="${1:-}"
      if [[ -z "$ALLOCATION_TOKEN" ]]; then
        echo "--allocation-token requires a value." >&2
        exit 2
      fi
      ;;
    --start-local-relay)
      START_LOCAL_RELAY=1
      ;;
    --allow-private-relay)
      ALLOW_PRIVATE_RELAY=1
      ;;
    --preflight-only)
      PREFLIGHT_ONLY=1
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

USE_ENDPOINT_LIST=0
if [[ -n "${RELAY_ENDPOINTS:-}" ]]; then
  USE_ENDPOINT_LIST=1
fi

if [[ "$USE_ENDPOINT_LIST" != "1" && -z "${RELAY_HOST:-}" ]]; then
  echo "Missing --relay-host or --relay-endpoint. The relay must be reachable from the runtime host and trusted device." >&2
  usage >&2
  exit 2
fi

if ! [[ "$RELAY_PORT" =~ ^[0-9]+$ ]] || (( RELAY_PORT < 1 || RELAY_PORT > 65535 )); then
  echo "Invalid relay port: $RELAY_PORT" >&2
  exit 2
fi

USE_LEGACY_RELAY=0
if [[ -n "${AETHERLINK_RELAY_ID:-}" || -n "${AETHERLINK_RELAY_SECRET:-}" ]]; then
  if [[ -z "${AETHERLINK_RELAY_ID:-}" || -z "${AETHERLINK_RELAY_SECRET:-}" ]]; then
    echo "Legacy manual relay mode requires both AETHERLINK_RELAY_ID and AETHERLINK_RELAY_SECRET." >&2
    exit 2
  fi
  USE_LEGACY_RELAY=1
fi

resolve_relay_endpoints() {
  local endpoints="$1"
  local fallback_host="$2"
  local default_port="$3"
  python3 - "$endpoints" "$fallback_host" "$default_port" <<'PY'
import sys

endpoint_list = sys.argv[1].strip()
fallback_host = sys.argv[2].strip()
default_port_text = sys.argv[3].strip()

try:
    default_port = int(default_port_text)
except ValueError:
    print(f"Invalid relay port: {default_port_text}", file=sys.stderr)
    raise SystemExit(2)
if not 1 <= default_port <= 65535:
    print(f"Invalid relay port: {default_port}", file=sys.stderr)
    raise SystemExit(2)

values = [item.strip() for item in endpoint_list.split(",") if item.strip()]
if not values and fallback_host:
    values = [fallback_host]
if not values:
    print("No relay endpoints were provided.", file=sys.stderr)
    raise SystemExit(2)

def parse_endpoint(value):
    if value.startswith("["):
        close = value.find("]")
        if close <= 1:
            raise ValueError(f"Invalid relay endpoint: {value}")
        host = value[1:close]
        remainder = value[close + 1:]
        if not remainder:
            return host, default_port
        if not remainder.startswith(":"):
            raise ValueError(f"Invalid relay endpoint: {value}")
        port_text = remainder[1:]
    elif value.count(":") == 1:
        host, port_text = value.rsplit(":", 1)
        if not host:
            raise ValueError(f"Invalid relay endpoint: {value}")
    else:
        return value, default_port

    try:
        port = int(port_text)
    except ValueError:
        raise ValueError(f"Invalid relay endpoint port: {value}") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid relay endpoint port: {value}")
    return host, port

for raw in values:
    try:
        host, port = parse_endpoint(raw)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
    if not host:
        print(f"Invalid relay endpoint: {raw}", file=sys.stderr)
        raise SystemExit(2)
    print(f"{host}\t{port}")
PY
}

RELAY_ENDPOINT_LINES=()
while IFS= read -r endpoint_line; do
  RELAY_ENDPOINT_LINES+=("$endpoint_line")
done < <(resolve_relay_endpoints "$RELAY_ENDPOINTS" "$RELAY_HOST" "$RELAY_PORT")
if [[ "${#RELAY_ENDPOINT_LINES[@]}" -eq 0 ]]; then
  echo "No relay endpoints were provided." >&2
  exit 2
fi

FIRST_RELAY_HOST="${RELAY_ENDPOINT_LINES[0]%%$'\t'*}"
FIRST_RELAY_PORT="${RELAY_ENDPOINT_LINES[0]##*$'\t'}"

if [[ "$USE_LEGACY_RELAY" == "1" && "$USE_ENDPOINT_LIST" == "1" ]]; then
  echo "Legacy manual relay mode requires --relay-host/--relay-port, not AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS or --relay-endpoint." >&2
  exit 2
fi

if [[ "$START_LOCAL_RELAY" == "1" && "${#RELAY_ENDPOINT_LINES[@]}" -ne 1 ]]; then
  echo "--start-local-relay can only be used with one relay endpoint." >&2
  exit 2
fi

validate_relay_endpoint_scope() {
  local allow_private="$1"
  local allow_local="$2"
  shift 2
  python3 - "$allow_private" "$allow_local" "$@" <<'PY'
import ipaddress
import socket
import sys

allow_private = sys.argv[1] == "1"
allow_local = sys.argv[2] == "1"
endpoints = sys.argv[3:]

def classify(host):
    normalized = host.strip().lower().strip("[]")
    if not normalized:
        return "empty"
    if "://" in normalized or "/" in normalized or "@" in normalized or "?" in normalized or "#" in normalized:
        return "url"
    if normalized in {"localhost", "0.0.0.0", "::", "::1"}:
        return "local"
    if normalized.endswith(".local"):
        return "local"
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return "hostname"
    if address.is_loopback or address.is_unspecified:
        return "local"
    if address.is_private or address.is_link_local:
        return "private"
    return "public"

failed = False
for item in endpoints:
    host, port = item.split("\t", 1)
    kind = classify(host)
    if kind == "empty":
        print("Invalid relay endpoint: empty host", file=sys.stderr)
        failed = True
    elif kind == "url":
        print(f"Invalid relay endpoint {host}:{port}: use a host or IP address, not a URL.", file=sys.stderr)
        failed = True
    elif kind == "local" and not allow_local:
        print(
            f"Invalid different-network relay endpoint {host}:{port}: loopback, .local, or unspecified hosts cannot be reached by a trusted device on another network. Use a public/VPN/tunnel relay or --start-local-relay for local diagnostics.",
            file=sys.stderr,
        )
        failed = True
    elif kind == "private" and not allow_private and not allow_local:
        print(
            f"Invalid different-network relay endpoint {host}:{port}: private/link-local addresses usually do not cross unrelated networks. Use a public/VPN/tunnel relay, or pass --allow-private-relay only for an explicit private overlay reachable by the runtime host and trusted device.",
            file=sys.stderr,
        )
        failed = True

if failed:
    raise SystemExit(2)
PY
}

validate_relay_endpoint_scope "$ALLOW_PRIVATE_RELAY" "$START_LOCAL_RELAY" "${RELAY_ENDPOINT_LINES[@]}"

if [[ "$USE_LEGACY_RELAY" == "1" ]]; then
  export AETHERLINK_RELAY_HOST="$RELAY_HOST"
  export AETHERLINK_RELAY_PORT="$RELAY_PORT"
  export AETHERLINK_RELAY_ID
  export AETHERLINK_RELAY_SECRET
else
  unset AETHERLINK_RELAY_HOST
  unset AETHERLINK_RELAY_PORT
  unset AETHERLINK_RELAY_ID
  unset AETHERLINK_RELAY_SECRET
  if [[ "$USE_ENDPOINT_LIST" == "1" ]]; then
    export AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS="$RELAY_ENDPOINTS"
    export AETHERLINK_BOOTSTRAP_RELAY_PORT="$RELAY_PORT"
    unset AETHERLINK_BOOTSTRAP_RELAY_HOST
  else
    unset AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS
    export AETHERLINK_BOOTSTRAP_RELAY_HOST="$RELAY_HOST"
    export AETHERLINK_BOOTSTRAP_RELAY_PORT="$RELAY_PORT"
  fi
fi
export AETHERLINK_DEV_PAIRING="${AETHERLINK_DEV_PAIRING:-1}"

RELAY_PID=""
cleanup() {
  if [[ -n "$RELAY_PID" ]]; then
    kill "$RELAY_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$ROOT_DIR"

check_relay_allocation() {
  local host="$1"
  local port="$2"
  local token="$3"
  local timeout="${4:-5}"
  python3 - "$host" "$port" "$token" "$timeout" <<'PY'
import json
import socket
import sys
import uuid

host = sys.argv[1]
port = int(sys.argv[2])
allocation_token = sys.argv[3].strip()
timeout = float(sys.argv[4])
route_token = f"aetherlink-preflight-{uuid.uuid4()}"
prefix = "AETHERLINK_RELAY allocation "
parts = ["AETHERLINK_RELAY", "allocate", route_token]
if allocation_token:
    parts.append(f"allocation_token={allocation_token}")

try:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall((" ".join(parts) + "\n").encode("utf-8"))
        buffer = b""
        while not buffer.endswith(b"\n") and len(buffer) < 8192:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buffer += chunk
except OSError as error:
    print(f"Could not allocate relay route from {host}:{port}: {error}", file=sys.stderr)
    raise SystemExit(1)

line = buffer.decode("utf-8", errors="replace").strip()
if not line.startswith(prefix):
    print(f"Relay {host}:{port} did not return an allocation response: {line!r}", file=sys.stderr)
    raise SystemExit(1)

try:
    payload = json.loads(line[len(prefix):])
except json.JSONDecodeError as error:
    print(f"Relay {host}:{port} returned invalid allocation JSON: {error}", file=sys.stderr)
    raise SystemExit(1)

required = ["relay_id", "relay_secret", "relay_expires_at", "relay_nonce"]
missing = [key for key in required if not payload.get(key)]
if missing:
    print(f"Relay {host}:{port} allocation response missing: {', '.join(missing)}", file=sys.stderr)
    raise SystemExit(1)
PY
}

if [[ "$START_LOCAL_RELAY" == "1" ]]; then
  echo "Starting local development relay on 0.0.0.0:$FIRST_RELAY_PORT"
  echo "This is only cross-network reachable if $FIRST_RELAY_HOST:$FIRST_RELAY_PORT reaches the runtime host."
  swift build --product AetherLinkRelay >/dev/null
  RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
  RELAY_ARGS=("$RELAY_BIN" --host 0.0.0.0 --port "$FIRST_RELAY_PORT")
  if [[ "$USE_LEGACY_RELAY" != "1" ]]; then
    RELAY_ARGS+=(--require-allocation)
  fi
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    RELAY_ARGS+=(--allocation-token "$ALLOCATION_TOKEN")
  fi
  "${RELAY_ARGS[@]}" &
  RELAY_PID="$!"
  sleep 0.5
fi

if [[ "$USE_LEGACY_RELAY" != "1" ]]; then
  allocation_preflight_succeeded=0
  for endpoint in "${RELAY_ENDPOINT_LINES[@]}"; do
    endpoint_host="${endpoint%%$'\t'*}"
    endpoint_port="${endpoint##*$'\t'}"
    echo "Checking relay allocation API at $endpoint_host:$endpoint_port"
    if check_relay_allocation "$endpoint_host" "$endpoint_port" "$ALLOCATION_TOKEN" 5; then
      allocation_preflight_succeeded=1
      echo "Relay allocation preflight succeeded at $endpoint_host:$endpoint_port"
      break
    fi
    echo "Relay allocation preflight failed at $endpoint_host:$endpoint_port; trying the next endpoint if available." >&2
  done
  if [[ "$allocation_preflight_succeeded" != "1" ]]; then
    echo "Relay allocation preflight failed for every configured endpoint." >&2
    echo "A QR-only different-network pairing cannot proceed until at least one relay/bootstrap endpoint is reachable and returns allocation fields." >&2
    exit 1
  fi
fi

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "OK: relay/bootstrap preflight passed."
  if [[ "$USE_LEGACY_RELAY" == "1" ]]; then
    echo "Legacy relay mode was statically validated; allocation API was skipped because relay id/secret were supplied manually."
  else
    echo "At least one configured endpoint accepted AETHERLINK_RELAY allocate and returned route material."
  fi
  exit 0
fi

echo "Starting AetherLink Runtime on local diagnostic port $PORT"
if [[ "$USE_ENDPOINT_LIST" == "1" ]]; then
  echo "Relay bootstrap endpoints: $RELAY_ENDPOINTS"
else
  echo "Relay route: $RELAY_HOST:$RELAY_PORT"
fi
if [[ "$USE_LEGACY_RELAY" == "1" ]]; then
  echo "Legacy relay frame secret is set and will be embedded in the development pairing QR."
else
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    export AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN="$ALLOCATION_TOKEN"
  fi
  echo "Runtime will request relay route material from the allocation service before printing the pairing QR."
fi
echo "Scan the printed relay QR payload in AetherLink, or use the GUI Pairing panel when running the app runtime."

LOCAL_AGENT_BRIDGE_PORT="$PORT" ./script/run_runtime_dev_server.sh
