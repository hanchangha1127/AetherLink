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
REQUIRE_MANUAL_NETWORK_CONFIRMATION=0
WORK_DIR=""
QR_PNG_PATH=""
PORT="${LOCAL_AGENT_BRIDGE_PORT:-}"
SELF_TEST_UNVERIFIED_QR_SUMMARY=0
SELF_TEST_EVIDENCE_CORRELATION=0
SELF_TEST_OWNED_PROCESS_CLEANUP="${AETHERLINK_OWNED_PROCESS_CLEANUP_SELF_TEST:-0}"

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
  - Relay readiness probes are marked preflight=1 so they do not persist
    throwaway relay leases in the relay store.

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
                        --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN,
                        and when --start-local-relay advertises a non-loopback
                        relay host that requires a wildcard bind.
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
  --require-manual-network-confirmation
                        Before waiting for the device, require an interactive
                        DIFFERENT_NETWORK or CELLULAR confirmation so a local
                        artifact run cannot be mistaken for cross-network proof.

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
    --require-manual-network-confirmation)
      REQUIRE_MANUAL_NETWORK_CONFIRMATION=1
      shift
      ;;
    --self-test-unverified-qr-summary)
      SELF_TEST_UNVERIFIED_QR_SUMMARY=1
      shift
      ;;
    --self-test-evidence-correlation)
      SELF_TEST_EVIDENCE_CORRELATION=1
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

if [[ "$SELF_TEST_OWNED_PROCESS_CLEANUP" == "1" ]]; then
  RELAY_HOST="127.0.0.1"
  RELAY_PORT="43171"
elif [[ "$SELF_TEST_EVIDENCE_CORRELATION" == "1" ]]; then
  RELAY_HOST="127.0.0.1"
  RELAY_PORT="43171"
elif [[ "$SELF_TEST_UNVERIFIED_QR_SUMMARY" == "1" && -z "$RELAY_HOST" ]]; then
  RELAY_HOST="127.0.0.1"
fi

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
if [[ "$START_LOCAL_RELAY" != "1" \
  && "$SELF_TEST_UNVERIFIED_QR_SUMMARY" != "1" \
  && "$SELF_TEST_EVIDENCE_CORRELATION" != "1" \
  && "$SELF_TEST_OWNED_PROCESS_CLEANUP" != "1" ]]; then
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
    --route-token-prefix aetherlink-no-adb-preflight
    --quiet
  )
  if [[ -n "$token" ]]; then
    AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN="$token" \
      AETHERLINK_RELAY_ALLOCATION_TOKEN="$token" \
      "${args[@]}"
  else
    "${args[@]}"
  fi
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

refresh_correlated_evidence_state() {
  local runtime_log="$1"
  local state_file="$2"
  local expected_run_id="$3"
  local expected_route_evidence_id="$4"
  python3 - "$runtime_log" "$state_file" "$expected_run_id" "$expected_route_evidence_id" <<'PY'
import json
import os
import re
import sys

runtime_log, state_file, expected_run_id, expected_route_id = sys.argv[1:]

state = {
    "correlation_valid": False,
    "failure_reason": None,
    "run_anchor_present": False,
    "route_anchor_present": False,
    "runtime_waiting_for_peer": False,
    "relay_ready": False,
    "pairing_accepted": False,
    "runtime_health": False,
    "runtime_health_count": 0,
    "reconnect_transition": False,
    "reconnect_ready": False,
    "trusted_device_reconnect": False,
    "same_run_route_session_sequence": False,
}

run_marker = re.compile(
    r"^\[smoke\] evidence run_start run_id=([0-9a-f]{32})$"
)
route_marker = re.compile(
    r"^\[smoke\] evidence route_anchor run_id=([0-9a-f]{32}) "
    r"route_evidence_id=([0-9a-f]{64})$"
)
received_health = re.compile(
    r"^\[runtime\] relay received type=runtime\.health request_id=(\S+)$"
)
sent_health = re.compile(
    r"^\[runtime\] sending type=runtime\.health request_id=(\S+)$"
)

def finish():
    os.makedirs(os.path.dirname(os.path.abspath(state_file)), exist_ok=True)
    temporary = state_file + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, state_file)

if not re.fullmatch(r"[0-9a-f]{32}", expected_run_id):
    state["failure_reason"] = "invalid_expected_run_id"
    finish()
    raise SystemExit(0)
if not re.fullmatch(r"[0-9a-f]{64}", expected_route_id):
    state["failure_reason"] = "route_anchor_not_generated"
    finish()
    raise SystemExit(0)

try:
    with open(runtime_log, encoding="utf-8", errors="replace") as handle:
        lines = [line.rstrip("\r\n") for line in handle]
except FileNotFoundError:
    lines = []

run_markers = [
    (index, match.group(1))
    for index, line in enumerate(lines)
    if (match := run_marker.fullmatch(line)) is not None
]
matching_runs = [index for index, run_id in run_markers if run_id == expected_run_id]
if len(matching_runs) != 1:
    state["failure_reason"] = (
        "run_anchor_missing" if not matching_runs else "run_anchor_duplicated"
    )
    finish()
    raise SystemExit(0)

run_index = matching_runs[0]
state["run_anchor_present"] = True
if any(index > run_index for index, _ in run_markers):
    state["failure_reason"] = "run_anchor_superseded"
    finish()
    raise SystemExit(0)

route_markers = [
    (index, match.group(1), match.group(2))
    for index, line in enumerate(lines)
    if index > run_index and (match := route_marker.fullmatch(line)) is not None
]
matching_routes = [
    index
    for index, run_id, route_id in route_markers
    if run_id == expected_run_id and route_id == expected_route_id
]
if len(matching_routes) != 1:
    state["failure_reason"] = (
        "route_anchor_missing" if not route_markers else "route_anchor_mismatch"
    )
    finish()
    raise SystemExit(0)
if len(route_markers) != 1:
    state["failure_reason"] = "route_anchor_superseded"
    finish()
    raise SystemExit(0)

route_index = matching_routes[0]
state["route_anchor_present"] = True
state["correlation_valid"] = True
state["runtime_waiting_for_peer"] = any(
    "[runtime] relay status=waiting_for_peer" in line
    for line in lines[run_index + 1 :]
)

phase = "await_ready"
pending_initial_health = set()
pending_reconnect_health = set()
initial_health_request_id = None
ambiguous_pairing = False
repaired_after_health = False

