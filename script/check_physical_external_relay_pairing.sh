#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELAY_HOST="${AETHERLINK_BOOTSTRAP_RELAY_HOST:-}"
RELAY_PORT="${AETHERLINK_BOOTSTRAP_RELAY_PORT:-43171}"
ALLOCATION_TOKEN="${AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN:-${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}}"
SERIAL=""
JSON_PATH="$ROOT_DIR/build/qa/android-external-relay-pairing.json"
LOG_PATH="$ROOT_DIR/build/qa/android-external-relay-pairing.log"
SKIP_INSTALL=0
KEEP_APP_DATA=0
ALLOW_PRIVATE_RELAY=0
EXPECT_RECONNECT=1
EXPECT_CHAT_CANCEL=0
LIVE_BACKEND=0
CHAT_TEXT="${AETHERLINK_ANDROID_CHAT_SMOKE_TEXT:-AetherLink_external_relay_smoke}"
CHAT_DELTA_TIMEOUT="${AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS:-15}"
REQUIRE_DIFFERENT_NETWORK_CONFIRMATION=0

usage() {
  cat <<'USAGE'
Usage:
  script/check_physical_external_relay_pairing.sh --relay-host <host> [--relay-port <port>]

Runs the physical Android external-relay QA gate for QR-only different-network
development routing. This is intentionally a wrapper around
script/android_pairing_deeplink_smoke.sh in external relay mode.

Success criteria:
  - The runtime host can reach the allocation-capable relay.
  - The attached Android device can open TCP to the relay without adb reverse.
  - The attached Android device can verify the QR relay id with the
    non-consuming AETHERLINK_RELAY probe before pairing.
  - Pairing succeeds from the generated QR deeplink route material.
  - runtime.health reaches AetherLink Runtime.
  - By default, the app is force-stopped/relaunched and models.list reaches the
    runtime from the saved trusted relay route.
  - Android never receives or calls Ollama or LM Studio URLs directly.

Options:
  --relay-host <host>     Public, VPN, tunnel, DNS, or private-overlay relay
                          endpoint reachable by both devices.
  --relay-port <port>     Relay TCP port. Default: 43171.
  --allocation-token <t>  Allocation token for a token-protected development
                          relay. The value is not written to the QA JSON.
  --serial <adb-serial>   Bind the run to a specific attached Android device.
  --json <path>           Write machine-readable QA evidence.
  --log <path>            Capture full smoke output.
  --skip-install          Reuse the already-installed Android debug app.
  --keep-app-data         Do not clear Android app data before pairing.
  --allow-private-relay   Allow private/CGNAT relay literals only for an
                          explicit VPN, tunnel, or private overlay.
  --no-expect-reconnect   Do not relaunch the app to prove saved route reconnect.
  --expect-chat-cancel    Also drive physical chat send/cancel UI proof.
  --live-backend          Use real local providers behind the runtime.
  --chat-text <text>      Text used by the optional chat/cancel proof.
  --chat-delta-timeout <s>
                          Timeout for optional chat.delta proof.
  --require-different-network-confirmation
                          Require AETHERLINK_DIFFERENT_NETWORK_CONFIRMED=1 so
                          local relay runs are not mistaken for cross-network
                          evidence.

This script still injects the generated aetherlink://pair URI through adb. It
does not prove optical camera scanning; use the no-ADB QR smoke for that QR
artifact and manual scan workflow.
USAGE
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
    --allocation-token)
      if [[ $# -lt 2 ]]; then
        echo "--allocation-token requires a value." >&2
        exit 2
      fi
      ALLOCATION_TOKEN="$2"
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
    --json)
      if [[ $# -lt 2 ]]; then
        echo "--json requires a value." >&2
        exit 2
      fi
      JSON_PATH="$2"
      shift 2
      ;;
    --log)
      if [[ $# -lt 2 ]]; then
        echo "--log requires a value." >&2
        exit 2
      fi
      LOG_PATH="$2"
      shift 2
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --keep-app-data)
      KEEP_APP_DATA=1
      shift
      ;;
    --allow-private-relay)
      ALLOW_PRIVATE_RELAY=1
      shift
      ;;
    --no-expect-reconnect)
      EXPECT_RECONNECT=0
      shift
      ;;
    --expect-chat-cancel)
      EXPECT_CHAT_CANCEL=1
      shift
      ;;
    --live-backend)
      LIVE_BACKEND=1
      shift
      ;;
    --chat-text)
      if [[ $# -lt 2 ]]; then
        echo "--chat-text requires a value." >&2
        exit 2
      fi
      CHAT_TEXT="$2"
      shift 2
      ;;
    --chat-delta-timeout)
      if [[ $# -lt 2 ]]; then
        echo "--chat-delta-timeout requires a value." >&2
        exit 2
      fi
      CHAT_DELTA_TIMEOUT="$2"
      shift 2
      ;;
    --require-different-network-confirmation)
      REQUIRE_DIFFERENT_NETWORK_CONFIRMATION=1
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
  echo "Missing --relay-host or AETHERLINK_BOOTSTRAP_RELAY_HOST." >&2
  usage >&2
  exit 2
fi

if [[ "$REQUIRE_DIFFERENT_NETWORK_CONFIRMATION" -eq 1 && "${AETHERLINK_DIFFERENT_NETWORK_CONFIRMED:-}" != "1" ]]; then
  echo "Set AETHERLINK_DIFFERENT_NETWORK_CONFIRMED=1 after putting the phone on a different network." >&2
  exit 2
fi

mkdir -p "$(dirname "$JSON_PATH")" "$(dirname "$LOG_PATH")"
cd "$ROOT_DIR"

COMMAND=(
  ./script/android_pairing_deeplink_smoke.sh
  --relay
  --external-relay-host "$RELAY_HOST"
  --external-relay-port "$RELAY_PORT"
  --probe-external-relay-from-device
)

if [[ -n "$SERIAL" ]]; then
  COMMAND+=(--serial "$SERIAL")
fi
if [[ -n "$ALLOCATION_TOKEN" ]]; then
  COMMAND+=(--allocation-token "$ALLOCATION_TOKEN")
fi
if [[ "$SKIP_INSTALL" -eq 1 ]]; then
  COMMAND+=(--skip-install)
fi
if [[ "$KEEP_APP_DATA" -eq 1 ]]; then
  COMMAND+=(--keep-app-data)
fi
if [[ "$ALLOW_PRIVATE_RELAY" -eq 1 ]]; then
  COMMAND+=(--allow-private-relay)
fi
if [[ "$EXPECT_RECONNECT" -eq 1 ]]; then
  COMMAND+=(--expect-reconnect)
fi
if [[ "$EXPECT_CHAT_CANCEL" -eq 1 ]]; then
  COMMAND+=(--expect-chat-cancel --chat-text "$CHAT_TEXT" --chat-delta-timeout "$CHAT_DELTA_TIMEOUT")
fi
if [[ "$LIVE_BACKEND" -eq 1 ]]; then
  COMMAND+=(--live-backend)
fi

redacted_command() {
  local redact_next=0
  local pieces=()
  local arg
  for arg in "${COMMAND[@]}"; do
    if [[ "$redact_next" -eq 1 ]]; then
      pieces+=("<redacted>")
      redact_next=0
      continue
    fi
    pieces+=("$arg")
    if [[ "$arg" == "--allocation-token" ]]; then
      redact_next=1
    fi
  done
  printf '%q ' "${pieces[@]}"
}

count_in_file() {
  local file="$1"
  local pattern="$2"
  if [[ -f "$file" ]]; then
    grep -c "$pattern" "$file" || true
  else
    echo 0
  fi
}

json_bool_at() {
  local file="$1"
  local dotted_key="$2"
  python3 - "$file" "$dotted_key" <<'PY'
import json
import sys

path, dotted_key = sys.argv[1:]
try:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
except Exception:
    raise SystemExit(1)
for key in dotted_key.split("."):
    if not isinstance(value, dict) or key not in value:
        raise SystemExit(1)
    value = value[key]
raise SystemExit(0 if value is True else 1)
PY
}

write_json_summary() {
  local status="$1"
  local started_at="$2"
  local ended_at="$3"
  local duration_seconds="$4"
  local smoke_work_dir="$5"
  local device_serial="$6"
  local runtime_log="$7"
  local screenshot="$8"
  local device_probe_json="$9"
  local no_adb_reverse="${10}"
  local device_route_probe_json="${11}"
  local redacted_command_text="${12}"

  local pairing_count
  local health_count
  local model_list_count
  local chat_send_count
  local chat_delta_count
  local chat_cancel_count
  pairing_count="$(count_in_file "$runtime_log" "Development pairing accepted")"
  health_count="$(count_in_file "$runtime_log" "runtime.health")"
  model_list_count="$(count_in_file "$runtime_log" "models.list")"
  chat_send_count="$(count_in_file "$runtime_log" "chat.send")"
  chat_delta_count="$(count_in_file "$runtime_log" "chat.delta")"
  chat_cancel_count="$(count_in_file "$runtime_log" "chat.cancel")"

  python3 - \
    "$JSON_PATH" \
    "$status" \
    "$started_at" \
    "$ended_at" \
    "$duration_seconds" \
    "$RELAY_HOST" \
    "$RELAY_PORT" \
    "$device_serial" \
    "$SERIAL" \
    "$ALLOW_PRIVATE_RELAY" \
    "$EXPECT_RECONNECT" \
    "$EXPECT_CHAT_CANCEL" \
    "$LIVE_BACKEND" \
    "$no_adb_reverse" \
    "$pairing_count" \
    "$health_count" \
    "$model_list_count" \
    "$chat_send_count" \
    "$chat_delta_count" \
    "$chat_cancel_count" \
    "$LOG_PATH" \
    "$smoke_work_dir" \
    "$runtime_log" \
    "$screenshot" \
    "$device_probe_json" \
    "$device_route_probe_json" \
    "$redacted_command_text" \
    "$REQUIRE_DIFFERENT_NETWORK_CONFIRMATION" \
    "$([[ -n "$ALLOCATION_TOKEN" ]] && echo 1 || echo 0)" <<'PY'
import json
import os
import sys

(
    path,
    status,
    started_at,
    ended_at,
    duration_seconds,
    relay_host,
    relay_port,
    observed_device_serial,
    requested_device_serial,
    allow_private_relay,
    expect_reconnect,
    expect_chat_cancel,
    live_backend,
    no_adb_reverse,
    pairing_count,
    health_count,
    model_list_count,
    chat_send_count,
    chat_delta_count,
    chat_cancel_count,
    log_path,
    smoke_work_dir,
    runtime_log,
    screenshot,
    device_probe_json,
    device_route_probe_json,
    redacted_command,
    require_different_network_confirmation,
    allocation_token_set,
) = sys.argv[1:]

exit_status = int(status)
pairing_count = int(pairing_count)
health_count = int(health_count)
model_list_count = int(model_list_count)
chat_send_count = int(chat_send_count)
chat_delta_count = int(chat_delta_count)
chat_cancel_count = int(chat_cancel_count)
expect_reconnect_bool = expect_reconnect == "1"
expect_chat_cancel_bool = expect_chat_cancel == "1"

caveats = [
    "uses_adb_deeplink_injection_not_optical_camera_qr_scan",
    "requires_user_controlled_public_vpn_tunnel_or_private_overlay_relay",
    "does_not_expose_ollama_or_lm_studio_to_android",
]
if require_different_network_confirmation != "1":
    caveats.append("operator_must_confirm_phone_was_on_a_different_network")
if exit_status != 0:
    caveats.append("physical_external_relay_pairing_failed")
if no_adb_reverse != "1":
    caveats.append("adb_reverse_absence_not_proven")
if expect_reconnect_bool and model_list_count < 1:
    caveats.append("saved_route_models_list_reconnect_not_observed")
if expect_chat_cancel_bool and chat_cancel_count < 1:
    caveats.append("chat_cancel_not_observed")

def load_json_artifact(candidate_path):
    if not candidate_path:
        return None
    try:
        with open(candidate_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        return {
            "path": candidate_path,
            "load_error": str(exc),
        }

def probe_bool(summary, key):
    if not isinstance(summary, dict):
        return False
    probe = summary.get("probe")
    return isinstance(probe, dict) and probe.get(key) is True

device_endpoint_probe = load_json_artifact(device_probe_json)
device_route_probe = load_json_artifact(device_route_probe_json)
endpoint_reachable = probe_bool(device_endpoint_probe, "reachable")
route_ready = probe_bool(device_route_probe, "route_ready")
if not endpoint_reachable:
    caveats.append("device_endpoint_probe_not_reachable_or_missing")
if not route_ready:
    caveats.append("device_route_probe_not_ready_or_missing")

summary = {
    "generated_at": ended_at,
    "started_at": started_at,
    "ended_at": ended_at,
    "duration_seconds": int(duration_seconds),
    "success": exit_status == 0 and no_adb_reverse == "1",
    "exit_status": exit_status,
    "command": redacted_command.strip(),
    "relay": {
        "host": relay_host,
        "port": int(relay_port),
        "allocation_token_set": allocation_token_set == "1",
        "allow_private_relay": allow_private_relay == "1",
    },
    "android_device": {
        "requested_adb_serial": requested_device_serial or None,
        "observed_adb_serial": observed_device_serial or None,
    },
    "coverage": {
        "external_relay_probe_from_device": bool(device_probe_json),
        "external_relay_route_probe_from_device": bool(device_route_probe_json),
        "external_relay_probe_reachable": endpoint_reachable,
        "external_relay_route_ready": route_ready,
        "adb_reverse_absence_proven": no_adb_reverse == "1",
        "pairing_accepted_count": pairing_count,
        "runtime_health_count": health_count,
        "models_list_count": model_list_count,
        "expect_reconnect": expect_reconnect_bool,
        "chat_send_count": chat_send_count,
        "chat_delta_count": chat_delta_count,
        "chat_cancel_count": chat_cancel_count,
        "expect_chat_cancel": expect_chat_cancel_bool,
        "live_backend": live_backend == "1",
    },
    "artifacts": {
        "wrapper_log": log_path,
        "smoke_work_dir": smoke_work_dir or None,
        "runtime_log": runtime_log or None,
        "device_relay_probe_json": device_probe_json or None,
        "device_relay_route_probe_json": device_route_probe_json or None,
        "screenshot": screenshot or None,
    },
    "probe_summaries": {
        "device_relay_endpoint": device_endpoint_probe,
        "device_relay_route": device_route_probe,
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

STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
START_SECONDS="$(date +%s)"
echo "Running physical external relay pairing QA. Full log: $LOG_PATH"
set +e
"${COMMAND[@]}" >"$LOG_PATH" 2>&1
STATUS=$?
set -e
ENDED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
END_SECONDS="$(date +%s)"
DURATION_SECONDS="$(( END_SECONDS - START_SECONDS ))"

SMOKE_WORK_DIR="$(sed -n 's/^Working directory: //p' "$LOG_PATH" | tail -n 1)"
DEVICE_SERIAL="$(sed -n 's/^Using Android device //p' "$LOG_PATH" | tail -n 1)"
RUNTIME_LOG="$(sed -n 's/^Runtime log: //p' "$LOG_PATH" | tail -n 1)"
SCREENSHOT="$(sed -n 's/^Screenshot: //p' "$LOG_PATH" | tail -n 1)"
DEVICE_PROBE_JSON=""
if [[ -n "$SMOKE_WORK_DIR" && -f "$SMOKE_WORK_DIR/android-relay-reachability.json" ]]; then
  DEVICE_PROBE_JSON="$SMOKE_WORK_DIR/android-relay-reachability.json"
fi
DEVICE_ROUTE_PROBE_JSON=""
if [[ -n "$SMOKE_WORK_DIR" && -f "$SMOKE_WORK_DIR/android-relay-route-readiness.json" ]]; then
  DEVICE_ROUTE_PROBE_JSON="$SMOKE_WORK_DIR/android-relay-route-readiness.json"
fi

NO_ADB_REVERSE=0
if grep -q "Skipping adb reverse;" "$LOG_PATH" && ! grep -q "Configuring adb reverse" "$LOG_PATH"; then
  NO_ADB_REVERSE=1
fi

if [[ "$STATUS" -eq 0 && "$NO_ADB_REVERSE" -ne 1 ]]; then
  echo "Physical external relay smoke completed but adb reverse absence was not proven." >&2
  STATUS=24
fi
if [[ "$STATUS" -eq 0 ]]; then
  if [[ -z "$DEVICE_PROBE_JSON" ]] || ! json_bool_at "$DEVICE_PROBE_JSON" "probe.reachable"; then
    echo "Physical external relay smoke completed but Android endpoint relay reachability was not proven." >&2
    STATUS=25
  elif [[ -z "$DEVICE_ROUTE_PROBE_JSON" ]] || ! json_bool_at "$DEVICE_ROUTE_PROBE_JSON" "probe.route_ready"; then
    echo "Physical external relay smoke completed but Android route-level relay readiness was not proven." >&2
    STATUS=26
  fi
fi

write_json_summary \
  "$STATUS" \
  "$STARTED_AT" \
  "$ENDED_AT" \
  "$DURATION_SECONDS" \
  "$SMOKE_WORK_DIR" \
  "$DEVICE_SERIAL" \
  "$RUNTIME_LOG" \
  "$SCREENSHOT" \
  "$DEVICE_PROBE_JSON" \
  "$NO_ADB_REVERSE" \
  "$DEVICE_ROUTE_PROBE_JSON" \
  "$(redacted_command)"

if [[ "$STATUS" -eq 0 ]]; then
  echo "OK: physical external relay pairing QA passed."
  echo "Summary: $JSON_PATH"
  echo "Log: $LOG_PATH"
  exit 0
fi

echo "Physical external relay pairing QA failed with status $STATUS." >&2
echo "Summary: $JSON_PATH" >&2
echo "Log: $LOG_PATH" >&2
tail -n 80 "$LOG_PATH" >&2 || true
exit "$STATUS"
