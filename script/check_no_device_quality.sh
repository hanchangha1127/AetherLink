#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

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

  port="$(free_tcp_port)"
  summary_path="$(mktemp "${TMPDIR:-/tmp}/aetherlink-runtime-preflight-summary.XXXXXX")"
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
assert summary["allocation"]["relay_id_present"] is True, summary
assert summary["allocation"]["relay_expires_at_present"] is True, summary
assert summary["allocation"]["relay_nonce_present"] is True, summary
assert summary["allocation"]["has_relay_secret"] is True, summary
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
  local normal_output

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
  normal_output="$(python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token normal-route \
    --persist \
  )"
  local normal_status=$?
  sleep 0.2
  python3 - "$store" "$normal_output" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(sys.argv[2])
contents = Path(sys.argv[1]).read_text(encoding="utf-8")
assert "requested_route_token" not in payload, payload
assert "rt1-" in contents, contents
assert payload["relay_id_present"] is True, payload
assert payload["relay_expires_at_present"] is True, payload
assert payload["relay_nonce_present"] is True, payload
assert payload["route_material_redacted"] is True, payload
assert "relay_id" not in payload, payload
assert "relay_expires_at" not in payload, payload
assert "relay_nonce" not in payload, payload
assert "relay_secret" not in payload, payload
assert payload["has_relay_secret"] is True, payload
assert "rt1-" not in json.dumps(payload), payload
assert "normal-route" not in json.dumps(payload), payload
assert "normal-route" not in contents, contents
assert "preflight-route" not in contents, contents
PY
  local normal_store_status=$?
  local status_code=$?
  set -e
  if [[ "$preflight_status" -ne 0 ]]; then
    status_code="$preflight_status"
  elif [[ "$preflight_store_status" -ne 0 ]]; then
    status_code="$preflight_store_status"
  elif [[ "$normal_status" -ne 0 ]]; then
    status_code="$normal_status"
  else
    status_code="$normal_store_status"
  fi

  if [[ -n "$relay_pid" ]]; then
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
  fi
  rm -rf "$work_dir"
  return "$status_code"
}

check_relay_preflight_rejects_raw_route_token_echo_guard() {
  local port
  local work_dir
  local fake_pid
  local output
  local status_code

  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-echo-preflight.XXXXXX")"
  fake_pid=""

  python3 - "$port" "$work_dir" <<'PY' &
import json
import socket
import sys
import time
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
        parts = request.split()
        route_token = parts[2] if len(parts) >= 3 else "missing-route-token"
        payload = {
            "relay_id": route_token,
            "relay_secret": "fake-relay-secret",
            "relay_expires_at": int(time.time()) + 300,
            "relay_nonce": "fake-relay-nonce",
        }
        line = "AETHERLINK_RELAY allocation " + json.dumps(payload, separators=(",", ":")) + "\n"
        connection.sendall(line.encode("utf-8"))
PY
  fake_pid="$!"

  for _ in {1..30}; do
    if [[ -f "$work_dir/ready" ]]; then
      break
    fi
    if ! kill -0 "$fake_pid" >/dev/null 2>&1; then
      echo "Fake relay allocation echo server exited before listening." >&2
      rm -rf "$work_dir"
      exit 1
    fi
    sleep 0.1
  done
  if [[ ! -f "$work_dir/ready" ]]; then
    echo "Fake relay allocation echo server did not become ready." >&2
    kill "$fake_pid" >/dev/null 2>&1 || true
    wait "$fake_pid" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
    exit 1
  fi

  set +e
  output="$(python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token echoed-route-token \
    --timeout 2 \
    --quiet \
    2>&1 >/dev/null)"
  status_code=$?
  wait "$fake_pid" >/dev/null 2>&1 || true
  set -e

  if [[ "$status_code" -eq 0 ]]; then
    echo "Relay allocation preflight should reject relay_id values that echo the raw route token." >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"echoed the requested route token as relay_id"* ]]; then
    echo "Relay allocation preflight did not explain the raw route-token relay_id echo rejection." >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if ! grep -q "AETHERLINK_RELAY allocate echoed-route-token" "$work_dir/request.txt"; then
    echo "Fake relay allocation echo server did not capture the expected route token request." >&2
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
    --relay-secret failure-redaction-relay-secret \
    --timeout 2 \
    --quiet \
    2>&1 >/dev/null)"
  status_code=$?
  wait "$fake_pid" >/dev/null 2>&1 || true
  set -e

  if [[ "$status_code" -eq 0 ]]; then
    echo "Relay allocation preflight should fail for malformed allocation responses." >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"did not return an allocation response"* ]]; then
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
import time
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
            "relay_id": "rt1-unexpected-field-relay",
            "relay_secret": "unexpected-field-relay-secret",
            "relay_expires_at": int(time.time()) + 300,
            "relay_nonce": "unexpected-field-relay-nonce",
            "requested_route_token": "leaked-route-token",
            "backend_url": "http://127.0.0.1:11434/api/tags",
            "provider_url": "https://provider.example.test/v1/models",
            "allocation_token": "leaked-allocation-token",
            "relay_secret_debug": "leaked-relay-secret",
        }
        line = "AETHERLINK_RELAY allocation " + json.dumps(payload, separators=(",", ":")) + "\n"
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
    --relay-secret unexpected-field-relay-secret \
    --timeout 2 \
    --quiet \
    2>&1 >/dev/null)"
  status_code=$?
  wait "$fake_pid" >/dev/null 2>&1 || true
  set -e

  if [[ "$status_code" -eq 0 ]]; then
    echo "Relay allocation preflight should reject allocation responses with unexpected metadata fields." >&2
    rm -rf "$work_dir"
    exit 1
  fi
  if [[ "$output" != *"unsupported metadata"* ]]; then
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
import time
from pathlib import Path

port = int(sys.argv[1])
work_dir = Path(sys.argv[2])
ready_path = work_dir / "ready"

def payload(**overrides):
    value = {
        "relay_id": "rt1-canonical-relay",
        "relay_secret": "canonical-relay-secret",
        "relay_expires_at": int(time.time()) + 300,
        "relay_nonce": "canonical-relay-nonce",
    }
    value.update(overrides)
    return value

