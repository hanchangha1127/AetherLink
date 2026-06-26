#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB="${ADB:-$ANDROID_HOME/platform-tools/adb}"
HOST=""
PORT=""
SERIAL=""
TIMEOUT_SECONDS=5
JSON_PATH=""
INCLUDE_NETWORK_SUMMARY=0

usage() {
  cat <<'USAGE'
Usage:
  script/android_relay_reachability_probe.sh --host <relay-host> --port <relay-port> [--timeout <seconds>] [--json <path>]

Checks whether a physically connected Android device can open a TCP connection
to an AetherLink relay endpoint without adb reverse. This is a route diagnostic
only: it does not pair, authenticate, call AetherLink Runtime, or call Ollama or
LM Studio.

Options:
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

set +e
PROBE_OUTPUT="$("$ADB" "${ADB_TARGET[@]}" shell nc -z -w "$TIMEOUT_SECONDS" "$HOST" "$PORT" 2>&1 </dev/null)"
PROBE_STATUS=$?
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
    "$DURATION_MS" \
    "$PROBE_OUTPUT" \
    "$NETWORK_SUMMARY" <<'PY'
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
    duration_ms,
    probe_output,
    network_summary,
) = sys.argv[1:]

caveats = [
    "tcp_connect_only_not_pairing_or_authentication",
    "adb_probe_not_optical_qr_scan",
]
if host_class in {"local", "link_local", "private_or_cgnat"}:
    caveats.append("endpoint_class_may_not_cross_unrelated_networks")
if int(probe_status) != 0:
    caveats.append("android_device_could_not_reach_relay_endpoint")

summary = {
    "generated_at": started_at,
    "device": {
        "adb_serial": serial,
    },
    "relay": {
        "host": host,
        "port": int(port),
        "host_class": host_class,
    },
    "probe": {
        "transport": "android_device_tcp_connect",
        "timeout_seconds": int(timeout_seconds),
        "duration_ms": int(duration_ms),
        "exit_status": int(probe_status),
        "reachable": int(probe_status) == 0,
        "output": probe_output.strip() or None,
    },
    "network_summary": network_summary.strip() or None,
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
  echo "OK: Android device $SERIAL can open TCP to $HOST:$PORT."
  if [[ -n "$JSON_PATH" ]]; then
    echo "Summary: $JSON_PATH"
  fi
  exit 0
fi

echo "Android device $SERIAL could not open TCP to $HOST:$PORT within ${TIMEOUT_SECONDS}s." >&2
if [[ -n "$PROBE_OUTPUT" ]]; then
  echo "$PROBE_OUTPUT" >&2
fi
if [[ "$HOST_CLASS" == "private_or_cgnat" || "$HOST_CLASS" == "link_local" || "$HOST_CLASS" == "local" ]]; then
  echo "Endpoint class '$HOST_CLASS' is usually not reachable from an unrelated network unless a VPN, tunnel, or private overlay makes it reachable." >&2
fi
if [[ -n "$JSON_PATH" ]]; then
  echo "Summary: $JSON_PATH" >&2
fi
exit 1
