#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}"
ADB="${ADB:-$ANDROID_HOME/platform-tools/adb}"
PACKAGE_NAME="com.localagentbridge.android"
MODE="relay"
REQUESTED_SERIAL=""
SKIP_INSTALL=0
KEEP_APP_DATA=0
EXTERNAL_RELAY_HOST=""
EXTERNAL_RELAY_PORT=""
ALLOCATION_TOKEN="${AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN:-${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}}"
ALLOW_DIRECT_FALLBACK=0
ALLOW_PRIVATE_RELAY=0
EXPECT_RECONNECT=0
EXPECT_CHAT_CANCEL=0
LIVE_BACKEND=0
PROBE_EXTERNAL_RELAY_FROM_DEVICE=0
CAPTURE_UI_POLISH=0
CHAT_TEXT="${AETHERLINK_ANDROID_CHAT_SMOKE_TEXT:-AetherLink_physical_cancel_smoke}"
CHAT_DELTA_TIMEOUT="${AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS:-15}"
SELF_TEST_SANITIZE_AM_START_LOG=0
AM_START_SANITIZER_SELF_TEST_MARKER="am_start_sanitizer_self_test_not_android_intent_or_phone_pairing_proof"
SELF_TEST_SANITIZE_ANDROID_QA_ARTIFACTS=0
ANDROID_QA_ARTIFACT_SANITIZER_SELF_TEST_MARKER="android_qa_artifact_sanitizer_self_test_not_phone_logcat_or_activity_proof"

usage() {
  cat <<'USAGE'
Usage: script/android_pairing_deeplink_smoke.sh [--relay|--direct] [--serial <adb-serial>] [--skip-install] [--keep-app-data] [--expect-reconnect] [--expect-chat-cancel] [--capture-ui-polish] [--live-backend] [--chat-text <text>] [--chat-delta-timeout <seconds>]
       script/android_pairing_deeplink_smoke.sh --relay --external-relay-host <host> [--external-relay-port <port>] [--allocation-token <token>] [--allow-private-relay] [--allow-direct-fallback] [--probe-external-relay-from-device]

Runs a physical-device smoke for the QR result path by injecting an
aetherlink://pair URI through Android's VIEW intent. Default mode is --relay:
the script starts the Swift development relay in allocation-required mode, maps
it through adb reverse, starts RuntimeDevServer with a fresh dev pairing window,
installs/launches the Android debug app, and verifies the runtime receives
pairing.request and runtime.health.

Use --expect-reconnect to force-stop and relaunch the Android app after the
first runtime.health without clearing app data, then wait for a second
runtime.health that proves the saved trusted relay route reconnects.

Use --serial when multiple adb devices are attached or when the QA evidence must
bind to a specific physical phone. The smoke fails if that serial is absent or
unauthorized.

Use --expect-chat-cancel to drive the physical Android UI after pairing:
tap the chat input, type a short smoke message, tap Send, wait for streamed
chat.delta, tap Cancel generation, and verify chat.cancel reaches the runtime.
This validates physical UI wiring through the runtime. It still injects the
pairing URI rather than optically scanning a camera QR.

Use --capture-ui-polish to save PNG and uiautomator XML artifacts for the
physical chat screen, navigation drawer, model selector, Settings screen, and
best-effort launcher icon placement after the pairing smoke succeeds.

Use --live-backend to start RuntimeDevServer against real Ollama + LM Studio
providers instead of the fast dev mock backend. Android still talks only to
AetherLink Runtime. Live model first-token latency can be much higher, so pair
it with --chat-delta-timeout when running chat/cancel proof.

This validates the app behavior after QR scan/deep-link delivery. It is still a
development smoke and does not replace a real different-network public/tunnel
relay test.

When --external-relay-host is provided, the script does not start a local relay
and does not configure adb reverse for the relay. The host:port must already be
an allocation-capable AetherLinkRelay reachable from both the runtime host and
the Android device. This is the closer different-network smoke path.

Use --probe-external-relay-from-device with --external-relay-host to make the
connected Android device open a raw TCP probe to the relay endpoint before the
pairing URI is injected. This catches unreachable private/VPN/tunnel routes
before they are confused with QR, pairing, or model-provider failures.

Use --allocation-token, AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN, or
AETHERLINK_RELAY_ALLOCATION_TOKEN when the development relay requires a token.
The token is checked during relay allocation preflight and passed to
RuntimeDevServer for QR route allocation. The allocation preflight is marked
preflight=1 so it does not persist a throwaway relay lease in the relay store.

By default relay mode verifies that the generated QR route is relay-only. Use
--allow-direct-fallback only for explicit mixed-route diagnostics where the QR
intentionally carries direct host/port as a fallback route candidate.

Use --allow-private-relay only when the external relay address is reachable
through a user-controlled VPN, tunnel, or private overlay from both devices.
USAGE
}

validate_external_relay_host_for_qr() {
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
        "--external-relay-host must be reachable from the Android network; "
        "loopback, wildcard, and .local hosts are invalid here.",
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
        "--external-relay-host must be a public, VPN/tunnel, DNS, or future "
        "private-overlay route name reachable from the Android network; "
        "private, link-local, CGNAT, loopback, and multicast IP literals are invalid here unless --allow-private-relay is set for an explicit private overlay.",
        file=sys.stderr,
    )
    raise SystemExit(2)
PY
}

sanitize_android_qa_text_for_route_material() {
  python3 -c "$(cat <<'PY'
import re
import sys

text = sys.stdin.read()

text = re.sub(
    r"aetherlink://pair\?[^ \t\r\n'\"<>})]+",
    "aetherlink://pair?<redacted>",
    text,
    flags=re.IGNORECASE,
)
text = re.sub(
    r"aetherlink%3A%2F%2Fpair%3F[^ \t\r\n'\"<>})]+",
    "aetherlink%3A%2F%2Fpair%3F<redacted>",
    text,
    flags=re.IGNORECASE,
)

sensitive_keys = (
    "AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN",
    "AETHERLINK_RELAY_ALLOCATION_TOKEN",
    "allocation_token",
    "auth",
    "discovery_token",
    "fingerprint",
    "pairing_code",
    "pairing_nonce",
    "public_key",
    "remote_expires_at",
    "remote_host",
    "remote_id",
    "remote_nonce",
    "remote_port",
    "remote_secret",
    "remote_scope",
    "rendezvous_expires_at",
    "rendezvous_host",
    "rendezvous_id",
    "rendezvous_nonce",
    "rendezvous_port",
    "rendezvous_secret",
    "rendezvous_scope",
    "relay_expires_at",
    "relay_host",
    "relay_id",
    "relay_nonce",
    "relay_port",
    "relay_scope",
    "relay_secret",
    "requested_route_token",
    "route_expires_at",
    "route_host",
    "route_id",
    "route_nonce",
    "route_port",
    "route_scope",
    "route_secret",
    "route_token",
    "runtime_device_id",
    "runtime_key_fingerprint",
    "runtime_public_key",
    "network_id",
    "p2p_record_id",
    "p2p_encrypted_body",
    "p2p_expires_at",
    "p2p_nonce",
)
compact_keys = (
    "c",
    "n",
    "pc",
    "peb",
    "pn",
    "prid",
    "pv",
    "px",
    "rf",
    "rh",
    "ri",
    "rid",
    "rk",
    "rp",
    "rrn",
    "rsc",
    "rs",
    "rt",
    "rx",
)
key_pattern = "|".join(re.escape(key) for key in sorted(sensitive_keys + compact_keys, key=len, reverse=True))

text = re.sub(
    rf"(?i)(?<![A-Za-z0-9_])({key_pattern})=([^ \t\r\n&;,'\"<>}})]+)",
    lambda match: f"{match.group(1)}=<redacted>",
    text,
)
text = re.sub(
    rf"(?i)(['\"]?)({key_pattern})\1\s*:\s*(['\"])[^'\"]*\3",
    lambda match: f"{match.group(1)}{match.group(2)}{match.group(1)}: {match.group(3)}<redacted>{match.group(3)}",
    text,
)
text = re.sub(
    r"(?i)\b[A-Za-z0-9_.:-]*(?:sensitive|leaked)[A-Za-z0-9_.:-]*\b",
    "<redacted>",
    text,
)

print(text, end="")
PY
)"
}