payloads = {
    "case-relay-id-whitespace": payload(relay_id="rt1 bad"),
    "case-relay-secret-whitespace": payload(relay_secret="secret value"),
    "case-relay-nonce-whitespace": payload(relay_nonce="nonce value"),
    "case-relay-id-url": payload(
        relay_id="https://provider.example.test/v1/rooms?route_token=leaked-route-token"
    ),
    "case-relay-expires-non-int": payload(relay_expires_at="not-an-int"),
    "case-relay-expires-numeric-string": payload(relay_expires_at=str(int(time.time()) + 300)),
    "case-relay-expires-bool": payload(relay_expires_at=True),
    "case-relay-expires-zero": payload(relay_expires_at=0),
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
            route_token = parts[2] if len(parts) >= 3 else "case-relay-id-whitespace"
            response_payload = payloads.get(route_token, payloads["case-relay-id-whitespace"])
            line = "AETHERLINK_RELAY allocation " + json.dumps(response_payload, separators=(",", ":")) + "\n"
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
    "case-relay-id-whitespace|invalid relay_id" \
    "case-relay-secret-whitespace|invalid relay_secret" \
    "case-relay-nonce-whitespace|invalid relay_nonce" \
    "case-relay-id-url|invalid relay_id" \
    "case-relay-expires-non-int|invalid relay_expires_at" \
    "case-relay-expires-numeric-string|invalid relay_expires_at" \
    "case-relay-expires-bool|invalid relay_expires_at" \
    "case-relay-expires-zero|expired relay_expires_at"
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
      "rt1 bad" \
      "secret value" \
      "nonce value" \
      "provider.example.test" \
      "route_token=" \
      "leaked-route-token" \
      "not-an-int" \
      "true"
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
    --relay-secret host-input-relay-secret \
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
  local persisted_status
  local persisted_store_status
  local status_code
  local persisted_output

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
  python3 - "$store" <<'PY'
import sys
from pathlib import Path

store = Path(sys.argv[1])
contents = store.read_text(encoding="utf-8") if store.exists() else ""
assert "token-preflight-route" not in contents, contents
PY
  preflight_store_status=$?
  persisted_output="$(python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token token-persisted-route \
    --relay-secret token-relay-secret-should-not-persist \
    --allocation-token no-device-allocation-token \
    --persist \
    --timeout 2 \
  )"
  persisted_status=$?
  sleep 0.2
  python3 - "$store" "$persisted_output" "$work_dir/relay.log" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(sys.argv[2])
contents = Path(sys.argv[1]).read_text(encoding="utf-8")
log_contents = Path(sys.argv[3]).read_text(encoding="utf-8")
assert "requested_route_token" not in payload, payload
assert "rt1-" in contents, contents
assert payload["relay_id_present"] is True, payload
assert payload["relay_expires_at_present"] is True, payload
assert payload["relay_nonce_present"] is True, payload
assert payload["route_material_redacted"] is True, payload
assert "relay_id" not in payload, payload
assert "relay_expires_at" not in payload, payload
assert "relay_nonce" not in payload, payload
assert "relay_secret" not in payload, payload
assert payload["has_relay_secret"] is True, payload
assert "rt1-" not in json.dumps(payload), payload
assert "token-persisted-route" not in json.dumps(payload), payload
assert "token-relay-secret-should-not-persist" not in json.dumps(payload), payload
assert "token-persisted-route" not in contents, contents
assert "token-preflight-route" not in contents, contents
assert "unauthorized-missing-token-route" not in contents, contents
assert "unauthorized-wrong-token-route" not in contents, contents
assert "token-relay-secret-should-not-persist" not in contents, contents
assert "no-device-allocation-token" not in contents, contents
assert "wrong-no-device-allocation-token" not in contents, contents
assert "token-persisted-route" not in log_contents, log_contents
assert "token-preflight-route" not in log_contents, log_contents
assert "unauthorized-missing-token-route" not in log_contents, log_contents
assert "unauthorized-wrong-token-route" not in log_contents, log_contents
assert "token-relay-secret-should-not-persist" not in log_contents, log_contents
assert "no-device-allocation-token" not in log_contents, log_contents
assert "wrong-no-device-allocation-token" not in log_contents, log_contents
PY
  persisted_store_status=$?
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
  elif [[ "$persisted_status" -ne 0 ]]; then
    status_code="$persisted_status"
  else
    status_code="$persisted_store_status"
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

  "$relay_bin" \
    --host 0.0.0.0 \
    --port "$token_port" \
    --require-allocation \
    --ephemeral-allocations \
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

  token="no-device-dry-run-token"
  summary_path="$(mktemp "${TMPDIR:-/tmp}/aetherlink-relay-dry-run-summary.XXXXXX")"
  set +e
  output="$(
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
  rm -f "$summary_path"

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
    --relay-secret "secret+with/symbols=" \
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
    --relay-secret "secret+with/symbols=" \
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
assert summary["coverage"]["production_relay"] is False, summary
assert summary["coverage"]["production_session_key_exchange"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption"] is False, summary
assert summary["probe_summaries"]["device_relay_endpoint"] is None, summary
assert summary["probe_summaries"]["device_relay_route"] is None, summary
assert summary["android_device"]["requested_adb_serial"] == "no-device-serial-1", summary
assert summary["android_device"]["observed_adb_serial"] is None, summary
assert "device_endpoint_probe_not_reachable_or_missing" in summary["caveats"], summary
assert "device_route_probe_not_ready_or_missing" in summary["caveats"], summary
assert "does_not_expose_ollama_or_lm_studio_to_android" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "--serial" in summary["command"], summary
assert "no-device-serial-1" in summary["command"], summary
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
assert summary["coverage"]["production_relay"] is False, summary
assert summary["coverage"]["production_session_key_exchange"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption"] is False, summary
assert summary["android_device"]["observed_adb_serial"] is None, summary
assert "physical_external_relay_pairing_failed" in summary["caveats"], summary
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
assert summary["coverage"]["external_relay_route_ready"] is True, summary
assert summary["coverage"]["probe_summary_redaction_self_test"] is True, summary
assert summary["coverage"]["live_android_device_probe_verified"] is False, summary
assert summary["coverage"]["physical_external_relay_verified"] is False, summary
assert summary["coverage"]["production_relay"] is False, summary
assert summary["coverage"]["production_session_key_exchange"] is False, summary
assert summary["coverage"]["production_end_to_end_transport_encryption"] is False, summary
assert summary["coverage"]["wrapper_log_artifact_present"] is True, summary
assert summary["coverage"]["wrapper_log_omits_temporary_secret_material"] is True, summary
assert summary["coverage"]["wrapper_log_contains_unredacted_route_material"] is False, summary
assert summary["coverage"]["runtime_log_artifact_present"] is True, summary
assert summary["coverage"]["runtime_log_contains_temporary_pairing_material"] is True, summary
assert summary["coverage"]["runtime_log_contains_temporary_route_material"] is True, summary
assert "wrapper_log_contains_unredacted_route_material" not in summary["caveats"], summary
assert "wrapper_log_redaction_not_verified" not in summary["caveats"], summary
assert "self_test_redaction_only_not_physical_relay_proof" in summary["caveats"], summary
assert "not_production_session_key_exchange_proof" in summary["caveats"], summary
assert "not_production_end_to_end_transport_encryption_proof" in summary["caveats"], summary
assert "runtime_log_contains_temporary_pairing_or_route_material" in summary["caveats"], summary
assert "aetherlink://pair?<redacted>" in wrapper_log, wrapper_log
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
  if [[ "$command_line" == *"AETHERLINK_RELAY probe"* ]]; then
    echo "AETHERLINK_RELAY probe known=1 runtime_waiting=1 relay_id=rt1-sensitive-route-material"
    exit 0
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
assert summary["probe"]["output"] == "AETHERLINK_RELAY probe known=1 runtime_waiting=1 relay_id=<relay-id>", summary
assert "redaction self-test" in stdout, stdout
assert "not phone reachability proof" in stdout, stdout
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
run check_legacy_relay_guard
run check_link_local_relay_guard
run check_different_network_relay_endpoint_input_redaction_guard
run check_no_adb_external_relay_url_host_redaction_guard
run check_different_network_preflight_summary_guard
run check_relay_preflight_allocation_guard
run check_relay_preflight_rejects_raw_route_token_echo_guard
run check_relay_preflight_failure_output_redaction_guard
run check_relay_preflight_unexpected_field_rejection_guard
run check_relay_preflight_response_value_canonicality_guard
run check_relay_preflight_host_input_guard
run check_relay_exposed_bind_token_guard
run check_relay_wrapper_dry_run_allocation_token_redaction_guard
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
run ./script/runtime_authenticated_mock_smoke.swift --relay --expect-p2p-route-refresh

run ./gradlew --no-daemon \
  :core:pairing:testDebugUnitTest \
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
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadPreservesProviderAndEmbeddingMetadata \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.modelInfoPayloadDefaultsMissingCapabilitiesToEmptyList \
  --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.memoryPayloadsUseProtocolFieldNames \
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
  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayFrameCryptorBindsRouteNonceIntoKey \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayFrameCryptorMatchesNonceBoundSharedCiphertextVectors \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayConnectTimesOutWhenReadyLineNeverArrives \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayConnectFailsWhenReadyLineRejectsRoute \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayChannelEncryptsSentFramesAndDecryptsRuntimeResponses \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayClientSerializesEncryptionWithConcurrentSends \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
	  :app:compileDebugKotlin \
		  :app:testDebugUnitTest \
		  --tests com.localagentbridge.android.AppNavigationTest \
		  --tests com.localagentbridge.android.AppNavigationTest.settingsSystemLanguageOptionIsSeparateFromFixedLaunchLanguages \
			  --tests com.localagentbridge.android.AppNavigationTest.pairingQrRawValueAcceptsCompactRelayPayloadsFromScanner \
			  --tests com.localagentbridge.android.AppNavigationTest.pairingQrScannerClassifiesRawValuesBeforeConsumingCameraResult \
			  --tests com.localagentbridge.android.AppNavigationTest.routeNoticeActionIgnoresTrustedLastKnownEndpointForNormalQrFirstRecovery \
			  --tests com.localagentbridge.android.AetherLinkThemeNoDeviceComposeTest \
			  --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest \
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
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelShowsSummaryDraftApprovalAction \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelDisablesPendingSummaryDraftApproval \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelShowsSummaryDraftDismissAction \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelDisablesPendingSummaryDraftDismissal \
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
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.rejectedCompactRelayQrPairingResultClearsPendingRouteAndSecret \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultRejectsIncompleteRelayRouteInsteadOfDirectFallback \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultRejectsIncompleteP2pRouteInsteadOfDirectFallback \
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
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataDropsDirectEndpointFromPendingPairingRouteStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRemovesPendingPairingRelaySecretWhenRouteClearsOrReplaces \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrRetriesAndSendsPairingRequestAfterRelayBecomesReady \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.releasePairingParserRejectsMacosLocalDiagnosticQrRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeHealthStoresModelResidencySnapshotFromAggregateRuntime \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeModelResidencyStatusRedactsUnsafeSnapshotDetails \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectedModelSendStateRejectsEmbeddingModelAsChatModel \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.requestModelInstallRejectsUnknownModelWithoutPersistingOrPulling \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectModelRejectsUnknownModelWithoutPersistingOrPulling \
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
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMessagesDoNotResurrectSessionMissingFromLatestRuntimeSummary \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeSessionSummariesReplaceRuntimeOwnedCacheAndPreserveLocalSessions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeSessionSummariesClampNegativeMessageCounts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingRuntimeOwnedChatRendersInMemoryButRedactsDeviceStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryListRendersInMemoryButRedactsDeviceStorage \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemorySummaryDraftsListRendersReviewStateWithoutDeviceStorage \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.approveMemorySummaryDraftSendsExpectedApprovalAndRendersRuntimeMemoryOnly \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.approveMemorySummaryDraftErrorClearsPendingAndAllowsRetry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.dismissMemorySummaryDraftSendsExpectedDecisionAndRemovesDraft \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.dismissMemorySummaryDraftErrorClearsPendingAndAllowsRetry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryEntriesReplaceAndMutateCachedMemory \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemoryRequestsFreshListAfterPendingListCompletes \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryRequestsFreshListAfterPendingListCompletes \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryCanSendTrimmedQuery \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistorySendsSelectedEmbeddingModelOnlyForSearchQuery \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeChatMessagesListErrorClearsLoadingAndShowsChatHistoryLoadFailed \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryErrorShowsLoadFailureAndAllowsRetry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemoryErrorShowsFailureAndAllowsRetry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemorySummaryDraftsErrorShowsFailureAndAllowsRetry \
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
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshRetryDelayStaysInsideActiveLease \
		  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeSchedulesRouteRefreshBeforeLeaseExpiry \
			  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesRouteRefreshErrorBeforeLeaseExpiry \
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
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.clientCapabilitiesAdvertiseRuntimeOwnedHistoryMemoryAndAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDeltaAppendsReasoningWithoutMixingIntoAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.thinkingDeltaAliasAppendsReasoning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.inlineThinkTagsAreSeparatedFromAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkTagsKeepReasoningCollapsedOutOfAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.activeStreamTerminationClosesTrailingAssistantReasoningState \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkOpeningTagAcrossDeltasDoesNotLeakTagToAnswer \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkClosingTagAcrossDeltasDoesNotLeakTagToReasoning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.incompleteInlineThinkTagPlaceholderIsClearedOnDone \
  -Pkotlin.incremental=false

run swift build --product AetherLink
run swift test --filter RelayServerCoreTests
run swift test --filter 'RelayHandshakeTests/testRejectsNonCanonicalRelayID|RelayProbeTests/testRejectsNonCanonicalRelayID|RelayHandshakeTests/testServerLineFramingRequiresNewlineForRelayHandshake|RelayHandshakeTests/testServerLineFramingRequiresNewlineForAllocationRequest|RelayProbeTests/testServerLineFramingRequiresNewlineForProbeRequest|RelayMatcherTests/testRuntimeWaitingProbeDoesNotConsumePendingRuntime|RelayMatcherTests/testRuntimeWaitingProbeIgnoresWaitingClient'
run swift test --filter 'RelayAllocationTests/testAllocationDerivesOpaqueStableRelayIDFromRouteTokenAndRequestedSecret|RelayAllocationTests/testAllocationRegistryPersistsOpaqueRelayIDWithoutRawRouteToken'
run swift test --filter 'RelayAllocationTests/testParsesAllocationRequestWithBase64RequestedRelaySecret|RelayAllocationTests/testRejectsBlankAllocationTokenAndRelaySecret'
run swift test --filter RelayAllocationTests/testRejectsUnexpectedAllocationRequestMetadata
run swift test --filter RelayAllocationTests/testRejectsInvalidAllocationResponseLineFields
run swift test --filter RelayAllocationTests/testRejectsUnexpectedAllocationResponseLineMetadata
run swift test --filter 'RelayAllocationTests/testAllocationRegistryIgnoresNonAdvancingRenewalForStableRelayID|RelayAllocationTests/testAllocationRegistryAcceptsAdvancingRenewalWithFreshNonce|RelayAllocationTests/testAllocationRegistryLoadsDuplicatePersistedRelayIDsWithAdvancingTicket|RelayAllocationTests/testAllocationRegistrySkipsMalformedPersistedTicketsOnLoad'
run swift test --filter RelayAllocationTests/testAllocationRegistrySkipsPersistedTicketsWithUnexpectedMetadata
run swift test --filter 'RelayAllocationTests/testRelayServerConfigurationUsesShortDefaultAllocationTTL|RelayAllocationTests/testAllocationRegistryExpiresAndRemovesRelayIDs|RelayAllocationTests/testAllocationRegistryPersistsAndReloadsRelayIDs|RelayAllocationTests/testAllocationRegistryPrunesExpiredPersistedRelayIDs'
run swift test --filter TransportTests
run swift test --filter 'RuntimeAdvertisementMetadataTests/testRuntimeAdvertisementMetadataPublishesOnlyRouteTokenIdentityHint|RuntimeAdvertisementMetadataTests/testRejectsWhitespaceMutatedRouteTokenInsteadOfNormalizing|RuntimeAdvertisementMetadataTests/testRejectsRequestedRouteTokenHintsFromDiscoveryTxtMetadata|LocalRuntimeMessageRouterTests/testCompanionAppModelAdvertisesRouteTokenWithoutStableIdentityTXTMetadata'
run swift test --filter 'LocalRuntimeMessageRouterTests/testRuntimeHealthIncludesAggregateProviderStatuses|LocalRuntimeMessageRouterTests/testRuntimeHealthIncludesModelResidencyLastUnloadFailureWithoutRawErrorMessage'
run swift test --filter AetherLinkLocalizationTests
run swift test --filter 'AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactRouteSecrets|AetherLinkLocalizationTests/testRouteDiagnosticDisclosureRedactsSensitiveDetails'
run swift test --filter AetherLinkRenderSmokeTests
run swift test --filter 'AetherLinkLocalizationTests/testRuntimeMemoryInspectorCopyLocalizesAcrossSupportedLanguages|AetherLinkRenderSmokeTests/testRuntimeMemoryInspectorRendersAcrossLanguagesAndAppearances'
run swift test --filter DocumentTextExtractorTests/testRejectsArchiveExtractionWhenResourcePolicyLimitIsExceeded
	run swift test --filter DocumentTextExtractorTests/testRejectsExtractedTextWhenResourcePolicyLimitIsExceeded
	run swift test --filter DocumentTextExtractorTests
	run swift test --filter ProtocolCodecTests/testProtocolEnvelopeDecodeRejectsMalformedRequiredFields
	run swift test --filter ProtocolCodecTests/testProtocolEnvelopeDecodeRejectsUnknownTopLevelFields
	run swift test --filter ProtocolCodecTests/testModelInfoCodablePreservesProviderAndEmbeddingMetadata
		run swift test --filter 'OllamaBackendTests/testListModelsUsesShowCapabilitiesToSeparateEmbeddingModels|OllamaBackendTests/testUnloadModelPostsEmptyChatWithKeepAliveZero|OllamaBackendTests/testUnloadModelHTTPStatusReturnsStructuredError|LMStudioBackendTests/testListModelsParsesNativeLocalLLMAndEmbeddingModelsSeparately|LMStudioBackendTests/testListModelsFallsBackToOpenAICompatibleModels|LMStudioBackendTests/testUnloadModelPostsLoadedInstanceID|LMStudioBackendTests/testUnloadModelHTTPStatusReturnsStructuredError|AggregatingLlmBackendResidencyTests/testSwitchingModelsUnloadsPreviousInactiveModel|AggregatingLlmBackendResidencyTests/testRepeatedSameModelDoesNotUnloadBetweenChats|AggregatingLlmBackendResidencyTests/testIdlePolicyUnloadsActiveModelAfterDelay|AggregatingLlmBackendResidencyTests/testDoneEventClearsInFlightResidencyBeforeClientObservesCompletion|AggregatingLlmBackendResidencyTests/testManualUnloadClearsActiveResidentModelAndEmitsManualEvent|AggregatingLlmBackendResidencyTests/testManualUnloadFailureKeepsStructuredManualFailureReason|AggregatingLlmBackendResidencyTests/testManualUnloadSkipsWhileGenerationIsInFlight|AggregatingLlmBackendResidencyTests/testUnloadFailureEmitsProviderSpecificFailureEventWithoutBreakingNextChat|AggregatingLlmBackendResidencyTests/testInstalledEmbeddingModelIsNotRoutedAsChat|AggregatingLlmBackendResidencyTests/testInstalledCloudChatModelIsNotRoutedAsChat|AggregatingLlmBackendResidencyTests/testUnknownUnqualifiedModelDoesNotFallbackToOllama|AggregatingLlmBackendResidencyTests/testQualifiedModelMustBeReportedByThatProvider|AggregatingLlmBackendResidencyTests/testDuplicateProviderBackendsKeepFirstProviderInsteadOfCrashing'
	run swift test --filter 'LMStudioBackendTests/testChatWithImageAttachmentUsesNativeImageInput|LMStudioBackendTests/testChatWithImageAttachmentFallsBackToOpenAICompatibleVisionContentWhenNativeRejects'
	run swift test --filter 'RuntimeIdentityKeyStoreTests/testFileStoreLoadOrCreatePersistsRuntimeIdentity|RuntimeIdentityKeyStoreTests/testFileStoreCorrectsBroadPermissionsWithoutRotatingIdentity|RuntimeIdentityKeyStoreTests/testFileStoreSignsVerifiableAuthChallenge'
run swift test --filter TrustedDeviceStoreTests
run swift test --filter 'LocalRuntimeMessageRouterTests/testTrustedHelloAndAuthResponseAuthenticatesConnection|LocalRuntimeMessageRouterTests/testHelloRejectsUnknownPayloadMetadataBeforeChallengeCreation|LocalRuntimeMessageRouterTests/testAuthResponseRejectsUnknownPayloadMetadataBeforeAuthentication|LocalRuntimeMessageRouterTests/testResponseOnlyMessageTypesReturnDirectionProtocolError|LocalRuntimeMessageRouterTests/testTrustedHelloIncludesVerifiableRuntimeProofWhenSignerIsAvailable|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsRawNonceSignature|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsReplayedNonceAfterAuthentication|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsSupersededChallengeNonce|LocalRuntimeMessageRouterTests/testUnauthenticatedRuntimeCommandsRejectBeforeProtocolPayloadHandling|LocalRuntimeMessageRouterTests/testPairingRequestStoresTrustedDeviceAndReturnsAccepted|LocalRuntimeMessageRouterTests/testPairingRequestRejectsUnknownPayloadMetadataBeforeTrusting|LocalRuntimeMessageRouterTests/testPairingRequestRejectsBlankAllowedFieldsBeforeTrusting|LocalRuntimeMessageRouterTests/testPairingRequestRejectsWhitespaceMutatedDeviceIdentityBeforeTrusting|LocalRuntimeMessageRouterTests/testConnectionDidCloseClearsAuthenticatedSession|LocalRuntimeMessageRouterTests/testRemovedTrustedDeviceCannotContinueUsingAuthenticatedConnection|LocalRuntimeMessageRouterTests/testRuntimeHealthRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testModelsListRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsUnknownPayloadMetadataBeforeRuntimeProviderDispatch|LocalRuntimeMessageRouterTests/testModelsPullRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testModelsPullRejectsInvalidAllowedPayloadTypesBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatCancelRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendAppendsDocumentAttachmentTextAndPreservesImageAttachment|LocalRuntimeMessageRouterTests/testChatSendExtractsMimeOnlyStructuredTextDocumentAttachment|LocalRuntimeMessageRouterTests/testChatSendRejectsTopLevelPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendRejectsInvalidAllowedPayloadTypesBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatTitleRequestRejectsUnknownPayloadMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatTitleRequestRejectsInvalidAllowedLocaleTypeBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendRejectsMessageSourceMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendRejectsAttachmentSourceMetadataBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatSendImageAttachmentRequiresVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendAllowsLMStudioImageAttachmentsForVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendUnsupportedDocumentAttachmentReturnsStructuredError|LocalRuntimeMessageRouterTests/testChatSendRoutesQualifiedLMStudioModelThroughAggregateBackend'
run swift test --filter LocalRuntimeMessageRouterTests/testUntrustedHelloReturnsPairingRequired
run swift test --filter 'LocalRuntimeMessageRouterTests/testRepeatedInvalidPairingAttemptsInvalidateActiveSession|LocalRuntimeMessageRouterTests/testExpiredAndNoActivePairingRequestsReturnStructuredRejections'
run swift test --filter PairingCoordinatorTests
		run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets|LocalRuntimeMessageRouterTests/testPairingQRCodePayloadCanOmitEndpointHints|LocalRuntimeMessageRouterTests/testPairingQRCodePayloadIncludesRelaySecretWhenPresent|LocalRuntimeMessageRouterTests/testPairingQRCodePayloadIncludesP2PRendezvousRecordWhenPresent|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedP2PRendezvousFixture|LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorUsesStoredBootstrapSettingsWhenEnvironmentIsEmpty|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingFallsBackAcrossBootstrapRelayEndpointsBeforeQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesSavedBootstrapRelayEndpointBeforeQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelStartRenewsSavedBootstrapRelayRouteBeforeRelayStart|LocalRuntimeMessageRouterTests/testCompanionAppModelRenewsBootstrapRelayRouteAfterRelayFailure|LocalRuntimeMessageRouterTests/testCompanionAppModelSavesBootstrapRelaySettingsAndAllocatesRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelAcceptsAdvancingSavedBootstrapLeaseForStableRelayID|LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsNonAdvancingSavedBootstrapLeaseForStableRelayID|LocalRuntimeMessageRouterTests/testCompanionAppModelDoesNotReuseSavedLeaseForDifferentRelayRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesBootstrapQRCodeWithExpiredSavedLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRequiresRemoteQRCodeForLoopbackSavedRelayHost|LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease|LocalRuntimeMessageRouterTests/testCompanionAppModelWaitsForLeaseBeforeUsingCGNATPrivateOverlayRelayQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteReturnsNilWithoutFreshRelayLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial|LocalRuntimeMessageRouterTests/testCompanionAppModelKeepsLeasePreparationIssueWhenRelayIsReadyWithoutLease|LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsUnknownRelayScopeFromRuntimeProvider|LocalRuntimeMessageRouterTests/testChatSendStoresRuntimeSideProcessingEvents|LocalRuntimeMessageRouterTests/testChatSendIntoArchivedRuntimeSessionReturnsStructuredErrorWithoutMutatingStore|LocalRuntimeMessageRouterTests/testChatCancelAcknowledgementPersistsRuntimeOwnedCancelledEvent|LocalRuntimeMessageRouterTests/testConnectionCloseCancelsActiveChatGenerationAndPersistsCancelledEvent|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore|LocalRuntimeMessageRouterTests/testChatMessagesListRejectsUnknownPayloadMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testChatMessagesListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryHandlersReturnEmptyForNonPositiveLimitsWithoutReadingStore|LocalRuntimeMessageRouterTests/testRuntimeChatStoreAppliesArchiveRestoreAndDeleteLifecycle|LocalRuntimeMessageRouterTests/testRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeChatStoreSearchesSessionSummariesAndTranscriptWithinOwnerScope|LocalRuntimeMessageRouterTests/testRuntimeChatStoreTreatsNonPositiveLimitsAsEmptyHistoryWindows|LocalRuntimeMessageRouterTests/testRuntimeChatStoreZeroLimitsReturnEmptyWithoutReadingLog|LocalRuntimeMessageRouterTests/testRuntimeChatStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeChatHistorySemanticallyInvalidEventReturnsStructuredError|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryCorruptStoreReturnsStructuredError|LocalRuntimeMessageRouterTests/testRuntimeChatSessionLifecycleMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testChatSessionLifecycleRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testRuntimeChatSessionRenameStoresRuntimeTitle|LocalRuntimeMessageRouterTests/testChatSessionRenameRejectsUnknownPayloadMetadataBeforeTitleStoreMutation|LocalRuntimeMessageRouterTests/testChatSessionsListQueryFiltersRuntimeOwnedSummaries|LocalRuntimeMessageRouterTests/testChatSessionsListEmbeddingModelHintStaysSearchOnly|LocalRuntimeMessageRouterTests/testChatSessionsListRejectsUnknownPayloadMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testChatSessionsListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testChatSessionsListQueryMatchesReasoningWhileMessagesKeepAnswerSeparate|LocalRuntimeMessageRouterTests/testRuntimeMemoryMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testMemoryListRejectsUnknownPayloadMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemoryUpsertRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemoryDeleteRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemoryListQueryFiltersRuntimeOwnedMemoryWithSearchMetadata|LocalRuntimeMessageRouterTests/testMemoryUpsertRejectsClientSuppliedSourceMetadataAndPreservesRuntimeSource|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreReportsSemanticallyInvalidUpsertLine|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreScopesEntriesByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeMemoryListCorruptStoreReturnsStructuredError|LocalRuntimeMessageRouterTests/testAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory|LocalRuntimeMessageRouterTests/testChatSendInjectsEnabledRuntimeMemoryFromRuntimeStore|LocalRuntimeMessageRouterTests/testChatSendRuntimeMemoryOverridesClientSuppliedMemory|LocalRuntimeMessageRouterTests/testChatSendStoresOnlyClientVisibleMessagesWhileBackendReceivesRuntimeContext|LocalRuntimeMessageRouterTests/testChatSendDoesNotCompactShortConversation|LocalRuntimeMessageRouterTests/testChatSendCompactsOlderTurnsBeforeBackendRequestWhenContextIsLarge|LocalRuntimeMessageRouterTests/testChatSendCompactionAnnotatesBackendOnlySourceSpanWithoutPersisting|LocalRuntimeMessageRouterTests/testChatSendUsesModelContextWindowMetadataForCompactionBudget|LocalRuntimeMessageRouterTests/testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate|LocalRuntimeMessageRouterTests/testChatSendReturnsStructuredErrorWhenRuntimeMemoryCannotLoad|LocalRuntimeMessageRouterTests/testChatSendStreamsReasoningDeltaSeparatelyFromAnswerDelta|LocalRuntimeMessageRouterTests/testChatSendSplitsInlineThinkTagsBeforeStreamingAnswer|LocalRuntimeMessageRouterTests/testChatSendInstalledEmbeddingModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendInstalledCloudModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse|LocalRuntimeMessageRouterTests/testChatSendGeneratedRuntimeTitleStripsInlineThinking|LocalRuntimeMessageRouterTests/testChatSendTitleGenerationUsesDeterministicFallbackWhenBackendTitleIsInvalid'
		run swift test --filter 'LocalRuntimeMessageRouterTests/testMemoryListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemoryListRejectsOversizedQueryBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemoryListQueryFiltersRuntimeOwnedMemoryWithSearchMetadata'
		run swift test --filter LocalRuntimeMessageRouterTests/testMemoryListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch
	run swift test --filter LocalRuntimeMessageRouterTests/testMemoryUpsertRejectsInvalidAllowedPayloadTypesBeforeStoreMutation
	run swift test --filter LocalRuntimeMessageRouterTests/testRejectsBlankEnvelopeRequestIDBeforeRuntimeCommandDispatch
	run swift test --filter LocalRuntimeMessageRouterTests/testRejectsUnsupportedEnvelopeVersionBeforeRuntimeCommandDispatch
	run swift test --filter 'LocalRuntimeMessageRouterTests/testHelloRejectsInvalidAllowedPayloadTypesBeforeChallengeCreation|LocalRuntimeMessageRouterTests/testAuthResponseRejectsBlankAllowedFieldsBeforeAuthentication'
	run swift test --filter LocalRuntimeMessageRouterTests/testChatCancelRejectsBlankTargetRequestIDBeforeBackendDispatch
		run swift test --filter 'LocalRuntimeMessageRouterTests/testChatTitleRequestRejectsBlankSessionIDBeforeBackendDispatch|LocalRuntimeMessageRouterTests/testChatTitleRequestRejectsBlankModelBeforeBackendDispatch'
	run swift test --filter 'LocalRuntimeMessageRouterTests/testChatSessionLifecycleRejectsInvalidAllowedPayloadTypesBeforeStoreMutation|LocalRuntimeMessageRouterTests/testChatSessionRenameRejectsInvalidAllowedPayloadTypesBeforeTitleStoreMutation|LocalRuntimeMessageRouterTests/testMemoryDeleteRejectsInvalidAllowedPayloadTypesBeforeStoreMutation'
	run swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesGUIAllocatedQRCodeWithNearExpiredLease
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesGUIAllocatedQRCodeWithExpiredLease'
run swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshRejectsMalformedRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshAllowsPrivateOverlayAndUsbReverseScopedRelayMaterial|LocalRuntimeMessageRouterTests/testRouteRefreshFailureRedactsRelaySecretsAndProviderEndpoints'
run swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshP2PRendezvousMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshAllowsBoundedP2PEncryptedBodyLargerThanRouteValues|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsMalformedP2PRendezvousMaterialFromRuntimeProvider'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelDoesNotExposeAuthenticatedRouteRefreshByDefault|LocalRuntimeMessageRouterTests/testCompanionAppModelExposesAuthenticatedRouteRefreshWhenDiagnosticOptInIsEnabled'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeHistoryTranscriptPreviewAcrossOwners|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesPreservesChatSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsPreservesMemorySummaryError'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingRequiresRemoteQRCodeRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRemoteRoutePreparationIssueWhenBootstrapAllocationThrows'
run swift test --filter 'LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListReturnsOwnerScopedActiveVisibleDraftsOnly|LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListRejectsUnknownPayloadMetadataBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveWritesIdempotentOwnerScopedMemoryAndHidesApprovedDraft|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRejectsInvalidAllowedPayloadTypesBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRejectsBlankDraftIDBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissHidesOwnerScopedDraftWithoutWritingMemory|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRejectsUnknownPayloadMetadataBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRejectsInvalidAllowedPayloadTypesBeforeStoreMutation|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRejectsBlankDraftIDBeforeStoreMutation'
run swift test --filter 'RelayPeerClientTests/testRelayPeerClientRetireKeepsCurrentConnectionAndSuppressesReconnect|RelayPeerClientTests/testRelayPeerConfigurationDefaultControlLineTimeoutAllowsPhysicalQrStartup|RelayPeerClientTests/testRelayPeerClientTimesOutWhenRegistrationLineNeverArrives|RelayPeerClientTests/testRelayPeerClientTimesOutWhenReadyLineNeverArrivesAfterRegistration'
run swift test --filter SQLiteRuntimeChatEventStoreTests
run swift test --filter 'SQLiteRuntimeChatEventStoreTests/testSQLiteRetentionPrunesDeletedSessionsByOwnerScopeAndCutoff|SQLiteRuntimeChatEventStoreTests/testSQLiteRetentionTombstonePreventsLegacyBackfillResurrection|SQLiteRuntimeChatEventStoreTests/testProductionRuntimeChatRetentionPolicyPrunesOnlyExpiredDeletedSessions'
run swift test --filter RuntimeLongInactivityMemorySummarizationPolicyTests

echo
echo "No-device quality checks passed."
echo "Covered: local emit-only pairing QR artifact generation, QR PNG decode, canonical pairing URI policy, authenticated mock relay E2E, QR candidate structured-error routing, identity-only QR USB reverse fallback, public relay remote-scope QR contract, private-overlay relay scope schema guard, Android private-overlay QR missing-scope diagnostic, link-local relay preflight rejection, relay preflight allocation non-persistence, bootstrap relay endpoint failover before QR generation, saved bootstrap relay endpoint allocation, remote relay lease renewal and QR eligibility, QR relay alias-family completeness, release-mode diagnostic direct-route rejection, invalid QR auto-reconnect state guard, relay-route payload validation, PairingStore complete and expired relay-route persistence, relay preparation host eligibility guard, expired relay lease reconnect guard, fresh relay QR recovery, Android QR route refresh public-key optional binding, macOS remote QR lease route binding, route.refresh runtime-identity binding, route.refresh relay-scope enum validation, route.refresh rejected-payload retry, cross-network QR readiness copy, diagnostic QR text fallback copy, macOS remote QR lease failure visibility, macOS first-launch pairing priority, macOS first-run diagnostics hiding, macOS Pairing QR accessibility state, macOS Pairing QR image accessibility element, macOS Pairing QR unavailable accessibility value, macOS Pairing QR time remaining accessibility value, macOS Pairing QR remote-route expiry accessibility hint, macOS Pairing QR generation action accessibility reason, macOS active Pairing QR renewal accessibility hint, macOS sidebar brand accessibility label, macOS sidebar brand heading trait, macOS page header accessibility labels, macOS page header heading trait, macOS panel header heading trait, macOS empty-state accessibility labels, macOS sidebar preference picker accessibility values, macOS sidebar preference picker accessibility hints, macOS nearby-only connection guidance copy, macOS global QR generation availability gate, macOS app-language date formatting, macOS app-language byte-count formatting, macOS app-language region tag normalization, macOS connection recovery form field accessibility, macOS connection recovery QR action accessibility reason, macOS Connection Recovery result tone accessibility label, macOS trusted-device remove accessibility labels, macOS trusted-device remove accessibility hints, macOS trusted-device row accessibility labels, macOS trusted-device row accessibility visual-summary separation, macOS trusted-device removal confirmation localization, macOS trusted-device confirm-remove action accessibility labels, macOS Activity trusted-device audit copy, macOS Activity model-residency event summaries, macOS Activity row tone accessibility labels, macOS Activity log list accessibility summary, macOS Activity diagnostic disclosure separate focus, macOS Activity route-success ready tone, macOS Activity technical-details accessibility state, macOS saved connection details removal accessibility label, macOS Activity technical-details accessibility labels, macOS provider technical-details accessibility labels, macOS provider technical-details accessibility state, macOS provider status pill accessibility labels, macOS provider row accessibility summaries, macOS runtime overview accessibility labels, macOS status card accessibility labels, macOS model row accessibility labels, macOS model group header accessibility labels, macOS model group header heading trait, macOS relay status row accessibility labels, macOS route diagnostic technical-details accessibility labels, macOS readiness row accessibility labels, macOS natural count/plural copy guard, macOS visible localization anchors with zh-Hans bundle fallback, macOS raw SwiftUI visible-string localization guard, macOS five-language system/light/dark detail render smoke including Connection Recovery, macOS active Pairing QR compact render smoke, macOS compact Quick Actions render smoke, macOS native language picker labels, macOS installed-local model visibility, macOS runtime-local chat routing, macOS corrupt chat-store visibility, macOS runtime-owned memory injection, stale-client-memory replacement, runtime-only context history filtering, and heuristic runtime chat context compaction, Android natural message-count plural resources, Android raw Compose visible-string localization guard, platform-neutral app copy guard, Android native language picker labels, Android first-run language picker before pairing, Android app System/Light/Dark theme path, Android refresh-health action copy, Android localized model-status resources, Android provider-managed model label suppression, Android strict local model metadata guard, Android drawer runtime session status, Android drawer runtime summary accessibility, Android drawer settings footer layout, Android app top-bar shell chrome, Android screen heading semantics, Android QR scanner heading semantics, Android chat top-bar install action cue, Android chat top-bar model search interaction, Android chat top-bar model row accessibility summaries, Android drawer chat options contextual accessibility, Android drawer chat options action labels, Android drawer chat menu contextual action labels, Android drawer chat row accessibility summaries, Android drawer chat search interaction, Android drawer streaming lockout visual-disabled state, Settings chat history search interaction, Android Settings chat-history runtime search metadata compact layout, Android QR scanner permission/settings/torch/cancel chrome, Android QR scanner close action accessibility label, Android QR scanner five-language chrome accessibility, QR scanner torch state accessibility, Android QR-first chat empty state, Android QR pairing live-region accessibility, Android Settings QR scan disabled reason, Android diagnostic QR text state accessibility, Android diagnostic QR text contextual action labels, Android connect action disabled reason, Android platform-neutral connect guidance copy, Android connection status hero accessibility summary, Android model refresh action accessibility state, Android New Chat disabled reason, Android chat empty route guidance full-wrap layout, Android expired remote-route QR recovery action, Android trusted composer readiness lock, Android composer readiness hint, Android composer input readiness accessibility state, Android send button readiness accessibility state, Android composer primary action click labels, Android composer attach action accessibility state, Android composer attachment count limit accessibility, Android attachment-only prompt resource localization, Android attachment picker single-dispatch guard, Android bounded attachment read guard, Android streaming cancel Compose action, Android attachment chip accessibility state, Android attachment remove disabled reason, Android attachment size locale formatting, Android message attachment accessibility state, Android message role accessibility summaries, Android assistant identity marker, Android assistant identity marker compact layout, Android message copy accessibility labels, Android copy success live-region accessibility, Android code block copy accessibility labels, Android multi-code-block copy action labels, Android backend readiness banner accessibility summary, Android generic error banner accessibility summary, Android provider diagnostics expanded state, Android provider diagnostics named accessibility labels, Android provider diagnostics action labels, Android provider row accessibility summaries, Android reasoning accessibility summary, Android jump-to-latest Compose interaction, Android jump-to-latest compact layout, Settings expandable section accessibility state, Settings expandable section duplicate icon semantics guard, Settings preference option accessibility summaries, Settings diagnostic endpoint expander accessibility state, Settings connection switch state accessibility, Settings discovered route contextual action accessibility, Settings discovered route unavailable accessibility summaries, Android discovered trusted-route row compact layout, Android embedding model row accessibility summaries, Settings embedding model streaming lockout accessibility state, Settings memory contextual action accessibility, Settings memory capped action accessibility labels, Settings memory add readiness accessibility state, Settings memory destructive confirmation haptic timing, chat history destructive confirmation haptic timing, confirmation-open lightweight haptic timing, Settings expired-route primary QR action, Android connected Settings redundant-connect guard, Android trusted-runtime forget confirmation, Settings pairing section resync, language alias selection normalization, legacy Python relay allocation-guard, Android no-device Compose screen smoke with five-language pairing copy, Settings diagnostic endpoint visibility guard, chat history bulk action hiding and two-step confirmation, chat history bulk expander accessibility state, chat history bulk action disabled accessibility state, chat history per-chat contextual action accessibility, chat history per-chat disabled accessibility state, chat history row accessibility summaries, Android rename chat readiness accessibility state, Android rename chat action labels, Android rename chat compact dialog layout, full five-language light/dark Chat/Settings/Connection layout matrix, reasoning toggle, chat top-bar model/embedding picker separation, selected model-picker plus Settings preference and embedding-model accessibility state, fake haptic callback dispatch, connection notice haptic callback dispatch, runtime-owned streaming storage redaction, pending relay QR retry, Android pending relay QR secret-store boundary, Android pending relay QR secret cleanup, relay QR completion persistence, real RuntimeRelayTcpClient app pairing path, relay-before-Bonjour fallback, and trusted relay app-init auto-reconnect."
echo "Covered private-overlay QR artifact addendum: shared compact private-overlay relay QR fixture renders to PNG and verifies with production bootstrap, relay route, CGNAT private-overlay scope, and no direct endpoint."
echo "Covered private-overlay QR scope canonicality addendum: QR artifact verification rejects case- or whitespace-mutated relay_scope/rsc values before private-overlay QR evidence is counted."
echo "Covered addendum: Android OS app-language handoff, Android follow system language preference, Android translated Memory noun, macOS menu-bar status and command localization, macOS quick action accessibility hints, macOS menu-bar quick action accessibility parity, macOS menu-bar model-residency controls, macOS menu-bar window and quit accessibility hints, macOS first-run Pairing QR primary action ordering, macOS Connection Recovery private-overlay toggle accessibility labels, macOS Connection Recovery and diagnostics disclosure accessibility state, macOS Connection Recovery Save Connection input state, macOS Connection Recovery Save Bootstrap Relay input state, macOS Connection Recovery bootstrap allocation token warning, macOS Connection Recovery host warning accessibility status, macOS Connection Recovery bootstrap relay removal accessibility labels, macOS Connection Recovery destructive removal action hints, macOS menu-bar Pairing QR active-session title, macOS Pairing QR route notice accessibility status, macOS Connection Recovery fallback-action accessibility hints, macOS CJK page-header accessibility spacing, macOS trusted-device refresh accessibility hint, Android trusted-runtime forget named accessibility label, Android trusted-runtime forget named click label, Android trusted-runtime forget confirmation action labels, Android trusted-runtime forget confirmation named message, Settings discovery action accessibility states, Settings discovery action accessibility labels, Android streaming cancel accessibility state, Android jump-to-latest accessibility state, Android jump-to-latest action labels, Android connected action accessibility states, Android connected action accessibility labels, Android connected action reconnect lockout, Android connected action compact layout, Android backend readiness refresh accessibility state, Android backend readiness refresh action labels, Android backend readiness banner bounded layout, Android generic runtime error banner bounded layout, Android model refresh action accessibility labels, Android route notice action accessibility labels, Android route notice accessibility summaries, Android route notice accessibility state, Android route notice QR recovery steps, Android connection status incomplete relay route live-region recovery, Android primary pairing cross-network route copy, Android pairing primary action accessibility labels, Android trusted-route connect label, Android manual diagnostic host QR-first guard, Android relay auth failure QR recovery notice, Android relay auth failure auto-retry stop, Android relay auth failure post-clear QR action, Android relay auth failure empty-chat copy, Android route rejection empty-chat copy, Android expired route empty-chat copy, Android expired remote-route QR recovery localization, Android expired relay route purge, Android relay secret store boundary, Android relay secret Base64 boundary, macOS relay secret store boundary, Android route.refresh terminal expiry state guard, Android QR runtime-name normalization, Android PairingStore incomplete relay cleanup, Android New Chat pairing-required disabled reason, Android New Chat action labels, Android permanent rail New Chat pairing gate, Android permanent rail Chat pairing gate, Android drawer rich chat search, Android drawer chat date grouping, Android drawer chat model metadata, Android chat history display-model search, Android drawer saved missing model recovery, Android drawer streaming lockout accessibility state, Android chat top-bar model picker streaming disabled state, Android chat top-bar model picker streaming transition lockout, Android chat top-bar stale saved model suppression, Android chat top-bar saved missing model recovery, Android chat top-bar compact long model name, Android chat top-bar model refresh action accessibility state, Android unknown model install guard, Android chat top-bar active chat title, Android chat top-bar model picker closed-button accessibility summary, Android chat top-bar model row action labels, Android search clear action labels, Android composer keyboard Send action, Android composer latest QR readiness hint, Android attachment-only composer readiness state, Android composer readiness live-region accessibility, Android route-recovery empty-state live-region accessibility, Android latest QR empty-state callback routing, Android chat empty-state primary action labels, Android reasoning toggle action labels, Android streaming assistant live-region accessibility, Settings expandable section action accessibility labels, Settings switch action accessibility labels, Settings memory action accessibility labels, Settings memory streaming lockout accessibility state, Settings memory add action accessibility labels, Settings memory add success live-region accessibility, Settings memory empty-state live-region accessibility, Settings memory delete confirmation action labels, Settings chat history model metadata, Android memory input readiness accessibility state, chat history bulk expander action labels, chat history bulk action accessibility labels, chat history destructive confirmation and cancel action labels."
echo "Covered Settings compact addendum: Android Settings trusted-runtime panel compact layout, Android trusted-runtime forget compact dialog layout, Android chat-history confirmation compact dialog layout, and Android memory delete compact dialog layout."
echo "Covered QR lease addendum: near-expiry remote relay lease QR renewal."
echo "Covered macOS stale GUI relay QR renewal addendum: ready stale or expired GUI-allocated relay leases are replaced with fresh relay id, secret, expiry, and nonce before QR generation."
echo "Covered remote QR lease monotonicity addendum: macOS runtime host accepts same-relay bootstrap lease renewal only when expiry advances and nonce changes."
echo "Covered relay probe addendum: non-consuming relay readiness probe and Android route-level relay preflight."
echo "Covered Android relay reachability probe input guard addendum: physical relay probe rejects URL-shaped hosts, invalid ports, and malformed relay IDs before ADB access."
echo "Covered Android relay reachability probe route-material redaction addendum: physical relay probe JSON, stdout, and stderr omit raw relay IDs while preserving seeded redaction-test route-ready evidence."
echo "Covered Android relay reachability probe self-test proof-boundary addendum: fake-ADB relay probe artifacts mark fake_adb_redaction_self_test, keep observed adb serial absent, and keep live Android relay/route proof false."
echo "Covered relay probe/physical wrapper production proof-boundary addendum: Android relay probe and physical external-relay wrapper summaries keep production relay, production session-key exchange, and production end-to-end transport encryption proof false."
echo "Covered Android pairing deeplink am-start route-material redaction addendum: physical deeplink smoke stores and prints sanitized am start output without raw pairing or relay route material."
echo "Covered Android pairing deeplink am-start sanitizer self-test proof-boundary addendum: hidden no-device sanitizer self-test output carries an in-band not-phone-pairing-proof marker."
echo "Covered Android pairing failure artifact redaction addendum: physical deeplink smoke sanitizes failed activity/logcat artifacts and filtered stderr tails while preserving structured failure diagnostics."
echo "Covered relay bind addendum: tokenless AetherLinkRelay binds are loopback-only and wildcard/non-loopback binds require an allocation token."
echo "Covered relay allocation-token addendum: token-required AetherLinkRelay allocation rejects missing or wrong tokens, keeps unauthorized and preflight routes out of the allocation store, and persists only authorized lease metadata."
echo "Covered relay allocation request unexpected metadata rejection addendum: AETHERLINK_RELAY allocate rejects unknown key=value request metadata before treating it as relay secret material."
echo "Covered relay opaque-id addendum: AetherLinkRelay allocation returns opaque stable relay IDs instead of raw route tokens, and keeps raw route tokens out of allocation stores and relay logs."
echo "Covered relay allocation opacity addendum: allocation responses, persisted stores, and relay logs use opaque stable relay IDs without exposing raw route tokens."
echo "Covered Android private-overlay QR missing-scope diagnostic addendum: private, CGNAT, and ULA relay hosts without relay_scope=private_overlay map to latest-QR route recovery instead of generic invalid QR."
echo "Covered relay preflight opaque-id echo rejection addendum: relay_allocation_preflight rejects allocation responses that echo the requested route token as relay_id."
echo "Covered relay preflight output redaction addendum: relay_allocation_preflight success JSON omits requested route tokens, relay secrets, raw relay IDs, raw relay expiries, and raw relay nonces while keeping safe presence booleans."
echo "Covered relay allocation renewal addendum: AetherLinkRelay allocation registry ignores non-advancing renewals for stable relay IDs and accepts only advancing renewals with fresh nonces."
echo "Covered relay allocation store-load addendum: AetherLinkRelay allocation registry deduplicates persisted relay tickets and skips malformed ticket entries on load."
echo "Covered relay allocation lease lifecycle addendum: AetherLinkRelay uses a short default allocation TTL, persists relay leases without secrets, removes expired relay IDs, and prunes expired persisted tickets on load."
echo "Covered relay wrapper dry-run allocation-token redaction addendum: run_allocation_relay --dry-run reports token-required mode without printing raw allocation-token values or argv-form token flags."
echo "Covered relay wrapper dry-run summary proof-boundary addendum: run_allocation_relay --dry-run --summary-json records no relay process, production relay, trusted-device, or optical QR proof while keeping allocation tokens redacted."
echo "Covered relay wrapper allocation-token argv redaction addendum: run_allocation_relay, run_different_network_dev_runtime, and no_adb_external_relay_pairing_smoke pass allocation tokens through environment variables so child process argv omits --allocation-token and the raw token while token-required allocation still works."
echo "Covered Android pairing deeplink allocation-token argv redaction addendum: android_pairing_deeplink_smoke and the physical external-relay wrapper pass allocation tokens through environment variables so relay/preflight child argv omits --allocation-token and the raw token."
echo "Covered no-ADB proof-boundary summary addendum: no_adb_external_relay_pairing_smoke separates runtime-host relay registration from trusted-device relay reachability, pairing, runtime.health, reconnect, and optical QR scan proof."
echo "Covered no-ADB external-relay URL host input redaction addendum: no_adb_external_relay_pairing_smoke rejects URL-shaped relay-host input without echoing provider/backend/route-token/relay-secret material."
echo "Covered no-ADB external-network proof-boundary addendum: no_adb_external_relay_pairing_smoke keeps operator-confirmed external-network relay proof, full-run trusted-device proof, and production relay proof false for emit-only and unverified QR summaries."
echo "Covered Swift relay allocation unexpected metadata rejection addendum: RelayAllocation.parseResponseLine rejects allocation responses with extra backend, provider, route-token, allocation-token, or relay-secret metadata fields."
echo "Covered relay allocation store unexpected metadata rejection addendum: RelayAllocationRegistry skips persisted tickets that contain backend, provider, route-token, allocation-token, or relay-secret metadata fields."
echo "Covered relay preflight failure-output redaction addendum: relay_allocation_preflight redacts malformed allocation response bodies from stderr while preserving a safe failure reason."
echo "Covered different-network relay endpoint input redaction addendum: run_different_network_dev_runtime rejects URL-shaped relay endpoints and malformed endpoint-list values without echoing provider, backend, route-token, or relay-secret material in stderr or summary JSON."
echo "Covered relay preflight unexpected-field rejection addendum: relay_allocation_preflight rejects allocation responses with extra metadata fields without echoing those fields or values."
echo "Covered relay preflight response value canonicality addendum: relay_allocation_preflight rejects whitespace-mutated relay_id, relay_secret, relay_nonce, URL-shaped relay_id, and invalid relay_expires_at values without echoing response values."
echo "Covered relay preflight expiry type strictness addendum: relay_allocation_preflight rejects numeric-string and boolean relay_expires_at values without coercion or response-value echoing."
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
echo "Covered P2P trusted-runtime restore addendum: Android trusted P2P rendezvous material persists after accepted pairing and restores as a prepared remote route without direct endpoint fallback."
echo "Covered remote route mismatch addendum: Android remote route identity mismatch QR recovery."
echo "Covered P2P failure recovery addendum: Android failed P2P route without saved relay fallback scans a fresh QR with relay or private overlay details."
echo "Covered long-inactivity memory summary draft protocol listing addendum: authenticated memory.summary.drafts.list returns owner-scoped active visible-transcript drafts without writing runtime memory."
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
echo "Covered RuntimeDevServer history/title/session lifecycle/memory smoke addendum: authenticated relay smoke positively validates chat.sessions.list, chat.messages.list, chat.title.request, chat.session rename/archive/restore/delete, archived chat.send restore-required rejection, chat.send context compaction backend-only audit, visible history separation, memory.upsert, memory.list, memory.delete, memory.summary.drafts.list, memory.summary.draft.approve, memory.summary.draft.dismiss, approved memory-summary memory.list visibility, memory-summary stale expected-metadata rejection, client-supplied memory source rejection, approved memory source-preserving edit/list visibility, dismissed draft hiding, dismissed draft no memory.list entry, and memory.summary draft unavailable errors over RuntimeDevServer."
echo "Covered RuntimeDevServer chat compaction backend-only audit addendum: authenticated relay smoke validates chat.send context compaction backend-only audit and visible history separation over RuntimeDevServer."
echo "Covered runtime session search addendum: chat.sessions.list query filters runtime-owned titles, model ids, and sanitized transcript text inside owner/archive/delete boundaries, with deterministic ranking, bounded snippets, Android query/search DTO serialization, selected embedding-model search hint plumbing, trimmed request plumbing, Settings chat-history search refresh query forwarding, Settings chat-history runtime search match metadata, RuntimeDevServer chat.sessions.list query search metadata smoke, and SQLite/FTS event-store parity plus JSONL-to-SQLite backfill, SQLite default-store rollout, and SQLite deleted-session retention pruning for sessions, messages, owner/archive/delete lifecycle, inline-byte redaction, corrupt-log handling, idempotency, legacy-file freshness, tombstone-backed legacy resurrection prevention, and search metadata."
echo "Covered SQLite runtime chat retention policy addendum: production runtime chat maintenance prunes only cutoff-eligible deleted sessions, preserves active/archived sessions, keeps owner scope, and preserves tombstone-backed legacy resurrection prevention."
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
echo "Covered runtime memory list search addendum: memory.list query filters owner-scoped runtime memory content and bounded runtime-derived source metadata with deterministic rank/snippet/matched_fields while memory.upsert rejects client-supplied source metadata."
echo "Covered RuntimeDevServer memory.list query search metadata smoke addendum: authenticated relay smoke validates memory.list query ranking, snippet, and matched_fields metadata over RuntimeDevServer."
echo "Covered RuntimeDevServer future memory.search rejection addendum: authenticated RuntimeDevServer relay smoke rejects memory.search with unknown_message_type before any advanced semantic memory search path exists."
echo "Covered Android Settings memory runtime search addendum: Settings Memory local filtering forwards trimmed runtime memory query refresh, renders rank/snippet/matched_fields metadata, and keeps runtime search snippets out of device storage."
echo "Covered runtime reasoning search metadata addendum: chat.sessions.list can match stored assistant reasoning separately from visible answer text across JSONL router and SQLite/FTS paths, and Android Settings labels reasoning matched fields."
echo "Covered context-window compaction addendum: models.result carries optional context_window_tokens, Android preserves the metadata, Ollama/LM Studio parse context-window hints, and macOS chat.send uses resolved model context windows to choose runtime compaction budget plus backend-only source-span metadata."
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
echo "Physical macOS Dock capture option: script/capture_macos_dock_icon.sh stages dist/AetherLink.app and captures build/qa/aetherlink-macos-dock-visible.png with CFBundleIconFile=AppIcon."
echo "Covered DocumentIngestion resource policy addendum: runtime-side document extraction rejects oversized archive entry output and oversized normalized extracted text before backend dispatch."
echo "Covered protocol reserved namespace guard addendum: projects. and automation. active messages remain blocked by protocol schema hygiene."
echo "Covered protocol generic tool namespace guard addendum: tool.* active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke until runtime tool permissions, execution, result handling, and audit semantics are designed."
echo "Covered protocol reserved tools/search/python namespace guard addendum: skills., mcp., web_search., and python. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered protocol reserved permission/approval/audit namespace guard addendum: permission., approval., and audit. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered protocol reserved runtime action namespace guard addendum: file., terminal., network., and backend. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke until runtime file, terminal, network, and backend action permissions are designed."
echo "Covered protocol reserved RAG/research namespace guard addendum: embeddings., retrieval., index., research., citation., and source_control. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke until runtime retrieval, indexing, research, citation, trusted-source, source-control, permission, and audit semantics are designed."
echo "Covered protocol reserved private-overlay namespace guard addendum: p2p., rendezvous., bootstrap., dht., nat., stun., and turn. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered protocol reserved encrypted-session namespace guard addendum: session., key_exchange., encrypted_session., and anti_replay. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered protocol reserved transport/crypto namespace guard addendum: transport. and crypto. active messages remain blocked by protocol schema hygiene and RuntimeDevServer relay smoke."
echo "Covered RuntimeDevServer future Python namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects python.run and python.exec with unknown_message_type before any runtime Python tool execution path exists."
echo "Covered RuntimeDevServer generic tool namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects tool.call, tool.result, and tool.run with unknown_message_type before any runtime generic-tool execution or result path exists."
echo "Covered RuntimeDevServer reserved projects/automation namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects projects.sessions.list and automation.runs.create with unknown_message_type before any workspace or scheduler feature path exists."
echo "Covered RuntimeDevServer reserved permission/approval/audit namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects permission.request, approval.prompt, and audit.events.list with unknown_message_type before any production permission broker, mobile approval, or audit-log control path exists."
echo "Covered RuntimeDevServer reserved runtime action namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects file.read, file.write, file.index, terminal.exec, terminal.kill, network.request, network.open, backend.call, and backend.configure with unknown_message_type before any production file, terminal, network, or backend action path exists."
echo "Covered RuntimeDevServer reserved RAG/research namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects embeddings.create, retrieval.query, index.build, research.brief.create, citation.sources.list, and source_control.status with unknown_message_type before any production embedding, retrieval, indexing, research, citation, source-control, or trusted-source path exists."
echo "Covered RuntimeDevServer reserved private-overlay namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects p2p.session.open, rendezvous.records.publish, bootstrap.records.lookup, dht.records.put, nat.candidates.gather, stun.binding.request, and turn.relay.allocate with unknown_message_type before any production P2P, rendezvous, bootstrap, DHT, NAT traversal, STUN, or TURN path exists."
echo "Covered RuntimeDevServer reserved encrypted-session namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects session.key.exchange, key_exchange.begin, encrypted_session.open, and anti_replay.window.commit with unknown_message_type before any production session-key exchange, encrypted-session, or replay-window control path exists."
echo "Covered RuntimeDevServer reserved transport/crypto namespace rejection addendum: authenticated RuntimeDevServer relay smoke rejects transport.handshake, transport.rekey, crypto.session.open, and crypto.key.rotate with unknown_message_type before any production transport handshake, rekey, crypto-session, or key-rotation control path exists."
echo "Covered RuntimeDevServer response-only message direction rejection addendum: authenticated RuntimeDevServer relay smoke rejects auth.challenge, pairing.result, models.result, chat.delta, chat.done, chat.title.result, and error with unexpected_message_direction before any client-supplied response frame can mutate runtime state."
echo "Covered protocol route namespace guard addendum: route.refresh remains the only active route.* message while future route diagnostics, candidate exchange, allocation-status, and failure-report messages stay reserved."
echo "Covered RuntimeDevServer future route namespace rejection addendum: authenticated RuntimeDevServer relay smoke accepts route.refresh but rejects route.candidates.exchange, route.diagnostics.report, route.allocation.status, and route.failure.report with unknown_message_type before any future route exchange, diagnostics, allocation-status, or failure-report path exists."
echo "Covered macOS protocol model metadata parity addendum: BridgeProtocol ModelInfo preserves provider, provider_model_id, qualified_id, model_kind, capabilities, and context_window_tokens for embedding model registration."
echo "Covered Android protocol model metadata parity addendum: Android ModelInfoPayload preserves backend, provider, provider_model_id, qualified_id, model_kind, kind, capabilities, size_bytes, context_window_tokens, modified_at, and remote_model for embedding model registration, and legacy missing capabilities decode as empty."
echo "Physical external-relay QA gate: script/check_physical_external_relay_pairing.sh --relay-host <public-or-vpn-host> writes build/qa/android-external-relay-pairing.json and must be run with a real attached phone on the target network."
echo "Not covered by this no-device gate: physical install, camera QR scan, real device haptics, physical TalkBack/VoiceOver traversal, Android system/per-app locale mutation on hardware, launcher/Dock screenshots, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity."
