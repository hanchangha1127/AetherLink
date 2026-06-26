#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELAY_HOST="${AETHERLINK_BOOTSTRAP_RELAY_HOST:-}"
RELAY_PORT="${AETHERLINK_BOOTSTRAP_RELAY_PORT:-43171}"
ALLOCATION_TOKEN="${AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN:-${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}}"
TIMEOUT_SECONDS=180
PAIRING_TTL_SECONDS=""
START_LOCAL_RELAY=0
EMIT_ONLY=0
PRINT_URI=0
OPEN_QR=0
USE_MOCK_BACKEND=1
ALLOW_DIRECT_FALLBACK=0
ALLOW_PRIVATE_RELAY=0
EXPECT_RECONNECT=0
WORK_DIR=""
QR_PNG_PATH=""
PORT="${LOCAL_AGENT_BRIDGE_PORT:-}"

usage() {
  cat <<'USAGE'
Usage:
  script/no_adb_external_relay_pairing_smoke.sh --relay-host <host> [--relay-port <port>] [--timeout <seconds>]
  script/no_adb_external_relay_pairing_smoke.sh --relay-host <host> --emit-only

Runs a no-ADB development pairing smoke for different-network QR routing.

The script starts RuntimeDevServer with AETHERLINK_BOOTSTRAP_RELAY_* allocation,
prints and saves the compact pairing URI when available, writes a QR PNG with
repo-local Swift/CoreImage fallback, then waits for a trusted device to use that
QR or URI through optical QR scan or the app's diagnostics payload input. It never
installs the Android app, injects an intent, reads logcat, or configures adb
reverse.

Requirements:
  - <host>:<port> must run an allocation-capable AetherLinkRelay reachable by
    both the runtime host and the trusted device.
  - Use script/run_allocation_relay.sh on a user-controlled public, VPN, tunnel,
    DNS, or future private-overlay route name. Do not expose Ollama or LM Studio.

Options:
  --start-local-relay   Start AetherLinkRelay on the runtime host. This only proves
                        no-ADB behavior across networks if <host>:<port> reaches
                        the runtime host through your public/VPN/tunnel route.
  --emit-only           Generate and save the pairing URI, then exit without
                        waiting for a trusted device.
  --work-dir <dir>      Store runtime logs, trusted devices, and pairing URI in
                        a specific directory.
  --runtime-port <port> Use a specific local RuntimeDevServer port.
  --allocation-token <token>
                        Send an allocation token to the development relay.
                        Required when the relay was started with
                        --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN.
  --pairing-ttl <sec>   Override the development pairing TTL.
  --qr-png <path>       Write the QR PNG to a specific path.
  --open-qr             Open the QR PNG after generation.
  --print-uri           Print the full pairing URI. This exposes temporary
                        pairing and relay secrets in terminal scrollback.
  --real-backend        Use the real model provider aggregate instead of the mock
                        provider. The trusted device still never talks to
                        Ollama or LM Studio directly.
  --allow-direct-fallback
                        Allow an explicit mixed-route diagnostic QR that carries
                        direct host/port in addition to relay route material.
  --allow-private-relay Allow a private/CGNAT relay address only when a
                        user-controlled VPN, tunnel, or private overlay makes
                        it reachable from both devices.
  --expect-reconnect    After the first runtime.health succeeds, keep the runtime
                        and relay running and wait for a second runtime.health.
                        Use this for no-ADB proof that the trusted device can
                        reconnect from its saved QR route after app restart or
                        explicit reconnect.

Success criteria without --emit-only:
  - Runtime reaches relay status=waiting_for_peer.
  - Client joins relay and runtime logs relay status=ready.
  - Runtime logs Development pairing accepted.
  - Runtime logs runtime.health.
  - With --expect-reconnect, runtime logs a second runtime.health after the
    initial pairing health check.

USAGE
}