sanitize_am_start_log_for_qa() {
  sanitize_android_qa_text_for_route_material
}

sanitize_android_qa_file_for_route_material() {
  local path="$1"
  local sanitized_path
  if [[ ! -f "$path" ]]; then
    return 0
  fi
  sanitized_path="$path.sanitized"
  sanitize_android_qa_text_for_route_material <"$path" >"$sanitized_path"
  mv "$sanitized_path" "$path"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --relay)
      MODE="relay"
      shift
      ;;
    --direct)
      MODE="direct"
      shift
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --serial)
      if [[ $# -lt 2 ]]; then
        echo "--serial requires a value." >&2
        exit 2
      fi
      REQUESTED_SERIAL="$2"
      shift 2
      ;;
    --keep-app-data)
      KEEP_APP_DATA=1
      shift
      ;;
    --external-relay-host)
      if [[ $# -lt 2 ]]; then
        echo "--external-relay-host requires a value." >&2
        exit 2
      fi
      EXTERNAL_RELAY_HOST="$2"
      shift 2
      ;;
    --external-relay-port)
      if [[ $# -lt 2 ]]; then
        echo "--external-relay-port requires a value." >&2
        exit 2
      fi
      EXTERNAL_RELAY_PORT="$2"
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
    --expect-chat-cancel)
      EXPECT_CHAT_CANCEL=1
      shift
      ;;
    --capture-ui-polish)
      CAPTURE_UI_POLISH=1
      shift
      ;;
    --live-backend)
      LIVE_BACKEND=1
      shift
      ;;
    --probe-external-relay-from-device)
      PROBE_EXTERNAL_RELAY_FROM_DEVICE=1
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
    --self-test-sanitize-am-start-log)
      SELF_TEST_SANITIZE_AM_START_LOG=1
      shift
      ;;
    --self-test-sanitize-android-qa-artifacts)
      SELF_TEST_SANITIZE_ANDROID_QA_ARTIFACTS=1
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

if [[ "$SELF_TEST_SANITIZE_AM_START_LOG" -eq 1 ]]; then
  printf '%s\n' "$AM_START_SANITIZER_SELF_TEST_MARKER"
  sanitize_am_start_log_for_qa
  exit 0
fi

if [[ "$SELF_TEST_SANITIZE_ANDROID_QA_ARTIFACTS" -eq 1 ]]; then
  printf '%s\n' "$ANDROID_QA_ARTIFACT_SANITIZER_SELF_TEST_MARKER"
  sanitize_android_qa_text_for_route_material
  exit 0
fi

if [[ ! -x "$ADB" ]]; then
  echo "adb not found at $ADB" >&2
  exit 2
fi

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "Java runtime not found at $JAVA_HOME/bin/java" >&2
  exit 2
fi

cd "$ROOT_DIR"

if [[ -n "$EXTERNAL_RELAY_HOST" ]]; then
  MODE="relay"
  EXTERNAL_RELAY_PORT="${EXTERNAL_RELAY_PORT:-43171}"
  if [[ "$EXTERNAL_RELAY_HOST" == *"://"* || "$EXTERNAL_RELAY_HOST" == *"/"* || "$EXTERNAL_RELAY_HOST" == *"@"* || "$EXTERNAL_RELAY_HOST" == *"?"* || "$EXTERNAL_RELAY_HOST" == *"#"* ]]; then
    echo "--external-relay-host must be a host or IP address, not a URL." >&2
    exit 2
  fi
  NORMALIZED_EXTERNAL_RELAY_HOST="$(printf '%s' "$EXTERNAL_RELAY_HOST" | tr '[:upper:]' '[:lower:]')"
  validate_external_relay_host_for_qr "$NORMALIZED_EXTERNAL_RELAY_HOST" "$ALLOW_PRIVATE_RELAY"
  if ! [[ "$EXTERNAL_RELAY_PORT" =~ ^[0-9]+$ ]] || (( EXTERNAL_RELAY_PORT < 1 || EXTERNAL_RELAY_PORT > 65535 )); then
    echo "--external-relay-port must be an integer in 1..65535." >&2
    exit 2
  fi
fi

if ! [[ "$CHAT_DELTA_TIMEOUT" =~ ^[0-9]+$ ]] || (( CHAT_DELTA_TIMEOUT < 1 || CHAT_DELTA_TIMEOUT > 600 )); then
  echo "--chat-delta-timeout must be an integer in 1..600 seconds." >&2
  exit 2
fi

free_port() {
  python3 - <<'PY'
import socket

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
}

wait_for_log() {
  local file="$1"
  local pattern="$2"
  local timeout="${3:-30}"
  local start
  start="$(date +%s)"
  while true; do
    if [[ -f "$file" ]] && grep -q "$pattern" "$file"; then
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for '$pattern' in $file" >&2
      echo "--- $file tail ---" >&2
      [[ -f "$file" ]] && tail -n 80 "$file" >&2
      return 1
    fi
    sleep 0.25
  done
}

count_log_matches() {
  local file="$1"
  local pattern="$2"
  if [[ ! -f "$file" ]]; then
    echo 0
    return 0
  fi
  grep -c "$pattern" "$file" || true
}

wait_for_log_match_count() {
  local file="$1"
  local pattern="$2"
  local expected_count="$3"
  local timeout="${4:-30}"
  local start
  local current_count
  start="$(date +%s)"
  while true; do
    current_count="$(count_log_matches "$file" "$pattern")"
    if (( current_count >= expected_count )); then
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for at least $expected_count '$pattern' entries in $file; saw $current_count" >&2
      echo "--- $file tail ---" >&2
      [[ -f "$file" ]] && tail -n 80 "$file" >&2
      return 1
    fi
    sleep 0.25
  done
}

check_tcp_connect() {
  local host="$1"
  local port="$2"
  local timeout="${3:-3}"
  python3 - "$host" "$port" "$timeout" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
timeout = float(sys.argv[3])

try:
    with socket.create_connection((host, port), timeout=timeout):
        pass
except OSError as error:
    print(f"Could not connect to {host}:{port}: {error}", file=sys.stderr)
    raise SystemExit(1)
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
    AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN="$token" \
      AETHERLINK_RELAY_ALLOCATION_TOKEN="$token" \
      "${args[@]}"
  else
    "${args[@]}"
  fi
}

diagnose_pairing_failure() {
  if [[ "$MODE" != "relay" ]]; then
    return 0
  fi

  echo "--- relay pairing diagnosis ---" >&2
  if grep -q "relay status=failed:" "$RUNTIME_LOG" 2>/dev/null; then
    echo "Runtime host failed to register with the relay. Check relay host, port, tunnel/VPN, and firewall." >&2
  elif grep -q "relay status=waiting_for_peer" "$RUNTIME_LOG" 2>/dev/null; then
    echo "Runtime host reached the relay and is waiting for the trusted device. Check that the device network can reach the relay host in the QR." >&2
  elif grep -q "relay status=ready" "$RUNTIME_LOG" 2>/dev/null; then
    echo "Relay matched the runtime host and trusted device. Pairing did not complete after relay match; inspect device logs and runtime protocol errors." >&2
  else
    echo "Runtime did not report relay readiness. Check RuntimeDevServer startup and relay configuration." >&2
  fi

  if [[ -n "$EXTERNAL_RELAY_HOST" ]]; then
    echo "External relay under test: $EXTERNAL_RELAY_HOST:$RELAY_PORT" >&2
  elif [[ -f "$RELAY_LOG" ]]; then
    echo "--- relay log tail ---" >&2
    tail -n 80 "$RELAY_LOG" >&2
  fi
}

