#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELAY_HOST="${AETHERLINK_BOOTSTRAP_RELAY_HOST:-}"
RELAY_PORT="${AETHERLINK_BOOTSTRAP_RELAY_PORT:-43171}"
ALLOCATION_TOKEN="${AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN:-${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}}"
SERIAL=""
JSON_PATH="$ROOT_DIR/build/qa/android-external-relay-pairing.json"
LOG_PATH="$ROOT_DIR/build/qa/android-external-relay-pairing.log"
ANDROID_PAIRING_SUMMARY_JSON=""
SKIP_INSTALL=0
KEEP_APP_DATA=0
ALLOW_PRIVATE_RELAY=0
EXPECT_RECONNECT=1
EXPECT_CHAT_CANCEL=0
EXPECT_CHAT_COMPLETE=0
LIVE_BACKEND=0
CHAT_MODEL_QUERY="${AETHERLINK_ANDROID_CHAT_MODEL_QUERY:-}"
CHAT_TEXT="${AETHERLINK_ANDROID_CHAT_SMOKE_TEXT:-AetherLink_external_relay_smoke}"
CHAT_DELTA_TIMEOUT="${AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS:-15}"
CHAT_COMPLETE_TIMEOUT="${AETHERLINK_ANDROID_CHAT_COMPLETE_TIMEOUT_SECONDS:-180}"
CHAT_EXPECTED_TERMS="${AETHERLINK_ANDROID_CHAT_EXPECTED_TERMS:-}"
REQUIRE_DIFFERENT_NETWORK_CONFIRMATION=0
SELF_TEST_REDACT_PROBE_SUMMARY=0
SUMMARY_RELAY_HOST="$RELAY_HOST"

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
  --expect-chat-complete  Also drive physical chat send/complete UI proof.
  --live-backend          Use real local providers behind the runtime.
  --chat-model-query <q>  Select a provider/model row before chat proof.
  --chat-text <text>      Text used by the optional chat proof.
  --chat-delta-timeout <s>
                          Timeout for optional chat.delta proof.
  --chat-complete-timeout <s>
                          Timeout for optional natural chat.done proof.
  --chat-expected-terms <term,...>
                          Comma-separated completed transcript terms required
                          by --expect-chat-complete.
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
    --expect-chat-complete)
      EXPECT_CHAT_COMPLETE=1
      shift
      ;;
    --live-backend)
      LIVE_BACKEND=1
      shift
      ;;
    --chat-model-query)
      if [[ $# -lt 2 ]]; then
        echo "--chat-model-query requires a value." >&2
        exit 2
      fi
      CHAT_MODEL_QUERY="$2"
      shift 2
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
    --chat-complete-timeout)
      if [[ $# -lt 2 ]]; then
        echo "--chat-complete-timeout requires a value." >&2
        exit 2
      fi
      CHAT_COMPLETE_TIMEOUT="$2"
      shift 2
      ;;
    --chat-expected-terms)
      if [[ $# -lt 2 ]]; then
        echo "--chat-expected-terms requires a value." >&2
        exit 2
      fi
      CHAT_EXPECTED_TERMS="$2"
      shift 2
      ;;
    --require-different-network-confirmation)
      REQUIRE_DIFFERENT_NETWORK_CONFIRMATION=1
      shift
      ;;
    --self-test-redact-probe-summary)
      SELF_TEST_REDACT_PROBE_SUMMARY=1
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

if [[ "$EXPECT_CHAT_CANCEL" -eq 1 && "$EXPECT_CHAT_COMPLETE" -eq 1 ]]; then
  echo "--expect-chat-cancel and --expect-chat-complete are mutually exclusive." >&2
  exit 2
fi
if [[ -n "$CHAT_MODEL_QUERY" && "$EXPECT_CHAT_CANCEL" -ne 1 && "$EXPECT_CHAT_COMPLETE" -ne 1 ]]; then
  echo "--chat-model-query requires --expect-chat-cancel or --expect-chat-complete." >&2
  exit 2
fi
if [[ -n "$CHAT_EXPECTED_TERMS" && "$EXPECT_CHAT_COMPLETE" -ne 1 ]]; then
  echo "--chat-expected-terms requires --expect-chat-complete." >&2
  exit 2
fi

if [[ "$SELF_TEST_REDACT_PROBE_SUMMARY" -eq 1 && -z "$RELAY_HOST" ]]; then
  RELAY_HOST="relay.example.test"
fi

if [[ -z "$RELAY_HOST" ]]; then
  echo "Missing --relay-host or AETHERLINK_BOOTSTRAP_RELAY_HOST." >&2
  usage >&2
  exit 2
fi

if [[ "$REQUIRE_DIFFERENT_NETWORK_CONFIRMATION" -eq 1 && "${AETHERLINK_DIFFERENT_NETWORK_CONFIRMED:-}" != "1" ]]; then
  echo "Set AETHERLINK_DIFFERENT_NETWORK_CONFIRMED=1 after putting the phone on a different network." >&2
  exit 2
fi

SUMMARY_RELAY_HOST="$RELAY_HOST"
json_dir="$(dirname "$JSON_PATH")"
json_base="$(basename "$JSON_PATH")"
ANDROID_PAIRING_SUMMARY_JSON="$json_dir/${json_base%.json}.android-pairing-summary.json"

mkdir -p "$(dirname "$JSON_PATH")" "$(dirname "$LOG_PATH")"
cd "$ROOT_DIR"

COMMAND=(
  ./script/android_pairing_deeplink_smoke.sh
  --relay
  --external-relay-host "$RELAY_HOST"
  --external-relay-port "$RELAY_PORT"
  --probe-external-relay-from-device
  --summary-json "$ANDROID_PAIRING_SUMMARY_JSON"
)

if [[ -n "$SERIAL" ]]; then
  COMMAND+=(--serial "$SERIAL")
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
if [[ "$EXPECT_CHAT_COMPLETE" -eq 1 ]]; then
  COMMAND+=(--expect-chat-complete --chat-text "$CHAT_TEXT" --chat-delta-timeout "$CHAT_DELTA_TIMEOUT" --chat-complete-timeout "$CHAT_COMPLETE_TIMEOUT")
  if [[ -n "$CHAT_EXPECTED_TERMS" ]]; then
    COMMAND+=(--chat-expected-terms "$CHAT_EXPECTED_TERMS")
  fi
fi
if [[ -n "$CHAT_MODEL_QUERY" ]]; then
  COMMAND+=(--chat-model-query "$CHAT_MODEL_QUERY")
fi
if [[ "$LIVE_BACKEND" -eq 1 ]]; then
  COMMAND+=(--live-backend)
fi

redacted_command() {
  local redact_next=0
  local sanitize_host_next=0
  local pieces=()
  local arg
  for arg in "${COMMAND[@]}"; do
    if [[ "$redact_next" -eq 1 ]]; then
      pieces+=("<redacted>")
      redact_next=0
      continue
    fi
    if [[ "$sanitize_host_next" -eq 1 ]]; then
      pieces+=("$SUMMARY_RELAY_HOST")
      sanitize_host_next=0
      continue
    fi
    pieces+=("$arg")
    if [[ "$arg" == "--allocation-token" ]]; then
      redact_next=1
    elif [[ "$arg" == "--external-relay-host" ]]; then
      sanitize_host_next=1
    fi
  done
  printf '%q ' "${pieces[@]}"
}

validate_relay_host_input() {
  local safe_host
  local status
  set +e
  safe_host="$(python3 - "$RELAY_HOST" <<'PY'
import sys

host = sys.argv[1]
normalized = host.strip().lower().strip("[]")
if not normalized:
    print("<empty-host>")
    raise SystemExit(2)
if "://" in normalized or "/" in normalized or "@" in normalized or "?" in normalized or "#" in normalized:
    print("<invalid-host>")
    raise SystemExit(2)
print(host)
PY
)"
  status=$?
  set -e
  SUMMARY_RELAY_HOST="$safe_host"
  return "$status"
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
  local android_pairing_summary_json="${13:-$ANDROID_PAIRING_SUMMARY_JSON}"

  local pairing_count
  local health_count
  local model_list_count
  local chat_send_count
  local chat_delta_count
  local chat_cancel_count
  local chat_done_count
  pairing_count="$(count_in_file "$runtime_log" "Development pairing accepted")"
  health_count="$(count_in_file "$runtime_log" "runtime.health")"
  model_list_count="$(count_in_file "$runtime_log" "models.list")"
  chat_send_count="$(count_in_file "$runtime_log" "chat.send")"
  chat_delta_count="$(count_in_file "$runtime_log" "chat.delta")"
  chat_cancel_count="$(count_in_file "$runtime_log" "chat.cancel")"
  chat_done_count="$(count_in_file "$runtime_log" "chat.done")"

  python3 - \
    "$JSON_PATH" \
    "$status" \
    "$started_at" \
    "$ended_at" \
    "$duration_seconds" \
    "$SUMMARY_RELAY_HOST" \
    "$RELAY_PORT" \
    "$device_serial" \
    "$SERIAL" \
    "$ALLOW_PRIVATE_RELAY" \
    "$EXPECT_RECONNECT" \
    "$EXPECT_CHAT_CANCEL" \
    "$EXPECT_CHAT_COMPLETE" \
    "$LIVE_BACKEND" \
    "$([[ -n "$CHAT_MODEL_QUERY" ]] && echo 1 || echo 0)" \
    "$no_adb_reverse" \
    "$pairing_count" \
    "$health_count" \
    "$model_list_count" \
    "$chat_send_count" \
    "$chat_delta_count" \
    "$chat_cancel_count" \
    "$chat_done_count" \
    "$LOG_PATH" \
    "$smoke_work_dir" \
    "$runtime_log" \
    "$screenshot" \
    "$device_probe_json" \
	    "$device_route_probe_json" \
	    "$redacted_command_text" \
	    "$REQUIRE_DIFFERENT_NETWORK_CONFIRMATION" \
	    "$([[ -n "$ALLOCATION_TOKEN" ]] && echo 1 || echo 0)" \
	    "$SELF_TEST_REDACT_PROBE_SUMMARY" \
	    "$android_pairing_summary_json" <<'PY'
import json
import os
import re
import sys
import urllib.parse

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
    expect_chat_complete,
    live_backend,
    chat_model_query_requested,
    no_adb_reverse,
    pairing_count,
    health_count,
    model_list_count,
    chat_send_count,
    chat_delta_count,
    chat_cancel_count,
    chat_done_count,
    log_path,
    smoke_work_dir,
    runtime_log,
    screenshot,
    device_probe_json,
    device_route_probe_json,
    redacted_command,
    require_different_network_confirmation,
    allocation_token_set,
    self_test_redact_probe_summary,
    android_pairing_summary_json,
) = sys.argv[1:]

exit_status = int(status)
pairing_count = int(pairing_count)
health_count = int(health_count)
model_list_count = int(model_list_count)
chat_send_count = int(chat_send_count)
chat_delta_count = int(chat_delta_count)
chat_cancel_count = int(chat_cancel_count)
chat_done_count = int(chat_done_count)
expect_reconnect_bool = expect_reconnect == "1"
expect_chat_cancel_bool = expect_chat_cancel == "1"
expect_chat_complete_bool = expect_chat_complete == "1"
self_test_redaction_only = self_test_redact_probe_summary == "1"
external_network_operator_confirmed = require_different_network_confirmation == "1"

caveats = [
    "uses_adb_deeplink_injection_not_optical_camera_qr_scan",
    "requires_user_controlled_public_vpn_tunnel_or_private_overlay_relay",
    "does_not_expose_ollama_or_lm_studio_to_android",
    "not_production_relay_proof",
    "not_production_session_key_exchange_proof",
    "not_production_end_to_end_transport_encryption_proof",
]
if not external_network_operator_confirmed:
    caveats.append("operator_must_confirm_phone_was_on_a_different_network")
if exit_status != 0:
    caveats.append("physical_external_relay_pairing_failed")
if no_adb_reverse != "1":
    caveats.append("adb_reverse_absence_not_proven")
if expect_reconnect_bool and model_list_count < 1:
    caveats.append("saved_route_models_list_reconnect_not_observed")
if expect_chat_cancel_bool and chat_cancel_count < 1:
    caveats.append("chat_cancel_not_observed")
if expect_chat_complete_bool and chat_done_count < 1:
    caveats.append("chat_complete_not_observed")
if expect_chat_complete_bool and chat_cancel_count > 0:
    caveats.append("chat_cancel_observed_during_chat_complete")
if self_test_redaction_only:
    caveats.append("self_test_redaction_only_not_physical_relay_proof")

def load_json_artifact(candidate_path):
    if not candidate_path:
        return None
    try:
        with open(candidate_path, "r", encoding="utf-8") as handle:
            return redact_probe_summary_route_material(json.load(handle))
    except Exception as exc:
        return {
            "path": candidate_path,
            "load_error": str(exc),
        }

SENSITIVE_ROUTE_KEYS = {
    "allocation_token",
    "allocationtoken",
    "requested_route_token",
    "requestedroutetoken",
    "network_id",
    "networkid",
    "remote_id",
    "remoteid",
    "remote_nonce",
    "remotenonce",
    "remote_secret",
    "remotesecret",
    "rendezvous_nonce",
    "rendezvousnonce",
    "rendezvous_secret",
    "rendezvoussecret",
    "relay_id",
    "relayid",
    "relay_secret",
    "relaysecret",
    "relay_nonce",
    "relaynonce",
    "relay_expires_at",
    "relayexpiresat",
    "ri",
    "rrn",
    "rs",
    "rt",
    "route_id",
    "routeid",
    "route_token",
    "routetoken",
    "route_secret",
    "routesecret",
    "route_nonce",
    "routenonce",
}

def redact_probe_summary_route_material(summary):
    sensitive_values = set()

    def collect(node):
        if isinstance(node, dict):
            for key, value in node.items():
                normalized_key = key.lower()
                compact_key = normalized_key.replace("_", "")
                if (
                    (normalized_key in SENSITIVE_ROUTE_KEYS or compact_key in SENSITIVE_ROUTE_KEYS)
                    and isinstance(value, str)
                    and value
                ):
                    sensitive_values.add(value)
                collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    def scrub_text(value):
        import re

        text = value
        for marker in sorted(sensitive_values, key=len, reverse=True):
            text = text.replace(marker, "<redacted-route-material>")
        key_pattern = "|".join(re.escape(key) for key in sorted(SENSITIVE_ROUTE_KEYS, key=len, reverse=True))
        return re.sub(
            rf"(?i)(?<![A-Za-z0-9_])(?:{key_pattern})=[^\s,;}}]+",
            "route_material=<redacted>",
            text,
        )

    def sanitize(node):
        if isinstance(node, dict):
            sanitized = {}
            for key, value in node.items():
                normalized_key = key.lower()
                compact_key = normalized_key.replace("_", "")
                if normalized_key == "relay_id":
                    if value:
                        sanitized["relay_id_present"] = True
                    continue
                if normalized_key in SENSITIVE_ROUTE_KEYS or compact_key in SENSITIVE_ROUTE_KEYS:
                    continue
                sanitized[key] = sanitize(value)
            return sanitized
        if isinstance(node, list):
            return [sanitize(item) for item in node]
        if isinstance(node, str):
            return scrub_text(node)
        return node

    collect(summary)
    return sanitize(summary)

def probe_bool(summary, key):
    if not isinstance(summary, dict):
        return False
    probe = summary.get("probe")
    return isinstance(probe, dict) and probe.get(key) is True

device_endpoint_probe = load_json_artifact(device_probe_json)
device_route_probe = load_json_artifact(device_route_probe_json)
android_pairing_summary = load_json_artifact(android_pairing_summary_json)
endpoint_reachable = probe_bool(device_endpoint_probe, "reachable")
route_ready = probe_bool(device_route_probe, "route_ready")
runtime_log_artifact_present = os.path.exists(runtime_log)
wrapper_log_artifact_present = os.path.exists(log_path)

def nested_value(summary, keys):
    value = summary
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value

def safe_android_pairing_summary(summary):
    if not isinstance(summary, dict):
        return None
    if "load_error" in summary:
        return None
    coverage = summary.get("coverage")
    events = summary.get("events")
    paths = summary.get("paths")
    safe_coverage_keys = (
        "physical_device_observed",
        "adb_deeplink_injection_attempted",
        "adb_deeplink_injection_succeeded",
        "adb_reverse_runtime_used",
        "adb_reverse_relay_used",
        "external_relay_mode",
        "external_relay_endpoint_probe_requested",
        "external_relay_endpoint_probe_artifact",
        "external_relay_route_probe_artifact",
        "runtime_pairing_accepted",
        "runtime_health_observed",
        "models_list_observed",
        "trusted_route_reconnect_requested",
        "trusted_route_reconnect_verified",
        "chat_cancel_requested",
        "chat_complete_requested",
        "chat_send_observed",
        "chat_delta_observed",
        "chat_cancel_observed",
        "chat_done_observed",
        "live_backend_requested",
        "live_provider_chat_cancel_proof",
        "live_provider_chat_complete_proof",
        "chat_expected_terms_requested",
        "chat_expected_terms_observed",
        "chat_model_query_requested",
        "chat_model_runtime_log_confirmed",
        "optical_camera_qr_scan",
        "production_relay_proof",
        "production_session_key_exchange_proof",
        "production_end_to_end_transport_encryption_proof",
        "real_different_network_connectivity_proof",
        "android_direct_model_backend_access",
    )
    safe_summary = {
        "success": summary.get("success") is True,
        "exit_status": summary.get("exit_status"),
        "mode": summary.get("mode"),
        "requested_serial_bound": bool(summary.get("requested_serial")),
        "observed_serial_present": bool(summary.get("observed_serial")),
        "coverage": {},
        "events": {},
        "paths_present": {},
    }
    if isinstance(coverage, dict):
        safe_summary["coverage"] = {
            key: coverage.get(key)
            for key in safe_coverage_keys
            if key in coverage
        }
    if isinstance(events, dict):
        for key in (
            "pairing_accepted_count",
            "runtime_health_count",
            "models_list_count",
            "chat_send_count",
            "chat_delta_count",
            "chat_cancel_count",
            "chat_done_count",
        ):
            if key in events:
                safe_summary["events"][key] = events.get(key)
    if isinstance(paths, dict):
        safe_summary["paths_present"] = {
            "runtime_log": bool(paths.get("runtime_log")),
            "external_relay_endpoint_probe_json": bool(paths.get("external_relay_endpoint_probe_json")),
            "external_relay_route_probe_json": bool(paths.get("external_relay_route_probe_json")),
            "screenshot": bool(paths.get("screenshot")),
            "chat_screenshot": bool(paths.get("chat_screenshot")),
            "chat_complete_ui_xml": bool(paths.get("chat_complete_ui_xml")),
        }
    return safe_summary

android_pairing_child_summary = safe_android_pairing_summary(android_pairing_summary)
android_pairing_summary_present = android_pairing_child_summary is not None
android_pairing_summary_success = bool(
    android_pairing_child_summary
    and android_pairing_child_summary.get("success") is True
)
android_pairing_summary_external_relay_mode = nested_value(
    android_pairing_child_summary,
    ("coverage", "external_relay_mode"),
) is True
android_pairing_summary_no_relay_adb_reverse = nested_value(
    android_pairing_child_summary,
    ("coverage", "adb_reverse_relay_used"),
) is False
android_pairing_summary_live_provider_chat_complete_proof = nested_value(
    android_pairing_child_summary,
    ("coverage", "live_provider_chat_complete_proof"),
) is True
android_pairing_summary_chat_expected_terms_observed = nested_value(
    android_pairing_child_summary,
    ("coverage", "chat_expected_terms_observed"),
) or []
android_pairing_summary_proof_boundary_preserved = bool(
    android_pairing_child_summary
    and nested_value(android_pairing_child_summary, ("coverage", "optical_camera_qr_scan")) is False
    and nested_value(android_pairing_child_summary, ("coverage", "production_relay_proof")) is False
    and nested_value(android_pairing_child_summary, ("coverage", "production_session_key_exchange_proof")) is False
    and nested_value(android_pairing_child_summary, ("coverage", "production_end_to_end_transport_encryption_proof")) is False
    and nested_value(android_pairing_child_summary, ("coverage", "real_different_network_connectivity_proof")) is False
    and nested_value(android_pairing_child_summary, ("coverage", "android_direct_model_backend_access")) is False
)
if expect_chat_complete_bool and not android_pairing_summary_live_provider_chat_complete_proof:
    caveats.append("android_pairing_summary_chat_complete_not_proven")

def read_text(candidate_path):
    try:
        with open(candidate_path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""

def pairing_uri_queries(text):
    marker = "AETHERLINK_DEV_PAIRING_URI "
    for line in text.splitlines():
        if marker not in line:
            continue
        uri = line.split(marker, 1)[1].strip()
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme == "aetherlink" and parsed.netloc == "pair":
            yield dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))