for line in lines[route_index + 1 :]:
    if "[runtime] relay status=ready" in line:
        if phase == "await_ready":
            state["relay_ready"] = True
            phase = "await_pairing"
        elif phase == "await_reconnect_ready" and state["reconnect_transition"]:
            state["reconnect_ready"] = True
            phase = "await_reconnect_health"
        continue

    if "[runtime] Development pairing accepted" in line:
        if phase == "await_pairing":
            state["pairing_accepted"] = True
            phase = "await_initial_health"
        elif state["pairing_accepted"] and initial_health_request_id is None:
            ambiguous_pairing = True
        elif initial_health_request_id is not None:
            repaired_after_health = True
        continue

    received = received_health.fullmatch(line)
    if received is not None:
        request_id = received.group(1)
        if phase == "await_initial_health":
            pending_initial_health.add(request_id)
        elif phase == "await_reconnect_health" and request_id != initial_health_request_id:
            pending_reconnect_health.add(request_id)
        continue

    sent = sent_health.fullmatch(line)
    if sent is not None:
        request_id = sent.group(1)
        if phase == "await_initial_health" and request_id in pending_initial_health:
            initial_health_request_id = request_id
            state["runtime_health"] = True
            state["runtime_health_count"] = 1
            state["same_run_route_session_sequence"] = True
            phase = "await_reconnect_transition"
        elif (
            phase == "await_reconnect_health"
            and request_id in pending_reconnect_health
            and request_id != initial_health_request_id
            and not repaired_after_health
        ):
            state["runtime_health_count"] = 2
            state["trusted_device_reconnect"] = True
            phase = "complete"
        continue

    if phase == "await_reconnect_transition" and (
        "[runtime] relay status=reconnecting" in line
        or "[runtime] relay status=connecting" in line
        or "[runtime] relay status=waiting_for_peer" in line
    ):
        state["reconnect_transition"] = True
        phase = "await_reconnect_ready"

if ambiguous_pairing:
    state.update(
        correlation_valid=False,
        failure_reason="ambiguous_pairing_sequence",
        pairing_accepted=False,
        runtime_health=False,
        runtime_health_count=0,
        reconnect_transition=False,
        reconnect_ready=False,
        trusted_device_reconnect=False,
        same_run_route_session_sequence=False,
    )
elif repaired_after_health:
    state["trusted_device_reconnect"] = False

finish()
PY
}

correlated_evidence_field_is_true() {
  local state_file="$1"
  local field="$2"
  python3 - "$state_file" "$field" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    state = json.load(handle)
raise SystemExit(0 if state.get(sys.argv[2]) is True else 1)
PY
}

correlated_evidence_failure_reason() {
  local state_file="$1"
  python3 - "$state_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    state = json.load(handle)
print(state.get("failure_reason") or "incomplete_correlated_sequence")
PY
}

wait_for_correlated_evidence() {
  local field="$1"
  local description="$2"
  local timeout="$3"
  local timeout_label="${4:-$description}"
  local start
  start="$(date +%s)"
  while true; do
    refresh_correlated_evidence_state \
      "$RUNTIME_LOG" \
      "$EVIDENCE_STATE_FILE" \
      "$EVIDENCE_RUN_ID" \
      "$EVIDENCE_ROUTE_ID"
    if correlated_evidence_field_is_true "$EVIDENCE_STATE_FILE" "$field"; then
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      local reason
      reason="$(correlated_evidence_failure_reason "$EVIDENCE_STATE_FILE")"
      echo "Timed out waiting for '$timeout_label' in correlated run/route/session evidence; expected $description (reason=$reason)." >&2
      return 1
    fi
    sleep 0.25
  done
}

compute_route_evidence_id() {
  local run_id="$1"
  local pairing_uri="$2"
  python3 - "$run_id" "$pairing_uri" <<'PY'
import hashlib
import hmac
import sys
import urllib.parse

run_id, pairing_uri = sys.argv[1:]
parsed = urllib.parse.urlparse(pairing_uri)
pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
names = [name for name, _ in pairs]
if len(names) != len(set(names)):
    raise SystemExit("Pairing URI contains duplicate query keys")
query = dict(pairs)

def required(*names):
    for name in names:
        value = query.get(name)
        if value:
            return value
    raise SystemExit("Pairing URI is missing evidence correlation material")

material = "\0".join(
    (
        required("pairing_nonce", "nonce", "n"),
        required("runtime_device_id", "mac_device_id", "device_id", "rid"),
        required("relay_id", "remote_id", "route_id", "network_id", "ri"),
        required("relay_nonce", "remote_nonce", "route_nonce", "rendezvous_nonce", "rrn"),
    )
).encode("utf-8")
print(hmac.new(bytes.fromhex(run_id), material, hashlib.sha256).hexdigest())
PY
}

assert_correlated_evidence_state() {
  local state_file="$1"
  local field="$2"
  local expected_json="$3"
  python3 - "$state_file" "$field" "$expected_json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    state = json.load(handle)
expected = json.loads(sys.argv[3])
actual = state.get(sys.argv[2])
if actual != expected:
    raise SystemExit(
        f"evidence self-test mismatch for {sys.argv[2]}: "
        f"expected {expected!r}, got {actual!r}"
    )
PY
}