dump_android_artifacts() {
  local prefix="$1"
  local screenshot="$WORK_DIR/${prefix}.png"
  local activity_dump="$WORK_DIR/${prefix}-activity.txt"
  local logcat_dump="$WORK_DIR/${prefix}-logcat.txt"

  "$ADB" -s "$SERIAL" exec-out screencap -p >"$screenshot" 2>/dev/null || true
  "$ADB" -s "$SERIAL" shell dumpsys activity activities >"$activity_dump" 2>/dev/null || true
  "$ADB" -s "$SERIAL" logcat -d -t 500 >"$logcat_dump" 2>/dev/null || true
  sanitize_android_qa_file_for_route_material "$activity_dump"
  sanitize_android_qa_file_for_route_material "$logcat_dump"

  echo "Android screenshot: $screenshot" >&2
  echo "Android activity dump: $activity_dump" >&2
  echo "Android logcat: $logcat_dump" >&2
  echo "--- filtered Android logcat tail ---" >&2
  grep -Ei 'localagentbridge|AetherLink|AndroidRuntime|FATAL|Exception|pairing|relay|ActivityTaskManager|am_start' "$logcat_dump" \
    | tail -n 120 >&2 || true
  diagnose_android_logcat "$logcat_dump"
}

diagnose_android_logcat() {
  local logcat_dump="$1"

  echo "--- Android pairing diagnosis ---" >&2
  if grep -q "Runtime connection failed code=" "$logcat_dump" 2>/dev/null; then
    grep "Runtime connection failed code=" "$logcat_dump" | tail -n 8 >&2 || true
    if grep -q "Runtime connection failed code=remote_route_unreachable diagnostic=route_diagnostic_relay_failed" "$logcat_dump" 2>/dev/null; then
      echo "Android handled the pairing QR and attempted the relay route, but the relay route was unreachable from the Android network." >&2
    elif grep -q "Runtime connection failed code=pairing_endpoint_unavailable" "$logcat_dump" 2>/dev/null; then
      echo "Android handled the pairing QR, but the QR did not contain a reachable direct or relay route." >&2
    else
      echo "Android handled the pairing QR and reported a runtime connection failure. Inspect the structured code/diagnostic line above." >&2
    fi
  elif grep -q "Connecting to runtime" "$logcat_dump" 2>/dev/null; then
    echo "Android started a runtime connection attempt, but no structured failure was logged before the smoke timeout." >&2
    grep "Connecting to runtime" "$logcat_dump" | tail -n 8 >&2 || true
  elif grep -q "ActivityTaskManager.*aetherlink://pair" "$logcat_dump" 2>/dev/null ||
    grep -q "am_start.*aetherlink://pair" "$logcat_dump" 2>/dev/null; then
    echo "Android launched the pairing deeplink, but no runtime connection attempt was observed in logcat." >&2
  else
    echo "No pairing deeplink or runtime route attempt was observed in the captured Android logcat." >&2
  fi
}

escape_remote_single_quoted() {
  python3 - "$1" <<'PY'
import sys

value = sys.argv[1]
print("'" + value.replace("'", "'\\''") + "'")
PY
}

dump_ui_xml() {
  local prefix="$1"
  local remote_path="/sdcard/aetherlink-${prefix}.xml"
  local local_path="$WORK_DIR/${prefix}.xml"

  "$ADB" -s "$SERIAL" shell "uiautomator dump $remote_path" >/dev/null 2>&1
  "$ADB" -s "$SERIAL" pull "$remote_path" "$local_path" >/dev/null 2>&1
  printf '%s\n' "$local_path"
}

node_center_by_content_description() {
  local xml_path="$1"
  local content_description="$2"
  local strategy="${3:-first}"
  python3 - "$xml_path" "$content_description" "$strategy" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET

xml_path, expected, strategy = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    root = ET.parse(xml_path).getroot()
except Exception:
    raise SystemExit(1)

bounds_pattern = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
candidates = []
for node in root.iter("node"):
    if node.attrib.get("content-desc") != expected:
        continue
    if strategy == "bottom-enabled" and node.attrib.get("enabled") == "false":
        continue
    bounds = node.attrib.get("bounds", "")
    match = bounds_pattern.fullmatch(bounds)
    if not match:
        continue
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        continue
    if strategy == "bottom-enabled":
        candidates.append((bottom, top, right, left))
        continue
    print(f"{(left + right) // 2} {(top + bottom) // 2}")
    raise SystemExit(0)
if candidates:
    bottom, top, right, left = max(candidates)
    print(f"{(left + right) // 2} {(top + bottom) // 2}")
    raise SystemExit(0)
raise SystemExit(1)
PY
}

node_center_by_localized_content_description() {
  local xml_path="$1"
  local string_name="$2"
  local strategy="${3:-first}"
  python3 - "$ROOT_DIR" "$xml_path" "$string_name" "$strategy" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root_dir = Path(sys.argv[1])
xml_path, string_name, strategy = sys.argv[2], sys.argv[3], sys.argv[4]
expected_values = set()
resources_dir = root_dir / "apps" / "android" / "app" / "src" / "main" / "res"
for strings_path in sorted(resources_dir.glob("values*/strings.xml")):
    try:
        strings_root = ET.parse(strings_path).getroot()
    except Exception:
        continue
    for item in strings_root.findall("string"):
        if item.attrib.get("name") != string_name:
            continue
        value = "".join(item.itertext()).strip()
        if value:
            expected_values.add(value)

if not expected_values:
    raise SystemExit(1)

try:
    root = ET.parse(xml_path).getroot()
except Exception:
    raise SystemExit(1)

bounds_pattern = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
candidates = []
for node in root.iter("node"):
    if node.attrib.get("content-desc") not in expected_values:
        continue
    if strategy == "bottom-enabled" and node.attrib.get("enabled") == "false":
        continue
    bounds = node.attrib.get("bounds", "")
    match = bounds_pattern.fullmatch(bounds)
    if not match:
        continue
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        continue
    if strategy == "bottom-enabled":
        candidates.append((bottom, top, right, left, node.attrib.get("content-desc", "")))
        continue
    print(f"{(left + right) // 2} {(top + bottom) // 2} {node.attrib.get('content-desc', '')}")
    raise SystemExit(0)
if candidates:
    bottom, top, right, left, matched = max(candidates)
    print(f"{(left + right) // 2} {(top + bottom) // 2} {matched}")
    raise SystemExit(0)
raise SystemExit(1)
PY
}

