#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LOCAL_AGENT_BRIDGE_PORT:-43170}"
RELAY_HOST="${AETHERLINK_BOOTSTRAP_RELAY_HOST:-${AETHERLINK_RELAY_HOST:-}}"
RELAY_PORT="${AETHERLINK_BOOTSTRAP_RELAY_PORT:-${AETHERLINK_RELAY_PORT:-43171}}"
RELAY_ENDPOINTS="${AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS:-}"
ALLOCATION_TOKEN="${AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN:-${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}}"
PREFLIGHT_SUMMARY_JSON="${AETHERLINK_PREFLIGHT_SUMMARY_JSON:-}"
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
                         then exit before starting RuntimeDevServer. The
                         allocation probe is marked preflight so it does not
                         persist a throwaway relay lease in the bootstrap relay
                         store.
  --summary-json <path>  Write structured relay/bootstrap preflight status.
                         This is useful for no-ADB or different-network QA logs.
  --allocation-token <token>
                         Send an allocation token to the development relay.
                         Required when the relay was started with
                         --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN,
                         and when --start-local-relay advertises a non-loopback
                         relay host that requires a wildcard bind.
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
    --summary-json)
      shift
      PREFLIGHT_SUMMARY_JSON="${1:-}"
      if [[ -z "$PREFLIGHT_SUMMARY_JSON" ]]; then
        echo "--summary-json requires a value." >&2
        exit 2
      fi
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
    if address.is_link_local or address.is_multicast:
        return "link_local"
    if address.is_private:
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
    elif kind == "link_local" and not allow_local:
        print(
            f"Invalid different-network relay endpoint {host}:{port}: link-local and multicast addresses cannot be used as QR relay routes, even with --allow-private-relay. Use a public/VPN/tunnel relay, or a private overlay address that both devices can reach.",
            file=sys.stderr,
        )
        failed = True
    elif kind == "private" and not allow_private and not allow_local:
        print(
            f"Invalid different-network relay endpoint {host}:{port}: private addresses usually do not cross unrelated networks. Use a public/VPN/tunnel relay, or pass --allow-private-relay only for an explicit private overlay reachable by the runtime host and trusted device.",
            file=sys.stderr,
        )
        failed = True

if failed:
    raise SystemExit(2)
PY
}

RELAY_PID=""
PREFLIGHT_SUCCESS_ENDPOINT=""
PREFLIGHT_REQUIRED_FIELDS_PRESENT=0
PREFLIGHT_FAILURE_DETAIL=""

write_preflight_summary() {
  local exit_status="$1"
  local endpoint_payload
  [[ -n "$PREFLIGHT_SUMMARY_JSON" ]] || return 0
  endpoint_payload="$(printf '%s\n' "${RELAY_ENDPOINT_LINES[@]}")"
  python3 - \
    "$PREFLIGHT_SUMMARY_JSON" \
    "$exit_status" \
    "$PREFLIGHT_ONLY" \
    "$START_LOCAL_RELAY" \
    "$ALLOW_PRIVATE_RELAY" \
    "$USE_LEGACY_RELAY" \
    "$PREFLIGHT_SUCCESS_ENDPOINT" \
    "$PREFLIGHT_REQUIRED_FIELDS_PRESENT" \
    "$PREFLIGHT_FAILURE_DETAIL" \
    "$endpoint_payload" <<'PY'
import datetime as dt
import json
import os
import sys

(
    summary_path,
    exit_status,
    preflight_only,
    start_local_relay,
    allow_private_relay,
    use_legacy_relay,
    success_endpoint,
    required_fields_present,
    failure_detail,
    endpoint_payload,
) = sys.argv[1:]

endpoints = []
for line in endpoint_payload.splitlines():
    if not line.strip():
        continue
    host, port = line.split("\t", 1)
    endpoints.append({"host": host, "port": int(port)})

caveats = ["runtime_host_preflight_only_not_phone_reachability_proof"]
if start_local_relay == "1":
    caveats.append("local_relay_only_unless_advertised_host_is_public_vpn_tunnel_or_overlay")
if use_legacy_relay == "1":
    caveats.append("legacy_manual_relay_allocation_not_checked")
if failure_detail.strip():
    caveats.append("relay_bootstrap_preflight_failed")

summary = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "exit_status": int(exit_status),
    "mode": {
        "preflight_only": preflight_only == "1",
    },
    "relay": {
        "endpoints": endpoints,
        "success_endpoint": success_endpoint or None,
        "start_local_relay": start_local_relay == "1",
        "allow_private_relay": allow_private_relay == "1",
    },
    "allocation": {
        "required_fields_present": required_fields_present == "1",
        "preflight_non_persistent": use_legacy_relay != "1",
        "legacy_allocation_skipped": use_legacy_relay == "1",
    },
    "failure_detail": failure_detail.strip() or None,
    "caveats": caveats,
}