run_evidence_correlation_self_test() {
  local run_id="11111111111111111111111111111111"
  local route_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  local other_run_id="22222222222222222222222222222222"
  local other_route_id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  local duplicate_query_uri="aetherlink://pair?pairing_nonce=first&pairing_nonce=second&runtime_device_id=runtime&relay_id=relay&relay_nonce=nonce"
  if compute_route_evidence_id "$run_id" "$duplicate_query_uri" >/dev/null 2>&1; then
    echo "Evidence correlation accepted a duplicate pairing query key." >&2
    return 1
  fi

  printf '%s\n' \
    "[smoke] evidence run_start run_id=$other_run_id" \
    "[smoke] evidence route_anchor run_id=$other_run_id route_evidence_id=$other_route_id" \
    "[runtime] relay status=ready" \
    "[runtime] Development pairing accepted for device_id=stale-device name=stale" \
    "[runtime] relay received type=runtime.health request_id=stale-health" \
    "[runtime] sending type=runtime.health request_id=stale-health" \
    "[smoke] evidence run_start run_id=$run_id" \
    "[runtime] relay status=waiting_for_peer" \
    "[smoke] evidence route_anchor run_id=$run_id route_evidence_id=$route_id" \
    >"$RUNTIME_LOG"
  refresh_correlated_evidence_state "$RUNTIME_LOG" "$EVIDENCE_STATE_FILE" "$run_id" "$route_id"
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" correlation_valid true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" same_run_route_session_sequence false
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" runtime_health_count 0

  printf '%s\n' \
    "[smoke] evidence run_start run_id=$run_id" \
    "[runtime] relay status=waiting_for_peer" \
    "[smoke] evidence route_anchor run_id=$run_id route_evidence_id=$other_route_id" \
    "[runtime] relay status=ready" \
    "[runtime] Development pairing accepted for device_id=mismatch-device name=mismatch" \
    "[runtime] relay received type=runtime.health request_id=mismatch-health" \
    "[runtime] sending type=runtime.health request_id=mismatch-health" \
    >"$RUNTIME_LOG"
  refresh_correlated_evidence_state "$RUNTIME_LOG" "$EVIDENCE_STATE_FILE" "$run_id" "$route_id"
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" correlation_valid false
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" failure_reason '"route_anchor_mismatch"'
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" same_run_route_session_sequence false

  printf '%s\n' \
    "[smoke] evidence run_start run_id=$run_id" \
    "[runtime] relay status=waiting_for_peer" \
    "[smoke] evidence route_anchor run_id=$run_id route_evidence_id=$route_id" \
    "[runtime] relay status=ready" \
    "[runtime] Development pairing accepted for device_id=old-run-device name=old-run" \
    "[runtime] relay received type=runtime.health request_id=old-run-health" \
    "[runtime] sending type=runtime.health request_id=old-run-health" \
    "[smoke] evidence run_start run_id=$other_run_id" \
    >"$RUNTIME_LOG"
  refresh_correlated_evidence_state "$RUNTIME_LOG" "$EVIDENCE_STATE_FILE" "$run_id" "$route_id"
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" correlation_valid false
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" failure_reason '"run_anchor_superseded"'
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" same_run_route_session_sequence false

  printf '%s\n' \
    "[smoke] evidence run_start run_id=$run_id" \
    "[runtime] relay status=waiting_for_peer" \
    "[smoke] evidence route_anchor run_id=$run_id route_evidence_id=$route_id" \
    "[runtime] relay status=ready" \
    "[runtime] Development pairing accepted for device_id=same-request-device name=same-request" \
    "[runtime] relay received type=runtime.health request_id=health-one" \
    "[runtime] sending type=runtime.health request_id=health-one" \
    "[runtime] relay status=reconnecting" \
    "[runtime] relay status=connecting" \
    "[runtime] relay status=waiting_for_peer" \
    "[runtime] relay status=ready" \
    "[runtime] relay received type=runtime.health request_id=health-one" \
    "[runtime] sending type=runtime.health request_id=health-one" \
    >"$RUNTIME_LOG"
  refresh_correlated_evidence_state "$RUNTIME_LOG" "$EVIDENCE_STATE_FILE" "$run_id" "$route_id"
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" same_run_route_session_sequence true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" runtime_health_count 1
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" trusted_device_reconnect false

  printf '%s\n' \
    "[smoke] evidence run_start run_id=$run_id" \
    "[runtime] relay status=waiting_for_peer" \
    "[smoke] evidence route_anchor run_id=$run_id route_evidence_id=$route_id" \
    "[runtime] relay status=ready" \
    "[runtime] Development pairing accepted for device_id=current-device name=current" \
    "[runtime] relay received type=runtime.health request_id=health-one" \
    "[runtime] sending type=runtime.health request_id=health-one" \
    "[runtime] relay status=reconnecting" \
    "[runtime] relay status=connecting" \
    "[runtime] relay status=waiting_for_peer" \
    "[runtime] relay status=ready" \
    "[runtime] relay received type=runtime.health request_id=health-two" \
    "[runtime] sending type=runtime.health request_id=health-two" \
    >"$RUNTIME_LOG"
  refresh_correlated_evidence_state "$RUNTIME_LOG" "$EVIDENCE_STATE_FILE" "$run_id" "$route_id"
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" correlation_valid true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" runtime_waiting_for_peer true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" relay_ready true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" pairing_accepted true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" runtime_health true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" runtime_health_count 2
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" reconnect_transition true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" reconnect_ready true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" trusted_device_reconnect true
  assert_correlated_evidence_state "$EVIDENCE_STATE_FILE" same_run_route_session_sequence true

  EVIDENCE_RUN_ID="$run_id"
  EVIDENCE_ROUTE_ID="$route_id"
  EXPECT_RECONNECT=1
  write_summary 0
  python3 - "$SUMMARY_FILE" "$run_id" "$route_id" <<'PY'
import json
import sys

summary_path, expected_run_id, expected_route_id = sys.argv[1:]
with open(summary_path, encoding="utf-8") as handle:
    summary = json.load(handle)
coverage = summary["coverage"]
assert summary["mode"]["evidence_correlation_self_test"] is True
assert coverage["evidence_correlation_fixture_verified"] is True
for field in (
    "runtime_host_relay_registration",
    "runtime_host_waiting_for_peer",
    "trusted_device_relay_reachability",
    "trusted_device_pairing",
    "trusted_device_runtime_health",
    "trusted_device_reconnect",
    "same_run_route_session_correlation",
    "reconnect_same_run_route_session_correlation",
    "full_run_trusted_device_proof",
    "external_network_relay_verified",
    "production_relay",
):
    assert coverage[field] is False, (field, coverage[field])
observed = summary["observed"]
assert observed["evidence_run_id"] == expected_run_id
assert observed["route_evidence_id"] == expected_route_id
assert observed["runtime_health_count"] == 2
serialized = json.dumps(summary, sort_keys=True)
for raw_fixture_value in ("current-device", "health-one", "health-two"):
    assert raw_fixture_value not in serialized
PY

  echo "Correlated evidence no-network self-test passed."
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

pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
names = [name for name, _ in pairs]
if len(names) != len(set(names)):
    raise SystemExit("Pairing URI contains duplicate query keys")
query = dict(pairs)
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
SUMMARY_FILE="$WORK_DIR/summary.json"
EVIDENCE_STATE_FILE="$WORK_DIR/evidence-state.json"
EVIDENCE_RUN_ID="$(python3 - <<'PY'
import secrets

print(secrets.token_hex(16))
PY
)"
EVIDENCE_ROUTE_ID=""
if [[ "$SELF_TEST_EVIDENCE_CORRELATION" == "1" \
  || "$SELF_TEST_OWNED_PROCESS_CLEANUP" == "1" ]]; then
  PORT="${PORT:-1}"
else
  PORT="${PORT:-$(free_port)}"
fi
PAIRING_TTL_SECONDS="${PAIRING_TTL_SECONDS:-$(( TIMEOUT_SECONDS + 180 ))}"
RUNTIME_PID=""
RELAY_PID=""
RELAY_SUPERVISOR_PID=""
RELAY_PID_FILE="$WORK_DIR/relay-child.pid"
RELAY_SUPERVISOR_START_TIME=""
RELAY_SUPERVISOR_COMMAND=""
RELAY_START_TIME=""
RELAY_COMMAND=""
RELAY_ORIGINAL_PARENT_PID=""
QR_ROUND_TRIP_VERIFIED=0
NETWORK_CONFIRMED=0