node_center_by_localized_text_or_content() {
  local xml_path="$1"
  local string_name="$2"
  local strategy="${3:-first}"
  python3 - "$ROOT_DIR" "$xml_path" "$string_name" "$strategy" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root_dir = Path(sys.argv[1])
xml_path, string_name, strategy = sys.argv[2], sys.argv[3], sys.argv[4]
expected_values = set()
resources_dir = root_dir / "apps" / "android" / "app" / "src" / "main" / "res"
for strings_path in sorted(resources_dir.glob("values*/strings.xml")):
    try:
        strings_root = ET.parse(strings_path).getroot()
    except Exception:
        continue
    for item in strings_root.findall("string"):
        if item.attrib.get("name") != string_name:
            continue
        value = "".join(item.itertext()).strip()
        if value:
            expected_values.add(value)

if not expected_values:
    raise SystemExit(1)

try:
    root = ET.parse(xml_path).getroot()
except Exception:
    raise SystemExit(1)

bounds_pattern = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
candidates = []
for node in root.iter("node"):
    matched = ""
    for attribute in ("text", "content-desc"):
        value = node.attrib.get(attribute, "")
        if value in expected_values:
            matched = value
            break
    if not matched:
        continue
    if strategy == "bottom-enabled" and node.attrib.get("enabled") == "false":
        continue
    bounds = node.attrib.get("bounds", "")
    match = bounds_pattern.fullmatch(bounds)
    if not match:
        continue
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        continue
    if strategy == "bottom-enabled":
        candidates.append((bottom, top, right, left, matched))
        continue
    print(f"{(left + right) // 2} {(top + bottom) // 2} {matched}")
    raise SystemExit(0)
if candidates:
    bottom, top, right, left, matched = max(candidates)
    print(f"{(left + right) // 2} {(top + bottom) // 2} {matched}")
    raise SystemExit(0)
raise SystemExit(1)
PY
}

node_center_by_localized_content_description_prefix() {
  local xml_path="$1"
  local string_name="$2"
  local strategy="${3:-first}"
  python3 - "$ROOT_DIR" "$xml_path" "$string_name" "$strategy" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root_dir = Path(sys.argv[1])
xml_path, string_name, strategy = sys.argv[2], sys.argv[3], sys.argv[4]
prefixes = set()
resources_dir = root_dir / "apps" / "android" / "app" / "src" / "main" / "res"
for strings_path in sorted(resources_dir.glob("values*/strings.xml")):
    try:
        strings_root = ET.parse(strings_path).getroot()
    except Exception:
        continue
    for item in strings_root.findall("string"):
        if item.attrib.get("name") != string_name:
            continue
        value = "".join(item.itertext()).strip()
        if not value:
            continue
        prefix = value.split("%", 1)[0].strip()
        if prefix:
            prefixes.add(prefix)
        prefixes.add(value)

if not prefixes:
    raise SystemExit(1)

try:
    root = ET.parse(xml_path).getroot()
except Exception:
    raise SystemExit(1)

bounds_pattern = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
candidates = []
for node in root.iter("node"):
    content_description = node.attrib.get("content-desc", "")
    matched = next((prefix for prefix in prefixes if prefix and prefix in content_description), "")
    if not matched:
        continue
    if strategy == "bottom-enabled" and node.attrib.get("enabled") == "false":
        continue
    bounds = node.attrib.get("bounds", "")
    match = bounds_pattern.fullmatch(bounds)
    if not match:
        continue
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        continue
    if strategy == "bottom-enabled":
        candidates.append((bottom, top, right, left, matched))
        continue
    print(f"{(left + right) // 2} {(top + bottom) // 2} {matched}")
    raise SystemExit(0)
if candidates:
    bottom, top, right, left, matched = max(candidates)
    print(f"{(left + right) // 2} {(top + bottom) // 2} {matched}")
    raise SystemExit(0)
raise SystemExit(1)
PY
}

node_center_by_enabled_edit_text() {
  local xml_path="$1"
  python3 - "$xml_path" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET

xml_path = sys.argv[1]
try:
    root = ET.parse(xml_path).getroot()
except Exception:
    raise SystemExit(1)

bounds_pattern = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
candidates = []
for node in root.iter("node"):
    if node.attrib.get("class") != "android.widget.EditText":
        continue
    if node.attrib.get("enabled") == "false":
        continue
    bounds = node.attrib.get("bounds", "")
    match = bounds_pattern.fullmatch(bounds)
    if not match:
        continue
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        continue
    candidates.append((bottom, top, right, left))
if candidates:
    bottom, top, right, left = max(candidates)
    print(f"{(left + right) // 2} {(top + bottom) // 2}")
    raise SystemExit(0)
raise SystemExit(1)
PY
}

ui_xml_contains_text() {
  local xml_path="$1"
  local expected_text="$2"
  python3 - "$xml_path" "$expected_text" <<'PY'
import sys
import xml.etree.ElementTree as ET

xml_path, expected = sys.argv[1], sys.argv[2]
try:
    root = ET.parse(xml_path).getroot()
except Exception:
    raise SystemExit(1)

for node in root.iter("node"):
    for attribute in ("text", "content-desc"):
        value = node.attrib.get(attribute, "")
        if expected and expected in value:
            raise SystemExit(0)
raise SystemExit(1)
PY
}

assert_reconnect_screen_not_route_recovery() {
  local xml_path
  xml_path="$(dump_ui_xml "reconnect-post-health")"
  for unexpected_text in \
    "Scan latest QR" \
    "Scan the latest AetherLink Runtime QR with connection details." \
    "Scan the latest AetherLink Runtime QR before sending."; do
    if ui_xml_contains_text "$xml_path" "$unexpected_text"; then
      echo "Reconnect reached runtime.health but the UI fell back to latest-QR route recovery: $unexpected_text" >&2
      echo "Reconnect UI XML: $xml_path" >&2
      return 1
    fi
  done
  return 0
}

tap_content_description() {
  local content_description="$1"
  local timeout="${2:-10}"
  local strategy="${3:-first}"
  local start
  local xml_path
  local coordinates
  start="$(date +%s)"

  while true; do
    xml_path="$(dump_ui_xml "ui-$(date +%s)-$RANDOM")"
    if coordinates="$(node_center_by_content_description "$xml_path" "$content_description" "$strategy" 2>/dev/null)"; then
      echo "Tapping '$content_description' at $coordinates"
      "$ADB" -s "$SERIAL" shell "input tap $coordinates"
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for Android UI node with content description '$content_description'" >&2
      echo "Last UI XML: $xml_path" >&2
      return 1
    fi
    sleep 0.25
  done
}

tap_localized_content_description() {
  local string_name="$1"
  local label="$2"
  local timeout="${3:-10}"
  local strategy="${4:-first}"
  local start
  local xml_path
  local result
  local coordinates
  local matched_label
  start="$(date +%s)"

  while true; do
    xml_path="$(dump_ui_xml "ui-$(date +%s)-$RANDOM")"
    if result="$(node_center_by_localized_content_description "$xml_path" "$string_name" "$strategy" 2>/dev/null)"; then
      coordinates="$(printf '%s\n' "$result" | awk '{ print $1 " " $2 }')"
      matched_label="$(printf '%s\n' "$result" | cut -d' ' -f3-)"
      echo "Tapping localized '$label' ('$matched_label') at $coordinates"
      "$ADB" -s "$SERIAL" shell "input tap $coordinates"
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for Android UI node with localized content description '$label' from string '$string_name'" >&2
      echo "Last UI XML: $xml_path" >&2
      return 1
    fi
    sleep 0.25
  done
}

tap_localized_text_or_content() {
  local string_name="$1"
  local label="$2"
  local timeout="${3:-10}"
  local strategy="${4:-first}"
  local start
  local xml_path
  local result
  local coordinates
  local matched_label
  start="$(date +%s)"

  while true; do
    xml_path="$(dump_ui_xml "ui-$(date +%s)-$RANDOM")"
    if result="$(node_center_by_localized_text_or_content "$xml_path" "$string_name" "$strategy" 2>/dev/null)"; then
      coordinates="$(printf '%s\n' "$result" | awk '{ print $1 " " $2 }')"
      matched_label="$(printf '%s\n' "$result" | cut -d' ' -f3-)"
      echo "Tapping localized '$label' text/content ('$matched_label') at $coordinates"
      "$ADB" -s "$SERIAL" shell "input tap $coordinates"
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for Android UI node with localized text/content '$label' from string '$string_name'" >&2
      echo "Last UI XML: $xml_path" >&2
      return 1
    fi
    sleep 0.25
  done
}