validate_remote_relay_host_for_qr() {
  local host="$1"
  local allow_private="$2"
  python3 - "$host" "$allow_private" <<'PY'
import ipaddress
import sys

raw_host = sys.argv[1]
allow_private = sys.argv[2] == "1"
host = raw_host.strip().lower()
if host.startswith("[") and host.endswith("]"):
    host = host[1:-1]

if host in {"localhost", "0", "0.0.0.0", "::", "::1"} or host.endswith(".local"):
    print(
        "--relay-host must be reachable from the trusted device network; "
        "loopback, wildcard, and .local hosts are invalid unless "
        "--start-local-relay is used for local diagnostics.",
        file=sys.stderr,
    )
    raise SystemExit(2)

try:
    ip = ipaddress.ip_address(host)
except ValueError:
    raise SystemExit(0)

if (
    ip.is_loopback
    or ip.is_unspecified
    or ip.is_link_local
    or ip.is_multicast
    or ip.is_private
    or ip in ipaddress.ip_network("100.64.0.0/10")
):
    if (
        allow_private
        and not (ip.is_loopback or ip.is_unspecified or ip.is_link_local or ip.is_multicast)
        and (ip.is_private or ip in ipaddress.ip_network("100.64.0.0/10"))
    ):
        raise SystemExit(0)
    print(
        "--relay-host must be a public, VPN/tunnel, DNS, or future "
        "private-overlay route name reachable from the trusted device network; "
        "private, link-local, CGNAT, loopback, and multicast IP literals are "
        "invalid unless --allow-private-relay is set for an explicit private overlay "
        "or --start-local-relay is used for local diagnostics.",
        file=sys.stderr,
    )
    raise SystemExit(2)
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --relay-host)
      if [[ $# -lt 2 ]]; then
        echo "--relay-host requires a value." >&2
        exit 2
      fi
      RELAY_HOST="$2"
      shift 2
      ;;
    --relay-port)
      if [[ $# -lt 2 ]]; then
        echo "--relay-port requires a value." >&2
        exit 2
      fi
      RELAY_PORT="$2"
      shift 2
      ;;
    --timeout)
      if [[ $# -lt 2 ]]; then
        echo "--timeout requires a value." >&2
        exit 2
      fi
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --pairing-ttl)
      if [[ $# -lt 2 ]]; then
        echo "--pairing-ttl requires a value." >&2
        exit 2
      fi
      PAIRING_TTL_SECONDS="$2"
      shift 2
      ;;
    --runtime-port)
      if [[ $# -lt 2 ]]; then
        echo "--runtime-port requires a value." >&2
        exit 2
      fi
      PORT="$2"
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
    --start-local-relay)
      START_LOCAL_RELAY=1
      shift
      ;;
    --emit-only)
      EMIT_ONLY=1
      shift
      ;;
    --work-dir)
      if [[ $# -lt 2 ]]; then
        echo "--work-dir requires a value." >&2
        exit 2
      fi
      WORK_DIR="$2"
      shift 2
      ;;
    --qr-png)
      if [[ $# -lt 2 ]]; then
        echo "--qr-png requires a value." >&2
        exit 2
      fi
      QR_PNG_PATH="$2"
      shift 2
      ;;
    --open-qr)
      OPEN_QR=1
      shift
      ;;
    --print-uri)
      PRINT_URI=1
      shift
      ;;
    --real-backend)
      USE_MOCK_BACKEND=0
      shift
      ;;
    --allow-direct-fallback)
      ALLOW_DIRECT_FALLBACK=1
      shift
      ;;
    --allow-private-relay)
      ALLOW_PRIVATE_RELAY=1
      shift
      ;;
    --expect-reconnect)
      EXPECT_RECONNECT=1
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

if [[ -z "$RELAY_HOST" ]]; then
  echo "Missing --relay-host. The relay host must be reachable from both devices." >&2
  usage >&2
  exit 2
fi

if [[ "$RELAY_HOST" == *"://"* || "$RELAY_HOST" == *"/"* || "$RELAY_HOST" == *"@"* || "$RELAY_HOST" == *"?"* || "$RELAY_HOST" == *"#"* ]]; then
  echo "--relay-host must be a host or IP address, not a URL." >&2
  exit 2
fi

NORMALIZED_RELAY_HOST="$(printf '%s' "$RELAY_HOST" | tr '[:upper:]' '[:lower:]')"
if [[ "$START_LOCAL_RELAY" != "1" ]]; then
  validate_remote_relay_host_for_qr "$NORMALIZED_RELAY_HOST" "$ALLOW_PRIVATE_RELAY"
fi

if ! [[ "$RELAY_PORT" =~ ^[0-9]+$ ]] || (( RELAY_PORT < 1 || RELAY_PORT > 65535 )); then
  echo "Invalid relay port: $RELAY_PORT" >&2
  exit 2
fi

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 1 )); then
  echo "Invalid timeout: $TIMEOUT_SECONDS" >&2
  exit 2
fi

if [[ -n "$PAIRING_TTL_SECONDS" ]] && (! [[ "$PAIRING_TTL_SECONDS" =~ ^[0-9]+$ ]] || (( PAIRING_TTL_SECONDS < 1 ))); then
  echo "Invalid pairing TTL: $PAIRING_TTL_SECONDS" >&2
  exit 2