def has_any(query, *names):
    return any(query.get(name) for name in names)

def wrapper_log_contains_unredacted_route_material(text):
    patterns = (
        r"AETHERLINK_DEV_PAIRING_URI\s+aetherlink://pair\?",
        r"aetherlink://pair\?(?!<redacted>)",
        r"(?i)(?<![A-Za-z0-9_])(?:pairing_nonce|pairing_code|relay_secret|remote_secret|route_secret|relay_nonce|remote_nonce|route_nonce|rendezvous_nonce|route_token|discovery_token|allocation_token|requested_route_token|runtime_public_key|runtime_key_fingerprint)=",
        r"(?i)(?<![A-Za-z0-9_])(?:rs|rrn|rt|rk|rf)=",
    )
    return any(re.search(pattern, text) for pattern in patterns)

wrapper_log_text = read_text(log_path)
wrapper_log_contains_route_material = wrapper_log_contains_unredacted_route_material(wrapper_log_text)
runtime_pairing_queries = list(pairing_uri_queries(read_text(runtime_log)))
runtime_log_contains_temporary_pairing_material = any(
    has_any(query, "pairing_nonce", "nonce", "n")
    and has_any(query, "pairing_code", "code", "c")
    for query in runtime_pairing_queries
)
runtime_log_contains_temporary_route_material = any(
    has_any(query, "relay_host", "remote_host", "route_host", "rendezvous_host", "rh")
    and has_any(query, "relay_port", "remote_port", "route_port", "rendezvous_port", "rp")
    and has_any(query, "relay_id", "remote_id", "route_id", "network_id", "ri")
    and has_any(query, "relay_secret", "remote_secret", "route_secret", "rs")
    and has_any(query, "relay_expires_at", "remote_expires_at", "route_expires_at", "rendezvous_expires_at", "rx")
    and has_any(query, "relay_nonce", "remote_nonce", "route_nonce", "rendezvous_nonce", "rrn")
    for query in runtime_pairing_queries
)
if not endpoint_reachable:
    caveats.append("device_endpoint_probe_not_reachable_or_missing")