tap_localized_model_picker() {
  local timeout="${1:-10}"
  local start
  local xml_path
  local result
  local coordinates
  local matched_label
  start="$(date +%s)"

  while true; do
    xml_path="$(dump_ui_xml "ui-$(date +%s)-$RANDOM")"
    if result="$(node_center_by_localized_content_description_prefix "$xml_path" "chat_model_picker_summary_selected" 2>/dev/null)"; then
      coordinates="$(printf '%s\n' "$result" | awk '{ print $1 " " $2 }')"
      matched_label="$(printf '%s\n' "$result" | cut -d' ' -f3-)"
      echo "Tapping localized model picker ('$matched_label') at $coordinates"
      "$ADB" -s "$SERIAL" shell "input tap $coordinates"
      return 0
    fi
    if result="$(node_center_by_localized_content_description "$xml_path" "chat_model_picker_summary" 2>/dev/null)"; then
      coordinates="$(printf '%s\n' "$result" | awk '{ print $1 " " $2 }')"
      matched_label="$(printf '%s\n' "$result" | cut -d' ' -f3-)"
      echo "Tapping localized model picker ('$matched_label') at $coordinates"
      "$ADB" -s "$SERIAL" shell "input tap $coordinates"
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for localized Android model picker" >&2
      echo "Last UI XML: $xml_path" >&2
      return 1
    fi
    sleep 0.25
  done
}

tap_chat_input() {
  local timeout="${1:-15}"
  local start
  local xml_path
  local result
  local coordinates
  local matched_label
  start="$(date +%s)"

  while true; do
    xml_path="$(dump_ui_xml "ui-$(date +%s)-$RANDOM")"
    if result="$(node_center_by_localized_content_description "$xml_path" "message" "bottom-enabled" 2>/dev/null)"; then
      coordinates="$(printf '%s\n' "$result" | awk '{ print $1 " " $2 }')"
      matched_label="$(printf '%s\n' "$result" | cut -d' ' -f3-)"
      echo "Tapping localized chat input ('$matched_label') at $coordinates"
      "$ADB" -s "$SERIAL" shell "input tap $coordinates"
      return 0
    fi
    if coordinates="$(node_center_by_enabled_edit_text "$xml_path" 2>/dev/null)"; then
      echo "Tapping enabled EditText chat input at $coordinates"
      "$ADB" -s "$SERIAL" shell "input tap $coordinates"
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      echo "Timed out waiting for localized Android chat input or enabled EditText" >&2
      echo "Last UI XML: $xml_path" >&2
      return 1
    fi
    sleep 0.25
  done
}

wait_for_log_match_count_quiet() {
  local file="$1"
  local pattern="$2"
  local expected_count="$3"
  local timeout="${4:-3}"
  local start
  local current_count
  start="$(date +%s)"
  while true; do
    current_count="$(count_log_matches "$file" "$pattern")"
    if (( current_count >= expected_count )); then
      return 0
    fi
    if (( $(date +%s) - start >= timeout )); then
      return 1
    fi
    sleep 0.25
  done
}

android_input_shown() {
  "$ADB" -s "$SERIAL" shell dumpsys input_method 2>/dev/null | grep -q "mInputShown=true"
}

adb_input_text() {
  local text="$1"
  local escaped
  escaped="$(python3 - "$text" <<'PY'
import sys

value = sys.argv[1]
value = value.replace("%", "%25")
value = value.replace(" ", "%s")
value = value.replace("'", "")
value = value.replace('"', "")
print(value)
PY
)"
  "$ADB" -s "$SERIAL" shell "input text '$escaped'"
}

bring_android_app_to_foreground() {
  "$ADB" -s "$SERIAL" shell \
    "monkey -p $PACKAGE_NAME -c android.intent.category.LAUNCHER 1" \
    >/dev/null 2>&1 || true
  sleep 1
}

tap_send_message_until_observed() {
  local expected_count
  local attempt
  local xml_path
  CHAT_SEND_TAP_FAILURE="chat-send-not-observed"
  expected_count=$(( $(count_log_matches "$RUNTIME_LOG" "chat.send") + 1 ))

  for attempt in 1 2 3; do
    if ! tap_localized_content_description "content_desc_send" "send message" 5 "bottom-enabled"; then
      if android_input_shown; then
        echo "Localized send message control is not visible while the input method is shown; closing input method before retry"
        "$ADB" -s "$SERIAL" shell "input keyevent KEYCODE_BACK" >/dev/null 2>&1 || true
        sleep 0.5
        continue
      fi
      CHAT_SEND_TAP_FAILURE="chat-send-missing"
      return 1
    fi
    if wait_for_log_match_count_quiet "$RUNTIME_LOG" "chat.send" "$expected_count" 3; then
      return 0
    fi
    xml_path="$(dump_ui_xml "chat-send-retry-$attempt")"
    echo "No chat.send observed after Send tap attempt $attempt; retry UI XML: $xml_path" >&2
    sleep 0.5
  done

  wait_for_log_match_count "$RUNTIME_LOG" "chat.send" "$expected_count" 6
}

run_chat_cancel_smoke() {
  echo "Running physical Android chat send/cancel UI smoke"

  if ! wait_for_log "$RUNTIME_LOG" "models.list" 30; then
    dump_android_artifacts "chat-models-list-missing"
    exit 13
  fi
  bring_android_app_to_foreground

  if ! tap_chat_input 15; then
    dump_android_artifacts "chat-input-missing"
    exit 14
  fi
  adb_input_text "$CHAT_TEXT"
  sleep 0.25

  if ! tap_send_message_until_observed; then
    dump_android_artifacts "$CHAT_SEND_TAP_FAILURE"
    if [[ "$CHAT_SEND_TAP_FAILURE" == "chat-send-missing" ]]; then
      exit 15
    fi
    exit 16
  fi
  if ! wait_for_log "$RUNTIME_LOG" "chat.delta" "$CHAT_DELTA_TIMEOUT"; then
    dump_android_artifacts "chat-delta-not-observed"
    exit 17
  fi
  if ! tap_localized_content_description "content_desc_cancel_generation" "cancel generation" 5; then
    dump_android_artifacts "chat-cancel-button-missing"
    exit 18
  fi
  if ! wait_for_log "$RUNTIME_LOG" "chat.cancel" 15; then
    dump_android_artifacts "chat-cancel-not-observed"
    exit 19
  fi
  if ! wait_for_log "$RUNTIME_LOG" "chat.done" 15; then
    dump_android_artifacts "chat-done-not-observed"
    exit 20
  fi

  CHAT_SCREENSHOT="$WORK_DIR/aetherlink-chat-cancel-smoke.png"
  "$ADB" -s "$SERIAL" exec-out screencap -p >"$CHAT_SCREENSHOT" || true
  echo "Chat/cancel screenshot: $CHAT_SCREENSHOT"
}

capture_ui_artifact() {
  local prefix="$1"
  local label="$2"
  local screenshot="$WORK_DIR/${prefix}.png"
  local xml_path

  xml_path="$(dump_ui_xml "$prefix")"
  "$ADB" -s "$SERIAL" exec-out screencap -p >"$screenshot" || true
  UI_CAPTURE_LAST_XML="$xml_path"
  echo "Captured $label screenshot: $screenshot"
  echo "Captured $label UI XML: $xml_path"
}