fi

if [[ -n "$PORT" ]] && (! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 ))); then
  echo "Invalid runtime port: $PORT" >&2
  exit 2
fi

cd "$ROOT_DIR"

free_port() {
  python3 - <<'PY'
import socket

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
}

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
route_token = f"aetherlink-no-adb-preflight-{uuid.uuid4()}"
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

wait_for_log() {
  local file="$1"
  local pattern="$2"
  local timeout="$3"
  local start
  start="$(date +%s)"
  while true; do
    if [[ -f "$file" ]] && grep -q "$pattern" "$file"; then
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for '$pattern' in $file" >&2
      return 1
    fi
    sleep 0.25
  done
}

log_match_count() {
  local file="$1"
  local pattern="$2"
  if [[ ! -f "$file" ]]; then
    echo 0
    return
  fi
  grep -c "$pattern" "$file" || true
}

wait_for_log_count_greater_than() {
  local file="$1"
  local pattern="$2"
  local previous_count="$3"
  local timeout="$4"
  local start
  start="$(date +%s)"
  while true; do
    local count
    count="$(log_match_count "$file" "$pattern")"
    if (( count > previous_count )); then
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for another '$pattern' in $file; count stayed at $previous_count" >&2
      return 1
    fi
    sleep 0.25
  done
}

extract_pairing_uri() {
  local file="$1"
  python3 - "$file" <<'PY'
import sys

marker = "AETHERLINK_DEV_PAIRING_URI "
compact_marker = "AETHERLINK_DEV_PAIRING_COMPACT_URI "
compact_uri = None
canonical_uri = None
for line in open(sys.argv[1], encoding="utf-8"):
    if compact_marker in line:
        compact_uri = line.split(compact_marker, 1)[1].strip()
    elif marker in line:
        canonical_uri = line.split(marker, 1)[1].strip()
if compact_uri:
    print(compact_uri)
    raise SystemExit(0)
if canonical_uri:
    print(canonical_uri)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

validate_pairing_uri() {
  local uri="$1"
  local expected_host="$2"
  local expected_port="$3"
  python3 - "$uri" "$expected_host" "$expected_port" "$ALLOW_DIRECT_FALLBACK" <<'PY'
import sys
import urllib.parse

uri = sys.argv[1]
expected_host = sys.argv[2]
expected_port = sys.argv[3]
allow_direct_fallback = sys.argv[4] == "1"
parsed = urllib.parse.urlparse(uri)
if parsed.scheme != "aetherlink" or parsed.netloc != "pair":
    raise SystemExit("Pairing URI must use aetherlink://pair")

query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
def q(*names):
    for name in names:
        value = query.get(name)
        if value:
            return value
    return None

required = [
    ("version", "v"),
    ("pairing_nonce", "nonce", "n"),
    ("pairing_code", "code", "c"),
    ("runtime_device_id", "mac_device_id", "device_id", "rid"),
    ("runtime_name", "mac_name", "name", "rn"),
    ("runtime_public_key", "mac_public_key", "public_key", "rk"),
    ("runtime_key_fingerprint", "fingerprint", "cert_fingerprint", "rf"),
    ("route_token", "discovery_token", "rt"),
    ("relay_host", "remote_host", "route_host", "rendezvous_host", "rh"),
    ("relay_port", "remote_port", "route_port", "rendezvous_port", "rp"),
    ("relay_id", "remote_id", "route_id", "network_id", "ri"),
    ("relay_secret", "remote_secret", "route_secret", "rs"),
    ("relay_expires_at", "remote_expires_at", "route_expires_at", "rendezvous_expires_at", "rx"),
    ("relay_nonce", "remote_nonce", "route_nonce", "rendezvous_nonce", "rrn"),
]
missing = [names[0] for names in required if q(*names) is None]
if missing:
    raise SystemExit(f"Pairing URI missing required field(s): {', '.join(missing)}")
has_direct_host = q("host", "runtime_host", "h") is not None
has_direct_port = q("port", "runtime_port", "p") is not None
if (has_direct_host or has_direct_port) and not allow_direct_fallback:
    raise SystemExit("External relay pairing URI must not include direct host/port fields")
if allow_direct_fallback and has_direct_host != has_direct_port:
    raise SystemExit("Mixed-route pairing URI must include both direct host and direct port")
if allow_direct_fallback and has_direct_port:
    try:
        direct_port = int(q("port", "runtime_port", "p"))
    except ValueError:
        raise SystemExit("Mixed-route pairing URI contains invalid direct port")
    if direct_port < 1 or direct_port > 65535:
        raise SystemExit("Mixed-route pairing URI direct port must be in 1..65535")
relay_host = q("relay_host", "remote_host", "route_host", "rendezvous_host", "rh")
relay_port = q("relay_port", "remote_port", "route_port", "rendezvous_port", "rp")
pairing_code = q("pairing_code", "code", "c")
relay_expires_at = q("relay_expires_at", "remote_expires_at", "route_expires_at", "rendezvous_expires_at", "rx")
if relay_host != expected_host:
    raise SystemExit(f"Pairing URI relay_host={relay_host!r} does not match {expected_host!r}")
if relay_port != expected_port:
    raise SystemExit(f"Pairing URI relay_port={relay_port!r} does not match {expected_port!r}")
if not pairing_code.isdigit() or len(pairing_code) != 6:
    raise SystemExit("Pairing URI contains invalid pairing_code")
try:
    expires_at = int(relay_expires_at)
except ValueError:
    raise SystemExit("Pairing URI contains invalid relay_expires_at")
if expires_at <= 0:
    raise SystemExit("Pairing URI relay_expires_at must be positive")
PY
}

if [[ -z "$WORK_DIR" ]]; then
  WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-adb-pairing.XXXXXX")"
else
  mkdir -p "$WORK_DIR"
fi
RUNTIME_LOG="$WORK_DIR/runtime.log"
RELAY_LOG="$WORK_DIR/relay.log"
TRUSTED_DEVICES_FILE="$WORK_DIR/trusted-devices.json"
RUNTIME_IDENTITY_FILE="$WORK_DIR/runtime-identity.json"
PAIRING_URI_FILE="$WORK_DIR/pairing-uri.txt"
PAIRING_QR_FILE="${QR_PNG_PATH:-$WORK_DIR/pairing-qr.png}"
PORT="${PORT:-$(free_port)}"
PAIRING_TTL_SECONDS="${PAIRING_TTL_SECONDS:-$(( TIMEOUT_SECONDS + 180 ))}"
RUNTIME_PID=""
RELAY_PID=""

cleanup() {
  if [[ -n "$RUNTIME_PID" ]]; then
    kill "$RUNTIME_PID" >/dev/null 2>&1 || true
    wait "$RUNTIME_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$RELAY_PID" ]]; then
    kill "$RELAY_PID" >/dev/null 2>&1 || true
    wait "$RELAY_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "Working directory: $WORK_DIR"

