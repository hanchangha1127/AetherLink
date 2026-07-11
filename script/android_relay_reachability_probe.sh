#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB="${ADB:-$ANDROID_HOME/platform-tools/adb}"
HOST=""
PORT=""
RELAY_ID=""
SERIAL=""
TIMEOUT_SECONDS=5
JSON_PATH=""
INCLUDE_NETWORK_SUMMARY=0
RELAY_PROBE_SELF_TEST="${AETHERLINK_RELAY_PROBE_SELF_TEST:-0}"

usage() {
  cat <<'USAGE'
Usage:
  script/android_relay_reachability_probe.sh --host <relay-host> --port <relay-port> [--relay-id <relay-id>] [--timeout <seconds>] [--json <path>]

Checks whether a physically connected Android device can open a TCP connection
to an AetherLink relay endpoint without adb reverse. With --relay-id, it sends
AETHERLINK_RELAY probe <relay-id> from the device network and requires the relay
to report both a known route and a waiting runtime. This is a route diagnostic
only: it does not pair, authenticate, call AetherLink Runtime, or call Ollama or
LM Studio.

Options:
  --relay-id <relay-id>         Run the non-consuming AetherLink relay probe
                                instead of a TCP-connect-only check.
  --serial <adb-serial>          Use a specific adb device.
  --timeout <seconds>           TCP connect timeout used on the device.
  --json <path>                 Write a machine-readable reachability summary.
  --include-network-summary     Include a short dumpsys connectivity excerpt in
                                the JSON summary for QA evidence.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host|--relay-host)
      if [[ $# -lt 2 ]]; then
        echo "$1 requires a value." >&2
        exit 2
      fi
      HOST="$2"
      shift 2
      ;;
    --port|--relay-port)
      if [[ $# -lt 2 ]]; then
        echo "$1 requires a value." >&2
        exit 2
      fi
      PORT="$2"
      shift 2
      ;;
    --relay-id)
      if [[ $# -lt 2 ]]; then
        echo "--relay-id requires a value." >&2
        exit 2
      fi
      RELAY_ID="$2"
      shift 2
      ;;
    --serial)
      if [[ $# -lt 2 ]]; then
        echo "--serial requires a value." >&2
        exit 2
      fi
      SERIAL="$2"
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
    --json)
      if [[ $# -lt 2 ]]; then
        echo "--json requires a value." >&2
        exit 2
      fi
      JSON_PATH="$2"
      shift 2
      ;;
    --include-network-summary)
      INCLUDE_NETWORK_SUMMARY=1
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

if [[ -z "$HOST" || -z "$PORT" ]]; then
  echo "Missing --host/--port. The relay endpoint must be explicit." >&2
  usage >&2
  exit 2
fi

if [[ "$HOST" == -* || "$HOST" == *"://"* || "$HOST" == *"/"* || "$HOST" == *"@"* || "$HOST" == *"?"* || "$HOST" == *"#"* ]]; then
  echo "--host must be a host or IP address, not a URL." >&2
  exit 2
fi

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "--port must be an integer in 1..65535." >&2
  exit 2
fi

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 1 || TIMEOUT_SECONDS > 120 )); then
  echo "--timeout must be an integer in 1..120 seconds." >&2
  exit 2
fi

if [[ -n "$RELAY_ID" ]]; then
  if [[ "$RELAY_ID" == -* || "$RELAY_ID" == *[[:space:]]* ]]; then
    echo "--relay-id must be a non-empty relay token without whitespace." >&2
    exit 2
  fi
fi

if [[ ! -x "$ADB" ]]; then
  echo "adb not found at $ADB" >&2
  exit 2
fi

cd "$ROOT_DIR"

if [[ -n "$SERIAL" ]]; then
  DEVICE_LINES="$("$ADB" -s "$SERIAL" devices | awk 'NR > 1 && NF >= 2 { print $1 " " $2 }')"
else
  DEVICE_LINES="$("$ADB" devices | awk 'NR > 1 && NF >= 2 { print $1 " " $2 }')"
fi
if [[ -z "$DEVICE_LINES" ]]; then
  echo "No Android device found. Connect a phone with USB debugging enabled." >&2
  exit 3
fi

if echo "$DEVICE_LINES" | awk '$2 == "unauthorized" { found = 1 } END { exit found ? 0 : 1 }'; then
  echo "Android device is connected but unauthorized." >&2
  if [[ -n "$SERIAL" ]]; then
    "$ADB" -s "$SERIAL" devices -l >&2
  else
    "$ADB" devices -l >&2
  fi
  exit 4
fi

if [[ -z "$SERIAL" ]]; then
  SERIAL="$(echo "$DEVICE_LINES" | awk '$2 == "device" { print $1; exit }')"
fi
if [[ -z "$SERIAL" ]]; then
  echo "No authorized Android device is available." >&2
  "$ADB" devices -l >&2
  exit 5
fi
ADB_TARGET=(-s "$SERIAL")

if ! "$ADB" "${ADB_TARGET[@]}" shell 'command -v nc >/dev/null 2>&1' >/dev/null 2>&1; then
  echo "The connected Android device does not expose nc/netcat; cannot run a TCP route probe." >&2
  exit 6
fi

classify_host() {
  python3 - "$HOST" <<'PY'
import ipaddress
import sys

host = sys.argv[1].strip().lower().strip("[]").rstrip(".")
if not host:
    print("empty")
    raise SystemExit
if host in {"localhost", "0.0.0.0", "::", "::1"} or host.endswith(".local"):
    print("local")
    raise SystemExit
try:
    ip = ipaddress.ip_address(host)
except ValueError:
    print("hostname")
    raise SystemExit
if ip.is_loopback or ip.is_unspecified:
    print("local")
elif ip.is_link_local or ip.is_multicast:
    print("link_local")
elif ip.is_private or ip in ipaddress.ip_network("100.64.0.0/10"):
    print("private_or_cgnat")
else:
    print("public")
PY
}

HOST_CLASS="$(classify_host)"
STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
START_NS="$(python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
)"

shell_quote() {
  python3 - "$1" <<'PY'
import sys

value = sys.argv[1]
print("'" + value.replace("'", "'\\''") + "'")
PY
}

classify_relay_probe_response() {
  python3 -c '
import sys

tokens = sys.stdin.read().strip().split()
if len(tokens) != 4 or tokens[:2] != ["AETHERLINK_RELAY", "probe"]:
    print("unsupported", "unset", "unset", "none", sep="\t")
    raise SystemExit(0)

values = {}
allowed_keys = {"known", "allocated", "runtime_waiting"}
for token in tokens[2:]:
    if token.count("=") != 1:
        print("unsupported", "unset", "unset", "none", sep="\t")
        raise SystemExit(0)
    key, raw_value = token.split("=", 1)
    if key not in allowed_keys or key in values:
        print("unsupported", "unset", "unset", "none", sep="\t")
        raise SystemExit(0)
    normalized_value = raw_value.lower()
    if normalized_value in {"1", "true", "yes"}:
        values[key] = True
    elif normalized_value in {"0", "false", "no"}:
        values[key] = False
    else:
        print("unsupported", "unset", "unset", "none", sep="\t")
        raise SystemExit(0)

route_status_keys = set(values).intersection({"known", "allocated"})
if len(route_status_keys) != 1 or "runtime_waiting" not in values:
    print("unsupported", "unset", "unset", "none", sep="\t")
    raise SystemExit(0)

route_known = values[route_status_keys.pop()]
runtime_waiting = values["runtime_waiting"]
result = "ready" if route_known and runtime_waiting else "unavailable"
canonical_output = (
    "AETHERLINK_RELAY probe "
    f"known={str(route_known).lower()} "
    f"runtime_waiting={str(runtime_waiting).lower()}"
)
print(
    result,
    "1" if route_known else "0",
    "1" if runtime_waiting else "0",
    canonical_output,
    sep="\t",
)
'
}

PROBE_MODE="tcp_connect"
RAW_PROBE_STATUS=0
PROBE_READY=0
PROBE_SUPPORTED=1
PROBE_RESULT="unavailable"
PROBE_ROUTE_KNOWN="unset"
PROBE_RUNTIME_WAITING="unset"
PROBE_OUTPUT=""
PROBE_RESPONSE_STATUS="unset"
CANONICAL_PROBE_OUTPUT=""

set +e
if [[ -n "$RELAY_ID" ]]; then
  PROBE_MODE="aetherlink_relay_probe"
  REMOTE_REQUEST="$(shell_quote "AETHERLINK_RELAY probe $RELAY_ID")"
  REMOTE_HOST="$(shell_quote "$HOST")"
  TCP_PROBE_OUTPUT="$("$ADB" "${ADB_TARGET[@]}" shell nc -z -w "$TIMEOUT_SECONDS" "$HOST" "$PORT" 2>&1 </dev/null)"
  RAW_PROBE_STATUS=$?
  if [[ "$RAW_PROBE_STATUS" -ne 0 ]]; then
    PROBE_SUPPORTED=0
    PROBE_STATUS=1
  else
    PROBE_OUTPUT="$("$ADB" "${ADB_TARGET[@]}" shell "printf '%s\n' $REMOTE_REQUEST | nc -w $TIMEOUT_SECONDS $REMOTE_HOST $PORT" 2>&1 </dev/null)"
    PROBE_RESPONSE_STATUS=$?
    if [[ "$PROBE_RESPONSE_STATUS" -ne 0 ]]; then
      PROBE_RESULT="unsupported"
      PROBE_ROUTE_KNOWN="unset"
      PROBE_RUNTIME_WAITING="unset"
      CANONICAL_PROBE_OUTPUT=""
      PROBE_SUPPORTED=0
      PROBE_STATUS=0
    else
      PROBE_PARSE_RESULT="$(printf '%s' "$PROBE_OUTPUT" | classify_relay_probe_response)"
      IFS=$'\t' read -r PROBE_RESULT PROBE_ROUTE_KNOWN PROBE_RUNTIME_WAITING CANONICAL_PROBE_OUTPUT <<<"$PROBE_PARSE_RESULT"
      if [[ "$CANONICAL_PROBE_OUTPUT" == "none" ]]; then
        CANONICAL_PROBE_OUTPUT=""
      fi
      case "$PROBE_RESULT" in
        ready)
          PROBE_READY=1
          PROBE_STATUS=0
          ;;
        unavailable)
          PROBE_STATUS=1
          ;;
        unsupported)
          PROBE_SUPPORTED=0
          PROBE_STATUS=0
          ;;
        *)
          PROBE_RESULT="unsupported"
          PROBE_ROUTE_KNOWN="unset"
          PROBE_RUNTIME_WAITING="unset"
          CANONICAL_PROBE_OUTPUT=""
          PROBE_SUPPORTED=0
          PROBE_STATUS=0
          ;;
      esac
    fi
  fi