capture_relay_process_snapshot() {
  local pid="$1"
  local parent_variable="$2"
  local start_variable="$3"
  local command_variable="$4"
  local state_variable="$5"
  local captured_parent_pid
  local captured_start_time
  local captured_command_line
  local captured_state
  local confirmed_start_time
  local confirmed_command_line

  captured_parent_pid="$(ps -ww -o ppid= -p "$pid" 2>/dev/null)" || return 1
  captured_start_time="$(ps -ww -o lstart= -p "$pid" 2>/dev/null)" || return 1
  captured_command_line="$(ps -ww -o command= -p "$pid" 2>/dev/null)" || return 1
  captured_state="$(ps -ww -o state= -p "$pid" 2>/dev/null)" || return 1
  confirmed_start_time="$(ps -ww -o lstart= -p "$pid" 2>/dev/null)" || return 1
  confirmed_command_line="$(ps -ww -o command= -p "$pid" 2>/dev/null)" || return 1

  captured_parent_pid="${captured_parent_pid//[[:space:]]/}"
  captured_start_time="${captured_start_time#"${captured_start_time%%[![:space:]]*}"}"
  confirmed_start_time="${confirmed_start_time#"${confirmed_start_time%%[![:space:]]*}"}"
  captured_command_line="${captured_command_line#"${captured_command_line%%[![:space:]]*}"}"
  confirmed_command_line="${confirmed_command_line#"${confirmed_command_line%%[![:space:]]*}"}"
  captured_state="${captured_state//[[:space:]]/}"

  [[ "$captured_parent_pid" =~ ^[0-9]+$ ]] || return 1
  [[ -n "$captured_start_time" && "$captured_start_time" == "$confirmed_start_time" ]] || return 1
  [[ -n "$captured_command_line" && "$captured_command_line" == "$confirmed_command_line" ]] || return 1
  [[ -n "$captured_state" && "$captured_state" != Z* ]] || return 1

  printf -v "$parent_variable" '%s' "$captured_parent_pid"
  printf -v "$start_variable" '%s' "$captured_start_time"
  printf -v "$command_variable" '%s' "$captured_command_line"
  printf -v "$state_variable" '%s' "$captured_state"
}