if [[ "$START_LOCAL_RELAY" == "1" ]]; then
  echo "Starting allocation-required relay on 0.0.0.0:$RELAY_PORT"
  swift build --product AetherLinkRelay >/dev/null
  RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
  RELAY_ARGS=("$RELAY_BIN" --host 0.0.0.0 --port "$RELAY_PORT" --require-allocation)
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    RELAY_ARGS+=(--allocation-token "$ALLOCATION_TOKEN")
  fi
  "${RELAY_ARGS[@]}" >"$RELAY_LOG" 2>&1 &
  RELAY_PID="$!"
  wait_for_log "$RELAY_LOG" "development relay listening" 10
  echo "Relay log: $RELAY_LOG"
fi

echo "Checking relay allocation API at $RELAY_HOST:$RELAY_PORT"
check_relay_allocation "$RELAY_HOST" "$RELAY_PORT" "$ALLOCATION_TOKEN" 5

echo "Building RuntimeDevServer"
swift build --product RuntimeDevServer >/dev/null
RUNTIME_BIN="$(swift build --show-bin-path)/RuntimeDevServer"

echo "Starting RuntimeDevServer for QR relay mode on local diagnostic port $PORT with bootstrap relay $RELAY_HOST:$RELAY_PORT"
RUNTIME_ENV=(
  "LOCAL_AGENT_BRIDGE_PORT=$PORT"
  "AETHERLINK_DEV_PAIRING=1"
  "AETHERLINK_DEV_PAIRING_TTL_SECONDS=$PAIRING_TTL_SECONDS"
  "AETHERLINK_DEV_TRUSTED_DEVICES_FILE=$TRUSTED_DEVICES_FILE"
  "AETHERLINK_DEV_RUNTIME_IDENTITY_FILE=$RUNTIME_IDENTITY_FILE"
  "AETHERLINK_DEV_DISABLE_BONJOUR=1"
  "AETHERLINK_BOOTSTRAP_RELAY_HOST=$RELAY_HOST"
  "AETHERLINK_BOOTSTRAP_RELAY_PORT=$RELAY_PORT"
)
if [[ -n "$ALLOCATION_TOKEN" ]]; then
  RUNTIME_ENV+=("AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN=$ALLOCATION_TOKEN")