directory = os.path.dirname(summary_path)
if directory:
    os.makedirs(directory, exist_ok=True)
with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

set +e
scope_validation_output="$(validate_relay_endpoint_scope "$ALLOW_PRIVATE_RELAY" "$START_LOCAL_RELAY" "${RELAY_ENDPOINT_LINES[@]}" 2>&1)"
scope_validation_status=$?
set -e
if [[ "$scope_validation_status" -ne 0 ]]; then
  PREFLIGHT_FAILURE_DETAIL="$scope_validation_output"
  if [[ -n "$scope_validation_output" ]]; then
    printf '%s\n' "$scope_validation_output" >&2
  fi
  write_preflight_summary "$scope_validation_status"
  exit "$scope_validation_status"
fi

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
cleanup() {
  if [[ -n "$RELAY_PID" ]]; then
    kill "$RELAY_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$ROOT_DIR"

local_relay_bind_host() {
  python3 - "$1" <<'PY'
import ipaddress
import sys

raw = sys.argv[1].strip()
host = raw.lower()
if host.startswith("[") and host.endswith("]"):
    host = host[1:-1]
if host in {"localhost", "localhost.", "::1"}:
    print(raw or "127.0.0.1")
    raise SystemExit(0)
try:
    address = ipaddress.ip_address(host)
except ValueError:
    print("0.0.0.0")
    raise SystemExit(0)
if address.is_loopback:
    print(host)
else:
    print("0.0.0.0")
PY
}

check_relay_allocation() {
  local host="$1"
  local port="$2"
  local token="$3"
  local timeout="${4:-5}"
  local args=(
    python3 script/relay_allocation_preflight.py
    --host "$host"
    --port "$port"
    --timeout "$timeout"
    --quiet
  )
  if [[ -n "$token" ]]; then
    args+=(--allocation-token "$token")
  fi
  "${args[@]}"
}

if [[ "$START_LOCAL_RELAY" == "1" ]]; then
  LOCAL_RELAY_BIND_HOST="$(local_relay_bind_host "$FIRST_RELAY_HOST")"
  if [[ "$LOCAL_RELAY_BIND_HOST" == "0.0.0.0" && -z "$ALLOCATION_TOKEN" ]]; then
    echo "--start-local-relay with a non-loopback advertised relay host must pass --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN." >&2
    exit 2
  fi
  echo "Starting local development relay on $LOCAL_RELAY_BIND_HOST:$FIRST_RELAY_PORT"
  echo "This is only cross-network reachable if $FIRST_RELAY_HOST:$FIRST_RELAY_PORT reaches the runtime host."
  swift build --product AetherLinkRelay >/dev/null
  RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
  RELAY_ARGS=("$RELAY_BIN" --host "$LOCAL_RELAY_BIND_HOST" --port "$FIRST_RELAY_PORT")
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
    set +e
    allocation_preflight_output="$(check_relay_allocation "$endpoint_host" "$endpoint_port" "$ALLOCATION_TOKEN" 5 2>&1)"
    allocation_preflight_status=$?
    set -e
    if [[ "$allocation_preflight_status" -eq 0 ]]; then
      allocation_preflight_succeeded=1
      PREFLIGHT_SUCCESS_ENDPOINT="$endpoint_host:$endpoint_port"
      PREFLIGHT_REQUIRED_FIELDS_PRESENT=1
      echo "Relay allocation preflight succeeded at $endpoint_host:$endpoint_port"
      break
    fi
    PREFLIGHT_FAILURE_DETAIL="$allocation_preflight_output"
    if [[ -n "$allocation_preflight_output" ]]; then
      printf '%s\n' "$allocation_preflight_output" >&2
    fi
    echo "Relay allocation preflight failed at $endpoint_host:$endpoint_port; trying the next endpoint if available." >&2
  done
  if [[ "$allocation_preflight_succeeded" != "1" ]]; then
    echo "Relay allocation preflight failed for every configured endpoint." >&2
    echo "A QR-only different-network pairing cannot proceed until at least one relay/bootstrap endpoint is reachable and returns allocation fields." >&2
    write_preflight_summary 1
    exit 1
  fi
else
  PREFLIGHT_SUCCESS_ENDPOINT="$FIRST_RELAY_HOST:$FIRST_RELAY_PORT"
fi

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "OK: relay/bootstrap preflight passed."
  if [[ "$USE_LEGACY_RELAY" == "1" ]]; then
    echo "Legacy relay mode was statically validated; allocation API was skipped because relay id/secret were supplied manually."
  else
    echo "At least one configured endpoint accepted AETHERLINK_RELAY allocate and returned route material."
  fi
  write_preflight_summary 0
  exit 0
fi

write_preflight_summary 0

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