relay_process_matches_identity() {
  local pid="$1"
  local expected_start_time="$2"
  local expected_command_line="$3"
  local parent_pid
  local start_time
  local command_line
  local state

  [[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1
  [[ -n "$expected_start_time" && -n "$expected_command_line" ]] || return 1
  capture_relay_process_snapshot \
    "$pid" parent_pid start_time command_line state || return 1
  [[ "$start_time" == "$expected_start_time" ]] \
    && [[ "$command_line" == "$expected_command_line" ]]
}

record_supervised_relay_process() {
  local expected_child_command="$1"
  local supervisor_parent_pid=""
  local supervisor_start_time=""
  local supervisor_command_line=""
  local supervisor_state=""
  local child_parent_pid=""
  local child_start_time=""
  local child_command_line=""
  local child_state=""
  local attempt

  for attempt in {1..100}; do
    capture_relay_process_snapshot \
      "$RELAY_SUPERVISOR_PID" \
      supervisor_parent_pid \
      supervisor_start_time \
      supervisor_command_line \
      supervisor_state || true
    capture_relay_process_snapshot \
      "$RELAY_PID" \
      child_parent_pid \
      child_start_time \
      child_command_line \
      child_state || true
    if [[ "$supervisor_parent_pid" == "$$" ]] \
      && [[ "$child_parent_pid" == "$RELAY_SUPERVISOR_PID" ]] \
      && [[ "$child_command_line" == *"$expected_child_command"* ]]; then
      RELAY_SUPERVISOR_START_TIME="$supervisor_start_time"
      RELAY_SUPERVISOR_COMMAND="$supervisor_command_line"
      RELAY_START_TIME="$child_start_time"
      RELAY_COMMAND="$child_command_line"
      RELAY_ORIGINAL_PARENT_PID="$RELAY_SUPERVISOR_PID"
      return 0
    fi
    if [[ -n "$child_start_time" \
      && "$child_command_line" == *"$expected_child_command"* ]] \
      && ! kill -0 "$RELAY_SUPERVISOR_PID" >/dev/null 2>&1; then
      RELAY_START_TIME="$child_start_time"
      RELAY_COMMAND="$child_command_line"
      RELAY_ORIGINAL_PARENT_PID="$RELAY_SUPERVISOR_PID"
      return 1
    fi
    sleep 0.05
  done
  return 1
}

terminate_recorded_relay_child_if_identical() {
  local child_pid="$1"
  local child_start_time="$2"
  local child_command_line="$3"
  local child_original_parent_pid="$4"
  local supervisor_pid="$5"
  local remaining_checks=60

  [[ "$child_pid" != "$$" && "$child_pid" != "$PPID" ]] || return 0
  [[ "$child_original_parent_pid" == "$supervisor_pid" ]] || return 0
  if ! relay_process_matches_identity \
    "$child_pid" "$child_start_time" "$child_command_line"; then
    return 0
  fi

  kill -TERM "$child_pid" >/dev/null 2>&1 || true
  while relay_process_matches_identity \
    "$child_pid" "$child_start_time" "$child_command_line" \
    && ((remaining_checks > 0)); do
    sleep 0.05
    remaining_checks=$((remaining_checks - 1))
  done
  if relay_process_matches_identity \
    "$child_pid" "$child_start_time" "$child_command_line"; then
    kill -KILL "$child_pid" >/dev/null 2>&1 || true
  fi

  remaining_checks=40
  while relay_process_matches_identity \
    "$child_pid" "$child_start_time" "$child_command_line" \
    && ((remaining_checks > 0)); do
    sleep 0.05
    remaining_checks=$((remaining_checks - 1))
  done
}

stop_and_reap_relay_supervisor_if_identical() {
  local supervisor_pid="$1"
  local supervisor_start_time="$2"
  local supervisor_command_line="$3"
  local term_remaining_checks=60
  local kill_remaining_checks=40

  kill -TERM "$supervisor_pid" >/dev/null 2>&1 || true
  while relay_process_matches_identity \
    "$supervisor_pid" "$supervisor_start_time" "$supervisor_command_line" \
    && ((term_remaining_checks > 0)); do
    sleep 0.05
    term_remaining_checks=$((term_remaining_checks - 1))
  done
  if relay_process_matches_identity \
    "$supervisor_pid" "$supervisor_start_time" "$supervisor_command_line"; then
    kill -KILL "$supervisor_pid" >/dev/null 2>&1 || true
  fi
  while relay_process_matches_identity \
    "$supervisor_pid" "$supervisor_start_time" "$supervisor_command_line" \
    && ((kill_remaining_checks > 0)); do
    sleep 0.05
    kill_remaining_checks=$((kill_remaining_checks - 1))
  done
  if ! relay_process_matches_identity \
    "$supervisor_pid" "$supervisor_start_time" "$supervisor_command_line"; then
    wait "$supervisor_pid" >/dev/null 2>&1 || true
  fi
}

cleanup_recorded_relay_process() {
  local supervisor_pid="$RELAY_SUPERVISOR_PID"
  local supervisor_start_time="$RELAY_SUPERVISOR_START_TIME"
  local supervisor_command_line="$RELAY_SUPERVISOR_COMMAND"
  local child_pid="$RELAY_PID"
  local child_start_time="$RELAY_START_TIME"
  local child_command_line="$RELAY_COMMAND"
  local child_original_parent_pid="$RELAY_ORIGINAL_PARENT_PID"
  local parent_pid=""
  local ignored_start_time=""
  local ignored_command_line=""
  local ignored_state=""
  local supervisor_was_identified=0

  if [[ -n "$supervisor_pid" ]]; then
    if [[ "$supervisor_pid" == "$$" || "$supervisor_pid" == "$PPID" ]]; then
      return 0
    fi
    if [[ -n "$supervisor_start_time" ]] \
      && relay_process_matches_identity \
        "$supervisor_pid" "$supervisor_start_time" "$supervisor_command_line" \
      && capture_relay_process_snapshot \
        "$supervisor_pid" parent_pid ignored_start_time ignored_command_line ignored_state \
      && [[ "$parent_pid" == "$$" ]]; then
      supervisor_was_identified=1
    elif [[ -z "$supervisor_start_time" ]] \
      && capture_relay_process_snapshot \
        "$supervisor_pid" parent_pid ignored_start_time ignored_command_line ignored_state \
      && [[ "$parent_pid" == "$$" ]] \
      && [[ "$ignored_command_line" == *"$ROOT_DIR/script/owned_process_supervisor.sh"* ]]; then
      supervisor_start_time="$ignored_start_time"
      supervisor_command_line="$ignored_command_line"
      supervisor_was_identified=1
    fi
    if ((supervisor_was_identified == 1)); then
      stop_and_reap_relay_supervisor_if_identical \
        "$supervisor_pid" "$supervisor_start_time" "$supervisor_command_line"
    fi
  fi
  if [[ -n "$child_pid" ]]; then
    terminate_recorded_relay_child_if_identical \
      "$child_pid" \
      "$child_start_time" \
      "$child_command_line" \
      "$child_original_parent_pid" \
      "$supervisor_pid"
  fi

  RELAY_SUPERVISOR_PID=""
  RELAY_PID=""
  RELAY_SUPERVISOR_START_TIME=""
  RELAY_SUPERVISOR_COMMAND=""
  RELAY_START_TIME=""
  RELAY_COMMAND=""
  RELAY_ORIGINAL_PARENT_PID=""
}

run_relay_cleanup_self_test() {
  local original_child_pid
  local original_child_start_time
  local original_child_command

  rm -f "$RELAY_PID_FILE"
  "$ROOT_DIR/script/owned_process_supervisor.sh" \
    --owner-pid "$$" \
    --pid-file "$RELAY_PID_FILE" \
    --grace-seconds 1 \
    -- /bin/sleep 30 \
    >"$RELAY_LOG" 2>&1 &
  RELAY_SUPERVISOR_PID="$!"
  for _ in {1..100}; do
    if [[ -s "$RELAY_PID_FILE" ]]; then
      RELAY_PID="$(<"$RELAY_PID_FILE")"
      break
    fi
    sleep 0.05
  done
  [[ "$RELAY_PID" =~ ^[1-9][0-9]*$ ]]
  record_supervised_relay_process /bin/sleep
  [[ "$RELAY_SUPERVISOR_PID" != "$$" && "$RELAY_SUPERVISOR_PID" != "$PPID" ]]
  [[ "$RELAY_PID" != "$$" && "$RELAY_PID" != "$PPID" ]]
  original_child_pid="$RELAY_PID"
  original_child_start_time="$RELAY_START_TIME"
  original_child_command="$RELAY_COMMAND"

  kill -KILL "$RELAY_SUPERVISOR_PID"
  wait "$RELAY_SUPERVISOR_PID" >/dev/null 2>&1 || true
  relay_process_matches_identity \
    "$RELAY_PID" "$original_child_start_time" "$original_child_command"
  terminate_recorded_relay_child_if_identical \
    "$RELAY_PID" \
    "$original_child_start_time" \
    "$original_child_command mismatched" \
    "$RELAY_ORIGINAL_PARENT_PID" \
    "$RELAY_SUPERVISOR_PID"
  relay_process_matches_identity \
    "$RELAY_PID" "$original_child_start_time" "$original_child_command"

  cleanup_recorded_relay_process
  if relay_process_matches_identity \
    "$original_child_pid" "$original_child_start_time" "$original_child_command"; then
    echo "Recorded relay child survived exact-identity parent cleanup." >&2
    return 1
  fi
  echo "No-ADB owned-process cleanup self-test passed."
}

if [[ "$SELF_TEST_OWNED_PROCESS_CLEANUP" == "1" ]]; then
  trap cleanup_recorded_relay_process EXIT
  run_relay_cleanup_self_test
  trap - EXIT
  exit 0
fi

start_evidence_run() {
  rm -f "$RELAY_LOG" "$EVIDENCE_STATE_FILE"
  printf '%s\n' \
    "[smoke] evidence run_start run_id=$EVIDENCE_RUN_ID" \
    >"$RUNTIME_LOG"
}

write_summary() {
  local exit_status="${1:-0}"
  [[ -n "${SUMMARY_FILE:-}" ]] || return 0
  refresh_correlated_evidence_state \
    "$RUNTIME_LOG" \
    "$EVIDENCE_STATE_FILE" \
    "$EVIDENCE_RUN_ID" \
    "$EVIDENCE_ROUTE_ID"
  python3 - \
    "$SUMMARY_FILE" \
    "$exit_status" \
    "$WORK_DIR" \
    "$RELAY_HOST" \
    "$RELAY_PORT" \
    "$START_LOCAL_RELAY" \
    "$EMIT_ONLY" \
    "$ALLOW_PRIVATE_RELAY" \
    "$EXPECT_RECONNECT" \
    "$RUNTIME_LOG" \
    "$RELAY_LOG" \
    "$PAIRING_URI_FILE" \
    "$PAIRING_QR_FILE" \
    "$QR_ROUND_TRIP_VERIFIED" \
    "$ALLOW_DIRECT_FALLBACK" \
    "$PRINT_URI" \
    "$REQUIRE_MANUAL_NETWORK_CONFIRMATION" \
    "$NETWORK_CONFIRMED" \
    "$SELF_TEST_UNVERIFIED_QR_SUMMARY" \
        "$SELF_TEST_EVIDENCE_CORRELATION" \
        "$EVIDENCE_STATE_FILE" \
        "$EVIDENCE_RUN_ID" \
        "$EVIDENCE_ROUTE_ID" <<'PY'
import datetime as dt
import json
import os
import re
import sys
import urllib.parse

(
    summary_path,
    exit_status,
    work_dir,
    relay_host,
    relay_port,
    start_local_relay,
    emit_only,
    allow_private_relay,
    expect_reconnect,
    runtime_log,
    relay_log,
    pairing_uri_file,
    pairing_qr_file,
    qr_round_trip_verified,
    allow_direct_fallback,
    print_uri,
    require_manual_network_confirmation,
    network_confirmed,
    self_test_unverified_qr_summary,
    self_test_evidence_correlation,
    evidence_state_file,
    evidence_run_id,
    route_evidence_id,
) = sys.argv[1:]

def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""

runtime_text = read(runtime_log)
relay_text = read(relay_log)
pairing_uri_text = read(pairing_uri_file).strip()
try:
    with open(evidence_state_file, encoding="utf-8") as handle:
        evidence = json.load(handle)
except (FileNotFoundError, json.JSONDecodeError, OSError):
    evidence = {}

def evidence_bool(field):
    return evidence.get(field) is True

health_count = evidence.get("runtime_health_count", 0)
if not isinstance(health_count, int) or isinstance(health_count, bool) or health_count < 0:
    health_count = 0
same_run_route_session_sequence = evidence_bool("same_run_route_session_sequence")
correlated_reconnect = evidence_bool("trusted_device_reconnect")
correlation_fixture_self_test = self_test_evidence_correlation == "1"
claimable_correlated_sequence = (
    same_run_route_session_sequence and not correlation_fixture_self_test
)
claimable_correlated_reconnect = correlated_reconnect and not correlation_fixture_self_test
runtime_log_artifact_present = os.path.exists(runtime_log)
relay_log_artifact_present = os.path.exists(relay_log)
pairing_uri_artifact_present = os.path.exists(pairing_uri_file)
pairing_qr_artifact_present = os.path.exists(pairing_qr_file)
qr_route_artifact_verified = qr_round_trip_verified == "1"

def pairing_uri_queries(text):
    marker = "AETHERLINK_DEV_PAIRING_URI "
    for line in text.splitlines():
        if marker not in line:
            continue
        query = pairing_uri_query(line.split(marker, 1)[1].strip())
        if query:
            yield query

def pairing_uri_query(uri):
    parsed = urllib.parse.urlparse(uri.strip())
    if parsed.scheme == "aetherlink" and parsed.netloc == "pair":
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        names = [name for name, _ in pairs]
        if len(names) == len(set(names)):
            return dict(pairs)
    return {}

def has_any(query, *names):
    return any(query.get(name) for name in names)

def has_temporary_pairing_material(query):
    return (
        has_any(query, "pairing_nonce", "nonce", "n")
        and has_any(query, "pairing_code", "code", "c")
    )

def has_complete_relay_route_material(query):
    return (
        has_any(query, "relay_host", "remote_host", "route_host", "rendezvous_host", "rh")
        and has_any(query, "relay_port", "remote_port", "route_port", "rendezvous_port", "rp")
        and has_any(query, "relay_id", "remote_id", "route_id", "network_id", "ri")
        and has_any(query, "relay_secret", "remote_secret", "route_secret", "rs")
        and has_any(query, "relay_expires_at", "remote_expires_at", "route_expires_at", "rendezvous_expires_at", "rx")
        and has_any(query, "relay_nonce", "remote_nonce", "route_nonce", "rendezvous_nonce", "rrn")
    )

def relay_log_contains_temporary_secret_material(text):
    patterns = (
        r"AETHERLINK_DEV_PAIRING_URI",
        r"aetherlink://pair",
        r"\b(?:pairing_nonce|pairing_code|relay_secret|remote_secret|route_secret|relay_nonce|remote_nonce|route_nonce|rendezvous_nonce|route_token|discovery_token|allocation_token|requested_route_token)\b",
        r"(?:^|[?&\s])(?:n|c|rs|rrn|rt)=",
    )
    return any(re.search(pattern, text) for pattern in patterns)

runtime_pairing_queries = list(pairing_uri_queries(runtime_text))
pairing_uri_query_from_file = pairing_uri_query(pairing_uri_text)
relay_log_relay_ids = re.findall(r"\brelay_id=([^\s]+)", relay_text)
relay_log_relay_ids_shortened = bool(relay_log_relay_ids) and all("..." in relay_id for relay_id in relay_log_relay_ids)
relay_log_contains_secret_material = relay_log_contains_temporary_secret_material(relay_text)
relay_log_contains_unshortened_long_relay_id = any(len(relay_id) > 12 and "..." not in relay_id for relay_id in relay_log_relay_ids)
relay_log_contains_unredacted_route_material = relay_log_contains_secret_material or relay_log_contains_unshortened_long_relay_id
runtime_log_contains_temporary_pairing_material = any(has_temporary_pairing_material(query) for query in runtime_pairing_queries)
runtime_log_contains_temporary_route_material = any(has_complete_relay_route_material(query) for query in runtime_pairing_queries)
pairing_uri_contains_temporary_pairing_material = pairing_uri_artifact_present and qr_route_artifact_verified
pairing_qr_contains_temporary_pairing_material = pairing_qr_artifact_present and qr_route_artifact_verified
terminal_output_contains_temporary_pairing_material = print_uri == "1" and has_temporary_pairing_material(pairing_uri_query_from_file)
terminal_output_contains_temporary_route_material = print_uri == "1" and has_complete_relay_route_material(pairing_uri_query_from_file)
summary = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "exit_status": int(exit_status),
    "work_dir": work_dir,
    "relay": {
        "host": relay_host,
        "port": int(relay_port),
        "start_local_relay": start_local_relay == "1",
        "allow_private_relay": allow_private_relay == "1",
    },
    "mode": {
        "emit_only": emit_only == "1",
        "expect_reconnect": expect_reconnect == "1",
        "print_uri": print_uri == "1",
        "require_manual_network_confirmation": require_manual_network_confirmation == "1",
        "evidence_correlation_self_test": correlation_fixture_self_test,
    },
    "artifacts": {
        "runtime_log": runtime_log if runtime_log_artifact_present else None,
        "relay_log": relay_log if relay_log_artifact_present else None,
        "pairing_uri": pairing_uri_file if pairing_uri_artifact_present else None,
        "pairing_qr": pairing_qr_file if pairing_qr_artifact_present else None,
        "evidence_state": evidence_state_file if os.path.exists(evidence_state_file) else None,
    },
    "coverage": {
        "runtime_host_relay_registration": (
            evidence_bool("runtime_waiting_for_peer") and not correlation_fixture_self_test
        ),
        "runtime_host_waiting_for_peer": (
            evidence_bool("runtime_waiting_for_peer") and not correlation_fixture_self_test
        ),
        "trusted_device_relay_reachability": (
            evidence_bool("relay_ready") and not correlation_fixture_self_test
        ),
        "trusted_device_pairing": (
            evidence_bool("pairing_accepted") and not correlation_fixture_self_test
        ),
        "trusted_device_runtime_health": (
            evidence_bool("runtime_health") and not correlation_fixture_self_test
        ),
        "trusted_device_reconnect": (
            expect_reconnect == "1" and claimable_correlated_reconnect
        ),
        "same_run_route_session_correlation": claimable_correlated_sequence,
        "reconnect_same_run_route_session_correlation": (
            expect_reconnect == "1" and claimable_correlated_reconnect
        ),
        "evidence_correlation_fixture_verified": (
            correlation_fixture_self_test
            and same_run_route_session_sequence
            and correlated_reconnect
        ),
        "optical_qr_scan": False,
        "external_network_operator_confirmed": network_confirmed == "1",
        "full_run_trusted_device_proof": (
            emit_only != "1"
            and claimable_correlated_sequence
        ),
        "external_network_relay_verified": (
            start_local_relay != "1"
            and emit_only != "1"
            and network_confirmed == "1"
            and claimable_correlated_sequence
        ),
        "production_relay": False,
        "production_session_key_exchange": False,
        "production_end_to_end_transport_encryption": False,
        "runtime_log_artifact_present": runtime_log_artifact_present,
        "runtime_log_contains_temporary_pairing_material": runtime_log_contains_temporary_pairing_material,
        "runtime_log_contains_temporary_route_material": runtime_log_contains_temporary_route_material,
        "relay_log_artifact_present": relay_log_artifact_present,
        "relay_log_relay_ids_shortened": relay_log_relay_ids_shortened,
        "relay_log_omits_temporary_secret_material": relay_log_artifact_present and not relay_log_contains_secret_material,
        "relay_log_contains_temporary_secret_material": relay_log_contains_secret_material,
        "relay_log_contains_unredacted_route_material": relay_log_contains_unredacted_route_material,
        "pairing_uri_artifact_present": pairing_uri_artifact_present,
        "pairing_qr_artifact_present": pairing_qr_artifact_present,
        "pairing_uri_contains_temporary_pairing_material": pairing_uri_contains_temporary_pairing_material,
        "pairing_qr_contains_temporary_pairing_material": pairing_qr_contains_temporary_pairing_material,
        "pairing_uri_contains_temporary_route_material": pairing_uri_artifact_present and qr_route_artifact_verified,
        "pairing_qr_contains_temporary_route_material": pairing_qr_artifact_present and qr_route_artifact_verified,
        "terminal_output_contains_temporary_pairing_material": terminal_output_contains_temporary_pairing_material,
        "terminal_output_contains_temporary_route_material": terminal_output_contains_temporary_route_material,
        "pairing_qr_round_trip_verified": qr_route_artifact_verified,
        "emit_only_qr_artifact_summary_verified": emit_only == "1" and pairing_uri_artifact_present and pairing_qr_artifact_present and qr_route_artifact_verified,
        "unverified_qr_artifact_self_test": self_test_unverified_qr_summary == "1",
        "relay_route_required": True,
        "direct_endpoint_forbidden": allow_direct_fallback != "1",
        "artifact_only_emit_mode": emit_only == "1",
    },
    "observed": {
        "evidence_run_id": evidence_run_id,
        "route_evidence_id": route_evidence_id or None,
        "correlation_valid": evidence_bool("correlation_valid"),
        "correlation_failure_reason": evidence.get("failure_reason"),
        "run_anchor_present": evidence_bool("run_anchor_present"),
        "route_anchor_present": evidence_bool("route_anchor_present"),
        "runtime_waiting_for_peer": evidence_bool("runtime_waiting_for_peer"),
        "relay_ready": evidence_bool("relay_ready"),
        "pairing_accepted": evidence_bool("pairing_accepted"),
        "runtime_health_count": health_count,
        "runtime_health_succeeded": evidence_bool("runtime_health"),
        "reconnect_transition": evidence_bool("reconnect_transition"),
        "reconnect_ready": evidence_bool("reconnect_ready"),
        "relay_runtime_registered": evidence_bool("runtime_waiting_for_peer"),
        "relay_client_registered": evidence_bool("relay_ready"),
    },
}

caveats = []
if runtime_log_contains_temporary_pairing_material or runtime_log_contains_temporary_route_material:
    caveats.append("runtime_log_contains_temporary_pairing_or_route_material")
if relay_log_contains_secret_material:
    caveats.append("relay_log_contains_temporary_secret_material")
if relay_log_artifact_present and (not relay_log_relay_ids_shortened or relay_log_contains_unredacted_route_material):
    caveats.append("relay_log_redaction_not_verified")
if pairing_uri_contains_temporary_pairing_material or pairing_qr_contains_temporary_pairing_material:
    caveats.append("manual_scan_qr_artifacts_contain_temporary_pairing_material")
if terminal_output_contains_temporary_pairing_material or terminal_output_contains_temporary_route_material:
    caveats.append("terminal_output_contains_temporary_pairing_or_route_material")
if qr_route_artifact_verified and (pairing_uri_artifact_present or pairing_qr_artifact_present):
    caveats.append("manual_scan_qr_artifacts_contain_temporary_route_material")
elif pairing_uri_artifact_present or pairing_qr_artifact_present:
    caveats.append("manual_scan_qr_artifacts_not_verified_as_route_material")
if emit_only == "1":
    caveats.append("artifact_only_emit_mode")
if correlation_fixture_self_test:
    caveats.append("no_network_evidence_correlation_fixture_only")
caveats.append("not_production_session_key_exchange_proof")
caveats.append("not_production_end_to_end_transport_encryption_proof")
if emit_only != "1" and network_confirmed != "1":
    caveats.append("external_network_operator_confirmation_missing")
if start_local_relay == "1":
    caveats.append("local_relay_only_unless_advertised_host_is_public_vpn_tunnel_or_overlay")
if route_evidence_id and not evidence_bool("correlation_valid"):
    caveats.append("run_route_evidence_correlation_failed")
if "relay status=ready" in runtime_text and not evidence_bool("relay_ready"):
    caveats.append("uncorrelated_relay_ready_ignored")
if "Development pairing accepted" in runtime_text and not evidence_bool("pairing_accepted"):
    caveats.append("uncorrelated_pairing_acceptance_ignored")
if "runtime.health" in runtime_text and not evidence_bool("runtime_health"):
    caveats.append("uncorrelated_or_unsuccessful_runtime_health_ignored")
if evidence_bool("runtime_waiting_for_peer") and not evidence_bool("relay_ready"):
    caveats.append("runtime_reached_relay_but_trusted_device_did_not_join")
if evidence_bool("relay_ready") and not evidence_bool("pairing_accepted"):
    caveats.append("relay_matched_but_pairing_not_accepted")
summary["caveats"] = caveats

with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

start_evidence_run

if [[ "$SELF_TEST_EVIDENCE_CORRELATION" == "1" ]]; then
  run_evidence_correlation_self_test
  exit 0
fi

if [[ "$SELF_TEST_UNVERIFIED_QR_SUMMARY" == "1" ]]; then
  EMIT_ONLY=1
  printf '%s\n' "aetherlink://pair?self_test=unverified_qr_summary&relay_host=$RELAY_HOST&relay_port=$RELAY_PORT" >"$PAIRING_URI_FILE"
  printf '%s\n' "self-test unverified QR artifact placeholder" >"$PAIRING_QR_FILE"
  : >"$RELAY_LOG"
  QR_ROUND_TRIP_VERIFIED=0
  write_summary 0
  echo "Summary: $SUMMARY_FILE"
  exit 0
fi

cleanup() {
  local exit_status=$?
  write_summary "$exit_status" >/dev/null 2>&1 || true
  if [[ -n "$RUNTIME_PID" ]]; then
    kill "$RUNTIME_PID" >/dev/null 2>&1 || true
    wait "$RUNTIME_PID" >/dev/null 2>&1 || true
  fi
  cleanup_recorded_relay_process
}
trap cleanup EXIT

echo "Working directory: $WORK_DIR"

if [[ "$START_LOCAL_RELAY" == "1" ]]; then
  LOCAL_RELAY_BIND_HOST="$(local_relay_bind_host "$RELAY_HOST")"
  if [[ "$LOCAL_RELAY_BIND_HOST" == "0.0.0.0" && -z "$ALLOCATION_TOKEN" ]]; then
    echo "--start-local-relay with a non-loopback advertised relay host must pass --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN." >&2
    exit 2
  fi
  echo "Starting allocation-required relay on $LOCAL_RELAY_BIND_HOST:$RELAY_PORT"
  swift build --product AetherLinkRelay >/dev/null
  RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
  RELAY_ARGS=(
    "$RELAY_BIN"
    --host "$LOCAL_RELAY_BIND_HOST"
    --port "$RELAY_PORT"
    --require-allocation
    --allocation-store "$WORK_DIR/relay-allocations.json"
  )
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    export AETHERLINK_RELAY_ALLOCATION_TOKEN="$ALLOCATION_TOKEN"
  fi
  rm -f "$RELAY_PID_FILE"
  "$ROOT_DIR/script/owned_process_supervisor.sh" \
    --owner-pid "$$" \
    --pid-file "$RELAY_PID_FILE" \
    -- "${RELAY_ARGS[@]}" \
    >"$RELAY_LOG" 2>&1 &
  RELAY_SUPERVISOR_PID="$!"
  for _ in {1..100}; do
    if [[ -s "$RELAY_PID_FILE" ]]; then
      RELAY_PID="$(<"$RELAY_PID_FILE")"
      break
    fi
    if ! kill -0 "$RELAY_SUPERVISOR_PID" >/dev/null 2>&1; then
      wait "$RELAY_SUPERVISOR_PID" >/dev/null 2>&1 || true
      echo "Local relay supervisor exited before recording its child PID." >&2
      exit 1
    fi
    sleep 0.05
  done
  if ! [[ "$RELAY_PID" =~ ^[1-9][0-9]*$ ]]; then
    echo "Local relay supervisor did not record a valid child PID." >&2
    exit 1
  fi
  if ! record_supervised_relay_process "$RELAY_BIN"; then
    echo "Local relay child identity could not be bound to its recorded supervisor." >&2
    exit 1
  fi
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
  "$RUNTIME_BIN" >>"$RUNTIME_LOG" 2>&1 &
RUNTIME_PID="$!"

wait_for_log "$RUNTIME_LOG" "AETHERLINK_DEV_PAIRING_URI" 20
PAIRING_URI="$(extract_pairing_uri "$RUNTIME_LOG")"
validate_pairing_uri "$PAIRING_URI" "$RELAY_HOST" "$RELAY_PORT"
EVIDENCE_ROUTE_ID="$(compute_route_evidence_id "$EVIDENCE_RUN_ID" "$PAIRING_URI")"
printf '%s\n' \
  "[smoke] evidence route_anchor run_id=$EVIDENCE_RUN_ID route_evidence_id=$EVIDENCE_ROUTE_ID" \
  >>"$RUNTIME_LOG"
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
QR_ROUND_TRIP_VERIFIED=1
echo "Pairing QR PNG: $PAIRING_QR_FILE"
if [[ "$OPEN_QR" == "1" ]]; then
  open "$PAIRING_QR_FILE" >/dev/null 2>&1 || true
fi
echo "Runtime log: $RUNTIME_LOG"
echo "Summary: $SUMMARY_FILE"
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

if [[ "$REQUIRE_MANUAL_NETWORK_CONFIRMATION" == "1" ]]; then
  echo "Manual network confirmation is required before waiting for the trusted device."
  echo "Confirm that the Android device is not using the same local network path as the runtime host, and that no adb reverse/tether tunnel is being used for the relay route."
  read -r -p "Type DIFFERENT_NETWORK or CELLULAR to continue: " NETWORK_CONFIRMATION
  if [[ "$NETWORK_CONFIRMATION" != "DIFFERENT_NETWORK" && "$NETWORK_CONFIRMATION" != "CELLULAR" ]]; then
    echo "Network confirmation failed; refusing to wait for a result that could be mistaken for cross-network evidence." >&2
    exit 2
  fi
  NETWORK_CONFIRMED=1
fi

echo "Waiting up to ${TIMEOUT_SECONDS}s for relay match, pairing acceptance, and runtime.health..."
wait_for_correlated_evidence \
  same_run_route_session_sequence \
  "relay-ready, pairing-accepted, and successful runtime.health sequence" \
  "$TIMEOUT_SECONDS" \
  "relay status=ready"

echo "OK: no-ADB external relay pairing smoke observed relay ready, pairing accepted, and runtime.health."
if [[ "$EXPECT_RECONNECT" == "1" ]]; then
  echo "Reconnect phase: fully close and reopen AetherLink on the trusted device, or tap reconnect."
  echo "Waiting up to ${TIMEOUT_SECONDS}s for a new relay-ready transition and successful runtime.health from the saved trusted relay route..."
  wait_for_correlated_evidence \
    trusted_device_reconnect \
    "saved-route reconnect transition and distinct successful runtime.health" \
    "$TIMEOUT_SECONDS"
  echo "OK: no-ADB external relay reconnect smoke observed a correlated second runtime.health."
fi
echo "Runtime log: $RUNTIME_LOG"
if [[ -f "$RELAY_LOG" ]]; then
  echo "Relay log: $RELAY_LOG"
fi