run_ui_polish_capture() {
  echo "Capturing physical Android UI polish screenshots"

  if ! wait_for_log "$RUNTIME_LOG" "models.list" 30; then
    dump_android_artifacts "ui-polish-models-list-missing"
    exit 24
  fi

  "$ADB" -s "$SERIAL" shell "input keyevent KEYCODE_BACK" >/dev/null 2>&1 || true
  sleep 0.5
  bring_android_app_to_foreground

  capture_ui_artifact "aetherlink-ui-chat" "chat screen"

  if ! tap_localized_model_picker 10; then
    dump_android_artifacts "ui-polish-model-picker-missing"
    exit 25
  fi
  sleep 0.75
  capture_ui_artifact "aetherlink-ui-model-selector" "model selector"

  "$ADB" -s "$SERIAL" shell "input keyevent KEYCODE_BACK" >/dev/null 2>&1 || true
  sleep 0.5
  if ! tap_localized_content_description "content_desc_open_navigation" "open navigation" 10; then
    bring_android_app_to_foreground
    if ! tap_localized_content_description "content_desc_open_navigation" "open navigation" 10; then
      dump_android_artifacts "ui-polish-drawer-button-missing"
      exit 26
    fi
  fi
  sleep 0.75
  capture_ui_artifact "aetherlink-ui-drawer" "navigation drawer"

  if ! tap_localized_text_or_content "tab_settings" "settings" 10; then
    dump_android_artifacts "ui-polish-settings-tab-missing"
    exit 27
  fi
  sleep 1
  capture_ui_artifact "aetherlink-ui-settings" "settings screen"

  "$ADB" -s "$SERIAL" shell "input keyevent HOME" >/dev/null 2>&1 || true
  sleep 1
  capture_ui_artifact "aetherlink-ui-launcher" "launcher"
  if ui_xml_contains_text "$UI_CAPTURE_LAST_XML" "AetherLink"; then
    echo "Launcher icon check: AetherLink label visible."
  else
    echo "Launcher icon check: AetherLink label not visible on the current launcher page; captured launcher XML for review." >&2
  fi

  bring_android_app_to_foreground
  echo "UI polish capture: chat, drawer, model selector, settings, and launcher screenshots/XML saved in $WORK_DIR."
}

relaunch_android_app_without_clearing_data() {
  local relaunch_log="$WORK_DIR/reconnect-relaunch.txt"

  echo "Force-stopping Android app without clearing data"
  "$ADB" -s "$SERIAL" shell "am force-stop $PACKAGE_NAME" >/dev/null

  if [[ "$REVERSE_RUNTIME" -eq 1 ]]; then
    echo "Refreshing adb reverse for runtime port $PORT before relaunch"
    "$ADB" -s "$SERIAL" reverse "tcp:$PORT" "tcp:$PORT" >/dev/null
  fi
  if [[ "$REVERSE_RELAY" -eq 1 ]]; then
    echo "Refreshing adb reverse for relay port $RELAY_PORT before relaunch"
    "$ADB" -s "$SERIAL" reverse "tcp:$RELAY_PORT" "tcp:$RELAY_PORT" >/dev/null
  fi

  echo "Relaunching Android app to verify saved trusted route reconnect"
  if ! "$ADB" -s "$SERIAL" shell \
    "monkey -p $PACKAGE_NAME -c android.intent.category.LAUNCHER 1" \
    >"$relaunch_log" 2>&1; then
    cat "$relaunch_log" >&2
    dump_android_artifacts "reconnect-relaunch-failed"
    exit 11
  fi
  cat "$relaunch_log"
}

DEVICE_LINES="$("$ADB" devices | awk 'NR > 1 && NF >= 2 { print $1 " " $2 }')"
if [[ -z "$DEVICE_LINES" ]]; then
  echo "No Android device found. Connect a phone with USB debugging enabled." >&2
  exit 3
fi

if [[ -n "$REQUESTED_SERIAL" ]]; then
  DEVICE_LINES="$(printf '%s\n' "$DEVICE_LINES" | awk -v serial="$REQUESTED_SERIAL" '$1 == serial { print $1 " " $2 }')"
  if [[ -z "$DEVICE_LINES" ]]; then
    echo "Requested Android device '$REQUESTED_SERIAL' was not found." >&2
    "$ADB" devices -l >&2
    exit 5
  fi
fi

if echo "$DEVICE_LINES" | awk '$2 == "unauthorized" { found = 1 } END { exit found ? 0 : 1 }'; then
  echo "Android device is connected but unauthorized." >&2
  "$ADB" devices -l >&2
  exit 4
fi

SERIAL="$(echo "$DEVICE_LINES" | awk '$2 == "device" { print $1; exit }')"
if [[ -z "$SERIAL" ]]; then
  echo "No authorized Android device is available." >&2
  "$ADB" devices -l >&2
  exit 5
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-android-pairing.XXXXXX")"
RUNTIME_LOG="$WORK_DIR/runtime.log"
RELAY_LOG="$WORK_DIR/relay.log"
TRUSTED_DEVICES_FILE="$WORK_DIR/trusted-devices.json"
RUNTIME_IDENTITY_FILE="$WORK_DIR/runtime-identity.json"
PORT="$(free_port)"
RELAY_PORT="$(free_port)"
RUNTIME_PID=""
RELAY_PID=""
REVERSE_RUNTIME=0
REVERSE_RELAY=0

cleanup() {
  set +e
  if [[ -n "${SERIAL:-}" && -n "${PORT:-}" ]]; then
    if [[ "${REVERSE_RUNTIME:-0}" -eq 1 ]]; then
      "$ADB" -s "$SERIAL" reverse --remove "tcp:$PORT" >/dev/null 2>&1
    fi
  fi
  if [[ -n "${SERIAL:-}" && -n "${RELAY_PORT:-}" ]]; then
    if [[ "${REVERSE_RELAY:-0}" -eq 1 ]]; then
      "$ADB" -s "$SERIAL" reverse --remove "tcp:$RELAY_PORT" >/dev/null 2>&1
    fi
  fi
  if [[ -n "$RUNTIME_PID" ]]; then
    kill "$RUNTIME_PID" >/dev/null 2>&1
    wait "$RUNTIME_PID" >/dev/null 2>&1
  fi
  if [[ -n "$RELAY_PID" ]]; then
    kill "$RELAY_PID" >/dev/null 2>&1
    wait "$RELAY_PID" >/dev/null 2>&1
  fi
}
trap cleanup EXIT

echo "Using Android device $SERIAL"
echo "Working directory: $WORK_DIR"
echo "Building RuntimeDevServer"
swift build --product RuntimeDevServer >/dev/null
RUNTIME_BIN="$(swift build --show-bin-path)/RuntimeDevServer"
RELAY_BIN=""
if [[ "$MODE" == "relay" && -z "$EXTERNAL_RELAY_HOST" ]]; then
  echo "Building AetherLinkRelay"
  swift build --product AetherLinkRelay >/dev/null
  RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
fi

if [[ "$MODE" == "relay" && -z "$EXTERNAL_RELAY_HOST" ]]; then
  echo "Starting local allocation-required diagnostic relay on loopback port $RELAY_PORT"
  RELAY_ARGS=("$RELAY_BIN" --host 127.0.0.1 --port "$RELAY_PORT" --require-allocation)
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    export AETHERLINK_RELAY_ALLOCATION_TOKEN="$ALLOCATION_TOKEN"
  fi
  "${RELAY_ARGS[@]}" >"$RELAY_LOG" 2>&1 &
  RELAY_PID="$!"
  wait_for_log "$RELAY_LOG" "development relay listening" 10