else
  PROBE_OUTPUT="$("$ADB" "${ADB_TARGET[@]}" shell nc -z -w "$TIMEOUT_SECONDS" "$HOST" "$PORT" 2>&1 </dev/null)"
  RAW_PROBE_STATUS=$?
  PROBE_STATUS=$RAW_PROBE_STATUS
  if [[ "$RAW_PROBE_STATUS" -eq 0 ]]; then
    PROBE_RESULT="tcp_reachable"
  fi
fi
set -e

END_NS="$(python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
)"
DURATION_MS="$(( (END_NS - START_NS) / 1000000 ))"

NETWORK_SUMMARY=""
if [[ "$INCLUDE_NETWORK_SUMMARY" == "1" || -n "$JSON_PATH" ]]; then
  NETWORK_SUMMARY="$("$ADB" "${ADB_TARGET[@]}" shell dumpsys connectivity 2>/dev/null \
    | grep -Ei 'NetworkAgentInfo|MOBILE|WIFI|CELLULAR|TRANSPORT|validated|LinkAddresses|Routes|Default' \
    | head -80 || true)"
fi

write_json() {
  [[ -n "$JSON_PATH" ]] || return 0
  python3 - \
    "$JSON_PATH" \
    "$STARTED_AT" \
    "$SERIAL" \
    "$HOST" \
    "$PORT" \
    "$HOST_CLASS" \
    "$TIMEOUT_SECONDS" \
    "$PROBE_STATUS" \
    "$RAW_PROBE_STATUS" \
    "$PROBE_MODE" \
    "$RELAY_ID" \
    "$PROBE_READY" \
    "$PROBE_SUPPORTED" \
    "$PROBE_RESULT" \
    "$PROBE_ROUTE_KNOWN" \
    "$PROBE_RUNTIME_WAITING" \
    "$PROBE_RESPONSE_STATUS" \
    "$DURATION_MS" \
    "$CANONICAL_PROBE_OUTPUT" \
    "$NETWORK_SUMMARY" \
    "$RELAY_PROBE_SELF_TEST" <<'PY'
import json
import os
import sys

(
    path,
    started_at,
    serial,
    host,
    port,
    host_class,
    timeout_seconds,
    probe_status,
    raw_probe_status,
    probe_mode,
    relay_id,
    probe_ready,
    probe_supported,
    probe_result,
    probe_route_known,
    probe_runtime_waiting,
    probe_response_status,
    duration_ms,
    canonical_probe_output,
    network_summary,
    relay_probe_self_test,
) = sys.argv[1:]
redaction_self_test = relay_probe_self_test == "1"

caveats = [
    "route_probe_not_pairing_or_authentication",
    "adb_probe_not_optical_qr_scan",
    "not_production_session_key_exchange_proof",
    "not_production_end_to_end_transport_encryption_proof",
]
if redaction_self_test:
    caveats.append("android_relay_probe_redaction_self_test_not_phone_reachability_proof")
if not relay_id:
    caveats.append("tcp_connect_only_not_relay_room_readiness")
if relay_id and probe_result == "unsupported":
    caveats.append("relay_route_probe_unsupported_authenticated_connection_required")
if host_class in {"local", "link_local", "private_or_cgnat"}:
    caveats.append("endpoint_class_may_not_cross_unrelated_networks")
if int(probe_status) != 0:
    caveats.append("android_device_relay_probe_failed")

summary = {
    "generated_at": started_at,
    "evidence": {
        "source": "fake_adb_redaction_self_test" if redaction_self_test else "android_device_network_probe",
        "self_test": redaction_self_test,
    },
    "device": {
        "adb_serial": None if redaction_self_test else serial,
    },
    "relay": {
        "host": host,
        "port": int(port),
        "host_class": host_class,
        "relay_id_present": bool(relay_id),
    },
    "probe": {
        "transport": probe_mode,
        "timeout_seconds": int(timeout_seconds),
        "duration_ms": int(duration_ms),
        "exit_status": int(probe_status),
        "raw_exit_status": int(raw_probe_status),
        "response_exit_status": None if probe_response_status == "unset" else int(probe_response_status),
        "tcp_reachable": int(raw_probe_status) == 0,
        "route_ready": probe_ready == "1",
        "supported": probe_supported == "1",
        "result": probe_result,
        "route_known": None if probe_route_known == "unset" else probe_route_known == "1",
        "runtime_waiting": None if probe_runtime_waiting == "unset" else probe_runtime_waiting == "1",
        "reachable": int(probe_status) == 0,
        "output": canonical_probe_output or None,
    },
    "network_summary": network_summary.strip() or None,
    "coverage": {
        "android_relay_probe_redaction_self_test": redaction_self_test,
        "live_android_relay_probe_verified": (
            (not redaction_self_test)
            and int(probe_status) == 0
            and probe_supported == "1"
        ),
        "live_android_route_probe_verified": (not redaction_self_test) and bool(relay_id) and probe_ready == "1",
        "production_relay": False,
        "production_session_key_exchange": False,
        "production_end_to_end_transport_encryption": False,
    },
    "caveats": caveats,
}

directory = os.path.dirname(path)
if directory:
    os.makedirs(directory, exist_ok=True)
with open(path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

write_json

if [[ "$PROBE_STATUS" -eq 0 ]]; then
  if [[ "$RELAY_PROBE_SELF_TEST" == "1" ]]; then
    if [[ "$PROBE_SUPPORTED" -eq 1 ]]; then
      echo "OK: Android relay reachability probe redaction self-test generated seeded route-ready evidence; not phone reachability proof."
    else
      echo "OK: Android relay reachability probe redaction self-test generated seeded TCP-reachable evidence; the route probe response is unsupported, so authenticated pairing must verify the route; not phone reachability proof."
    fi
  elif [[ -n "$RELAY_ID" ]]; then
    if [[ "$PROBE_SUPPORTED" -eq 1 ]]; then
      echo "OK: Android device $SERIAL sees relay route ready at $HOST:$PORT."
    else
      echo "OK: Android device $SERIAL can reach relay TCP at $HOST:$PORT; the route probe response is unsupported, so authenticated pairing must verify the route."
    fi
  else
    echo "OK: Android device $SERIAL can open TCP to $HOST:$PORT."
  fi
  if [[ -n "$JSON_PATH" ]]; then
    echo "Summary: $JSON_PATH"
  fi
  exit 0
fi

if [[ -n "$RELAY_ID" ]]; then
  echo "Android device $SERIAL could not verify relay route at $HOST:$PORT within ${TIMEOUT_SECONDS}s." >&2
else
  echo "Android device $SERIAL could not open TCP to $HOST:$PORT within ${TIMEOUT_SECONDS}s." >&2
fi
if [[ "$HOST_CLASS" == "private_or_cgnat" || "$HOST_CLASS" == "link_local" || "$HOST_CLASS" == "local" ]]; then
  echo "Endpoint class '$HOST_CLASS' is usually not reachable from an unrelated network unless a VPN, tunnel, or private overlay makes it reachable." >&2
fi
if [[ -n "$JSON_PATH" ]]; then
  echo "Summary: $JSON_PATH" >&2
fi
exit 1
