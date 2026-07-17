#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo
echo "==> python3 script/check_runtime_python_sandbox_review.py"
python3 script/check_runtime_python_sandbox_review.py
echo
echo "==> python3 -m unittest script/test_runtime_python_sandbox_review.py"
python3 -m unittest script/test_runtime_python_sandbox_review.py

DEFAULT_JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export JAVA_HOME="${JAVA_HOME:-$DEFAULT_JAVA_HOME}"
TEMP_DIRS=()

cleanup_temp_dirs() {
  local temp_dir
  set +u
  for temp_dir in "${TEMP_DIRS[@]}"; do
    if [[ -d "$temp_dir" && "$(basename "$temp_dir")" == aetherlink-no-device-qr.* ]]; then
      rm -rf "$temp_dir"
    fi
  done
  set -u
}

trap cleanup_temp_dirs EXIT

run() {
  echo
  echo "==> $*"
  "$@"
}

check_android_authenticated_read_authority_junit() {
  python3 - <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

report_path = Path(
    "apps/android/app/build/test-results/testDebugUnitTest/"
    "TEST-com.localagentbridge.android.runtime.RuntimeClientViewModelTest.xml"
)
expected_names = (
    "runtimeDocumentCatalogRequiresExactCurrentAuthorityAndConsumesOnce",
    "runtimeDocumentSearchRequiresExactCurrentAuthorityAndConsumesOnce",
    "delayedOldDocumentSendFailureCannotCloseReplacementRequest",
    "pendingDocumentAuthorityClearsOnDisconnectRevocationAndViewModelClear",
    "chatMessagesListRequiresExactCurrentAuthorityAndConsumesOnce",
    "sameChannelReauthenticationTombstonesOldChatMessagesAuthority",
    "runtimeDocumentCatalogErrorConsumesOnlyExactCurrentAuthorityAllowsRetryAndKeepsDuplicatesInert",
    "runtimeDocumentCatalogImmediateSendFailureAllowsRetryAndKeepsLateFramesInert",
    "delayedOldChatMessagesListSendFailureCannotCloseReplacementRequest",
    "pendingChatMessagesAuthorityClearsOnDisconnectRevocationAndViewModelClear",
)

try:
    root = ET.parse(report_path).getroot()
except (OSError, ET.ParseError) as error:
    raise SystemExit(f"Authenticated read authority JUnit report is unavailable: {error}") from error

failures = []
test_cases = root.findall("testcase")
for expected_name in expected_names:
    matches = [
        case
        for case in test_cases
        if case.get("classname") == "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"
        and case.get("name") == expected_name
    ]
    if len(matches) != 1:
        failures.append(f"{expected_name}: expected one executed testcase, found {len(matches)}")
        continue
    case = matches[0]
    terminal_tags = [tag for tag in ("skipped", "failure", "error") if case.find(tag) is not None]
    if terminal_tags:
        failures.append(f"{expected_name}: unexpected {','.join(terminal_tags)} result")

if failures:
    print("Authenticated read authority JUnit proof failed:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    raise SystemExit(1)

print(
    "Android authenticated read authority JUnit proof verified: "
    "10 executed tests, 0 skipped, 0 failures, 0 errors."
)
PY
}

check_android_authenticated_read_rollover_authority_junit() {
  python3 - <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

report_path = Path(
    "apps/android/app/build/test-results/testDebugUnitTest/"
    "TEST-com.localagentbridge.android.runtime.RuntimeClientViewModelTest.xml"
)
expected_names = (
    "chatSessionsListRequiresExactCurrentAuthorityAndConsumesOnce",
    "chatSessionsListWrongSourceCannotAdvancePaginationOrTriggerTerminalFailure",
    "sameChannelReauthenticationReplacesPendingMemoryAndResearchListAuthority",
    "siblingAuthenticationErrorClearsConcurrentPendingMemoryListAuthority",
)

try:
    root = ET.parse(report_path).getroot()
except (OSError, ET.ParseError) as error:
    raise SystemExit(f"Authenticated read rollover authority JUnit report is unavailable: {error}") from error

failures = []
test_cases = root.findall("testcase")
for expected_name in expected_names:
    matches = [
        case
        for case in test_cases
        if case.get("classname") == "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"
        and case.get("name") == expected_name
    ]
    if len(matches) != 1:
        failures.append(f"{expected_name}: expected one executed testcase, found {len(matches)}")
        continue
    case = matches[0]
    terminal_tags = [tag for tag in ("skipped", "failure", "error") if case.find(tag) is not None]
    if terminal_tags:
        failures.append(f"{expected_name}: unexpected {','.join(terminal_tags)} result")

if failures:
    print("Authenticated read rollover authority JUnit proof failed:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    raise SystemExit(1)

print(
    "Android authenticated read rollover authority JUnit proof verified: "
    "4 executed tests, 0 skipped, 0 failures, 0 errors."
)
PY
}

check_android_chat_sessions_bulk_terminal_authority_junit() {
  python3 - <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

report_path = Path(
    "apps/android/app/build/test-results/testDebugUnitTest/"
    "TEST-com.localagentbridge.android.runtime.RuntimeClientViewModelTest.xml"
)
expected_names = (
    "chatSessionsBulkLifecycleRequiresExactTerminalAuthority",
    "chatSessionsBulkMalformedCurrentErrorConsumesOnlyExactAuthority",
    "chatSessionsBulkSendFailureRequiresExactDispatchAuthority",
)

try:
    root = ET.parse(report_path).getroot()
except (OSError, ET.ParseError) as error:
    raise SystemExit(f"Chat sessions bulk terminal authority JUnit report is unavailable: {error}") from error

failures = []
test_cases = root.findall("testcase")
for expected_name in expected_names:
    matches = [
        case
        for case in test_cases
        if case.get("classname") == "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"
        and case.get("name") == expected_name
    ]
    if len(matches) != 1:
        failures.append(
            f"{expected_name}: expected one executed testcase, found {len(matches)}"
        )
        continue
    terminal_tags = [
        tag
        for tag in ("skipped", "failure", "error")
        if matches[0].find(tag) is not None
    ]
    if terminal_tags:
        failures.append(f"{expected_name}: has {','.join(terminal_tags)}")

if failures:
    print("Chat sessions bulk terminal authority JUnit proof failed:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    raise SystemExit(1)

print(
    "Android chat sessions bulk terminal authority JUnit proof verified: "
    "3 executed tests, 0 skipped, 0 failures, 0 errors."
)
PY
}

check_android_memory_mutation_authority_junit() {
  python3 - <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

report_path = Path(
    "apps/android/app/build/test-results/testDebugUnitTest/"
    "TEST-com.localagentbridge.android.runtime.RuntimeClientViewModelTest.xml"
)
expected_names = (
    "memoryUpsertResultRejectsUnknownMetadataBeforeMemoryMutation",
    "memoryDeleteResultRejectsUnknownMetadataBeforeMemoryMutation",
    "memoryMutationResultsRequireExactCurrentAuthorityAndExpectedPayload",
    "memoryMutationErrorsRequireExactCurrentAuthorityAndConsumeOnce",
    "memoryMutationSendFailureAndLifecycleCleanupRequireExactAuthority",
)

try:
    root = ET.parse(report_path).getroot()
except (OSError, ET.ParseError) as error:
    raise SystemExit(f"Memory mutation authority JUnit report is unavailable: {error}") from error

failures = []
test_cases = root.findall("testcase")
for expected_name in expected_names:
    matches = [
        case
        for case in test_cases
        if case.get("classname") == "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"
        and case.get("name") == expected_name
    ]
    if len(matches) != 1:
        failures.append(f"{expected_name}: expected one executed testcase, found {len(matches)}")
        continue
    terminal_tags = [
        tag
        for tag in ("skipped", "failure", "error")
        if matches[0].find(tag) is not None
    ]
    if terminal_tags:
        failures.append(f"{expected_name}: has {','.join(terminal_tags)}")

if failures:
    print("Memory mutation authority JUnit proof failed:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    raise SystemExit(1)

print(
    "Android memory mutation authority JUnit proof verified: "
    "5 executed tests, 0 skipped, 0 failures, 0 errors."
)

deadline_report_path = Path(
    "apps/android/app/build/test-results/testDebugUnitTest/"
    "TEST-com.localagentbridge.android.runtime.RuntimeClientViewModelProductionDeadlineTest.xml"
)
deadline_classname = (
    "com.localagentbridge.android.runtime.RuntimeClientViewModelProductionDeadlineTest"
)
deadline_test_name = "productionFactoryEnablesHostAlignedMemorySummaryDeadlines"

try:
    deadline_root = ET.parse(deadline_report_path).getroot()
except (OSError, ET.ParseError) as error:
    raise SystemExit(
        f"Production memory mutation deadline JUnit report is unavailable: {error}"
    ) from error

deadline_matches = [
    case
    for case in deadline_root.findall("testcase")
    if case.get("classname") == deadline_classname
    and case.get("name") == deadline_test_name
]
if len(deadline_matches) != 1:
    raise SystemExit(
        f"{deadline_test_name}: expected one executed production deadline testcase, "
        f"found {len(deadline_matches)}"
    )
deadline_terminal_tags = [
    tag
    for tag in ("skipped", "failure", "error")
    if deadline_matches[0].find(tag) is not None
]
if deadline_terminal_tags:
    raise SystemExit(
        f"{deadline_test_name}: has {','.join(deadline_terminal_tags)}"
    )

print(
    "Android production memory mutation deadline JUnit proof verified: "
    "1 executed test, 0 skipped, 0 failures, 0 errors."
)
PY
}

check_legacy_relay_guard() {
  local output
  local status_code
  set +e
  output="$(python3 script/aetherlink_relay.py --host 127.0.0.1 --port 1 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Legacy Python relay guard should exit 2 without --allow-legacy-no-allocation, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"does not support allocation leases required by QR pairing"* ]]; then
    echo "Legacy Python relay guard did not explain the allocation-lease limitation." >&2
    echo "$output" >&2
    exit 1
  fi
}

check_link_local_relay_guard() {
  local output
  local summary_path
  local status_code

  summary_path="$(mktemp "${TMPDIR:-/tmp}/aetherlink-link-local-summary.XXXXXX")"
  set +e
  output="$(script/run_different_network_dev_runtime.sh --relay-host 169.254.10.20 --relay-port 43171 --allow-private-relay --preflight-only --summary-json "$summary_path" 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Different-network runtime preflight should reject link-local relay hosts even with --allow-private-relay, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"link-local and multicast addresses cannot be used as QR relay routes"* ]]; then
    echo "Different-network runtime preflight did not explain the link-local relay limitation." >&2
    echo "$output" >&2
    exit 1
  fi
  python3 - "$summary_path" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
assert summary["exit_status"] == 2, summary
assert summary["relay"]["endpoints"][0]["host"] == "169.254.10.20", summary
assert summary["coverage"]["runtime_host_allocation_preflight"] is False, summary
assert summary["coverage"]["trusted_device_relay_reachability"] is False, summary
assert summary["coverage"]["trusted_device_pairing"] is False, summary
assert summary["coverage"]["optical_qr_scan"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
assert summary["coverage"]["production_session_key_exchange"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption"] is False, summary
assert summary["allocation"]["relay_id_present"] is False, summary
assert summary["allocation"]["relay_expires_at_present"] is False, summary
assert summary["allocation"]["relay_nonce_present"] is False, summary
assert summary["allocation"]["has_relay_secret"] is False, summary
assert summary["allocation"]["route_material_redacted"] is False, summary
assert "relay_bootstrap_preflight_failed" in summary["caveats"], summary
assert "link-local" in summary["failure_detail"], summary
PY
  rm -f "$summary_path"

  set +e
  output="$(script/no_adb_external_relay_pairing_smoke.sh --relay-host 169.254.10.20 --relay-port 43171 --allow-private-relay --emit-only 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "No-ADB QR smoke should reject link-local relay hosts even with --allow-private-relay, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"private, link-local, CGNAT, loopback, and multicast IP literals are invalid"* ]]; then
    echo "No-ADB QR smoke did not explain the link-local relay limitation." >&2
    echo "$output" >&2
    exit 1
  fi
}

check_different_network_relay_endpoint_input_redaction_guard() {
  local output
  local summary_path
  local status_code

  summary_path="$(mktemp "${TMPDIR:-/tmp}/aetherlink-different-network-invalid-endpoint.XXXXXX")"
  set +e
  output="$(script/run_different_network_dev_runtime.sh \
    --relay-host "https://provider.example.test:11434/v1/models?route_token=leaked-route-token&relay_secret=leaked-relay-secret" \
    --relay-port 43171 \
    --preflight-only \
    --summary-json "$summary_path" \
    2>&1 >/dev/null)"
  status_code=$?
  set -e

  if [[ "$status_code" -ne 2 ]]; then
    echo "Different-network runtime preflight should reject URL-shaped relay endpoints, got $status_code" >&2
    echo "$output" >&2
    rm -f "$summary_path"
    exit 1
  fi
  if [[ "$output" != *"Invalid relay endpoint <invalid-host>:43171: use a host or IP address, not a URL."* ]]; then
    echo "Different-network runtime preflight did not preserve the safe invalid-endpoint failure reason." >&2
    echo "$output" >&2
    rm -f "$summary_path"
    exit 1
  fi
  for marker in \
    "provider.example.test" \
    "11434/v1/models" \
    "route_token=" \
    "relay_secret=" \
    "leaked-route-token" \
    "leaked-relay-secret"
  do
    if [[ "$output" == *"$marker"* ]]; then
      echo "Different-network runtime preflight leaked invalid-endpoint marker $marker." >&2
      echo "$output" >&2
      rm -f "$summary_path"
      exit 1
    fi
  done
  python3 - "$summary_path" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
payload = json.dumps(summary, sort_keys=True)
assert summary["exit_status"] == 2, summary
assert summary["relay"]["endpoints"][0]["host"] == "<invalid-host>", summary
assert summary["failure_detail"] == (
    "Invalid relay endpoint <invalid-host>:43171: use a host or IP address, not a URL."
), summary
for marker in (
    "provider.example.test",
    "11434/v1/models",
    "route_token=",
    "relay_secret=",
    "leaked-route-token",
    "leaked-relay-secret",
):
    assert marker not in payload, (marker, payload)
PY
  rm -f "$summary_path"

  set +e
  output="$(script/run_different_network_dev_runtime.sh \
    --relay-endpoint "provider.example.test:bad?route_token=leaked-route-token&relay_secret=leaked-relay-secret" \
    --preflight-only \
    2>&1 >/dev/null)"
  status_code=$?
  set -e

  if [[ "$status_code" -ne 2 ]]; then
    echo "Different-network runtime endpoint parser should reject malformed relay endpoints, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"Invalid relay endpoint port: <invalid-endpoint>"* ]]; then
    echo "Different-network runtime endpoint parser did not preserve the safe invalid-endpoint-port failure reason." >&2
    echo "$output" >&2
    exit 1
  fi
  for marker in \
    "provider.example.test" \
    "route_token=" \
    "relay_secret=" \
    "leaked-route-token" \
    "leaked-relay-secret"
  do
    if [[ "$output" == *"$marker"* ]]; then
      echo "Different-network runtime endpoint parser leaked malformed-endpoint marker $marker." >&2
      echo "$output" >&2
      exit 1
    fi
  done
}

check_different_network_preflight_summary_guard() {
  local port
  local summary_path
  local work_dir

  port="$(free_tcp_port)"
  summary_path="$(mktemp "${TMPDIR:-/tmp}/aetherlink-runtime-preflight-summary.XXXXXX")"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-runtime-preflight-store.XXXXXX")"
  AETHERLINK_RELAY_ALLOCATION_STORE="$work_dir/allocations.json" \
    script/run_different_network_dev_runtime.sh \
    --relay-host 127.0.0.1 \
    --relay-port "$port" \
    --start-local-relay \
    --preflight-only \
    --summary-json "$summary_path" \
    >/dev/null
  python3 - "$summary_path" "$port" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
port = int(sys.argv[2])
payload = json.dumps(summary, sort_keys=True)
assert summary["exit_status"] == 0, summary
assert summary["mode"]["preflight_only"] is True, summary
assert summary["relay"]["success_endpoint"] == f"127.0.0.1:{port}", summary
assert summary["relay"]["start_local_relay"] is True, summary
assert summary["coverage"]["runtime_host_allocation_preflight"] is True, summary
assert summary["coverage"]["runtime_host_static_legacy_relay_validation"] is False, summary
assert summary["coverage"]["trusted_device_relay_reachability"] is False, summary
assert summary["coverage"]["trusted_device_pairing"] is False, summary
assert summary["coverage"]["optical_qr_scan"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
assert summary["allocation"]["required_fields_present"] is True, summary
assert summary["allocation"]["preflight_non_persistent"] is True, summary
assert summary["allocation"]["preflight_acknowledged"] is True, summary
assert summary["allocation"]["relay_id_present"] is False, summary
assert summary["allocation"]["relay_expires_at_present"] is False, summary
assert summary["allocation"]["relay_nonce_present"] is False, summary
assert summary["allocation"]["has_relay_secret"] is False, summary
assert summary["allocation"]["crypto_version"] == 2, summary
assert summary["allocation"]["allocation_auth"] == "runtime-p256-v1", summary
assert summary["allocation"]["endpoint_owned_relay_secret"] is True, summary
assert summary["allocation"]["route_material_returned"] is False, summary
assert summary["allocation"]["route_material_redacted"] is True, summary
for marker in (
    '"relay_id"',
    '"relay_secret"',
    '"relay_nonce"',
    '"relay_expires_at"',
    '"requested_route_token"',
    "rt1-",
    "aetherlink-preflight",
    "allocation_token",
    "route_token",
):
    assert marker not in payload, (marker, payload)
assert "runtime_host_preflight_only_not_phone_reachability_proof" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "local_relay_only_unless_advertised_host_is_public_vpn_tunnel_or_overlay" in summary["caveats"], summary
PY
  rm -f "$summary_path"
  rm -rf "$work_dir"
}

check_no_adb_external_relay_url_host_redaction_guard() {
  local output
  local status_code
  local sensitive_markers=(
    "provider.example.test"
    "11434/v1/models"
    "route_token"
    "relay_secret"
    "leaked-route-token"
    "leaked-relay-secret"
  )
  local marker

  set +e
  output="$(script/no_adb_external_relay_pairing_smoke.sh \
    --relay-host "https://provider.example.test:11434/v1/models?route_token=leaked-route-token&relay_secret=leaked-relay-secret" \
    --relay-port 43171 \
    --emit-only \
    2>&1 >/dev/null)"
  status_code=$?
  set -e

  if [[ "$status_code" -ne 2 ]]; then
    echo "No-ADB external-relay smoke should reject URL-shaped relay hosts before artifact generation, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"--relay-host must be a host or IP address, not a URL."* ]]; then
    echo "No-ADB external-relay smoke did not explain URL-shaped host rejection safely." >&2
    echo "$output" >&2
    exit 1
  fi
  for marker in "${sensitive_markers[@]}"; do
    if [[ "$output" == *"$marker"* ]]; then
      echo "No-ADB external-relay smoke exposed URL host route material in rejection output: $marker" >&2
      echo "$output" >&2
      exit 1
    fi
  done
}

check_relay_preflight_allocation_guard() {
  local relay_bin
  local port
  local work_dir
  local store
  local relay_pid

  swift build --product AetherLinkRelay >/dev/null
  relay_bin="$(swift build --show-bin-path)/AetherLinkRelay"
  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-preflight.XXXXXX")"
  store="$work_dir/allocations.json"
  relay_pid=""

  "$relay_bin" \
    --host 127.0.0.1 \
    --port "$port" \
    --require-allocation \
    --allocation-store "$store" \
    >"$work_dir/relay.log" 2>&1 &
  relay_pid="$!"

  set +e
  python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token preflight-route \
    --quiet
  local preflight_status=$?
  sleep 0.2
  python3 - "$store" <<'PY'
import sys
from pathlib import Path

store = Path(sys.argv[1])
contents = store.read_text(encoding="utf-8") if store.exists() else ""
assert "preflight-route" not in contents, contents
PY
  local preflight_store_status=$?
  local status_code=0
  set -e
  if [[ "$preflight_status" -ne 0 ]]; then
    status_code="$preflight_status"
  elif [[ "$preflight_store_status" -ne 0 ]]; then
    status_code="$preflight_store_status"
  fi

  if [[ -n "$relay_pid" ]]; then
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
  fi
  rm -rf "$work_dir"
  return "$status_code"
}

check_relay_preflight_rejects_route_material_guard() {
  local port
  local work_dir
  local fake_pid
  local output
  local status_code

  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-route-material-preflight.XXXXXX")"
  fake_pid=""

  python3 - "$port" "$work_dir" <<'PY' &
import json
import socket
import sys
from pathlib import Path

port = int(sys.argv[1])
work_dir = Path(sys.argv[2])
ready_path = work_dir / "ready"
request_path = work_dir / "request.txt"

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    server.settimeout(5)
    ready_path.write_text("ready", encoding="utf-8")
    connection, _ = server.accept()
    with connection:
        connection.settimeout(2)
        buffer = b""
        while not buffer.endswith(b"\n") and len(buffer) < 4096:
            chunk = connection.recv(1024)
            if not chunk:
                break
            buffer += chunk
        request = buffer.decode("utf-8", errors="replace").strip()
        request_path.write_text(request, encoding="utf-8")
        payload = {
            "preflight": True,
            "crypto_version": 2,
            "allocation_auth": "runtime-p256-v1",
            "relay_id": "rt2-forbidden-route-material",
        }
        line = "AETHERLINK_RELAY preflight " + json.dumps(payload, separators=(",", ":")) + "\n"
        connection.sendall(line.encode("utf-8"))
PY
  fake_pid="$!"

  for _ in {1..30}; do
    if [[ -f "$work_dir/ready" ]]; then
      break
    fi
    if ! kill -0 "$fake_pid" >/dev/null 2>&1; then
      echo "Fake relay preflight route-material server exited before listening." >&2
      rm -rf "$work_dir"
      exit 1
    fi
    sleep 0.1
  done
  if [[ ! -f "$work_dir/ready" ]]; then
    echo "Fake relay preflight route-material server did not become ready." >&2
    kill "$fake_pid" >/dev/null 2>&1 || true
    wait "$fake_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  output="$(python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token route-material-route-token \
    --timeout 2 \
    --quiet \
    2>&1 >/dev/null)"
  status_code=$?
  wait "$fake_pid" >/dev/null 2>&1 || true
  set -e

  if [[ "$status_code" -eq 0 ]]; then
    echo "Relay allocation preflight should reject every route-material response field." >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"preflight response included unsupported metadata"* ]]; then
    echo "Relay allocation preflight did not explain the forbidden route-material field rejection." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if ! grep -q "AETHERLINK_RELAY allocate route-material-route-token crypto=2 preflight=1" "$work_dir/request.txt"; then
    echo "Fake relay preflight route-material server did not capture the expected non-persisting request." >&2
    cat "$work_dir/request.txt" >&2 || true
    rm -rf "$work_dir"
    exit 1
  fi
  rm -rf "$work_dir"
}

check_relay_preflight_failure_output_redaction_guard() {
  local port
  local work_dir
  local fake_pid
  local output
  local status_code

  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-failure-redaction.XXXXXX")"
  fake_pid=""

  python3 - "$port" "$work_dir" <<'PY' &
import socket
import sys
from pathlib import Path

port = int(sys.argv[1])
work_dir = Path(sys.argv[2])
ready_path = work_dir / "ready"

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    server.settimeout(5)
    ready_path.write_text("ready", encoding="utf-8")
    connection, _ = server.accept()
    with connection:
        connection.settimeout(2)
        buffer = b""
        while not buffer.endswith(b"\n") and len(buffer) < 4096:
            chunk = connection.recv(1024)
            if not chunk:
                break
            buffer += chunk
        bad_line = (
            "NOT_AETHERLINK_ALLOCATION "
            "route_token=leaked-route-token "
            "relay_secret=leaked-relay-secret "
            "allocation_token=leaked-allocation-token "
            "rt=compact-route-token rs=compact-relay-secret rrn=compact-relay-nonce "
            "https://provider.example.test/v1/models http://127.0.0.1:11434/api/tags "
            "backend=192.168.1.23:11434\n"
        )
        connection.sendall(bad_line.encode("utf-8"))
PY
  fake_pid="$!"

  for _ in {1..30}; do
    if [[ -f "$work_dir/ready" ]]; then
      break
    fi
    if ! kill -0 "$fake_pid" >/dev/null 2>&1; then
      echo "Fake relay failure-redaction server exited before listening." >&2
      rm -rf "$work_dir"
      exit 1
    fi
    sleep 0.1
  done
  if [[ ! -f "$work_dir/ready" ]]; then
    echo "Fake relay failure-redaction server did not become ready." >&2
    kill "$fake_pid" >/dev/null 2>&1 || true
    wait "$fake_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  output="$(python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token failure-redaction-route-token \
    --allocation-token failure-redaction-allocation-token \
    --timeout 2 \
    --quiet \
    2>&1 >/dev/null)"
  status_code=$?
  wait "$fake_pid" >/dev/null 2>&1 || true
  set -e

  if [[ "$status_code" -eq 0 ]]; then
    echo "Relay allocation preflight should fail for malformed preflight responses." >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"did not return a preflight response"* ]]; then
    echo "Relay allocation preflight did not preserve the safe unexpected-response failure." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"<redacted unexpected relay response"* ]]; then
    echo "Relay allocation preflight did not redact the malformed response body." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  for marker in \
    "route_token=" \
    "relay_secret=" \
    "allocation_token=" \
    "rt=" \
    "rs=" \
    "rrn=" \
    "ri=" \
    "leaked-route-token" \
    "leaked-relay-secret" \
    "leaked-allocation-token" \
    "compact-route-token" \
    "compact-relay-secret" \
    "compact-relay-nonce" \
    "provider.example.test" \
    "127.0.0.1:11434" \
    "192.168.1.23:11434"
  do
    if [[ "$output" == *"$marker"* ]]; then
      echo "Relay allocation preflight leaked malformed response marker $marker." >&2
      echo "$output" >&2
      rm -rf "$work_dir"
      exit 1
    fi
  done
  rm -rf "$work_dir"
}

check_relay_preflight_unexpected_field_rejection_guard() {
  local port
  local work_dir
  local fake_pid
  local output
  local status_code

  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-unexpected-fields.XXXXXX")"
  fake_pid=""

  python3 - "$port" "$work_dir" <<'PY' &
import json
import socket
import sys
from pathlib import Path

port = int(sys.argv[1])
work_dir = Path(sys.argv[2])
ready_path = work_dir / "ready"

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    server.settimeout(5)
    ready_path.write_text("ready", encoding="utf-8")
    connection, _ = server.accept()
    with connection:
        connection.settimeout(2)
        buffer = b""
        while not buffer.endswith(b"\n") and len(buffer) < 4096:
            chunk = connection.recv(1024)
            if not chunk:
                break
            buffer += chunk
        payload = {
            "preflight": True,
            "crypto_version": 2,
            "allocation_auth": "runtime-p256-v1",
            "requested_route_token": "leaked-route-token",
            "backend_url": "http://127.0.0.1:11434/api/tags",
            "provider_url": "https://provider.example.test/v1/models",
            "allocation_token": "leaked-allocation-token",
            "relay_secret_debug": "leaked-relay-secret",
        }
        line = "AETHERLINK_RELAY preflight " + json.dumps(payload, separators=(",", ":")) + "\n"
        connection.sendall(line.encode("utf-8"))
PY
  fake_pid="$!"

  for _ in {1..30}; do
    if [[ -f "$work_dir/ready" ]]; then
      break
    fi
    if ! kill -0 "$fake_pid" >/dev/null 2>&1; then
      echo "Fake relay unexpected-field server exited before listening." >&2
      rm -rf "$work_dir"
      exit 1
    fi
    sleep 0.1
  done
  if [[ ! -f "$work_dir/ready" ]]; then
    echo "Fake relay unexpected-field server did not become ready." >&2
    kill "$fake_pid" >/dev/null 2>&1 || true
    wait "$fake_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  output="$(python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token unexpected-field-route-token \
    --allocation-token unexpected-field-allocation-token \
    --timeout 2 \
    --quiet \
    2>&1 >/dev/null)"
  status_code=$?
  wait "$fake_pid" >/dev/null 2>&1 || true
  set -e

  if [[ "$status_code" -eq 0 ]]; then
    echo "Relay allocation preflight should reject preflight responses with unexpected metadata fields." >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"included unsupported metadata"* ]]; then
    echo "Relay allocation preflight did not preserve the safe unexpected-field failure reason." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  for marker in \
    "requested_route_token" \
    "backend_url" \
    "provider_url" \
    "allocation_token" \
    "relay_secret_debug" \
    "leaked-route-token" \
    "leaked-allocation-token" \
    "leaked-relay-secret" \
    "unexpected-field-relay-secret" \
    "unexpected-field-relay-nonce" \
    "provider.example.test" \
    "127.0.0.1:11434"
  do
    if [[ "$output" == *"$marker"* ]]; then
      echo "Relay allocation preflight leaked unexpected-field marker $marker." >&2
      echo "$output" >&2
      rm -rf "$work_dir"
      exit 1
    fi
  done
  rm -rf "$work_dir"
}

check_relay_preflight_response_value_canonicality_guard() {
  local port
  local work_dir
  local fake_pid
  local output
  local route_token
  local expected
  local case_spec
  local status_code

  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-response-canonicality.XXXXXX")"
  fake_pid=""

  python3 - "$port" "$work_dir" <<'PY' &
import json
import socket
import sys
from pathlib import Path

port = int(sys.argv[1])
work_dir = Path(sys.argv[2])
ready_path = work_dir / "ready"

def payload(**overrides):
    value = {
        "preflight": True,
        "crypto_version": 2,
        "allocation_auth": "runtime-p256-v1",
    }
    value.update(overrides)
    return value

payloads = {
    "case-preflight-false": payload(preflight=False),
    "case-preflight-one": payload(preflight=1),
    "case-crypto-version-one": payload(crypto_version=1),
    "case-crypto-version-bool": payload(crypto_version=True),
    "case-allocation-auth-legacy": payload(allocation_auth="legacy-bearer-v1"),
    "case-allocation-auth-bool": payload(allocation_auth=True),
    "case-missing-auth": {"preflight": True, "crypto_version": 2},
    "case-route-material": payload(relay_nonce="forbidden-relay-nonce"),
}

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(len(payloads))
    server.settimeout(10)
    ready_path.write_text("ready", encoding="utf-8")
    for _ in payloads:
        connection, _ = server.accept()
        with connection:
            connection.settimeout(2)
            buffer = b""
            while not buffer.endswith(b"\n") and len(buffer) < 4096:
                chunk = connection.recv(1024)
                if not chunk:
                    break
                buffer += chunk
            request = buffer.decode("utf-8", errors="replace").strip()
            parts = request.split()
            route_token = parts[2] if len(parts) >= 3 else "case-preflight-false"
            response_payload = payloads.get(route_token, payloads["case-preflight-false"])
            line = "AETHERLINK_RELAY preflight " + json.dumps(response_payload, separators=(",", ":")) + "\n"
            connection.sendall(line.encode("utf-8"))
PY
  fake_pid="$!"

  for _ in {1..30}; do
    if [[ -f "$work_dir/ready" ]]; then
      break
    fi
    if ! kill -0 "$fake_pid" >/dev/null 2>&1; then
      echo "Fake relay response-canonicality server exited before listening." >&2
      rm -rf "$work_dir"
      exit 1
    fi
    sleep 0.1
  done
  if [[ ! -f "$work_dir/ready" ]]; then
    echo "Fake relay response-canonicality server did not become ready." >&2
    kill "$fake_pid" >/dev/null 2>&1 || true
    wait "$fake_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  for case_spec in \
    "case-preflight-false|did not acknowledge preflight" \
    "case-preflight-one|did not acknowledge preflight" \
    "case-crypto-version-one|invalid crypto_version" \
    "case-crypto-version-bool|invalid crypto_version" \
    "case-allocation-auth-legacy|invalid allocation_auth" \
    "case-allocation-auth-bool|invalid allocation_auth" \
    "case-missing-auth|did not match the expected closed field set" \
    "case-route-material|included unsupported metadata"
  do
    route_token="${case_spec%%|*}"
    expected="${case_spec##*|}"
    set +e
    output="$(python3 script/relay_allocation_preflight.py \
      --host 127.0.0.1 \
      --port "$port" \
      --route-token "$route_token" \
      --timeout 2 \
      --quiet \
      2>&1 >/dev/null)"
    status_code=$?
    set -e
    if [[ "$status_code" -eq 0 ]]; then
      echo "Relay allocation preflight should reject non-canonical response value case $route_token." >&2
      rm -rf "$work_dir"
      exit 1
    fi
    if [[ "$output" != *"$expected"* ]]; then
      echo "Relay allocation preflight did not preserve safe response-value failure reason $expected for $route_token." >&2
      echo "$output" >&2
      rm -rf "$work_dir"
      exit 1
    fi
    for marker in \
      "legacy-bearer-v1" \
      "forbidden-relay-nonce"
    do
      if [[ "$output" == *"$marker"* ]]; then
        echo "Relay allocation preflight leaked non-canonical response marker $marker." >&2
        echo "$output" >&2
        rm -rf "$work_dir"
        exit 1
      fi
    done
  done
  wait "$fake_pid" >/dev/null 2>&1 || true
  rm -rf "$work_dir"
}

check_relay_preflight_host_input_guard() {
  local output
  local status_code

  set +e
  output="$(python3 script/relay_allocation_preflight.py \
    --host "https://provider.example.test:11434/v1/models?route_token=leaked-route-token&relay_secret=leaked-relay-secret" \
    --port 43171 \
    --route-token host-input-route-token \
    --allocation-token host-input-allocation-token \
    --timeout 0.1 \
    --quiet \
    2>&1 >/dev/null)"
  status_code=$?
  set -e

  if [[ "$status_code" -eq 0 ]]; then
    echo "Relay allocation preflight should reject URL-shaped relay hosts before network access." >&2
    exit 1
  fi
  if [[ "$output" != *"--host must be a relay host or IP literal"* ]]; then
    echo "Relay allocation preflight did not preserve the safe invalid-host failure reason." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"<invalid-host>:43171"* ]]; then
    echo "Relay allocation preflight did not redact the invalid host in its endpoint label." >&2
    echo "$output" >&2
    exit 1
  fi
  for marker in \
    "provider.example.test" \
    "127.0.0.1:11434" \
    "11434/v1/models" \
    "route_token=" \
    "relay_secret=" \
    "leaked-route-token" \
    "leaked-relay-secret" \
    "host-input-route-token" \
    "host-input-allocation-token" \
    "host-input-relay-secret"
  do
    if [[ "$output" == *"$marker"* ]]; then
      echo "Relay allocation preflight leaked invalid-host marker $marker." >&2
      echo "$output" >&2
      exit 1
    fi
  done
}

check_relay_allocation_token_authorization_guard() {
  local relay_bin
  local port
  local work_dir
  local store
  local relay_pid
  local missing_status
  local wrong_status
  local preflight_status
  local preflight_store_status
  local status_code

  swift build --product AetherLinkRelay >/dev/null
  relay_bin="$(swift build --show-bin-path)/AetherLinkRelay"
  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-token-auth.XXXXXX")"
  store="$work_dir/allocations.json"
  relay_pid=""

  "$relay_bin" \
    --host 127.0.0.1 \
    --port "$port" \
    --require-allocation \
    --allocation-store "$store" \
    --allocation-token no-device-allocation-token \
    >"$work_dir/relay.log" 2>&1 &
  relay_pid="$!"
  for _ in {1..30}; do
    if [[ -f "$work_dir/relay.log" ]] && grep -q "development relay listening" "$work_dir/relay.log"; then
      break
    fi
    if ! kill -0 "$relay_pid" >/dev/null 2>&1; then
      echo "Token-required relay exited before listening." >&2
      cat "$work_dir/relay.log" >&2 || true
      rm -rf "$work_dir"
      exit 1
    fi
    sleep 0.1
  done
  if ! grep -q "development relay listening" "$work_dir/relay.log"; then
    echo "Token-required relay did not start." >&2
    cat "$work_dir/relay.log" >&2 || true
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token unauthorized-missing-token-route \
    --timeout 2 \
    --quiet
  missing_status=$?
  python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token unauthorized-wrong-token-route \
    --allocation-token wrong-no-device-allocation-token \
    --timeout 2 \
    --quiet
  wrong_status=$?
  python3 - "$store" <<'PY'
import sys
from pathlib import Path

store = Path(sys.argv[1])
contents = store.read_text(encoding="utf-8") if store.exists() else ""
assert "unauthorized-missing-token-route" not in contents, contents
assert "unauthorized-wrong-token-route" not in contents, contents
PY
  local unauthorized_store_status=$?
  python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token token-preflight-route \
    --allocation-token no-device-allocation-token \
    --timeout 2 \
    --quiet
  preflight_status=$?
  sleep 0.2
  python3 - "$store" "$work_dir/relay.log" <<'PY'
import sys
from pathlib import Path

store = Path(sys.argv[1])
contents = store.read_text(encoding="utf-8") if store.exists() else ""
log_contents = Path(sys.argv[2]).read_text(encoding="utf-8")
assert "token-preflight-route" not in contents, contents
assert "token-preflight-route" not in contents, contents
assert "unauthorized-missing-token-route" not in contents, contents
assert "unauthorized-wrong-token-route" not in contents, contents
assert "no-device-allocation-token" not in contents, contents
assert "wrong-no-device-allocation-token" not in contents, contents
assert "token-preflight-route" not in log_contents, log_contents
assert "unauthorized-missing-token-route" not in log_contents, log_contents
assert "unauthorized-wrong-token-route" not in log_contents, log_contents
assert "no-device-allocation-token" not in log_contents, log_contents
assert "wrong-no-device-allocation-token" not in log_contents, log_contents
PY
  preflight_store_status=$?
  set -e

  status_code=0
  if [[ "$missing_status" -eq 0 ]]; then
    echo "Missing allocation token should fail against a token-required relay." >&2
    status_code=1
  elif [[ "$wrong_status" -eq 0 ]]; then
    echo "Wrong allocation token should fail against a token-required relay." >&2
    status_code=1
  elif [[ "$unauthorized_store_status" -ne 0 ]]; then
    status_code="$unauthorized_store_status"
  elif [[ "$preflight_status" -ne 0 ]]; then
    status_code="$preflight_status"
  elif [[ "$preflight_store_status" -ne 0 ]]; then
    status_code="$preflight_store_status"
  fi

  if [[ -n "$relay_pid" ]]; then
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
  fi
  rm -rf "$work_dir"
  return "$status_code"
}

check_relay_exposed_bind_token_guard() {
  local relay_bin
  local port
  local token_port
  local work_dir
  local relay_pid
  local output
  local status_code
  local ephemeral_output
  local ephemeral_status
  local legacy_output
  local legacy_status

  swift build --product AetherLinkRelay >/dev/null
  relay_bin="$(swift build --show-bin-path)/AetherLinkRelay"
  port="$(free_tcp_port)"
  token_port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-bind-token.XXXXXX")"
  relay_pid=""

  set +e
  output="$("$relay_bin" --host 0.0.0.0 --port "$port" --require-allocation --ephemeral-allocations 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 1 ]]; then
    echo "Wildcard relay bind without allocation token should fail, got $status_code" >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"allocation token required for non-loopback relay bind 0.0.0.0"* ]]; then
    echo "Wildcard relay bind failure did not explain the allocation-token requirement." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  ephemeral_output="$("$relay_bin" \
    --host 0.0.0.0 \
    --port "$token_port" \
    --require-allocation \
    --ephemeral-allocations \
    --allocation-token no-device-bind-token \
    2>&1 >/dev/null)"
  ephemeral_status=$?
  set -e
  if [[ "$ephemeral_status" -ne 1 || "$ephemeral_output" != *"durable allocation store required for strict non-loopback relay bind 0.0.0.0"* ]]; then
    echo "Wildcard strict relay should reject ephemeral allocation storage even with an allocation token." >&2
    echo "$ephemeral_output" >&2
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  legacy_output="$("$relay_bin" \
    --host 0.0.0.0 \
    --port "$token_port" \
    --allow-legacy \
    --allocation-token no-device-bind-token \
    2>&1 >/dev/null)"
  legacy_status=$?
  set -e
  if [[ "$legacy_status" -ne 1 || "$legacy_output" != *"legacy unallocated relay mode is loopback-only"* ]]; then
    echo "Wildcard relay bind must reject legacy unallocated mode even with an allocation token." >&2
    echo "$legacy_output" >&2
    rm -rf "$work_dir"
    exit 1
  fi

  "$relay_bin" \
    --host 0.0.0.0 \
    --port "$token_port" \
    --require-allocation \
    --allocation-store "$work_dir/allocations.json" \
    --allocation-token no-device-bind-token \
    >"$work_dir/relay.log" 2>&1 &
  relay_pid="$!"
  for _ in {1..30}; do
    if [[ -f "$work_dir/relay.log" ]] && grep -q "development relay listening" "$work_dir/relay.log"; then
      break
    fi
    if ! kill -0 "$relay_pid" >/dev/null 2>&1; then
      echo "Wildcard relay bind with allocation token exited before listening." >&2
      cat "$work_dir/relay.log" >&2 || true
      rm -rf "$work_dir"
      exit 1
    fi
    sleep 0.1
  done
  if ! grep -q "development relay listening" "$work_dir/relay.log"; then
    echo "Wildcard relay bind with allocation token did not start." >&2
    cat "$work_dir/relay.log" >&2 || true
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi
  kill "$relay_pid" >/dev/null 2>&1 || true
  wait "$relay_pid" >/dev/null 2>&1 || true
  rm -rf "$work_dir"
}

check_relay_wrapper_dry_run_allocation_token_redaction_guard() {
  local output
  local summary_path
  local status_code
  local token
  local work_dir
  local real_python3
  local python_argv_log

  token="no-device-dry-run-token"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-dry-run-summary.XXXXXX")"
  summary_path="$work_dir/summary.json"
  python_argv_log="$work_dir/python-argv.log"
  real_python3="$(command -v python3)"
  mkdir -p "$work_dir/bin"
  cat >"$work_dir/bin/python3" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
{
  printf 'python3'
  for argument in "$@"; do
    printf '\t%s' "$argument"
  done
  printf '\n'
} >>"$PYTHON_ARGV_LOG"
exec "$REAL_PYTHON3" "$@"
SH
  chmod +x "$work_dir/bin/python3"
  set +e
  output="$(
    PATH="$work_dir/bin:$PATH" \
      REAL_PYTHON3="$real_python3" \
      PYTHON_ARGV_LOG="$python_argv_log" \
      script/run_allocation_relay.sh \
        --host 0.0.0.0 \
        --port 43171 \
        --allocation-token "$token" \
        --dry-run \
        --summary-json "$summary_path" \
        2>&1
  )"
  status_code=$?
  set -e

  if [[ "$status_code" -ne 0 ]]; then
    echo "run_allocation_relay dry-run with token should pass for a non-loopback bind, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"Allocation token: required"* ]]; then
    echo "run_allocation_relay dry-run should report token-required mode without printing the token." >&2
    echo "$output" >&2
    exit 1
  fi
  for marker in "$token" "--allocation-token" "AETHERLINK_RELAY_ALLOCATION_TOKEN=$token"; do
    if [[ "$output" == *"$marker"* ]]; then
      echo "run_allocation_relay dry-run leaked allocation-token marker $marker." >&2
      echo "$output" >&2
      exit 1
    fi
  done
  if grep -Fq "$token" "$python_argv_log"; then
    echo "run_allocation_relay dry-run exposed the raw allocation token in Python child argv." >&2
    cat "$python_argv_log" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if ! grep -Fq "$summary_path" "$python_argv_log"; then
    echo "run_allocation_relay dry-run Python argv guard did not observe summary generation." >&2
    cat "$python_argv_log" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$summary_path" "$token" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
token = sys.argv[2]
combined = json.dumps(summary, sort_keys=True)
assert token not in combined, summary
assert "--allocation-token" not in combined, summary
assert summary["exit_status"] == 0, summary
assert summary["mode"]["dry_run"] is True, summary
assert summary["relay"]["bind_host"] == "0.0.0.0", summary
assert summary["relay"]["bind_port"] == 43171, summary
assert summary["relay"]["development_relay_started"] is False, summary
assert summary["allocation"]["required"] is True, summary
assert summary["allocation"]["token_present"] is True, summary
assert summary["allocation"]["token_redacted"] is True, summary
assert summary["abuse_controls"]["probe_policy"] == "loopback-only", summary
assert summary["abuse_controls"]["control_timeout_seconds"] == 10.0, summary
assert summary["abuse_controls"]["max_connections"] == 256, summary
assert summary["abuse_controls"]["source_peer_quotas"] == {
    "max_concurrent_connections_per_source": 64,
    "max_waiting_peers_per_source": 32,
    "runtime_enforcement_verified": False,
    "shared_nat_vpn_bucket": True,
    "source_identity": "accepted_socket_address",
}, summary
assert summary["abuse_controls"]["waiting_peer_policy"] == {
    "max_duration_seconds": 60,
    "max_waiting_peers_per_authenticated_identity": 4,
    "post_authentication_only": True,
    "runtime_enforcement_verified": False,
    "unauthenticated_bootstrap_clients_source_only": True,
}, summary
source_rate_limits = summary["abuse_controls"]["source_rate_limits"]
assert source_rate_limits == {
    "preflight_rate_per_minute": 120,
    "preflight_burst": 30,
    "allocation_rate_per_minute": 30,
    "allocation_burst": 10,
    "max_rate_limit_sources": 4096,
}, summary
coverage = summary["coverage"]
assert coverage["relay_wrapper_dry_run_summary"] is True, summary
assert coverage["development_relay_started"] is False, summary
assert coverage["production_relay"] is False, summary
assert coverage["trusted_device_relay_reachability"] is False, summary
assert coverage["trusted_device_pairing"] is False, summary
assert coverage["optical_qr_scan"] is False, summary
assert "dry_run_not_relay_process_proof" in summary["caveats"], summary
assert "not_production_relay_proof" in summary["caveats"], summary
assert "not_trusted_device_reachability_proof" in summary["caveats"], summary
PY

  set +e
  output="$(
    script/run_allocation_relay.sh \
      --host 0.0.0.0 \
      --port 43171 \
      --allocation-token "$token" \
      --ephemeral-allocations \
      --dry-run \
      2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "run_allocation_relay dry-run should reject ephemeral non-loopback strict allocation storage, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"Durable allocation storage is required for non-loopback relay bind 0.0.0.0"* ]]; then
    echo "run_allocation_relay did not explain the durable allocation-store requirement." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" == *"$token"* ]]; then
    echo "run_allocation_relay durable-store rejection leaked the allocation token." >&2
    echo "$output" >&2
    exit 1
  fi

  set +e
  output="$(
    script/run_allocation_relay.sh \
      --host 0.0.0.0 \
      --port 43171 \
      --dry-run \
      2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "run_allocation_relay dry-run should reject non-loopback binds without an allocation token, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"Allocation token required for non-loopback relay bind 0.0.0.0"* ]]; then
    echo "run_allocation_relay dry-run did not explain the non-loopback token requirement." >&2
    echo "$output" >&2
    exit 1
  fi
  rm -rf "$work_dir"
}

check_relay_source_rate_limit_configuration_guard() {
  local output
  local status_code
  local summary_path
  local work_dir

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-source-rate-limit.XXXXXX")"
  summary_path="$work_dir/summary.json"
  output="$(
    AETHERLINK_RELAY_PREFLIGHT_RATE_PER_MINUTE=121 \
      AETHERLINK_RELAY_PREFLIGHT_BURST=31 \
      AETHERLINK_RELAY_ALLOCATION_RATE_PER_MINUTE=32 \
      AETHERLINK_RELAY_ALLOCATION_BURST=11 \
      AETHERLINK_RELAY_MAX_RATE_LIMIT_SOURCES=4100 \
      script/run_allocation_relay.sh \
        --host 127.0.0.1 \
        --ephemeral-allocations \
        --dry-run \
        --summary-json "$summary_path" \
        2>&1
  )"
  if [[ "$output" != *"Source limits apply only to allocation, preflight, and paired-renewal control records"* ]] ||
    [[ "$output" != *"Shared NAT/VPN users share source quotas and rate-limit buckets"* ]]; then
    echo "run_allocation_relay did not preserve the source-rate-limit scope and shared-source caveat." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$summary_path" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
assert summary["abuse_controls"]["source_rate_limits"] == {
    "preflight_rate_per_minute": 121,
    "preflight_burst": 31,
    "allocation_rate_per_minute": 32,
    "allocation_burst": 11,
    "max_rate_limit_sources": 4100,
}, summary
assert summary["coverage"]["development_relay_started"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
PY

  local invalid_case
  for invalid_case in \
    "--preflight-rate-per-minute 0" \
    "--preflight-rate-per-minute 08" \
    "--preflight-burst 1000001" \
    "--allocation-rate-per-minute 0" \
    "--allocation-burst 1000001" \
    "--max-rate-limit-sources 65537"
  do
    set -- $invalid_case
    set +e
    output="$(script/run_allocation_relay.sh --host 127.0.0.1 --ephemeral-allocations "$1" "$2" --dry-run 2>&1)"
    status_code=$?
    set -e
    if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"Invalid "* ]]; then
      echo "run_allocation_relay should reject invalid source-rate-limit arguments: $invalid_case" >&2
      echo "$output" >&2
      rm -rf "$work_dir"
      exit 1
    fi
  done

  set +e
  output="$(
    script/run_allocation_relay.sh \
      --host 127.0.0.1 \
      --ephemeral-allocations \
      --preflight-rate-per-minute 1 \
      --preflight-burst 16 \
      --dry-run \
      2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"burst must fully refill within 900 seconds"* ]]; then
    echo "run_allocation_relay should reject source-rate limits that can reset before full refill." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  output="$(
    script/run_allocation_relay.sh \
      --host 127.0.0.1 \
      --ephemeral-allocations \
      --allocation-rate-per-minute 1 \
      --allocation-burst 16 \
      --dry-run \
      2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"Invalid allocation rate/burst combination"* ]]; then
    echo "run_allocation_relay should reject allocation limits that can reset before full refill." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  output="$(
    AETHERLINK_RELAY_MAX_RATE_LIMIT_SOURCES=65537 \
      script/run_allocation_relay.sh --host 127.0.0.1 --ephemeral-allocations --dry-run 2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"Invalid maximum rate-limit sources"* ]]; then
    echo "run_allocation_relay should reject invalid source-rate-limit environment values." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  rm -rf "$work_dir"
}

check_relay_source_peer_quota_configuration_guard() {
  local invalid_case
  local output
  local status_code
  local summary_path
  local work_dir

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-source-peer-quota.XXXXXX")"
  summary_path="$work_dir/summary.json"
  output="$(
    AETHERLINK_RELAY_MAX_CONNECTIONS_PER_SOURCE=96 \
      AETHERLINK_RELAY_MAX_WAITING_PEERS_PER_SOURCE=40 \
      script/run_allocation_relay.sh \
        --host 127.0.0.1 \
        --ephemeral-allocations \
        --dry-run \
        --summary-json "$summary_path" \
        2>&1
  )"
  if [[ "$output" != *"Source quotas: connections=96; waiting peers=40"* ]] ||
    [[ "$output" != *"Shared NAT/VPN users share source quotas"* ]] ||
    [[ "$output" != *"Active bridges remain counted against the source connection quota; frame forwarding is not throttled."* ]]; then
    echo "run_allocation_relay did not preserve the source peer quota scope and NAT/VPN caveat." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$summary_path" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
assert summary["abuse_controls"]["source_peer_quotas"] == {
    "max_concurrent_connections_per_source": 96,
    "max_waiting_peers_per_source": 40,
    "runtime_enforcement_verified": False,
    "shared_nat_vpn_bucket": True,
    "source_identity": "accepted_socket_address",
}, summary
assert summary["coverage"]["development_relay_started"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
PY

  for invalid_case in \
    "--max-connections-per-source 0" \
    "--max-connections-per-source 08" \
    "--max-connections-per-source 65537" \
    "--max-waiting-peers-per-source 0" \
    "--max-waiting-peers-per-source +8" \
    "--max-waiting-peers-per-source 65537"
  do
    set -- $invalid_case
    set +e
    output="$(script/run_allocation_relay.sh --host 127.0.0.1 --ephemeral-allocations "$1" "$2" --dry-run 2>&1)"
    status_code=$?
    set -e
    if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"Invalid "* ]]; then
      echo "run_allocation_relay should reject invalid source peer quota arguments: $invalid_case" >&2
      echo "$output" >&2
      rm -rf "$work_dir"
      exit 1
    fi
  done

  set +e
  output="$(
    script/run_allocation_relay.sh \
      --host 127.0.0.1 \
      --ephemeral-allocations \
      --max-connections-per-source 63 \
      --max-waiting-peers-per-source 32 \
      --dry-run \
      2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"twice maximum waiting peers per source"* ]]; then
    echo "run_allocation_relay should preserve counterpart headroom in source peer quotas." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  output="$(
    AETHERLINK_RELAY_MAX_CONNECTIONS_PER_SOURCE=08 \
      script/run_allocation_relay.sh --host 127.0.0.1 --ephemeral-allocations --dry-run 2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"Invalid maximum connections per source"* ]]; then
    echo "run_allocation_relay should reject noncanonical source peer quota environment values." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  rm -rf "$work_dir"
}

check_relay_waiting_peer_policy_configuration_guard() {
  local invalid_case
  local output
  local status_code
  local summary_path
  local work_dir

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-waiting-policy.XXXXXX")"
  summary_path="$work_dir/summary.json"
  output="$(
    AETHERLINK_RELAY_WAITING_TIMEOUT_SECONDS=180 \
      AETHERLINK_RELAY_MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY=12 \
      script/run_allocation_relay.sh \
        --host 127.0.0.1 \
        --ephemeral-allocations \
        --dry-run \
        --summary-json "$summary_path" \
        2>&1
  )"
  if [[ "$output" != *"Waiting policy: timeout=180s; authenticated identity waiting peers=12; unauthenticated bootstrap clients remain source-only."* ]]; then
    echo "run_allocation_relay did not preserve the bounded waiting and post-auth identity policy." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$summary_path" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
assert summary["abuse_controls"]["waiting_peer_policy"] == {
    "max_duration_seconds": 180,
    "max_waiting_peers_per_authenticated_identity": 12,
    "post_authentication_only": True,
    "runtime_enforcement_verified": False,
    "unauthenticated_bootstrap_clients_source_only": True,
}, summary
assert summary["coverage"]["development_relay_started"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
PY

  for invalid_case in \
    "--waiting-timeout-seconds 0" \
    "--waiting-timeout-seconds 08" \
    "--waiting-timeout-seconds 3601" \
    "--max-waiting-peers-per-authenticated-identity 0" \
    "--max-waiting-peers-per-authenticated-identity +8" \
    "--max-waiting-peers-per-authenticated-identity 65537"
  do
    set -- $invalid_case
    set +e
    output="$(script/run_allocation_relay.sh --host 127.0.0.1 --ephemeral-allocations "$1" "$2" --dry-run 2>&1)"
    status_code=$?
    set -e
    if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"Invalid "* ]]; then
      echo "run_allocation_relay should reject invalid waiting peer policy arguments: $invalid_case" >&2
      echo "$output" >&2
      rm -rf "$work_dir"
      exit 1
    fi
  done

  set +e
  output="$(
    AETHERLINK_RELAY_WAITING_TIMEOUT_SECONDS=08 \
      script/run_allocation_relay.sh --host 127.0.0.1 --ephemeral-allocations --dry-run 2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]] || [[ "$output" != *"Invalid waiting timeout seconds"* ]]; then
    echo "run_allocation_relay should reject noncanonical waiting policy environment values." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  rm -rf "$work_dir"
}

check_relay_binary_source_rate_limit_cli_guard() {
  local invalid_case
  local output
  local relay_bin
  local status_code

  relay_bin="$(swift build --show-bin-path)/AetherLinkRelay"
  for invalid_case in \
    "--preflight-rate-per-minute 08" \
    "--allocation-burst +8"
  do
    set -- $invalid_case
    set +e
    output="$("$relay_bin" "$1" "$2" --help 2>&1)"
    status_code=$?
    set -e
    if [[ "$status_code" -ne 2 ]]; then
      echo "AetherLinkRelay should reject noncanonical source-rate-limit CLI input: $invalid_case" >&2
      echo "$output" >&2
      exit 1
    fi
  done

  set +e
  output="$(AETHERLINK_RELAY_MAX_RATE_LIMIT_SOURCES=08 "$relay_bin" --help 2>&1)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "AetherLinkRelay should reject noncanonical source-rate-limit environment input." >&2
    echo "$output" >&2
    exit 1
  fi

  set +e
  output="$(
    "$relay_bin" \
      --host 0.0.0.0 \
      --ephemeral-allocations \
      --allocation-rate-per-minute 1 \
      --allocation-burst 16 \
      2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "AetherLinkRelay should reject allocation limits that can reset before full refill." >&2
    echo "$output" >&2
    exit 1
  fi
}

check_relay_binary_source_peer_quota_cli_guard() {
  local invalid_case
  local output
  local relay_bin
  local status_code

  relay_bin="$(swift build --show-bin-path)/AetherLinkRelay"
  for invalid_case in \
    "--max-connections 08" \
    "--max-connections-per-source 08" \
    "--max-waiting-peers-per-source +8"
  do
    set -- $invalid_case
    set +e
    output="$("$relay_bin" "$1" "$2" --help 2>&1)"
    status_code=$?
    set -e
    if [[ "$status_code" -ne 2 ]]; then
      echo "AetherLinkRelay should reject noncanonical source peer quota CLI input: $invalid_case" >&2
      echo "$output" >&2
      exit 1
    fi
  done

  set +e
  output="$(
    AETHERLINK_RELAY_MAX_WAITING_PEERS_PER_SOURCE=08 \
      "$relay_bin" --help 2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "AetherLinkRelay should reject noncanonical source peer quota environment input." >&2
    echo "$output" >&2
    exit 1
  fi

  set +e
  output="$(
    "$relay_bin" \
      --max-connections-per-source 63 \
      --max-waiting-peers-per-source 32 \
      2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "AetherLinkRelay should reject source peer quotas without counterpart headroom." >&2
    echo "$output" >&2
    exit 1
  fi
}

check_relay_binary_waiting_peer_policy_cli_guard() {
  local invalid_case
  local output
  local relay_bin
  local status_code

  relay_bin="$(swift build --show-bin-path)/AetherLinkRelay"
  for invalid_case in \
    "--waiting-timeout-seconds 08" \
    "--waiting-timeout-seconds 3601" \
    "--max-waiting-peers-per-authenticated-identity +8" \
    "--max-waiting-peers-per-authenticated-identity 65537"
  do
    set -- $invalid_case
    set +e
    output="$("$relay_bin" "$1" "$2" --help 2>&1)"
    status_code=$?
    set -e
    if [[ "$status_code" -ne 2 ]]; then
      echo "AetherLinkRelay should reject noncanonical waiting peer policy CLI input: $invalid_case" >&2
      echo "$output" >&2
      exit 1
    fi
  done

  set +e
  output="$(
    AETHERLINK_RELAY_MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY=08 \
      "$relay_bin" --help 2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "AetherLinkRelay should reject noncanonical waiting peer policy environment input." >&2
    echo "$output" >&2
    exit 1
  fi
}

relay_child_command_for_parent() {
  local parent_pid="$1"
  ps -ax -o ppid= -o command= | awk -v parent="$parent_pid" '
    $1 == parent {
      line = $0
      sub(/^[[:space:]]*[0-9]+[[:space:]]+/, "", line)
      if (line ~ /AetherLinkRelay/ && line ~ /--host/) {
        print line
        exit
      }
    }
  '
}

wait_for_relay_child_command() {
  local parent_pid="$1"
  local command_line
  for _ in {1..120}; do
    command_line="$(relay_child_command_for_parent "$parent_pid")"
    if [[ -n "$command_line" ]]; then
      printf '%s\n' "$command_line"
      return 0
    fi
    if ! kill -0 "$parent_pid" >/dev/null 2>&1; then
      return 1
    fi
    sleep 0.1
  done
  return 1
}

check_relay_wrapper_allocation_token_argv_redaction_guard() {
  local port
  local work_dir
  local relay_pid
  local command_line
  local wrong_status
  local token

  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-wrapper-token.XXXXXX")"
  relay_pid=""
  token="no-device-wrapper-token"

  script/run_allocation_relay.sh \
    --host 127.0.0.1 \
    --port "$port" \
    --allocation-token "$token" \
    --ephemeral-allocations \
    >"$work_dir/relay.log" 2>&1 &
  relay_pid="$!"
  for _ in {1..80}; do
    if [[ -f "$work_dir/relay.log" ]] && grep -q "development relay listening" "$work_dir/relay.log"; then
      break
    fi
    if ! kill -0 "$relay_pid" >/dev/null 2>&1; then
      echo "run_allocation_relay exited before listening." >&2
      cat "$work_dir/relay.log" >&2 || true
      rm -rf "$work_dir"
      exit 1
    fi
    sleep 0.1
  done
  if ! grep -q "development relay listening" "$work_dir/relay.log"; then
    echo "run_allocation_relay did not start the allocation relay." >&2
    cat "$work_dir/relay.log" >&2 || true
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  command_line="$(ps -p "$relay_pid" -o command= || true)"
  if [[ "$command_line" == *"--allocation-token"* || "$command_line" == *"$token"* ]]; then
    echo "run_allocation_relay exposed the allocation token in child process argv." >&2
    echo "$command_line" >&2
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token wrapper-wrong-token-route \
    --allocation-token wrong-wrapper-token \
    --quiet \
    >"$work_dir/wrong.out" 2>&1
  wrong_status=$?
  set -e
  if [[ "$wrong_status" -eq 0 ]]; then
    echo "run_allocation_relay child did not enforce the exported allocation token." >&2
    cat "$work_dir/wrong.out" >&2 || true
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token wrapper-valid-token-route \
    --allocation-token "$token" \
    --quiet \
    >"$work_dir/valid.out"

  kill "$relay_pid" >/dev/null 2>&1 || true
  wait "$relay_pid" >/dev/null 2>&1 || true
  rm -rf "$work_dir"
}

check_different_network_wrapper_allocation_token_argv_redaction_guard() {
  local port
  local work_dir
  local wrapper_pid
  local command_line
  local token

  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-different-network-wrapper-token.XXXXXX")"
  wrapper_pid=""
  token="no-device-different-network-wrapper-token"

  AETHERLINK_RELAY_ALLOCATION_STORE="$work_dir/allocations.json" \
    script/run_different_network_dev_runtime.sh \
    --relay-host 127.0.0.1 \
    --relay-port "$port" \
    --allocation-token "$token" \
    --start-local-relay \
    >"$work_dir/wrapper.log" 2>&1 &
  wrapper_pid="$!"

  command_line="$(wait_for_relay_child_command "$wrapper_pid" || true)"
  if [[ -z "$command_line" ]]; then
    echo "run_different_network_dev_runtime did not start an AetherLinkRelay child for argv inspection." >&2
    cat "$work_dir/wrapper.log" >&2 || true
    kill "$wrapper_pid" >/dev/null 2>&1 || true
    wait "$wrapper_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$command_line" == *"--allocation-token"* || "$command_line" == *"$token"* ]]; then
    echo "run_different_network_dev_runtime exposed the allocation token in AetherLinkRelay child argv." >&2
    echo "$command_line" >&2
    kill "$wrapper_pid" >/dev/null 2>&1 || true
    wait "$wrapper_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  kill "$wrapper_pid" >/dev/null 2>&1 || true
  wait "$wrapper_pid" >/dev/null 2>&1 || true
  rm -rf "$work_dir"
}

check_no_adb_wrapper_allocation_token_argv_redaction_guard() {
  local port
  local work_dir
  local wrapper_pid
  local command_line
  local token

  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-adb-wrapper-token.XXXXXX")"
  wrapper_pid=""
  token="no-device-no-adb-wrapper-token"

  script/no_adb_external_relay_pairing_smoke.sh \
    --relay-host 127.0.0.1 \
    --relay-port "$port" \
    --allocation-token "$token" \
    --start-local-relay \
    --timeout 30 \
    --work-dir "$work_dir/smoke" \
    >"$work_dir/wrapper.log" 2>&1 &
  wrapper_pid="$!"

  command_line="$(wait_for_relay_child_command "$wrapper_pid" || true)"
  if [[ -z "$command_line" ]]; then
    echo "no_adb_external_relay_pairing_smoke did not start an AetherLinkRelay child for argv inspection." >&2
    cat "$work_dir/wrapper.log" >&2 || true
    cat "$work_dir/smoke/relay.log" >&2 || true
    kill "$wrapper_pid" >/dev/null 2>&1 || true
    wait "$wrapper_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$command_line" == *"--allocation-token"* || "$command_line" == *"$token"* ]]; then
    echo "no_adb_external_relay_pairing_smoke exposed the allocation token in AetherLinkRelay child argv." >&2
    echo "$command_line" >&2
    kill "$wrapper_pid" >/dev/null 2>&1 || true
    wait "$wrapper_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  kill "$wrapper_pid" >/dev/null 2>&1 || true
  wait "$wrapper_pid" >/dev/null 2>&1 || true
  rm -rf "$work_dir"
}

check_android_pairing_deeplink_allocation_token_argv_redaction_guard() {
  local work_dir
  local fake_adb
  local smoke_pid
  local command_line
  local token

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-android-pairing-token.XXXXXX")"
  fake_adb="$work_dir/adb"
  smoke_pid=""
  token="no-device-android-pairing-token"

  cat >"$fake_adb" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "devices" ]]; then
  printf 'List of devices attached\n'
  printf 'fake-device\tdevice\n'
  exit 0
fi
if [[ "${1:-}" == "-s" ]]; then
  shift 2
fi
case "${1:-}" in
  reverse|install|shell|exec-out|pull|logcat)
    sleep 30
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
SH
  chmod +x "$fake_adb"

  ADB="$fake_adb" \
    script/android_pairing_deeplink_smoke.sh \
      --relay \
      --allocation-token "$token" \
      >"$work_dir/smoke.log" 2>&1 &
  smoke_pid="$!"

  command_line="$(wait_for_relay_child_command "$smoke_pid" || true)"
  if [[ -z "$command_line" ]]; then
    echo "android_pairing_deeplink_smoke did not start an AetherLinkRelay child for argv inspection." >&2
    cat "$work_dir/smoke.log" >&2 || true
    kill "$smoke_pid" >/dev/null 2>&1 || true
    wait "$smoke_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$command_line" == *"--allocation-token"* || "$command_line" == *"$token"* ]]; then
    echo "android_pairing_deeplink_smoke exposed the allocation token in AetherLinkRelay child argv." >&2
    echo "$command_line" >&2
    kill "$smoke_pid" >/dev/null 2>&1 || true
    wait "$smoke_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  kill "$smoke_pid" >/dev/null 2>&1 || true
  wait "$smoke_pid" >/dev/null 2>&1 || true
  rm -rf "$work_dir"
}

check_physical_external_relay_summary_guard() {
  local work_dir
  local summary_path
  local log_path
  local output
  local status_code

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-physical-wrapper-summary.XXXXXX")"
  summary_path="$work_dir/summary.json"
  log_path="$work_dir/run.log"
  set +e
  output="$(
    ADB=/bin/true \
      script/check_physical_external_relay_pairing.sh \
        --relay-host 0.0.0.0 \
        --serial no-device-serial-1 \
        --expect-chat-complete \
        --chat-text "External wrapper complete proof" \
        --chat-delta-timeout 9 \
        --chat-complete-timeout 11 \
        --chat-expected-terms "ExternalComplete" \
        --chat-model-query "gemma4:e4b-mlx" \
        --live-backend \
        --json "$summary_path" \
        --log "$log_path" \
        2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Physical external-relay wrapper invalid-host guard should exit 2, got $status_code" >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$summary_path" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
assert summary["success"] is False, summary
assert summary["exit_status"] == 2, summary
assert summary["coverage"]["external_relay_probe_from_device"] is False, summary
assert summary["coverage"]["external_relay_route_probe_from_device"] is False, summary
assert summary["coverage"]["external_relay_probe_reachable"] is False, summary
assert summary["coverage"]["external_relay_route_ready"] is False, summary
assert summary["coverage"]["android_pairing_summary_json_present"] is False, summary
assert summary["coverage"]["android_pairing_summary_success"] is False, summary
assert summary["coverage"]["android_pairing_summary_external_relay_mode"] is False, summary
assert summary["coverage"]["android_pairing_summary_no_relay_adb_reverse"] is False, summary
assert summary["coverage"]["android_pairing_summary_proof_boundary_preserved"] is False, summary
assert summary["coverage"]["expect_chat_complete"] is True, summary
assert summary["coverage"]["chat_model_query_requested"] is True, summary
assert summary["coverage"]["live_backend"] is True, summary
assert summary["coverage"]["adb_deeplink_injection"] is False, summary
assert summary["coverage"]["optical_camera_qr_scan"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
assert summary["coverage"]["production_relay_proof"] is False, summary
assert summary["coverage"]["production_session_key_exchange"] is False, summary
assert summary["coverage"]["production_session_key_exchange_proof"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption_proof"] is False, summary
assert summary["coverage"]["external_network_operator_confirmed"] is False, summary
assert summary["coverage"]["real_different_network_relay_verified"] is False, summary
assert summary["coverage"]["real_different_network_connectivity_proof"] is False, summary
assert summary["coverage"]["android_direct_model_backend_access"] is False, summary
assert summary["coverage"]["private_relay_allowed"] is False, summary
assert summary["coverage"]["private_or_same_lan_development_relay"] is False, summary
assert summary["probe_summaries"]["device_relay_endpoint"] is None, summary
assert summary["probe_summaries"]["device_relay_route"] is None, summary
assert summary["child_summaries"]["android_pairing_deeplink"] is None, summary
assert summary["artifacts"]["android_pairing_summary_json"].endswith(".android-pairing-summary.json"), summary
assert summary["android_device"]["requested_adb_serial"] == "no-device-serial-1", summary
assert summary["android_device"]["observed_adb_serial"] is None, summary
assert "android_pairing_summary_json_missing" in summary["caveats"], summary
assert "device_endpoint_probe_not_reachable_or_missing" in summary["caveats"], summary
assert "device_route_probe_not_ready_or_missing" in summary["caveats"], summary
assert "does_not_expose_ollama_or_lm_studio_to_android" in summary["caveats"], summary
assert "not_production_relay_proof" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "--serial" in summary["command"], summary
assert "no-device-serial-1" in summary["command"], summary
assert "--expect-chat-complete" in summary["command"], summary
assert "--chat-complete-timeout" in summary["command"], summary
assert "--chat-expected-terms" in summary["command"], summary
assert "--chat-model-query" in summary["command"], summary
assert "--allocation-token" not in summary["command"], summary
PY
  rm -rf "$work_dir"
}

check_physical_external_relay_url_host_redaction_guard() {
  local work_dir
  local summary_path
  local log_path
  local output
  local status_code

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-physical-wrapper-url-host.XXXXXX")"
  summary_path="$work_dir/summary.json"
  log_path="$work_dir/run.log"
  set +e
  output="$(
    ADB=/bin/true \
      script/check_physical_external_relay_pairing.sh \
        --relay-host "https://provider.example.test:11434/v1/models?route_token=leaked-route-token&relay_secret=leaked-relay-secret" \
        --json "$summary_path" \
        --log "$log_path" \
        2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Physical external-relay wrapper URL-host guard should exit 2, got $status_code" >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"Invalid relay host <invalid-host>:43171: use a host or IP address, not a URL."* ]]; then
    echo "Physical external-relay wrapper URL-host guard did not preserve the safe failure reason." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$summary_path" "$log_path" "$output" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
log_text = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
output = sys.argv[3]
combined = json.dumps(summary, sort_keys=True) + log_text + output
assert summary["success"] is False, summary
assert summary["exit_status"] == 2, summary
assert summary["relay"]["host"] == "<invalid-host>", summary
assert summary["coverage"]["external_relay_probe_from_device"] is False, summary
assert summary["coverage"]["external_relay_route_probe_from_device"] is False, summary
assert summary["coverage"]["live_android_device_probe_verified"] is False, summary
assert summary["coverage"]["physical_external_relay_verified"] is False, summary
assert summary["coverage"]["adb_deeplink_injection"] is False, summary
assert summary["coverage"]["optical_camera_qr_scan"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
assert summary["coverage"]["production_relay_proof"] is False, summary
assert summary["coverage"]["production_session_key_exchange"] is False, summary
assert summary["coverage"]["production_session_key_exchange_proof"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption_proof"] is False, summary
assert summary["coverage"]["external_network_operator_confirmed"] is False, summary
assert summary["coverage"]["real_different_network_relay_verified"] is False, summary
assert summary["coverage"]["real_different_network_connectivity_proof"] is False, summary
assert summary["coverage"]["android_direct_model_backend_access"] is False, summary
assert summary["coverage"]["private_relay_allowed"] is False, summary
assert summary["coverage"]["private_or_same_lan_development_relay"] is False, summary
assert summary["android_device"]["observed_adb_serial"] is None, summary
assert "physical_external_relay_pairing_failed" in summary["caveats"], summary
assert "not_production_relay_proof" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "<invalid-host>" in combined, combined
for marker in (
    "provider.example.test",
    "11434/v1/models",
    "route_token=",
    "relay_secret=",
    "leaked-route-token",
    "leaked-relay-secret",
):
    assert marker not in combined, (marker, combined)
PY
  rm -rf "$work_dir"
}

check_physical_external_relay_probe_summary_redaction_guard() {
  local work_dir
  local summary_path
  local log_path
  local stdout_path
  local status_code

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-physical-wrapper-probe-redaction.XXXXXX")"
  summary_path="$work_dir/summary.json"
  log_path="$work_dir/run.log"
  stdout_path="$work_dir/stdout.json"

  set +e
  script/check_physical_external_relay_pairing.sh \
    --self-test-redact-probe-summary \
    --expect-chat-complete \
    --chat-text "External wrapper complete proof" \
    --chat-delta-timeout 9 \
    --chat-complete-timeout 11 \
    --chat-expected-terms "ExternalComplete" \
    --chat-model-query "gemma4:e4b-mlx" \
    --live-backend \
    --json "$summary_path" \
    --log "$log_path" \
    >"$stdout_path" \
    2>&1
  status_code=$?
  set -e

  if [[ "$status_code" -ne 0 ]]; then
    echo "Physical external-relay probe summary redaction self-test should pass, got $status_code" >&2
    cat "$stdout_path" >&2 || true
    rm -rf "$work_dir"
    exit 1
  fi

  python3 - "$summary_path" "$stdout_path" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
stdout = Path(sys.argv[2]).read_text(encoding="utf-8")
wrapper_log = Path(summary["artifacts"]["wrapper_log"]).read_text(encoding="utf-8", errors="replace")
combined = json.dumps(summary, sort_keys=True) + stdout + wrapper_log
assert summary["success"] is True, summary
assert summary["self_test_success"] is True, summary
assert summary["physical_external_relay_success"] is False, summary
assert summary["android_device"]["observed_adb_serial"] is None, summary
for marker in (
    "runtime-pairing-nonce-sensitive",
    "runtime-route-token-sensitive",
    "runtime-device-sensitive",
    "runtime-public-key-sensitive",
    "runtime-fingerprint-sensitive",
    "relay-id-sensitive",
    "relay-secret-sensitive",
    "relay-nonce-sensitive",
    "route-token-sensitive",
):
    assert marker not in combined, combined

route_summary = summary["probe_summaries"]["device_relay_route"]
assert route_summary["probe"]["reachable"] is True, summary
assert route_summary["probe"]["supported"] is True, summary
assert route_summary["probe"]["route_ready"] is True, summary
assert route_summary["relay"]["relay_id_present"] is True, summary
assert "relay_id" not in route_summary["relay"], summary
assert "relay_secret" not in route_summary["relay"], summary
assert "relay_nonce" not in route_summary["relay"], summary
assert "route_token" not in route_summary["relay"], summary
probe_output = route_summary["probe"]["output"]
assert "relay_id=" not in probe_output, summary
assert "relay_secret" not in probe_output, summary
assert "route_token" not in probe_output, summary
assert "route_material=<redacted>" in probe_output, summary
assert summary["coverage"]["external_relay_probe_reachable"] is True, summary
assert summary["coverage"]["external_relay_probe_supported"] is True, summary
assert summary["coverage"]["external_relay_route_ready"] is True, summary
assert summary["coverage"]["probe_summary_redaction_self_test"] is True, summary
assert summary["coverage"]["android_pairing_summary_json_present"] is True, summary
assert summary["coverage"]["android_pairing_summary_success"] is True, summary
assert summary["coverage"]["android_pairing_summary_external_relay_mode"] is True, summary
assert summary["coverage"]["android_pairing_summary_no_relay_adb_reverse"] is True, summary
assert summary["coverage"]["android_pairing_summary_proof_boundary_preserved"] is True, summary
assert summary["coverage"]["android_pairing_summary_live_provider_chat_complete_proof"] is True, summary
assert summary["coverage"]["android_pairing_summary_chat_expected_terms_observed"] == ["ExternalComplete"], summary
assert summary["coverage"]["expect_chat_complete"] is True, summary
assert summary["coverage"]["chat_model_query_requested"] is True, summary
assert summary["coverage"]["live_backend"] is True, summary
assert summary["coverage"]["chat_done_count"] == 1, summary
assert summary["coverage"]["live_android_device_probe_verified"] is False, summary
assert summary["coverage"]["physical_external_relay_verified"] is False, summary
assert summary["coverage"]["adb_deeplink_injection"] is True, summary
assert summary["coverage"]["optical_camera_qr_scan"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
assert summary["coverage"]["production_relay_proof"] is False, summary
assert summary["coverage"]["production_session_key_exchange"] is False, summary
assert summary["coverage"]["production_session_key_exchange_proof"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption_proof"] is False, summary
assert summary["coverage"]["external_network_operator_confirmed"] is False, summary
assert summary["coverage"]["real_different_network_relay_verified"] is False, summary
assert summary["coverage"]["real_different_network_connectivity_proof"] is False, summary
assert summary["coverage"]["android_direct_model_backend_access"] is False, summary
assert summary["coverage"]["private_relay_allowed"] is False, summary
assert summary["coverage"]["private_or_same_lan_development_relay"] is False, summary
assert summary["coverage"]["wrapper_log_artifact_present"] is True, summary
assert summary["coverage"]["wrapper_log_omits_temporary_secret_material"] is True, summary
assert summary["coverage"]["wrapper_log_contains_unredacted_route_material"] is False, summary
assert summary["coverage"]["runtime_log_artifact_present"] is True, summary
assert summary["coverage"]["runtime_log_contains_temporary_pairing_material"] is True, summary
assert summary["coverage"]["runtime_log_contains_temporary_route_material"] is True, summary
assert "wrapper_log_contains_unredacted_route_material" not in summary["caveats"], summary
assert "wrapper_log_redaction_not_verified" not in summary["caveats"], summary
assert "self_test_redaction_only_not_physical_relay_proof" in summary["caveats"], summary
assert "not_production_relay_proof" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "runtime_log_contains_temporary_pairing_or_route_material" in summary["caveats"], summary
assert "aetherlink://pair?<redacted>" in wrapper_log, wrapper_log
child = summary["child_summaries"]["android_pairing_deeplink"]
assert child["success"] is True, summary
assert child["coverage"]["external_relay_mode"] is True, summary
assert child["coverage"]["adb_reverse_relay_used"] is False, summary
assert child["coverage"]["chat_complete_requested"] is True, summary
assert child["coverage"]["chat_send_observed"] is True, summary
assert child["coverage"]["chat_delta_observed"] is True, summary
assert child["coverage"]["chat_done_observed"] is True, summary
assert child["coverage"]["live_backend_requested"] is True, summary
assert child["coverage"]["live_provider_chat_complete_proof"] is True, summary
assert child["coverage"]["chat_expected_terms_requested"] is True, summary
assert child["coverage"]["chat_expected_terms_observed"] == ["ExternalComplete"], summary
assert child["coverage"]["chat_model_query_requested"] is True, summary
assert child["coverage"]["chat_model_runtime_log_confirmed"] is True, summary
assert child["coverage"]["optical_camera_qr_scan"] is False, summary
assert child["coverage"]["production_relay_proof"] is False, summary
assert child["coverage"]["production_session_key_exchange_proof"] is False, summary
assert child["coverage"]["production_end_to_end_transport_encryption_proof"] is False, summary
assert child["coverage"]["real_different_network_connectivity_proof"] is False, summary
assert child["coverage"]["android_direct_model_backend_access"] is False, summary
assert child["paths_present"]["external_relay_route_probe_json"] is True, summary
assert child["paths_present"]["chat_complete_ui_xml"] is False, summary
for marker in ("pairing_nonce=", "pairing_code=", "relay_secret=", "relay_nonce=", "route_token=", "allocation_token=", "requested_route_token=", "runtime_public_key=", "runtime_key_fingerprint=", "rs=", "rrn=", "rt=", "rk=", "rf="):
    assert marker not in wrapper_log, wrapper_log
PY

  rm -rf "$work_dir"
}

check_physical_external_relay_different_network_confirmation_guard() {
  local work_dir
  local summary_path
  local log_path
  local output
  local status_code

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-physical-wrapper-confirmation.XXXXXX")"
  summary_path="$work_dir/summary.json"
  log_path="$work_dir/run.log"
  set +e
  output="$(
    AETHERLINK_DIFFERENT_NETWORK_CONFIRMED=0 \
    ADB=/bin/true \
      script/check_physical_external_relay_pairing.sh \
        --relay-host 0.0.0.0 \
        --require-different-network-confirmation \
        --json "$summary_path" \
        --log "$log_path" \
        2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Physical external-relay wrapper confirmation guard should exit 2, got $status_code" >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"Set AETHERLINK_DIFFERENT_NETWORK_CONFIRMED=1 after putting the phone on a different network."* ]]; then
    echo "Physical external-relay wrapper confirmation guard did not explain the required operator confirmation." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ -e "$summary_path" || -e "$log_path" ]]; then
    echo "Physical external-relay wrapper confirmation guard should stop before writing QA artifacts." >&2
    rm -rf "$work_dir"
    exit 1
  fi
  rm -rf "$work_dir"
}

check_android_relay_reachability_probe_input_guard() {
  local output
  local status_code

  set +e
  output="$(script/android_relay_reachability_probe.sh --host https://relay.example.test --port 43171 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Android relay reachability probe should reject URL-shaped hosts before ADB access, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"--host must be a host or IP address, not a URL."* ]]; then
    echo "Android relay reachability probe did not explain the URL-shaped host rejection." >&2
    echo "$output" >&2
    exit 1
  fi

  set +e
  output="$(script/android_relay_reachability_probe.sh --host relay.example.test --port 0 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Android relay reachability probe should reject invalid ports before ADB access, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"--port must be an integer in 1..65535."* ]]; then
    echo "Android relay reachability probe did not explain the invalid port rejection." >&2
    echo "$output" >&2
    exit 1
  fi

  set +e
  output="$(script/android_relay_reachability_probe.sh --host relay.example.test --port 43171 --relay-id "relay 1" 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Android relay reachability probe should reject malformed relay IDs before ADB access, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"--relay-id must be a non-empty relay token without whitespace."* ]]; then
    echo "Android relay reachability probe did not explain the malformed relay ID rejection." >&2
    echo "$output" >&2
    exit 1
  fi
}

check_android_relay_reachability_probe_route_material_redaction_guard() {
  local work_dir
  local fake_adb
  local summary_json
  local stdout_log
  local stderr_log
  local case_summary_json
  local case_stdout_log
  local case_stderr_log
  local probe_case
  local status_code

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-probe-redaction.XXXXXX")"
  fake_adb="$work_dir/adb"
  summary_json="$work_dir/summary.json"
  stdout_log="$work_dir/stdout.log"
  stderr_log="$work_dir/stderr.log"

  cat >"$fake_adb" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "devices" ]]; then
  echo "List of devices attached"
  echo "fake-device	device"
  exit 0
fi

if [[ "${1:-}" == "-s" ]]; then
  shift 2
fi

if [[ "${1:-}" == "devices" ]]; then
  echo "List of devices attached"
  echo "fake-device	device"
  exit 0
fi

if [[ "${1:-}" == "shell" ]]; then
  shift
  command_line="$*"
  if [[ "$command_line" == *"command -v nc"* ]]; then
    echo "/system/bin/nc"
    exit 0
  fi
  if [[ "$command_line" == *"dumpsys connectivity"* ]]; then
    echo "NetworkAgentInfo WIFI validated"
    exit 0
  fi
  if [[ "$command_line" == nc\ -z\ * ]]; then
    if [[ "${FAKE_RELAY_TCP_UNREACHABLE:-0}" == "1" ]]; then
      echo "nc: tcp-failure-secret" >&2
      exit 1
    fi
    exit 0
  fi
  if [[ "$command_line" == *"AETHERLINK_RELAY probe"* ]]; then
    response_status=0
    case "${FAKE_RELAY_PROBE_CASE:-known_ready}" in
      known_ready)
        echo "AETHERLINK_RELAY probe known=1 runtime_waiting=1"
        ;;
      allocated_ready)
        echo "AETHERLINK_RELAY probe allocated=YES runtime_waiting=TRUE"
        ;;
      known_false)
        echo "AETHERLINK_RELAY probe known=0 runtime_waiting=1"
        ;;
      allocated_false)
        echo "AETHERLINK_RELAY probe allocated=false runtime_waiting=yes"
        ;;
      runtime_not_waiting)
        echo "AETHERLINK_RELAY probe known=true runtime_waiting=no"
        ;;
      empty)
        ;;
      extra)
        echo "AETHERLINK_RELAY probe known=1 runtime_waiting=1 extra=extra-probe-secret"
        ;;
      duplicate)
        echo "AETHERLINK_RELAY probe known=1 known=duplicate-probe-secret runtime_waiting=1"
        ;;
      secret_bearing)
        echo "AETHERLINK_RELAY probe known=1 runtime_waiting=1 relay_secret=secret-bearing-probe-marker"
        response_status=7
        ;;
      known_ready_nonzero)
        echo "AETHERLINK_RELAY probe known=1 runtime_waiting=1"
        response_status=7
        ;;
      known_false_nonzero)
        echo "AETHERLINK_RELAY probe known=0 runtime_waiting=1"
        response_status=7
        ;;
      incomplete)
        echo "AETHERLINK_RELAY probe known=incomplete-probe-secret"
        ;;
      unknown)
        echo "UNKNOWN_RELAY_RESPONSE unknown-probe-secret"
        ;;
      *)
        echo "Unexpected fake relay probe case" >&2
        exit 1
        ;;
    esac
    exit "$response_status"
  fi
fi

echo "Unexpected fake adb invocation: $*" >&2
exit 1
SH
  chmod +x "$fake_adb"

  set +e
  AETHERLINK_RELAY_PROBE_SELF_TEST=1 ADB="$fake_adb" script/android_relay_reachability_probe.sh \
    --host relay.example.test \
    --port 43171 \
    --relay-id rt1-sensitive-route-material \
    --json "$summary_json" \
    >"$stdout_log" \
    2>"$stderr_log"
  status_code=$?
  set -e

  if [[ "$status_code" -ne 0 ]]; then
    echo "Android relay reachability probe route-material redaction guard should pass with fake adb, got $status_code" >&2
    cat "$stdout_log" >&2 || true
    cat "$stderr_log" >&2 || true
    rm -rf "$work_dir"
    exit 1
  fi

  python3 - "$summary_json" "$stdout_log" "$stderr_log" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
stdout = Path(sys.argv[2]).read_text(encoding="utf-8")
stderr = Path(sys.argv[3]).read_text(encoding="utf-8")
marker = "rt1-sensitive-route-material"
combined = json.dumps(summary, sort_keys=True) + stdout + stderr
assert marker not in combined, combined
assert summary["evidence"]["source"] == "fake_adb_redaction_self_test", summary
assert summary["evidence"]["self_test"] is True, summary
assert summary["device"]["adb_serial"] is None, summary
assert "relay_id" not in summary["relay"], summary
assert summary["relay"]["relay_id_present"] is True, summary
assert summary["probe"]["route_ready"] is True, summary
assert summary["probe"]["supported"] is True, summary
assert summary["probe"]["reachable"] is True, summary
assert summary["coverage"]["android_relay_probe_redaction_self_test"] is True, summary
assert summary["coverage"]["live_android_relay_probe_verified"] is False, summary
assert summary["coverage"]["live_android_route_probe_verified"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
assert summary["coverage"]["production_session_key_exchange"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption"] is False, summary
assert "android_relay_probe_redaction_self_test_not_phone_reachability_proof" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert summary["probe"]["result"] == "ready", summary
assert summary["probe"]["raw_exit_status"] == 0, summary
assert summary["probe"]["response_exit_status"] == 0, summary
assert summary["probe"]["route_known"] is True, summary
assert summary["probe"]["runtime_waiting"] is True, summary
assert summary["probe"]["output"] == "AETHERLINK_RELAY probe known=true runtime_waiting=true", summary
assert "redaction self-test" in stdout, stdout
assert "not phone reachability proof" in stdout, stdout
PY

  case_summary_json="$work_dir/allocated-ready-summary.json"
  case_stdout_log="$work_dir/allocated-ready-stdout.log"
  case_stderr_log="$work_dir/allocated-ready-stderr.log"
  set +e
  FAKE_RELAY_PROBE_CASE=allocated_ready AETHERLINK_RELAY_PROBE_SELF_TEST=1 ADB="$fake_adb" \
    script/android_relay_reachability_probe.sh \
      --host relay.example.test \
      --port 43171 \
      --relay-id rt1-sensitive-route-material \
      --json "$case_summary_json" \
      >"$case_stdout_log" \
      2>"$case_stderr_log"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 0 ]]; then
    echo "Canonical allocated=true relay probe should be route-ready, got $status_code" >&2
    cat "$case_stdout_log" >&2 || true
    cat "$case_stderr_log" >&2 || true
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$case_summary_json" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert summary["probe"]["result"] == "ready", summary
assert summary["probe"]["raw_exit_status"] == 0, summary
assert summary["probe"]["response_exit_status"] == 0, summary
assert summary["probe"]["supported"] is True, summary
assert summary["probe"]["route_ready"] is True, summary
assert summary["probe"]["route_known"] is True, summary
assert summary["probe"]["runtime_waiting"] is True, summary
assert summary["probe"]["output"] == "AETHERLINK_RELAY probe known=true runtime_waiting=true", summary
PY

  for probe_case in known_false allocated_false runtime_not_waiting; do
    case_summary_json="$work_dir/$probe_case-summary.json"
    case_stdout_log="$work_dir/$probe_case-stdout.log"
    case_stderr_log="$work_dir/$probe_case-stderr.log"
    set +e
    FAKE_RELAY_PROBE_CASE="$probe_case" AETHERLINK_RELAY_PROBE_SELF_TEST=1 ADB="$fake_adb" \
      script/android_relay_reachability_probe.sh \
        --host relay.example.test \
        --port 43171 \
        --relay-id rt1-sensitive-route-material \
        --json "$case_summary_json" \
        >"$case_stdout_log" \
        2>"$case_stderr_log"
    status_code=$?
    set -e
    if [[ "$status_code" -ne 1 ]]; then
      echo "Canonical unavailable relay probe case $probe_case should fail, got $status_code" >&2
      cat "$case_stdout_log" >&2 || true
      cat "$case_stderr_log" >&2 || true
      rm -rf "$work_dir"
      exit 1
    fi
    python3 - "$case_summary_json" "$probe_case" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
probe_case = sys.argv[2]
probe = summary["probe"]
assert probe["result"] == "unavailable", summary
assert probe["raw_exit_status"] == 0, summary
assert probe["response_exit_status"] == 0, summary
assert probe["supported"] is True, summary
assert probe["tcp_reachable"] is True, summary
assert probe["route_ready"] is False, summary
assert probe["reachable"] is False, summary
assert probe["route_known"] is (probe_case == "runtime_not_waiting"), summary
assert probe["runtime_waiting"] is (probe_case != "runtime_not_waiting"), summary
assert probe["output"] in {
    "AETHERLINK_RELAY probe known=false runtime_waiting=true",
    "AETHERLINK_RELAY probe known=true runtime_waiting=false",
}, summary
assert "relay_route_probe_unsupported_authenticated_connection_required" not in summary["caveats"], summary
PY
  done

  for probe_case in empty extra duplicate secret_bearing known_ready_nonzero known_false_nonzero incomplete unknown; do
    case_summary_json="$work_dir/$probe_case-summary.json"
    case_stdout_log="$work_dir/$probe_case-stdout.log"
    case_stderr_log="$work_dir/$probe_case-stderr.log"
    set +e
    FAKE_RELAY_PROBE_CASE="$probe_case" AETHERLINK_RELAY_PROBE_SELF_TEST=1 ADB="$fake_adb" \
      script/android_relay_reachability_probe.sh \
        --host relay.example.test \
        --port 43171 \
        --relay-id rt1-sensitive-route-material \
        --json "$case_summary_json" \
        >"$case_stdout_log" \
        2>"$case_stderr_log"
    status_code=$?
    set -e
    if [[ "$status_code" -ne 0 ]]; then
      echo "Unsupported relay probe case $probe_case should continue to authenticated pairing, got $status_code" >&2
      cat "$case_stdout_log" >&2 || true
      cat "$case_stderr_log" >&2 || true
      rm -rf "$work_dir"
      exit 1
    fi
    python3 - "$case_summary_json" "$case_stdout_log" "$case_stderr_log" "$probe_case" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
stdout = Path(sys.argv[2]).read_text(encoding="utf-8")
stderr = Path(sys.argv[3]).read_text(encoding="utf-8")
probe_case = sys.argv[4]
combined = json.dumps(summary, sort_keys=True) + stdout + stderr
probe = summary["probe"]
assert probe["result"] == "unsupported", summary
assert probe["raw_exit_status"] == 0, summary
assert probe["response_exit_status"] == (
    7 if probe_case in {"secret_bearing", "known_ready_nonzero", "known_false_nonzero"} else 0
), summary
assert summary["probe"]["supported"] is False, summary
assert summary["probe"]["reachable"] is True, summary
assert summary["probe"]["route_ready"] is False, summary
assert probe["tcp_reachable"] is True, summary
assert probe["route_known"] is None, summary
assert probe["runtime_waiting"] is None, summary
assert probe["output"] is None, summary
assert summary["coverage"]["live_android_relay_probe_verified"] is False, summary
assert summary["coverage"]["live_android_route_probe_verified"] is False, summary
assert "relay_route_probe_unsupported_authenticated_connection_required" in summary["caveats"], summary
assert "authenticated pairing must verify the route" in stdout, stdout
for marker in (
    "rt1-sensitive-route-material",
    "extra-probe-secret",
    "duplicate-probe-secret",
    "secret-bearing-probe-marker",
    "incomplete-probe-secret",
    "unknown-probe-secret",
):
    assert marker not in combined, (probe_case, marker, combined)
PY
  done

  case_summary_json="$work_dir/tcp-unavailable-summary.json"
  case_stdout_log="$work_dir/tcp-unavailable-stdout.log"
  case_stderr_log="$work_dir/tcp-unavailable-stderr.log"
  set +e
  FAKE_RELAY_TCP_UNREACHABLE=1 AETHERLINK_RELAY_PROBE_SELF_TEST=1 ADB="$fake_adb" \
    script/android_relay_reachability_probe.sh \
      --host relay.example.test \
      --port 43171 \
      --relay-id rt1-sensitive-route-material \
      --json "$case_summary_json" \
      >"$case_stdout_log" \
      2>"$case_stderr_log"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 1 ]]; then
    echo "Genuine relay TCP connection failure should be unavailable, got $status_code" >&2
    cat "$case_stdout_log" >&2 || true
    cat "$case_stderr_log" >&2 || true
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$case_summary_json" "$case_stdout_log" "$case_stderr_log" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
stdout = Path(sys.argv[2]).read_text(encoding="utf-8")
stderr = Path(sys.argv[3]).read_text(encoding="utf-8")
combined = json.dumps(summary, sort_keys=True) + stdout + stderr
probe = summary["probe"]
assert probe["result"] == "unavailable", summary
assert probe["raw_exit_status"] == 1, summary
assert probe["response_exit_status"] is None, summary
assert probe["tcp_reachable"] is False, summary
assert probe["supported"] is False, summary
assert probe["route_ready"] is False, summary
assert probe["reachable"] is False, summary
assert probe["route_known"] is None, summary
assert probe["runtime_waiting"] is None, summary
assert probe["output"] is None, summary
assert "relay_route_probe_unsupported_authenticated_connection_required" not in summary["caveats"], summary
assert "tcp-failure-secret" not in combined, combined
PY

  rm -rf "$work_dir"
}

check_android_pairing_deeplink_am_start_log_redaction_guard() {
  local output
  local marker
  local sensitive_markers=(
    "pairing-nonce-sensitive"
    "pairing-code-sensitive"
    "route-token-sensitive"
    "relay-id-sensitive"
    "relay-secret-sensitive"
    "relay-nonce-sensitive"
    "pairing_nonce"
    "pairing_code"
    "route_token"
    "relay_id"
    "relay_secret"
    "relay_nonce"
  )

  output="$(
    printf '%s\n' \
      "Starting: Intent { act=android.intent.action.VIEW dat=aetherlink://pair?version=1&pairing_nonce=pairing-nonce-sensitive&pairing_code=pairing-code-sensitive&runtime_device_id=runtime-1&route_token=route-token-sensitive&relay_host=relay.example.test&relay_port=43171&relay_id=relay-id-sensitive&relay_secret=relay-secret-sensitive&relay_expires_at=4102444800000&relay_nonce=relay-nonce-sensitive cmp=com.localagentbridge.android/.MainActivity }" \
      "Status: ok" \
      | script/android_pairing_deeplink_smoke.sh --self-test-sanitize-am-start-log
  )"

  if [[ "$output" != *"dat=aetherlink://pair?<redacted>"* ]]; then
    echo "Android pairing deeplink smoke should preserve only a redacted pairing URI marker in am start logs." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"am_start_sanitizer_self_test_not_android_intent_or_phone_pairing_proof"* ]]; then
    echo "Android pairing deeplink am-start sanitizer self-test should mark its output as not phone pairing proof." >&2
    echo "$output" >&2
    exit 1
  fi

  for marker in "${sensitive_markers[@]}"; do
    if [[ "$output" == *"$marker"* ]]; then
      echo "Android pairing deeplink smoke exposed route material in sanitized am start output: $marker" >&2
      echo "$output" >&2
      exit 1
    fi
  done
}

check_android_pairing_failure_artifact_redaction_guard() {
  local output
  local sensitive_markers=(
    "pairing-nonce-sensitive"
    "pairing-code-sensitive"
    "route-token-sensitive"
    "relay-id-sensitive"
    "relay-secret-sensitive"
    "relay-nonce-sensitive"
    "runtime-public-key-sensitive"
    "runtime-fingerprint-sensitive"
    "allocation-token-sensitive"
    "compact-route-token-sensitive"
    "compact-relay-secret-sensitive"
    "compact-relay-nonce-sensitive"
    "leaked-route-token"
    "leaked-relay-secret"
  )

  output="$(
    printf '%s\n' \
      "ActivityTaskManager: START u0 {act=android.intent.action.VIEW dat=aetherlink://pair?version=1&pairing_nonce=pairing-nonce-sensitive&pairing_code=pairing-code-sensitive&runtime_public_key=runtime-public-key-sensitive&runtime_key_fingerprint=runtime-fingerprint-sensitive&route_token=route-token-sensitive&relay_host=relay.example.test&relay_port=43171&relay_id=relay-id-sensitive&relay_secret=relay-secret-sensitive&relay_expires_at=4102444800000&relay_nonce=relay-nonce-sensitive cmp=com.localagentbridge.android/.MainActivity}" \
      "AetherLink Runtime connection failed code=remote_route_unreachable diagnostic=route_diagnostic_relay_failed route_token=leaked-route-token relay_secret=leaked-relay-secret allocation_token=allocation-token-sensitive" \
      "am_start dat=aetherlink://pair?n=pairing-nonce-sensitive&c=pairing-code-sensitive&rt=compact-route-token-sensitive&rk=runtime-public-key-sensitive&rf=runtime-fingerprint-sensitive&ri=relay-id-sensitive&rs=compact-relay-secret-sensitive&rrn=compact-relay-nonce-sensitive" \
      "Connecting to runtime relay_id=relay-id-sensitive relay_nonce=relay-nonce-sensitive" \
      | script/android_pairing_deeplink_smoke.sh --self-test-sanitize-android-qa-artifacts
  )"

  if [[ "$output" != *"android_qa_artifact_sanitizer_self_test_not_phone_logcat_or_activity_proof"* ]]; then
    echo "Android QA artifact sanitizer self-test should mark its output as not phone logcat/activity proof." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"aetherlink://pair?<redacted>"* ]]; then
    echo "Android QA artifact sanitizer should preserve only redacted pairing URI markers." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"Runtime connection failed code=remote_route_unreachable diagnostic=route_diagnostic_relay_failed"* ]]; then
    echo "Android QA artifact sanitizer should preserve structured runtime failure diagnostics." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"Connecting to runtime"* ]]; then
    echo "Android QA artifact sanitizer should preserve route-attempt diagnosis copy." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"<redacted>"* ]]; then
    echo "Android QA artifact sanitizer should include explicit redaction markers." >&2
    echo "$output" >&2
    exit 1
  fi

  for marker in "${sensitive_markers[@]}"; do
    if [[ "$output" == *"$marker"* ]]; then
      echo "Android QA artifact sanitizer exposed route material marker: $marker" >&2
      echo "$output" >&2
      exit 1
    fi
  done
}

check_android_pairing_chat_model_query_selector_guard() {
  local output

  output="$(
    AETHERLINK_ANDROID_CHAT_MODEL_QUERY="lm_studio:target-model" \
      script/android_pairing_deeplink_smoke.sh --self-test-chat-model-query-selector <<'XML'
<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node class="android.view.View" content-desc="Chat model picker. Selected chat model Target Model." enabled="true" bounds="[10,10][600,110]" />
  <node class="android.view.View" content-desc="Refresh models" enabled="true" bounds="[100,160][900,280]" />
  <node class="android.view.View" content-desc="Selected chat model Target Model. LM Studio - Installed." enabled="true" bounds="[100,640][900,780]" />
  <node class="android.view.View" content-desc="Chat model Other Model. Ollama - Installed." enabled="true" bounds="[100,820][900,960]" />
</hierarchy>
XML
  )"

  if [[ "$output" != *"chat_model_query_selector_self_test_not_phone_model_selection_proof"* ]]; then
    echo "Android pairing chat-model query selector self-test should mark its output as not phone model-selection proof." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"500 710 Selected chat model Target Model. LM Studio - Installed."* ]]; then
    echo "Android pairing chat-model query selector should choose the LM Studio row from a provider-qualified query." >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" == *"Chat model picker. Selected chat model Target Model."* ]]; then
    echo "Android pairing chat-model query selector must not choose the top-bar picker summary." >&2
    echo "$output" >&2
    exit 1
  fi
}

check_android_pairing_summary_json_guard() {
  local work_dir
  local summary_path
  local complete_summary_path
  local failure_summary_path
  local output
  local complete_output
  local failure_output

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-summary-json-guard.XXXXXX")"
  summary_path="$work_dir/summary.json"
  complete_summary_path="$work_dir/complete-summary.json"
  failure_summary_path="$work_dir/failure-summary.json"
  output="$(
    script/android_pairing_deeplink_smoke.sh \
      --self-test-summary-json \
      --summary-json "$summary_path"
  )"

  if [[ "$output" != *"android_pairing_summary_json_self_test_not_phone_pairing_proof"* ]]; then
    echo "Android pairing summary JSON self-test should mark output as not phone pairing proof." >&2
    echo "$output" >&2
    exit 1
  fi

  python3 - "$summary_path" <<'PY'
import json
import sys

summary_path = sys.argv[1]
with open(summary_path, "r", encoding="utf-8") as handle:
    summary = json.load(handle)

coverage = summary.get("coverage", {})
required_true = {
    "adb_deeplink_injection_succeeded",
    "runtime_pairing_accepted",
    "runtime_health_observed",
    "models_list_observed",
    "trusted_route_reconnect_verified",
    "chat_send_observed",
    "chat_delta_observed",
    "chat_cancel_observed",
    "chat_done_observed",
    "live_backend_requested",
    "live_provider_chat_cancel_proof",
    "chat_model_query_requested",
    "chat_model_runtime_log_confirmed",
    "ui_polish_capture_requested",
    "ui_polish_capture_artifacts",
    "ui_polish_capture_artifact_manifest_complete",
}
required_false = {
    "optical_camera_qr_scan",
    "production_relay_proof",
    "production_session_key_exchange_proof",
    "production_end_to_end_transport_encryption_proof",
    "real_different_network_connectivity_proof",
    "android_direct_model_backend_access",
}
missing_true = sorted(key for key in required_true if coverage.get(key) is not True)
missing_false = sorted(key for key in required_false if coverage.get(key) is not False)
if missing_true or missing_false:
    raise SystemExit(
        "summary coverage mismatch; true=%s false=%s"
        % (",".join(missing_true), ",".join(missing_false))
    )

ui_artifacts = summary.get("paths", {}).get("ui_polish_artifacts", {})
required_ui_artifacts = {
    "chat",
    "model_selector",
    "drawer",
    "settings",
    "launcher",
}
missing_artifacts = []
for key in sorted(required_ui_artifacts):
    entry = ui_artifacts.get(key, {})
    if not entry.get("screenshot") or not entry.get("ui_xml"):
        missing_artifacts.append(key)
if missing_artifacts:
    raise SystemExit("missing UI polish artifact manifest entries: %s" % ",".join(missing_artifacts))

encoded = json.dumps(summary, ensure_ascii=False).lower()
for forbidden in (
    "aetherlink://pair?",
    "pairing_uri",
    "relay_secret",
    "route_token",
    "allocation_token",
    "provider_url",
    "backend_url",
):
    if forbidden in encoded:
        raise SystemExit(f"summary JSON exposed forbidden route/backend material marker: {forbidden}")
PY

  complete_output="$(
    script/android_pairing_deeplink_smoke.sh \
      --self-test-chat-complete-summary-json \
      --summary-json "$complete_summary_path"
  )"

  if [[ "$complete_output" != *"android_pairing_chat_complete_summary_json_self_test_not_phone_chat_proof"* ]]; then
    echo "Android pairing chat-complete summary JSON self-test should mark output as not phone chat proof." >&2
    echo "$complete_output" >&2
    exit 1
  fi

  python3 - "$complete_summary_path" <<'PY'
import json
import sys

summary_path = sys.argv[1]
with open(summary_path, "r", encoding="utf-8") as handle:
    summary = json.load(handle)

coverage = summary.get("coverage", {})
required_true = {
    "adb_deeplink_injection_succeeded",
    "runtime_pairing_accepted",
    "runtime_health_observed",
    "models_list_observed",
    "chat_complete_requested",
    "chat_send_observed",
    "chat_delta_observed",
    "chat_done_observed",
    "live_backend_requested",
    "live_provider_chat_complete_proof",
    "chat_expected_terms_requested",
    "chat_model_query_requested",
    "chat_model_runtime_log_confirmed",
}
required_false = {
    "chat_cancel_requested",
    "chat_cancel_observed",
    "live_provider_chat_cancel_proof",
    "trusted_route_reconnect_verified",
    "ui_polish_capture_artifacts",
    "ui_polish_capture_artifact_manifest_complete",
    "optical_camera_qr_scan",
    "production_relay_proof",
    "production_session_key_exchange_proof",
    "production_end_to_end_transport_encryption_proof",
    "real_different_network_connectivity_proof",
    "android_direct_model_backend_access",
}
missing_true = sorted(key for key in required_true if coverage.get(key) is not True)
missing_false = sorted(key for key in required_false if coverage.get(key) is not False)
if missing_true or missing_false:
    raise SystemExit(
        "chat-complete summary coverage mismatch; true=%s false=%s"
        % (",".join(missing_true), ",".join(missing_false))
    )

observed_terms = set(coverage.get("chat_expected_terms_observed", []))
if not {"CompleteProof", "런타임"}.issubset(observed_terms):
    raise SystemExit("chat-complete summary did not preserve expected-term observation")

if "chat_complete_ui_xml" not in summary.get("paths", {}):
    raise SystemExit("chat-complete summary should include completed transcript UI XML")

encoded = json.dumps(summary, ensure_ascii=False).lower()
for forbidden in (
    "aetherlink://pair?",
    "pairing_uri",
    "relay_secret",
    "route_token",
    "allocation_token",
    "provider_url",
    "backend_url",
):
    if forbidden in encoded:
        raise SystemExit(f"chat-complete summary JSON exposed forbidden route/backend material marker: {forbidden}")
PY

  failure_output="$(
    script/android_pairing_deeplink_smoke.sh \
      --self-test-summary-json-failure \
      --summary-json "$failure_summary_path"
  )"

  if [[ "$failure_output" != *"android_pairing_summary_json_failure_self_test_not_phone_pairing_proof"* ]]; then
    echo "Android pairing failure summary JSON self-test should mark output as not phone pairing proof." >&2
    echo "$failure_output" >&2
    exit 1
  fi

  python3 - "$failure_summary_path" <<'PY'
import json
import sys

summary_path = sys.argv[1]
with open(summary_path, "r", encoding="utf-8") as handle:
    summary = json.load(handle)

if summary.get("success") is not False or summary.get("exit_status") != 42:
    raise SystemExit("failure summary should preserve unsuccessful status and exit code")

coverage = summary.get("coverage", {})
required_true = {
    "adb_deeplink_injection_attempted",
    "app_install_attempted",
    "app_data_clear_attempted",
    "adb_reverse_runtime_used",
    "adb_reverse_relay_used",
    "trusted_route_reconnect_requested",
    "chat_complete_requested",
    "chat_cancel_requested",
    "live_backend_requested",
    "chat_model_query_requested",
    "ui_polish_capture_requested",
}
required_false = {
    "physical_device_observed",
    "adb_deeplink_injection_succeeded",
    "app_install_succeeded",
    "app_data_cleared",
    "runtime_pairing_accepted",
    "runtime_health_observed",
    "models_list_observed",
    "trusted_route_reconnect_verified",
    "chat_send_observed",
    "chat_delta_observed",
    "chat_cancel_observed",
    "chat_done_observed",
    "live_provider_chat_cancel_proof",
    "live_provider_chat_complete_proof",
    "chat_model_runtime_log_confirmed",
    "ui_polish_capture_artifacts",
    "ui_polish_capture_artifact_manifest_complete",
    "optical_camera_qr_scan",
    "production_relay_proof",
    "production_session_key_exchange_proof",
    "production_end_to_end_transport_encryption_proof",
    "real_different_network_connectivity_proof",
    "android_direct_model_backend_access",
}
missing_true = sorted(key for key in required_true if coverage.get(key) is not True)
missing_false = sorted(key for key in required_false if coverage.get(key) is not False)
if missing_true or missing_false:
    raise SystemExit(
        "failure summary coverage mismatch; true=%s false=%s"
        % (",".join(missing_true), ",".join(missing_false))
    )

if coverage.get("chat_expected_terms_observed"):
    raise SystemExit("failure summary should not observe completed-chat expected terms")

if "ui_polish_artifacts" in summary.get("paths", {}):
    raise SystemExit("failure summary should not invent a UI polish artifact manifest")

encoded = json.dumps(summary, ensure_ascii=False).lower()
for forbidden in (
    "aetherlink://pair?",
    "pairing_uri",
    "relay_secret",
    "route_token",
    "allocation_token",
    "provider_url",
    "backend_url",
):
    if forbidden in encoded:
        raise SystemExit(f"failure summary JSON exposed forbidden route/backend material marker: {forbidden}")
PY
}

check_macos_dock_capture_dry_run_summary_guard() {
  local work_dir
  local output_path
  local summary_path
  local stdout_log

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-macos-dock-dry-run.XXXXXX")"
  output_path="$work_dir/aetherlink-macos-dock-visible.png"
  summary_path="$work_dir/summary.json"
  stdout_log="$work_dir/stdout.log"

  script/capture_macos_dock_icon.sh \
    --dry-run \
    --output "$output_path" \
    --summary-json "$summary_path" \
    >"$stdout_log"

  python3 - "$summary_path" "$stdout_log" "$output_path" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
stdout = Path(sys.argv[2]).read_text(encoding="utf-8")
output_path = Path(sys.argv[3])
summary = json.loads(summary_path.read_text(encoding="utf-8"))

assert "Dock capture dry-run summary:" in stdout, stdout
assert "Not a macOS Dock screenshot proof." in stdout, stdout
assert not output_path.exists(), output_path
assert summary["exit_status"] == 0, summary
assert summary["mode"]["dry_run"] is True, summary
assert Path(summary["paths"]["output"]) == output_path, summary
assert summary["paths"]["bundle"].endswith("dist/AetherLink.app"), summary
coverage = summary["coverage"]
assert coverage["macos_dock_capture_dry_run"] is True, summary
assert coverage["macos_dock_capture_verified"] is False, summary
assert coverage["macos_dock_screenshot_artifact_present"] is False, summary
assert coverage["physical_macos_dock_screenshot"] is False, summary
assert coverage["dock_autohide_changed"] is False, summary
assert "dry_run_not_macos_dock_screenshot_proof" in summary["caveats"], summary
PY

  rm -rf "$work_dir"
}

free_tcp_port() {
  python3 - <<'PY'
import socket

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
}

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "JAVA_HOME does not point to a runnable JDK: $JAVA_HOME" >&2
  echo "Set JAVA_HOME or install Android Studio's bundled JBR before running this check." >&2
  exit 1
fi

run python3 -m py_compile \
  script/check_android_string_parity.py \
  script/check_macos_localization.py \
	  script/check_protocol_schema.py \
	  script/check_p2p_nat_contract_vectors.py \
	  script/check_p2p_nat_pre_network_review.py \
	  script/test_p2p_nat_pre_network_review.py \
	  script/check_p2p_nat_controlled_spike_review.py \
	  script/test_p2p_nat_controlled_spike_review.py \
	  script/check_p2p_nat_session_crypto_vectors.py \
	  script/test_p2p_nat_session_crypto_vectors.py \
	  script/check_p2p_nat_phase_a_harness_egress.py \
	  script/test_p2p_nat_phase_a_harness_egress.py \
	  script/check_p2p_nat_libjuice_offline_source.py \
	  script/test_p2p_nat_libjuice_offline_source.py \
	  script/check_p2p_nat_libjuice_compile_only.py \
	  script/test_p2p_nat_libjuice_compile_only.py \
	  script/check_p2p_nat_security_design.py \
	  script/check_p2p_nat_phase_a_progress.py \
	  script/test_p2p_nat_phase_a_progress.py \
	  script/check_production_relay_security_design.py \
	  script/check_runtime_python_sandbox_review.py \
	  script/test_runtime_python_sandbox_review.py \
	  script/check_copy_hygiene.py \
  script/check_docs_hygiene.py \
  script/check_license.py \
  script/check_app_icons.py \
  script/relay_allocation_preflight.py \
  script/aetherlink_relay.py

run bash -n script/*.sh
run check_android_relay_reachability_probe_input_guard
run check_android_relay_reachability_probe_route_material_redaction_guard
run check_android_pairing_deeplink_am_start_log_redaction_guard
run check_android_pairing_failure_artifact_redaction_guard
run check_android_pairing_chat_model_query_selector_guard
run check_android_pairing_summary_json_guard
run check_legacy_relay_guard
run check_link_local_relay_guard
run check_different_network_relay_endpoint_input_redaction_guard
run check_no_adb_external_relay_url_host_redaction_guard
run check_different_network_preflight_summary_guard
run check_relay_preflight_allocation_guard
run check_relay_preflight_rejects_route_material_guard
run check_relay_preflight_failure_output_redaction_guard
run check_relay_preflight_unexpected_field_rejection_guard
run check_relay_preflight_response_value_canonicality_guard
run check_relay_preflight_host_input_guard
run check_relay_exposed_bind_token_guard
run check_relay_wrapper_dry_run_allocation_token_redaction_guard
run check_relay_source_rate_limit_configuration_guard
run check_relay_source_peer_quota_configuration_guard
run check_relay_waiting_peer_policy_configuration_guard
run check_relay_wrapper_allocation_token_argv_redaction_guard
run check_different_network_wrapper_allocation_token_argv_redaction_guard
run check_no_adb_wrapper_allocation_token_argv_redaction_guard
run check_android_pairing_deeplink_allocation_token_argv_redaction_guard
run check_relay_allocation_token_authorization_guard
run check_physical_external_relay_summary_guard
run check_physical_external_relay_url_host_redaction_guard
run check_physical_external_relay_probe_summary_redaction_guard
run check_physical_external_relay_different_network_confirmation_guard
run git diff --check

run python3 script/check_android_string_parity.py
run python3 script/check_macos_localization.py
run python3 script/check_protocol_schema.py
run python3 script/check_p2p_nat_contract_vectors.py
run python3 script/check_p2p_nat_pre_network_review.py
run python3 -m unittest script/test_p2p_nat_pre_network_review.py
run python3 script/check_p2p_nat_controlled_spike_review.py
run python3 -m unittest script/test_p2p_nat_controlled_spike_review.py
run python3 script/check_p2p_nat_security_design.py
run python3 script/check_p2p_nat_phase_a_progress.py
run python3 -m unittest script/test_p2p_nat_phase_a_progress.py
run python3 script/check_p2p_nat_libjuice_offline_source.py
run python3 -m unittest script/test_p2p_nat_libjuice_offline_source.py
run python3 script/check_p2p_nat_libjuice_compile_only.py
run python3 -m unittest script/test_p2p_nat_libjuice_compile_only.py
run python3 script/check_p2p_nat_session_crypto_vectors.py
run python3 -m unittest script/test_p2p_nat_session_crypto_vectors.py
run python3 script/check_p2p_nat_phase_a_harness_egress.py
run python3 -m unittest script/test_p2p_nat_phase_a_harness_egress.py
run python3 script/check_production_relay_security_design.py
run ./gradlew --no-daemon \
	  :core:protocol:testDebugUnitTest \
	  :core:transport:testDebugUnitTest \
	  --tests 'com.localagentbridge.android.core.protocol.p2pnat.*' \
	  --tests 'com.localagentbridge.android.core.transport.p2pnat.*' \
	  -Pkotlin.incremental=false
run swift test --filter 'P2PNATContractsTests|P2PNATSharedVectorTests|P2PNATConformanceTests'
run ./gradlew --no-daemon \
	  :core:pairing:testDebugUnitTest \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsWhitespaceMutatedRelaySecretAliasesInQrPayload \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.parsesAllowedDiscoveryServiceTypeHints \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsBackendProviderOrUrlShapedServiceTypeHints \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsDuplicateQueryKeysBeforeFieldSelection \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsUnknownQueryKeysBeforeFieldSelection \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsMixedSemanticAliasesBeforeFieldSelection \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsNonCanonicalRelayHostsBeforeRouteMaterialAcceptance \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsMixedRelayAliasFamiliesFromQrPayload \
		  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.parsesRouteAliasPrivateOverlayScopeFromQrPayload \
		  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsMixedP2pAliasFamiliesFromQrPayload \
		  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsNonCanonicalP2pProtocolVersionAliasesInQrPayload \
		  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsNonCanonicalRouteExpirationAliasesInQrPayload \
		  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsNonCanonicalRelayPortAliasesInQrPayload \
		  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsRelayScopeWithoutRelayRouteMaterial \
	  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.preservesLiteralPlusInOpaqueQrValues \
	  -Pkotlin.incremental=false
run python3 script/check_copy_hygiene.py
run python3 script/check_docs_hygiene.py
run python3 script/check_license.py
run python3 script/check_app_icons.py
run check_macos_dock_capture_dry_run_summary_guard

QR_SMOKE_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-device-qr.XXXXXX")"
TEMP_DIRS+=("$QR_SMOKE_WORK_DIR")
QR_SMOKE_RELAY_PORT="$(free_tcp_port)"
run ./script/no_adb_external_relay_pairing_smoke.sh \
  --relay-host 127.0.0.1 \
  --relay-port "$QR_SMOKE_RELAY_PORT" \
  --start-local-relay \
  --emit-only \
  --timeout 30 \
  --work-dir "$QR_SMOKE_WORK_DIR"
run ./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_WORK_DIR/pairing-qr.png" \
  --expected "$QR_SMOKE_WORK_DIR/pairing-uri.txt" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  >/dev/null
QR_SMOKE_DUPLICATE_QUERY_KEY_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-duplicate-query-key.txt"
QR_SMOKE_DUPLICATE_QUERY_KEY_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-duplicate-query-key.png"
run python3 - "$QR_SMOKE_WORK_DIR/pairing-uri.txt" "$QR_SMOKE_DUPLICATE_QUERY_KEY_URI_FILE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
if "route_token=" in text:
    mutated = text + "&route%5Ftoken=route-duplicate-artifact"
elif "rt=" in text:
    mutated = text + "&rt=route-duplicate-artifact"
else:
    raise SystemExit("loopback QR fixture did not contain route token material")
target.write_text(mutated, encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_DUPLICATE_QUERY_KEY_URI_FILE" \
  --output "$QR_SMOKE_DUPLICATE_QUERY_KEY_QR_FILE"
set +e
QR_SMOKE_DUPLICATE_QUERY_KEY_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_DUPLICATE_QUERY_KEY_QR_FILE" \
  --expected "$QR_SMOKE_DUPLICATE_QUERY_KEY_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  2>&1 >/dev/null)"
QR_SMOKE_DUPLICATE_QUERY_KEY_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_DUPLICATE_QUERY_KEY_VERIFY_STATUS" -eq 0 ]]; then
  echo "Pairing QR verifier should reject duplicate decoded query-key artifacts." >&2
  exit 1
fi
if [[ "$QR_SMOKE_DUPLICATE_QUERY_KEY_VERIFY_OUTPUT" != *"duplicate query key"* ]]; then
  echo "Pairing QR verifier did not report duplicate query key for a duplicate decoded query-key artifact." >&2
  echo "$QR_SMOKE_DUPLICATE_QUERY_KEY_VERIFY_OUTPUT" >&2
  exit 1
fi
QR_SMOKE_UNKNOWN_QUERY_KEY_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-unknown-query-key.txt"
QR_SMOKE_UNKNOWN_QUERY_KEY_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-unknown-query-key.png"
run python3 - "$QR_SMOKE_WORK_DIR/pairing-uri.txt" "$QR_SMOKE_UNKNOWN_QUERY_KEY_URI_FILE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
target.write_text(
    text + "&backend_url=http%3A%2F%2F127.0.0.1%3A11434%2Fapi%2Ftags",
    encoding="utf-8",
)
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_UNKNOWN_QUERY_KEY_URI_FILE" \
  --output "$QR_SMOKE_UNKNOWN_QUERY_KEY_QR_FILE"
set +e
QR_SMOKE_UNKNOWN_QUERY_KEY_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_UNKNOWN_QUERY_KEY_QR_FILE" \
  --expected "$QR_SMOKE_UNKNOWN_QUERY_KEY_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  2>&1 >/dev/null)"
QR_SMOKE_UNKNOWN_QUERY_KEY_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_UNKNOWN_QUERY_KEY_VERIFY_STATUS" -eq 0 ]]; then
  echo "Pairing QR verifier should reject unknown decoded query-key artifacts." >&2
  exit 1
fi
if [[ "$QR_SMOKE_UNKNOWN_QUERY_KEY_VERIFY_OUTPUT" != *"unknown query key"* ]]; then
  echo "Pairing QR verifier did not report unknown query key for an unknown decoded query-key artifact." >&2
  echo "$QR_SMOKE_UNKNOWN_QUERY_KEY_VERIFY_OUTPUT" >&2
  exit 1
fi
QR_SMOKE_MIXED_SEMANTIC_ALIAS_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-mixed-semantic-alias.txt"
QR_SMOKE_MIXED_SEMANTIC_ALIAS_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-mixed-semantic-alias.png"
run python3 - "$QR_SMOKE_WORK_DIR/pairing-uri.txt" "$QR_SMOKE_MIXED_SEMANTIC_ALIAS_URI_FILE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
if "route_token=" in text:
    mutated = text + "&rt=semantic-alias-artifact"
elif "rt=" in text:
    mutated = text + "&route_token=semantic-alias-artifact"
else:
    raise SystemExit("loopback QR fixture did not contain route token material")
target.write_text(mutated, encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_MIXED_SEMANTIC_ALIAS_URI_FILE" \
  --output "$QR_SMOKE_MIXED_SEMANTIC_ALIAS_QR_FILE"
set +e
QR_SMOKE_MIXED_SEMANTIC_ALIAS_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_MIXED_SEMANTIC_ALIAS_QR_FILE" \
  --expected "$QR_SMOKE_MIXED_SEMANTIC_ALIAS_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  2>&1 >/dev/null)"
QR_SMOKE_MIXED_SEMANTIC_ALIAS_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_MIXED_SEMANTIC_ALIAS_VERIFY_STATUS" -eq 0 ]]; then
  echo "Pairing QR verifier should reject mixed semantic alias artifacts." >&2
  exit 1
fi
if [[ "$QR_SMOKE_MIXED_SEMANTIC_ALIAS_VERIFY_OUTPUT" != *"Mixed pairing QR semantic alias fields"* ]]; then
  echo "Pairing QR verifier did not report mixed semantic alias fields for a mixed alias artifact." >&2
  echo "$QR_SMOKE_MIXED_SEMANTIC_ALIAS_VERIFY_OUTPUT" >&2
  exit 1
fi
QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-mixed-relay-alias-family.txt"
QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-mixed-relay-alias-family.png"
run python3 - "$QR_SMOKE_WORK_DIR/pairing-uri.txt" "$QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_URI_FILE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
if "relay_port=" in text:
    mutated = text + "&rp=443"
elif "rp=" in text:
    mutated = text + "&relay_port=443"
else:
    raise SystemExit("loopback QR fixture did not contain relay port material")
target.write_text(mutated, encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_URI_FILE" \
  --output "$QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_QR_FILE"
set +e
QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_QR_FILE" \
  --expected "$QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  2>&1 >/dev/null)"
QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_VERIFY_STATUS" -eq 0 ]]; then
  echo "Pairing QR verifier should reject mixed relay alias family artifacts." >&2
  exit 1
fi
if [[ "$QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_VERIFY_OUTPUT" != *"Mixed relay alias families"* ]]; then
  echo "Pairing QR verifier did not report mixed relay alias families for a mixed relay alias family artifact." >&2
  echo "$QR_SMOKE_MIXED_RELAY_ALIAS_FAMILY_VERIFY_OUTPUT" >&2
  exit 1
fi
QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-mixed-p2p-alias-family.txt"
QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-mixed-p2p-alias-family.png"
run python3 - "shared/protocol/fixtures/macos-compact-p2p-rendezvous-pairing-uri.txt" "$QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_URI_FILE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8").strip()
if "pc=p2p_rendezvous" not in text:
    raise SystemExit("compact P2P QR fixture did not contain compact P2P material")
target.write_text(text + "&p2p_class=p2p_rendezvous", encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_URI_FILE" \
  --output "$QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_QR_FILE"
set +e
QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_QR_FILE" \
  --expected "$QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_URI_FILE" \
  --require-production-bootstrap \
  --forbid-direct-endpoint \
  2>&1 >/dev/null)"
QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_VERIFY_STATUS" -eq 0 ]]; then
  echo "Pairing QR verifier should reject mixed P2P alias family artifacts." >&2
  exit 1
fi
if [[ "$QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_VERIFY_OUTPUT" != *"Mixed P2P alias families"* ]]; then
  echo "Pairing QR verifier did not report mixed P2P alias families for a mixed P2P alias family artifact." >&2
  echo "$QR_SMOKE_MIXED_P2P_ALIAS_FAMILY_VERIFY_OUTPUT" >&2
  exit 1
fi
QR_SMOKE_RENDEZVOUS_RELAY_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-rendezvous-relay.txt"
QR_SMOKE_RENDEZVOUS_RELAY_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-rendezvous-relay.png"
run python3 - "$QR_SMOKE_RENDEZVOUS_RELAY_URI_FILE" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1])
target.write_text(
    "aetherlink://pair?v=1&n=nonce-rendezvous-1&c=123456"
    "&rid=runtime-1&rn=AetherLink%20Runtime&rf=runtime-fingerprint"
    "&rk=runtime%2Bpublic/key%3D&rt=route-token-rendezvous-1"
    "&rendezvous_host=relay.example.test&rendezvous_port=443"
    "&rendezvous_id=relay-rendezvous-1&rendezvous_secret=secret-rendezvous-1"
    "&rendezvous_expires_at=4102444800000&rendezvous_nonce=nonce-rendezvous-route-1",
    encoding="utf-8",
)
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_RENDEZVOUS_RELAY_URI_FILE" \
  --output "$QR_SMOKE_RENDEZVOUS_RELAY_QR_FILE"
run ./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_RENDEZVOUS_RELAY_QR_FILE" \
  --expected "$QR_SMOKE_RENDEZVOUS_RELAY_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host relay.example.test \
  --expected-relay-port 443 \
  --forbid-direct-endpoint \
  >/dev/null
QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-mutated-rendezvous-secret.txt"
QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-mutated-rendezvous-secret.png"
run python3 - "$QR_SMOKE_RENDEZVOUS_RELAY_URI_FILE" "$QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_URI_FILE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
mutated = text.replace(
    "rendezvous_secret=secret-rendezvous-1",
    "rendezvous_secret=secret%20rendezvous-1",
)
if mutated == text:
    raise SystemExit("rendezvous relay QR fixture did not contain rendezvous_secret material")
target.write_text(mutated, encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_URI_FILE" \
  --output "$QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_QR_FILE"
set +e
QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_QR_FILE" \
  --expected "$QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host relay.example.test \
  --expected-relay-port 443 \
  --forbid-direct-endpoint \
  2>&1 >/dev/null)"
QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_VERIFY_STATUS" -eq 0 ]]; then
  echo "Pairing QR verifier should reject whitespace-mutated rendezvous relay secrets." >&2
  exit 1
fi
if [[ "$QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_VERIFY_OUTPUT" != *"invalid relay_secret"* ]]; then
  echo "Pairing QR verifier did not report invalid relay_secret for a whitespace-mutated rendezvous secret artifact." >&2
  echo "$QR_SMOKE_MUTATED_RENDEZVOUS_SECRET_VERIFY_OUTPUT" >&2
  exit 1
fi
QR_SMOKE_MUTATED_SCOPE_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-remote-scope.txt"
QR_SMOKE_MUTATED_SCOPE_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-remote-scope.png"
run python3 - "$QR_SMOKE_WORK_DIR/pairing-uri.txt" "$QR_SMOKE_MUTATED_SCOPE_URI_FILE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
mutated = text.replace("relay_scope=usb_reverse", "relay_scope=remote").replace(
    "rsc=usb_reverse",
    "rsc=remote",
)
if mutated == text:
    raise SystemExit("loopback QR fixture did not contain usb_reverse scope")
target.write_text(mutated, encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_MUTATED_SCOPE_URI_FILE" \
  --output "$QR_SMOKE_MUTATED_SCOPE_QR_FILE"
set +e
QR_SMOKE_MUTATED_SCOPE_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_MUTATED_SCOPE_QR_FILE" \
  --expected "$QR_SMOKE_MUTATED_SCOPE_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  2>&1 >/dev/null)"
QR_SMOKE_MUTATED_SCOPE_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_MUTATED_SCOPE_VERIFY_STATUS" -eq 0 ]]; then
  echo "Loopback local-relay QR verifier should reject remote-scoped loopback artifacts." >&2
  exit 1
fi
if [[ "$QR_SMOKE_MUTATED_SCOPE_VERIFY_OUTPUT" != *"relay_host is not a remote-reachable relay host"* ]]; then
  echo "Loopback local-relay QR verifier did not report invalid relay_host for a remote-scoped loopback artifact." >&2
  echo "$QR_SMOKE_MUTATED_SCOPE_VERIFY_OUTPUT" >&2
  exit 1
fi
QR_SMOKE_MUTATED_PORT_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-zero-padded-port.txt"
QR_SMOKE_MUTATED_PORT_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-zero-padded-port.png"
run python3 - "$QR_SMOKE_WORK_DIR/pairing-uri.txt" "$QR_SMOKE_MUTATED_PORT_URI_FILE" <<'PY'
from pathlib import Path
import re
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
mutated = None
for field in ("relay_port", "rp"):
    candidate, count = re.subn(rf"({field}=)([1-9][0-9]*)", r"\g<1>0\2", text, count=1)
    if count == 1:
        mutated = candidate
        break
if mutated is None:
    raise SystemExit("loopback QR fixture did not contain a relay port field")
target.write_text(mutated, encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_MUTATED_PORT_URI_FILE" \
  --output "$QR_SMOKE_MUTATED_PORT_QR_FILE"
set +e
QR_SMOKE_MUTATED_PORT_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_MUTATED_PORT_QR_FILE" \
  --expected "$QR_SMOKE_MUTATED_PORT_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --forbid-direct-endpoint \
  --allow-local-relay \
  2>&1 >/dev/null)"
QR_SMOKE_MUTATED_PORT_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_MUTATED_PORT_VERIFY_STATUS" -eq 0 ]]; then
  echo "Pairing QR verifier should reject zero-padded relay port artifacts." >&2
  exit 1
fi
if [[ "$QR_SMOKE_MUTATED_PORT_VERIFY_OUTPUT" != *"invalid relay_port"* ]]; then
  echo "Pairing QR verifier did not report invalid relay_port for a zero-padded port artifact." >&2
  echo "$QR_SMOKE_MUTATED_PORT_VERIFY_OUTPUT" >&2
  exit 1
fi
QR_SMOKE_MUTATED_EXPIRATION_URI_FILE="$QR_SMOKE_WORK_DIR/pairing-uri-zero-padded-expiration.txt"
QR_SMOKE_MUTATED_EXPIRATION_QR_FILE="$QR_SMOKE_WORK_DIR/pairing-qr-zero-padded-expiration.png"
run python3 - "$QR_SMOKE_WORK_DIR/pairing-uri.txt" "$QR_SMOKE_MUTATED_EXPIRATION_URI_FILE" <<'PY'
from pathlib import Path
import re
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
mutated = None
for field in ("relay_expires_at", "rx"):
    candidate, count = re.subn(rf"({field}=)([1-9][0-9]*)", r"\g<1>0\2", text, count=1)
    if count == 1:
        mutated = candidate
        break
if mutated is None:
    raise SystemExit("loopback QR fixture did not contain a relay expiration field")
target.write_text(mutated, encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$QR_SMOKE_MUTATED_EXPIRATION_URI_FILE" \
  --output "$QR_SMOKE_MUTATED_EXPIRATION_QR_FILE"
set +e
QR_SMOKE_MUTATED_EXPIRATION_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_MUTATED_EXPIRATION_QR_FILE" \
  --expected "$QR_SMOKE_MUTATED_EXPIRATION_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  2>&1 >/dev/null)"
QR_SMOKE_MUTATED_EXPIRATION_VERIFY_STATUS=$?
set -e
if [[ "$QR_SMOKE_MUTATED_EXPIRATION_VERIFY_STATUS" -eq 0 ]]; then
  echo "Pairing QR verifier should reject zero-padded relay expiration artifacts." >&2
  exit 1
fi
if [[ "$QR_SMOKE_MUTATED_EXPIRATION_VERIFY_OUTPUT" != *"invalid relay_expires_at"* ]]; then
  echo "Pairing QR verifier did not report invalid relay_expires_at for a zero-padded expiration artifact." >&2
  echo "$QR_SMOKE_MUTATED_EXPIRATION_VERIFY_OUTPUT" >&2
  exit 1
fi
PRIVATE_OVERLAY_QR_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-device-qr.private-overlay.XXXXXX")"
TEMP_DIRS+=("$PRIVATE_OVERLAY_QR_WORK_DIR")
PRIVATE_OVERLAY_QR_FILE="$PRIVATE_OVERLAY_QR_WORK_DIR/private-overlay-pairing-qr.png"
PRIVATE_OVERLAY_MUTATED_SCOPE_URI_FILE="$PRIVATE_OVERLAY_QR_WORK_DIR/private-overlay-mutated-scope-uri.txt"
PRIVATE_OVERLAY_MUTATED_SCOPE_QR_FILE="$PRIVATE_OVERLAY_QR_WORK_DIR/private-overlay-mutated-scope-qr.png"
PRIVATE_OVERLAY_URI_FILE="shared/protocol/fixtures/macos-compact-private-overlay-pairing-uri.txt"
run ./script/render_pairing_qr.swift \
  --input "$PRIVATE_OVERLAY_URI_FILE" \
  --output "$PRIVATE_OVERLAY_QR_FILE"
run ./script/verify_pairing_qr.swift \
  --image "$PRIVATE_OVERLAY_QR_FILE" \
  --expected "$PRIVATE_OVERLAY_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 100.64.1.10 \
  --expected-relay-port 43171 \
  --forbid-direct-endpoint \
  >/dev/null
run python3 - "$PRIVATE_OVERLAY_URI_FILE" "$PRIVATE_OVERLAY_MUTATED_SCOPE_URI_FILE" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
mutated = text.replace("rsc=private_overlay", "rsc=PRIVATE_OVERLAY%20")
if mutated == text:
    raise SystemExit("private-overlay fixture did not contain compact private_overlay scope")
target.write_text(mutated, encoding="utf-8")
PY
run ./script/render_pairing_qr.swift \
  --input "$PRIVATE_OVERLAY_MUTATED_SCOPE_URI_FILE" \
  --output "$PRIVATE_OVERLAY_MUTATED_SCOPE_QR_FILE"
set +e
PRIVATE_OVERLAY_MUTATED_SCOPE_VERIFY_OUTPUT="$(./script/verify_pairing_qr.swift \
  --image "$PRIVATE_OVERLAY_MUTATED_SCOPE_QR_FILE" \
  --expected "$PRIVATE_OVERLAY_MUTATED_SCOPE_URI_FILE" \
  --require-relay-route \
  --require-production-bootstrap \
  --expected-relay-host 100.64.1.10 \
  --expected-relay-port 43171 \
  --forbid-direct-endpoint \
  2>&1 >/dev/null)"
PRIVATE_OVERLAY_MUTATED_SCOPE_VERIFY_STATUS=$?
set -e
if [[ "$PRIVATE_OVERLAY_MUTATED_SCOPE_VERIFY_STATUS" -eq 0 ]]; then
  echo "Private-overlay QR verifier should reject case/whitespace-mutated relay_scope artifacts." >&2
  exit 1
fi
if [[ "$PRIVATE_OVERLAY_MUTATED_SCOPE_VERIFY_OUTPUT" != *"invalid relay_scope"* ]]; then
  echo "Private-overlay QR verifier did not report invalid relay_scope for a mutated scope artifact." >&2
  echo "$PRIVATE_OVERLAY_MUTATED_SCOPE_VERIFY_OUTPUT" >&2
  exit 1
fi
run python3 - "$QR_SMOKE_WORK_DIR/summary.json" <<'PY'
import json
import sys
import urllib.parse
from pathlib import Path

summary = json.load(open(sys.argv[1], encoding="utf-8"))
coverage = summary["coverage"]
assert summary["mode"]["emit_only"] is True, summary
assert summary["mode"]["expect_reconnect"] is False, summary
assert coverage["runtime_host_relay_registration"] is True, summary
assert coverage["runtime_host_waiting_for_peer"] is True, summary
assert coverage["trusted_device_relay_reachability"] is False, summary
assert coverage["trusted_device_pairing"] is False, summary
assert coverage["trusted_device_runtime_health"] is False, summary
assert coverage["trusted_device_reconnect"] is False, summary
assert coverage["optical_qr_scan"] is False, summary
assert coverage["external_network_operator_confirmed"] is False, summary
assert coverage["full_run_trusted_device_proof"] is False, summary
assert coverage["external_network_relay_verified"] is False, summary
assert coverage["production_relay"] is False, summary
assert coverage["production_session_key_exchange"] is False, summary
assert coverage["production_end_to_end_transport_encryption"] is False, summary
assert coverage["runtime_log_artifact_present"] is True, summary
assert coverage["runtime_log_contains_temporary_pairing_material"] is True, summary
assert coverage["runtime_log_contains_temporary_route_material"] is True, summary
assert coverage["relay_log_artifact_present"] is True, summary
assert coverage["relay_log_relay_ids_shortened"] is True, summary
assert coverage["relay_log_omits_temporary_secret_material"] is True, summary
assert coverage["relay_log_contains_temporary_secret_material"] is False, summary
assert coverage["relay_log_contains_unredacted_route_material"] is False, summary
assert coverage["pairing_uri_artifact_present"] is True, summary
assert coverage["pairing_qr_artifact_present"] is True, summary
assert coverage["pairing_uri_contains_temporary_pairing_material"] is True, summary
assert coverage["pairing_qr_contains_temporary_pairing_material"] is True, summary
assert coverage["pairing_uri_contains_temporary_route_material"] is True, summary
assert coverage["pairing_qr_contains_temporary_route_material"] is True, summary
assert coverage["terminal_output_contains_temporary_pairing_material"] is False, summary
assert coverage["terminal_output_contains_temporary_route_material"] is False, summary
assert coverage["pairing_qr_round_trip_verified"] is True, summary
assert coverage["emit_only_qr_artifact_summary_verified"] is True, summary
assert coverage["unverified_qr_artifact_self_test"] is False, summary
assert coverage["relay_route_required"] is True, summary
assert coverage["direct_endpoint_forbidden"] is True, summary
assert coverage["artifact_only_emit_mode"] is True, summary
assert "runtime_log_contains_temporary_pairing_or_route_material" in summary["caveats"], summary
assert "relay_log_contains_temporary_secret_material" not in summary["caveats"], summary
assert "relay_log_redaction_not_verified" not in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "manual_scan_qr_artifacts_contain_temporary_pairing_material" in summary["caveats"], summary
assert "manual_scan_qr_artifacts_contain_temporary_route_material" in summary["caveats"], summary
assert "terminal_output_contains_temporary_pairing_or_route_material" not in summary["caveats"], summary
assert "artifact_only_emit_mode" in summary["caveats"], summary
assert "external_network_operator_confirmation_missing" not in summary["caveats"], summary
assert "local_relay_only_unless_advertised_host_is_public_vpn_tunnel_or_overlay" in summary["caveats"], summary
relay_log_path = Path(summary["artifacts"]["relay_log"])
pairing_uri_path = Path(summary["artifacts"]["pairing_uri"])
assert relay_log_path.exists(), summary
relay_log = relay_log_path.read_text(encoding="utf-8", errors="replace")
pairing_uri = pairing_uri_path.read_text(encoding="utf-8").strip()
query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(pairing_uri).query, keep_blank_values=True))
def query_value(*names):
    for name in names:
        value = query.get(name)
        if value:
            return value
    raise AssertionError(query)
relay_id = query_value("relay_id", "remote_id", "route_id", "network_id", "ri")
assert relay_id not in relay_log, relay_log
if len(relay_id) > 12:
    shortened = f"{relay_id[:6]}...{relay_id[-6:]}"
    assert shortened in relay_log, relay_log
for marker in ("relay_secret", "relay_nonce", "route_token", "allocation_token", "requested_route_token", "rs=", "rrn=", "rt="):
    assert marker not in relay_log, relay_log
PY
EXPECT_RECONNECT_QR_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-device-qr.expect-reconnect.XXXXXX")"
TEMP_DIRS+=("$EXPECT_RECONNECT_QR_WORK_DIR")
EXPECT_RECONNECT_QR_RELAY_PORT="$(free_tcp_port)"
echo
echo "==> no-ADB expect-reconnect emit-only summary guard"
run ./script/no_adb_external_relay_pairing_smoke.sh \
  --relay-host 127.0.0.1 \
  --relay-port "$EXPECT_RECONNECT_QR_RELAY_PORT" \
  --start-local-relay \
  --emit-only \
  --expect-reconnect \
  --timeout 30 \
  --work-dir "$EXPECT_RECONNECT_QR_WORK_DIR"
run python3 - "$EXPECT_RECONNECT_QR_WORK_DIR/summary.json" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
coverage = summary["coverage"]
assert summary["mode"]["emit_only"] is True, summary
assert summary["mode"]["expect_reconnect"] is True, summary
assert summary["mode"]["require_manual_network_confirmation"] is False, summary
assert coverage["runtime_host_relay_registration"] is True, summary
assert coverage["runtime_host_waiting_for_peer"] is True, summary
assert coverage["trusted_device_relay_reachability"] is False, summary
assert coverage["trusted_device_pairing"] is False, summary
assert coverage["trusted_device_runtime_health"] is False, summary
assert coverage["trusted_device_reconnect"] is False, summary
assert coverage["optical_qr_scan"] is False, summary
assert coverage["external_network_operator_confirmed"] is False, summary
assert coverage["full_run_trusted_device_proof"] is False, summary
assert coverage["external_network_relay_verified"] is False, summary
assert coverage["production_relay"] is False, summary
assert coverage["production_session_key_exchange"] is False, summary
assert coverage["production_end_to_end_transport_encryption"] is False, summary
assert coverage["pairing_qr_round_trip_verified"] is True, summary
assert coverage["emit_only_qr_artifact_summary_verified"] is True, summary
assert coverage["unverified_qr_artifact_self_test"] is False, summary
assert coverage["artifact_only_emit_mode"] is True, summary
assert "artifact_only_emit_mode" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "external_network_operator_confirmation_missing" not in summary["caveats"], summary
assert "runtime_reached_relay_but_trusted_device_did_not_join" in summary["caveats"], summary
PY
PRINT_URI_QR_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-device-qr.print-uri.XXXXXX")"
TEMP_DIRS+=("$PRINT_URI_QR_WORK_DIR")
PRINT_URI_QR_RELAY_PORT="$(free_tcp_port)"
PRINT_URI_STDOUT="$PRINT_URI_QR_WORK_DIR/stdout.txt"
echo
echo "==> no-ADB print-uri terminal-output summary guard"
./script/no_adb_external_relay_pairing_smoke.sh \
  --relay-host 127.0.0.1 \
  --relay-port "$PRINT_URI_QR_RELAY_PORT" \
  --start-local-relay \
  --emit-only \
  --print-uri \
  --timeout 30 \
  --work-dir "$PRINT_URI_QR_WORK_DIR" \
  >"$PRINT_URI_STDOUT"
run python3 - "$PRINT_URI_QR_WORK_DIR/summary.json" "$PRINT_URI_STDOUT" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
stdout = open(sys.argv[2], encoding="utf-8", errors="replace").read()
coverage = summary["coverage"]
assert "aetherlink://pair" in stdout, stdout
assert summary["mode"]["print_uri"] is True, summary
assert coverage["production_session_key_exchange"] is False, summary
assert coverage["production_end_to_end_transport_encryption"] is False, summary
assert coverage["terminal_output_contains_temporary_pairing_material"] is True, summary
assert coverage["terminal_output_contains_temporary_route_material"] is True, summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "terminal_output_contains_temporary_pairing_or_route_material" in summary["caveats"], summary
PY
UNVERIFIED_QR_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-device-qr.unverified.XXXXXX")"
TEMP_DIRS+=("$UNVERIFIED_QR_WORK_DIR")
UNVERIFIED_QR_RELAY_PORT="$(free_tcp_port)"
run ./script/no_adb_external_relay_pairing_smoke.sh \
  --self-test-unverified-qr-summary \
  --relay-host 127.0.0.1 \
  --relay-port "$UNVERIFIED_QR_RELAY_PORT" \
  --work-dir "$UNVERIFIED_QR_WORK_DIR"
run python3 - "$UNVERIFIED_QR_WORK_DIR/summary.json" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
coverage = summary["coverage"]
assert coverage["runtime_host_relay_registration"] is False, summary
assert coverage["runtime_host_waiting_for_peer"] is False, summary
assert coverage["trusted_device_relay_reachability"] is False, summary
assert coverage["trusted_device_pairing"] is False, summary
assert coverage["trusted_device_runtime_health"] is False, summary
assert coverage["trusted_device_reconnect"] is False, summary
assert coverage["optical_qr_scan"] is False, summary
assert coverage["external_network_operator_confirmed"] is False, summary
assert coverage["full_run_trusted_device_proof"] is False, summary
assert coverage["external_network_relay_verified"] is False, summary
assert coverage["production_relay"] is False, summary
assert coverage["production_session_key_exchange"] is False, summary
assert coverage["production_end_to_end_transport_encryption"] is False, summary
assert coverage["runtime_log_artifact_present"] is True, summary
assert coverage["runtime_log_contains_temporary_pairing_material"] is False, summary
assert coverage["runtime_log_contains_temporary_route_material"] is False, summary
assert coverage["relay_log_artifact_present"] is True, summary
assert coverage["relay_log_relay_ids_shortened"] is False, summary
assert coverage["relay_log_omits_temporary_secret_material"] is True, summary
assert coverage["relay_log_contains_temporary_secret_material"] is False, summary
assert coverage["relay_log_contains_unredacted_route_material"] is False, summary
assert coverage["pairing_uri_artifact_present"] is True, summary
assert coverage["pairing_qr_artifact_present"] is True, summary
assert coverage["pairing_qr_round_trip_verified"] is False, summary
assert coverage["emit_only_qr_artifact_summary_verified"] is False, summary
assert coverage["unverified_qr_artifact_self_test"] is True, summary
assert coverage["pairing_uri_contains_temporary_pairing_material"] is False, summary
assert coverage["pairing_qr_contains_temporary_pairing_material"] is False, summary
assert coverage["pairing_uri_contains_temporary_route_material"] is False, summary
assert coverage["pairing_qr_contains_temporary_route_material"] is False, summary
assert "runtime_log_contains_temporary_pairing_or_route_material" not in summary["caveats"], summary
assert "external_network_operator_confirmation_missing" not in summary["caveats"], summary
assert "relay_log_contains_temporary_secret_material" not in summary["caveats"], summary
assert "relay_log_redaction_not_verified" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "manual_scan_qr_artifacts_contain_temporary_pairing_material" not in summary["caveats"], summary
assert "manual_scan_qr_artifacts_not_verified_as_route_material" in summary["caveats"], summary
assert "manual_scan_qr_artifacts_contain_temporary_route_material" not in summary["caveats"], summary
PY
CONFIRM_QR_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-device-qr.confirmation.XXXXXX")"
TEMP_DIRS+=("$CONFIRM_QR_WORK_DIR")
CONFIRM_QR_RELAY_PORT="$(free_tcp_port)"
CONFIRM_QR_OUTPUT="$CONFIRM_QR_WORK_DIR/output.txt"
echo
echo "==> no-ADB manual network confirmation negative summary guard"
set +e
printf '%s\n' "SAME_NETWORK" | ./script/no_adb_external_relay_pairing_smoke.sh \
  --relay-host 127.0.0.1 \
  --relay-port "$CONFIRM_QR_RELAY_PORT" \
  --start-local-relay \
  --require-manual-network-confirmation \
  --timeout 5 \
  --work-dir "$CONFIRM_QR_WORK_DIR" \
  >"$CONFIRM_QR_OUTPUT" 2>&1
confirm_status=$?
set -e
if [[ "$confirm_status" -ne 2 ]]; then
  echo "no-ADB manual network confirmation guard should exit 2 for invalid confirmation, got $confirm_status" >&2
  cat "$CONFIRM_QR_OUTPUT" >&2
  exit 1
fi
if ! grep -Fq "Network confirmation failed" "$CONFIRM_QR_OUTPUT"; then
  echo "no-ADB manual network confirmation guard did not explain the failed confirmation." >&2
  cat "$CONFIRM_QR_OUTPUT" >&2
  exit 1
fi
run python3 - "$CONFIRM_QR_WORK_DIR/summary.json" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
coverage = summary["coverage"]
assert summary["exit_status"] == 2, summary
assert summary["mode"]["emit_only"] is False, summary
assert summary["mode"]["require_manual_network_confirmation"] is True, summary
assert coverage["runtime_host_relay_registration"] is True, summary
assert coverage["runtime_host_waiting_for_peer"] is True, summary
assert coverage["trusted_device_relay_reachability"] is False, summary
assert coverage["trusted_device_pairing"] is False, summary
assert coverage["trusted_device_runtime_health"] is False, summary
assert coverage["external_network_operator_confirmed"] is False, summary
assert coverage["full_run_trusted_device_proof"] is False, summary
assert coverage["external_network_relay_verified"] is False, summary
assert coverage["production_relay"] is False, summary
assert coverage["production_session_key_exchange"] is False, summary
assert coverage["production_end_to_end_transport_encryption"] is False, summary
assert coverage["pairing_qr_round_trip_verified"] is True, summary
assert coverage["emit_only_qr_artifact_summary_verified"] is False, summary
assert coverage["unverified_qr_artifact_self_test"] is False, summary
assert "external_network_operator_confirmation_missing" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
PY
CONFIRMED_TIMEOUT_QR_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-device-qr.confirmed-timeout.XXXXXX")"
TEMP_DIRS+=("$CONFIRMED_TIMEOUT_QR_WORK_DIR")
CONFIRMED_TIMEOUT_QR_RELAY_PORT="$(free_tcp_port)"
CONFIRMED_TIMEOUT_QR_OUTPUT="$CONFIRMED_TIMEOUT_QR_WORK_DIR/output.txt"
echo
echo "==> no-ADB operator-confirmed timeout summary guard"
set +e
printf '%s\n' "DIFFERENT_NETWORK" | ./script/no_adb_external_relay_pairing_smoke.sh \
  --relay-host 127.0.0.1 \
  --relay-port "$CONFIRMED_TIMEOUT_QR_RELAY_PORT" \
  --start-local-relay \
  --require-manual-network-confirmation \
  --timeout 1 \
  --work-dir "$CONFIRMED_TIMEOUT_QR_WORK_DIR" \
  >"$CONFIRMED_TIMEOUT_QR_OUTPUT" 2>&1
confirmed_timeout_status=$?
set -e
if [[ "$confirmed_timeout_status" -ne 1 ]]; then
  echo "no-ADB operator-confirmed timeout guard should exit 1 when no trusted device joins, got $confirmed_timeout_status" >&2
  cat "$CONFIRMED_TIMEOUT_QR_OUTPUT" >&2
  exit 1
fi
if ! grep -Fq "Timed out waiting for 'relay status=ready'" "$CONFIRMED_TIMEOUT_QR_OUTPUT"; then
  echo "no-ADB operator-confirmed timeout guard did not wait for a trusted device relay join." >&2
  cat "$CONFIRMED_TIMEOUT_QR_OUTPUT" >&2
  exit 1
fi
run python3 - "$CONFIRMED_TIMEOUT_QR_WORK_DIR/summary.json" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
coverage = summary["coverage"]
observed = summary["observed"]
assert summary["exit_status"] == 1, summary
assert summary["mode"]["emit_only"] is False, summary
assert summary["mode"]["require_manual_network_confirmation"] is True, summary
assert coverage["runtime_host_relay_registration"] is True, summary
assert coverage["runtime_host_waiting_for_peer"] is True, summary
assert coverage["trusted_device_relay_reachability"] is False, summary
assert coverage["trusted_device_pairing"] is False, summary
assert coverage["trusted_device_runtime_health"] is False, summary
assert coverage["trusted_device_reconnect"] is False, summary
assert coverage["external_network_operator_confirmed"] is True, summary
assert coverage["full_run_trusted_device_proof"] is False, summary
assert coverage["external_network_relay_verified"] is False, summary
assert coverage["production_relay"] is False, summary
assert coverage["production_session_key_exchange"] is False, summary
assert coverage["production_end_to_end_transport_encryption"] is False, summary
assert coverage["pairing_qr_round_trip_verified"] is True, summary
assert coverage["emit_only_qr_artifact_summary_verified"] is False, summary
assert coverage["unverified_qr_artifact_self_test"] is False, summary
assert observed["relay_ready"] is False, summary
assert observed["relay_client_registered"] is False, summary
assert observed["pairing_accepted"] is False, summary
assert observed["runtime_health_count"] == 0, summary
assert "external_network_operator_confirmation_missing" not in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "runtime_reached_relay_but_trusted_device_did_not_join" in summary["caveats"], summary
PY
run ./script/runtime_authenticated_mock_smoke.swift --default-mock-routing-only
run ./script/runtime_authenticated_mock_smoke.swift --relay --expect-p2p-route-refresh

run ./gradlew --no-daemon \
	  :core:pairing:testDebugUnitTest \
	  --tests com.localagentbridge.android.core.pairing.InitialPairingProofTest \
	  --tests com.localagentbridge.android.core.pairing.PairedRelayAllocationAuthorizationTest \
  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest \
  --tests com.localagentbridge.android.core.pairing.RuntimeIdentityProofVerifierTest \
  --tests com.localagentbridge.android.core.pairing.DeviceIdentityStoreTest \
  --tests com.localagentbridge.android.core.pairing.PairingStoreTest \
  --tests com.localagentbridge.android.core.pairing.PairingStoreTest.pairingStoreDropsNonCanonicalStoredTrustedIdentityOnRead \
  --tests com.localagentbridge.android.core.pairing.PairingStoreTest.pairingStoreDropsNonCanonicalStoredRuntimePublicKeyOnRead \
  --tests com.localagentbridge.android.core.pairing.PairingStoreTest.pairingStoreDropsNonCanonicalTrustedIdentityOnWrite \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
  :core:protocol:testDebugUnitTest \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.decodeRejectsMalformedRequiredEnvelopeFields \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.decodeRejectsUnsupportedVersionAndBlankRequestId \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.decodeRejectsUnknownTopLevelEnvelopeFields \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.routeRefreshPayloadRejectsInvalidScalarRouteMaterial \
	  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.routeRefreshPayloadRequiresCompleteRouteMaterialFamilies \
	  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.relayAllocationChallengePayloadRoundTripsExactWireShape \
	  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.relayAllocationChallengePayloadRejectsMalformedAndSecretBearingSamples \
	  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.relayAllocationAuthorizationPayloadRoundTripsExactWireShape \
	  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.relayAllocationAuthorizationPayloadRejectsMalformedAndSecretBearingSamples \
	  --tests com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationAuthorizationTest \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.errorPayloadAcceptsKnownProtocolCodes \
	  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.errorPayloadDecodesNonRetryableChatContextWindowExceeded \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.errorPayloadRejectsUnknownCodes \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadPreservesProviderAndEmbeddingMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelsResultPayloadEnforcesExactCatalogRowLimitWithoutTruncation \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadUsesUnicodeCodePointLimitsForIdentityStrings \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadUsesUnicodeCodePointLimitForQualifiedId \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadUsesSharedCatalogBlankCodePointSet \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadEnforcesCapabilityCountAndUnicodeItemLimits \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadEnforcesExactSizeByteMaximum \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadEnforcesExactContextWindowMaximum \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadRejectsInvalidScalarMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadRejectsInvalidModifiedAtMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadRejectsInvalidNumericMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadDefaultsMissingCapabilitiesToEmptyList \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.runtimeHealthBackendStatusAcceptsSchemaMinimalPayload \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.runtimeHealthPayloadRejectsInvalidStatus \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.runtimeHealthPayloadRejectsInvalidModelResidencyBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSendRequestRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatStreamResponsePayloadsRejectInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSessionsListRequestRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSessionsListResponseRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatAndMemoryPayloadsRejectInvalidTimestampMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatMessagesListRequestRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatMessagesListRejectsInlineStoredAttachmentBytes \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSourceAttributionResolvePayloadsRoundTripExactExistingSourceShapes \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSourceAttributionResolvePayloadsRejectUnknownMalformedAndMismatchedValues \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSourceAttributionsUseExactSafeWireShapeAndRemainOptional \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSourceAttributionsRejectInvalidBoundsOrderFinishReasonAndForbiddenMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatTitleAndSessionMutationRequestsRejectInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelPullAndChatCancelRequestsRejectInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.indexDocumentsListPayloadUsesProtocolFieldNames \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.indexDocumentsListRequestRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.indexDocumentsListResponseRejectsInvalidDocumentMetadataBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.indexDocumentsListResponseRejectsInvalidSummaryBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryPayloadUsesProtocolFieldNames \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryRequestRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalAndSourceAnchorDocumentMetadataRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryResponseRejectsTooManyResults \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.sourceAnchorResolvePayloadUsesProtocolFieldNames \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.indexDocumentsListRejectsNonCanonicalContentFingerprints \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryResultRejectsNonCanonicalDocumentContentFingerprints \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.sourceAnchorResolveResultRejectsNonCanonicalDocumentContentFingerprints \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryResultRejectsNonCanonicalSourceAnchorIds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.sourceAnchorResolveRequestRejectsNonCanonicalSourceAnchorIds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.sourceAnchorResolveResultRejectsNonCanonicalSourceAnchorIds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.sourceAnchorResolveRequestRejectsMissingRequiredField \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.sourceAnchorResolveResultRejectsMissingRequiredFields \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.sourceAnchorResolveResultRejectsInvalidChunkSummaryValues \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryResultRejectsInvalidCoordinatesAndRank \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryResultRejectsInvalidLexicalMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryMatchKindDefaultsLexicalAndControlsMatchedTermsBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryRequestSerializesEmbeddingModelHintAndRejectsBlankHint \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryResultRejectsMissingSourceAnchorId \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.retrievalQueryResultRejectsMissingMatchedTerms \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryPayloadsUseProtocolFieldNames \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryListRequestRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryDuplicateSuggestionsPayloadUsesClosedCanonicalContract \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryDuplicateSuggestionsPayloadRejectsMalformedOrNoncanonicalGroups \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryDuplicateSuggestionsPayloadUsesUnsignedUtf8OrderingForBmpAndAstralIds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryDuplicateSuggestionsPayloadRejectsJsonEscapedUnpairedSurrogateId \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryDuplicateSuggestionsPayloadUsesSharedAggregateUtf8IdBudget \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryDuplicateSuggestionsPayloadRejectsUnknownFields \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateSuggestionsPayloadUsesCanonicalWireContract \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateSuggestionsRequestRejectsBoundsAndInvalidTypes \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateSuggestionsResponseRejectsBoundsAndInvalidTypes \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateSuggestionsEnforcesPairShapeOrderAndDuplicates \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateSuggestionsUsesUnsignedUtf8AndAllowsIdsAcrossPairs \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateSuggestionsEnforcesAggregateUtf8IdBudget \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateSuggestionsWireRejectsDuplicateObjectKeysBeforeMaterialization \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateClustersPayloadUsesCanonicalWireContract \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateClustersRequestRejectsBoundsUnknownFieldsAndInvalidTypes \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateClustersWireRejectsDuplicateObjectKeysAndDeepNesting \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateClustersEnforcesShapeDisjointnessCountsAndOrder \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySemanticDuplicateClustersRejectsResponseTypesMetadataUnicodeAndIdBudget \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.decodeRejectsJsonNestingBeyondProtocolLimitWithoutStackOverflow \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryCrudRequestsRejectInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySummaryDraftsListRequestRejectsInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySummaryDraftGeneratePayloadRoundTripsExactWireShape \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySummaryDraftGeneratePayloadRejectsBoundsMalformedValuesAndUnknownMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySummaryDraftApprovePayloadUsesProtocolFieldNamesAndAcceptsGeneratedSource \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySummaryDraftDecisionRequestsRejectInvalidBounds \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memorySummaryDraftResponsePayloadsRejectInvalidBounds \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
  :core:protocol:testDebugUnitTest \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
  :core:transport:testDebugUnitTest \
  --tests com.localagentbridge.android.core.transport.BonjourDiscoveryTest.bonjourTxtRouteTokenRejectsWhitespaceMutationsInsteadOfTrimming \
  --tests com.localagentbridge.android.core.transport.BonjourDiscoveryTest.bonjourTxtRouteTokenRejectsOversizedAndMalformedValues \
  --tests com.localagentbridge.android.core.transport.BonjourDiscoveryTest.bonjourTxtMetadataRejectsForbiddenDiscoveryMaterial \
  --tests com.localagentbridge.android.core.transport.BonjourDiscoveryTest.bonjourTxtMetadataSanitizesLegacyIdentityHints \
  --tests com.localagentbridge.android.core.transport.RuntimePeerToPeerRoutePreparationTest \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparationTest \
  --tests com.localagentbridge.android.core.transport.RuntimeTransportClientTest.queuedSendDoesNotCrossReconnectOnSameClientObject \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.remoteRouteSecurityContextRejectsMissingOrExpiredRouteMetadata \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.remoteRoutePreparerRejectsRoutesThatReusePairingRouteTokenMaterial \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.identityOnlyTargetResolvesRoutesButNoConnectableRoute \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.remoteRoutePreparerCanConnectIdentityOnlyTargetThroughPeerToPeerConnector \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.defaultResolverIgnoresTrustedLastKnownEndpointHintForPairedTarget \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.preparedRelayRouteStillConnectsWhenTargetHasTrustedLastKnownEndpointHint \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.preparedRelayRouteIsAttemptedBeforeStaleEndpointHint \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.preparedRelayRoutePrecedesFreshDiscoveryRoute \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.freshDiscoveryRouteFallbacksWhenPreparedRelayRouteFails \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.relayConnectorCanFallbackAfterPreparedPeerToPeerRouteFails \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.futurePeerToPeerAndRelayRoutesAreNotAttemptedByDirectTcp \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.expiredRemoteRoutesAreRejectedBeforeConnectorAttempt \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.mismatchedRemoteRouteIdentityIsRejectedBeforeConnectorAttempt \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.remoteRouteMissingPinnedMetadataIsRejectedBeforeConnectorAttempt \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relaySessionCryptoMatchesP256ScalarOneAndTwoVectors \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relaySessionCryptoBindsRouteNonceIntoBindingAndTrafficKeys \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayFrameV2MatchesEpochBoundaryVectors \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayFrameV2RejectsReplayWithoutAdvancingAfterFailedAuthentication \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayFrameV2RejectsExhaustedCounterBeforeCrypt \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayEphemeralKeyRequiresCanonicalOnCurveP256Point \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.plaintextRelayPreservesLegacyRegistrationAndFrames \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.initialStrictRelayWithNullGenerationUsesExactV2HandshakeAndEncryptedFrames \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.strictRelayRejectsLegacyAndNonCanonicalReadyWithoutV1Fallback \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.strictRelayRejectsInvalidRuntimeConfirmationAndClosesSocket \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.pairedRelayAuthorizesMatchingChallengeThenCompletesStrictCrypto \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.pairedRouteRejectsMissingChallengeAsDowngradeBeforeAuthorizer \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.pairedRouteRejectsChallengeMismatchesBeforeAuthorizer \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.pairedRouteRejectsMatchingChallengeWhenAuthorizerIsMissing \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.strictRelayAuthenticationFailureClosesTransport \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayClientSerializesStrictEncryptionWithConcurrentSends \
	  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayConnectTimesOutWhenReadyLineNeverArrives \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
	  :app:compileDebugKotlin \
		  :app:testDebugUnitTest \
		  --tests com.localagentbridge.android.AppNavigationTest \
		  --tests com.localagentbridge.android.ResearchNotebookDrawerTest \
			  --tests com.localagentbridge.android.AppNavigationTest.settingsSystemLanguageOptionIsSeparateFromFixedLaunchLanguages \
				  --tests com.localagentbridge.android.AppNavigationTest.pairingQrRawValueAcceptsCompactRelayPayloadsFromScanner \
					  --tests com.localagentbridge.android.AppNavigationTest.pairingQrScannerClassifiesRawValuesBeforeConsumingCameraResult \
					  --tests com.localagentbridge.android.PairingQrScanResultTest \
					  --tests com.localagentbridge.android.PairingQrScanResultTest.validCompactPrivateOverlayRouteQrReturnsValid \
					  --tests com.localagentbridge.android.AppNavigationTest.routeNoticeActionIgnoresTrustedLastKnownEndpointForNormalQrFirstRecovery \
				  --tests com.localagentbridge.android.AetherLinkThemeNoDeviceComposeTest \
			  --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerVirtualizesAuthoritativeTenThousandNotebookSnapshot \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerKeepsNotebookMenuBoundToSessionAcrossActiveArchivedMove \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerHoistedChatMenuTracksStreamingLockoutAndFilteredAuthority \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerSeparatesResearchNotebooksAndRunsLifecycleConfirmation \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.researchNotebookDrawerFitsCompactHeightAtLargeFontScale \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.researchBriefDialogKeepsContentReachableAtCompactHeightAndLargeFont \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.researchBriefDialogModelPickerProjectsRuntimeCapabilitiesAndLocksDuringStreaming \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.researchBriefDialogModelRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.researchBriefCreateRejectsNonRuntimeHostLocalChatModelsBeforeDispatch \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.sharedChatDraftImportSnackbarStaysBoundedAboveComposerAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatArchiveUndoSnackbarStaysBoundedAboveComposerAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusProviderRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusProviderDiagnosticsDetailsStayBoundedAndRedactedAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusPanelStaysBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusModelResidencyLineLocalizesAndStaysBoundedAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusConnectedActionsStayBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusRouteNoticesStayBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsLanguagePickerStaysInPreferencesAfterPairingFirstAcrossLaunchLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsExpandableSectionHeadersStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimePanelStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimeForgetDialogStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsQrPairingPanelStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPendingPairingRouteStatusStaysBoundedAtLargeFontAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerSearchMatchesModelAndRuntimeMetadata \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerEmptyHistoryStaysBoundedAtLargeFontAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerChatSearchNoResultsStaysBoundedAtLargeFontAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerGroupsPreviousChatsByLocalDateAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerDisabledItemsExplainStreamingLockoutAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerOverflowMenuActionsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryStaysBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryShowsSavedMissingModelRecovery \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerShowsSavedMissingChatModelRecovery \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerKeepsLongModelNamesCompact \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarActiveTitleStaysBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarNewChatActionStaysBoundedAtLargeFontAcrossSupportedStates \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerStreamingDisabledStateStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerRowsExposeAccessibilitySummaries \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerDisablesUninstalledLocalChatModelPendingRuntimeHostApproval \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerRowsLocalizeAccessibilitySummariesAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerVisionRecoveryRowsStayBoundedAtLargeFontOnNarrowSurface \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerSearchNoResultsStaysBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerRefreshRowStaysBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarShowsNamedActiveChatTitleAndHidesDefaultNewChatFallback \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRowsExposeLocalizedModelMetadata \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRowsExposeLocalizedAccessibilitySummaries \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistorySummaryLocalizesSavedActiveAndArchivedCounts \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryActiveRowCanOpenChatWithHapticFeedback \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRefreshUsesCurrentSearchQuery \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistorySearchRefreshHeaderStaysBoundedAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryShowsRuntimeSearchSnippetForQueryResults \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRuntimeSearchMetadataStaysBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistorySearchResultActionsKeepFilteredContext \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRowActionsStayInsideNarrowLargeFontRowsAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryBulkActionsStayBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatHistoryConfirmationDialogsStayBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDiscoveredRuntimeRowsStayInsideNarrowLargeFontRowsAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDiscoveryActionsStayBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDeveloperDiagnosticsToggleRowStaysBoundedAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsHistoryAndMemoryRenderRepresentativeNarrowPhoneAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.renameChatSessionDialogStaysBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsCoreControlsRemainReachableAtLargeFontScaleAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsConnectionStatusTalkBackOrderProxyKeepsVisibleControlsReachableAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsAutoReconnectRowStaysBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.embeddingModelMenuModelsKeepsOnlyRuntimeHostLocalEmbeddingModels \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelRowsExposeSelectedStateToAccessibility \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelControlsAreDisabledWhileStreaming \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelRowsLocalizeAccessibilitySummariesAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenEmbeddingModelRowsStayBoundedWhenExpandedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPreferenceRowsExposeSelectedStateToAccessibility \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsAppearanceAndLanguagePreferenceRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsLanguagePreferenceRowsDispatchSystemAndFixedSelectionCallbacks \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.diagnosticQrTextDialogStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsKeepActionsBelowLongContentOnCompactWidth \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryDeleteConfirmationDialogStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsShowApprovedSourceMetadataWithoutFullTranscript \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryApprovedSourceMetadataLocalizesAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryApprovedSourceMetadataStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryAddControlsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryEmptyStatesStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemorySummaryLocalizesSavedAndPausedCountsAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemorySearchFiltersRowsAndShowsRuntimeSearchMetadata \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDocumentPanelShowsCatalogSummaryAndRows \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDocumentSearchCallsRuntimeQueryAndShowsResults \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDocumentSearchKeepsSourceAnchorIdsHiddenFromUi \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsSemanticDocumentSearchUsesLocalizedMetadataAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDocumentSearchSourceReviewActionUsesNamedTalkBackLabelAndHidesOpaqueCanaries \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsSourceReviewDialogShowsLoadingAndSafeUntrustedMetadataWithDisabledBusyControls \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedSourceReviewAndListSupportRefreshAndRevokeWithoutOpaqueExposure \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedSourcesDistinguishNotLoadedFromLoadedEmpty \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTrustedSourcePickerUsesCheckboxesCapsSelectionAndRemovesSafeDocumentChips \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTrustedSourceErrorsUseActionableCopyInsteadOfUnknownFallback \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenSourceAttributionsRenderBetweenAnswerAndActionsWithLocalizedTalkBackSummaries \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.historicalSourceAttributionRowOpensReviewAndKeepsStableLoadingDimensions \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDocumentRefreshActionFollowsConnectionStateAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDocumentRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelShowsSummaryDraftApprovalAction \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelDisablesPendingSummaryDraftApproval \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelShowsSummaryDraftDismissAction \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelDisablesPendingSummaryDraftDismissal \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelGenerateSummaryActionTransitionsToLockedGeneratingState \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelGeneratedSummaryShowsReviewLabelWithoutGenerateAction \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemorySummaryDraftRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatSurfaceRendersRepresentativeNarrowPhoneWithoutComposerOverlap \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatSurfaceRepresentativePopulatedStateStaysBoundedAtLargeFontAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenCoreControlsRemainReachableAtLargeFontScaleAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenTalkBackOrderProxyKeepsVisibleChatControlsReachableAtLargeFontAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.parseMessageContentPreservesCodeBlocksAndNormalizesMarkdownTextBlocks \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRendersMarkdownListsAndInlineCode \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenMarkdownTablesExposeLocalizedAccessibilitySummaryAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenCodeBlocksExposeLocalizedAccessibilitySummaryAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenMarkdownTablesAndCodeBlocksStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShortReasoningIsReadAsStaticThinkingAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenAssistantReasoningStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsRegenerateActionOnlyForLatestAssistantAndHidesWhileStreaming \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsReuseDraftActionOnlyForLatestEligibleUserMessage \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenLatestMessageActionsExposeLocalizedStateAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenLatestMessageActionsStayInsideNarrowLargeFontRowsAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenTranscriptUsesCompactSameRoleSpacingAndWiderRoleChanges \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenJumpToLatestButtonStaysAboveComposerAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenAttachmentOnlyMessageRowsExposeLocalizedRoleAccessibilitySummaries \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenAssistantIdentityMarkerStaysLegibleAndSeparateAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenReadOnlyAttachmentChipsWrapOnCompactWidthAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenPendingAttachmentChipsWrapOnCompactWidthAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenClearDraftActionClearsComposerAndHidesWhileStreaming \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenTextOnlyDraftControlsStayBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenStreamingCancelControlsStayBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenStreamingProgressIndicatorStaysDecorativeAndBoundedAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenComposerReadinessStatusStaysBoundedAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRouteAvailabilityNoticeStaysBoundedAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRouteRefreshSavedNoticeStaysBoundedAboveComposerAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsRouteRefreshSavedNoticeStaysBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenBackendUnavailableBannerStaysBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenGenericErrorBannerStaysBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatContextWindowExceededErrorLocalizesAndStaysBoundedAtLargeFont \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsLocalizedLoadingStateWhileRuntimeTranscriptLoads \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRuntimeTranscriptLoadingStateStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsCompanionOnlyPanelAnnouncesLocalizedPrivateModelAccessAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsCompanionOnlyPanelStaysBoundedAtLargeFontAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenTrustedRuntimeWithoutConnectableRouteShowsLatestQrEmptyState \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatEmptyNoModelGuidesUsersToHeaderModelPickerAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatEmptyUninstalledModelGuidesUsersToInstallOrChooseAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatEmptyStatesStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusScreenKeepsDiagnosticRoutesStatusOnly \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusTrustedLastKnownOnlyRouteScansLatestQrWithHaptic \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusConnectedActionsDisableWhileConnectingAcrossSupportedLanguages \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayRestoreMarksConnectingBeforeRelayDialCompletes \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelAutoReconnectsTrustedRelayOnInitAndRefreshesRuntimeState \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelShowsExpiredRemoteRouteWhenTrustedRelayLeaseExpiredOnInit \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRestoreDoesNotStartDiscoveryWhenRelayRouteIsAvailable \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRestoreDoesNotStartDiscoveryWhenP2pRouteIsAvailable \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairedRelayAllocationClaimSignsExactAuthorizationAndPersistsFinalGeneration \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairedRelayAllocationRenewalPersistsNextGeneration \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairedRelayAllocationClaimsUnversionedRouteAfterRuntimeOnlyBootstrapRenewals \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairedRelayAllocationRejectsWrongMutatedExpiredSecretBearingAndDuplicateChallenges \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairedRelayAllocationRejectsFinalBeforeProofMismatchAndMissingGeneration \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairedRelayAllocationTimeoutDisconnectAndPlaintextChannelClearWithoutSigning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.newPairingQrPreemptsActiveUntrustedConnection \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.newPairingQrPreemptsActiveDifferentTrustedRuntimeConnection \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sameRuntimePairingQrDoesNotPreemptActiveTrustedConnection \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayReconnectAttemptsRelayBeforeMatchingBonjourFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayQrPairingFailsBeforeConnectWhenDeviceCannotReachRelayRoute \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayProbeResponseParserRequiresKnownRouteAndWaitingRuntime \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayProbeKnownParserAllowsRuntimeReconnectRace \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrPairingResultPersistsTrustedRelayAndClearsPendingRoute \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.duplicateCompactRelayQrScanSendsSinglePairingRequestOnActiveRelayConnection \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.unsignedRejectedPairingResultKeepsPendingRouteAndSecretForAuthenticatedRetry \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairingResultRejectsUnknownMetadataBeforeTrustMutation \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultRejectsIncompleteRelayRouteInsteadOfDirectFallback \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultRejectsIncompleteP2pRouteInsteadOfDirectFallback \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.currentAuthenticationErrorWithChatHistoryPrefixIsNotIgnored \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.malformedAuthChallengeTerminatesAttemptAndFreshAcceptedResponseCannotAuthenticate \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authResponseResultRejectsUnknownMetadataBeforeAuthenticationStateMutation \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pendingPairingQrWithoutRemoteRouteDoesNotFallbackToSavedRelayRoute \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultDropsQrDirectEndpointFromTrustedRuntimeStorage \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeConnectionTargetDropsTrustedLastKnownEndpoint \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.discoveredRuntimeSelectionRequiresTrustedIdentityMetadata \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.discoveredRuntimeSelectionCanUsePendingPairingIdentityBeforeTrustIsSaved \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesUseDiscoveredEndpointInsteadOfTrustedLastKnownFallback \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesDoNotAutoUseMetadataLessDiscoveryForTrustedIdentity \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesUseRouteTokenBeforeLegacyIdentityMetadata \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesIgnoreRouteTokenMismatchEvenWhenLegacyIdentityMatches \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesRejectUnpinnedDiscoveryRouteTokenEvenWhenLegacyIdentityMatches \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedDiscoveredRuntimeConnectionTargetRequiresMatchingDiscoveryIdentity \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedDiscoveredRuntimeConnectionTargetRejectsMetadataLessDiscovery \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesIgnoreDiscoveredEndpointWithMismatchedIdentityMetadata \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesIgnoreSelectedBonjourEndpointWithMismatchedIdentityMetadata \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesRejectMetadataLessSelectedBonjourEndpoint \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesRejectSelectedBonjourEndpointMissingCurrentDiscoveryMetadata \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.autoReconnectTrustedRuntimeTargetWaitsForFreshRouteWhenOnlyTrustedLastKnownEndpointExists \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.autoReconnectRouteCandidatesDoNotUseTrustedLastKnownEndpointAsFallback \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesRejectDirectModelProviderPortsFromSelectedAndDiscoveredRoutes \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.transportBoundAuthenticationRejectsDowngradeMismatchAndOldBindingReplay \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.compactRelayQrPairingUsesRealRelayTcpClientAndPersistsTrustedRelay \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.privateOverlayRelayQrPairingUsesRealRelayTcpClientAndPersistsOverlayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.trustedRelayReconnectRejectsInvalidRuntimeProofBeforeAuthResponse \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.trustedRelayReconnectRejectsRuntimeFingerprintMismatchBeforeAuthResponse \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.freshCompactRelayQrRefreshesExpiredTrustedRelayRouteAndReconnectsViaRelay \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.invalidPairingQrDoesNotEnableTrustedRuntimeAutoReconnect \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.privateOverlayRelayQrParseFailureReportsScopeRequired \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrRejectsIdentityOnlyQrInNormalScanPath \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.diagnosticIdentityOnlyQrPlanStartsDiscoveryAndWaitsForRouteWhenRemoteRouteIsNotRequired \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.diagnosticIdentityOnlyPairingQrCanUseUsbReverseFallbackWhenRemoteRouteIsNotRequired \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromMacosPrivateOverlayQrConnectsRelayAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrPersistsPendingRouteAfterInitialConnectionFailure \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresPendingPairingRouteUntilShorterRelayExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresPendingP2pRendezvousRouteUntilShorterRecordExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRejectsNonCanonicalPendingPairingIdentityValues \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRejectsNonCanonicalPendingPairingRouteToken \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRejectsNonCanonicalPendingRuntimePublicKey \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRejectsNonCanonicalPendingRelayRouteMaterial \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerRejectsNonCanonicalSavedRelayMaterial \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerRejectsNonCanonicalPendingRelayMaterial \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerPlansPendingP2pRendezvousBeforeRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesOnlyMatchingPendingDualRouteMaterial \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesInjectedClockForPendingP2pRendezvousRecord \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeP2pReconnectUsesStoredQrRendezvousMetadata \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedPeerToPeerRouteFallsBackToRelayAtViewModelConnectionLayer \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesInjectedClockForSavedP2pRendezvousRecord \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.autoReconnectTrustedRuntimeTargetUsesSavedP2pRouteWithoutManualEndpoint \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.productPairingQrParserRejectsIdentityOnlyQrWhenRemoteRouteIsRequired \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.productPairingQrParserRequiresRuntimePublicKeyAndRouteTokenWhenRemoteRouteIsRequired \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.productPairingQrParserAcceptsP2pRendezvousQrWhenRemoteRouteIsRequired \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultPreservesRelaySecretForTrustedRuntimeRestore \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultRejectsMismatchedRuntimeIdentity \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultPreservesP2pRendezvousForTrustedRuntimeRestore \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.expiredRelayQrIsNotSavedAsTrustedRuntime \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.expiredP2pQrIsNotSavedAsTrustedRuntime \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAfterAcceptedRelayPairingDoesNotOpenDuplicateRelayConnection \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAfterAcceptedP2pPairingDoesNotOpenDuplicatePeerConnection \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAddsP2pRendezvousRouteToExistingTrustedRuntime \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeSchedulesRouteRefreshBeforeRecordExpiry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeRetriesRouteRefreshErrorBeforeRecordExpiry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeMarksRouteExpiredWhenRefreshCannotRetryBeforeRecordExpiry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedMixedRoutesRefreshUrgentRelayAndRetryWithinP2pLease \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedMixedRoutesRefreshUrgentP2pAfterRelayFallbackAndRetryWithinRelayLease \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataDropsDirectEndpointFromPendingPairingRouteStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRemovesPendingPairingRelaySecretWhenRouteClearsOrReplaces \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrRetriesAndSendsPairingRequestAfterRelayBecomesReady \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.releasePairingParserRejectsMacosLocalDiagnosticQrRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeHealthStoresModelResidencySnapshotFromAggregateRuntime \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeHealthRejectsUnknownMetadataBeforeRuntimeStatePublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeHealthPublishesOnlyLatestCurrentRequestOnce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeHealthRejectsWrongChannelConnectionAndReauthenticatedAuthority \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeHealthExactCurrentTerminalsCloseBeforeDuplicateAndRetry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeHealthClearsPendingOnDisconnectRevocationAndViewModelClear \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeHealthIgnoresSupersededErrorAndDelayedSendFailure \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentCatalogRequiresExactCurrentAuthorityAndConsumesOnce \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchRequiresExactCurrentAuthorityAndConsumesOnce \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.delayedOldDocumentSendFailureCannotCloseReplacementRequest \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pendingDocumentAuthorityClearsOnDisconnectRevocationAndViewModelClear \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatMessagesListRequiresExactCurrentAuthorityAndConsumesOnce \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sameChannelReauthenticationTombstonesOldChatMessagesAuthority \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentCatalogErrorConsumesOnlyExactCurrentAuthorityAllowsRetryAndKeepsDuplicatesInert \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentCatalogImmediateSendFailureAllowsRetryAndKeepsLateFramesInert \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.delayedOldChatMessagesListSendFailureCannotCloseReplacementRequest \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pendingChatMessagesAuthorityClearsOnDisconnectRevocationAndViewModelClear \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSessionsListRequiresExactCurrentAuthorityAndConsumesOnce \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSessionsListWrongSourceCannotAdvancePaginationOrTriggerTerminalFailure \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sameChannelReauthenticationReplacesPendingMemoryAndResearchListAuthority \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.siblingAuthenticationErrorClearsConcurrentPendingMemoryListAuthority \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSessionsBulkLifecycleRequiresExactTerminalAuthority \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSessionsBulkMalformedCurrentErrorConsumesOnlyExactAuthority \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSessionsBulkSendFailureRequiresExactDispatchAuthority \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeModelResidencyStatusRedactsUnsafeSnapshotDetails \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderSafeMessageTreatsMissingAndUnsafeMessagesAsEmpty \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectedModelSendStateRejectsEmbeddingModelAsChatModel \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.requestModelInstallRejectsUnknownModelWithoutPersistingOrPulling \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectModelRejectsUnknownModelWithoutPersistingOrPulling \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelsResultRejectsUnknownMetadataBeforeModelStatePublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSessionsListRejectsUnknownMetadataBeforeHistoryStatePublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.updateChatInputRejectsWhileStreamingAndPreservesDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksModelSelectionAndInstallRequests \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksReentrantChatSendRequests \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksMemoryMutations \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksRuntimeRouteTrustAndConnectionMutations \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectEmbeddingModelRejectsUninstalledRuntimeModelWithoutChangingSelection \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsPersistedSelectionsWhileModelListIsRestoring \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsMissingPersistedSelectionsTypedAcrossRefresh \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsSelectionsWhenRefreshedModelHasWrongKind \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsEmbeddingSelectionWhenModelIsNotInstalled \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsExplicitEmbeddingSelection \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelKindNormalizationSeparatesChatAndEmbeddingModels \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.embeddingCapabilityPreventsModelFromBeingTreatedAsChat \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresSelectedChatAndEmbeddingModelsSeparately \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataCanClearSelectedEmbeddingModel \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateBuildsAfterFirstCompletedExchange \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateRejectsUnsafeOrAlreadyTitledSessions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleResultRejectsUnknownMetadataBeforeGeneratedTitlePublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleCurrentSuccessPublishesAndReconcilesOnce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleReconciliationCoalescesBothAuthoritativeResponseOrders \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleReconciliationRejectsLegacySnapshotsForBothLegsAndResponseOrders \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.emptyChatTitleResultClosesAndReconcilesWithoutLocalPublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.malformedChatTitleResultIsTerminalAndLateSameIdFramesAreInert \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleFramesCannotCrossChannelConnectionOrReauthenticationAuthority \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sameChannelReauthenticationClosesPendingTitleAndReconcilesOnce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sameChannelReauthenticationReplacesHeldTitleReconciliationAuthorityOnce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.currentTitleAuthenticationErrorRevokesAndRecoversWithOneReconciliation \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleOrdinaryErrorClosesAndReconcilesOnce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.malformedAndUnknownChatTitleErrorsAreTerminalBeforeAuthInterpretation \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleTombstonesCapAt128AndRetainedOrEvictedFramesRemainInert \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleSendFailureAndTimeoutCloseOnceAndIgnoreLateResults \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleResultSkipsStalePublicationAfterLocalSessionRace \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.secondChatTitleCandidateDrainsAfterFirstTerminalWithoutOverwritingCorrelation \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleReconciliationAllLegTerminalsReleaseForOneFreshGeneration \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleDeferredCandidatesCapEvictAndDrainRetainedFifoOnce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleReconciliationTimeoutJobsCancelOnAuthConnectionAndClear \
  --tests com.localagentbridge.android.runtime.RuntimeClientChatSessionMutationFailureTest.chatSessionRenameResultRejectsUnknownMetadataBeforeCachePublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientChatSessionMutationFailureTest.chatSessionLifecycleResultRejectsUnknownMetadataBeforeCachePublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.newPersistedMessagesDoNotUseFirstUserPromptAsTitle \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedMigratesLegacyPromptTitleToDefaultTitle \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedPreservesExplicitAndRuntimeGeneratedPromptTitles \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.generatedChatTitleAppliesOnlyUntilUserRenamesSession \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedComposerDraftRestoresOnViewModelCreationAndUpdatesWithTyping \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openPreviousChatRestoresSessionScopedComposerDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.clearChatDraftClearsActiveSessionTextAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.startNewChatClearsNoActiveDraftButKeepsSessionDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveActiveChatClearsNoActiveDraftAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveAllChatsClearsNoActiveDraftAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openingRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sendChatMessageClearsOnlyActiveSessionComposerDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedCapsSessionScopedComposerDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedDropsArchivedSessionComposerDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sendChatMessageClearsPersistedComposerDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.regenerateLatestResponseExcludesOldAssistantFromPayloadAndHistory \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.regenerateLatestResponsePreservesComposerDraftAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.regenerateLatestResponseBlocksAttachmentBackedPriorPrompt \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.reuseLatestUserMessageAsDraftCopiesLatestTextWithoutSendingOrMutatingHistory \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.reuseLatestUserMessageAsDraftRejectsAttachmentBackedPromptAndPreservesDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.reuseLatestUserMessageAsDraftRejectsWhileStreamingAndPreservesDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotRedactsArchivedRuntimeOwnedBodiesButKeepsLocalArchivedBodies \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteRequiresArchivedChatSession \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveAllChatSessionsRetainsSessionsAsArchivedAndKeepsMemoryCandidatesEmpty \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteArchivedChatSessionsDoesNotDeleteActivePreviousChats \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteArchivedChatSessionsSuppressesOnlyRuntimeOwnedArchivedSessions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMessagesReplaceSessionTranscriptAndPreserveReasoningWithStableIds \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatMessagesListIgnoresRuntimeOnlyCompactionMetadataInRawPayload \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatMessagesListRejectsUnknownMetadataBeforeTranscriptPublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatMessagesListRejectsInlineStoredAttachmentBytesBeforeTranscriptPublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMessagesDoNotResurrectSessionMissingFromLatestRuntimeSummary \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeSessionSummariesReplaceRuntimeOwnedCacheAndPreserveLocalSessions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeSessionSummariesClampNegativeMessageCounts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingRuntimeOwnedChatRendersInMemoryButRedactsDeviceStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryListRendersInMemoryButRedactsDeviceStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryListRejectsUnknownMetadataBeforeMemoryStatePublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryUpsertResultRejectsUnknownMetadataBeforeMemoryMutation \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryDeleteResultRejectsUnknownMetadataBeforeMemoryMutation \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryMutationResultsRequireExactCurrentAuthorityAndExpectedPayload \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryMutationErrorsRequireExactCurrentAuthorityAndConsumeOnce \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryMutationSendFailureAndLifecycleCleanupRequireExactAuthority \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryDuplicateSuggestionsPublishesReviewOnlyStateWithoutPersistence \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryDuplicateSuggestionsRejectsMalformedDuplicateUnknownIdsAndMetadata \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryDuplicateSuggestionsIgnoresStaleResponsesAndClearsAcrossAuthorityChanges \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryDuplicateSuggestionsClosesSendFailuresBeforeIgnoringStaleErrors \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryDuplicateSuggestionsClosedCorrelationHistoryIsBounded \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryDuplicateSuggestionsResetsAcrossDisconnectAndReplacementChannelAuthority \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memoryDuplicateSuggestionsDisablesOldRuntimeUnsupportedOperationsForCurrentAuthority \
		  --tests com.localagentbridge.android.AppNavigationTest.memoryDuplicateReviewRequiresAuthenticatedFeatureAvailability \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.memoryDuplicateReviewShowsLocalizedReviewOnlyAndTruncatedState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsAdvertisesSeparatelyAndRequiresCurrentAuthorityAndLocalModel \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsPublishesTransientReviewStateWithoutPersistence \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsRejectsLowScoresUnknownIdsAndUnknownMetadata \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsIgnoresSupersededResponsesAndNamespacedErrors \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsUnsupportedDisablesOnlySemanticForCurrentAuthority \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsClearsOnModelChangeMutationAndAuthoritativeRefresh \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsClearsAcrossDisconnectAndReplacementAuthentication \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsClosedCorrelationHistoryIsBounded \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateSuggestionsRejectsResponseAfterSelectedModelLeavesCurrentCatalog \
		  --tests com.localagentbridge.android.AppNavigationTest.memorySemanticDuplicateReviewRequiresCurrentInstalledLocalEmbeddingModel \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.memoryExactAndSemanticDuplicateActionsStayDistinctAndUseExactBasisPoints \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.memorySemanticDuplicateResultIsReviewOnlyAndKeepsManualControls \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.memorySemanticDuplicateControlsExposeDisabledReasonAndScanningState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateClustersAdvertisesCanonicalRequestAndPublishesTransientReviewState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateClustersRejectsLowScoresUnknownIdsMetadataAndIdenticalContents \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateClustersIgnoresStaleResponsesAndUnsupportedDisablesOnlyClusters \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateClustersRejectsStaleCatalogAndClearsOnModelMutationAndDisconnect \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateClustersRequiresCurrentAuthorityCorrelatedModelCatalog \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateClustersIgnoresSupersededModelListSendFailure \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateClustersMalformedCorrelatedErrorPreservesInvalidPayload \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticDuplicateClustersClosedCorrelationHistoryIsBounded \
		  --tests com.localagentbridge.android.AppNavigationTest.memorySemanticDuplicateClustersReviewRequiresSeparateCapabilityAndCurrentLocalModel \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.memorySemanticDuplicateClustersControlsStayDistinctAndUseExactBasisPoints \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.memorySemanticDuplicateClustersResultIsReviewOnlyAndKeepsManualRowControls \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemorySummaryDraftsListRendersReviewStateWithoutDeviceStorage \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryDraftsListRejectsUnknownMetadataBeforeReviewStatePublication \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryDraftsListIgnoresSupersededDuplicateAndUnsolicitedResponsesAfterGeneration \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryDraftReconciliationWaitsForConcurrentActionAndDrainsAfterLastCompletion \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryDraftDeferredReconciliationDrainsOnTerminalErrorAndSendFailure \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.staleMemorySummaryApproveAndDismissReconcileOnceAfterLastPendingAction \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.malformedMemorySummaryDecisionResultsClearPendingAndDrainDeferredRefreshOnce \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryDraftsListSameChannelReauthenticationReplacesOldAuthorityRequest \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.delayedMemorySummaryActionResultsCannotCrossSameChannelReauthentication \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummarySourceIdentityRejectsEveryAuthoritativeFieldMutationExceptInactivity \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryDecisionFramesRequireExactChannelAndIgnoreLateDuplicates \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelProductionDeadlineTest.productionFactoryEnablesHostAlignedMemorySummaryDeadlines \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryGenerationAcceptsResultAfterControlDeadlineBeforeHostAlignedDeadline \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryProtocolErrorMalformedResultAndSendFailureCancelExactTimeoutJobs \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryListAndActionsTimeoutClosePendingAndAllowRetry \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryActionTimeoutDrainsDeferredRefreshOnceAndIgnoresLateTerminals \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryTimeoutJobsStayAuthorityBoundAndCancelOnDisconnectAndClear \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryApproveAndDismissPendingStateClearsOnReceiveFailure \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryListAndActionErrorsRejectUnknownMetadataBeforeAuthRevocation \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.evictedClosedMemorySummaryListErrorCannotReachGenericErrorHandling \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.generateMemorySummaryDraftSendsStaleGuardsBlocksDuplicateDecisionsAndStaysTransient \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.generateMemorySummaryDraftRejectsCanonicalResultFromDifferentRequestedModelAndRefreshesDrafts \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.generateMemorySummaryDraftRejectsBusyOrIneligibleModelAndRetainsMalformedResult \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.generateMemorySummaryDraftStaleErrorClearsPendingKeepsPreviewAndRefreshesDrafts \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.generateMemorySummaryDraftSendFailureClearsPendingAndKeepsDeterministicPreview \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.approveMemorySummaryDraftSendsExpectedApprovalAndRendersRuntimeMemoryOnly \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.approveMemorySummaryDraftOmitsExpectedMethodForLegacyRuntime \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.approveMemorySummaryDraftRejectsResultsNotBoundToExactGeneratedDraftAndCanonicalEntry \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryDraftApproveResultRejectsUnknownMetadataBeforeMemoryMutation \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.approveMemorySummaryDraftErrorClearsPendingAndAllowsRetry \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.dismissMemorySummaryDraftSendsExpectedDecisionAndRemovesDraft \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.dismissMemorySummaryDraftRejectsNoncanonicalResultBinding \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySummaryDraftDismissResultRejectsUnknownMetadataBeforeReviewStateMutation \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.dismissMemorySummaryDraftErrorClearsPendingAndAllowsRetry \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryEntriesReplaceAndMutateCachedMemory \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemoryRequestsFreshListAfterPendingListCompletes \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryRequestsFreshListAfterPendingListCompletes \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryCanSendTrimmedQuery \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistorySendsSelectedEmbeddingModelOnlyForSearchQuery \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeChatSearchResultsStayTransientAndDoNotReplaceFullHistoryCache \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authoritativeSearchOnlyRuntimeChatCanOpenAndLoadTranscript \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.completedRuntimeChatSearchResponseCannotReplayAsFullHistorySync \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeReceiveFailureRevokesSearchOnlySessionAuthority \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeConnectionReplacementRevokesSearchOnlySessionAuthority \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.delayedRevokedSessionSendFailureCannotMutateReauthenticatedState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.completedMutationDelayedSendFailureCannotMutateActiveStream \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.completedHelloSendFailureCannotMutateAuthenticatedState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.completedPairingSendFailureCannotMutateAuthenticatedState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeChatHistoryAuthenticationLossRevokesSearchOnlySessionAuthority \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryAuthenticationLossRevokesSearchAndPendingHistoryAuthority \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMutationFailureSupersedesPendingSearchAndRestoresOptimisticState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeAuthenticationLossRollsBackConcurrentChatSessionMutations \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.promotedSearchSummaryIsConsumedBeforeRuntimeLifecycleActions \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.remoteSearchSummaryCannotReplaceLocalOnlySessionWithSameId \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemorySearchSendsSelectedEmbeddingModelHint \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemorySearchResultsStayTransientAndIgnoreLateResponses \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.malformedMemoryListResponsesReleasePendingRequestAndIgnoreLateResults \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.memorySemanticSearchRetriesLexicallyWhenRuntimeRejectsEmbeddingHint \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemorySearchUsesMatchingRemoteSemanticResultsOnlyForCurrentQuery \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeChatMessagesListErrorClearsLoadingAndShowsChatHistoryLoadFailed \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryErrorShowsLoadFailureAndAllowsRetry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemoryErrorShowsFailureAndAllowsRetry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemorySummaryDraftsErrorShowsFailureAndAllowsRetry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.errorPayloadRejectsUnknownMetadataBeforePendingStateMutation \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.errorPayloadRejectsUnknownMetadataBeforeActiveStreamTermination \
  --tests com.localagentbridge.android.runtime.RuntimeClientChatSessionMutationFailureTest \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotDropsRuntimeOwnedDataButKeepsLocalDrafts \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeLifecycleAckDoesNotMutateLocalOnlySessionWithSameId \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeConnectionTargetOmitsDirectEndpointWhenRelayRouteIsSaved \
					  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeConnectionTargetOmitsDirectEndpointWhenP2pRouteIsSaved \
							  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectUsesStoredQrLeaseMetadata \
							  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectRejectsMismatchedPinnedIdentity \
							  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectIgnoresLoopbackRelayRoute \
							  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectAllowsDebugUsbReverseRelayRoute \
							  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectAllowsPrivateOverlayRelayRoute \
							  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectRejectsScopeLessPrivateRelayRoute \
							  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesInjectedClockForSavedRelayLease \
									  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesInjectedClockForPendingPairingRelayLease \
									  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairingRuntimeTargetUsesRelayQrWithoutLocalEndpoint \
									  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairingRuntimeTargetIgnoresDirectEndpointWhenRelayQrAlsoHasIt \
									  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairingRuntimeTargetIgnoresDirectEndpointWhenP2pQrAlsoHasIt \
								  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pendingPairingRelayQrOverridesSavedRelayRoute \
					  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectRejectsExpiredSavedRelayLease \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectRejectsIncompleteSavedRelayLease \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.autoReconnectTrustedRuntimeTargetUsesSavedRelayRouteWithoutManualEndpoint \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshLeaseDelayUsesRenewalWindow \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshLeaseDelayRefreshesImmediatelyWhenMinimumDelayWouldOutliveLease \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshRetryDelayStaysInsideActiveLease \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.remoteRouteLeaseHelpersSelectEarliestEligibleMixedRouteLease \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeSchedulesRouteRefreshBeforeLeaseExpiry \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesRouteRefreshErrorBeforeLeaseExpiry \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeDoesNotRetryNonRetryableRouteRefreshError \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRejectsRouteRefreshPayloadWithUnknownMetadataBeforeStorage \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesMalformedRouteRefreshAllowedFieldPayloadBeforeLeaseExpiry \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsMismatchedRuntimeIdentity \
				  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsNonCanonicalRuntimeIdentity \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsUnknownRelayScope \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsScopedRelayHostScopeMismatch \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsNonCanonicalRelayMaterial \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshRelayRouteToCurrentTrustedRuntime \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteRelayMaterial \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAllowsStableRelayIdAndSecretWithFreshNonceAndExpiry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsReusedRelayNonce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsNonAdvancingRelayExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshP2pRendezvousRouteToCurrentTrustedRuntime \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteP2pMaterial \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsNonCanonicalP2pMaterial \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsReusedP2pRendezvousRecordOrNonce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsNonAdvancingP2pExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeRetriesRouteRefreshWhenRuntimeReturnsReusedP2pRecord \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeRetriesRouteRefreshWhenRuntimeReturnsNonAdvancingP2pExpiry \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRejectsIncompletePendingPairingRoute \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrWithoutPublicKeyCanRefreshPinnedRuntimeRelayRoute \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrWithoutPublicKeyCanRefreshPinnedRuntimeP2pRendezvousRoute \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAddsRelayRouteToExistingTrustedRuntime \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrRejectsReusedOrNonAdvancingRemoteRouteMaterial \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrDropsTrustedEndpointFallbackWhenRelayRouteIsSaved \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrRejectsDirectRouteForExistingTrustedRuntime \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrCanRotateRouteTokenForPinnedRuntimeIdentity \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrRejectsUntrustedOrMismatchedRuntimeIdentity \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.expiredRouteRefreshQrIsNotSavedAsTrustedRuntimeRoute \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrRejectsRelayRouteWithoutSecret \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrRejectsExpiredOrIncompleteP2pRoute \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrRejectsP2pRouteWithRelayScopeOnly \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrKeepsUnreachableRelayRouteForRetryOrFreshQrRecovery \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayReceiveAuthenticationFailureClearsStoredRelayAndStopsAutoReconnect \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayConnectionFailureKeepsStoredRelayAndStopsAutoReconnectUntilUserRetries \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayHandshakeRejectionKeepsStoredRelayAndStopsAutoReconnectUntilUserRetries \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeMarksRouteExpiredWhenRefreshErrorCannotRetryBeforeLeaseExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshAuthenticationRequiredDoesNotRetainRouteMaterialTechnicalDetail \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesRejectedRouteRefreshPayloadBeforeLeaseExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRelayRuntimeRetriesRouteRefreshWhenRuntimeReturnsReusedRelayNonce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRelayRuntimeRetriesRouteRefreshWhenRuntimeReturnsNonAdvancingRelayExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeConnectionFailureMapsRouteMissingReasonsToFocusedUiErrors \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.activeCompletionCancellationAndErrorRemoveOnlyBlankAssistantPlaceholder \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeReceiveFailureClearsStreamingAndRemovesOnlyBlankAssistantPlaceholder \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeAuthenticationErrorTransitionsToPairingRequiredState \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelReconcilesSystemAppLanguageUntilInAppLanguageIsSelected \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.systemAppLanguageHelperDoesNotOverrideInAppLanguageSelection \
  --tests com.localagentbridge.android.runtime.RuntimeAttachmentPromptResourceTest.attachmentOnlyPromptHeaderUsesLocalizedAndroidResources \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlyPromptUsesSelectedAppLanguageAndEnglishFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlySendUsesSelectedLanguagePromptInChatSendPayload \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentSendAttachesMetadataOnlyToFinalUserPayloadMessage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.imageAttachmentSendRequiresVisionModelAndKeepsPendingAttachmentsWhenBlocked \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.validAttachmentSendClearsPendingAttachmentsAndRetainsReadonlyMessageChips \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksPendingAttachmentMutation \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.removePendingAttachmentDropsOnlySelectedAttachmentAndClearsError \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.blankMessageWithoutAttachmentsDoesNotSend \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsLoadsDocumentAndImageUrisIntoPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsStopsBeforeReadingReportedOversizeFile \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsBoundsReadWhenReportedSizeIsUnknown \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsKeepsAtMostFourPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsWithExistingPendingAttachmentsReadsOnlyRemainingSlotsAndShowsLimit \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSendMessagesSerializesOnlyClientVisibleConversationAndFinalAttachments \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryEntriesReplaceAndMutateCachedMemory \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemorySendsTrimmedQueryAndRedactsSearchMetadataFromDeviceStorage \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemorySearchDoesNotSendSelectedEmbeddingModelHint \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentCatalogRequestStoresTransientCatalogWithoutDeviceStorage \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentCatalogClearsTransientRowsOnDisconnect \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentCatalogSummaryBoundsTransientCountsFromRuntimeResponses \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentResponsesCapTransientRowsToRequestLimits \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentMetadataRejectsNonCanonicalContentFingerprintsBeforeTransientState \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentResponsesRejectUnknownFutureMetadataBeforeTransientState \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentMetadataReplacesNonCanonicalMimeTypesInTransientState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentMetadataDerivesQualityFromChunkCountInTransientState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentMetadataBoundsIdsAndDisplayNamesInTransientState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchSendsBoundedQueryAndStaysOutOfChatContext \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchSendsSelectedEmbeddingModelHint \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchRejectsOverlongQueryBeforeSendingRetrievalRequest \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchInvalidQueryCancelsPendingRequestAndIgnoresStaleResponses \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchBoundsTransientLexicalMetadataFromRuntimeResponses \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchRejectsInvalidLexicalMetadataBeforeTransientState \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchAcceptsSemanticMatchKindAndPreservesEmptyTerms \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSemanticSearchRetriesLexicallyOnceAndIgnoresLateSemanticResponses \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchIgnoresVeryLateErrorsAfterManyCompletedSearches \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSemanticSearchDoesNotFallbackForNonCompatibilityErrors \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchRejectsInvalidCoordinatesAndRankBeforeTransientState \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchDropsNonCanonicalSourceAnchorIdsFromTransientState \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeIgnoresUnsolicitedSourceAnchorResolveResultWithoutAdvertisingOrPersisting \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchClearsTransientResultsAndSourceAnchorsOnDisconnect \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeDocumentSearchErrorClearsPendingAndAllowsRetry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedSourceFullLifecycleKeepsOpaqueValuesOutOfUiPersistenceAndChat \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedSourceSelectionCapsAtEightCurrentListedSources \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedSourceSelectionIsTransientOneShotAndRegenerateRequiresNewSelection \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDoneAttributionsRequireSafeMetadataPreserveMalformedStreamsAndPersistOnlyProjection \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.historicalSourceAttributionResolveCorrelatesCanonicalLocatorAndReusesTrustedReviewTokens \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.historicalSourceAttributionResolveRejectsMismatchedProjectionAndCleansUpOnSessionChange \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openingRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedChatSourceAttributionSanitizerRejectsIsoControlDocumentNames \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.postPairingMalformedChallengeRetriesWithFreshHelloAndRejectsOldFinalResponse \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.postPairingMalformedFinalResponseClearsAttemptAndBoundsRetry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.postPairingRetryableRuntimeErrorClearsAttemptAndUsesFreshHello \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.delayedPostPairIdentityLoadCannotSendHelloOrAuthenticateAcrossReplacementConnection \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.malformedAuthChallengeTerminatesAttemptAndFreshAcceptedResponseCannotAuthenticate \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedSourceSelectionClearsOnChatSwitchListOmissionRevokeAndDisconnect \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedSourceChatFailureInvalidatesStaleGrantListWithoutPersistingOpaqueIds \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedSourceChatSendDoesNotCrossAReplacedTransportChannel \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedSourceAuthenticationLossClearsSessionCapabilitiesBeforeOperationErrorHandling \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedSourceTerminalReviewAndRevokeErrorsRemoveDeadCapabilities \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.malformedTrustedSourceErrorClearsPendingCapabilityAndAllowsRetry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.staleTrustedSourceListResponseCannotResurrectRevokedGrant \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.revokingTrustedCitationReviewClearsPendingConfirmationCapability \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.malformedCitationResponseReleasesPendingRequestWithoutLeakingOpaqueDetail \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.clientCapabilitiesAdvertiseRuntimeOwnedHistoryMemoryAndAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.clientCapabilitiesDoNotAdvertiseFutureWorkspaceRagSourceProtocols \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectUninstalledChatModelKeepsCurrentSelectionAndDoesNotRequestRuntimePull \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.unsolicitedModelPullResultCannotMutateSelectionOrRefreshCatalog \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatCancelAckRejectsUnknownMetadataBeforeStreamingClear \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDeltaRejectsUnknownMetadataBeforeMessagePublication \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDoneRejectsUnknownMetadataBeforeCompletionSideEffects \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDeltaAppendsReasoningWithoutMixingIntoAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.thinkingDeltaAliasAppendsReasoning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.inlineThinkTagsAreSeparatedFromAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkTagsKeepReasoningCollapsedOutOfAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.activeStreamTerminationClosesTrailingAssistantReasoningState \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkOpeningTagAcrossDeltasDoesNotLeakTagToAnswer \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkClosingTagAcrossDeltasDoesNotLeakTagToReasoning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.incompleteInlineThinkTagPlaceholderIsClearedOnDone \
  -Pkotlin.incremental=false

run check_android_authenticated_read_authority_junit
run check_android_authenticated_read_rollover_authority_junit
run check_android_chat_sessions_bulk_terminal_authority_junit
run check_android_memory_mutation_authority_junit

run swift build --product AetherLink
run swift build --product AetherLinkRelay
run check_relay_binary_source_rate_limit_cli_guard
run check_relay_binary_source_peer_quota_cli_guard
run check_relay_binary_waiting_peer_policy_cli_guard
run swift test --filter 'RelayAllocationTests|RelayIdentityBoundSocketTests|RelaySourceQuotaLimiterTests|RelaySourceRateLimiterTests|RelayWaitingPeerPolicyTests|RelayClientRegistrationAdmissionTests|RelayHandshakeTests|RelayMatcherTests|RelayProbeTests'
run swift test --filter 'RelayIdentityBoundSocketTests/testControlLineReaderUsesAbsoluteDeadlineAndPreserves4096ByteLimit|RelayIdentityBoundSocketTests/testControlLineReaderRecomputesDeadlineAfterEveryPollAndReceiveInterrupt|RelayIdentityBoundSocketTests/testIdleControlTimeoutReclaimsConnectionPermit|RelayIdentityBoundSocketTests/testWaitingPeerDisconnectReclaimsConnectionPermit|RelayIdentityBoundSocketTests/testAcceptedSocketResetDuringResponseDoesNotTerminateServer|RelayIdentityBoundSocketTests/testSinglePeerCloseReclaimsBothBridgePermitsAndActiveRoom|RelayIdentityBoundSocketTests/testExposedBindDisablesProbeUnlessLegacyDiagnosticPolicyIsExplicit|RelayAllocationTests/testRelayConfigurationRejectsInvalidAbuseControlLimits|RelayAllocationTests/testLegacyUnallocatedRelayModeIsLoopbackOnly|RelayAllocationTests/testProbePolicyDefaultsToLoopbackOnlyAndRequiresExplicitExposedOptIn'
run swift test --filter 'RelaySourceRateLimiterTests|RelayIdentityBoundSocketTests/testLoopbackPreflightRateLimitSilentlyClosesWithStableSourceFreeObservability|RelayIdentityBoundSocketTests/testMalformedAllocationControlRecordsConsumeClassifiedSourceBudgets|RelayIdentityBoundSocketTests/testAllocationMutationBucketIsSeparateFromPreflightBucket|RelayIdentityBoundSocketTests/testPairedRenewalSharesAllocationMutationBucket|RelayIdentityBoundSocketTests/testRateLimitedSourceStillUsesPeerAdmissionAndBridgeTraffic'
run swift test --filter 'RelaySourceQuotaLimiterTests|RelayMatcherTests/testSourceWaitingQuotaRejectsOnlyNewWaitersAndAllowsImmediateMatch|RelayMatcherTests/testCrossSourceReplacementRejectionPreservesOriginalWaiter|RelayMatcherTests/testWaitingQuotaReleasesOnInvalidation|RelayMatcherTests/testCounterpartOnlyRegistrationAllowsMatchOrSameSourceReplacement|RelayMatcherTests/testSourceReserveCandidateCannotDischargeAnotherSourcesWaiter|RelayIdentityBoundSocketTests/testSourceConnectionQuotaRejectsExcessWhileActiveBridgeStillForwards|RelayIdentityBoundSocketTests/testSourceWaitingQuotaRejectsOnlyNewWaiterAndAllowsImmediateCounterpart|RelayIdentityBoundSocketTests/testWaitingDisconnectReleasesSourceQuotaBeforeConnectionPermit|RelayIdentityBoundSocketTests/testCounterpartReserveSurvivesActiveBridgeAndRejectsNonmatchingCandidate'
run swift test --filter 'RelayWaitingPeerPolicyTests|RelayMatcherTests/testWaitingDeadlinePersistsAcrossSameRoleReplacement|RelayMatcherTests/testExpiredWaitingRoomCannotMatchLateCounterpart|RelayMatcherTests/testExpiredWaitingRoomCannotBeReplacedOrReportedByProbe|RelayMatcherTests/testWaitingRegistrationAttemptRetainsDeadlineAfterCounterpartMatches|RelayMatcherTests/testAuthenticatedIdentityQuotaIsCrossSourceAndReleasesEveryWaitingPath|RelayIdentityBoundSocketTests/testWaitingTimeoutReleasesSourceAndIdentityCapacityAndAllowsRetry|RelayIdentityBoundSocketTests/testMatchedBridgeCancelsWaitingTimeoutAndContinuesForwarding|RelayIdentityBoundSocketTests/testAuthenticatedIdentityWaitingQuotaRejectsOnlySameIdentity|RelayIdentityBoundSocketTests/testPairedClientIdentityWaitingQuotaRequiresVerifiedClientProof|RelayIdentityBoundSocketTests/testWrongKeyAndRegistrationProofReplayCannotReplaceWaitingRuntime'
run ./gradlew --no-daemon \
  :app:testDebugUnitTest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayQrPairingUnavailableProbeFailsBeforeConnectWhenDeviceCannotReachRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayQrPairingUnsupportedProbeContinuesToRelayConnector \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayProbeResultRejectsMalformedDuplicateAndUnknownFieldsAsUnsupported \
  -Pkotlin.incremental=false
run swift test --filter 'RelayIdentityBoundSocketTests/testUnsignedPreflightReturnsExactClosedResponseAndNoUsableRoute|RelayIdentityBoundSocketTests/testChallengeAllocationAndRuntimeAdmissionSucceeds|RelayIdentityBoundSocketTests/testAllocationProofReplayAndFieldMutationFailClosed|RelayIdentityBoundSocketTests/testWrongKeyAndRegistrationProofReplayCannotReplaceWaitingRuntime|RelayIdentityBoundSocketTests/testConcurrentServerWithSameDurableAllocationStoreThrowsAlreadyOwned|RelayIdentityBoundSocketTests/testSecondRunOnSameServerThrowsAlreadyRunningAndOriginalListenerStillWorks|RelayIdentityBoundSocketTests/testBindFailureReleasesAllocationStoreOwnershipForRetainedServer|RelayAllocationTests/testSchemaV4StorePersistsAuthorizationModeAndConsumptionEnvelope|RelayAllocationTests/testSchemaV3PairedBindingRotatesToPairScopedRoomAndPersistsTombstone|RelayAllocationTests/testSchemaV2MigrationPersistenceFailureFailsClosed|RelayAllocationTests/testStoreReloadsActiveBindingAndRetainsExpiredTombstone|RelayAllocationTests/testRenewalRequiresSameKeyAndGenerationCAS|RelayAllocationTests/testLegacyCorruptAndUnknownStoresFailClosed|RelayAllocationTests/testStrictNonLoopbackRelayRejectsEphemeralAllocationStore|RelayAllocationTests/testStaleBootstrapCreateCannotRecreateConsumedPairClaim|RelayAllocationTests/testRepeatedRegistryCreationReusesPooledLockDescriptor|RelayAllocationTests/testClosingSiblingTransactionLockDoesNotReleaseActiveProcessRecordLock|RelayAllocationTests/testStoreOwnershipCanonicalizesSymlinkedParentAliases|RelayAllocationTests/testDeletedEstablishedDurableStoreFailsClosedForLiveAndRestartedRegistries|RelayAllocationTests/testGroupOrWorldWritableStoreParentFailsClosed|RelayAllocationTests/testValidUnversionedV1StoreIsRevokedIntoEmptyTokenBoundV4Store|RelayAllocationTests/testDanglingDurableStoreSymlinkFailsClosed|RelayAllocationTests/testHardLinkedStoreAliasFailsClosedWithoutDivergingAtomicWrites|RelayAllocationTests/testPostRenameDirectorySyncFailureReconcilesCommittedEnvelopeBeforeSuccess|RelayAllocationTests/testUninitializedMarkerRecoversTokenMatchedDurableStoreAfterInterruptedInitialization|RelayAllocationTests/testEstablishedLockReplacementQuarantinesLiveAndReplacementRegistries|RelayAllocationTests/testCaseVariantStorePathSharesOneOwnerOnCaseInsensitiveVolumes'
run ./script/relay_allocation_store_ownership_smoke.sh
run swift test --filter RelayIdentityAuthorizationTests
run swift test --filter RuntimeIdentityKeyStoreTests
run swift test --filter InitialPairingProofTests
run swift test --filter PairedRelayAllocationAuthorizationTests
run swift test --filter PairedRelayAllocationRuntimeSigningTests
run swift test --filter PairedRelayAllocationClientTests
run swift test --filter PairedRuntimeRouteRefreshTests
run swift test --filter MacRuntimeConnectionManagerTests
run swift test --filter PairScopedRelayRouteStoreTests
run swift test --filter 'RelayIdentityBoundSocketTests/testPairedClaimThenRenewSucceedsAndPersistsPinnedClient|RelayIdentityBoundSocketTests/testPairedRenewalRejectsTokenSubstitutionDowngradeAndAbsentTicketBeforeChallenge|RelayIdentityBoundSocketTests/testPairedProofReplayAndConcurrentGenerationRaceFailCAS|RelayIdentityBoundSocketTests/testPairedProofRejectsMissingWrongAndSwappedRoleSignatures|RelayIdentityBoundSocketTests/testPairedChallengeMutationAndExpiryFailWithoutCommit|RelayIdentityBoundSocketTests/testPairedClaimCanRecoverExpiredPersistedTombstone'
run swift test --filter 'RelayIdentityBoundSocketTests/testPairedClaimChallengesClientAndAdmitsValidPinnedProof|RelayIdentityBoundSocketTests/testRejectedClientProofsCannotDisplaceVerifiedWaitingRuntime|RelayIdentityBoundSocketTests/testActiveRoomRejectsSecondPairUntilBridgeClosesThenReconnects|RelayIdentityBoundSocketTests/testPairedRenewalInvalidatesStaleWaitingGeneration|RelayIdentityBoundSocketTests/testTwoPairScopedRoomsBridgeConcurrentlyWithoutCrossTalk|RelayClientRegistrationAdmissionTests'
run swift test --filter 'LocalRuntimeMessageRouterTests/testAuthenticatedRouteRefreshRejectsNilTransportBindingBeforeRefresherDispatch|LocalRuntimeMessageRouterTests/testAuthenticatedRouteRefreshRejectsMismatchedLiveBindingBeforeRefresherDispatch|LocalRuntimeMessageRouterTests/testAuthenticatedRouteRefreshForwardsExactRelayChallengeAndAcceptsCanonicalClientProof|LocalRuntimeMessageRouterTests/testRelayAllocationAuthorizationWrongProofFailsClosedAndIsOneShot|LocalRuntimeMessageRouterTests/testRelayAllocationAuthorizationTimesOutAndResumesRouteRefresh|LocalRuntimeMessageRouterTests/testRelayAllocationAuthorizationDisconnectCancelsPendingContinuation|LocalRuntimeMessageRouterTests/testRelayAllocationAuthorizationTrustReplacementCancelsPendingContinuation|LocalRuntimeMessageRouterTests/testRelayAllocationAuthorizationBindingMutationCancelsPendingContinuation|LocalRuntimeMessageRouterTests/testConcurrentRouteRefreshWithSameConnectionAndRequestAdmitsSingleAuthorization'
run swift test --filter 'LocalRuntimeMessageRouterTests/testTCPRelayServiceRouteAllocator|LocalRuntimeMessageRouterTests/testPairingRequestBindingChangeBeforeTrustLeavesTrustedStoreEmpty|LocalRuntimeMessageRouterTests/testPairingRequestRejectsMutatedProofWithoutConsumingSession|LocalRuntimeMessageRouterTests/testPairingResultSignerFailureReleasesReservationBeforeTrust'
run swift test --filter TransportTests
run swift test --filter 'RuntimeAdvertisementMetadataTests/testRuntimeAdvertisementMetadataPublishesOnlyRouteTokenIdentityHint|RuntimeAdvertisementMetadataTests/testRejectsWhitespaceMutatedRouteTokenInsteadOfNormalizing|RuntimeAdvertisementMetadataTests/testRejectsRequestedRouteTokenHintsFromDiscoveryTxtMetadata|LocalRuntimeMessageRouterTests/testCompanionAppModelAdvertisesRouteTokenWithoutStableIdentityTXTMetadata'
run swift test --filter 'LocalRuntimeMessageRouterTests/testRuntimeHealthIncludesAggregateProviderStatuses|LocalRuntimeMessageRouterTests/testRuntimeHealthIncludesModelResidencyLastUnloadFailureWithoutRawErrorMessage'
run swift test --filter AetherLinkLocalizationTests
run swift test --filter 'AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactRouteSecrets|AetherLinkLocalizationTests/testRouteDiagnosticDisclosureRedactsSensitiveDetails'
run swift test --filter 'AetherLinkLocalizationTests/testModelCapabilityDisplayProjectsOnlyKnownCapabilitiesAcrossSupportedLanguages|AetherLinkLocalizationTests/testModelCapabilityDisplayOmitsInvalidContextAndRawUnknownCapabilities|AetherLinkLocalizationTests/testModelRowAccessibilityLabelIncludesKnownCapabilitiesAcrossSupportedLanguages|AetherLinkLocalizationTests/testModelRowAccessibilityLabelUsesModelContext|AetherLinkLocalizationTests/testVisibleModelGroupsShowOnlyInstalledLocalModels'
run swift test --filter AetherLinkRenderSmokeTests
run swift test --filter 'AetherLinkRenderSmokeTests/testModelIdleUnloadPolicyPickerRendersAcrossLanguagesAndAppearances|AetherLinkRenderSmokeTests/testCompanionAppModelAppliesPersistedPolicyToInjectedAggregate'
run swift test --filter 'AetherLinkLocalizationTests/testRuntimeMemoryInspectorCopyLocalizesAcrossSupportedLanguages|AetherLinkRenderSmokeTests/testRuntimeMemoryInspectorRendersAcrossLanguagesAndAppearances'
	run swift test --filter RuntimeDocumentIndexStoreTests
	run swift test --filter SQLiteRuntimeDocumentIndexStoreTests
		run swift test --filter RuntimeDocumentSourceGovernanceTests
		run swift test --filter RuntimeDocumentSourceManagerTests
		run swift test --filter RuntimeDocumentCitationGovernanceTests
			run swift test --filter SQLiteRuntimeDocumentSemanticEmbeddingCacheTests
			run swift test --filter 'LocalRuntimeMessageRouterTests/testApprovedRuntimeSharedDocumentsAuditTrustedReadersAndRevokeAcrossDevices|LocalRuntimeMessageRouterTests/testDocumentReadsFailClosedWhenSourceAuditWriteFails'
			run swift test --filter 'LocalRuntimeMessageRouterTests/testSemanticRetrieval'
			run swift test --filter 'LocalRuntimeMessageRouterTests/testCitation'
			run swift test --filter 'LocalRuntimeMessageRouterTests/testChatSendConsumesCurrentDeviceGrantAsBackendOnlyTrustedSourceContext|SQLiteRuntimeChatEventStoreTests/testSQLiteStoreResolvesOnlyOwnerScopedBoundCanonicalAssistantAttribution|LocalRuntimeMessageRouterTests/testChatSendTrustedSourceContextFailsClosedWhenAuditPersistenceFails|LocalRuntimeMessageRouterTests/testChatSendTrustedSourceContextRespectsModelWindowWithoutPersistingContext|LocalRuntimeMessageRouterTests/testChatSendRejectsMalformedOrWrongDeviceTrustedSourceGrantsBeforeBackend'
			run swift test --filter 'LocalRuntimeMessageRouterTests/testChatCancelPersistenceFailureReturnsStoreErrorsWithoutSuccessOrDuplicateTerminal|LocalRuntimeMessageRouterTests/testConcurrentStopAndCancelClaimsExactlyOneStoredAndWireTerminal|LocalRuntimeMessageRouterTests/testDelayedCancelCapturedBeforeStopCannotClaimSecondTerminal|LocalRuntimeMessageRouterTests/testConnectionCloseNotFoundDoesNotSuppressConcurrentStopTerminal|LocalRuntimeMessageRouterTests/testDevelopmentPathProjectsStoredSourceAttributionsWithoutHelloCapability'
			run swift test --filter 'LocalRuntimeMessageRouterTests/testRetrievalQueryReturnsBoundedLexicalResultsWithoutFullChunkOrFutureMetadata|LocalRuntimeMessageRouterTests/testRetrievalQueryZeroSnippetLimitStillReturnsSchemaValidNonemptySnippet|LocalRuntimeMessageRouterTests/testRetrievalMatchKindSerializationRequiresExplicitNegotiatedOptIn'
run swift test --filter 'RuntimeDocumentIndexStoreTests/testSourceAnchorIDIsStableForSameChunkAndRotatesWhenContentChanges|SQLiteRuntimeDocumentIndexStoreTests/testSQLiteSourceAnchorIDIsStableAfterReopenAndRotatesWhenContentChanges'
run swift test --filter 'RuntimeDocumentIndexStoreTests/testSourceAnchorIDIsIndependentOfQueryWindowAndSnippetBounds|SQLiteRuntimeDocumentIndexStoreTests/testSQLiteSourceAnchorIDIsIndependentOfQueryWindowAndSnippetBoundsAfterReopen'
run swift test --filter 'RuntimeDocumentIndexStoreTests/testSourceAnchorResolverRejectsWhitespaceMutatedAnchorIDs|SQLiteRuntimeDocumentIndexStoreTests/testSQLiteSourceAnchorResolverRejectsWhitespaceMutatedAnchorIDsAfterReopen'
run swift test --filter 'RuntimeDocumentIndexStoreTests/testSourceAnchorResolverReturnsRedactedEnvelopeWithoutTextOrFutureMetadata|SQLiteRuntimeDocumentIndexStoreTests/testSQLiteSourceAnchorResolverMatchesRuntimeStoreAfterReopenWithoutTextOrFutureMetadata|LocalRuntimeMessageRouterTests/testChatSendRejectsRawSourceAnchorInsteadOfTrustedSourceGrantIDs'
run swift test --filter 'RuntimeDocumentIndexStoreTests/testSourceAnchorResolverInvalidatesAnchorsAfterReplaceAndDelete|SQLiteRuntimeDocumentIndexStoreTests/testSQLiteSourceAnchorResolverInvalidatesAnchorsAfterReplaceDeleteAndReopen|LocalRuntimeMessageRouterTests/testRetrievalQueryRejectsUnknownMetadataBeforeStoreDispatch'
run swift test --filter 'RuntimeDocumentIndexStoreTests/testSourceAnchorResolverInvalidatesAnchorsAfterFilteredMaintenanceDeletes|SQLiteRuntimeDocumentIndexStoreTests/testSQLiteSourceAnchorResolverInvalidatesAnchorsAfterFilteredMaintenanceDeletesAndReopen'
run swift test --filter 'RuntimeDocumentIndexStoreTests/testRejectsControlCharacterDisplayNamesBeforeStorageAndLookup|SQLiteRuntimeDocumentIndexStoreTests/testSQLiteStoreRejectsControlCharacterDisplayNamesAfterReopen'
run swift test --filter 'RuntimeDocumentIndexStoreTests/testRejectsControlCharacterRequestedDocumentIDsBeforeStorageAndLookup|SQLiteRuntimeDocumentIndexStoreTests/testSQLiteRejectsControlCharacterRequestedDocumentIDsAfterReopen'
run swift test --filter DocumentIngestorTests
run swift test --filter DocumentIngestorTests/testRejectsOversizedDirectExtractedDocumentTextBeforeChunking
run swift test --filter DocumentIngestorTests/testCanonicalizesDirectExtractedDocumentSourceLabelsBeforeChunkingAndSummary
run swift test --filter DocumentChunkerTests
run swift test --filter DocumentTextExtractorTests/testCanonicalizesMimeTypeBeforeDispatchingExtensionlessAttachments
run swift test --filter DocumentTextExtractorTests/testIgnoresPathShapedArchiveEntriesBeforeExtraction
run swift test --filter DocumentTextExtractorTests/testAppliesStoreOwnedResourcePolicyCeilingsBeforeExtraction
run swift test --filter DocumentTextExtractorTests/testRejectsNonPositiveResourcePolicyBeforeExtraction
run swift test --filter DocumentTextExtractorTests/testRejectsArchiveEntryFanoutWhenResourcePolicyLimitIsExceeded
run swift test --filter DocumentTextExtractorTests/testRejectsArchiveExtractionWhenResourcePolicyLimitIsExceeded
	run swift test --filter DocumentTextExtractorTests/testRejectsExtractedTextWhenResourcePolicyLimitIsExceeded
	run swift test --filter DocumentTextExtractorTests
	run swift test --filter ProtocolCodecTests/testProtocolEnvelopeDecodeRejectsMalformedRequiredFields
	run swift test --filter ProtocolCodecTests/testProtocolEnvelopeDecodeRejectsUnknownTopLevelFields
		run swift test --filter ProtocolCodecTests/testModelInfoCodablePreservesProviderAndEmbeddingMetadata
			run swift test --filter 'ProtocolCodecTests/testRelaySessionNonceGenerationIsCanonicalAndUnique|ProtocolCodecTests/testRelayEphemeralKeysMatchP256ScalarVectorsAndValidateOnCurve|ProtocolCodecTests/testRelaySessionCryptoMatchesBindingHkdfAndConfirmationVectors|ProtocolCodecTests/testRelaySessionCryptoBindsRouteNonceIntoBindingAndTrafficKeys|ProtocolCodecTests/testRelayKeyConfirmationRequiresExactRoleBindingProofAndLineFeed|ProtocolCodecTests/testRelayFrameCipherMatchesDirectionalFrameZeroVectors|ProtocolCodecTests/testRelayFrameCipherRoundTripsAndRejectsWrongDirection|ProtocolCodecTests/testRelayFrameCipherDoesNotAdvanceReceiveCounterAfterAuthenticationFailure|ProtocolCodecTests/testRelayFrameCipherRotatesAtEpochBoundaryUsingFixedVectors|ProtocolCodecTests/testRelayFrameCipherRejectsCounterAtInt64MaxBeforeCryptography'
			run swift test --filter 'RelayPeerClientTests/testStrictRelayPeerClientCompletesCrypto2HandshakeAndEncryptsFrames|RelayPeerClientTests/testStrictRelayPeerClientRejectsPlainRegisteredWithoutV1Fallback|RelayPeerClientTests/testStrictRelayPeerClientRejectsOffCurvePeerKey|RelayPeerClientTests/testStrictRelayPeerClientFailsClosedOnWrongClientConfirmation|RelayPeerClientTests/testStrictRelayPeerClientClosesImmediatelyOnFrameAuthenticationFailure'
			run swift test --filter 'RelayHandshakeTests/testParsesExactCryptoV2Handshake|RelayHandshakeTests/testRejectsAnyCryptoVersionOtherThanTwo|RelayHandshakeTests/testRejectsNonCanonicalEphemeralKeyShapeWithoutCheckingCurve|RelayHandshakeTests/testBuildsExactCryptoV2ControlLines|RelayMatcherTests/testMatchedRegistrationsPreserveCryptoV2Metadata|RelayServerSocketTests/testStrictServerRejectsLegacyAndIncompleteCryptoRegistrations|RelayServerSocketTests/testLegacyServerRejectsCryptoV2Registration|RelayServerSocketTests/testLegacyServerConnectsTwoPeersWithLegacyReadyLine|RelayServerSocketTests/testStrictServerSendsExactRegisteredAndPeerReadyFields|RelayServerSocketTests/testStrictServerForwardsConfirmationAndFrameBytesOpaquely'
		run swift test --filter 'RuntimeIdentityKeyStoreTests/testFileStoreSignsTransportBoundV2AuthChallengeWithoutV1Downgrade|RuntimeIdentityKeyStoreTests/testKeychainStoreSignsTransportBoundV2AuthChallenge|RuntimeIdentityKeyStoreTests/testRuntimeIdentitySignersRejectNoncanonicalTransportBindings'
		run swift test --filter 'LocalRuntimeMessageRouterTests/testTransportBoundHelloAndAuthResponseUseV2SignaturesAndDispatchCommands|LocalRuntimeMessageRouterTests/testTransportBoundHelloRejectsMissingMalformedAndMismatchedBindingsBeforeCommands|LocalRuntimeMessageRouterTests/testTransportBoundAuthRejectsMissingBindingAndV1SignatureBeforeCommands|LocalRuntimeMessageRouterTests/testTransportBoundAuthRejectsReplayedOldBindingAfterSinkBindingChanges|LocalRuntimeMessageRouterTests/testUnboundSinkRejectsUnexpectedTransportBindingBeforeChallengeAndCommands'
		run swift test --filter 'OllamaBackendTests/testListModelsUsesShowCapabilitiesToSeparateEmbeddingModels|OllamaBackendTests/testEmbedPostsBatchWithoutTruncationAndReturnsVectors|OllamaBackendTests/testEmbedRejectsEmptyOrInconsistentVectors|OllamaBackendTests/testEmbedRejectsWrongVectorCount|OllamaBackendTests/testUnloadModelPostsEmptyChatWithKeepAliveZero|OllamaBackendTests/testUnloadModelHTTPStatusReturnsStructuredError|LMStudioBackendTests/testListModelsParsesNativeLocalLLMAndEmbeddingModelsSeparately|LMStudioBackendTests/testListModelsFallsBackToOpenAICompatibleModels|LMStudioBackendTests/testEmbedPostsBatchAndRestoresIndexOrder|LMStudioBackendTests/testEmbedRejectsDuplicateMissingOrOutOfRangeIndexes|LMStudioBackendTests/testEmbedRejectsEmptyOrInconsistentVectors|LMStudioBackendTests/testUnloadModelPostsLoadedInstanceID|LMStudioBackendTests/testUnloadModelHTTPStatusReturnsStructuredError|AggregatingLlmBackendResidencyTests/testSwitchingModelsUnloadsPreviousInactiveModel|AggregatingLlmBackendResidencyTests/testRepeatedSameModelDoesNotUnloadBetweenChats|AggregatingLlmBackendResidencyTests/testIdlePolicyUnloadsActiveModelAfterDelay|AggregatingLlmBackendResidencyTests/testDoneEventClearsInFlightResidencyBeforeClientObservesCompletion|AggregatingLlmBackendResidencyTests/testManualUnloadClearsActiveResidentModelAndEmitsManualEvent|AggregatingLlmBackendResidencyTests/testManualUnloadFailureKeepsStructuredManualFailureReason|AggregatingLlmBackendResidencyTests/testManualUnloadSkipsWhileGenerationIsInFlight|AggregatingLlmBackendResidencyTests/testCancelBeforeAsyncRouteResolutionPreventsProviderChatDispatch|AggregatingLlmBackendResidencyTests/testRejectedDuplicateGenerationCannotRemoveOriginalReservation|AggregatingLlmBackendResidencyTests/testUnloadFailureEmitsProviderSpecificFailureEventWithoutBreakingNextChat|AggregatingLlmBackendResidencyTests/testInstalledEmbeddingModelIsNotRoutedAsChat|AggregatingLlmBackendResidencyTests/testInstalledCloudChatModelIsNotRoutedAsChat|AggregatingLlmBackendResidencyTests/testEmbeddingRejectsChatModelAndDoesNotRoute|AggregatingLlmBackendResidencyTests/testEmbeddingRejectsProviderManagedModelAndDoesNotRoute|AggregatingLlmBackendResidencyTests/testQualifiedInstalledEmbeddingRoutesToItsProviderModelID|AggregatingLlmBackendResidencyTests/testEmbeddingDoesNotEnterGenerationCancellationRegistry|AggregatingLlmBackendResidencyTests/testUnknownUnqualifiedModelDoesNotFallbackToOllama|AggregatingLlmBackendResidencyTests/testQualifiedModelMustBeReportedByThatProvider|AggregatingLlmBackendResidencyTests/testDuplicateProviderBackendsKeepFirstProviderInsteadOfCrashing|RuntimeSemanticChatSessionSearchTests'
		run swift test --filter 'ProtocolCodecTests/testRelayPlaintextFrameCeilingReservesAuthenticationTag|OllamaBackendTests/testModelInfoCatalogPublicationLimitsAcceptExactBoundariesAndRejectLimitPlusOne|OllamaBackendTests/testCatalogStreamingReadAcceptsExactByteLimitAndRejectsLimitPlusOne|OllamaBackendTests/testCatalogStreamingReadRejectsOversizedPositiveContentLength|OllamaBackendTests/testShowStreamingReadAcceptsExactByteLimitAndExcludesOnlyLimitPlusOneDetail|OllamaBackendTests/testListModelsPropagatesCancellationDuringShowFanout|OllamaBackendTests/testListModelsAccepts256RowsAndRejects257RowsOrUniqueDetailFanout|OllamaBackendTests/testListModelsKeepsByteDistinctUnicodeIdentitiesAcrossCatalogs|OllamaBackendTests/testListModelsPreservesByteDistinctUnicodeCapabilities|OllamaBackendTests/testUnloadModelDoesNotMatchByteDistinctUnicodeRunningIdentity|OllamaBackendTests/testUnloadModelRejectsOversizedRunningCatalogBeforePosting|OllamaBackendTests/testHealthCheckRejectsMalformedTagsCatalog|OllamaBackendTests/testListModelsRejectsDuplicateAndEscapeEquivalentKeysInTagsAndRunningCatalogs|OllamaBackendTests/testListModelsRejectsDuplicateExactAndCanonicalModelIdentities|OllamaBackendTests/testListModelsRejectsConflictingNameAndModelIdentityAliases|OllamaBackendTests/testListModelsAcceptsContextWindowBoundariesAndMatchingAliases|OllamaBackendTests/testListModelsOmitsInvalidContextMetadataAndPreservesValidCapabilities|OllamaBackendTests/testListModelsExcludesShowDetailsWithInvalidCapabilities|OllamaBackendTests/testListModelsOmitsConflictingContextMetadataAndPreservesValidCapabilities|OllamaBackendTests/testListModelsOmitsShowDetailsWithDuplicateOrEscapeEquivalentKeys|LMStudioBackendTests/testNativeCatalogStreamingReadAcceptsExactByteLimitAndRejectsLimitPlusOneWithoutFallback|LMStudioBackendTests/testFallbackCatalogStreamingReadAcceptsExactByteLimitAndRejectsLimitPlusOne|LMStudioBackendTests/testNativeCatalogRejectsOversizedPositiveContentLengthWithoutFallback|LMStudioBackendTests/testNativeCatalogAccepts256RowsAndRejects257Rows|LMStudioBackendTests/testNativeCatalogRejectsInvalidPublicationMetadataWithoutFallback|LMStudioBackendTests/testUnloadModelRejectsOversizedNativeCatalogBeforePosting|LMStudioBackendTests/testUnloadModelAcceptsMaximumLoadedInstanceFanout|LMStudioBackendTests/testUnloadModelRejectsInvalidLoadedInstanceFanoutBeforePosting|LMStudioBackendTests/testUnloadModelRejectsInvalidLoadedInstanceMetadataDuringPolling|LMStudioBackendTests/testListModelsFallsBackToOpenAICompatibleModels|LMStudioBackendTests/testListModelsFallsBackForExplicitNativeEndpointIncompatibility|LMStudioBackendTests/testListModelsDoesNotFallbackForNativeAuthClientOrServerFailures|LMStudioBackendTests/testListModelsDoesNotFallbackForNativeTransportFailure|LMStudioBackendTests/testListModelsRejectsDuplicateAndEscapeEquivalentNativeObjectKeysWithoutFallback|LMStudioBackendTests/testListModelsRejectsDuplicateAndEscapeEquivalentFallbackObjectKeys|LMStudioBackendTests/testListModelsRejectsExactAndCanonicalDuplicateModelIdentities|LMStudioBackendTests/testListModelsRejectsConflictingNativeModelIdentityAliases|LMStudioBackendTests/testListModelsAcceptsExactIntegralContextAliasesAtSharedCeiling|LMStudioBackendTests/testListModelsAcceptsMatchingNativeContextAliases|LMStudioBackendTests/testListModelsRejectsInvalidNativeContextWindowValuesWithoutFallback|LMStudioBackendTests/testListModelsRejectsInvalidFallbackContextWindowValues|LMStudioBackendTests/testListModelsRejectsConflictingContextWindowAliases|LMStudioBackendTests/testChatStreamsFinalNativeJSONLineWithoutTrailingBlankSeparator|LMStudioBackendTests/testChatDoesNotFallbackAfterMalformedNativeStreamEmitsContent|LMStudioBackendTests/testChatRejectsNativeStreamEOFWithoutTerminalAndDoesNotFallback|AggregatingLlmBackendResidencyTests/testListModelsPropagatesCancellationInsteadOfReturningPartialCatalog|LocalRuntimeMessageRouterTests/testModelsListAcceptsCatalogAtPublicationLimits|LocalRuntimeMessageRouterTests/testModelsListRejectsValidCartesianLimitsAboveRelayFrameCeiling|LocalRuntimeMessageRouterTests/testModelsListPublishesInt64MaximumSizeWithoutPrecisionLoss|LocalRuntimeMessageRouterTests/testModelsListRejectsCatalogAbovePublicationLimit|LocalRuntimeMessageRouterTests/testModelsListRejectsUntrustedMetadataAtPublicationBoundary|LocalRuntimeMessageRouterTests/testModelsListRejectsContextWindowMetadataOutsideRuntimeCeiling|LocalRuntimeMessageRouterTests/testModelsListSingleFlightCoalescesBoundedWaitersAndDoesNotCacheSuccess|LocalRuntimeMessageRouterTests/testModelsListSingleFlightCancellationKeepsSharedWorkForRemainingWaiter|LocalRuntimeMessageRouterTests/testModelsListSingleFlightCancelledNonLastWaitersReturnBeforeProviderCompletion|LocalRuntimeMessageRouterTests/testModelsListSingleFlightLastWaiterCancellationStopsProviderWork|LocalRuntimeMessageRouterTests/testModelsListSingleFlightWaitsForCancelledProviderToRetireBeforeReplacement|LocalRuntimeMessageRouterTests/testModelsListSingleFlightDoesNotCacheFailure|LocalRuntimeMessageRouterTests/testModelsListSingleFlightSuppressesPublicationAfterReauthentication|LocalRuntimeMessageRouterTests/testChatSendIgnoresContextWindowMetadataAboveRuntimeCeiling'
		run swift test --filter 'AggregatingLlmBackendResidencyTests/testQualifiedModelMatchesOnlyExactProviderModelID|AggregatingLlmBackendResidencyTests/testChatRejectsProviderModelIDWithReservedQualifiedPrefix|AggregatingLlmBackendResidencyTests/testEmbeddingRejectsProviderModelIDWithReservedQualifiedPrefix'
		run swift test --filter 'AggregatingLlmBackendResidencyTests/testEmbeddingResidencyUnloadsPreviousChatModel|SQLiteRuntimeChatEventStoreTests/testSQLiteSemanticSearchSourcesReadOwnerScopedSessionsAndMessagesInOneSnapshot'
			run swift test --filter 'RuntimeModelIdleUnloadPolicyTests|AggregatingLlmBackendResidencyTests/testUpdatingIdlePolicyUnloadsModelWhenNewDelayAlreadyElapsed|AggregatingLlmBackendResidencyTests/testUpdatingIdlePolicyWhileGenerationIsInFlightDefersUnloadUntilCompletion|AggregatingLlmBackendResidencyTests/testPendingIdleUnloadBlocksSameModelChatUntilProviderUnloadCompletes|AggregatingLlmBackendResidencyTests/testCancelledChatWaitingForSameModelUnloadDoesNotReserveOrDispatch|AggregatingLlmBackendResidencyTests/testCancelledChatWaitingForModelSwitchUnloadDoesNotReserveOrDispatch|AggregatingLlmBackendResidencyTests/testCancelledEmbeddingWaitingForSameModelUnloadDoesNotDispatch|AggregatingLlmBackendResidencyTests/testExtendingIdlePolicyInvalidatesEarlierTimer'
			run swift test --filter 'OllamaBackendTests/testModelUnloadResultOutcomesPreserveBooleanGuard|OllamaBackendTests/testUnloadModelReturnsAlreadyAbsentWithoutPosting|OllamaBackendTests/testUnloadModelUsesCanonicalRunningTarget|OllamaBackendTests/testUnloadModelRejectsDuplicateRunningStateKeysAtInitialLookup|OllamaBackendTests/testUnloadModelRejectsDuplicateRunningStateKeysDuringPolling|OllamaBackendTests/testUnloadModelRejectsMalformedAndFalseAcknowledgements|OllamaBackendTests/testUnloadModelRejectsPersistentProviderResidencyAfterBoundedPolling|OllamaBackendTests/testUnloadModelPollingPropagatesCancellation|OllamaBackendTests/testUnloadConfirmationFailureBackendErrorIsSanitized|LMStudioBackendTests/testUnloadModelReturnsAlreadyAbsentForMissingModelWithoutRawIDFallback|LMStudioBackendTests/testUnloadModelReturnsAlreadyAbsentWhenExactModelHasNoInstances|LMStudioBackendTests/testUnloadModelRejectsMissingNullOrDuplicateResidencyAtInitialLookup|LMStudioBackendTests/testUnloadModelRejectsMissingNullOrDuplicateResidencyDuringPolling|LMStudioBackendTests/testUnloadModelResolvesExactKeyOnly|LMStudioBackendTests/testUnloadModelReturnsUnsupportedWhenNativeAPIRequiresFallback|LMStudioBackendTests/testUnloadModelRejectsMalformedAndMismatchedInstanceAcknowledgements|LMStudioBackendTests/testUnloadModelRejectsPartialMultipleInstanceAcknowledgement|LMStudioBackendTests/testUnloadModelRejectsPersistentProviderResidencyAfterBoundedPolling|LMStudioBackendTests/testUnloadModelPollingPropagatesCancellation|LMStudioBackendTests/testUnloadConfirmationFailureBackendErrorIsSanitized'
			run swift test --filter 'AggregatingLlmBackendResidencyTests/testManualUnloadKeepsActiveModelVisibleWhileProviderConfirmationIsPending|AggregatingLlmBackendResidencyTests/testManualUnloadFailureKeepsStructuredManualFailureReason|AggregatingLlmBackendResidencyTests/testNonthrowingUnsupportedUnloadIsFailureAndKeepsManualResidencyActive|AggregatingLlmBackendResidencyTests/testMismatchedUnloadConfirmationIdentityIsFailureAndKeepsManualResidencyActive|AggregatingLlmBackendResidencyTests/testIdleUnloadFailureKeepsPossiblyResidentModelActive|AggregatingLlmBackendResidencyTests/testUnloadFailureEmitsProviderSpecificFailureEventWithoutBreakingNextChat'
			run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesResidencyInFlightTransitionsWithoutManualRefresh|LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsRapidIdleUnloadPolicyIntentWhileUpdateIsPending'
			run swift test --filter 'AetherLinkLocalizationTests/testModelResidencyUnloadConfirmationStatesUseSelectedLanguage|AetherLinkRenderSmokeTests/testStatusModelResidencyStatesRenderAtCompactDetailSizeAcrossLanguagesAndAppearances'
		run swift test --filter 'LMStudioBackendTests/testChatWithImageAttachmentUsesNativeImageInput|LMStudioBackendTests/testChatWithImageAttachmentFallsBackToOpenAICompatibleVisionContentWhenNativeRejects'
		run swift test --filter 'OllamaBackendTests/testChatStreamsOllamaLineDelimitedJSON|OllamaBackendTests/testChatStreamsServerSentEventLines|LMStudioBackendTests/testChatStreamsNativeServerSentEvents|LMStudioBackendTests/testChatFallsBackToOpenAICompatibleStreamingWhenNativeChatShapeFails'
	run swift test --filter 'RuntimeIdentityKeyStoreTests/testFileStoreLoadOrCreatePersistsRuntimeIdentity|RuntimeIdentityKeyStoreTests/testFileStoreCorrectsBroadPermissionsWithoutRotatingIdentity|RuntimeIdentityKeyStoreTests/testFileStoreSignsVerifiableAuthChallenge'
run swift test --filter TrustedDeviceStoreTests
run swift test --filter RuntimeModelPullApproval
run swift test --filter CompanionModelPullApprovalTests
run swift test --filter RuntimePermissionPolicyRegistryTests
run swift test --filter RuntimeHostApprovalCoordinatorTests
	run swift test --filter 'RuntimeHostApprovalCoordinatorTests/testEscapedReservationAfterPreCommitAuthorizationFailureCannotReserve|RuntimeHostApprovalCoordinatorTests/testWrongReceiptWaitsForConcurrentReservationCommitBeforeFailClosedDecision|RuntimeHostApprovalCoordinatorTests/testPublicationDelayCrossingEitherDeadlineSuppressesResult|RuntimeHostApprovalCoordinatorTests/testReservationSuppressionUsesReservationTimestampAfterWallRollback|RuntimeHostApprovalCoordinatorTests/testExpiredAdapterErrorWithoutTerminalizationEntersRecoveryMode|RuntimeHostApprovalCoordinatorTests/testUnprovenTerminalExpiredErrorEntersRecoveryMode|RuntimeHostApprovalCoordinatorTests/testAuthorityFailureCrossingExpiryMapsExpiredTerminalizationToReviewNotFound|RuntimeHostApprovalCoordinatorTests/testInMemoryPersistenceMirrorsSQLiteTerminalTransitionMatrix'
run swift test --filter 'RuntimePromptSkillRegistryTests|RuntimeResearchNotebookStoreTests|SQLiteRuntimeResearchNotebookStoreTests'
run swift test --filter 'LocalRuntimeMessageRouterTests/(testChatTitle|testAutomaticChatTitle|testAutomaticAndExplicitChatTitle|testConcurrentExplicitChatTitle)'
run swift test --filter 'LocalRuntimeMessageRouterTests/testResearchBriefCreateAcceptsEightUniqueGrantsAndStreamsUnderOriginalRequest|LocalRuntimeMessageRouterTests/testResearchBriefCreateFailsClosedWhenPinnedPromptSkillIsUnavailable|LocalRuntimeMessageRouterTests/testResearchNotebookFollowUpUsesStoredHistoricalPromptSkillRevision|LocalRuntimeMessageRouterTests/testResearchNotebookFollowUpFailsBeforeSourceConsumptionWhenStoredPromptRevisionIsUnavailable|LocalRuntimeMessageRouterTests/testResearchNotebookFollowUpCommitRejectsEveryNotebookStateDrift'
run swift test --filter 'LocalRuntimeMessageRouterTests/testModelsPullHostApprovalReservesAuditBeforeSingleProviderDispatch|LocalRuntimeMessageRouterTests/testModelsPullReviewProjectsTrustedDeviceNameWithoutBidiOrInvisibleSpoofingBeforeDispatch|LocalRuntimeMessageRouterTests/testModelsPullHostApprovalTerminalAuditFailureSendsNoWireResult|LocalRuntimeMessageRouterTests/testModelsPullHostApprovalRejectsRevokedTrustBeforeProviderDispatch|LocalRuntimeMessageRouterTests/testModelsPullMissingPermissionPolicyFailsClosedBeforeAuditOrDispatch'
run swift test --filter AetherLinkLocalizationTests/testModelPullApprovalCopyLocalizesAcrossSupportedLanguages
run swift test --filter AetherLinkLocalizationTests/testModelPullApprovalRequiresExactExplicitConfirmation
run swift test --filter AetherLinkLocalizationTests/testModelPullRequesterUsesHostOwnedBidiIsolationAcrossSupportedLanguages
run swift test --filter AetherLinkRenderSmokeTests/testModelPullApprovalPanelRendersPendingReviewAcrossLanguagesAndAppearances
run swift test --filter 'LocalRuntimeMessageRouterTests/testTrustedHelloAndAuthResponseAuthenticatesConnection|LocalRuntimeMessageRouterTests/testHelloRejectsUnknownPayloadMetadataBeforeChallengeCreation|LocalRuntimeMessageRouterTests/testAuthResponseRejectsUnknownPayloadMetadataBeforeAuthentication|LocalRuntimeMessageRouterTests/testResponseOnlyMessageTypesReturnDirectionProtocolError|LocalRuntimeMessageRouterTests/testTrustedHelloIncludesVerifiableRuntimeProofWhenSignerIsAvailable|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsRawNonceSignature|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsReplayedNonceAfterAuthentication|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsSupersededChallengeNonce|LocalRuntimeMessageRouterTests/testUnauthenticatedRuntimeCommandsRejectBeforeProtocolPayloadHandling|LocalRuntimeMessageRouterTests/testPairingRequestStoresTrustedDeviceAndReturnsAccepted|LocalRuntimeMessageRouterTests/testPairingRequestRejectsUnknownPayloadMetadataBeforeTrusting|LocalRuntimeMessageRouterTests/testPairingRequestRejectsBlankAllowedFieldsBeforeTrusting|LocalRuntimeMessageRouterTests/testPairingRequestRejectsWhitespaceMutatedDeviceIdentityBeforeTrusting|LocalRuntimeMessageRouterTests/testConnectionDidCloseClearsAuthenticatedSession|LocalRuntimeMessageRouterTests/testRemovedTrustedDeviceCannotContinueUsingAuthenticatedConnection|LocalRuntimeMessageRouterTests/testRuntimeHealthRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testModelsListRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsUnknownPayloadMetadataBeforeRuntimeProviderDispatch|LocalRuntimeMessageRouterTests/testModelsPullRequiresHostApprovalWithoutBackendDispatch|LocalRuntimeMessageRouterTests/testModelsPullApprovalBarrierPreventsBackendErrorAndURLExposure|LocalRuntimeMessageRouterTests/testModelsPullRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testModelsPullRejectsInvalidAllowedPayloadTypesBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatCancelRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendAppendsDocumentAttachmentTextAndPreservesImageAttachment|LocalRuntimeMessageRouterTests/testChatSendExtractsMimeOnlyStructuredTextDocumentAttachment|LocalRuntimeMessageRouterTests/testChatSendRejectsTopLevelPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendRejectsInvalidAllowedPayloadTypesBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatTitleRequestRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatTitleRequestRejectsInvalidAllowedLocaleTypeBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendRejectsMessageSourceMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendRejectsAttachmentSourceMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendImageAttachmentRequiresVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendAllowsLMStudioImageAttachmentsForVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendUnsupportedDocumentAttachmentReturnsStructuredError|LocalRuntimeMessageRouterTests/testChatSendRoutesQualifiedLMStudioModelThroughAggregateBackend'
run swift test --filter 'LocalRuntimeMessageRouterTests/testIndexDocumentsListReturnsBoundedCatalogWithoutContentOrFutureMetadata|LocalRuntimeMessageRouterTests/testIndexDocumentsListRejectsUnknownMetadataBeforeStoreDispatch'
run swift test --filter 'LocalRuntimeMessageRouterTests/testRetrievalQueryReturnsBoundedLexicalResultsWithoutFullChunkOrFutureMetadata|LocalRuntimeMessageRouterTests/testRetrievalQueryRejectsUnknownMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testRetrievalQueryRejectsOversizedQueryBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testSourceAnchorResolveRejectsMissingBlankOrNonStringAnchorBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testSourceAnchorResolve'
run swift test --filter LocalRuntimeMessageRouterTests/testUntrustedHelloReturnsPairingRequired
run swift test --filter 'LocalRuntimeMessageRouterTests/testRepeatedInvalidPairingAttemptsInvalidateActiveSession|LocalRuntimeMessageRouterTests/testExpiredAndNoActivePairingRequestsReturnStructuredRejections'
run swift test --filter PairingCoordinatorTests
				run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets|LocalRuntimeMessageRouterTests/testPairingQRCodePayloadCanOmitEndpointHints|LocalRuntimeMessageRouterTests/testPairingQRCodePayloadIncludesRelaySecretWhenPresent|LocalRuntimeMessageRouterTests/testPairingQRCodePayloadIncludesP2PRendezvousRecordWhenPresent|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedP2PRendezvousFixture|LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorUsesStoredBootstrapSettingsWhenEnvironmentIsEmpty|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingFallsBackAcrossBootstrapRelayEndpointsBeforeQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesSavedBootstrapRelayEndpointBeforeQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelStartRenewsSavedBootstrapRelayRouteBeforeRelayStart|LocalRuntimeMessageRouterTests/testCompanionAppModelRenewsBootstrapRelayRouteAfterRelayFailure|LocalRuntimeMessageRouterTests/testCompanionAppModelSavesBootstrapRelaySettingsAndAllocatesRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelAcceptsAdvancingSavedBootstrapLeaseForStableRelayID|LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsNonAdvancingSavedBootstrapLeaseForStableRelayID|LocalRuntimeMessageRouterTests/testCompanionAppModelDoesNotReuseSavedLeaseForDifferentRelayRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesBootstrapQRCodeWithExpiredSavedLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRequiresRemoteQRCodeForLoopbackSavedRelayHost|LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease|LocalRuntimeMessageRouterTests/testCompanionAppModelWaitsForLeaseBeforeUsingCGNATPrivateOverlayRelayQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteReturnsNilWithoutFreshRelayLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial|LocalRuntimeMessageRouterTests/testCompanionAppModelKeepsLeasePreparationIssueWhenRelayIsReadyWithoutLease|LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsUnknownRelayScopeFromRuntimeProvider|LocalRuntimeMessageRouterTests/testChatSendStoresRuntimeSideProcessingEvents|LocalRuntimeMessageRouterTests/testChatSendIntoArchivedRuntimeSessionReturnsStructuredErrorWithoutMutatingStore|LocalRuntimeMessageRouterTests/testChatCancelAcknowledgementPersistsRuntimeOwnedCancelledEvent|LocalRuntimeMessageRouterTests/testConnectionCloseCancelsActiveChatGenerationAndPersistsCancelledEvent|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore|LocalRuntimeMessageRouterTests/testChatMessagesListDoesNotExposeRuntimeCompactionMetadata|LocalRuntimeMessageRouterTests/testChatMessagesListRejectsUnknownPayloadMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testChatMessagesListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryHandlersReturnEmptyForNonPositiveLimitsWithoutReadingStore|LocalRuntimeMessageRouterTests/testRuntimeChatStoreAppliesArchiveRestoreAndDeleteLifecycle|LocalRuntimeMessageRouterTests/testRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeChatStoreSearchesSessionSummariesAndTranscriptWithinOwnerScope|LocalRuntimeMessageRouterTests/testRuntimeChatStoreTreatsNonPositiveLimitsAsEmptyHistoryWindows|LocalRuntimeMessageRouterTests/testRuntimeChatStoreZeroLimitsReturnEmptyWithoutReadingLog|LocalRuntimeMessageRouterTests/testRuntimeChatStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeChatHistorySemanticallyInvalidEventReturnsStructuredError|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryCorruptStoreReturnsStructuredError|LocalRuntimeMessageRouterTests/testRuntimeChatSessionLifecycleMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testChatSessionLifecycleRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testRuntimeChatSessionRenameStoresRuntimeTitle|LocalRuntimeMessageRouterTests/testChatSessionRenameRejectsUnknownPayloadMetadataBeforeTitleStoreMutation|LocalRuntimeMessageRouterTests/testChatSessionsListQueryFiltersRuntimeOwnedSummaries|LocalRuntimeMessageRouterTests/testChatSessionsListEmbeddingModelHintStaysSearchOnly|LocalRuntimeMessageRouterTests/testChatSessionsListSemanticSearchFailureDoesNotFallBackToLexicalSearch|LocalRuntimeMessageRouterTests/testChatSessionsListRejectsResourceHeavyQueriesBeforeEmbeddingOrStoreSearch|LocalRuntimeMessageRouterTests/testChatSessionsListRejectsUnknownPayloadMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testChatSessionsListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testChatSessionsListQueryMatchesReasoningWhileMessagesKeepAnswerSeparate|LocalRuntimeMessageRouterTests/testRuntimeMemoryMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testMemoryListRejectsUnknownPayloadMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemoryUpsertRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemoryDeleteRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemoryListQueryFiltersRuntimeOwnedMemoryWithSearchMetadata|LocalRuntimeMessageRouterTests/testMemoryUpsertRejectsClientSuppliedSourceMetadataAndPreservesRuntimeSource|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreReportsSemanticallyInvalidUpsertLine|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreScopesEntriesByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeMemoryListCorruptStoreReturnsStructuredError|LocalRuntimeMessageRouterTests/testAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory|LocalRuntimeMessageRouterTests/testChatSendInjectsEnabledRuntimeMemoryFromRuntimeStore|LocalRuntimeMessageRouterTests/testChatSendRuntimeMemoryOverridesClientSuppliedMemory|LocalRuntimeMessageRouterTests/testChatSendStoresOnlyClientVisibleMessagesWhileBackendReceivesRuntimeContext|LocalRuntimeMessageRouterTests/testChatSendDoesNotCompactShortConversation|LocalRuntimeMessageRouterTests/testChatSendCompactsOlderTurnsBeforeBackendRequestWhenContextIsLarge|LocalRuntimeMessageRouterTests/testChatSendCompactionAnnotatesBackendOnlySourceSpanWithoutPersisting|LocalRuntimeMessageRouterTests/testChatSendUsesModelContextWindowMetadataForCompactionBudget|LocalRuntimeMessageRouterTests/testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate|LocalRuntimeMessageRouterTests/testChatSendReturnsStructuredErrorWhenRuntimeMemoryCannotLoad|LocalRuntimeMessageRouterTests/testChatSendStreamsReasoningDeltaSeparatelyFromAnswerDelta|LocalRuntimeMessageRouterTests/testChatSendSplitsInlineThinkTagsBeforeStreamingAnswer|LocalRuntimeMessageRouterTests/testChatSendInstalledEmbeddingModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendInstalledCloudModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse|LocalRuntimeMessageRouterTests/testChatSendGeneratedRuntimeTitleStripsInlineThinking|LocalRuntimeMessageRouterTests/testChatSendTitleGenerationUsesDeterministicFallbackWhenBackendTitleIsInvalid'
	run swift test --filter 'LocalRuntimeMessageRouterTests/testChatSessionsListSerializesPerConnectionAndConnectionCloseCancelsEmbedding|LocalRuntimeMessageRouterTests/testConnectionCloseKeepsGlobalSemanticSlotUntilNoncooperativeEmbeddingEnds|LocalRuntimeMessageRouterTests/testConnectionCloseSuppressesSuccessfulResultFromEmbeddingThatIgnoresCancellation|LocalRuntimeMessageRouterTests/testChatSessionsListInvalidEmbeddingResponseUsesKnownBackendErrorCode|LocalRuntimeMessageRouterTests/testChatSessionsListEmbeddingBudgetMatchesLatestAliasRouting|LocalRuntimeMessageRouterTests/testChatSessionsListPersistentEmbeddingCacheEmbedsOnlyQueryAfterColdFill|LocalRuntimeMessageRouterTests/testChatSessionsListDoesNotPersistEmbeddingsWithoutStrongModelRevision|LocalRuntimeMessageRouterTests/testChatSessionsListModelRevisionChangeDoesNotReusePriorCachedVectors|LocalRuntimeMessageRouterTests/testChatSessionsListMalformedCachedDimensionTriggersFullRefresh|LocalRuntimeMessageRouterTests/testChatSessionsListSemanticCacheFailureDegradesToOnDemandEmbedding|LocalRuntimeMessageRouterTests/testConnectionCloseBeforeSemanticCacheCommitPreventsPersistentWrite'
	run swift test --filter RuntimeChatContextCompactionPlannerTests
	run swift test --filter RuntimeChatCompactionSourceFingerprintTests
	run swift test --filter 'LocalRuntimeMessageRouterTests/testChatSendCompactionAnnotatesBackendOnlySourceSpanWithoutPersisting|LocalRuntimeMessageRouterTests/testChatSendUsesModelContextWindowMetadataForCompactionBudget|LocalRuntimeMessageRouterTests/testChatSendRejectsOversizedNewestMessageBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate'
	run swift test --filter 'LocalRuntimeMessageRouterTests/testChatSendUsesBoundedBackendOnlyGeneratedCompactionSummary|LocalRuntimeMessageRouterTests/testChatSendSkipsCompactionPrepassAndCacheWhenCurrentPromptSkillIsUnavailable|LocalRuntimeMessageRouterTests/testChatSendOversizedGeneratedCompactionSummaryFallsBackDeterministically|LocalRuntimeMessageRouterTests/testGeneratedCompactionSummaryStaysAbsentAfterSQLiteReopenAndSearch|LocalRuntimeMessageRouterTests/testChatCancelDuringGeneratedCompactionPrepassCancelsDerivedGeneration|LocalRuntimeMessageRouterTests/testChatCancelBeforeCompactionPrepassRegistrationPreventsDerivedAndPrimaryDispatch|LocalRuntimeMessageRouterTests/testChatCancelFromDifferentConnectionCannotCancelActiveGeneration|LocalRuntimeMessageRouterTests/testDuplicateActiveChatRequestIDIsRejectedWithoutReplacingOriginalContext|LocalRuntimeMessageRouterTests/testDerivedCompactionGenerationIDIsReservedAgainstPrimaryChatCollision|LocalRuntimeMessageRouterTests/testSecondChatCancelCannotReachBackendWhileOwnedCancellationIsInProgress|LocalRuntimeMessageRouterTests/testChatCancelPersistsIntentWhenBackendGenerationHandoffReturnsNotFound|LocalRuntimeMessageRouterTests/testChatCancelWaitsForAtomicPrimaryBackendRegistration'
			run swift test --filter 'SQLiteRuntimeChatCompactionSummaryCacheTests|LocalRuntimeMessageRouterTests/testChatSendReusesDurableGeneratedCompactionSummaryAfterCacheReopen|LocalRuntimeMessageRouterTests/testChatSendEvolvesStrictlyExtendedCompactionSummaryAndCachesResult|LocalRuntimeMessageRouterTests/testChatSendDoesNotEvolveSummaryAfterCompactedPrefixEdit|LocalRuntimeMessageRouterTests/testFailedIncrementalPrimaryDoesNotPersistEvolvedCompactionSummary|LocalRuntimeMessageRouterTests/testFailedPrimaryDoesNotPersistGeneratedCompactionSummary|LocalRuntimeMessageRouterTests/testChatSessionDeletePurgesDurableCompactionSummaries|SQLiteRuntimeChatEventStoreTests/testSQLiteStoreRejectsInvalidOrMismatchedAdaptiveV3SourceFingerprint'
			run swift test --filter 'AggregatingLlmBackendResidencyTests/testProviderUsageSourceForwardsThroughAggregateAndIsConsumedOnce|AggregatingLlmBackendResidencyTests/testRejectedDuplicateGenerationDoesNotEraseOriginalProviderUsageSource|LocalRuntimeMessageRouterTests/testChatSendUsesBoundedBackendOnlyGeneratedCompactionSummary|LocalRuntimeMessageRouterTests/testProviderUsageAboveInputBudgetDoesNotCommitGeneratedCompactionSummary|LocalRuntimeMessageRouterTests/testMismatchedProviderUsageDoesNotCalibrateOrCommitGeneratedCompactionSummary|SQLiteRuntimeChatEventStoreTests/testStoresRoundTripProviderUsageCalibration|SQLiteRuntimeChatEventStoreTests/testStoresRejectInvalidProviderUsageCalibrationShapes'
			run swift test --filter 'RuntimeChatCompactionCalibrationReportTests|SQLiteRuntimeChatEventStoreTests/testStoresExposeAggregateOnlyCompactionCalibrationReportAfterReopen|SQLiteRuntimeChatEventStoreTests/testCalibrationReportCapCountsFullyEligibleSamplesPastNewerCalibrationShapedRows|SQLiteRuntimeChatEventStoreTests/testCalibrationReportsRejectMalformedOrWrongTypeCalibrationPayloads|SQLiteRuntimeChatEventStoreTests/testCalibrationReportsRequireSelectedRequestBinding|SQLiteRuntimeChatEventStoreTests/testStoresRequireDeterministicPreviewEstimateToMatchBoundRequest|SQLiteRuntimeChatEventStoreTests/testStoresRejectDeterministicPreviewEstimateMismatchAfterReopenAndReport|SQLiteRuntimeChatEventStoreTests/testStoresRejectDuplicateCompactionTerminalBindingOnAppend|SQLiteRuntimeChatEventStoreTests/testStoresRejectDuplicateCompactionTerminalBindingAfterReopenAndReport|SQLiteRuntimeChatEventStoreTests/testStoresKeepSessionAndRequestCompactionBindingsExact|SQLiteRuntimeChatEventStoreTests/testCalibrationReportsRejectDuplicateBindingWithUncalibratedTerminal|SQLiteRuntimeChatEventStoreTests/testCalibrationReportStoreLimitsFailClosedOnExhaustion|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesCompactionCalibrationReportOnExplicitRefresh|AetherLinkLocalizationTests/testCompactionCalibrationCopyLocalizesAcrossSupportedLanguages|AetherLinkRenderSmokeTests/testCompactionCalibrationSheetRendersAcrossLanguagesAndAppearances'
		run swift test --filter 'LocalRuntimeMessageRouterTests/testMemoryListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemoryListRejectsOversizedQueryBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemoryListQueryFiltersRuntimeOwnedMemoryWithSearchMetadata'
		run swift test --filter DuplicateSuggestions
		run swift test --filter ProtocolCodecTests/testSemanticDuplicateThresholdPreservesExactIntegerWireKind
			run swift test --filter 'RuntimeMemorySemanticCalibrationTests|RuntimeMemorySemanticDuplicateSuggestionsTests|MemorySemanticDuplicateSuggestionsRouterTests'
			run python3 -m unittest script/test_memory_semantic_calibration.py
			run python3 -m unittest script/test_memory_semantic_calibration_acceptance.py
			run python3 -m py_compile script/run_memory_semantic_calibration.py script/test_memory_semantic_calibration.py script/check_memory_semantic_calibration_acceptance.py script/test_memory_semantic_calibration_acceptance.py
			run python3 script/check_memory_semantic_calibration_acceptance.py
		echo
		echo "==> python3 script/run_memory_semantic_calibration.py --mode offline"
		python3 script/run_memory_semantic_calibration.py --mode offline \
		  > build/qa/memory-semantic-calibration-offline-v1.json
		python3 - build/qa/memory-semantic-calibration-offline-v1.json <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
assert report["mode"] == "offline", report
assert report["corpus_sha256"] == "d41a31045a5a4d35ad8ce4ee05af34fc0937326b114a1512fb1160be75b571ff", report
assert report["aggregate_metrics"]["best_f1"]["threshold_basis_points"] == 9511, report
assert report["aggregate_metrics"]["review_threshold"]["threshold_basis_points"] == 9000, report
assert report["aggregate_metrics"]["review_threshold"]["f1_basis_points"] == 10000, report
assert report["review_clusters_exact_match"] is True, report
assert report["default_threshold_changed"] is False, report
assert report["automatic_memory_mutation"] is False, report
assert report["protocol_changed"] is False, report
assert "model_id" not in report and "model_fingerprint" not in report, report
PY
		run swift test --filter RuntimeSemanticMemorySearchTests
		run swift test --filter RuntimeMemorySemanticEmbeddingCacheTests
		run swift test --filter 'LocalRuntimeMessageRouterTests/testMemoryListSemanticSearchPersistsApprovedContentAndEmbedsOnlyQueryOnHit|LocalRuntimeMessageRouterTests/testMemoryListSemanticSearchDoesNotEmbedReviewDraftOrSourceAuditText|LocalRuntimeMessageRouterTests/testMemoryListSemanticSearchDropsEntryDeletedDuringInference|LocalRuntimeMessageRouterTests/testMemoryListSemanticHintWithoutQueryStaysLexicalAndDoesNotEmbed'
		run swift test --filter LocalRuntimeMessageRouterTests/testMemoryListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch
	run swift test --filter LocalRuntimeMessageRouterTests/testMemoryUpsertRejectsInvalidAllowedPayloadTypesBeforeStoreMutation
	run swift test --filter LocalRuntimeMessageRouterTests/testRejectsBlankEnvelopeRequestIDBeforeRuntimeCommandDispatch
	run swift test --filter LocalRuntimeMessageRouterTests/testRejectsUnsupportedEnvelopeVersionBeforeRuntimeCommandDispatch
		run swift test --filter 'LocalRuntimeMessageRouterTests/testHelloRejectsInvalidAllowedPayloadTypesBeforeChallengeCreation|LocalRuntimeMessageRouterTests/testHelloCapabilityCountBoundAccepts64AndRejects65|LocalRuntimeMessageRouterTests/testHelloNegotiatesRuntimeCapabilitiesWithoutChangingLegacyChallengeShape|LocalRuntimeMessageRouterTests/testAuthResponseRejectsBlankAllowedFieldsBeforeAuthentication'
	run swift test --filter LocalRuntimeMessageRouterTests/testChatCancelRejectsBlankTargetRequestIDBeforeBackendDispatch
		run swift test --filter 'LocalRuntimeMessageRouterTests/testChatTitleRequestRejectsBlankSessionIDBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatTitleRequestRejectsBlankModelBeforeBackendDispatch'
	run swift test --filter 'LocalRuntimeMessageRouterTests/testChatSessionLifecycleRejectsInvalidAllowedPayloadTypesBeforeStoreMutation|LocalRuntimeMessageRouterTests/testChatSessionRenameRejectsInvalidAllowedPayloadTypesBeforeTitleStoreMutation|LocalRuntimeMessageRouterTests/testMemoryDeleteRejectsInvalidAllowedPayloadTypesBeforeStoreMutation'
	run swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesGUIAllocatedQRCodeWithNearExpiredLease
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesGUIAllocatedQRCodeWithExpiredLease'
run swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshRejectsMalformedRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshAllowsPrivateOverlayAndUsbReverseScopedRelayMaterial|LocalRuntimeMessageRouterTests/testRouteRefreshFailureRedactsRelaySecretsAndProviderEndpoints'
run swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshP2PRendezvousMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshAllowsBoundedP2PEncryptedBodyLargerThanRouteValues|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsMalformedP2PRendezvousMaterialFromRuntimeProvider'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelDoesNotExposeAuthenticatedRouteRefreshByDefault|LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsRuntimeOnlyRouteRefreshWhenDiagnosticOptInIsEnabled'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores|LocalRuntimeMessageRouterTests/testCompanionAppModelRunsAllOwnerRuntimeChatRetentionMaintenance|LocalRuntimeMessageRouterTests/testCompanionAppModelRetentionMaintenanceDoesNotRescanRuntimeDataSummary|LocalRuntimeMessageRouterTests/testCompanionAppModelRetentionScheduleDoesNotKeepModelAlive|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeHistoryTranscriptPreviewAcrossOwners|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesPreservesChatSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsPreservesMemorySummaryError'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingRequiresRemoteQRCodeRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRemoteRoutePreparationIssueWhenBootstrapAllocationThrows'
run swift test --filter 'LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListReturnsOwnerScopedActiveVisibleDraftsOnly|LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListRejectsUnknownPayloadMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateCachesReviewDraftAndApprovalPreservesGeneratedSource|LocalRuntimeMessageRouterTests/testAuthenticatedMemorySummaryDraftGenerateReusesOwnerScopedCache|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateDoesNotReuseCacheAcrossRequestedModels|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateDoesNotCoalesceConcurrentDifferentModels|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateDoesNotReuseCacheAcrossPromptRevisions|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateFailsBeforeBackendWhenPromptSkillIsUnavailable|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateMalformedResponseLeavesPreviewAndMemoryUnchanged|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateRejectsValidJSONWhenStreamEndsWithoutDone|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateStopsAtDoneBeforePostTerminalEvents|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateRevalidatesSourceAfterInferenceBeforeCaching|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveWritesIdempotentOwnerScopedMemoryAndHidesApprovedDraft|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveDoesNotReuseUnresolvableHistoricalPromptRevision|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRejectsInvalidAllowedPayloadTypesBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRejectsBlankDraftIDBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissHidesOwnerScopedDraftWithoutWritingMemory|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRejectsInvalidAllowedPayloadTypesBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRejectsBlankDraftIDBeforeStoreMutation'
	run swift test --filter 'LocalRuntimeMessageRouterTests/testMemorySummaryDraftGeneratePinsAggregateProviderModelIDAcrossAliasDrift|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateFailsClosedOnSameProviderAliasReuse|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateDoesNotCoalesceSameAliasAcrossResolvedProviders|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateCancelsLastWaiterBeforeCacheCommit|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateKeepsSharedWorkerForRemainingWaiter|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateStartsFreshFlightAfterLastWaiterCancellation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateRetiresCompletedFlightBeforeDelayedCancellationCleanup|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateConnectionCloseBeforeCommitOrPublicationWritesNothing|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateReadsLegacyProviderlessCacheButRegenerates|LocalRuntimeMessageRouterTests/testQualifiedChatRequestDoesNotResolveDisplayAliasForDirectOrAggregateBackend|LocalRuntimeMessageRouterTests/testQualifiedMemorySummaryRequestDoesNotResolveDisplayAliasForDirectOrAggregateBackend|LocalRuntimeMessageRouterTests/testQualifiedChatTitleRequestDoesNotResolveDisplayAliasForDirectOrAggregateBackend|LocalRuntimeMessageRouterTests/testChatSendPinsResolvedAggregateProviderAcrossCompactionPrepassAndPrimaryDispatch|LocalRuntimeMessageRouterTests/testChatSendFailsClosedWhenResolvedAggregateProviderModelDisappears|LocalRuntimeMessageRouterTests/testChatSendRejectsReservedQualifiedPrefixInProviderNativeModelID|LocalRuntimeMessageRouterTests/testChatTitleRequestPinsAggregateProviderModelIDAcrossAliasDrift|LocalRuntimeMessageRouterTests/testChatTitleRequestFallsBackWithoutDispatchOnSameProviderAliasReuse|LocalRuntimeMessageRouterTests/testModelsPullAuthorityChangeAfterPublicationPreparationBeforeCommitSuppressesWireResult|LocalRuntimeMessageRouterTests/testModelsPullTransportBindingDriftAfterFinalReadBeforeTerminalCommitSuppressesWireResult|LocalRuntimeMessageRouterTests/testModelsPullTransportBindingMutationCannotLinearizeInsideFinalAuthorityTransaction'
		run swift test --filter 'LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerationDeadlineBoundsBlockingCancellationForExactKey|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerationDeadlineBoundsModelLookupBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerationDeadlineRetiresOnlyExpiredSharedWaiter|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateRejectsOversizedRawReasoningAndCancelsExactGeneration|LocalRuntimeMessageRouterTests/testMemorySummaryDraftCancellationForOneKeyDoesNotStarveAnotherKey|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateRevalidatesSourceAfterWorkerBeforePublication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGeneratePublishesBeforeBlockingDurableCache|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGeneratePersistsOnlyAfterTransportSuccessAndRetriesMaterializedCandidate|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRejectsUndeliveredGeneratedContentAndFallsBackToVisiblePreview|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveAcceptsExactPublishedContentWhilePersistenceIsPending|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveBindsIdenticalContentToExpectedSummaryMethod|LocalRuntimeMessageRouterTests/testMemorySummaryDraftConcurrentSuccessfulRetriesPersistMaterializedCandidateOnce|LocalRuntimeMessageRouterTests/testMemorySummaryDraftMaterializedCacheKeepsTokensBoundAcrossReplacement|LocalRuntimeMessageRouterTests/testMemorySummaryDraftMaterializedCacheRejectsReplacedWorkerSnapshot|LocalRuntimeMessageRouterTests/testMemorySummaryDraftMaterializedCachePinsPublicationAcrossCapacityEviction|LocalRuntimeMessageRouterTests/testMemorySummaryDraftMaterializedCacheRetriesOnlyIdempotentPersistenceFailure|LocalRuntimeMessageRouterTests/testMemorySummaryDraftPersistenceDispatcherBoundsIdempotentRetryToTwoAttempts|LocalRuntimeMessageRouterTests/testMemorySummaryDraftAmbiguousPersistenceFailureRetriesIdempotentlyAfterConcurrentSuccess|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateJSONLSourceLockCoversTransportEnqueue'
run swift test --filter 'RuntimeMemoryStoreGeneratedDraftTests|RuntimeMemoryStoreSummaryDecisionTests|RuntimeLongInactivityMemorySummarizationPolicyTests'
run swift test --filter 'LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRejectsRenamedSameCountSourceBeforeMemoryMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRevalidatesSourceAtMutationCommit|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRevalidatesSourceAtMutationCommit|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveHoldsSQLiteSourceLockThroughMemoryMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissHoldsSQLiteSourceLockThroughMemoryMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDecisionMutationErrorsRemainMemoryStoreErrors|LocalRuntimeMessageRouterTests/testMemorySummaryDraftGenerateRejectsStaleGuardsBeforeModelLookup|LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListRequiresV2ReviewForLegacyRecordsAndRejectsLegacyRequestAuthority'
run swift test --filter 'LocalPeerServerTests/testLocalPeerConnectionCompletion|RelayPeerClientTests/testRelayPeerConnectionCompletion'
run swift test --filter 'RelayPeerClientTests/testRelayPeerClientRetireKeepsCurrentConnectionAndSuppressesReconnect|RelayPeerClientTests/testRelayPeerConfigurationDefaultControlLineTimeoutAllowsPhysicalQrStartup|RelayPeerClientTests/testRelayPeerClientTimesOutWhenRegistrationLineNeverArrives|RelayPeerClientTests/testRelayPeerClientTimesOutWhenReadyLineNeverArrivesAfterRegistration'
	run ./gradlew --no-daemon :core:protocol:testDebugUnitTest --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest
	run ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --tests com.localagentbridge.android.runtime.RuntimeClientChatSessionMutationFailureTest --tests com.localagentbridge.android.AppNavigationTest
	run ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ResearchNotebookDrawerTest
	run swift test --filter 'ResearchNotebook|ResearchBrief|ResearchPromotion|ExpiredLifecycleCannotTakeOver|ChatSessionsList.*Research|ChatTitleRequest|AutomaticChatTitle|RuntimeChatSessionRenameStoresRuntimeTitle|ChatSessionRenameRejectsInvalidTitles|ChatEventStoresRejectInvalidTitleEvents|SameTimestampTitleAppendOrder|ReverseTimestampTitle|LegacyInvalidTitles'
	run swift test --filter 'LocalRuntimeMessageRouterTests/testAuthoritativeSessionSyncWireTranscriptMatchesSharedExactPayloads|LocalRuntimeMessageRouterTests/testAuthoritativeSessionSyncMatchesSharedLifecycleFixtureAcrossPaginationAndBulkLifecycle|LocalRuntimeMessageRouterTests/testAuthoritativeChatSessionCursorTraversesSnapshotWithAbsoluteRanksAndRejectsTampering|LocalRuntimeMessageRouterTests/testAuthoritativePaginationRejectsExpiredEvictedAndCrossOwnerCursors|LocalRuntimeMessageRouterTests/testAuthoritativePaginationExpiresAfterMonotonicTTLWhenWallClockRollsBack|LocalRuntimeMessageRouterTests/testReauthenticationChallengeInvalidatesCursorAndSuppressesInFlightInitialPublication|LocalRuntimeMessageRouterTests/testNewerAuthoritativeInitialRequestRetainsAuthorityOverOlderSlowRequest|LocalRuntimeMessageRouterTests/testAuthoritativeBulkLifecycleUsesBoundedFreshRequestBatchesAndReportsRemaining|LocalRuntimeMessageRouterTests/testAuthoritativeBulkLifecycleRejectsAuthorityCapturedBeforeCapabilityDowngrade|LocalRuntimeMessageRouterTests/testSingleSessionLifecycleRejectsAuthorityCapturedBeforeReauthentication|LocalRuntimeMessageRouterTests/testChatSessionRenameRejectsAuthorityCapturedBeforeDifferentOwnerReauthentication|LocalRuntimeMessageRouterTests/testDevelopmentChatSessionRenameRejectsConnectionClosedAfterAuthorityCapture|LocalRuntimeMessageRouterTests/testDevelopmentChatSessionRenameRejectsCloseDuringRequestTaskRegistration|LocalRuntimeMessageRouterTests/testDevelopmentSingleSessionLifecycleRejectsConnectionClosedAfterAuthorityCapture|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsChallengeSupersededDuringTrustedDeviceLookup|LocalRuntimeMessageRouterTests/testAuthoritativeSessionListRejectsOversizedCursorAndSnapshotOverflow|LocalRuntimeMessageRouterTests/testAuthoritativeBulkDeletePurgeFailurePreventsLifecycleMutation|SQLiteRuntimeChatEventStoreTests/testSQLiteBulkLifecycleProcessesDeterministicBoundedBatchesBeyondFirstPage|SQLiteRuntimeChatEventStoreTests/testJSONLBulkLifecycleHoldsOwnerScopedDeterministicBatchState|SQLiteRuntimeChatEventStoreTests/testSQLiteBulkLifecycleRollsBackEntireBatchOnInsertFailure|SQLiteRuntimeChatEventStoreTests/testBulkLifecyclePreCommitFailureReceivesExactTargetsAndWritesNothing'
	run swift test --filter SQLiteRuntimeChatEventStoreTests
	run swift test --filter 'SQLiteRuntimeChatEventStoreTests/testSQLiteStorePreservesRuntimeCompactionMetadataWithoutIndexingIt|SQLiteRuntimeChatEventStoreTests/testSQLiteStorePreservesAndRevalidatesAdaptiveV3SourceFingerprint|SQLiteRuntimeChatEventStoreTests/testJSONLStoreRevalidatesAdaptiveV3SourceFingerprintAfterReopen|SQLiteRuntimeChatEventStoreTests/testSQLiteStoreRejectsInvalidOrMismatchedAdaptiveV3SourceFingerprint|SQLiteRuntimeChatEventStoreTests/testStoresRejectInvalidCompactionResolutionShapes|SQLiteRuntimeChatEventStoreTests/testStoresBindCompactionResolutionToAdaptiveV3RequestAccounting|SQLiteRuntimeChatEventStoreTests/testStoresRejectMismatchedCompactionResolutionAfterReopen|SQLiteRuntimeChatEventStoreTests/testSQLiteStoreImportsLegacyCompactionMetadataWithoutStructuralAccounting|SQLiteRuntimeChatEventStoreTests/testSQLiteStoreRejectsInvalidRuntimeCompactionMetadata'
run swift test --filter 'SQLiteRuntimeChatEventStoreTests/testSQLiteRetentionPrunesDeletedSessionsByOwnerScopeAndCutoff|SQLiteRuntimeChatEventStoreTests/testSQLiteRetentionTombstonePreventsLegacyBackfillResurrection|SQLiteRuntimeChatEventStoreTests/testProductionRuntimeChatRetentionPolicyPrunesOnlyExpiredDeletedSessions|SQLiteRuntimeChatEventStoreTests/testSQLiteAllOwnerRetentionUsesGlobalLimitAndDeterministicOwnerTieBreak|SQLiteRuntimeChatEventStoreTests/testSQLiteAllOwnerRetentionUsesBoundedMetadataQueryAndTargetedFTSDeletion|SQLiteRuntimeChatEventStoreTests/testProductionAllOwnerMaintenanceOverloadPrunesAcrossOwnersWithOneLimit|SQLiteRuntimeChatEventStoreTests/testProductionRetentionCompactsLegacyJSONLOnlyAfterCommitAndPreservesAppendBackfill|SQLiteRuntimeChatEventStoreTests/testLegacyCompactionCoordinatesConcurrentCrossInstanceAppendWithoutDataLoss|SQLiteRuntimeChatEventStoreTests/testProductionRetentionDefersLegacyCompactionUntilFinalBatchDrain'
run swift test --filter RuntimeLongInactivityMemorySummarizationPolicyTests

echo
echo "No-device quality checks passed."
echo "Covered v0.4 addendum: Android runtime-mediated model capability display"
echo "Covered v0.4 addendum: macOS runtime model capability display"
echo "Covered v0.4 addendum: Android memory indexing model capability display"
echo "Covered v0.4 addendum: Android authoritative drawer virtualization"
echo "Covered v0.4 addendum: Android research brief model capability selection"
echo "Covered v0.4 addendum: Android drawer selected-model capability summary"
echo "Covered v0.5 prerequisite: models.pull host-approval fail-closed barrier"
echo "Covered v0.5 addendum: models.pull host-local approval broker and durable redacted audit"
echo "Covered v0.5 addendum: host-local runtime permission policy registry and redacted action audit"
echo "Covered v0.5 addendum: host-local action-neutral approval lifecycle core"
echo "Covered v0.5 addendum: exact provider dispatch identity and host-approval publication linearization"
echo "Covered v0.5 addendum: host-local approval review text anti-spoofing"
echo "Covered v0.5 addendum: immutable host-local prompt-only skill registry foundation"
echo "Covered v0.5 addendum: durable research notebook prompt-skill revision binding"
echo "Covered v0.5 addendum: memory-summary draft requested-model and prompt-skill revision binding"
echo "Covered v0.5 addendum: memory-summary source-bound review identity and commit linearization"
echo "Covered v0.5 addendum: memory-summary durable terminal decision linearization"
echo "Covered v0.5 addendum: Android memory-summary drafts list authority correlation"
echo "Covered v0.5 addendum: memory-summary generation terminal-event integrity"
echo "Covered v0.5 addendum: memory-summary generation bounded lifecycle"
echo "Covered v0.5 addendum: memory-summary transport completion and persistence coalescing"
echo "Covered v0.5 addendum: Android memory-summary terminal channel and source-identity closure"
echo "Covered v0.5 addendum: Android memory-summary request deadline closure"
echo "Covered v0.5 addendum: chat compaction prompt-skill revision binding"
echo "Covered v0.5 addendum: runtime-authoritative chat title single-flight and terminal correlation"
echo "Covered v0.5 review-only addendum: runtime Python sandbox recommendation remains proposed_not_selected; App Sandbox XPC design is unselected; Python execution, source acquisition, protocol activation, files, network, child processes, packages, and live measurement remain unauthorized."
echo "Covered: local emit-only pairing QR artifact generation, QR PNG decode, canonical pairing URI policy, authenticated mock relay E2E, QR candidate structured-error routing, identity-only QR USB reverse fallback, public relay remote-scope QR contract, private-overlay relay scope schema guard, Android private-overlay QR missing-scope diagnostic, link-local relay preflight rejection, relay preflight allocation non-persistence, bootstrap relay endpoint failover before QR generation, saved bootstrap relay endpoint allocation, remote relay lease renewal and QR eligibility, QR relay alias-family completeness, release-mode diagnostic direct-route rejection, invalid QR auto-reconnect state guard, relay-route payload validation, PairingStore complete and expired relay-route persistence, relay preparation host eligibility guard, expired relay lease reconnect guard, fresh relay QR recovery, Android QR route refresh public-key optional binding, macOS remote QR lease route binding, route.refresh runtime-identity binding, route.refresh relay-scope enum validation, route.refresh rejected-payload retry, cross-network QR readiness copy, diagnostic QR text fallback copy, macOS remote QR lease failure visibility, macOS first-launch pairing priority, macOS first-run diagnostics hiding, macOS Pairing QR accessibility state, macOS Pairing QR image accessibility element, macOS Pairing QR unavailable accessibility value, macOS Pairing QR time remaining accessibility value, macOS Pairing QR remote-route expiry accessibility hint, macOS Pairing QR generation action accessibility reason, macOS active Pairing QR renewal accessibility hint, macOS sidebar brand accessibility label, macOS sidebar brand heading trait, macOS page header accessibility labels, macOS page header heading trait, macOS panel header heading trait, macOS empty-state accessibility labels, macOS sidebar preference picker accessibility values, macOS sidebar preference picker accessibility hints, macOS nearby-only connection guidance copy, macOS global QR generation availability gate, macOS app-language date formatting, macOS app-language byte-count formatting, macOS app-language region tag normalization, macOS connection recovery form field accessibility, macOS connection recovery QR action accessibility reason, macOS Connection Recovery result tone accessibility label, macOS trusted-device remove accessibility labels, macOS trusted-device remove accessibility hints, macOS trusted-device row accessibility labels, macOS trusted-device row accessibility visual-summary separation, macOS trusted-device removal confirmation localization, macOS trusted-device confirm-remove action accessibility labels, macOS Activity trusted-device audit copy, macOS Activity model-residency event summaries, macOS Activity row tone accessibility labels, macOS Activity log list accessibility summary, macOS Activity diagnostic disclosure separate focus, macOS Activity route-success ready tone, macOS Activity technical-details accessibility state, macOS saved connection details removal accessibility label, macOS Activity technical-details accessibility labels, macOS provider technical-details accessibility labels, macOS provider technical-details accessibility state, macOS provider status pill accessibility labels, macOS provider row accessibility summaries, macOS runtime overview accessibility labels, macOS status card accessibility labels, macOS model row accessibility labels, macOS model group header accessibility labels, macOS model group header heading trait, macOS relay status row accessibility labels, macOS route diagnostic technical-details accessibility labels, macOS readiness row accessibility labels, macOS natural count/plural copy guard, macOS visible localization anchors with zh-Hans bundle fallback, macOS raw SwiftUI visible-string localization guard, macOS five-language system/light/dark detail render smoke including Connection Recovery, macOS active Pairing QR compact render smoke, macOS compact Quick Actions render smoke, macOS native language picker labels, macOS installed-local model visibility, macOS runtime-local chat routing, macOS corrupt chat-store visibility, macOS runtime-owned memory injection, stale-client-memory replacement, runtime-only context history filtering, and heuristic runtime chat context compaction, Android natural message-count plural resources, Android raw Compose visible-string localization guard, platform-neutral app copy guard, Android native language picker labels, Android first-run language picker before pairing, Android app System/Light/Dark theme path, Android refresh-health action copy, Android localized model-status resources, Android provider-managed model label suppression, Android strict local model metadata guard, Android drawer runtime session status, Android drawer runtime summary accessibility, Android drawer settings footer layout, Android app top-bar shell chrome, Android screen heading semantics, Android QR scanner heading semantics, Android chat top-bar install action cue, Android chat top-bar model search interaction, Android chat top-bar model row accessibility summaries, Android drawer chat options contextual accessibility, Android drawer chat options action labels, Android drawer chat menu contextual action labels, Android drawer chat row accessibility summaries, Android drawer chat search interaction, Android drawer streaming lockout visual-disabled state, Settings chat history search interaction, Android Settings chat-history runtime search metadata compact layout, Android QR scanner permission/settings/torch/cancel chrome, Android QR scanner close action accessibility label, Android QR scanner five-language chrome accessibility, QR scanner torch state accessibility, Android QR-first chat empty state, Android QR pairing live-region accessibility, Android Settings QR scan disabled reason, Android diagnostic QR text state accessibility, Android diagnostic QR text contextual action labels, Android connect action disabled reason, Android platform-neutral connect guidance copy, Android connection status hero accessibility summary, Android model refresh action accessibility state, Android New Chat disabled reason, Android chat empty route guidance full-wrap layout, Android expired remote-route QR recovery action, Android trusted composer readiness lock, Android composer readiness hint, Android composer input readiness accessibility state, Android send button readiness accessibility state, Android composer primary action click labels, Android composer attach action accessibility state, Android composer attachment count limit accessibility, Android attachment-only prompt resource localization, Android attachment picker single-dispatch guard, Android bounded attachment read guard, Android streaming cancel Compose action, Android attachment chip accessibility state, Android attachment remove disabled reason, Android attachment size locale formatting, Android message attachment accessibility state, Android message role accessibility summaries, Android assistant identity marker, Android assistant identity marker compact layout, Android message copy accessibility labels, Android copy success live-region accessibility, Android code block copy accessibility labels, Android multi-code-block copy action labels, Android backend readiness banner accessibility summary, Android generic error banner accessibility summary, Android provider diagnostics expanded state, Android provider diagnostics named accessibility labels, Android provider diagnostics action labels, Android provider row accessibility summaries, Android reasoning accessibility summary, Android jump-to-latest Compose interaction, Android jump-to-latest compact layout, Settings expandable section accessibility state, Settings expandable section duplicate icon semantics guard, Settings preference option accessibility summaries, Settings diagnostic endpoint expander accessibility state, Settings connection switch state accessibility, Settings discovered route contextual action accessibility, Settings discovered route unavailable accessibility summaries, Android discovered trusted-route row compact layout, Android embedding model row accessibility summaries, Settings embedding model streaming lockout accessibility state, Settings memory contextual action accessibility, Settings memory capped action accessibility labels, Settings memory add readiness accessibility state, Settings memory destructive confirmation haptic timing, chat history destructive confirmation haptic timing, confirmation-open lightweight haptic timing, Settings expired-route primary QR action, Android connected Settings redundant-connect guard, Android trusted-runtime forget confirmation, Settings pairing section resync, language alias selection normalization, legacy Python relay allocation-guard, Android no-device Compose screen smoke with five-language pairing copy, Settings diagnostic endpoint visibility guard, chat history bulk action hiding and two-step confirmation, chat history bulk expander accessibility state, chat history bulk action disabled accessibility state, chat history per-chat contextual action accessibility, chat history per-chat disabled accessibility state, chat history row accessibility summaries, Android rename chat readiness accessibility state, Android rename chat action labels, Android rename chat compact dialog layout, full five-language light/dark Chat/Settings/Connection layout matrix, reasoning toggle, chat top-bar model/embedding picker separation, selected model-picker plus Settings preference and embedding-model accessibility state, fake haptic callback dispatch, connection notice haptic callback dispatch, runtime-owned streaming storage redaction, pending relay QR retry, Android pending relay QR secret-store boundary, Android pending relay QR secret cleanup, relay QR completion persistence, real RuntimeRelayTcpClient app pairing path, relay-before-Bonjour fallback, and trusted relay app-init auto-reconnect."
echo "Covered private-overlay QR artifact addendum: shared compact private-overlay relay QR fixture renders to PNG and verifies with production bootstrap, relay route, CGNAT private-overlay scope, and no direct endpoint."
echo "Covered private-overlay QR scope canonicality addendum: QR artifact verification rejects case- or whitespace-mutated relay_scope/rsc values before private-overlay QR evidence is counted."
echo "Covered Android private-overlay QR scanner acceptance addendum: Android scanner raw-value handling accepts the shared compact private-overlay relay QR fixture through the runtime pairing parser while still requiring route-capable QR material."
echo "Covered addendum: Android OS app-language handoff, Android follow system language preference, Android translated Memory noun, macOS menu-bar status and command localization, macOS quick action accessibility hints, macOS menu-bar quick action accessibility parity, macOS menu-bar model-residency controls, macOS menu-bar window and quit accessibility hints, macOS first-run Pairing QR primary action ordering, macOS Connection Recovery private-overlay toggle accessibility labels, macOS Connection Recovery and diagnostics disclosure accessibility state, macOS Connection Recovery Save Connection input state, macOS Connection Recovery Save Bootstrap Relay input state, macOS Connection Recovery bootstrap allocation token warning, macOS Connection Recovery host warning accessibility status, macOS Connection Recovery bootstrap relay removal accessibility labels, macOS Connection Recovery destructive removal action hints, macOS menu-bar Pairing QR active-session title, macOS Pairing QR route notice accessibility status, macOS Connection Recovery fallback-action accessibility hints, macOS CJK page-header accessibility spacing, macOS trusted-device refresh accessibility hint, Android trusted-runtime forget named accessibility label, Android trusted-runtime forget named click label, Android trusted-runtime forget confirmation action labels, Android trusted-runtime forget confirmation named message, Settings discovery action accessibility states, Settings discovery action accessibility labels, Android streaming cancel accessibility state, Android jump-to-latest accessibility state, Android jump-to-latest action labels, Android connected action accessibility states, Android connected action accessibility labels, Android connected action reconnect lockout, Android connected action compact layout, Android backend readiness refresh accessibility state, Android backend readiness refresh action labels, Android backend readiness banner bounded layout, Android generic runtime error banner bounded layout, Android model refresh action accessibility labels, Android route notice action accessibility labels, Android route notice accessibility summaries, Android route notice accessibility state, Android route notice QR recovery steps, Android connection status incomplete relay route live-region recovery, Android primary pairing cross-network route copy, Android pairing primary action accessibility labels, Android trusted-route connect label, Android manual diagnostic host QR-first guard, Android relay auth failure QR recovery notice, Android relay auth failure auto-retry stop, Android relay auth failure post-clear QR action, Android relay auth failure empty-chat copy, Android route rejection empty-chat copy, Android expired route empty-chat copy, Android expired remote-route QR recovery localization, Android expired relay route purge, Android relay secret store boundary, Android relay secret Base64 boundary, macOS relay secret store boundary, Android route.refresh terminal expiry state guard, Android QR runtime-name normalization, Android PairingStore incomplete relay cleanup, Android New Chat pairing-required disabled reason, Android New Chat action labels, Android permanent rail New Chat pairing gate, Android permanent rail Chat pairing gate, Android drawer rich chat search, Android drawer chat date grouping, Android drawer chat model metadata, Android chat history display-model search, Android drawer saved missing model recovery, Android drawer streaming lockout accessibility state, Android chat top-bar model picker streaming disabled state, Android chat top-bar model picker streaming transition lockout, Android chat top-bar stale saved model suppression, Android chat top-bar saved missing model recovery, Android chat top-bar compact long model name, Android chat top-bar model refresh action accessibility state, Android unknown model install guard, Android chat top-bar active chat title, Android chat top-bar model picker closed-button accessibility summary, Android chat top-bar model row action labels, Android search clear action labels, Android composer keyboard Send action, Android composer latest QR readiness hint, Android attachment-only composer readiness state, Android composer readiness live-region accessibility, Android route-recovery empty-state live-region accessibility, Android latest QR empty-state callback routing, Android chat empty-state primary action labels, Android reasoning toggle action labels, Android streaming assistant live-region accessibility, Settings expandable section action accessibility labels, Settings switch action accessibility labels, Settings memory action accessibility labels, Settings memory streaming lockout accessibility state, Settings memory add action accessibility labels, Settings memory add success live-region accessibility, Settings memory empty-state live-region accessibility, Settings memory delete confirmation action labels, Settings chat history model metadata, Android memory input readiness accessibility state, chat history bulk expander action labels, chat history bulk action accessibility labels, chat history destructive confirmation and cancel action labels."
echo "Covered Settings compact addendum: Android Settings trusted-runtime panel compact layout, Android trusted-runtime forget compact dialog layout, Android chat-history confirmation compact dialog layout, and Android memory delete compact dialog layout."
echo "Covered QR lease addendum: near-expiry remote relay lease QR renewal."
echo "Covered macOS stale GUI relay QR renewal addendum: ready stale or expired GUI-allocated relay leases are replaced with fresh relay id, secret, expiry, and nonce before QR generation."
echo "Covered remote QR lease monotonicity addendum: macOS runtime host accepts same-relay bootstrap lease renewal only when expiry advances and nonce changes."
echo "Covered relay probe addendum: non-consuming relay readiness probe is loopback-only by default, exposed relays close it unless diagnostic legacy opt-in is explicit, and Android route-level relay preflight treats a closed probe as unsupported before attempting authenticated relay connection."
echo "Covered Android relay reachability probe input guard addendum: physical relay probe rejects URL-shaped hosts, invalid ports, and malformed relay IDs before ADB access."
echo "Covered Android relay reachability probe route-material redaction addendum: physical relay probe JSON, stdout, and stderr omit raw relay IDs while preserving seeded redaction-test route-ready evidence."
echo "Covered Android relay reachability probe self-test proof-boundary addendum: fake-ADB relay probe artifacts mark fake_adb_redaction_self_test, keep observed adb serial absent, and keep live Android relay/route proof false."
echo "Covered relay probe/physical wrapper production proof-boundary addendum: Android relay probe and physical external-relay wrapper summaries keep production relay, production session-key exchange, and production end-to-end transport encryption proof false."
echo "Covered Android pairing deeplink am-start route-material redaction addendum: physical deeplink smoke stores and prints sanitized am start output without raw pairing or relay route material."
echo "Covered Android pairing deeplink am-start sanitizer self-test proof-boundary addendum: hidden no-device sanitizer self-test output carries an in-band not-phone-pairing-proof marker."
echo "Covered Android pairing failure artifact redaction addendum: physical deeplink smoke sanitizes failed activity/logcat artifacts and filtered stderr tails while preserving structured failure diagnostics."
echo "Covered relay bind addendum: tokenless AetherLinkRelay binds are loopback-only; wildcard/non-loopback binds require an allocation token and durable allocation storage."
echo "Covered relay allocation-token addendum: token-required AetherLinkRelay preflight rejects missing or wrong bearer tokens without creating route material; normal allocation additionally requires runtime-key proof."
echo "Covered runtime-key-bound relay allocation addendum: allocation-required relays accept canonical crypto=2 runtime-p256-v1 identities, verify same-socket allocation challenge proofs, return exact secret-free rt2 lease metadata, and leave the runtime host to own the 32-byte QR and traffic secret."
echo "Covered runtime-role admission addendum: strict relay runtime registration signs the current lease, nonce, generation, session nonce, and ephemeral key before the matcher can accept or replace a runtime role."
echo "Covered pairing trust-order addendum: macOS revalidates the stable transport binding before persisting a newly trusted client, and a binding change leaves the trust store empty."
echo "Covered relay allocation request unexpected metadata rejection addendum: AETHERLINK_RELAY allocate rejects unknown key=value request metadata before treating it as relay secret material."
echo "Covered relay opaque-id addendum: AetherLinkRelay derives rt2 relay IDs from the route token and runtime-key fingerprint, while keeping raw route tokens out of allocation stores and relay logs."
echo "Covered relay allocation opacity addendum: allocation responses, schema-v2 persisted bindings, and relay logs use opaque key-bound relay IDs without exposing raw route tokens."
echo "Covered Android private-overlay QR missing-scope diagnostic addendum: private, CGNAT, and ULA relay hosts without relay_scope=private_overlay map to latest-QR route recovery instead of generic invalid QR."
echo "Covered relay preflight route-material rejection addendum: relay_allocation_preflight accepts only preflight, crypto_version, and allocation_auth fields and rejects relay IDs, expiries, nonces, secrets, and other metadata."
echo "Covered relay preflight output redaction addendum: relay_allocation_preflight success JSON records the allocation capability contract without returning requested route tokens or allocated route material; preflight itself is not runtime-signed."
echo "Covered relay allocation renewal addendum: AetherLinkRelay renews an rt2 binding only for the same runtime key with an advancing generation compare-and-swap."
echo "Covered relay per-connection session key addendum: strict allocated relay peers exchange independent 128-bit session nonces, Android and macOS bind both nonces into shared frame keys, reconnects cannot reuse prior session ciphertext keys, encrypted peers reject legacy ready lines, and plaintext legacy peers reject nonce-bearing ready lines."
echo "Covered relay allocation store-load addendum: AetherLinkRelay schema-v2 persistence fails closed on legacy, corrupt, duplicate, or unknown-version stores instead of treating them as empty."
echo "Covered relay allocation lease lifecycle addendum: AetherLinkRelay uses a short default allocation TTL, persists public identity and lease metadata without secrets, and retains expired bindings as ownership tombstones."
echo "Covered relay wrapper dry-run allocation-token redaction addendum: run_allocation_relay --dry-run reports token-required mode without printing raw allocation-token values or argv-form token flags."
echo "Covered relay wrapper dry-run summary proof-boundary addendum: run_allocation_relay --dry-run --summary-json records no relay process, production relay, trusted-device, or optical QR proof while keeping allocation tokens redacted."
echo "Covered relay wrapper allocation-token argv redaction addendum: run_allocation_relay, run_different_network_dev_runtime, and no_adb_external_relay_pairing_smoke pass allocation tokens through environment variables so child process argv omits --allocation-token and the raw token while token-required allocation still works."
echo "Covered Android pairing deeplink allocation-token argv redaction addendum: android_pairing_deeplink_smoke and the physical external-relay wrapper pass allocation tokens through environment variables so relay/preflight child argv omits --allocation-token and the raw token."
echo "Covered no-ADB proof-boundary summary addendum: no_adb_external_relay_pairing_smoke separates runtime-host relay registration from trusted-device relay reachability, pairing, runtime.health, reconnect, and optical QR scan proof."
echo "Covered no-ADB external-relay URL host input redaction addendum: no_adb_external_relay_pairing_smoke rejects URL-shaped relay-host input without echoing provider/backend/route-token/relay-secret material."
echo "Covered no-ADB external-network proof-boundary addendum: no_adb_external_relay_pairing_smoke keeps operator-confirmed external-network relay proof, full-run trusted-device proof, and production relay proof false for emit-only and unverified QR summaries."
echo "Covered Swift relay allocation unexpected metadata rejection addendum: RelayAllocation.parseResponseLine rejects allocation responses with extra backend, provider, route-token, allocation-token, or relay-secret metadata fields."
echo "Covered relay allocation store unexpected metadata rejection addendum: RelayAllocationRegistry fails closed when schema-v2 bindings contain backend, provider, route-token, allocation-token, relay-secret, challenge, or signature metadata."
echo "Covered relay preflight failure-output redaction addendum: relay_allocation_preflight redacts malformed preflight response bodies from stderr while preserving a safe failure reason."
echo "Covered different-network relay endpoint input redaction addendum: run_different_network_dev_runtime rejects URL-shaped relay endpoints and malformed endpoint-list values without echoing provider, backend, route-token, or relay-secret material in stderr or summary JSON."
echo "Covered relay preflight unexpected-field rejection addendum: relay_allocation_preflight rejects preflight responses with extra metadata fields without echoing those fields or values."
echo "Covered relay preflight response canonicality addendum: relay_allocation_preflight requires boolean preflight=true, integer crypto_version=2, and allocation_auth=runtime-p256-v1 without coercion."
echo "Covered relay preflight host input guard addendum: relay_allocation_preflight rejects URL-shaped relay hosts before network access without echoing host, provider, backend, or route-token material."
echo "Covered QR production bootstrap addendum: QR production relay bootstrap verifier requires runtime public key, route token, and complete relay route material."
echo "Covered Android product QR bootstrap addendum: normal QR scans require runtime public key, route token, and complete remote route material; diagnostic identity-only fallback must opt out explicitly."
echo "Covered Android client-side runtime proof rejection addendum: trusted relay reconnect rejects invalid nonce-bound runtime_signature and runtime_key_fingerprint mismatch before sending auth.response or runtime.health and surfaces runtime_authentication_failed."
echo "Covered relay allocation request input rejection addendum: AETHERLINK_RELAY allocate rejects blank allocation_token/auth values and blank or whitespace requested relay secrets before issuing route material."
echo "Covered relay allocation base64 requested-secret addendum: AETHERLINK_RELAY allocate accepts base64-style requested relay secrets with +, /, and = padding while still rejecting backend/provider/request metadata fields."
echo "Covered relay allocation response field validation addendum: allocation response lines re-run relay_id, relay_secret, relay_expires_at, and relay_nonce validation after JSON decoding."
echo "Covered Swift relay allocation relay-id canonicality addendum: RelayAllocation rejects URL-shaped, path-shaped, query, fragment, user-info, host:port, oversized, blank, and whitespace-mutated relay IDs before allocation response or persisted ticket use."
echo "Covered Android accepted-pairing incomplete relay route addendum: accepted pairing rejects incomplete relay route material instead of falling back to a diagnostic direct endpoint."
echo "Covered Android accepted-pairing incomplete P2P route addendum: accepted pairing rejects incomplete p2p_rendezvous material instead of falling back to a diagnostic direct endpoint."
echo "Covered Android initial pairing QR expired relay lease rejection addendum: accepted pairing refuses to create trusted runtime storage from already-expired relay QR material."
echo "Covered Android initial pairing QR expired P2P record rejection addendum: accepted pairing refuses to create trusted runtime storage from already-expired P2P rendezvous QR material."
echo "Covered Android accepted-pairing relay secret restore boundary addendum: accepted relay pairing preserves complete relay host/id/secret/lease/nonce material for trusted runtime restore."
echo "Covered Android accepted-pairing runtime identity mismatch rejection addendum: accepted pairing creates trust only when result device id, fingerprint, and public key match the pending QR identity."
echo "Covered rejected pairing addendum: Android rejected relay QR pairing clears pending route material, stale pairing code, and pending relay secret references."
echo "Covered accepted pairing direct-endpoint cleanup addendum: Android accepted pairing drops direct endpoint material before trusted runtime storage."
echo "Covered stale relay refresh addendum: Android authenticated route.refresh keeps the current relay route and schedules retry when refreshed relay material reuses the active nonce or lease."
echo "Covered Android route.refresh timing policy addendum: Android route.refresh renewal and retry delays stay inside the active remote-route lease window."
echo "Covered Android mixed remote-route lease boundary addendum: urgent renewal runs immediately instead of at or after expiry, while mixed P2P and relay helpers select the earliest active and retryable leases independently."
echo "Covered Android near-expiry route-refresh immediate dispatch addendum: authenticated relay and P2P sessions with only the minimum lease window each send exactly one route.refresh without advancing the coroutine scheduler clock."
echo "Covered Android mixed-route lease retry fallback addendum: an active P2P session refreshes immediately for an urgent relay lease, then retries a transient failure from the alternate retryable P2P lease without dialing relay or dropping connection state."
echo "Covered Android mixed-route relay-fallback retry addendum: failed P2P connection falls back to relay, refreshes immediately for the urgent P2P lease, then retries a transient failure from the alternate retryable relay lease without redialing routes or dropping connection state."
echo "Covered Android non-retryable route-refresh contract addendum: retryable=false stops automatic route.refresh retries while preserving the authenticated connection, trusted route material, and latest-QR recovery guidance."
echo "Covered Android route.refresh scalar route-material decode addendum: Android RouteRefreshPayload rejects schema-invalid scalar relay and P2P route material during JSON DTO decode, including noncanonical opaque route values, invalid relay ports, nonpositive expiries, unsupported relay_scope values, unsupported p2p_class values, oversized encrypted bodies, and unsupported p2p_protocol_version values before trusted route storage, route-refresh retry handling, live relay/P2P behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android route.refresh complete route-material decode addendum: Android RouteRefreshPayload accepts empty route.refresh responses and complete relay or P2P route-material families, but rejects identity-only, missing-runtime-identity, partial relay, relay_scope-only, partial P2P, and missing-p2p_class payloads during JSON DTO decode before trusted route storage, route-refresh retry handling, live relay/P2P behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android authenticated relay route.refresh scheduling/retry addendum: authenticated relay sessions send route.refresh before lease expiry and retry retryable route.refresh errors inside the active lease."
echo "Covered Android authenticated route.refresh default-off addendum: production Android does not advertise or send authenticated route.refresh unless explicitly enabled for diagnostic coverage."
echo "Covered PairingStore direct endpoint cleanup addendum: Android trusted runtime persistence drops current and legacy direct host/port fields."
echo "Covered pending pairing direct-endpoint cleanup addendum: Android pending pairing route storage drops direct QR host/port fields."
echo "Covered Android pending pairing identity canonicality addendum: pending pairing route storage rejects whitespace-mutated or oversized pairing nonce, runtime device id, and fingerprint values, and whitespace-mutated pairing codes, instead of trimming them into pending trusted identity material."
echo "Covered Android pending pairing route-token canonicality addendum: pending pairing route storage rejects whitespace-mutated or oversized route_token values instead of trimming them into pending trusted identity material."
echo "Covered Android app relay route-material canonicality addendum: pending route storage and RuntimeRemoteRoutePlanner reject whitespace-mutated or oversized relay hosts, relay ids, frame secrets, nonces, and scopes before pending restore, trusted reconnect target state, or prepared route planning."
echo "Covered trusted route fallback addendum: Android trusted reconnect drops trusted last-known direct endpoint fallback."
echo "Covered trusted route UI addendum: Android route UI treats trusted last-known direct endpoints as latest-QR recovery."
echo "Covered trusted route core addendum: Android core transport default resolver ignores trusted last-known direct endpoints."
echo "Covered Android relay route-material canonicality addendum: relay route preparation rejects whitespace-mutated relay hosts, URL-shaped hosts, relay IDs, frame secrets, anti-replay nonces, and oversized opaque relay route material before connector use."
echo "Covered Android pairing/trusted relay host canonicality addendum: QR parsing, PairingStore persistence/restore, route planning, and route UI reject whitespace-mutated, URL-shaped, path, query, fragment, or userinfo relay hosts before trusted route use."
echo "Covered Android stored route-token canonicality addendum: PairingStore rejects whitespace-mutated or oversized stored route tokens on read and write before trusted discovery or remote route preparation can use them."
echo "Covered Android stored trusted identity canonicality addendum: PairingStore rejects whitespace-mutated or oversized stored runtime device ids, fingerprints, and public keys before trusted runtime restore or persistence."
echo "Covered Android trusted relay scope canonicality addendum: PairingStore rejects blank, unknown, case-mutated, and whitespace-mutated runtime_relay_scope values on write/read before trusted relay restore or persistence."
echo "Covered Android pairing QR relay-secret canonicality addendum: relay_secret, remote_secret, route_secret, rendezvous_secret, and rs reject whitespace-mutated values while preserving base64-style +, /, and = characters."
echo "Covered Android pairing QR service_type discovery-hint sanitization addendum: pairing QR parsing and the shared QR schema accept only AetherLink discovery service hints and reject URL-shaped, backend, provider, model, or whitespace-mutated service_type values."
echo "Covered Android QR scanner decoded-result classification addendum: scanner raw-value batches ignore blank frames, prioritize valid AetherLink route QR values, and preserve invalid-pairing feedback ahead of unsupported QR feedback."
echo "Covered Android pairing QR duplicate query-key rejection addendum: decoded pairing QR query keys cannot repeat before field selection, alias handling, or route material assembly."
echo "Covered shared QR verifier duplicate query-key rejection addendum: rendered QR artifact verification rejects repeated decoded query keys before route material validation, matching Android parser duplicate-key rejection."
echo "Covered Android pairing QR unknown query-key rejection addendum: decoded pairing QR query keys outside the shared schema allowlist fail before identity, relay, P2P, backend, or model-shaped metadata can be ignored."
echo "Covered shared QR verifier unknown query-key rejection addendum: rendered QR artifact verification rejects decoded query keys outside the shared schema allowlist before route material validation."
echo "Covered Android pairing QR semantic alias conflict rejection addendum: decoded QR aliases for the same semantic field, including relay scope aliases, fail before field selection or route material assembly."
echo "Covered Android pairing QR relay alias-family isolation addendum: relay, remote, route, rendezvous, and compact relay material families cannot be mixed to assemble one QR route."
echo "Covered shared pairing QR relay alias-family schema addendum: protocol schema rejects mixed canonical, remote, route, rendezvous, and compact relay aliases while preserving valid single-family QR payloads."
echo "Covered shared pairing QR semantic alias exclusivity schema addendum: protocol schema rejects multiple decoded aliases for the same QR field before artifacts can satisfy conflicting identity, route-token, local-endpoint, relay-id, or relay-scope values."
echo "Covered shared pairing QR relay-scope alias exclusivity schema addendum: protocol schema rejects multiple relay_scope, remote_scope, route_scope, or rsc aliases before QR artifacts can satisfy conflicting scopes."
echo "Covered shared pairing QR usb-reverse loopback host schema addendum: protocol schema checker pins usb_reverse across relay_scope, remote_scope, route_scope, and rsc as explicit debug USB reverse route material, and QR verification rejects loopback local-relay artifacts unless the scope is exactly usb_reverse."
echo "Covered shared pairing QR route-scope private-overlay schema addendum: protocol schema accepts route_scope=private_overlay for route_* relay aliases and requires it for private route_host literals like Android parsing."
echo "Covered Android pairing QR P2P alias-family isolation addendum: pairing QR parsing rejects mixed canonical and compact P2P rendezvous aliases before route material is assembled."
echo "Covered Android pairing QR P2P protocol-version canonicality addendum: pairing QR parsing rejects leading-zero, plus-prefixed, and compact non-canonical P2P protocol version values before route material is accepted."
echo "Covered shared pairing QR P2P alias-family schema addendum: protocol schema rejects mixed canonical and compact P2P rendezvous aliases while preserving valid single-family QR payloads."
echo "Covered P2P route prep addendum: Android p2p_rendezvous route preparation contract and relay fallback ordering."
echo "Covered Android P2P route-family isolation addendum: p2p_rendezvous route preparation carries opaque record/body/nonce material without relay ids, relay frame secrets, direct host/port fields, or paired route-token session material."
	echo "Covered Android route-token remote material isolation addendum: paired runtime route tokens bind identities but cannot be reused as P2P session/rendezvous material or relay route IDs."
		echo "Covered Android identity-only no-route transport boundary addendum: identity-only trusted targets resolve local, P2P, and relay diagnostics but fail closed without connectable route material or direct TCP calls."
		echo "Covered Android prepared relay route ordering addendum: prepared relay routes run before stale trusted endpoints and fresh discovery, while fresh discovery remains fallback when relay fails."
			echo "Covered Android trusted remote-route target endpoint-hint suppression addendum: trusted reconnect targets with saved relay or P2P route material omit stale direct endpoint hints before route planning."
					echo "Covered Android saved relay reconnect pinned-identity rejection addendum: trusted reconnect refuses saved relay route planning when the pinned runtime fingerprint or public key mismatches."
					echo "Covered Android trusted relay reconnect scope eligibility addendum: trusted reconnect rejects scope-less loopback/private saved relay routes while allowing explicit usb_reverse and private_overlay scopes."
					echo "Covered Android authenticated relay reconnect route.refresh fresh lease addendum: real relay reconnect accepts and persists authenticated route.refresh material only when the relay nonce is fresh and the lease advances."
								echo "Covered Android saved relay lease reconnect eligibility addendum: trusted reconnect uses complete saved QR relay lease metadata without manual endpoints and rejects expired or incomplete saved relay leases before route planning."
							echo "Covered Android pending relay QR planning eligibility addendum: pending pairing relay QR material creates identity-only targets without direct endpoints, respects relay lease expiry, and overrides saved relay routes while pairing."
							echo "Covered Android pairing relay QR direct-endpoint suppression addendum: relay-backed pairing QR targets ignore stray fixed host/port hints and stay identity/relay-bound before trust creation."
							echo "Covered Android pairing P2P QR direct-endpoint suppression addendum: P2P-backed pairing QR targets ignore stray fixed host/port hints and stay identity/P2P-route-bound before trust creation."
						echo "Covered Android route-refresh QR relay add-route addendum: fresh relay route-refresh QR material adds complete relay host/id/secret/lease/nonce material to an existing trusted runtime while preserving pinned runtime identity."
						echo "Covered Android route-refresh QR P2P add-route addendum: fresh P2P route-refresh QR material adds complete p2p_rendezvous record/body/lease/nonce material to an existing trusted runtime while dropping stale direct endpoints."
echo "Covered Android route-refresh QR fixed-endpoint fallback removal addendum: fresh relay route-refresh QR material drops stale trusted direct host/port fallback."
echo "Covered Android route-refresh QR direct-only rejection addendum: direct-only route-refresh QR cannot replace an existing trusted remote route with fixed host/port material."
echo "Covered Android route-refresh QR route-token rotation addendum: latest QR can rotate route tokens and relay material for the same pinned runtime identity."
echo "Covered Android route-refresh QR pinned-identity rejection addendum: route-refresh QR must match an existing trusted runtime identity and public key before route storage changes."
echo "Covered Android route-refresh QR expired-or-incomplete relay rejection addendum: expired route-refresh QR leases and relay routes missing relay_secret fail closed before trusted storage changes."
echo "Covered Android route-refresh QR expired-or-incomplete P2P rejection addendum: expired P2P route-refresh QR records and incomplete p2p_rendezvous material fail closed before trusted storage changes."
echo "Covered Android route-refresh QR stale material rejection addendum: route-refresh QR rejects reused relay nonces, reused P2P record IDs, reused P2P anti-replay nonces, and non-advancing relay or P2P expiries before trusted route storage changes."
echo "Covered Android route-refresh QR P2P relay-scope isolation addendum: P2P route-refresh QR material with stray relay scope fails closed unless complete relay material is present."
echo "Covered Android app P2P encrypted body 2048-byte route material addendum: app route planning, trusted reconnect dispatch, authenticated route.refresh, and pending route storage preserve max-sized opaque P2P bodies."
echo "Covered Android P2P connector dispatch addendum: identity-only trusted targets with prepared P2P material use RuntimePeerToPeerConnector without direct TCP fallback."
echo "Covered Android remote route direct transport boundary addendum: prepared P2P or relay routes never fall through to direct TCP when the dedicated connector is unavailable."
echo "Covered P2P QR planning addendum: Android QR-carried opaque P2P rendezvous records persist as pending route material and plan before relay."
echo "Covered Android pending dual-route QR authority addendum: matching pending QR P2P and relay material plans in order, stays pinned to the QR runtime identity, does not reuse route_token as route material, and supersedes saved trusted routes."
echo "Covered P2P trusted-runtime restore addendum: Android trusted P2P rendezvous material persists after accepted pairing and restores as a prepared remote route without direct endpoint fallback."
echo "Covered remote route mismatch addendum: Android remote route identity mismatch QR recovery."
echo "Covered P2P failure recovery addendum: Android failed P2P route without saved relay fallback scans a fresh QR with relay or private overlay details."
echo "Covered long-inactivity memory summary draft protocol listing addendum: authenticated memory.summary.drafts.list returns owner-scoped active visible-transcript drafts without writing runtime memory."
echo "Covered review-required long-inactivity memory summary generation addendum: authenticated memory.summary.draft.generate validates exact owner-scoped stale guards and an installed runtime-host local chat model, sends only bounded visible transcript excerpts, strips reasoning, requires strict bounded JSON, caches by deterministic draft id, revalidates after inference, never auto-approves memory, and preserves deterministic preview on failure."
echo "Covered Android transient memory summary generation addendum: Android Settings exposes Generate Summary only for deterministic drafts, locks concurrent decisions while generating, labels generated summaries for review, refreshes stale drafts, and keeps generated summaries out of RuntimeLocalStore."
echo "Covered memory.summary.drafts.list unknown metadata rejection addendum: RuntimeDevServer memory.summary.drafts.list payloads reject response-only drafts, backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime chat or memory store dispatch."
echo "Covered memory.summary.drafts.list invalid allowed type rejection addendum: RuntimeDevServer memory.summary.drafts.list payloads reject string and fractional limit values before runtime chat or memory store dispatch."
echo "Covered Android memory summary draft review addendum: Android requests memory.summary.drafts.list, renders suggested memories in Settings Memory, approves memory.summary.draft.approve, and keeps draft previews out of device storage."
echo "Covered long-inactivity memory summary draft approval addendum: authenticated memory.summary.draft.approve writes idempotent owner-scoped runtime memory and hides approved drafts from later review lists."
echo "Covered memory.summary.draft.approve unknown metadata rejection addendum: RuntimeDevServer memory.summary.draft.approve payloads reject response-only status and entry, backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime chat store recomputation or memory store mutation."
echo "Covered memory.summary.draft.approve invalid allowed type rejection addendum: RuntimeDevServer memory.summary.draft.approve payloads reject blank draft_id, non-string or blank content, non-boolean enabled, non-string or blank expected_session_id, and string or fractional expected_source_message_count before runtime chat store recomputation or memory store mutation."
echo "Covered long-inactivity memory summary draft dismiss addendum: authenticated memory.summary.draft.dismiss stores owner-scoped dismiss decisions, hides dismissed drafts, and does not write runtime memory."
echo "Covered memory.summary.draft.dismiss unknown metadata rejection addendum: RuntimeDevServer memory.summary.draft.dismiss payloads reject response-only status and dismissed_at, backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime chat store recomputation or memory store mutation."
echo "Covered memory.summary.draft.dismiss invalid allowed type rejection addendum: RuntimeDevServer memory.summary.draft.dismiss payloads reject blank draft_id, non-string or blank expected_session_id, and string or fractional expected_source_message_count before runtime chat store recomputation or memory store mutation."
echo "Covered approved memory source metadata addendum: approved long-inactivity memory entries preserve bounded visible-transcript source metadata through runtime storage, memory.list, protocol DTOs, and Android in-memory state while device storage remains redacted."
echo "Covered approved memory source review UI addendum: Android Settings Memory shows approved-memory source metadata on demand without exposing the full transcript by default."
echo "Covered macOS Runtime Memory approved source review UI addendum: Runtime Memory Inspector shows approved-memory source title/range metadata, keeps source excerpts collapsed and bounded, and avoids draft/session/debug identifiers."
echo "Covered P2P canonical material addendum: Android pending, trusted, and route.refresh P2P rendezvous records reject whitespace-mutated opaque route values."
echo "Covered P2P app route addendum: Android ViewModel injects a P2P connector, attempts saved opaque P2P before relay, and falls back to relay without direct endpoint fallback."
echo "Covered P2P route-refresh lease addendum: Android P2P-only trusted routes schedule, retry, and expire route.refresh renewal from the P2P rendezvous record lease."
echo "Covered P2P route-refresh replay addendum: Android route.refresh rejects reused or non-advancing P2P rendezvous records before storage."
echo "Covered Android route.refresh P2P noncanonical rejection addendum: authenticated route.refresh rejects whitespace-mutated P2P class, record id, encrypted body, and anti-replay nonce before trusted storage changes."
echo "Covered Android route-refresh QR optional-public-key relay update addendum: route-refresh QR without runtime_public_key can update complete relay route material for an already pinned runtime while preserving the pinned public key."
echo "Covered Android route-refresh QR optional-public-key P2P update addendum: route-refresh QR without runtime_public_key can update complete p2p_rendezvous material for an already pinned runtime while preserving the pinned public key."
echo "Covered stale P2P refresh addendum: Android authenticated route.refresh keeps the current P2P rendezvous route and schedules retry when refreshed P2P material reuses the active record or lease."
echo "Covered Android trusted P2P restore discovery-suppression addendum: saved opaque P2P routes suppress Bonjour/local discovery and reconnect from prepared route material without endpoint hints."
echo "Covered Android opaque route material size-bound addendum: QR route tokens, relay ids/secrets/nonces, and P2P record/body/nonces are capped before parser, trusted restore, and P2P route preparation."
echo "Covered Android trusted relay store canonicality addendum: PairingStore rejects whitespace-mutated or oversized stored relay ids, secrets, and nonces before trusted restore or write persistence."
echo "Covered shared route material schema size-bound addendum: pairing QR and route.refresh schemas cap opaque route ids, tokens, secrets, nonces, and P2P encrypted bodies before parser or runtime handling."
echo "Covered Android remote route expiry connector guard addendum: prepared remote route security material must be complete and unexpired before any P2P or relay connector attempt."
echo "Covered Android remote route identity binding addendum: prepared P2P or relay route material must match the trusted runtime identity before any connector attempt."
echo "Covered macOS pairing QR payload shape addendum: canonical QR payloads can omit diagnostic endpoint hints, include relay secrets when route material is present, and compact camera QR payloads use short aliases."
echo "Covered macOS pairing QR relay-scope allowlist addendum: PairingCoordinator emits only remote, private_overlay, usb_reverse, or local_diagnostic route scopes before QR payload generation."
echo "Covered macOS pairing QR relay host-scope eligibility addendum: PairingCoordinator emits relay QR route material only when public hosts use remote or no scope, private-overlay hosts use private_overlay, and loopback hosts use usb_reverse."
echo "Covered macOS pairing QR relay host canonical emission addendum: PairingCoordinator emits normalized relay_host values after host/scope eligibility checks, including lowercased no-trailing-dot DNS names and bracketless IPv6 literals."
echo "Covered macOS pairing QR opaque route-material canonicality addendum: PairingCoordinator omits whitespace-mutated or oversized optional opaque QR values before emitting relay, P2P, runtime public-key, or route-token query material."
echo "Covered macOS pairing QR route-material numeric validity addendum: PairingCoordinator omits invalid relay ports and non-positive relay or P2P route expiries before emitting relay or P2P QR families."
echo "Covered macOS P2P QR canonical generation addendum: canonical macOS pairing QR payloads emit complete p2p_rendezvous route material while keeping relay and direct endpoint aliases absent."
echo "Covered macOS P2P QR generation addendum: macOS pairing QR generation emits the shared opaque P2P rendezvous record family."
echo "Covered relay control-line framing addendum: relay handshake, allocation, and probe control lines require trailing newlines, and readiness probes do not consume waiting runtimes."
echo "Covered relay control-line relay-id canonicality addendum: runtime/client handshakes and readiness probes reject whitespace, oversized, URL-shaped, path-shaped, query, fragment, user-info, and host:port relay ids before matching."
echo "Covered relay readiness runtime-only probe addendum: Relay readiness requires a waiting runtime, not just any pending peer."
echo "Covered authenticated model list runtime-boundary addendum: authenticated RuntimeDevServer relay models.list exposes runtime-mediated model metadata without backend URLs, provider endpoints, remote_host, cloud suggestions, or direct Ollama/LM Studio route material."
echo "Covered runtime mock attachment addendum: authenticated relay chat.send document attachment, non-vision image rejection, vision image success, and pulled model chat smoke."
echo "Covered pre-auth unknown metadata rejection addendum: RuntimeDevServer pairing.request, hello, and auth.response payloads reject response-only pairing/auth fields, runtime identity forgery, backend_url, backend_credentials, provider_url, route_token, relay_secret, requested_route_token, workspace_id, permission_grant, source_path, and source_control_status before trust, challenge, or authentication mutation."
echo "Covered pairing.request blank allowed field rejection addendum: RuntimeDevServer pairing.request payloads reject blank pairing_nonce, pairing_code, device_id, device_name, and public_key before failed-attempt accounting or trust mutation."
echo "Covered empty runtime request unknown metadata rejection addendum: RuntimeDevServer runtime.health, models.list, and route.refresh payloads reject response-only status, models, route material, backend_url, backend_credentials, provider_url, route_token, relay_secret, requested_route_token, workspace_id, permission_grant, source_path, and source_control_status before backend or route-refresh dispatch."
echo "Covered RuntimeDevServer non-object payload decode rejection addendum: authenticated relay smoke rejects runtime.health array payloads, models.list string payloads, and route.refresh null payloads with invalid_payload while keeping the connection usable for follow-up runtime.health."
echo "Covered chat.send top-level payload metadata rejection addendum: RuntimeDevServer chat.send payloads reject project_id, workspace_id, retrieval_context, permission_grant, and backend_url before backend dispatch."
echo "Covered chat.send invalid allowed type rejection addendum: RuntimeDevServer chat.send payloads reject blank session_id, blank model, non-string locale, non-enum message role, non-enum attachment type, and non-string attachment name, data_base64, or text before backend dispatch."
echo "Covered chat.title.request unknown metadata rejection addendum: RuntimeDevServer chat.title.request payloads reject title, project_id, workspace_id, retrieval_context, permission_grant, backend_url, backend_credentials, provider_url, route_token, relay_secret, requested_route_token, source_path, source_control_status, and tool_results before backend title generation."
echo "Covered chat.title.request invalid allowed type rejection addendum: RuntimeDevServer chat.title.request payloads reject blank model and non-string locale before backend title generation."
echo "Covered chat.title.request blank session_id rejection addendum: RuntimeDevServer chat.title.request payloads reject blank session_id before backend title generation."
echo "Covered chat.send message metadata rejection addendum: RuntimeDevServer chat.send messages reject source_path, workspace_id, source_control_status, backend_url, and trusted_source before backend dispatch."
echo "Covered attachment source metadata rejection addendum: RuntimeDevServer chat.send attachments reject source_path, workspace_id, source_control_status, and backend_url before backend dispatch."
echo "Covered models.pull unknown metadata rejection addendum: RuntimeDevServer models.pull payloads reject backend_url, provider_url, route_token, relay_secret, requested_route_token, workspace_id, and permission_grant before backend pull dispatch."
echo "Covered models.pull invalid allowed type rejection addendum: RuntimeDevServer models.pull payloads reject non-string, empty, or blank model values and non-ollama legacy backend values before backend pull dispatch."
echo "Covered chat.cancel unknown metadata rejection addendum: RuntimeDevServer chat.cancel payloads reject backend_url, route_token, relay_secret, workspace_id, permission_grant, and source_control_status before backend cancel dispatch."
echo "Covered chat.cancel blank target rejection addendum: RuntimeDevServer chat.cancel payloads reject blank target_request_id values before backend cancel dispatch."
echo "Covered chat.cancel acknowledgement target id schema parity addendum: protocol schema and checker require chat.cancel acknowledgement target_request_id to stay nonblank like the runtime echo."
echo "Covered relay ciphertext boundary addendum: authenticated relay smoke checks encrypted frame bodies for AI protocol payloads, model lists, prompts, files, memory, backend credentials, backend URLs, model commands, cancel, history, memory.list query/search, pairing bootstrap, and route.refresh route-material plaintext markers."
echo "Covered relay ciphertext sensitive-class canary addendum: authenticated relay smoke checks encrypted frame bodies for backend credential, backend URL, model command payload, prompt, file payload label, model-list response, and memory plaintext markers."
echo "Covered RuntimeDevServer memory.list query ciphertext marker addendum: authenticated relay ciphertext boundary includes the memory.list query request id, memory id, trimmed query text, and query/search/snippet JSON keys."
echo "Covered macOS RelayPeerClient ciphertext addendum: macOS RelayPeerClient sends nonce-bound encrypted runtime frame bodies after relay readiness."
echo "Covered Android relay TCP ciphertext addendum: Android RuntimeRelayTcpClient encrypts sent frame bodies and decrypts nonce-bound runtime responses on a real socket channel."
echo "Covered runtime pairing relay smoke addendum: RuntimeDevServer relay rejected pairing request leaves device untrusted before accepted pairing."
echo "Covered RuntimeDevServer accepted pairing runtime identity confirmation addendum: accepted relay pairing.result must echo the QR-pinned runtime id, runtime_public_key, and runtime_key_fingerprint before the smoke treats pairing as trusted."
echo "Covered initial pairing mutual P-256 proof addendum: Android signs the QR-pinned pairing request, the runtime verifies client key possession before trust, accepted pairing results are request-digest and transport-bound runtime signatures, and both sides persist trust only after verification."
echo "Covered runtime auth relay smoke addendum: RuntimeDevServer relay unauthenticated runtime command and untrusted hello rejection."
echo "Covered RuntimeDevServer relay trusted hello runtime proof addendum: file-backed RuntimeDevServer identity signs relay auth.challenge and the smoke verifies runtime_signature against the QR-pinned runtime_public_key."
echo "Covered untrusted-client rejection addendum: LocalRuntimeMessageRouter rejects unknown-device hello with non-retryable pairing_required while RuntimeDevServer relay smoke rejects unauthenticated runtime commands and untrusted hello."
echo "Covered macOS untrusted hello unit rejection addendum: LocalRuntimeMessageRouter returns non-retryable pairing_required for unknown-device hello before trusted auth or runtime command access."
echo "Covered macOS runtime identity fallback signing addendum: file-backed runtime identity fallback signs nonce-bound auth challenges with the persisted public-key fingerprint."
echo "Covered macOS trusted hello runtime proof addendum: trusted hello auth.challenge includes a verifiable runtime_signature and runtime_key_fingerprint when a runtime signer is available."
echo "Covered macOS pairing abuse structured rejection addendum: repeated invalid, expired, and inactive pairing requests return structured non-trusting rejections without creating trusted devices."
echo "Covered RuntimeDevServer malformed pairing identity smoke addendum: RuntimeDevServer relay malformed pairing identity rejection keeps the device untrusted while preserving the active QR for a later valid pairing."
echo "Covered RuntimeDevServer consumed pairing QR reuse smoke addendum: RuntimeDevServer relay rejects consumed pairing QR reuse and keeps the second device untrusted."
echo "Covered RuntimeDevServer rejected pairing connection auth-boundary addendum: RuntimeDevServer relay keeps rejected and consumed pairing connections unauthenticated."
echo "Covered RuntimeDevServer raw nonce auth relay smoke addendum: RuntimeDevServer relay rejects raw nonce auth signatures and keeps the connection unauthenticated."
echo "Covered RuntimeDevServer auth replay relay smoke addendum: RuntimeDevServer relay rejects replayed auth responses and superseded challenge nonces while preserving valid auth paths."
echo "Covered runtime auth revocation smoke addendum: RuntimeDevServer relay trusted-device revocation clears authenticated sessions."
echo "Covered physical relay QA addendum: Android device relay-id readiness probe."
echo "Covered physical external-relay summary addendum: invalid-host no-device summaries keep endpoint and route probe coverage false, child probe summaries explicit, and recovery caveats present."
echo "Covered physical external-relay requested serial evidence binding addendum: invalid-host no-device summaries preserve requested adb serial, keep observed adb serial absent, and record the redacted --serial command evidence."
echo "Covered physical external-relay URL host input redaction addendum: URL-shaped wrapper relay hosts fail before child smoke execution while summary, log, stdout, and stderr keep only safe invalid-host labels."
echo "Covered physical external-relay probe-summary route-material redaction addendum: wrapper probe_summaries preserve seeded redaction-test evidence while stripping raw relay and route material from embedded child probe artifacts."
echo "Covered physical external-relay probe-summary self-test proof-boundary addendum: seeded redaction self-tests stay marked as self-tests and keep live Android probe proof, physical external-relay proof, and physical external-relay success false."
echo "Covered physical external-relay runtime-log temporary route-material summary addendum: wrapper summaries classify runtime.log temporary pairing and route material without embedding raw pairing URI values."
echo "Covered physical external-relay different-network confirmation gate addendum: unconfirmed required different-network physical QA exits before smoke execution or artifact writes."
echo "Covered Android relay QR idempotency addendum: duplicate compact relay QR scans send one pairing request on the active relay connection."
echo "Covered duplicate relay QR idempotency addendum: duplicate compact relay QR scans send one pairing request on one active relay connection without falling back to direct TCP."
echo "Covered Android route-refresh QR active-connection reuse addendum: route-refresh QR scans update saved relay and P2P route material while reusing the active connection and avoiding duplicate relay or peer dials."
echo "Covered Android QR pairing preemption addendum: new QR pairing can preempt untrusted or different-runtime active connections while same-runtime QR keeps the trusted session active."
echo "Covered Android product QR scanner policy addendum: scanner raw-value handling accepts route-capable compact relay QR and rejects identity-only or expired product QR before consuming camera results."
echo "Covered Android QR policy addendum: Android product QR remote-route requirement and identity-only scanner rejection."
echo "Covered Android direct model-provider route block addendum: selected, discovered, USB reverse, and emulator direct routes reject Ollama and LM Studio backend ports before any client-side TCP connection."
echo "Covered Android Bonjour discovery identity metadata boundary addendum: trusted Bonjour/local discovery routes require matching route-token or pinned identity metadata, advertised route-token cannot fall back to legacy identity metadata when unpinned, and metadata-less or mismatched discoveries remain non-trusted diagnostics."
echo "Covered Android Bonjour TXT receive canonicality addendum: Bonjour TXT route_token values reject whitespace mutation, oversized values, malformed UTF-8, and forbidden discovery metadata before trusted discovery matching."
echo "Covered Android pending route-less QR no saved relay fallback addendum: pending pairing QR without remote route material does not borrow a saved relay route from the trusted runtime."
echo "Covered Android diagnostic identity-only discovery wait addendum: diagnostic identity-only QR starts discovery and waits for a route instead of manufacturing a connection target."
echo "Covered Android relay frame cryptor nonce-bound vector addendum: fixed ciphertext vectors bind relay_secret and relay_nonce, and mismatched route nonces cannot decrypt relay frames."
echo "Covered Android relay TCP ready timeout addendum: RuntimeRelayTcpClient fails within the route timeout when the relay TCP socket never sends a ready line."
echo "Covered macOS RelayPeerClient registration/ready timeout addendum: RelayPeerClient defaults to a physical-QR-tolerant 45s control-line timeout and still fails within a bounded override when the relay accepts TCP but never sends AETHERLINK_RELAY registered or ready."
echo "Covered Android relay concurrent encrypted send serialization addendum: RuntimeRelayTcpClient serializes concurrent encrypted sends without corrupting nonce-bound relay frames."
echo "Covered Android chat history addendum: Settings chat history selected active chat state."
echo "Covered Android chat empty-state addendum: Android no-model empty chat header picker guidance."
echo "Covered Android chat empty-state addendum: Android uninstalled selected model install-or-choose guidance."
echo "Covered provider addendum: Android provider label normalization."
echo "Covered runtime provider addendum: macOS duplicate provider registration guard."
echo "Covered model-residency smoke addendum: macOS model-switch unload, same-model unload suppression, idle-timeout unload, runtime-host-owned manual model unload, provider-specific unload-failure reporting, Ollama unload wire format, LM Studio unload wire format, and provider adapter structured unload-failure errors."
echo "Covered model-residency unload behavior addendum: macOS model-switch unload, same-model unload suppression, idle-timeout unload, Ollama unload wire format, and LM Studio unload wire format stay in the default no-device gate."
echo "Covered LM Studio vision image native/fallback request shape addendum: LM Studio image attachments use native /api/v1/chat image input first, then OpenAI-compatible vision content when the native request is rejected."
echo "Covered macOS model-residency foreground completion addendum: terminal chat done events clear in-flight residency before a client observes completion."
echo "Covered model-residency foreground completion cleanup addendum: chat .done events are observed only after aggregate model residency clears in-flight generation state."
echo "Covered macOS unknown unqualified model routing addendum: runtime-host model routing rejects unknown unqualified model ids instead of falling back to Ollama or another default provider."
echo "Covered macOS qualified provider model routing rejection addendum: provider-qualified chat model ids must be reported by that exact local provider before runtime routing."
echo "Covered runtime auth gate addendum: unauthenticated models.list, models.pull, chat.send, chat.cancel, route.refresh, chat history/title/session mutation, memory list/upsert/delete, and memory-summary draft command rejection."
echo "Covered route.refresh addendum: route.refresh malformed relay material validation, route.refresh private-overlay and usb-reverse scoped relay material validation."
echo "Covered macOS route.refresh relay host producer canonicality addendum: route.refresh rejects URL-shaped, path, query, fragment, user-info, port-suffixed, and whitespace-mutated relay hosts returned by the runtime provider before emitting route material."
echo "Covered shared route.refresh private-overlay scope schema addendum: protocol schema requires relay_scope=private_overlay when authenticated route.refresh relay_host is a private, CGNAT, or ULA relay literal."
echo "Covered shared route.refresh runtime identity canonicality schema addendum: protocol schema caps runtime_device_id and runtime_key_fingerprint with the same whitespace-free opaque route value rule as route.refresh route material."
echo "Covered shared route.refresh relay_host canonicality schema addendum: protocol schema rejects whitespace-mutated, URL-shaped, path, query, fragment, or user-info relay_host values before authenticated route.refresh artifacts can validate."
echo "Covered shared route.refresh relay_host scope eligibility schema addendum: protocol schema rejects mDNS-local, unspecified, link-local, multicast, and broadcast relay_host values and requires relay_scope=usb_reverse for loopback route-refresh material."
echo "Covered Android route.refresh relay payload acceptance/incomplete rejection addendum: authenticated relay route.refresh stores fresh relay material and rejects expired or missing relay_secret material before trusted storage changes."
echo "Covered Android route.refresh relay material canonicality addendum: authenticated relay route.refresh rejects whitespace-mutated, URL-shaped, oversized, private-overlay scope-mismatched, and loopback scope-mismatched relay material before trusted storage changes."
echo "Covered route.refresh relay freshness addendum: Android route.refresh rejects reused relay nonces or non-advancing relay leases before storage while allowing stable relay id/secret reuse."
echo "Covered Android route.refresh rejected-payload retry addendum: authenticated relay route.refresh responses rejected by identity or route-material validation keep the current trusted relay route and retry inside the active lease."
echo "Covered route.refresh P2P addendum: authenticated route.refresh can carry complete opaque P2P rendezvous material without claiming real P2P traversal."
echo "Covered macOS route.refresh opaque material size-bound addendum: route.refresh caps runtime, relay, and P2P route values at 512 characters while allowing p2p_encrypted_body up to 2048 characters."
echo "Covered macOS authenticated route.refresh diagnostic opt-in addendum: macOS app runtime returns route_refresh_unavailable by default and emits route material only when diagnostic route refresh is explicitly enabled."
echo "Covered RuntimeDevServer route.refresh P2P smoke addendum: authenticated relay smoke validates complete opaque P2P rendezvous material from RuntimeDevServer."
echo "Covered RuntimeDevServer route.refresh relay lease freshness smoke addendum: authenticated relay smoke requires route.refresh to advance the QR relay lease expiry and use a fresh relay nonce while allowing stable relay id/secret reuse."
echo "Covered macOS route.refresh failure redaction addendum: route.refresh failures return fixed retryable recovery copy without relay secrets, route tokens, provider URLs, or backend endpoints."
echo "Covered relay client retirement addendum: RelayPeerClient retireAfterCurrentConnection keeps the active relay session usable while suppressing stale-nonce reconnects after route.refresh."
echo "Covered no-ADB QR summary addendum: no-ADB external-relay QR smoke records machine-readable runtime-log, QR URI, QR PNG, print-uri terminal-output, round-trip decode, runtime-host proof-boundary, temporary pairing-material, relay-route, direct-endpoint, and emit-only coverage, plus stale/unverified artifact negative caveat coverage."
echo "Covered no-device production session proof-boundary addendum: no-ADB QR and different-network preflight summaries keep production session-key exchange and production end-to-end transport encryption proof false."
echo "Covered RuntimeDevServer history/title/session lifecycle/memory smoke addendum: authenticated relay smoke positively validates chat.sessions.list, chat.messages.list, chat.title.request, chat.session rename/archive/restore/delete, archived chat.send restore-required rejection, chat.send context compaction backend-only audit, visible history separation, memory.upsert, memory.list, memory.delete, memory.summary.drafts.list, memory.summary.draft.generate success/cache/malformed fallback/source isolation, memory.summary.draft.approve, memory.summary.draft.dismiss, generated-summary approval source metadata, approved memory-summary memory.list visibility, memory-summary stale expected-metadata rejection, client-supplied memory source rejection, approved memory source-preserving edit/list visibility, dismissed draft hiding, dismissed draft no memory.list entry, and memory.summary draft unavailable errors over RuntimeDevServer."
echo "Covered review-only exact memory duplicate suggestions authenticated smoke addendum: RuntimeDevServer requires authentication and the negotiated memory.duplicate_suggestions.v1 capability, rejects non-empty requests before storage access, returns only exact unsigned-UTF-8-ordered entry_ids groups plus scanned_count and truncated, omits content and protected metadata, and leaves all deletion as explicit memory.delete cleanup."
echo "Covered review-only semantic memory duplicate suggestions authenticated smoke addendum: RuntimeDevServer requires authentication and memory.semantic_duplicate_suggestions.v1, validates a provider-qualified installed runtime-local embedding model plus an exact integer 8000...10000 threshold, enforces bounded vectors and Android JSON nesting, excludes byte-exact pairs, returns only canonically ordered entry_ids pairs with integer similarity_basis_points and bounded counts, omits protected model/vector/source/route metadata, keeps final trust lease, observed-model generation, source identity, authentication, and runtime-owned memory mutation publication boundaries coordinated, and does not mutate memory."
echo "Covered review-only semantic memory duplicate clusters authenticated smoke addendum: RuntimeDevServer independently requires memory.semantic_duplicate_clusters.v1, rejects noncanonical request metadata and integral-float thresholds, uses the selected installed runtime-local embedding model, excludes byte-exact contents, returns only disjoint canonically ordered complete-link entry_ids clusters with integer minimum_similarity_basis_points and bounded counts, omits protected model/vector/source/route metadata, and preserves authoritative memory bytes before and after review."
echo "Covered RuntimeDevServer chat compaction backend-only audit addendum: authenticated relay smoke validates chat.send context compaction backend-only audit and visible history separation over RuntimeDevServer."
echo "Covered RuntimeDevServer adaptive compaction trust-boundary smoke addendum: authenticated relay smoke requires fixed system provenance, an untrusted assistant summary, a prompt-injection canary confined outside generated system messages, chat_context_window_exceeded for an oversized newest request, and no backend dispatch for that rejection."
echo "Covered runtime session search addendum: chat.sessions.list query filters runtime-owned titles, model ids, and sanitized transcript text inside owner/archive/delete boundaries, with deterministic ranking, bounded snippets, score/activity/session-id total ordering, Android query/search DTO serialization, selected embedding-model search hint plumbing, trimmed request plumbing, exact pending-response matching including stale old-channel rejection, connection-, authentication-, and route-lifetime search authority revocation with pending-history reset across request-specific errors, request-bound mutation acknowledgements, malformed-ack rollback, same-session mutation serialization, stale pending-search and pre-mutation-list supersession, delayed revoked-session, completed-request, and completed pre-auth pairing/hello send-failure rejection, exact rename timestamp rollback, optimistic lifecycle rollback, visible search-row consumption, one-shot search-summary promotion before lifecycle actions, local-only identity-collision preservation, authoritative search-only session in-memory promotion and transcript loading without full-cache replacement or search-metadata persistence, Settings chat-history search refresh query forwarding, Settings chat-history runtime search match metadata, RuntimeDevServer chat.sessions.list query search metadata smoke, and SQLite/FTS event-store parity plus JSONL-to-SQLite backfill, SQLite default-store rollout, and SQLite deleted-session retention pruning for sessions, messages, owner/archive/delete lifecycle, inline-byte redaction, corrupt-log handling, idempotency, legacy-file freshness, tombstone-backed legacy resurrection prevention, and search metadata."
echo "Covered runtime-authoritative chat session pagination and bulk lifecycle addendum: capability-gated HMAC snapshots bind connection, owner, query context, page size, snapshot count, offset, and expiry; capable initial limits are 1 through 200; snapshots expire after 120 monotonic seconds, cap at 10000 sessions, one per connection, and eight globally; reauthentication invalidates cursors and in-flight publication while per-connection initial generations prevent an older slow result from evicting a newer snapshot; trusted-device lookup cannot publish a superseded authentication challenge, and rename plus single and bulk lifecycle mutations revalidate exact owner, authentication generation, capability, and request-task cancellation under the host lifecycle lock, including unauthenticated development mutations without retaining closed-connection UUID tombstones; request task dispatch starts behind its registration barrier, and connection close claims active backend generations before cancelling tracked request tasks and clearing lifecycle authority; Android publishes and persists only a validated terminal snapshot, rejects duplicate ids, cursor loops, count drift, empty nonterminal pages, final mismatch, page-budget overflow, and authoritative-to-legacy downgrade; authoritative downgrade quarantine blocks runtime-owned archive-all and delete-all until fresh capable reconciliation; bounded closed-history correlation ignores delayed superseded or completed errors while current request IDs take precedence, including current authentication errors whose request IDs use a history namespace; dedicated history request namespaces keep evicted stale errors harmless and discard closed errors before payload validation; current transcript malformed errors close pending and loading state before rejecting late success; list and transcript send failures clear only their current request while stale failures cannot revoke newer authority; owner-scoped archive-all-active and delete-all-archived use atomic 200-session host batches, exact-target compaction-summary purge before commit, 50-batch and 10000-row client ceilings, no optimistic runtime-owned mutation, mandatory failure reconciliation without automatic retry, and preserved legacy plus local-only behavior."
echo "Covered runtime-authoritative chat session cross-platform wire transcript addendum: one exact two-session payload transcript is emitted by the macOS router after non-secret cursor/timestamp normalization and consumed directly as JSON by Android; the same fixture separately drives a 201-session pagination and bounded bulk-lifecycle stress flow on both platforms. This is no-device in-process compatibility and lifecycle evidence, not physical Android or live-network proof."
echo "Covered runtime-authoritative research notebook pagination addendum: research.notebooks.authoritative_sync.v1 keeps legacy notebooks-only pages compatible while capable peers use cursor-only continuations, 200-row pages, a 10000-row owner snapshot ceiling, 120-second HMAC cursors bound to the connection, authenticated owner, include-archived context, page size, count, offset, and expiry, one snapshot per connection, and eight globally; disconnect, reauthentication, create, archive, restore, and delete invalidate authority; Android privately accumulates and validates every page before atomically replacing notebook and backing-session authority without a stale completed emission, rejects duplicate notebook or session ids, count drift, cursor loops, empty nonterminal pages, stale authority, page-budget overflow, and capable-to-legacy downgrade, while no-op create deltas cannot extend the authority-bound idle timeout; the shared fixture drives an exact compact transcript and is materialized into temporary runtime stores for an authenticated 201-notebook 100/100/1 stress flow with independent cursor-plus-limit and cursor-plus-include-archived rejection; the bounded hello capability ceiling is 64 with 65 rejected. This is no-device protocol, SwiftPM, authenticated loopback-development-smoke, and Android JVM/fake-channel evidence only, not physical Android, optical QR, external-network, live-provider, production P2P/NAT, ICE/STUN/TURN, or traversal proof."
echo "Covered research notebook rename title-authority addendum: chat.session.rename remains the sole authenticated user title mutation; research.notebooks.list projects the backing runtime chat-session title and separate title-update time without a second mutable notebook title authority, preserves conversational last activity, advances deterministic notebook ordering, fences legacy and authoritative publication races, and invalidates prior owner cursors after manual or accepted generated-title commits. Explicit and automatic generated titles require an existing active placeholder, capture its title revision, revalidate owner, authentication, lifecycle, title, and revision before commit, and cannot overwrite a concurrent rename; JSONL and SQLite reject new noncanonical title appends, safely project legacy non-NFC, control-bearing, or oversized titles, preserve append authority across equal or reverse timestamps and legacy import, and make new title timestamps advance beyond the prior title update. Android keeps research backing sessions out of persistence while applying and rolling back transient notebook-title updates under request, channel, connection, and authentication correlation, queues mandatory post-brief reconciliation instead of publishing a stale terminal notebook snapshot, redacts held chat snapshots against every research session ID observed during pagination, uses an optimistic notebook revision CAS so stale rename errors or acknowledgements cannot overwrite a newer authoritative row, serializes same-session lifecycle work, rejects malformed lifecycle timestamps with exact rollback and resync, tombstones completed requests, and ignores uncorrelated delayed authentication errors after timeout or tombstone eviction before refreshing both runtime authorities. This is no-device SwiftPM/JSONL/SQLite and Android JVM/Compose evidence only, not physical Android, optical QR, live-provider, external-network, production P2P/NAT, ICE/STUN/TURN, or traversal proof."
echo "Covered review-only exact memory duplicate suggestions addendum: an authenticated capability-gated owner-scoped runtime scan bounds production JSONL input to 8 MiB, candidates to the latest 200 entries and 1 MiB of content, and returned IDs to 128 KiB, uses unsigned UTF-8 ordering, rechecks trust after storage work, and returns only entry-id groups plus count/truncation metadata. Android requires a current-authority unqueried memory list, rejects queried-list authorization, namespaces scan request IDs so evicted stale errors cannot revoke current authentication, bounds retained correlations, disables unsupported runtimes per authority, keeps review state transient, and never automatically merges, edits, enables, disables, or deletes memory. This is no-device Swift/JVM/Compose evidence, not semantic clustering, live-provider, physical Android, or live-network proof."
echo "Covered review-only semantic memory duplicate suggestions addendum: a separate authenticated capability-gated owner-scoped semantic-pair scan uses an explicit runtime-local embedding model and integer threshold, bounds event-log input to 8 MiB, latest candidates to 200, selected full content to 1 MiB, embedding batches to 64 documents and 262144 UTF-8 bytes, pairs to 100, and returned IDs to 128 KiB. Strong model revisions may use owner/model/document/source-revision cache keys while weak revisions stay on demand; source, model, trust, public-key, and authentication authority are rechecked before publication. Android correlates model and threshold with the current channel and authority, keeps semantic state transient and separate from exact results, disables only unsupported semantic capability, and retains explicit manual controls without automatic merge or mutation. This is no-device deterministic-mock/JVM/Compose evidence, not live-model quality, physical Android, optical QR, P2P/NAT, or live-network proof."
echo "Covered review-only semantic memory duplicate clusters addendum: the independent authenticated complete-link scan reuses the semantic pair candidate, event-log, content, batch, vector, strong/weak revision cache, concurrency, and final trust/model/source/authentication/mutation publication bounds while scoring the admitted set before pair-response truncation. Every returned cluster member pair meets the exact integer threshold, clusters are disjoint and canonical with at most 100 groups and 128 KiB of IDs, and Android keeps model/threshold/channel/authority-bound results transient with existing manual controls only. This is no-device deterministic-mock/JVM/Compose evidence, not calibrated live-model quality, automatic merge, physical Android, optical QR, P2P/NAT, or live-network proof."
echo "Covered review-only semantic memory threshold calibration foundation addendum: a SHA-256-pinned five-language synthetic corpus, exact offline vectors, canonical pair labels, complete-link review labels, and both Swift and independent Python evaluators sweep every integer threshold from 8000 through 10000. The deterministic fixture keeps the Android default at 9000, changes no protocol, performs no memory mutation, and reports calibration evidence separately from optional loopback live-model measurements."
echo "Covered review-only semantic memory acceptance recommendation addendum: a closed versioned proposed-not-selected packet defines representative corpus intake, a two-provider exact-artifact matrix, precommitted overall and language-stratum precision/recall floors, hard-negative specificity, denominator requirements, one shared threshold, privacy and holdout boundaries, and a future batched evaluator requirement. The strict validator rejects duplicate keys, exact-type confusion, unknown fields, synthetic-fixture drift, present historical-report hash drift, approval or authorization escalation, matrix completion, floor weakening, averaging, and blocked-state mutation. Representative corpus evidence remains blocked_missing_representative_corpus; measurement is not started; the 9000 default, threshold range, protocol, automatic merge or mutation, corpus intake, and additional live execution remain unchanged and unauthorized."
echo "Covered SQLite runtime chat retention policy addendum: production runtime chat maintenance prunes only cutoff-eligible deleted sessions, preserves active/archived sessions, keeps owner scope, and preserves tombstone-backed legacy resurrection prevention."
echo "Covered macOS runtime chat retention production ownership addendum: app launch, 24-hour scheduling, and the Runtime History Inspector drain eligible all-owner deleted sessions in cancellable 100-session SQL batches with deterministic owner isolation, targeted FTS deletion, one post-drain legacy JSONL compaction coordinated across current writer instances and processes, localized status, and tombstone-backed resurrection prevention."
echo "Covered chat.session.rename unknown metadata rejection addendum: RuntimeDevServer chat.session.rename payloads reject renamed_at, backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime title store mutation."
echo "Covered chat.session lifecycle unknown metadata rejection addendum: RuntimeDevServer chat.session archive/restore/delete payloads reject backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime chat store mutation."
echo "Covered chat.session lifecycle invalid allowed type rejection addendum: RuntimeDevServer chat.session archive/restore/delete payloads reject non-string, empty, or blank session_id values before runtime chat store mutation."
echo "Covered chat.session.rename invalid allowed type rejection addendum: RuntimeDevServer chat.session.rename payloads reject non-string or blank session_id and non-string or empty title values before runtime title store mutation."
echo "Covered chat.sessions.list unknown metadata rejection addendum: RuntimeDevServer chat.sessions.list payloads reject backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime chat store dispatch."
echo "Covered chat.sessions.list invalid allowed type rejection addendum: RuntimeDevServer chat.sessions.list payloads reject string limit, fractional limit, string include_archived, non-string query, and non-string embedding_model_id before runtime chat store dispatch."
echo "Covered chat.messages.list unknown metadata rejection addendum: RuntimeDevServer chat.messages.list payloads reject backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime chat store dispatch."
echo "Covered chat.messages.list invalid allowed type rejection addendum: RuntimeDevServer chat.messages.list payloads reject blank session_id plus string and fractional limit values before runtime chat store dispatch."
echo "Covered memory.list unknown metadata rejection addendum: RuntimeDevServer memory.list payloads reject response-only entries, backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime memory store dispatch."
echo "Covered memory.list invalid allowed type rejection addendum: RuntimeDevServer memory.list payloads reject non-string query values before runtime memory store dispatch."
echo "Covered runtime memory.list query resource guard addendum: memory.list rejects overlong or excessive-term lexical queries before runtime memory-store search dispatch."
echo "Covered memory.upsert unknown metadata rejection addendum: RuntimeDevServer memory.upsert payloads reject response-only entry, source, backend_url, backend_credentials, provider_url, route_token, relay_secret, requested_route_token, workspace_id, permission_grant, source_path, and source_control_status before runtime memory store mutation."
echo "Covered memory.upsert invalid allowed type rejection addendum: RuntimeDevServer memory.upsert payloads reject non-string, empty, or blank id values, non-string or blank content values, and non-boolean enabled values before runtime memory store mutation."
echo "Covered envelope request_id blank rejection addendum: RuntimeDevServer rejects blank envelope request_id values before authentication checks, backend dispatch, route refresh, or runtime store mutation."
echo "Covered envelope version rejection addendum: RuntimeDevServer rejects unsupported envelope version values before authentication checks, backend dispatch, route refresh, or runtime store mutation."
echo "Covered macOS protocol envelope required-field decode addendum: BridgeProtocol ProtocolCodec rejects missing, mistyped, and malformed required envelope version, request_id, timestamp, type, and payload fields before RuntimeDevServer or router command handling."
echo "Covered macOS protocol envelope unknown top-level field decode addendum: BridgeProtocol ProtocolCodec rejects unknown top-level envelope metadata fields before RuntimeDevServer or router command handling."
echo "Covered Android protocol envelope required-field decode addendum: Android ProtocolCodec rejects missing and mistyped required envelope version, type, request_id, timestamp, and payload fields before default values can hide malformed frames."
echo "Covered Android protocol envelope version/request_id semantic decode addendum: Android ProtocolCodec rejects unsupported envelope version values and blank envelope request_id strings before message dispatch or relay transport handling."
echo "Covered Android protocol envelope timestamp format decode addendum: Android ProtocolCodec rejects malformed envelope timestamp strings before ProtocolEnvelope defaults, message dispatch, or relay transport handling can accept them."
echo "Covered Android protocol envelope unknown top-level field decode addendum: Android ProtocolCodec rejects unknown top-level envelope metadata fields while preserving message-specific payload object handling."
echo "Covered RuntimeDevServer envelope version/request_id decode rejection addendum: RuntimeDevServer rejects missing or mistyped envelope version and request_id values with invalid_payload while keeping the connection usable for follow-up pre-auth runtime.health."
echo "Covered RuntimeDevServer envelope timestamp decode rejection addendum: RuntimeDevServer rejects missing, non-string, and malformed envelope timestamp values with invalid_payload while keeping the connection usable for follow-up pre-auth runtime.health."
echo "Covered RuntimeDevServer envelope type/payload decode rejection addendum: RuntimeDevServer rejects missing or non-string envelope type values and missing or non-object payload values with invalid_payload while keeping the connection usable for follow-up pre-auth runtime.health."
echo "Covered RuntimeDevServer envelope unknown top-level metadata decode rejection addendum: RuntimeDevServer rejects unknown top-level envelope metadata with invalid_payload while keeping the connection usable for follow-up pre-auth runtime.health."
echo "Covered pre-auth invalid allowed type rejection addendum: RuntimeDevServer hello and auth.response payloads reject blank or malformed allowed fields before challenge creation or authentication."
echo "Covered protocol schema active request contract parity addendum: shared protocol schema mirrors minimal hello, active request nonblank identifier fields, and models.pull backend enum contracts enforced by the schema gate."
echo "Covered memory.delete unknown metadata rejection addendum: RuntimeDevServer memory.delete payloads reject deleted_at, backend_url, route_token, relay_secret, workspace_id, permission_grant, source_path, and source_control_status before runtime memory store mutation."
echo "Covered memory.delete invalid allowed type rejection addendum: RuntimeDevServer memory.delete payloads reject non-string, empty, and blank id values before runtime memory store mutation."
echo "Covered runtime embedding search-hint boundary addendum: chat.sessions.list accepts selected embedding_model_id only with a real query, passes it to the runtime search boundary, and never echoes it as a response field or treats it as a chat model override; RuntimeDevServer authenticated relay smoke sends embedding_model_id with chat.sessions.list query and verifies no response echo or chat model override."
echo "Covered persistent runtime chat semantic embedding cache addendum: SQLite reuses owner/session/canonical-model/model-fingerprint/document-fingerprint scoped vectors across reopen, rejects stale source revisions after append, treats malformed rows as read-only misses, bounds rows per owner/model, and checks cancellation after lock acquisition and before commit. Only canonical Ollama SHA-256 revisions enable persistence; providers without a strong artifact revision stay on demand. RuntimeDevServer authenticated relay smoke proves the second identical search embeds only the query without logging input text. Android keeps remote search results transient and does not replace or persist the full runtime history cache. This is no-device mock/unit evidence, not live-provider quality, physical Android, or production-network proof."
echo "Covered approved runtime memory semantic search and cache addendum: memory.list embeds only persisted owner-scoped approved entry content, excludes generated and dismissed review drafts plus source audit metadata, considers at most 200 entries, and returns the existing rank/snippet/matched_fields shape without model, vector, cache, or revision metadata. An owner-only SQLite sidecar binds owner, memory id, canonical model, strong model fingerprint, document fingerprint, and current source revision; edits and deletes purge derived rows before mutation, stale in-flight results are revalidated, and purge failure blocks the privacy-sensitive mutation. RuntimeDevServer smoke proves a repeated semantic memory query embeds only the query on the second call without logging text. Android keeps queried results transient, ignores late request ids, releases pending state after malformed matching responses, and retries strict old-runtime hint rejection lexically. This is no-device mock/unit evidence, not live-provider quality, physical Android, semantic document indexing, or production-network proof."
echo "Covered runtime memory list search addendum: memory.list query filters owner-scoped runtime memory content and bounded runtime-derived source metadata with deterministic rank/snippet/matched_fields while memory.upsert rejects client-supplied source metadata."
echo "Covered RuntimeDevServer memory.list query search metadata smoke addendum: authenticated relay smoke validates memory.list query ranking, snippet, and matched_fields metadata over RuntimeDevServer."
echo "Covered RuntimeDevServer future memory.search rejection addendum: authenticated RuntimeDevServer relay smoke rejects memory.search with unknown_message_type because semantic approved-memory ranking remains inside memory.list and no separate memory.search namespace exists."
echo "Covered Android Settings memory runtime search addendum: Settings Memory local filtering forwards trimmed runtime memory query refresh, renders rank/snippet/matched_fields metadata, and keeps runtime search snippets out of device storage."
echo "Covered Android memory.list semantic-model hint and transient-cache addendum: Android RuntimeClientViewModel sends selected embedding_model_id only with a real memory query, keeps queried results out of the full persisted memory cache, ignores late request ids, and retries only strict old-runtime unknown-field rejection without the hint."
echo "Covered Android memory.list closed-payload app-path addendum: RuntimeClientViewModel rejects unknown top-level memory.list response metadata, unknown per-entry metadata, unknown nested search metadata, and unknown approved-memory source/session/source-pointer metadata before runtime memory state publication or device storage mutation, then accepts a canonical retry before semantic memory search, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered runtime reasoning search metadata addendum: chat.sessions.list can match stored assistant reasoning separately from visible answer text across JSONL router and SQLite/FTS paths, and Android Settings labels reasoning matched fields."
echo "Covered context-window compaction addendum: models.result carries optional context_window_tokens, Android preserves the metadata, Ollama/LM Studio parse context-window hints, and macOS chat.send uses resolved model context windows to choose runtime compaction budget plus backend-only summary text and durable source-pointer metadata that stays out of chat.messages.list and SQLite FTS."
echo "Covered resource-bounded provider model-catalog/context-window trust-boundary addendum: focused Swift and Android protocol tests pin true streaming 4 MiB catalog/detail ingestion, positive Content-Length preflight, limit-plus-one stop, 256 rows and Ollama detail calls, aggregate and Ollama detail-fanout cancellation propagation, bounded unique LM Studio unload instances, exact 1,048,560-byte relay plaintext acceptance and 1,048,561-byte rejection, exact Int64 size serialization, 512/522-code-point byte-exact identities, shared Unicode blank-only rejection, 32 byte-exact-unique nonblank capabilities of at most 128 code points, strict duplicate and escape-equivalent JSON keys, precision-safe Decimal context validation through 16,777,216, LM Studio catalog fallback only 404/405/501, explicit native chat.end including final-line parser.finish success, whole-catalog router rejection without truncation, provider-specific Ollama context omission versus LM Studio and final-router rejection, Android/schema exact-plus-one parity, and conservative legacy compaction fallback only for genuinely absent context metadata. This is URLProtocol/JVM-backed no-device proof, not live-provider, physical-device, or live-network proof."
echo "Covered v0.2 addendum: bounded public models.list single-flight. Up to eight concurrent public waiters share one provider catalog operation; a ninth receives a sanitized retryable backend_unavailable. Every waiter retains its own request id and publication authority, one waiter cancellation preserves shared work, last-waiter cancellation stops provider work, cancellation must retire before replacement, and success or failure is not cached. Internal authority catalog lookups remain outside coalescing. This is no-device mock-backend proof, not live-provider, physical-device, external-network, throughput, production-relay/P2P, or Phase B proof."
echo "Covered v0.2 addendum: Android runtime.health current-request authority. Each authenticated request uses a namespaced id bound to the exact channel, connection generation, and authenticated authority generation; only the latest exact result, error, or send failure can close or mutate state, while stale, duplicate, wrong-channel, old-connection, and prior-auth terminals are inert. Disconnect, revocation, reauthentication, and ViewModel clear remove pending authority. This is Android JVM no-device proof, not physical-device, peer-receipt, live-provider, external-network, production-relay/P2P, Phase B, or deployment proof."
echo "Covered v0.2 addendum: Android authenticated transcript and document read current-request authority. chat.messages.list, index.documents.list, and retrieval.query results, errors, and send failures require the exact request id, channel, connection generation, and authenticated authority generation before pending state, transient document state, transcript publication, or device persistence can change. Wrong-channel, old-connection, prior-auth, duplicate, superseded, and delayed terminals are inert; reauthentication, disconnect, revocation, and ViewModel clear remove old authority. This is Android JVM no-device proof, not physical-device, optical QR, peer receipt, live-provider, external-network, production-relay/P2P, Phase B, or deployment proof."
echo "Covered v0.2 addendum: Android authenticated read rollover and chat.sessions.list receive authority. chat.sessions.list results and pagination require the exact request id, receiving channel, connection generation, and authenticated authority generation before any accumulator, terminal, history, search, or bulk-lifecycle state can change. Successful same-channel reauthentication replaces pending memory.list and research.notebooks.list authority, authentication revocation clears pending memory.list authority, stale results, errors, and canceled timeouts are inert, and current replacements remain usable. This is Android JVM no-device proof, not physical-device, optical QR, peer receipt, live-provider, external-network, production-relay/P2P, Phase B, or deployment proof."
echo "Covered v0.2 addendum: Android chat.sessions bulk terminal authority. Runtime-authoritative archive-all and delete-all success results, malformed errors, ordinary errors, and asynchronous send failures require the exact pending request id, operation type where applicable, receiving or dispatch channel, connection generation, and authenticated authority generation before bulk state, local session persistence, reconciliation, error publication, or authentication state can change. Wrong-channel, old-connection, prior-authentication, duplicate, and stale terminals are inert. This is Android JVM no-device proof, not physical-device, optical QR, peer receipt, live-provider, external-network, production-relay/P2P, Phase B, or deployment proof."
echo "Covered v0.2 addendum: Android persistent-memory mutation current-request authority. memory.upsert and memory.delete use namespaced request ids bound to the exact operation, target, transmitted payload and expected result fields, channel, connection generation, and authenticated authority generation. Receive-loop-captured source authority is forwarded unchanged. Only one exact-current result, error, or send failure may close a mutation or change device memory state; unsolicited, mismatched, stale, duplicate, and delayed terminals are inert. Same-target mutations serialize while different targets remain independent. Any memory.list authority that predates mutation dispatch or remains pending when an exact mutation terminal closes is invalidated, so a stale full-list response cannot undo a completed add, enable change, or delete. The 15-second local timeout closes only the exact current request, never automatically retries the mutation, and requires fresh memory.list reconciliation; independent sibling mutations defer it, while invalidating an in-flight required reconciliation preserves and reissues it after the final sibling closes. Reauthentication, revocation, disconnect, receive failure, and ViewModel clear cancel pending authority and timeout jobs. This is Android JVM no-device proof, not physical-device, optical QR, peer receipt or exactly-once host mutation, real lost-response recovery beyond the deterministic timeout, live-provider, external-network, production-relay/P2P/NAT, Phase B, or deployment proof."
echo "Covered adaptive context compaction budget and pre-dispatch rejection addendum: the planner enforces byte- and decoded-image-aware input accounting across multilingual text and attachments, emits fixed provenance plus untrusted summaries with request-matching contiguous source pointers, rejects an oversized newest request before backend dispatch, preserves runtime-memory separation, validates SQLite accounting metadata, pins chat_context_window_exceeded in Android and the shared schema, and keeps localized Android error layout bounded."
echo "Covered backend-only LLM chat compaction summary addendum: focused Swift regressions require a bounded same-model summary prepass, reasoning isolation, deterministic fallback on oversized output, durable cancellation intent across the prepass-to-primary handoff, atomic primary backend registration with connection-owned cancellation, one global primary-and-derived generation-id reservation namespace, and absence of generated summary text after SQLite reopen and session search."
echo "Covered durable chat compaction summary cache addendum: an owner-only SQLite sidecar keys exact bounded prepass input by owner, session, dedicated source fingerprint, actual resolved provider model, and summary policy; successful primary completion enables reopen reuse without another prepass, while cancellation/error/non-fitting output does not commit, corrupt rows miss, row count is bounded, session deletion purges derived rows, and summary text remains outside chat history and FTS."
echo "Covered incremental chat compaction summary lineage addendum: exact reuse binds the full storage-safe compacted-prefix lineage, verified strict extensions evolve only the previous generated summary plus newly compacted whole-turn delta as untrusted input, edit/reorder/delete/scope mismatch fail closed, failed primaries do not commit evolved summaries, legacy v1 metadata remains readable, and the derived old cache schema is rebuilt without migration."
echo "Covered provider usage calibration foundation addendum: Ollama chat, LM Studio native, and LM Studio OpenAI-compatible completions keep the original stream enum and two-value done contract while bounded generation-scoped one-shot registries expose provider/model/wire source; the OpenAI-compatible path requests stream_options.include_usage and waits for a usage-only chunk after finish_reason. Adaptive v3 terminal validation binds usage to the router-resolved provider-qualified model, recomputes conservative-estimate and hard-budget relation, rejects malformed calibration, and prevents generated-summary cache commit after a reported budget exceedance or mismatched one-shot source. Missing usage and legacy records remain compatible. This is no-device post-dispatch calibration evidence, not exact preflight tokenizer parity, automatic policy tuning, live-provider, physical Android, optical QR, production relay/P2P, or real-network proof."
echo "Covered v0.2 addendum: host-local chat compaction calibration acceptance report. Revalidated JSONL and SQLite terminal events feed an aggregate-only report keyed by exact provider, canonical provider model id, wire mode, and estimator revision. Newest-first processing is capped at 1,000 fully eligible samples and 32 groups; 20 samples means ready for human review only, while any hard input-budget exceedance remains a warning. JSONL reverse-tail work is capped at 64 MiB, 50,000 lines, and 4 MiB per line; SQLite scans at most 50,000 terminal rows with indexed exact request binding. Duplicate terminals, deterministic estimate mismatch, malformed calibration, missing bindings, and scan-ceiling exhaustion fail closed. Encoded output omits prompt/messages, summaries, owner/session/request/event ids, timestamps, and source pointers. The macOS host loads off the main actor, clears stale results on failure, and exposes an explicit five-locale review sheet. No protocol/Android state, provider probe, automatic estimator change, socket/network I/O, physical-device, live-provider parity, or production authority is added or proven."
echo "Covered runtime compaction metadata validation addendum: SQLite runtime chat storage rejects non-request compaction metadata, blank strategies, empty source pointers, invalid turn ranges, and invalid retained ranges before event storage."
echo "Covered adaptive v3 compaction source fingerprint addendum: canonical multilingual and attachment vectors bind the exact storage-safe compacted conversation prefix, SQLite and JSONL revalidate the request-bound digest and canonical byte count after reopen, malformed or tampered bindings fail closed, legacy v1/v2 metadata remains readable, and fingerprint metadata plus backend-only summary text remain outside transcript FTS."
echo "Covered adaptive compaction effective terminal accounting addendum: v3 request metadata labels its post-compaction estimate as a planned upper bound, terminal resolution records whether primary dispatch occurred, dispatched deterministic or LLM summary method and exact conservative estimate, undispatched cancellation omits method and estimate, malformed resolution shapes fail closed, SQLite and JSONL require a preceding owner/session/request-scoped adaptive v3 request with matching estimator and input budget on append and reopen, and no summary text or generated-summary hash is persisted."
echo "Covered Android chat.messages.list compaction metadata projection addendum: Android ignores runtime-only compaction_metadata/source_pointers in raw chat.messages.list results and keeps summary sentinels out of UI state and device storage."
echo "Covered Android chat.messages.list closed-payload app-path addendum: RuntimeClientViewModel rejects unknown top-level chat.messages.list response metadata, unknown stored-message metadata, and unknown stored-attachment metadata before transcript state publication or device storage mutation, while preserving runtime-only compaction_metadata/source_pointers projection and accepting a canonical retry before workspace search, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered long-inactivity memory summarization eligibility addendum: runtime-host policy selects only owner-scoped, active, sufficiently old, sufficiently long chat sessions as future memory-summary candidates, and builds deterministic long-inactivity memory summary drafts/source pointers from visible transcript text without writing runtime memory."
echo "Covered runtime archive polish addendum: chat.send into archived runtime sessions returns a restore-required structured error before backend dispatch or chat-event mutation."
echo "Covered RuntimeDevServer multi-device owner isolation smoke addendum: authenticated relay smoke validates memory, chat session, message, and session mutation owner-device boundaries across two trusted devices."
echo "Covered RuntimeDevServer model-residency smoke addendum: authenticated relay smoke validates aggregate mock model-switch unload, same-model unload suppression, missing-model rejection without unload, idle unload, and unload-failure runtime.health redaction through RuntimeDevServer."
echo "Covered unload-failure health redaction addendum: RuntimeDevServer runtime.health exposes safe last_unload_failure provider/model/reason metadata while redacting raw provider errors, backend routes, route tokens, and relay secrets."
echo "Covered runtime.health model-residency contract addendum: runtime.health model-residency contract spans macOS aggregate runtime snapshots, protocol schema/docs, Android DTO parsing, and Android in-memory state with unsafe details redacted."
echo "Covered runtime.health model-residency unload-failure contract addendum: runtime.health model_residency.last_unload_failure reports provider/model/reason only, without raw provider error messages or backend route material."
echo "Covered Android model-residency status addendum: Android Connection Status model-residency status UI, Android Connection Status model-residency unload failure UI, macOS model-residency manual unload quick action, and macOS manual model-residency activity summaries."
echo "Covered relay/auth hardening addendum: Android relay preparation explicit relay_id route material, macOS auth response replayed nonce rejection, macOS superseded challenge nonce rejection."
echo "Covered macOS menu-bar addendum: macOS menu-bar status accessibility labels."
echo "Covered macOS dialog addendum: macOS trusted-device cancel-remove action accessibility labels, macOS saved connection details cancel accessibility label."
echo "Covered macOS status addendum: macOS model-provider empty-state accessibility labels, macOS provider status decorative icon hiding, macOS runtime data status cards, macOS runtime history saved/archived status card summary, macOS runtime memory saved/paused status card summary, macOS runtime data all-owner summary, macOS runtime data summary error recovery, macOS runtime memory inspector, macOS runtime history inspector, macOS runtime history inspector saved/archived summary, macOS runtime history transcript preview."
echo "Covered macOS model-residency refresh quick action addendum: macOS model-residency refresh quick action."
echo "Covered v0.2 addendum: runtime model idle-unload policy user control."
echo "Covered v0.2 addendum: provider-confirmed runtime model unload state."
echo "Covered macOS model layout addendum: macOS compact long model row render smoke, macOS compact model-residency status render smoke, and macOS compact trusted-device row render smoke."
echo "Covered macOS large-text addendum: macOS large accessibility text sidebar preference render."
echo "Covered macOS sidebar preference addendum: macOS sidebar App Preferences group label, macOS sidebar preference detail copy."
echo "Covered macOS route recovery addendum: macOS failed saved connection recovery requires a fresh QR."
echo "Covered macOS QR-only pairing addendum: clean first-run Pairing hides Connection Recovery unless saved route diagnostics or a route-preparation issue exists, and does not expose setup only because automatic route preparation is unavailable."
echo "Covered runtime history addendum: Android runtime history message-count clamp, macOS runtime history message-count clamp, macOS chat.cancel runtime-owned cancelled event, macOS chat.cancel immediate done closure, macOS connection-close generation cancellation."
echo "Covered macOS P2P route material redaction addendum: macOS Activity diagnostics, route diagnostics, and companion logs redact p2p_rendezvous record IDs, encrypted bodies, anti-replay nonces, expiries, protocol versions, and compact P2P aliases."
echo "Covered macOS Bonjour TXT metadata boundary addendum: Bonjour/local discovery TXT publishes route_token as the identity hint and omits stable device_id, fingerprint, backend, provider, model, and runtime payload metadata."
echo "Covered macOS Bonjour route-token canonicality addendum: Bonjour/local discovery TXT rejects whitespace-mutated route_token values instead of trimming them into trusted discovery identity hints."
echo "Covered macOS Bonjour requested-route-token metadata addendum: Bonjour/local discovery TXT rejects requested_route_token and requested-route-token debug metadata before publishing route_token, app, or version hints."
echo "Covered Android device identity atomic persistence addendum: first-run keypair creation failure leaves no orphan android_device_id or android_device_name in DataStore."
echo "Covered Android pending pairing runtime public-key canonicality addendum: Android pending pairing route storage rejects whitespace-mutated or oversized runtime public keys before pending route restore, route planning, or accepted-pairing identity comparison."
echo "Covered readiness addendum: macOS runtime overview installed-local model readiness, macOS readiness row fallback accessibility, macOS trusted-device missing-date ID accessibility, Android streaming chat input mutation guard, Android streaming send reentrancy guard, Android streaming attachment mutation guard, Android streaming embedding-model selection guard, Android streaming memory mutation guard, Android streaming route/trust mutation guard, Android stream termination reasoning closure, Android runtime-owned stale message resurrection guard, Android runtime-owned local memory storage redaction, Android runtime memory client-prompt suppression, Android runtime lifecycle local-session collision guard, Android unreachable route-refresh QR cleanup guard, Android route.refresh sensitive detail minimization, Android pending relay QR secret-store boundary, Android pending relay QR secret cleanup, Android runtime technical error detail storage boundary, Android safe runtime technical diagnostics surface, Android share-sheet intake, Android explicit share-sheet MIME scope, Android private-overlay real relay TCP pairing path, Android private-overlay real relay TCP reconnect path, Android device identity Base64 signature guard, Android device identity persistence guard, Android QR trust value whitespace guard, Android/macOS client auth domain separation, macOS pairing trusted-device identity validation, macOS auth session disconnect cleanup, macOS trusted-device removal live-session revocation, macOS relay line framing newline guard, macOS relay disconnect callback idempotency, macOS local peer disconnect callback idempotency, macOS route material diagnostic redaction, macOS attachment prompt storage separation, macOS trusted-device store file permission hardening, macOS runtime identity fallback file permission hardening, macOS runtime event-log file permission hardening, macOS runtime history router nonpositive-limit guard, macOS runtime history nonpositive limit guard, macOS runtime history zero-limit corrupt-log bypass, macOS runtime history semantic corruption visibility, macOS runtime memory corrupt-log visibility, macOS runtime memory semantic corruption visibility, macOS authenticated runtime history and memory owner-device scoping."
echo "Covered Android settings addendum: Android preference group heading semantics, Android Settings panel heading semantics, Settings preference option action labels, Android Settings private model access live-region summary, Android drawer section heading semantics, Android drawer empty-history live-region accessibility, Android drawer Settings footer action semantics, Android drawer Settings footer readiness state, Android permanent rail Settings action semantics, Android permanent rail Settings readiness state, Android chat search no-results live-region accessibility, Android model search no-results live-region accessibility, Android streaming assistant content live-region accessibility, Android model picker empty-state live-region accessibility, Android embedding model empty-state live-region accessibility, Android open reasoning collapsed live-region accessibility, Android open reasoning live-region accessibility, Android short reasoning static accessibility state, Android memory delete confirmation named message, Android memory manual runtime refresh, Android chat history manual runtime refresh, Android Settings chat history open-chat action, Android Settings chat-history search result action context, Android runtime chat mutation error resync, Android runtime data load error surfacing."
echo "Covered Android Settings embedding model compact row layout."
echo "Covered Android SettingsScreen embedding model compact row layout."
echo "Covered Android Settings auto-reconnect compact row layout."
echo "Covered Android Settings Connection Status TalkBack-order proxy addendum: Android Settings embedded QR scan, route recovery notice, refresh, disconnect, and auto-reconnect controls keep localized semantics and reachable bounds order at large font."
echo "Covered Android Settings preference compact row layout."
echo "Covered Android Settings section header compact layout."
echo "Covered language/trust copy addendum: Android appearance system detail copy, Android follow-system language callback dispatch, Android follow-system selected preference state, and macOS Trusted Devices runtime requests empty-state copy."
echo "Covered Android localization addendum: Android French chat accessibility copy."
echo "Covered Android accessibility addendum: Android attachment-only message role accessibility."
echo "Covered suggested-question removal tombstone addendum: active code/protocol/current docs/ops paths forbid chat.suggestions and suggested-question UI symbols."
echo "Covered Android pairing QR relay port canonicality addendum: Android parser and QR verifier reject signed or zero-padded relay port strings before route material acceptance."
echo "Covered Android pairing QR route expiration canonicality addendum: Android parser and QR verifier reject signed or zero-padded relay/P2P route expiration strings before route material acceptance."
echo "Covered shared QR verifier semantic alias rejection addendum: rendered QR verification rejects route_token plus rt mixed semantic aliases before route material validation."
echo "Covered shared QR verifier alias-family parity addendum: rendered QR verification rejects mixed relay and P2P alias families, accepts complete rendezvous_* relay route material, and rejects whitespace-mutated relay secrets."
echo "Covered Android route.refresh response unknown metadata addendum: Android rejects authenticated route.refresh response payload fields outside the route material allowlist before trusted runtime storage and keeps the current route for retry."
echo "Covered Android route.refresh runtime identity canonicality addendum: authenticated route.refresh rejects whitespace-mutated or oversized runtime identity fields before trusted route storage changes."
echo "Covered Android route.refresh malformed allowed-field retry addendum: authenticated route.refresh responses with allowed keys but invalid JSON types keep the current trusted route and retry inside the active lease before trusted storage changes."
echo "Covered Android layout addendum: Android ChatGPT-like chat surface narrow-phone layout regression, Android representative populated chat surface compact layout, Android populated Settings history and Memory narrow-phone render, Android drawer chat row compact layout, Android drawer overflow menu compact layout, Android drawer empty-history compact layout, Android drawer chat-search no-results compact layout, Android drawer runtime summary compact layout, Android provider status compact diagnostic layout, Android connection status panel compact layout, Android Connection Status route notice compact layout, Android Settings QR pairing panel compact first-run layout, Android Settings pending pairing route compact layout, Android Settings route-refresh saved notice compact layout, Android Settings companion-only compact layout, Android Settings discovery actions compact layout, Android Settings developer diagnostics toggle compact layout, Android Settings memory compact long-content actions layout, Android Settings memory approved-source compact layout, Android Settings memory add controls compact layout, Android Settings memory empty-state compact layout, Android Settings chat-history search-refresh header compact layout, Android Settings chat-history compact row actions, Android Settings chat-history bulk action compact layout, Android memory summary draft compact review layout, Android assistant reasoning compact layout, Android read-only attachment chip wrapping, Android pending attachment chip wrapping, Android text-only draft composer controls compact layout, Android streaming cancel composer controls compact layout, Android streaming assistant progress decorative compact layout, Android composer readiness status compact layout, Android chat route availability notice compact layout, Android route-refresh saved notice compact layout, Android QR recovery diagnostics compact layout, Android chat empty-state compact layout, Android markdown table and code block compact layout, Android Settings memory saved/paused summary localization, Android markdown message rendering, Android assistant response regenerate action, Android latest user-message draft reuse action, Android latest message action localized states, Android latest message action wrapping, Android transcript role-change spacing rhythm, Android chat top-bar active-title compact layout, Android chat top-bar streaming-disabled model picker compact layout, Android model picker general row compact layout, Android model picker vision recovery compact row layout, Android model picker search no-results compact layout, Android model picker refresh compact row layout, Android localized clipboard payload labels, Android composer clear-draft action, Android composer clear-draft localized state, Android clear-draft attachment cleanup, Android composer draft persistence, Android session-scoped composer draft switching, Android transient attachment cleanup on chat switching, Android transient attachment cleanup on chat lifecycle exits, Android runtime transcript loading state, Android runtime transcript loading compact layout, Android runtime transcript lifecycle mutation lockout, Android empty-state latest-QR composer alignment."
echo "Covered Android large-font chat addendum: Android large-font multilingual Chat render."
echo "Covered Android TalkBack-order proxy addendum: Android Chat transcript, latest message actions, jump-to-latest, send composer, and cancel composer controls keep localized semantics and bounds order at large font."
echo "Covered Android large-font layout addendum: Android large-font multilingual Settings render."
echo "Covered Android layout detail addendum: Android Settings chat-history saved/archived summary localization, Android markdown heading accessibility, Android markdown table accessibility, Android code block accessibility summary."
echo "Covered Android share addendum: Android share-sheet import confirmation, Android share-sheet import compact snackbar layout, Android share-sheet import haptic feedback, Android share-sheet content URI boundary."
echo "Covered Android archive snackbar addendum: Android chat archive undo compact snackbar layout."
echo "Covered Android top-bar addendum: Android chat top-bar New Chat compact layout."
echo "Covered Android scanner addendum: Android QR scanner compact pairing-state render smoke, Android QR scanner compact large-font bounds, Android QR scanner scan-target accessibility label, Android QR scanner invalid-code recovery."
echo "Covered Android diagnostics addendum: Android diagnostic QR text open action labels and Android diagnostic QR text compact dialog layout."
echo "Covered Android provider diagnostics addendum: Android provider diagnostics detail compact redaction."
echo "Covered app icon addendum: no-device Android launcher and macOS Dock small-size readability plus asset-chain validation."
echo "Covered macOS Dock capture dry-run summary addendum: capture_macos_dock_icon dry-run writes no-side-effect summary evidence without claiming a physical Dock screenshot."
echo "Physical UI polish capture option: script/android_pairing_deeplink_smoke.sh --capture-ui-polish captures chat, model selector, drawer, Settings, and launcher screenshots/XML on an attached phone."
echo "Covered Android pairing summary UI polish artifact-manifest addendum: android_pairing_deeplink_smoke --summary-json lists chat, model selector, drawer, Settings, and launcher PNG/XML artifacts when --capture-ui-polish runs, without turning no-device self-tests into physical UI proof."
echo "Covered Android pairing chat-model query selector addendum: android_pairing_deeplink_smoke --chat-model-query can select provider/model rows from UI XML and the no-device self-test proves provider-qualified LM Studio query matching without claiming phone model-selection proof."
echo "Covered Android pairing summary JSON proof-boundary addendum: android_pairing_deeplink_smoke --summary-json records success and failure-path physical smoke proof booleans for adb deeplink injection, live-provider chat/cancel, live-provider chat-complete, model-log confirmation, reconnect, and UI capture while keeping optical QR, production relay, real different-network, direct backend access, and raw route material proof false or absent."
echo "Covered Android pairing chat-complete summary addendum: android_pairing_deeplink_smoke --expect-chat-complete records natural chat.done without chat.cancel and expected transcript terms in summary JSON without converting no-device self-tests into phone chat proof."
echo "Covered physical external-relay Android pairing summary artifact addendum: check_physical_external_relay_pairing passes --summary-json into the child Android pairing smoke and records safe child-summary proof booleans without converting no-device self-tests into physical external-relay proof."
echo "Covered physical external-relay chat-complete pass-through addendum: check_physical_external_relay_pairing forwards --expect-chat-complete, completed-term checks, and model query options to the child Android pairing smoke and preserves safe child chat-complete proof booleans in wrapper summary JSON."
echo "Covered physical external-relay proof-boundary split addendum: check_physical_external_relay_pairing records external_network_operator_confirmed, real_different_network_relay_verified, real_different_network_connectivity_proof, optical_camera_qr_scan, production proof, direct-backend, and private_or_same_lan_development_relay fields so same-LAN/private relay evidence cannot be mistaken for real different-network, optical QR, production relay/session/encryption, or direct Android backend proof."
echo "Covered QA evidence latest-entry proof-boundary hygiene addendum: check_docs_hygiene validates the latest QA evidence entry for proof-boundary, no-device, physical/live-provider separation, agent-state, caveat, and verification-command wording."
echo "Physical macOS Dock capture option: script/capture_macos_dock_icon.sh stages dist/AetherLink.app and captures build/qa/aetherlink-macos-dock-visible.png with CFBundleIconFile=AppIcon."
echo "Covered SQLite runtime document index store addendum: SQLiteRuntimeDocumentIndexStore persists runtime-owned document records and chunks with deterministic IDs, owner-only SQLite file protection, bounded catalog listing, display-name catalog filtering, MIME-type catalog filtering, safe summary counts, chunk metadata summaries, content-fingerprint match listing, quality-filtered catalog, FTS candidate row maintenance, lexical query parity, replacement, deletion, and quality-filtered deletion without project IDs, workspace IDs, source paths, retrieval_context, embeddings, protocol/router exposure, or Android UI integration."
echo "Covered runtime document index store addendum: RuntimeDocumentIndexStore stores runtime-owned document records and chunks with deterministic document IDs, deterministic chunk IDs, display names, MIME types, content fingerprints, bounded catalog listing, display-name catalog filtering, MIME-type catalog filtering, safe summary counts, chunk metadata summaries, content-fingerprint match listing, quality-filtered catalog, chunk offsets, lexical query rank/snippet results, replacement, deletion, and quality-filtered deletion without project IDs, workspace IDs, source paths, retrieval_context, embeddings, protocol/router exposure, or Android UI integration."
echo "Covered runtime document index display-name canonicality addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore trim display-name lookup input, derive stored display names and chunk labels from canonical document file names, strip path-shaped labels to their final component, and fall back to untitled-document for blank or oversized labels without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index display-name control-character canonicality addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore reject control-character display names before catalog lookup, in-memory storage, chunk labels, or SQLite display-name rows, falling back to untitled-document without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index chunk-envelope canonicality addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore derive stored chunk indexes and offsets from store-owned chunk envelopes, validate offsets against document text, locate malformed offsets from document text when possible, and bound unlocatable forged chunk offsets before catalog or SQLite storage without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index ingestion summary normalization addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore derive extracted-character count, chunk count, and quality from document text and chunks before catalog or SQLite storage, so malformed direct-ingestion summaries cannot persist forged counts or quality states without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index MIME-type canonicality addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore trim MIME-type lookup input, require canonical lowercase type/subtype tokens before catalog lookup or SQLite query dispatch, and store malformed document or chunk MIME metadata as application/octet-stream without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index content-fingerprint canonicality addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore trim content-fingerprint lookup input and reject blank, wrong-length, uppercase, or non-hex fingerprints before catalog lookup or SQLite query dispatch without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index chunk read limit addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore clamp full chunk reads to a store-owned maximum before returning chunk text, while keeping replacement/deletion parity and avoiding protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index limit-ceiling addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore clamp catalog rows, chunk metadata summaries, lexical query results, and snippets to store-owned maximums without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index query resource guard addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore reject overlong lexical query text, excessive deduplicated query terms, and overlong individual terms before in-memory search or SQLite search dispatch without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index SQLite substring parity addendum: SQLiteRuntimeDocumentIndexStore public query preserves the shared substring lexical rank/snippet contract even when internal FTS candidate rows miss substring-only token matches, while keeping FTS rows as internal maintenance and future-search infrastructure without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index requested document ID canonicality addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore trim requested document IDs, reject blank or oversized requested document IDs back to deterministic stable IDs before document/chunk/SQLite FTS storage, and share the same canonicality guard for document lookup, chunk reads, chunk metadata summaries, and deletion without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index requested document ID control-character canonicality addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore reject control-character requested document IDs back to deterministic stable IDs before document, chunk, or SQLite FTS storage, and reject control-character document ID lookup, chunk reads, chunk metadata summaries, and deletion without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index documents list protocol addendum: authenticated LocalRuntimeMessageRouter index.documents.list returns bounded runtime-owned document catalog metadata and summary counts without chunk text, source paths, workspace/project IDs, retrieval_context, embeddings, citations, or trusted-source fields, while rejecting response-only catalog payloads and future source metadata before document-index store dispatch."
echo "Covered runtime document retrieval query protocol addendum: authenticated LocalRuntimeMessageRouter retrieval.query returns bounded lexical runtime-owned document snippets with rank, matched_terms, document metadata, and chunk offsets without full chunk text, chunk IDs, source paths, workspace/project IDs, retrieval_context, embeddings, citations, or trusted-source fields, while rejecting response-only results and future source or embedding metadata before document-index store dispatch."
echo "Covered macOS retrieval.query request bounds addendum: authenticated LocalRuntimeMessageRouter rejects retrieval.query query text longer than 1024 characters with invalid_payload before lexical or semantic document-index dispatch, matching the shared schema and runtime document-index query ceiling without citation, client trusted-source review, local persistence, or chat context behavior."
echo "Covered macOS source-anchor resolver request required-field router addendum: authenticated LocalRuntimeMessageRouter rejects missing, empty, whitespace-only, and non-string source_anchor_id values with invalid_payload before source-anchor store dispatch, keeping source_anchor.resolve request handling aligned with the shared schema without source approval, citation, trusted-source review, permission, audit, Android UI, local persistence, or chat context behavior."
echo "Covered Android protocol document index, retrieval, and source-anchor resolver payload parity addendum: Android ProtocolModels and ProtocolCodecTest serialize and decode index.documents.list catalog/summary payloads, retrieval.query lexical snippet payloads, and source_anchor.resolve redacted resolver payloads with the shared schema field names."
echo "Covered Android source-anchor resolver request required-field decode addendum: Android SourceAnchorResolveRequestPayload now rejects missing source_anchor_id during DTO decode before Android can advertise, send, persist, consume, or display source_anchor.resolve requests."
echo "Covered Android source-anchor resolver required-field decode addendum: Android SourceAnchorResolveResultPayload now rejects missing source_anchor_id, document, chunk_summary, and nested chunk_summary chunk_index, start_character_offset, end_character_offset, and character_count required fields before DTO parity can be mistaken for Android UI resolver consumption, local persistence, chat context injection, source approval, citation, trusted-source review, permission, or audit semantics."
echo "Covered Android document index and retrieval transient ViewModel wiring addendum: Android RuntimeClientViewModel advertises index.documents.list and retrieval.query client capabilities, sends bounded explicit catalog/search requests, decodes catalog and lexical snippet responses into transient RuntimeUiState only, clears search errors for retry, and keeps chat.send payloads free of retrieval_context, source paths, workspace/project IDs, citations, and trusted-source fields without Compose UI consumption or chat context injection."
echo "Covered Android document catalog disconnect transient clear addendum: Android RuntimeClientViewModel clears transient index.documents.list documentCatalog rows and summary values on explicit disconnect and receive failure, while keeping runtime document catalog state local to RuntimeUiState without source approval, citation, trusted-source review, permission, audit, local persistence, or chat context behavior."
echo "Covered Android client capability future Workspace/RAG/source deny-list addendum: Android runtimeClientCapabilities advertises active index.documents.list, retrieval.query, research.brief.create, research.notebooks.list, and research.notebooks.v1 while keeping source_anchor.resolve unadvertised until Android UI/client consumption exists, and keeping future embeddings.create, index.build, research.web.query, citation.sources.list, source_control.status, projects.sessions.list, automation.runs.create, tool.call, tool.result, tool.run, skills.run, mcp.tool.call, web_search.query, python.run, python.exec, permission.request, approval.prompt, audit.events.list, file.read, file.write, file.index, terminal.exec, terminal.kill, network.request, network.open, backend.call, backend.configure, memory.search, route.candidates.exchange, route.diagnostics.report, route.allocation.status, and route.failure.report out of default and diagnostic hello client_capabilities."
echo "Covered Android document catalog summary transient-state bounds addendum: Android RuntimeClientViewModel now rejects schema-invalid index.documents.list summary values before transient state while preserving schema-valid catalog summary rows before local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android document retrieval source anchor canonical transient-state addendum: Android RuntimeClientViewModel keeps only exact source_anchor_[16 lowercase hex] retrieval.query source_anchor_id values in transient document search state and now treats noncanonical wire source_anchor_id values as invalid_payload before transient rows are published, without creating source approval, citation, trusted-source review, permission, audit, local persistence, or chat context behavior."
echo "Covered Android unsolicited source-anchor resolver boundary addendum: Android RuntimeClientViewModel ignores unsolicited source_anchor.resolve result frames even when they carry future chunk_text, snippet, source_path, retrieval_context, citations, trusted_source, approval_state, and backend_url metadata, does not advertise source_anchor.resolve in client_capabilities, does not send resolver requests, and keeps resolver document metadata, chunk_summary, source_anchor_id values, local persistence, and chat.send payloads unchanged until Android UI/client resolver consumption is designed."
echo "Covered Android document search disconnect transient clear addendum: Android RuntimeClientViewModel clears transient retrieval.query documentSearchQuery, documentSearchResults, and source_anchor_id values on explicit disconnect and receive failure, while keeping document search state local to RuntimeUiState without source approval, citation, trusted-source review, permission, audit, local persistence, or chat context behavior."
echo "Covered Android document index and retrieval read-only Compose UI addendum: Android Settings exposes a read-only Documents panel that renders transient RuntimeUiState catalog summary rows and retrieval.query snippet rows, invokes explicit refresh/search callbacks only, localizes connected/streaming/disconnected action states, and keeps fingerprints, source paths, workspace/project IDs, retrieval_context, citations, trusted-source fields, local persistence, and chat context injection out of UI behavior."
echo "Covered Android document retrieval source anchor hidden UI addendum: Android Settings Documents search keeps transient retrieval.query source_anchor_id values out of visible text and accessibility content descriptions while preserving snippet, rank, matched-term, and document metadata rendering."
echo "Covered Android document index and retrieval compact layout addendum: Android Settings Documents catalog and retrieval.query rows stay bounded at large font across supported app languages on compact width while preserving the read-only transient UI boundary and avoiding fingerprints, source paths, workspace/project IDs, retrieval_context, citations, trusted-source fields, local persistence, and chat context injection."
echo "Covered Android trusted relay document index/retrieval integration addendum: Android RuntimeClientViewModelRelayIntegrationTest.trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession proves an authenticated trusted private-overlay relay reconnect carries index.documents.list and retrieval.query over RuntimeRelayTcpClient, trims the search query, preserves request limits, updates transient catalog/search state, and keeps chat.send payloads free of retrieval_context, source paths, workspace/project IDs, citations, trusted-source fields, document filenames, and snippets without direct TCP or direct backend access."
echo "Covered runtime document index clear-all maintenance addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore clear catalog rows, chunk metadata, lexical query rows, summaries, and SQLite FTS candidates without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index quality-delete maintenance addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore remove only documents matching an ingestion quality state while preserving other catalog rows, chunk metadata, lexical query rows, summaries, and SQLite FTS candidates without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index content-fingerprint delete maintenance addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore remove only documents matching a canonical content fingerprint while preserving unrelated catalog rows, chunk metadata, lexical query rows, summaries, and SQLite FTS candidates without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index MIME-type delete maintenance addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore remove only documents matching a canonical MIME type while preserving unrelated catalog rows, chunk metadata, lexical query rows, summaries, and SQLite FTS candidates without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered runtime document index display-name delete maintenance addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore remove only documents matching a canonical display name while preserving unrelated catalog rows, chunk metadata, lexical query rows, summaries, and SQLite FTS candidates without protocol/router exposure, Android UI integration, project IDs, workspace IDs, source paths, retrieval_context, embeddings, citations, or trusted-source fields."
echo "Covered DocumentIngestion direct extracted-document text ceiling addendum: runtime-side DocumentIngestor rejects oversized direct ExtractedDocument text before chunk planning, summary construction, or result return while preserving extractor-owned file ingestion resource policy behavior without source paths, project IDs, embeddings, retrieval, protocol, router, or Android UI integration."
echo "Covered DocumentIngestion direct extracted-document source-label canonicality addendum: runtime-side DocumentIngestor canonicalizes direct ExtractedDocument file names before chunk planning, summary construction, or result return while preserving existing MIME metadata boundaries without source paths, project IDs, embeddings, retrieval, protocol, router, or Android UI integration."
echo "Covered DocumentIngestion result envelope addendum: runtime-side DocumentIngestor combines extraction and chunk planning into a safe result with document text, chunks, file name, MIME type, extracted character count, chunk count, min/max chunk lengths, and no-usable-text/single-chunk/chunked quality states without source paths, project IDs, embeddings, retrieval, protocol, router, or Android UI integration."
echo "Covered DocumentIngestion chunk planner addendum: runtime-side DocumentChunker creates deterministic bounded chunks from extracted text with source labels, character offsets, sentence/word boundary preference, overlap, multilingual text preservation, whitespace-only empty results, and invalid policy rejection without project IDs, source paths, embeddings, or protocol/router integration."
echo "Covered DocumentIngestion chunk policy ceiling addendum: runtime-side DocumentChunker rejects oversized max-character, overlap-character, and min-chunk policy values before chunk planning, keeping caller-supplied policy windows store-owned and bounded without source paths, project IDs, embeddings, retrieval, protocol, router, or Android UI integration."
echo "Covered DocumentIngestion MIME dispatch canonicality addendum: runtime-side DocumentTextExtractor trims attachment MIME types, ignores MIME parameters, and lowercases MIME dispatch before extensionless document extraction without source paths, project IDs, embeddings, retrieval, protocol, router, or Android UI integration."
echo "Covered DocumentIngestion archive-entry path canonicality addendum: runtime-side DocumentTextExtractor ignores path-shaped archive entries before archive entry fanout counting or extraction without source paths, project IDs, embeddings, retrieval, protocol, router, or Android UI integration."
echo "Covered DocumentIngestion archive entry fanout policy addendum: runtime-side DocumentTextExtractor rejects excessive selected archive entries before archive entry extraction, keeping compressed document fanout store-owned and bounded without source paths, project IDs, embeddings, retrieval, protocol, router, or Android UI integration."
echo "Covered DocumentIngestion resource policy ceiling addendum: runtime-side DocumentTextExtractor rejects oversized or non-positive caller-supplied resource policy limits before file reads, archive listing, archive entry extraction, textutil conversion, or normalized text dispatch without source paths, project IDs, embeddings, retrieval, protocol, router, or Android UI integration."
echo "Covered DocumentIngestion resource policy addendum: runtime-side document extraction rejects oversized archive entry output and oversized normalized extracted text before backend dispatch."
echo "Covered protocol reserved namespace guard addendum: projects. and automation. active messages remain blocked by protocol schema hygiene."
echo "Covered protocol generic tool namespace guard addendum: tool.* active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke until runtime tool permissions, execution, result handling, and audit semantics are designed."
echo "Covered protocol reserved tools/search/python namespace guard addendum: skills., mcp., web_search., and python. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered protocol reserved permission/approval/audit namespace guard addendum: permission., approval., and audit. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered protocol reserved runtime action namespace guard addendum: file., terminal., network., and backend. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke until runtime file, terminal, network, and backend action permissions are designed."
echo "Covered protocol reserved RAG/research namespace guard addendum: approved semantic retrieval is active through retrieval.query, research.brief.create and research.notebooks.list are the only active research.* messages, and embeddings.*, unsupported retrieval/index/research including research.web.query, unsupported citation/source-anchor/trusted-source messages, and source_control.* remain blocked."
echo "Covered protocol citation and trusted-source namespace guard addendum: citation.resolve plus trusted_source.approve, trusted_source.dismiss, trusted_source.list, and trusted_source.revoke are the only active citation/trusted_source messages; unsupported citation.* and trusted_source.* messages plus unsupported source_anchor.* beyond source_anchor.resolve remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered RuntimeDevServer reserved source-anchor namespace rejection addendum: authenticated RuntimeDevServer relay smoke accepts source_anchor.resolve but rejects source_anchor.metadata.get with unknown_message_type before any future source-anchor metadata, approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered protocol reserved private-overlay namespace guard addendum: p2p., rendezvous., bootstrap., dht., nat., stun., and turn. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered protocol reserved encrypted-session namespace guard addendum: session., key_exchange., encrypted_session., and anti_replay. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered protocol reserved transport/crypto namespace guard addendum: transport. and crypto. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered RuntimeDevServer future Python namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects python.run and python.exec with unknown_message_type before any runtime Python tool execution path exists."
echo "Covered RuntimeDevServer generic tool namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects tool.call, tool.result, and tool.run with unknown_message_type before any runtime generic-tool execution or result path exists."
echo "Covered RuntimeDevServer reserved projects/automation namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects projects.sessions.list and automation.runs.create with unknown_message_type before any workspace or scheduler feature path exists."
echo "Covered RuntimeDevServer reserved permission/approval/audit namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects permission.request, approval.prompt, and audit.events.list with unknown_message_type before any production permission broker, mobile approval, or audit-log control path exists."
echo "Covered RuntimeDevServer reserved runtime action namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects file.read, file.write, file.index, terminal.exec, terminal.kill, network.request, network.open, backend.call, and backend.configure with unknown_message_type before any production file, terminal, network, or backend action path exists."
echo "Covered RuntimeDevServer index.documents.list seeded catalog no-device smoke addendum: authenticated RuntimeDevServer relay smoke accepts index.documents.list against a seeded runtime document index with one bounded catalog row, summary metadata, document metadata, and quality counts while rejecting response-only documents, summary, embedding_model_id, retrieval_context, source_path, workspace_id, citations, trusted-source, and backend metadata before document-index dispatch."
echo "Covered RuntimeDevServer retrieval.query lexical and semantic no-device smoke addendum: authenticated RuntimeDevServer relay smoke preserves the bounded legacy lexical response, then opts into approved semantic ranking with embedding_model_id, requires explicit semantic match_kind, verifies a query-only persistent cache hit, and keeps model ids, scores, vectors, fingerprints, source revisions, cache state, paths, citations, and trusted-source metadata out of responses and content-free embedding audit rows."
echo "Covered Android semantic document request compatibility addendum: Android RuntimeClientViewModel sends the selected runtime-host embedding_model_id with bounded retrieval.query, retries exactly one strict older-runtime unsupported-field rejection with the same query and bounds but no hint, ignores retired responses, and never silently downgrades backend or document-index failures to lexical ranking."
echo "Covered RuntimeDevServer retrieval.query request bounds no-device smoke addendum: authenticated RuntimeDevServer relay smoke rejects retrieval.query query text longer than 1024 characters with invalid_payload before the seeded lexical or semantic document-index path, matching the router and shared schema request ceiling without citation, client trusted-source review, local persistence, or chat context behavior."
echo "Covered protocol source-anchor wire-shape addendum: shared protocol schema pins retrieval.query response and source_anchor.resolve request/response source_anchor_id to source_anchor_[16 lowercase hex], Android ProtocolCodecTest asserts the same decoded response shape, RuntimeDevServer relay smoke requires the exact shape, and retrieval.query requests still cannot carry source_anchor_id before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android retrieval source-anchor required decode addendum: Android RetrievalQueryResultItemPayload requires source_anchor_id during decode, and ProtocolCodecTest rejects retrieval.query result rows missing the response-only source anchor before Android transient state, resolver protocol, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android source-anchor canonical decode addendum: Android protocol DTO decode rejects noncanonical retrieval.query and source_anchor.resolve source_anchor_id values before Android transient state, resolver dispatch, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android retrieval matched-terms required decode addendum: Android RetrievalQueryResultItemPayload requires matched_terms during decode, and ProtocolCodecTest rejects rows missing matched_terms before transient lexical or semantic metadata canonicalization; citations and client trusted-source review remain inactive."
echo "Covered Android retrieval/source-anchor coordinate decode addendum: Android RetrievalQueryResultItemPayload rejects negative chunk indexes, negative offsets, end-before-start offsets, and nonpositive ranks during decode, SourceAnchorChunkSummaryPayload rejects the same invalid resolver chunk summary coordinates, and RuntimeClientViewModel rejects malformed retrieval.query coordinate responses before transient source_anchor_id state, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android retrieval match-kind contract addendum: missing match_kind remains legacy lexical, explicit lexical results require nonempty bounded matched_terms, explicit semantic results may carry zero honest lexical overlaps, unknown kinds and malformed terms fail closed, and the localized UI labels semantic ranking without inventing a matched term."
echo "Covered approved runtime semantic document retrieval addendum: retrieval.query semantic opt-in uses deterministic document-round-robin candidates and overflow-stable cosine ranking. Strong-fingerprint models consider up to 200 approved runtime_shared chunks with 64-item batches and revision-keyed persistent candidate vectors; weak or no-fingerprint providers atomically embed one query plus at most 63 candidates in one request and never persist those vectors. SQLite records content-free semantic_accessed after pre-inference approval revalidation, then conditionally drops changed or revoked candidates and commits content-free queried before a redacted response; backend failure or cancellation observed before the final commit keeps access evidence without a completed query event. Lexical requests retain the legacy response shape and embedding or index failures never silently fall back."
echo "Covered citation and device trusted-source review addendum: citation.resolve and trusted_source approve, dismiss, list, and revoke use closed authenticated schemas with explicit cancel plus 15-second citation timeout; chat.send optionally carries one through eight unique canonical grant ids. The runtime atomically revalidates authenticated-device ownership, chat_context scope, current runtime_shared revision, citation, anchor, chunk, and revocation state, commits content-free consumed audit before bounded text release, injects reference JSON only into the backend copy of the newest user turn, and keeps source text plus opaque ids out of stored chat history and model-visible authorization metadata. Android selection is transient, one-shot, bounded, stale-safe, localized, and opaque-id-free in UI, accessibility, messages, and persistence."
echo "Covered Android document retrieval request bounds decode addendum: Android IndexDocumentsListRequestPayload rejects negative and over-maximum limit values during decode, and RetrievalQueryRequestPayload rejects blank or overlong query text, negative or over-maximum limit values, and negative or over-maximum max_snippet_characters values plus blank embedding_model_id before lexical or semantic runtime dispatch."
echo "Covered Android chat.sessions.list request bounds decode addendum: Android ChatSessionsListRequestPayload rejects negative and over-maximum limit values, empty query text, and empty embedding_model_id values during decode before runtime chat-store dispatch, embedding search-hint handling, local persistence, workspace search, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android chat.sessions.list response bounds decode addendum: Android ChatSessionSummaryPayload rejects empty session_id values, negative message_count values, unknown status values, and unknown last_event values, while ChatSessionSearchPayload rejects nonpositive rank values, empty matched_fields arrays, empty matched field entries, and duplicate matched_fields during decode before Android chat-history UI state, local persistence, workspace search, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android chat.sessions.list closed-payload app-path addendum: RuntimeClientViewModel rejects unknown top-level chat.sessions.list response metadata, unknown per-session metadata, and unknown nested search metadata before runtime chat-history state publication or device storage mutation, then publishes a canonical retry before workspace search, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android chat.messages.list stored attachment safe-metadata addendum: Android ChatStoredAttachmentPayload keeps stored transcript attachments limited to type, mime_type, name, and text, rejects inline data_base64 during protocol decode, and RuntimeClientViewModel rejects stored attachment data_base64 before transcript state publication or device storage mutation while chat.send attachments still preserve data_base64 for outbound runtime-mediated uploads before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered protocol source-anchor sample validation addendum: protocol schema hygiene now runs canonical and noncanonical source_anchor_id samples through the exact source_anchor_[16 lowercase hex] regex, accepting lowercase 16-hex handles while rejecting whitespace, newline, uppercase, short, long, non-hex, missing-prefix, and empty variants before resolver protocol, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered protocol retrieval.query source-anchor request payload sample addendum: protocol schema hygiene now validates retrieval.query request payload samples so query remains required and nonblank, limit and max_snippet_characters stay bounded when present, request payloads remain closed to unknown fields, and source_anchor_id is rejected from requests before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered protocol source-anchor resolver payload sample addendum: protocol schema hygiene now validates source_anchor.resolve request and response payload samples so requests require only canonical source_anchor_id and responses require source_anchor_id, document, and chunk_summary while rejecting response-only request fields, future resolver metadata, missing required fields, noncanonical source anchors, invalid chunk_summary integers, and end-before-start offsets before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered protocol retrieval.query request bounds sample addendum: protocol schema hygiene pins retrieval.query request properties to query, limit, max_snippet_characters, and optional nonblank embedding_model_id, and rejects malformed numeric bounds or model hints across lexical and semantic dispatch."
echo "Covered protocol retrieval.query query-length and response result sample addendum: protocol schema hygiene caps request query text at 1024 characters and rejects oversized queries while response samples reject unknown metadata, missing rank, empty snippets, invalid match-kind terms, and malformed coordinate or rank values across lexical and semantic results."
echo "Covered protocol retrieval.query positive-rank wire-shape addendum: protocol schema hygiene and RuntimeDevServer smoke require positive integer rank values and reject zero-rank response samples for lexical and semantic results."
echo "Covered protocol retrieval.query result ordering and offset sanity addendum: runtime store, SQLite parity, router tests, RuntimeDevServer smoke, and protocol schema hygiene pin retrieval.query result limits, deterministic rank ordering, and end_character_offset >= start_character_offset across lexical and semantic retrieval."
echo "Covered protocol index.documents.list request and response sample addendum: protocol schema hygiene accepts empty or bounded-limit catalog requests, rejects malformed limits and unknown metadata, and validates the safe metadata-only catalog shape used by approved lexical and semantic retrieval."
echo "Covered protocol index.documents.list quality-count completeness addendum: macOS runtime catalog responses serialize no_usable_text, single_chunk, and chunked quality_counts with zero defaults, while protocol schema hygiene rejects missing nested quality-count keys."
echo "Covered protocol index.documents.list content-fingerprint wire-shape addendum: protocol schema hygiene pins catalog document content_fingerprint values to 16 lowercase hex characters and rejects empty, whitespace-mutated, uppercase, short, long, and non-hex response samples."
echo "Covered Android document content-fingerprint protocol parity addendum: Android ProtocolCodecTest serializes and decodes catalog and lexical or semantic retrieval content_fingerprint samples as 16 lowercase hex characters, and RuntimeDevServer relay smoke requires the same shape."
echo "Covered Android document content-fingerprint canonical decode addendum: Android RuntimeDocumentIndexDocumentPayload now rejects noncanonical content_fingerprint values during DTO decode for index.documents.list, retrieval.query, and source_anchor.resolve before transient document state, resolver consumption, local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android document metadata response bounds decode addendum: Android RuntimeDocumentIndexDocumentPayload, IndexDocumentsListResultPayload, IndexDocumentsSummaryPayload, and IndexDocumentsQualityCountsPayload reject empty or overlong document ids and display names, malformed or overlong MIME types, negative document counts, invalid quality values, quality/chunk_count mismatches, over-100 catalog documents, and negative summary or quality-count values during DTO decode for index.documents.list, retrieval.query, and source_anchor.resolve before transient document state, resolver consumption, local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android retrieval.query response array bounds decode addendum: Android RetrievalQueryResultPayload rejects over-100 retrieval.query result arrays during DTO decode, matching the shared protocol response ceiling before transient document search state, resolver consumption, local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android document response future-metadata fail-closed addendum: Android RuntimeClientViewModel now rejects unknown future/private metadata in active index.documents.list catalog responses and retrieval.query search responses before transient document state, local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android document MIME transient-state canonicality addendum: Android RuntimeClientViewModel now rejects schema-invalid MIME values before transient state and preserves only exact lowercase type/subtype MIME values up to 128 characters in transient document state across catalog and retrieval search rows before local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android document quality/chunk-count transient-state consistency addendum: Android RuntimeClientViewModel now rejects schema-invalid quality/chunk_count combinations before transient state and preserves schema-canonical zero, single, and multi-chunk quality values across catalog and retrieval search rows before local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android document id/display-name transient-state bounds addendum: Android RuntimeClientViewModel now rejects schema-invalid empty or overlong document ids and display names before transient state, keeps schema-valid transient document ids nonblank and control-free with response-local fallbacks, and keeps display names as bounded final path components or untitled-document across catalog and retrieval search rows before local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android retrieval query outbound bounds addendum: Android RuntimeClientViewModel now rejects document search queries longer than 1024 characters before emitting retrieval.query, matching the shared protocol request ceiling before relay/runtime dispatch, local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android document search pending invalidation addendum: Android RuntimeClientViewModel now clears pending retrieval.query request tracking when the user submits a blank or overlong document search, ignores stale runtime responses for superseded invalid searches, and allows a fresh bounded search without local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics."
echo "Covered Android document response row transient-state cap addendum: Android RuntimeClientViewModel now accepts schema-valid index.documents.list catalog rows up to the 100-row protocol maximum and caps retrieval.query search rows to 10 before they reach transient RuntimeUiState, matching Android request limits before local persistence, chat context injection, semantic retrieval, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android retrieval lexical metadata transient-state bounds addendum: Android RuntimeClientViewModel coerces retrieval.query transient rank values to positive integers, keeps source offsets ordered, caps snippets, and keeps matched_terms to 16 distinct trimmed nonblank terms of 64 characters or less for lexical and semantic rows before transient publication; results do not enter local persistence or chat context."
echo "Covered protocol document quality/chunk-count consistency addendum: protocol schema hygiene binds indexDocument quality to chunk_count for catalog and lexical or semantic retrieval documents and rejects zero-chunk, single-chunk, and multi-chunk mismatch samples."
echo "Covered protocol document MIME type wire-shape addendum: protocol schema hygiene pins catalog and lexical or semantic retrieval mime_type values to lowercase type/subtype tokens and rejects whitespace-mutated, uppercase, missing-slash, parameterized, URL-shaped, and overlong MIME samples."
echo "Covered protocol document metadata string-bounds and retrieval nested-document parity addendum: protocol schema hygiene caps catalog and retrieval document id and MIME type values at 128 characters, display_name at 256 characters, requires lexical and semantic retrieval.query documents to reuse indexDocument, and rejects malformed nested metadata."
echo "Covered protocol retrieval.query matched-terms bounds addendum: protocol schema hygiene requires non-empty matched_terms for legacy or lexical results, permits empty honest overlaps only for explicit semantic results, caps arrays at 16 terms and terms at 64 characters, and rejects malformed combinations."
echo "Covered protocol retrieval.query snippet bounds addendum: protocol schema hygiene caps lexical and semantic retrieval.query response snippets at 500 characters and rejects overlong samples."
echo "Covered protocol document retrieval response array bounds addendum: protocol schema hygiene caps index.documents.list documents and lexical or semantic retrieval.query results at 100 items and rejects 101-row response samples."
echo "Covered protocol retrieval.query source-anchor response payload sample addendum: protocol schema hygiene now validates retrieval.query response payload samples so results[].source_anchor_id is required and exact source_anchor_[16 lowercase hex], rejecting missing, whitespace, uppercase, short, long, non-hex, and empty source anchors before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered macOS document retrieval source anchor exact-shape addendum: RuntimeDocumentIndexStore, SQLiteRuntimeDocumentIndexStore, and LocalRuntimeMessageRouter retrieval.query tests require generated and serialized source_anchor_id values to pass the exact runtimeDocumentIndexCanonicalSourceAnchorID source_anchor_[16 lowercase hex] contract instead of prefix-only checks, without adding resolver protocol, source approval, citation, trusted-source review, permission, audit, Android UI, local persistence, or chat context behavior."
echo "Covered document retrieval source anchor addendum: RuntimeDocumentIndexStore, SQLiteRuntimeDocumentIndexStore, LocalRuntimeMessageRouter, RuntimeDevServer authenticated relay smoke, Android ProtocolCodecTest, Android RuntimeClientViewModelTest, and Android trusted relay integration preserve source_anchor_id on retrieval.query rows while keeping source paths, retrieval_context, citations, trusted-source fields, document filenames, snippets, and source anchors out of chat.send."
echo "Covered document retrieval source anchor stability addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore prove source_anchor_id stays stable for the same safe document fingerprint/chunk offsets and rotates when same-id document content changes, without exposing source paths, workspace/project IDs, chunk text, snippets, citations, trusted-source fields, or retrieval_context."
echo "Covered document retrieval source anchor query-window addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore prove source_anchor_id stays tied to the same safe document/chunk envelope across different query terms, rank windows, result limits, snippet bounds, and SQLite reopen paths without adding resolver protocol, trusted-source, citation, permission, or audit semantics."
echo "Covered document retrieval source anchor canonicality addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore reject whitespace-mutated source_anchor_id resolver inputs instead of trimming them into future approval or citation handles, without adding resolver protocol, trusted-source, citation, permission, or audit semantics."
echo "Covered document retrieval source anchor resolver addendum: RuntimeDocumentIndexStore, SQLiteRuntimeDocumentIndexStore, and LocalRuntimeMessageRouter source_anchor.resolve resolve source_anchor_id to redacted document metadata plus chunk_summary only, while LocalRuntimeMessageRouter rejects source_anchor_id in chat.send until trusted-source, citation, permission, and audit semantics exist."
echo "Covered document retrieval source anchor lifecycle addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore invalidate stale source_anchor_id handles after same-id document replacement and deletion, while LocalRuntimeMessageRouter rejects client-supplied source_anchor_id in retrieval.query requests before resolver protocol, trusted-source, citation, permission, or audit semantics exist."
echo "Covered document retrieval source anchor filtered-delete lifecycle addendum: RuntimeDocumentIndexStore and SQLiteRuntimeDocumentIndexStore invalidate source_anchor_id handles after display-name, MIME-type, content-fingerprint, quality, and delete-all maintenance deletes, including SQLite reopen and FTS cleanup evidence, without adding resolver protocol, trusted-source, citation, permission, or audit semantics."
echo "Covered RuntimeDevServer reserved RAG/research namespace rejection addendum: authenticated RuntimeDevServer relay smoke accepts research.brief.create and research.notebooks.list under research.notebooks.v1, reuses the existing chat stream and approved source lifecycle, and rejects embeddings.create, index.build, research.web.query, citation.sources.list, and source_control.status with unknown_message_type."
echo "Covered runtime-owned research notebooks addendum: owner-scoped memory and SQLite notebook metadata, SQLite-canonical lifecycle lease timestamps, authenticated capability-gated routing, complete 10000-row candidate ranking before the 100-row legacy wire limit and capable authoritative snapshot pagination, pinned one-through-eight approved source grants, pre-backend and commit-bound authorization/notebook-state checks, rejected follow-up lifecycle fencing, shared lifecycle coordination and final research-session publication filtering, authoritative pagination invalidation after promotion, runtime-only instructions, safe summaries, Android transient history with authority-bound list timeout and active-session reclassification reload, mixed active and archived Android notebook authority, channel/auth-bound lifecycle acknowledgements, closed lifecycle errors, archived active-session and pending-transcript cleanup, active/archive drawer groups, two-step permanent delete, compact drawer/create UI with an explicit eight-source cap, dynamic action lockout, strict correlation, and authenticated RuntimeDevServer smoke are covered without web search, external network access, whole-document authority, physical Android, optical QR, live-provider, or production P2P/NAT claims."
echo "Covered RuntimeDevServer source-anchor resolver no-device smoke addendum: authenticated RuntimeDevServer relay smoke accepts source_anchor.resolve for a seeded retrieval source_anchor_id, rejects unknown resolver metadata and malformed handles with invalid_payload, returns source_anchor_not_found for stale canonical handles, and keeps chunk text, snippets, source paths, workspace/project IDs, citations, trusted-source fields, and approval state out of the response."
echo "Covered RuntimeDevServer citation and device trusted-source lifecycle addendum: authenticated RuntimeDevServer relay smoke resolves a current approved source anchor into a redacted citation/review envelope, rejects a wrong confirmation, approves exactly once for the authenticated device and chat_context scope, rejects replay, lists and revokes the grant, then proves the list is empty without exposing source revision, path, body, snippet, query, model, vector, cache, or host approval identifiers."
echo "Covered runtime-shared document source governance foundation: host-owned reviewed ingestion writes a strong runtime_shared approval and content-free audit bounded to the newest 100000 events in both memory and SQLite, legacy unapproved rows remain unreadable, authenticated catalog/retrieval/anchor reads plus audit insertion and oldest-overflow trimming linearize in store transactions and fail closed when audit persistence fails, and revoke/delete atomically blocks later catalog, lexical or semantic retrieval, stale anchors, citation reviews, and device trusted-source grants. Device grants remain separate from host runtime_shared approval and cannot mutate host approval state."
echo "Covered RuntimeDevServer reserved private-overlay namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects p2p.session.open, rendezvous.records.publish, bootstrap.records.lookup, dht.records.put, nat.candidates.gather, stun.binding.request, and turn.relay.allocate with unknown_message_type before any production P2P, rendezvous, bootstrap, DHT, NAT traversal, STUN, or TURN path exists."
echo "Covered RuntimeDevServer reserved encrypted-session namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects session.key.exchange, key_exchange.begin, encrypted_session.open, and anti_replay.window.commit with unknown_message_type before any production session-key exchange, encrypted-session, or replay-window control path exists."
echo "Covered RuntimeDevServer reserved transport/crypto namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects transport.handshake, transport.rekey, crypto.session.open, and crypto.key.rotate with unknown_message_type before any production transport handshake, rekey, crypto-session, or key-rotation control path exists."
echo "Covered RuntimeDevServer response-only message direction rejection addendum: authenticated RuntimeDevServer relay smoke rejects auth.challenge, pairing.result, models.result, chat.delta, chat.done, chat.title.result, and error with unexpected_message_direction before any client-supplied response frame can mutate runtime state."
echo "Covered protocol route namespace guard addendum: route.refresh remains the only active route.* message while future route diagnostics, candidate exchange, allocation-status, and failure-report messages stay reserved."
echo "Covered RuntimeDevServer future route namespace rejection addendum: authenticated RuntimeDevServer relay smoke accepts route.refresh but rejects route.candidates.exchange, route.diagnostics.report, route.allocation.status, and route.failure.report with unknown_message_type before any future route exchange, diagnostics, allocation-status, or failure-report path exists."
echo "Covered macOS protocol model metadata parity addendum: BridgeProtocol ModelInfo preserves provider, provider_model_id, qualified_id, model_kind, capabilities, and context_window_tokens for embedding model registration."
echo "Covered Android protocol model metadata parity addendum: Android ModelInfoPayload preserves backend, provider, provider_model_id, qualified_id, model_kind, kind, capabilities, size_bytes, context_window_tokens, modified_at, and remote_model for embedding model registration, and legacy missing capabilities decode as empty."
echo "Covered Android models.result closed-payload app-path addendum: RuntimeClientViewModel rejects unknown top-level models.result metadata and unknown per-model route/provider metadata before model state publication, keeps the previous model list after rejection, and recovers on a canonical retry before Android model selection state, provider API access, live-provider behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android runtime.health closed-payload app-path addendum: RuntimeClientViewModel rejects unknown top-level runtime.health metadata, unknown provider metadata, unknown model-residency metadata, and unknown nested model-residency unload-failure metadata before runtime/provider/residency state publication or authenticated follow-up refresh fanout, then recovers on a canonical runtime.health response before live-provider behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android model scalar metadata decode addendum: Android ModelInfoPayload rejects empty id or name values, missing name values, unsupported backend/provider/model_kind/source values, and duplicate capabilities during models.result decode before model selection state, runtime-side compaction budgets, provider API access, live-provider behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android model modified_at date-time decode addendum: Android ModelInfoPayload rejects malformed, date-only, and timezone-less modified_at values during models.result decode before model selection state, runtime-side compaction budgets, provider API access, live-provider behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android model numeric metadata decode addendum: Android ModelInfoPayload rejects negative size_bytes values and nonpositive context_window_tokens values during models.result decode before model selection state, runtime-side compaction budgets, provider API access, live-provider behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android runtime.health backend status minimal decode addendum: Android RuntimeBackendStatusPayload accepts schema-valid provider health objects with available only and treats omitted message/code/retryable as absent before Android runtime-health provider status UI state, live-provider behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android runtime.health status enum decode addendum: Android RuntimeHealthPayload rejects unsupported status values outside ok, degraded, or unavailable during decode before Android runtime-health status state, provider status UI state, live-provider behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android runtime.health model-residency numeric bounds decode addendum: Android RuntimeModelResidencyPayload rejects negative in_flight_generations values and negative idle_unload_delay_seconds values during decode before Android runtime-health status state, model residency UI, provider lifecycle hints, live-provider behavior, direct Android backend access, or physical Android proof exists."
echo "Covered Android chat.send request bounds decode addendum: Android ChatSendPayload rejects blank session_id values, blank model values, empty messages, invalid message roles, invalid attachment types, and empty attachment mime_type values during decode before runtime chat dispatch, local persistence, context compaction, live-provider behavior, production relay/session/encryption, direct Android backend access, or physical Android proof exists."
echo "Covered Android chat stream response bounds decode addendum: Android ChatDeltaPayload rejects empty stream delta payloads, ChatDonePayload rejects unsupported finish_reason values, and UsagePayload rejects negative input_tokens or output_tokens during decode before Android streaming UI state, local persistence, title generation, live-provider behavior, production relay/session/encryption, direct Android backend access, or physical Android proof exists."
echo "Covered Android chat stream closed-payload app-path addendum: RuntimeClientViewModel rejects unknown chat.delta response metadata and unknown top-level or nested chat.done usage metadata before streaming message publication, completion side effects, title/history follow-up, or device storage mutation, while preserving the active stream for canonical retry before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android models.pull fail-closed and chat.cancel acknowledgement app-path addendum: RuntimeClientViewModel does not advertise or dispatch models.pull, preserves the installed selection for uninstalled rows, ignores unsolicited legacy pull results, and still rejects unknown chat.cancel acknowledgement metadata before streaming cancellation or device storage mutation; no host approval UI, live-provider download, production relay/session/encryption, direct Android backend access, or physical Android proof exists."
echo "Covered Android pairing.result closed-payload app-path addendum: RuntimeClientViewModel rejects unknown pairing.result response metadata before trust mutation, pending route cleanup, authenticated refresh fanout, or device storage mutation, then accepts a canonical retry while keeping backend_url canaries out of state/storage before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android auth.challenge closed-payload app-path addendum: RuntimeClientViewModel rejects unknown auth.challenge response metadata before runtime proof verification or auth.response signing/sending, closes the authentication attempt, and rejects a later unsolicited accepted response before authenticated session state, route-refresh scheduling, or authenticated refresh fanout while keeping backend_url canaries out of state/storage."
echo "Covered Android auth.response result closed-payload app-path addendum: RuntimeClientViewModel rejects unknown auth.response result metadata before authentication state mutation or authenticated refresh fanout, then accepts a canonical auth.response retry while keeping backend_url canaries out of state/storage before route refresh, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android error payload closed-payload app-path addendum: RuntimeClientViewModel rejects unknown error response metadata before active stream termination, route/auth state mutation, or device storage mutation. Exact-current namespaced memory.list malformed errors consume only their correlation before error publication, allow a fresh replacement, and make late canonical errors for the closed id inert; active chat errors retain canonical same-id retry. Backend_url and workspace_id canaries stay out of state/storage before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android error payload code enum decode addendum: shared protocol schema, docs, schema hygiene, and Android ErrorPayload now use the same canonical protocol error code set, and Android rejects unknown, blank, or whitespace-mutated error payload codes during decode before runtime UI state, local persistence, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android chat and memory timestamp date-time decode addendum: Android chat sessions, stored chat messages, chat session mutation results, memory entries, memory delete results, memory summary draft dismiss results, memory summary draft sessions, and memory summary draft source pointers reject malformed, date-only, and timezone-less timestamp metadata during DTO decode before Android chat-history state, memory review state, local persistence, source approval, citation, trusted-source review, permission, audit, direct Android backend access, or physical Android proof exists."
echo "Covered Android chat.messages.list request bounds decode addendum: Android ChatMessagesListRequestPayload rejects blank session_id values plus negative and over-maximum limit values during decode before runtime chat-store dispatch, local persistence, chat compaction metadata projection, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android chat title and session mutation request bounds decode addendum: Android ChatTitleRequestPayload rejects blank session_id values, blank model values, and empty messages during decode, ChatSessionRenamePayload rejects blank session_id and title values, and ChatSessionLifecyclePayload rejects blank session_id values before backend title generation, runtime title mutation, runtime chat-store lifecycle mutation, local persistence, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android chat.title.result closed-payload app-path addendum: RuntimeClientViewModel rejects unknown chat.title.result response metadata before generated-title publication or device storage mutation, preserves the pending title request for a canonical retry, then clears the stale invalid-payload error when the canonical title result is accepted before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android chat.session mutation result closed-payload app-path addendum: RuntimeClientViewModel rejects unknown chat.session.rename and chat.session lifecycle response metadata before runtime session cache publication or device storage mutation, preserves pending mutation requests for canonical retry, then clears stale invalid-payload errors when canonical acknowledgements are accepted before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android model pull and chat cancel request bounds decode addendum: Android ModelPullPayload accepts only 1..256 printable ASCII model characters without edge spaces and ChatCancelPayload rejects blank target_request_id values during decode before runtime model installation dispatch, active generation cancellation, local persistence, live-provider behavior, production relay/session/encryption, direct Android backend access, or physical Android proof exists."
echo "Covered Android memory.list request bounds decode addendum: Android MemoryListRequestPayload rejects empty query values during DTO decode before runtime memory-store search dispatch, local persistence, memory source approval, citations, trusted-source review, permission, or audit semantics exist."
echo "Covered Android memory CRUD request bounds decode addendum: Android MemoryUpsertPayload rejects blank optional id values and blank content values, and MemoryDeletePayload rejects blank id values during decode before runtime memory-store mutation, local persistence, memory source approval, citations, trusted-source review, permission, or audit semantics exist."
echo "Covered Android memory summary drafts list request bounds decode addendum: Android MemorySummaryDraftsListRequestPayload rejects negative and over-maximum limit values during decode before runtime chat-store draft listing, memory upsert, dismiss mutation, local persistence, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android memory summary draft decision request bounds decode addendum: Android MemorySummaryDraftApprovePayload and MemorySummaryDraftDismissPayload reject blank draft_id values, blank optional content or expected_session_id values, and nonpositive expected_source_message_count values during decode before runtime chat-store draft recomputation, memory upsert, dismiss mutation, local persistence, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android memory summary draft response bounds decode addendum: Android MemorySummaryDraftPayload, MemorySummaryDraftSessionPayload, MemorySummaryDraftSourcePointerPayload, MemoryEntryPayload, and MemoryEntrySourcePayload reject empty ids/content/source fields, nonpositive source counts, negative session counters, empty pointer lists, invalid source pointer roles, and invalid source kind or summary_method values during decode before Android memory review UI state, runtime-owned memory state, local persistence, source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android memory.summary.drafts.list closed-payload app-path addendum: RuntimeClientViewModel rejects unknown top-level memory.summary.drafts.list response metadata, unknown per-draft metadata, unknown draft session metadata, and unknown draft source-pointer metadata before memory review state publication or device storage mutation, then accepts a canonical retry before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android memory summary draft decision result closed-payload app-path addendum: after exact request, channel, and authority correlation, RuntimeClientViewModel treats unknown memory.summary.draft.approve and memory.summary.draft.dismiss result metadata as terminal, consumes the correlation, clears action UI, drains one deferred refresh, ignores a late result using the old request id, and keeps backend_url and workspace_id canaries out of runtime memory, review state, and device storage before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered Android memory CRUD result closed-payload app-path addendum: RuntimeClientViewModel rejects unknown memory.upsert result metadata and unknown memory.delete result metadata before runtime memory state mutation or device storage mutation, then accepts canonical retries while keeping backend_url and workspace_id canaries out of state/storage before source approval, citation, trusted-source review, permission, or audit semantics exist."
echo "Covered strict allocated relay crypto v2 addendum: Android and macOS perform ephemeral P-256 ECDH, mix the shared secret with the QR relay secret through HKDF-SHA256 over a canonical per-connection transcript, mutually confirm the derived binding before encrypted frames, bind paired-identity v2 authentication to it, rotate directional AES-GCM epoch keys every 65,536 frames, reject ordered replay and authentication failures without advancing receive state, and fail closed before Int64 frame-counter exhaustion. Local direct and legacy plaintext diagnostics remain unchanged. This is not post-compromise security, a complete unordered replay window, production end-to-end deployment, or physical-device proof."
echo "Covered pair-scoped relay room authorization addendum: shared Swift and Android runtime-client-p256-v2 transcripts bind current and next relay ids, schema-v4 atomically rotates a consumed bootstrap allocation into a pair-derived room with a persistent tombstone, paired client sockets authenticate before matcher admission, active rooms reject duplicate pairs until release, stale waiting generations are closed, and Android fails closed on missing or mismatched admission challenges. This no-device foundation does not provide allocation-channel TLS/server authentication, immediate active-session revocation, production P2P/NAT traversal, or physical Android proof."
echo "Covered macOS runtime connection ownership completion addendum: one main-actor manager owns the local listener, Bonjour advertiser, bootstrap relay, and fingerprint-keyed pair transports. It starts the listener before advertising exact route metadata, stops partial local ownership and advertisement after failed start, replaces prior local ownership in stop-before-start order, refreshes only Bonjour while the current listener remains valid, tears down stale Bonjour and local ownership after asynchronous listener failure, forwards local and relay disconnect ids to the runtime router, invalidates replaced, retired, stopped, and failed message-callback leases plus relay status generations, waits for admitted message callbacks before external invalidation returns, and performs one idempotent unified shutdown. This is no-device Swift lifecycle and mock evidence, not cross-machine Bonjour discovery, production TLS/KEX/pair-epoch, public-network, optical QR, or physical Android proof."
echo "Covered macOS pair-scoped private-overlay lifecycle seam addendum: an optional injected private-overlay transport is owned per client fingerprint beside, but independently from, the pair relay transport. Pair activation and restored-route startup attempt the overlay before relay fallback; generation and synchronized message leases reject superseded callbacks before stop; terminal stop leases prevent an already-stopped transport from being stopped again; runtime and fingerprint lifecycle generations block delayed refresh activation after runtime stop and block persistence after pair revocation while preserving an already-committed advancing lease for restart recovery; fingerprint-keyed pending activations preserve overlapping pairs; same-fingerprint request sequences, in-flight tracking, captured-base compare-and-swap persistence, and deferred activation reconciliation preserve an older committed lease across a newer failure while rejecting a conflicting late overwrite; overlay and relay failed states do not remove the other candidate; abstract local, relay, and overlay disconnect capabilities forward exact UUIDs for router cleanup; pair-scoped stop releases only that fingerprint; and idempotent stop-all releases both resource families once. No concrete P2P connector, signaling, candidate exchange, STUN, TURN, hole punching, protocol message, production relay selection, physical Android, optical QR, public-network, or real different-network behavior is implemented or proven."
echo "Covered relay allocation cross-process ownership addendum: durable schema-v4 registry operations bind an established marker token to the store, reload under transaction byte-range 0 before compare-and-swap, persist through descriptor-relative mode-600 fsync-and-rename, and hold owner byte-range 1 for the relay lifetime so a second process cannot split matcher or active-room state. Timed monotonic lock retries prevent unbounded startup waits, inode aliases reuse one process lock descriptor, consumed bootstrap leases cannot be recreated by stale writers, interrupted token-matched initialization recovers, and same-instance concurrent run attempts fail without releasing the live listener. Missing/replaced/hard-linked state fails closed, simultaneous first start converges to one owner, process exit releases ownership, and a successor reopens the same token-bound store. This does not provide distributed multi-host consensus, allocation-channel TLS/server authentication, or physical Android proof."
echo "Covered relay abuse-control foundation addendum: accepted sockets hold one global permit across control handling, waiting-peer storage, and active bridging; disconnected waiters reclaim permits; every control record uses one absolute monotonic read deadline while preserving the 4096-byte limit; exposed probe is disabled by default; exposed legacy relay mode fails closed; Android continues to authenticated relay connection when the probe oracle is unsupported. This is no-device development-relay hardening, not allocation rate limiting, per-IP quotas, production TLS, public-relay deployment, or physical Android proof."
echo "Covered relay source-aware allocation control addendum: only the exact cheap strict preflight envelope selects preflight; malformed, duplicate, mutation-like allocation and renewal attempts consume the stricter mutation bucket before full parsing. Separate monotonic token buckets use canonical accepted IPv4/IPv6 source and IPv6 scope. A shared unknown-source bucket, shared overflow bucket without capacity-reset bypass, periodically counted idle sweeps, full-refill-before-retention validation, stable source-free reason counters, and CLI defaults 120/30 and 30/10 bound at most 4096 tracked buckets without per-request full-map scans. Peer admission, waiting rooms, active bridges, probes, and encrypted forwarding do not consume these rate buckets; separate source peer quotas govern accepted-connection and waiting admission. This is no-device development-relay control-plane hardening, not production capacity validation, public-relay deployment, live-network proof, or physical Android proof."
echo "Covered relay source peer quota addendum: canonical accepted IPv4/IPv6 source identity now bounds concurrent accepted sockets at 64 per source and unmatched waiting peers at 32 per source by default, with no disable value and 2:1 counterpart headroom validation. Normal admission keeps one global and one per-source slot available before the first waiter, and every waiting insertion atomically rechecks both connection-plus-reservation bounds. Global/source reserve provenance remains attached to each candidate, so per-source reserve can discharge only a waiter owned by that source while global-only reserve may match across sources. A socket admitted from reserve is counterpart-only, cannot run probe/allocation or become another waiter, and is confirmed only by an immediate permitted opposite-role match or authenticated same-source waiting replacement. Nonmatching and cross-source replacement candidates close with source-free counters without displacing the original waiter, while matcher-atomic accounting releases counts on match, replacement, disconnect, generation invalidation, and close. Active bridges remain counted against source connection quotas, while established encrypted frame forwarding is not throttled or evicted. Stable source-free reasons and saturating metrics expose only aggregate counts. Shared carrier-NAT/VPN users share quotas, so these are configurable development-relay guardrails rather than per-user isolation or production capacity proof. This is no-device synthetic and loopback evidence, not public-relay, live-network, or physical Android proof."
echo "Covered relay bounded waiting and authenticated identity fairness addendum: unmatched rooms retain one monotonic first-registration deadline across same-role replacements, cap it by allocation lease expiry, and close after 60 seconds by default. Matcher-atomic registration and readiness-probe expiration prevents delayed timer delivery from allowing a late match, replacement, or readiness result. Waiting registration returns the deadline in the same transaction, so a concurrent counterpart match cannot turn a later room lookup into a false missing-deadline close. Runtime keys and paired-client keys that complete cryptographic relay admission may hold at most 4 unmatched waits per role-separated identity across source addresses; unauthenticated bootstrap clients remain source-quota-only. Timeout, match, replacement, disconnect, invalidation, and close release exact source and identity counts. Stable source-free timeout and identity-quota reasons plus saturating metrics expose aggregate counts only. Active bridges cancel waiting timers and remain unthrottled. This is configurable no-device development-relay fairness evidence, not per-user isolation, public-network capacity proof, production identity service, or physical Android proof."
echo "Covered production relay security design addendum: evidence-pinned portfolio recommends TLS 1.3 plus delegated signed lease capabilities, peer-verifiable identity KEX, and a monotonic pair-epoch recovery state machine with deny-only revocation and signed status reconciliation. This validates design artifacts only; it does not claim implementation, production relay deployment, public-network behavior, or physical Android proof."
echo "Covered production P2P/NAT bounded no-network handoff addendum: explicit approval selects authenticated-encrypted-ice-turn with transport-neutral-identity-session, requires relay-only-sealed-signaling rollback, and defers decentralized rendezvous, QUIC, and relay-first promotion. Shared Swift/Kotlin ALP1 evidence contains seven positive vectors across all five canonical object types plus nine negative vectors, including on-curve P-256, receipt-time freshness, transcript SHA-256, and role-bound HMAC; bounded candidate policy, pair-and-role replay, expiry, resource ceilings, and readiness/fallback state machines fail closed without network I/O. Handoff-v2 records canonical-contracts and no-network-conformance completed while controlled-network-spike remains blocked, all packages keep networkIOAllowed=false, all seven pre-network decisions remain open, productionDesignStatus stays not_implemented, and route.refresh stays the only active traversal namespace. This does not claim a concrete connector, STUN/TURN traffic, candidate exchange, hole punching, NAT behavior, public-network reachability, latency or memory measurements, optical QR, or physical Android proof."
echo "Covered production P2P/NAT pre-network approval addendum: immutable review-v1 preserves exactly seven canonically ordered proposed_not_selected recommendations, decision-v1 resolves all seven to their recommended options with explicit_user_instruction, and closed handoff-v3 supersedes handoff-v2. The 15-test mutation suite rejects missing, duplicate-key, unknown, reordered, partial, mismatched, evidence-drifted, weakened, fabricated-measurement, or unauthorized states; handoff-v3 hash-pins Android P2pNatContract.kt, the no-network scan covers SocketFactory.createSocket and CFStreamCreatePairWithSocketToHost, the security-design validator directly verifies canonical handoff closure, and Kotlin and Swift P2P/NAT contract/conformance suites execute in the default gate. controlled-network-spike remains blocked_on_separate_review by networking_library_selection, session_cryptography_library_selection, isolated_harness_design, and socket_destination_and_egress_controls; networkIOAllowed, librarySelectionAuthorized, productionDeploymentAuthorized, and controlledNetworkSpikeSocketExecutionAuthorized stay false. This is policy approval and no-device validation only, not ICE/STUN/TURN implementation, candidate exchange, NAT traversal, physical Android, optical QR, live-network, performance, battery, capacity, deployment, or production-readiness proof."
echo "Covered production P2P/NAT controlled-spike review addendum: closed review-v1 proposes exactly four canonically ordered recommendations and selects zero. It recommends libjuice-1.7.2-static-c-abi subject to exact source and regular-nomination/consent audit, platform-native-p256-hkdf-sha256-aes256gcm, linux-netns-twin-agent-local-services, and numeric-endpoint-allowlist-plus-os-egress-witness. The 10-test mutation suite rejects implicit selection, incomplete or reordered decisions, option or source drift, weakened security floors, fabricated measurements, authorization, handoff, and immutability changes. librarySelectionAuthorized, harnessImplementationAuthorized, networkIOAllowed, socketExecutionAuthorized, productionDeploymentAuthorized, and nextHandoffAuthorized remain false. This is official-source review and no-device validation only, not source download, library selection, compilation, harness implementation, socket execution, ICE/STUN/TURN traffic, NAT traversal, physical Android, live-network, performance, deployment, or production-readiness proof."
echo "Covered production P2P/NAT controlled-spike phase A approval addendum: separate decision-v1 records explicit_user_instruction for all four canonical recommendations as approved_for_bounded_phase_a_evidence, and closed handoff-v4 supersedes handoff-v3 while preserving both completed package evidence maps and all seven pre-network resolutions. Offline inspection/pinning of user-provided or pre-existing workspace libjuice source, Android/macOS compile-only integration, transport-neutral session-cryptography vectors, and static phase A harness/egress policy work are authorized; git clone/fetch, download tools, package-manager source acquisition, and inspected-code execution are prohibited. The 17-test mutation suite rejects partial, reordered, implicit, evidence-drifted, offline-source-policy-expanded, phase-expanded, network/socket/phase-B-authorized, bool/int-type-confused, fabricated-measurement, namespace-expanded, mutable, or misleading states, and the independent security-design validator verifies the same handoff. sourceAcquisitionNetworkIOAllowed, controlledSpikeNetworkIOAllowed, controlledSpikeSocketExecutionAuthorized, phaseBExecutionAuthorized, productionNetworkIOAllowed, and productionDeploymentAuthorized remain false. This is no-device/static approval evidence only, not completed source audit, compilation, executable harness, socket execution, ICE/STUN/TURN traffic, NAT traversal, physical Android, live-network, performance, deployment, or production-readiness proof."
echo "Covered production P2P/NAT controlled-spike phase A crypto and static-policy addendum: the shared ALP1 fixture and independent Python oracle verify direct and relay P-256 ECDH, leading-zero secret normalization, transcript-bound HKDF-SHA-256 key separation, role-bound bidirectional confirmation, single-use ephemeral derivation, key-owned one-shot cipher issuance, deterministic directional AES-256-GCM nonce/AAD construction, tamper/replay/provider failure, concurrent sequence safety, and counter exhaustion across Swift CryptoKit and provider-neutral Android JCA. An execution-before-import AST allowlist and 22-file SHA-256 preflight runs before the Phase A validators. The static harness artifact hash-pins decision-v1, review-v1, and handoff-v4; fixes agent_a, agent_b, stun_service, and turn_service; permits only exact numeric UDP tuples; rejects DNS, DoH, DoT, proxy, redirect, wildcard, range, malformed, loopback, link-local, broadcast, unlisted private, unspecified, multicast, and general external TCP/UDP IPv4/IPv6 egress; and keeps retainedRuntimeEvents empty. All execution, socket, network, measurement, Phase B, and production gates remain false. Offline libjuice source audit and actual Android/macOS C ABI compile-only evidence remain blocked because no reviewed offline libjuice source is present. This is no-device/static interoperability and policy proof, not dependency execution, executable netns proof, packet capture, ICE/STUN/TURN traffic, NAT traversal, physical Android, optical QR, live-network, performance, deployment, or production-readiness proof."
echo "Covered production P2P/NAT controlled-spike phase A offline-source and compile-boundary addendum: offline-source-intake-v1 fixes build/offline-source/libjuice-1.7.2 as the only reviewed intake location and validates the current blocked_missing_offline_source state; an unexpected source drop fails closed until a new versioned reviewed manifest records exact provenance, commit, archive and file digests, license, generated files, dependency closure, and build flags. libjuice-compile-only-contract-v1 keeps android_macos_compile_only_integration=blocked_missing_reviewed_source and records only a future direct-compile/static-archive C ABI boundary for Android minSdk 26 arm64-v8a and x86_64 plus macOS 14.0 arm64 and x86_64. No source was acquired or executed, no compiler was invoked, no native adapter or build wiring was created, and all socket, network, Phase B, measurement, and production gates remain closed. This is no-device/static blocked-state evidence, not source-audit completion, compilation, ABI compatibility, library behavior, ICE/STUN/TURN, NAT traversal, physical Android, live-network, deployment, or production-readiness proof."
echo "Covered production P2P/NAT controlled-spike phase A progress addendum: immutable progress-v1 records 4 bounded Phase A approvals, 2 bounded evidence groups completed, 2 bounded evidence groups blocked, and the final Phase A security review blocked_on_source_and_compile_evidence. Source acquisition, source execution, compiler/archive invocation, socket creation, runtime/harness/controlled-spike network I/O, Phase B network/socket/external egress, production network I/O, and production deployment remain false. The 7-test progress mutation suite independently rejects authority, evidence, source-chain, measurement, Phase B, and immutability drift. This is no-device/static progress evidence only, not source acquisition, compilation, library execution, sockets, network traffic, Phase B, external egress, production deployment, or production-readiness proof."
echo "Covered macOS host document source review and audit export addendum: one security-scoped coordinated regular-file selection is copied into a bounded owner-only private snapshot, reviewed without approving or exposing content, and shared with explicit runtime_shared scope only after a versioned one-time ten-minute confirmation. Replacements preserve the active revision until source-revision compare-and-swap commits on the same SQLite store used by the runtime router; removal requires the current revision and retains content-free audit tombstones. The inspector previews 50 app-data-lifetime audit events and exports at most the latest 1,000 without paths, bookmarks, bodies, queries, snippets, or pending content. Citations, a client trusted-source review protocol, physical Android, optical QR, live-provider semantic quality, production relay/P2P, and real-network behavior remain unproven."
echo "Covered structured answer source attribution addendum: successful nonblank stop completions can store one through eight ordered runtime-generated source references containing only source_index, safe document_name, canonical mime_type, and nonnegative chunk_index from contexts actually supplied to generation. Capability-negotiated authenticated chat.done and history responses project that historical snapshot; legacy clients retain the old shape, later revoke does not rewrite completed provenance, regenerate replaces prior attribution, and cancel, error, blank, audit-failed, or source-free requests expose none. Android strictly decodes, sanitizes, persists, restores, and renders the source list between answer and actions with localized accessibility summaries. This does not claim sentence-level entailment, current authorization, physical Android rendering, live-provider citation quality, optical QR, production relay/P2P, or real-network proof."
echo "Covered authenticated historical chat source attribution review addendum: chat.source_attribution.resolve uses exact session_id, server-generated non-authorizing assistant_message_id, and source_index input under chat.source_attribution.resolve.v1. Normal done/history keeps source_attributions at exactly four safe display fields and never exposes source text or the internal source_index, source_anchor_id, document_id, and source_revision binding. Review preparation resolves canonical owner-scoped history, atomically revalidates current runtime_shared approval and the exact historical revision, and fails closed for regenerated, deleted, legacy, stale, replaced, or revoked sources without display-metadata inference. Capability omission and partial capability compatibility are router-unit evidence; live smoke covers the fully capable request, happy response, forbidden metadata, exact invalid_payload and chat_source_attribution_not_found failures, authentication rejection, and connection survival. Android reuses the existing review dialog; only the locator may persist while authority ids, tokens, and revisions remain private and transient. This remains no-device evidence and does not claim physical Android, live-provider citation quality, production relay/P2P, or real-network proof."
echo "Physical external-relay QA gate: script/check_physical_external_relay_pairing.sh --relay-host <public-or-vpn-host> writes build/qa/android-external-relay-pairing.json and must be run with a real attached phone on the target network."
echo "Not covered by this no-device gate: physical install, camera QR scan, real device haptics, physical TalkBack/VoiceOver traversal, Android system/per-app locale mutation on hardware, launcher/Dock screenshots, physical/live-backend streamed chat/cancel or chat-complete, and real different-network runtime connectivity."