elif [[ "$MODE" == "relay" ]]; then
  RELAY_PORT="$EXTERNAL_RELAY_PORT"
  echo "Using external allocation-capable development relay at $EXTERNAL_RELAY_HOST:$RELAY_PORT"
  echo "Checking runtime-host TCP reachability to external relay"
  if ! check_tcp_connect "$EXTERNAL_RELAY_HOST" "$RELAY_PORT" 3; then
    echo "External relay is not reachable from the runtime host. Start the relay or fix the public/VPN/tunnel route before running this smoke." >&2
    exit 9
  fi
  echo "Checking external relay allocation API"
  if ! check_relay_allocation "$EXTERNAL_RELAY_HOST" "$RELAY_PORT" "$ALLOCATION_TOKEN" 5; then
    echo "External relay is reachable but did not accept AetherLink allocation. Start AetherLinkRelay --require-allocation, pass the required --allocation-token, or use the correct relay endpoint." >&2
    exit 10
  fi
  if [[ "$PROBE_EXTERNAL_RELAY_FROM_DEVICE" -eq 1 ]]; then
    echo "Checking Android-device TCP reachability to external relay without adb reverse"
    DEVICE_RELAY_PROBE_JSON="$WORK_DIR/android-relay-reachability.json"
    if ! script/android_relay_reachability_probe.sh \
      --serial "$SERIAL" \
      --host "$EXTERNAL_RELAY_HOST" \
      --port "$RELAY_PORT" \
      --timeout 5 \
      --json "$DEVICE_RELAY_PROBE_JSON" \
      --include-network-summary; then
      echo "Android cannot reach the external relay directly. Fix the public/VPN/tunnel/private-overlay route before treating this as a QR pairing failure." >&2
      exit 21
    fi
  fi
fi

echo "Starting RuntimeDevServer for $MODE QR mode on local diagnostic port $PORT"
RUNTIME_ENV=(
  "LOCAL_AGENT_BRIDGE_PORT=$PORT"
  "AETHERLINK_DEV_PAIRING=1"
  "AETHERLINK_DEV_PAIRING_TTL_SECONDS=180"
  "AETHERLINK_DEV_TRUSTED_DEVICES_FILE=$TRUSTED_DEVICES_FILE"
  "AETHERLINK_DEV_RUNTIME_IDENTITY_FILE=$RUNTIME_IDENTITY_FILE"
  "AETHERLINK_DEV_DISABLE_BONJOUR=1"
)
if [[ "$LIVE_BACKEND" -eq 0 ]]; then
  RUNTIME_ENV+=("LOCAL_AGENT_BRIDGE_MOCK_BACKEND=1")
fi
if [[ "$EXPECT_CHAT_CANCEL" -eq 1 && "$LIVE_BACKEND" -eq 0 ]]; then
  RUNTIME_ENV+=("AETHERLINK_DEV_MOCK_CHUNK_DELAY_MS=5000")
fi
if [[ "$MODE" == "relay" ]]; then
  RELAY_HOST="${EXTERNAL_RELAY_HOST:-127.0.0.1}"
  RUNTIME_ENV+=(
    "AETHERLINK_BOOTSTRAP_RELAY_HOST=$RELAY_HOST"
    "AETHERLINK_BOOTSTRAP_RELAY_PORT=$RELAY_PORT"
  )
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    RUNTIME_ENV+=("AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN=$ALLOCATION_TOKEN")
  fi
fi

env "${RUNTIME_ENV[@]}" "$RUNTIME_BIN" >"$RUNTIME_LOG" 2>&1 &
RUNTIME_PID="$!"
wait_for_log "$RUNTIME_LOG" "AETHERLINK_DEV_PAIRING_INFO" 15

PAIRING_INFO_JSON="$(python3 - "$RUNTIME_LOG" <<'PY'
import sys

marker = "AETHERLINK_DEV_PAIRING_INFO "
for line in open(sys.argv[1], encoding="utf-8"):
    if marker in line:
        print(line.split(marker, 1)[1].strip())
        raise SystemExit(0)
raise SystemExit(1)
PY
)"

python3 - "$PAIRING_INFO_JSON" "$MODE" "$EXTERNAL_RELAY_HOST" "$ALLOW_DIRECT_FALLBACK" <<'PY'
import json
import sys

info = json.loads(sys.argv[1])
mode = sys.argv[2]
external_relay_host = sys.argv[3]
allow_direct_fallback = sys.argv[4] == "1"

required_relay_fields = [
    "relay_host",
    "relay_port",
    "relay_id",
    "relay_secret",
    "relay_expires_at",
    "relay_nonce",
]
optional_relay_fields = ["relay_scope"]
if mode == "relay":
    missing = [field for field in required_relay_fields if field not in info]
    if missing:
        raise SystemExit(f"Pairing info missing relay field(s): {', '.join(missing)}")
    if external_relay_host and info.get("relay_host") != external_relay_host:
        raise SystemExit(
            f"Pairing info relay_host={info.get('relay_host')!r} does not match external relay {external_relay_host!r}"
        )
    has_direct_host = "host" in info
    has_direct_port = "port" in info
    if (has_direct_host or has_direct_port) and not allow_direct_fallback:
        raise SystemExit("Relay pairing info must not include direct host/port unless explicitly testing direct mode")
    if allow_direct_fallback and (has_direct_host != has_direct_port):
        raise SystemExit("Mixed-route relay pairing info must include both direct host and direct port")
    if allow_direct_fallback and has_direct_port:
        try:
            direct_port = int(info["port"])
        except (TypeError, ValueError):
            raise SystemExit("Mixed-route relay pairing info contains invalid direct port")
        if direct_port < 1 or direct_port > 65535:
            raise SystemExit("Mixed-route relay pairing info direct port must be in 1..65535")
else:
    if any(field in info for field in required_relay_fields + optional_relay_fields):
        raise SystemExit("Direct pairing info unexpectedly includes relay fields")
PY

PAIRING_RELAY_ID=""
if [[ "$MODE" == "relay" ]]; then
  PAIRING_RELAY_ID="$(python3 - "$PAIRING_INFO_JSON" <<'PY'
import json
import sys

info = json.loads(sys.argv[1])
print(info.get("relay_id") or "")
PY
)"
fi

PAIRING_URI_FROM_LOG="$(python3 - "$RUNTIME_LOG" <<'PY'
import sys

compact_marker = "AETHERLINK_DEV_PAIRING_COMPACT_URI "
canonical_marker = "AETHERLINK_DEV_PAIRING_URI "
compact_uri = None
canonical_uri = None
for line in open(sys.argv[1], encoding="utf-8"):
    if compact_marker in line:
        compact_uri = line.split(compact_marker, 1)[1].strip()
    elif canonical_marker in line:
        canonical_uri = line.split(canonical_marker, 1)[1].strip()
print(compact_uri or canonical_uri or "")
PY
)"

if [[ -n "$PAIRING_URI_FROM_LOG" ]]; then
  PAIRING_URI="$PAIRING_URI_FROM_LOG"
else
  PAIRING_URI="$(python3 - "$PAIRING_INFO_JSON" <<'PY'
import json
import sys
import urllib.parse