if not route_ready:
    caveats.append("device_route_probe_not_ready_or_missing")
if runtime_log_contains_temporary_pairing_material or runtime_log_contains_temporary_route_material:
    caveats.append("runtime_log_contains_temporary_pairing_or_route_material")
if wrapper_log_contains_route_material:
    caveats.append("wrapper_log_contains_unredacted_route_material")
if not wrapper_log_artifact_present or wrapper_log_contains_route_material:
    caveats.append("wrapper_log_redaction_not_verified")
if not android_pairing_summary_present:
    caveats.append("android_pairing_summary_json_missing")
elif not android_pairing_summary_success:
    caveats.append("android_pairing_summary_json_not_successful")
if android_pairing_summary_present and not android_pairing_summary_proof_boundary_preserved:
    caveats.append("android_pairing_summary_json_proof_boundary_not_preserved")

live_android_device_probe_verified = (
    not self_test_redaction_only
    and bool(observed_device_serial)
    and bool(device_probe_json)
    and bool(device_route_probe_json)
    and endpoint_reachable
    and route_ready
)
physical_external_relay_verified = (
    exit_status == 0
    and no_adb_reverse == "1"
    and android_pairing_summary_success
    and android_pairing_summary_external_relay_mode
    and android_pairing_summary_no_relay_adb_reverse
    and live_android_device_probe_verified
    and pairing_count > 0
    and health_count > 0
)
real_different_network_connectivity_proof = (
    physical_external_relay_verified
    and external_network_operator_confirmed
)
private_or_same_lan_development_relay = (
    allow_private_relay == "1"
    and not external_network_operator_confirmed
)
if private_or_same_lan_development_relay:
    caveats.append("private_or_same_lan_development_relay_not_real_different_network_proof")