fi
if [[ "$USE_MOCK_BACKEND" == "1" ]]; then
  RUNTIME_ENV+=("LOCAL_AGENT_BRIDGE_MOCK_BACKEND=1")
fi
env \
  "${RUNTIME_ENV[@]}" \
  "$RUNTIME_BIN" >"$RUNTIME_LOG" 2>&1 &
RUNTIME_PID="$!"

wait_for_log "$RUNTIME_LOG" "AETHERLINK_DEV_PAIRING_URI" 20
PAIRING_URI="$(extract_pairing_uri "$RUNTIME_LOG")"
validate_pairing_uri "$PAIRING_URI" "$RELAY_HOST" "$RELAY_PORT"
printf '%s\n' "$PAIRING_URI" >"$PAIRING_URI_FILE"

echo "Pairing URI: $PAIRING_URI_FILE"
if [[ "$PRINT_URI" == "1" ]]; then
  echo "WARNING: full pairing URI contains temporary pairing and relay secrets."
  echo "$PAIRING_URI"
fi
if command -v qrencode >/dev/null 2>&1; then
  mkdir -p "$(dirname "$PAIRING_QR_FILE")"
  qrencode -o "$PAIRING_QR_FILE" "$PAIRING_URI"
else
  ./script/render_pairing_qr.swift --input "$PAIRING_URI_FILE" --output "$PAIRING_QR_FILE"
fi
echo "Verifying QR PNG round-trip decode"
VERIFY_QR_ARGS=(
  --image "$PAIRING_QR_FILE"
  --expected "$PAIRING_URI_FILE"
  --require-relay-route
  --expected-relay-host "$RELAY_HOST"
  --expected-relay-port "$RELAY_PORT"
)
if [[ "$ALLOW_DIRECT_FALLBACK" != "1" ]]; then
  VERIFY_QR_ARGS+=(--forbid-direct-endpoint)
fi
if [[ "$START_LOCAL_RELAY" == "1" ]]; then
  VERIFY_QR_ARGS+=(--allow-local-relay)
fi
./script/verify_pairing_qr.swift "${VERIFY_QR_ARGS[@]}" >/dev/null
echo "Pairing QR PNG: $PAIRING_QR_FILE"
if [[ "$OPEN_QR" == "1" ]]; then
  open "$PAIRING_QR_FILE" >/dev/null 2>&1 || true
fi
echo "Runtime log: $RUNTIME_LOG"
echo "The URI file, QR image, and runtime log contain temporary pairing or relay secrets until the route expires."
if [[ "$START_LOCAL_RELAY" == "1" ]]; then
  echo "Local relay mode generated and verified the QR artifact only."
  echo "This is not proof of different-network reachability unless $RELAY_HOST:$RELAY_PORT is exposed through a public, VPN, tunnel, or private-overlay route that the trusted device can reach."
else
  echo "Scan the QR or paste the URI into AetherLink on a trusted device that can reach the configured relay route $RELAY_HOST:$RELAY_PORT."
fi

if [[ "$EMIT_ONLY" == "1" ]]; then
  echo "Emit-only mode complete."
  exit 0
fi

echo "Waiting up to ${TIMEOUT_SECONDS}s for relay match, pairing acceptance, and runtime.health..."
wait_for_log "$RUNTIME_LOG" "relay status=ready" "$TIMEOUT_SECONDS"
wait_for_log "$RUNTIME_LOG" "Development pairing accepted" "$TIMEOUT_SECONDS"
wait_for_log "$RUNTIME_LOG" "runtime.health" "$TIMEOUT_SECONDS"
INITIAL_HEALTH_COUNT="$(log_match_count "$RUNTIME_LOG" "runtime.health")"

echo "OK: no-ADB external relay pairing smoke observed relay ready, pairing accepted, and runtime.health."
if [[ "$EXPECT_RECONNECT" == "1" ]]; then
  echo "Reconnect phase: fully close and reopen AetherLink on the trusted device, or tap reconnect."
  echo "Waiting up to ${TIMEOUT_SECONDS}s for another runtime.health from the saved trusted relay route..."
  wait_for_log_count_greater_than "$RUNTIME_LOG" "runtime.health" "$INITIAL_HEALTH_COUNT" "$TIMEOUT_SECONDS"
  echo "OK: no-ADB external relay reconnect smoke observed a second runtime.health."
fi
echo "Runtime log: $RUNTIME_LOG"
if [[ -f "$RELAY_LOG" ]]; then
  echo "Relay log: $RELAY_LOG"
fi