info = json.loads(sys.argv[1])
canonical_values = {
    "runtime_device_id": info.get("runtime_device_id") or info.get("mac_device_id"),
    "runtime_name": info.get("runtime_name") or info.get("mac_name"),
    "runtime_key_fingerprint": info.get("runtime_key_fingerprint") or info.get("fingerprint"),
}
keys = [
    "pairing_nonce",
    "pairing_code",
    "runtime_device_id",
    "runtime_name",
    "runtime_public_key",
    "runtime_key_fingerprint",
    "route_token",
    "host",
    "port",
    "relay_host",
    "relay_port",
    "relay_id",
    "relay_secret",
    "relay_expires_at",
    "relay_nonce",
    "relay_scope",
]
params = [("version", "1")]
for key in keys:
    value = canonical_values.get(key)
    if value is None:
        value = info.get(key)
    if value is not None:
        params.append((key, str(value)))
print("aetherlink://pair?" + urllib.parse.urlencode(params))
PY
)"
fi

if [[ "$MODE" == "direct" || -z "$EXTERNAL_RELAY_HOST" ]]; then
  echo "Configuring adb reverse for runtime port $PORT"
  "$ADB" -s "$SERIAL" reverse "tcp:$PORT" "tcp:$PORT" >/dev/null
  REVERSE_RUNTIME=1
fi
if [[ "$MODE" == "relay" && -z "$EXTERNAL_RELAY_HOST" ]]; then
  echo "Configuring adb reverse for relay port $RELAY_PORT"
  "$ADB" -s "$SERIAL" reverse "tcp:$RELAY_PORT" "tcp:$RELAY_PORT" >/dev/null
  REVERSE_RELAY=1
fi
if [[ "$REVERSE_RUNTIME" -eq 1 || "$REVERSE_RELAY" -eq 1 ]]; then
  echo "--- adb reverse mappings ---"
  "$ADB" -s "$SERIAL" reverse --list
else
  echo "Skipping adb reverse; Android must reach relay $EXTERNAL_RELAY_HOST:$RELAY_PORT directly."
fi

if [[ "$MODE" == "relay" && -n "$EXTERNAL_RELAY_HOST" && "$PROBE_EXTERNAL_RELAY_FROM_DEVICE" -eq 1 ]]; then
  if [[ -z "$PAIRING_RELAY_ID" ]]; then
    echo "Pairing info did not include relay_id; cannot run Android route-level relay readiness probe." >&2
    exit 22
  fi
  echo "Waiting for runtime host to register with relay before route-level device probe"
  wait_for_log "$RUNTIME_LOG" "relay status=waiting_for_peer" 15
  echo "Checking Android-device relay route readiness without adb reverse"
  DEVICE_RELAY_ROUTE_PROBE_JSON="$WORK_DIR/android-relay-route-readiness.json"
  if ! script/android_relay_reachability_probe.sh \
    --serial "$SERIAL" \
    --host "$EXTERNAL_RELAY_HOST" \
    --port "$RELAY_PORT" \
    --relay-id "$PAIRING_RELAY_ID" \
    --timeout 5 \
    --json "$DEVICE_RELAY_ROUTE_PROBE_JSON" \
    --include-network-summary; then
    echo "Android can open the relay endpoint only if TCP probe passed, but the QR relay route is not ready for this relay_id. Regenerate the QR after the runtime host is waiting on the relay." >&2
    exit 23
  fi
fi

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  echo "Installing current Android debug APK"
  ANDROID_HOME="$ANDROID_HOME" JAVA_HOME="$JAVA_HOME" ./gradlew --no-daemon :app:installDebug --console=plain >/dev/null
fi

if [[ "$KEEP_APP_DATA" -eq 0 ]]; then
  echo "Clearing app data for a clean pairing smoke"
  "$ADB" -s "$SERIAL" shell "pm clear $PACKAGE_NAME" >/dev/null
fi

REMOTE_URI="$(escape_remote_single_quoted "$PAIRING_URI")"
echo "Injecting pairing URI through Android VIEW intent"
"$ADB" -s "$SERIAL" logcat -c >/dev/null || true
AM_START_LOG="$WORK_DIR/am-start.txt"
RAW_AM_START_LOG="$WORK_DIR/am-start.raw.txt"
if ! "$ADB" -s "$SERIAL" shell \
  "am start -W -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d $REMOTE_URI -p $PACKAGE_NAME" \
  >"$RAW_AM_START_LOG" 2>&1; then
  sanitize_am_start_log_for_qa <"$RAW_AM_START_LOG" >"$AM_START_LOG"
  rm -f "$RAW_AM_START_LOG"
  cat "$AM_START_LOG" >&2
  dump_android_artifacts "pairing-am-start-failed"
  exit 6
fi
sanitize_am_start_log_for_qa <"$RAW_AM_START_LOG" >"$AM_START_LOG"
rm -f "$RAW_AM_START_LOG"
cat "$AM_START_LOG"

if ! wait_for_log "$RUNTIME_LOG" "Development pairing accepted" 30; then
  diagnose_pairing_failure
  dump_android_artifacts "pairing-not-accepted"
  exit 7
fi
if ! wait_for_log "$RUNTIME_LOG" "runtime.health" 30; then
  dump_android_artifacts "pairing-health-missing"
  exit 8
fi

if [[ "$EXPECT_CHAT_CANCEL" -eq 1 ]]; then
  run_chat_cancel_smoke
fi

if [[ "$EXPECT_RECONNECT" -eq 1 ]]; then
  FIRST_HEALTH_COUNT="$(count_log_matches "$RUNTIME_LOG" "runtime.health")"
  EXPECTED_HEALTH_COUNT=$(( FIRST_HEALTH_COUNT + 1 ))
  FIRST_MODEL_LIST_COUNT="$(count_log_matches "$RUNTIME_LOG" "received type=models.list")"
  EXPECTED_MODEL_LIST_COUNT=$(( FIRST_MODEL_LIST_COUNT + 1 ))
  relaunch_android_app_without_clearing_data
  if ! wait_for_log_match_count "$RUNTIME_LOG" "runtime.health" "$EXPECTED_HEALTH_COUNT" 30; then
    dump_android_artifacts "reconnect-health-missing"
    exit 12
  fi
  if ! wait_for_log_match_count "$RUNTIME_LOG" "received type=models.list" "$EXPECTED_MODEL_LIST_COUNT" 30; then
    dump_android_artifacts "reconnect-model-list-missing"
    exit 22
  fi
  sleep 1
  if ! assert_reconnect_screen_not_route_recovery; then
    dump_android_artifacts "reconnect-route-recovery-ui"
    exit 23
  fi
fi

if [[ "$CAPTURE_UI_POLISH" -eq 1 ]]; then
  run_ui_polish_capture
fi

SCREENSHOT="$WORK_DIR/aetherlink-pairing-smoke.png"
"$ADB" -s "$SERIAL" exec-out screencap -p >"$SCREENSHOT" || true

echo "OK: Android pairing deeplink smoke passed in $MODE mode."
if [[ "$EXPECT_RECONNECT" -eq 1 ]]; then
  echo "Reconnect check: observed a second runtime.health after app relaunch."
fi
if [[ "$EXPECT_CHAT_CANCEL" -eq 1 ]]; then
  echo "Chat/cancel check: observed chat.send, chat.delta, chat.cancel, and chat.done through the physical Android UI."
fi
if [[ "$CAPTURE_UI_POLISH" -eq 1 ]]; then
  echo "UI polish capture: saved chat, drawer, model selector, settings, and launcher PNG/XML artifacts."
fi
echo "Runtime log: $RUNTIME_LOG"
if [[ "$MODE" == "relay" ]]; then
  if [[ -n "$EXTERNAL_RELAY_HOST" ]]; then
    echo "External relay: $EXTERNAL_RELAY_HOST:$RELAY_PORT"
  else
    echo "Relay log: $RELAY_LOG"
  fi
fi
echo "Screenshot: $SCREENSHOT"