summary = {
    "generated_at": ended_at,
    "started_at": started_at,
    "ended_at": ended_at,
    "duration_seconds": int(duration_seconds),
    "success": exit_status == 0 and no_adb_reverse == "1",
    "self_test_success": self_test_redaction_only and exit_status == 0,
    "physical_external_relay_success": physical_external_relay_verified,
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
        "probe_summary_redaction_self_test": self_test_redaction_only,
        "live_android_device_probe_verified": live_android_device_probe_verified,
        "physical_external_relay_verified": physical_external_relay_verified,
        "android_pairing_summary_json_present": android_pairing_summary_present,
        "android_pairing_summary_success": android_pairing_summary_success,
        "android_pairing_summary_external_relay_mode": android_pairing_summary_external_relay_mode,
        "android_pairing_summary_no_relay_adb_reverse": android_pairing_summary_no_relay_adb_reverse,
        "android_pairing_summary_proof_boundary_preserved": android_pairing_summary_proof_boundary_preserved,
        "adb_deeplink_injection": nested_value(android_pairing_child_summary, ("coverage", "adb_deeplink_injection_succeeded")) is True,
        "optical_camera_qr_scan": False,
        "production_relay": False,
        "production_relay_proof": False,
        "production_session_key_exchange": False,
        "production_session_key_exchange_proof": False,
        "production_end_to_end_transport_encryption": False,
        "production_end_to_end_transport_encryption_proof": False,
        "external_network_operator_confirmed": external_network_operator_confirmed,
        "real_different_network_relay_verified": real_different_network_connectivity_proof,
        "real_different_network_connectivity_proof": real_different_network_connectivity_proof,
        "android_direct_model_backend_access": False,
        "private_relay_allowed": allow_private_relay == "1",
        "private_or_same_lan_development_relay": private_or_same_lan_development_relay,
        "wrapper_log_artifact_present": wrapper_log_artifact_present,
        "wrapper_log_omits_temporary_secret_material": wrapper_log_artifact_present and not wrapper_log_contains_route_material,
        "wrapper_log_contains_unredacted_route_material": wrapper_log_contains_route_material,
        "runtime_log_artifact_present": runtime_log_artifact_present,
        "runtime_log_contains_temporary_pairing_material": runtime_log_contains_temporary_pairing_material,
        "runtime_log_contains_temporary_route_material": runtime_log_contains_temporary_route_material,
        "adb_reverse_absence_proven": no_adb_reverse == "1",
        "pairing_accepted_count": pairing_count,
        "runtime_health_count": health_count,
        "models_list_count": model_list_count,
        "expect_reconnect": expect_reconnect_bool,
        "chat_send_count": chat_send_count,
        "chat_delta_count": chat_delta_count,
        "chat_cancel_count": chat_cancel_count,
        "chat_done_count": chat_done_count,
        "expect_chat_cancel": expect_chat_cancel_bool,
        "expect_chat_complete": expect_chat_complete_bool,
        "chat_model_query_requested": chat_model_query_requested == "1",
        "android_pairing_summary_live_provider_chat_complete_proof": android_pairing_summary_live_provider_chat_complete_proof,
        "android_pairing_summary_chat_expected_terms_observed": android_pairing_summary_chat_expected_terms_observed,
        "live_backend": live_backend == "1",
    },
    "artifacts": {
        "wrapper_log": log_path,
        "smoke_work_dir": smoke_work_dir or None,
        "runtime_log": runtime_log or None,
        "android_pairing_summary_json": android_pairing_summary_json or None,
        "device_relay_probe_json": device_probe_json or None,
        "device_relay_route_probe_json": device_route_probe_json or None,
        "screenshot": screenshot or None,
    },
    "probe_summaries": {
        "device_relay_endpoint": device_endpoint_probe,
        "device_relay_route": device_route_probe,
    },
    "child_summaries": {
        "android_pairing_deeplink": android_pairing_child_summary,
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

if [[ "$SELF_TEST_REDACT_PROBE_SUMMARY" -eq 1 ]]; then
  SELF_TEST_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-physical-wrapper-redaction.XXXXXX")"
  SELF_TEST_RUNTIME_LOG="$SELF_TEST_WORK_DIR/runtime.log"
  SELF_TEST_ENDPOINT_JSON="$SELF_TEST_WORK_DIR/endpoint.json"
  SELF_TEST_ROUTE_JSON="$SELF_TEST_WORK_DIR/route.json"
  SELF_TEST_PAIRING_SUMMARY_JSON="$SELF_TEST_WORK_DIR/android-pairing-summary.json"
  cat >"$SELF_TEST_RUNTIME_LOG" <<'LOG'
[runtime] AETHERLINK_DEV_PAIRING_URI aetherlink://pair?v=1&pairing_nonce=runtime-pairing-nonce-sensitive&pairing_code=123456&runtime_device_id=runtime-device-sensitive&runtime_name=AetherLink&runtime_public_key=runtime-public-key-sensitive&runtime_key_fingerprint=runtime-fingerprint-sensitive&route_token=runtime-route-token-sensitive&relay_host=relay.example.test&relay_port=43171&relay_id=relay-id-sensitive&relay_secret=relay-secret-sensitive&relay_expires_at=4102444800&relay_nonce=relay-nonce-sensitive
Development pairing accepted
runtime.health
models.list
chat.send
chat.delta
chat.done
LOG
  cat >"$LOG_PATH" <<'LOG'
Running physical external relay pairing QA self-test.
Pairing deeplink output: aetherlink://pair?<redacted>
AETHERLINK_RELAY probe route_material=<redacted>
Runtime log: <self-test-runtime-log>
Summary: <self-test-summary>
LOG
  cat >"$SELF_TEST_ENDPOINT_JSON" <<'JSON'
{
  "probe": {
    "reachable": true,
    "output": "tcp connected"
  },
  "relay": {
    "host": "relay.example.test",
    "port": 43171
  }
}
JSON
  cat >"$SELF_TEST_ROUTE_JSON" <<'JSON'
{
  "probe": {
    "reachable": true,
    "route_ready": true,
    "output": "AETHERLINK_RELAY probe known=1 runtime_waiting=1 relay_id=relay-id-sensitive relay_secret=relay-secret-sensitive route_token=route-token-sensitive"
  },
  "relay": {
    "host": "relay.example.test",
    "port": 43171,
    "relay_id": "relay-id-sensitive",
    "relay_secret": "relay-secret-sensitive",
    "relay_nonce": "relay-nonce-sensitive",
    "route_token": "route-token-sensitive"
  }
}
JSON
  cat >"$SELF_TEST_PAIRING_SUMMARY_JSON" <<'JSON'
{
  "success": true,
  "exit_status": 0,
  "mode": "relay",
  "requested_serial": "self-test-requested-serial",
  "observed_serial": "self-test-observed-serial",
  "events": {
    "pairing_accepted_count": 1,
    "runtime_health_count": 1,
    "models_list_count": 1,
    "chat_send_count": 1,
    "chat_delta_count": 1,
    "chat_cancel_count": 0,
    "chat_done_count": 1
  },
  "coverage": {
    "physical_device_observed": true,
    "adb_deeplink_injection_attempted": true,
    "adb_deeplink_injection_succeeded": true,
    "adb_reverse_runtime_used": false,
    "adb_reverse_relay_used": false,
    "external_relay_mode": true,
    "external_relay_endpoint_probe_requested": true,
    "external_relay_endpoint_probe_artifact": true,
    "external_relay_route_probe_artifact": true,
    "runtime_pairing_accepted": true,
    "runtime_health_observed": true,
    "models_list_observed": true,
    "trusted_route_reconnect_requested": true,
    "trusted_route_reconnect_verified": true,
    "chat_cancel_requested": false,
    "chat_complete_requested": true,
    "chat_send_observed": true,
    "chat_delta_observed": true,
    "chat_cancel_observed": false,
    "chat_done_observed": true,
    "live_backend_requested": true,
    "live_provider_chat_cancel_proof": false,
    "live_provider_chat_complete_proof": true,
    "chat_expected_terms_requested": true,
    "chat_expected_terms_observed": ["ExternalComplete"],
    "chat_model_query_requested": true,
    "chat_model_runtime_log_confirmed": true,
    "optical_camera_qr_scan": false,
    "production_relay_proof": false,
    "production_session_key_exchange_proof": false,
    "production_end_to_end_transport_encryption_proof": false,
    "real_different_network_connectivity_proof": false,
    "android_direct_model_backend_access": false
  },
  "paths": {
    "runtime_log": "/tmp/redacted-runtime.log",
    "external_relay_endpoint_probe_json": "/tmp/redacted-endpoint.json",
    "external_relay_route_probe_json": "/tmp/redacted-route.json"
  }
}
JSON
  write_json_summary \
    0 \
    "2026-07-03T00:00:00Z" \
	    "2026-07-03T00:00:01Z" \
	    1 \
	    "$SELF_TEST_WORK_DIR" \
	    "" \
	    "$SELF_TEST_RUNTIME_LOG" \
    "" \
    "$SELF_TEST_ENDPOINT_JSON" \
    1 \
    "$SELF_TEST_ROUTE_JSON" \
    "$(redacted_command)" \
    "$SELF_TEST_PAIRING_SUMMARY_JSON"
  cat "$JSON_PATH"
  rm -rf "$SELF_TEST_WORK_DIR"
  exit 0
fi

if ! validate_relay_host_input; then
  STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  ENDED_AT="$STARTED_AT"
  mkdir -p "$(dirname "$LOG_PATH")"
  printf 'Invalid relay host %s:%s: use a host or IP address, not a URL.\n' \
    "$SUMMARY_RELAY_HOST" \
    "$RELAY_PORT" >"$LOG_PATH"
  write_json_summary \
    2 \
    "$STARTED_AT" \
    "$ENDED_AT" \
    0 \
    "" \
    "" \
    "" \
    "" \
    "" \
    0 \
    "" \
    "$(redacted_command)"
  echo "Invalid relay host $SUMMARY_RELAY_HOST:$RELAY_PORT: use a host or IP address, not a URL." >&2
  echo "Summary: $JSON_PATH" >&2
  echo "Log: $LOG_PATH" >&2
  exit 2
fi

STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
START_SECONDS="$(date +%s)"
echo "Running physical external relay pairing QA. Full log: $LOG_PATH"
set +e
if [[ -n "$ALLOCATION_TOKEN" ]]; then
  AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN="$ALLOCATION_TOKEN" \
    AETHERLINK_RELAY_ALLOCATION_TOKEN="$ALLOCATION_TOKEN" \
    "${COMMAND[@]}" >"$LOG_PATH" 2>&1
else
  "${COMMAND[@]}" >"$LOG_PATH" 2>&1
fi
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
  elif [[ -z "$ANDROID_PAIRING_SUMMARY_JSON" || ! -f "$ANDROID_PAIRING_SUMMARY_JSON" ]] || ! json_bool_at "$ANDROID_PAIRING_SUMMARY_JSON" "success"; then
    echo "Physical external relay smoke completed but Android pairing summary JSON success was not proven." >&2
    STATUS=27
  elif [[ "$EXPECT_CHAT_COMPLETE" -eq 1 ]] && ! json_bool_at "$ANDROID_PAIRING_SUMMARY_JSON" "coverage.live_provider_chat_complete_proof"; then
    echo "Physical external relay smoke completed but Android pairing summary JSON did not prove chat-complete." >&2
    STATUS=28
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
