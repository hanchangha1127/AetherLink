#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${AETHERLINK_RELAY_BIND_HOST:-127.0.0.1}"
PORT="${AETHERLINK_RELAY_PORT:-43171}"
ALLOCATION_STORE="${AETHERLINK_RELAY_ALLOCATION_STORE:-}"
ALLOCATION_TOKEN="${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}"
ALLOCATION_TTL_SECONDS="${AETHERLINK_RELAY_ALLOCATION_TTL_SECONDS:-}"
REQUIRE_ALLOCATION=1
DRY_RUN=0
EPHEMERAL_ALLOCATIONS=0
SUMMARY_JSON=""

usage() {
  cat <<'USAGE'
Usage:
  script/run_allocation_relay.sh [--host <bind-host>] [--port <port>] [--allocation-token <token>] [--allocation-ttl-seconds <seconds>] [--allocation-store <path>] [--ephemeral-allocations] [--allow-legacy] [--dry-run] [--summary-json <path>]

Starts the AetherLink development relay. By default it requires route allocation,
which is the path used by QR pairing across different networks.
Allocation tickets are persisted by AetherLinkRelay by default so issued QR
relay ids can survive relay process restarts. Relay allocation leases are
short-lived by default; use --allocation-ttl-seconds only for explicit
development diagnostics that need a longer route lease.

This relay forwards encrypted AetherLink runtime frames only. It is not an AI
backend and does not expose Ollama, LM Studio, prompts, chat history, or files.
Tokenless relay binds are allowed only on loopback hosts such as 127.0.0.1,
::1, or localhost. Use --host 0.0.0.0 plus --allocation-token, or
AETHERLINK_RELAY_ALLOCATION_TOKEN, when the relay must be reachable outside the
runtime host. Runtime bootstrap scripts can send the same value with
AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN.

For a no-USB different-network smoke, run this on a host/port reachable by both
the runtime machine and the Android device, then run:

  script/no_adb_external_relay_pairing_smoke.sh --relay-host <public-or-vpn-host> --relay-port <port>

To check relay/bootstrap readiness before starting RuntimeDevServer, run:

  script/run_different_network_dev_runtime.sh --relay-host <public-or-vpn-host> --relay-port <port> --preflight-only

For a USB-assisted app/deeplink regression check that still avoids adb reverse
for the relay, run:

  script/android_pairing_deeplink_smoke.sh --relay --external-relay-host <public-or-vpn-host> --external-relay-port <port>

USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      if [[ $# -lt 2 ]]; then
        echo "--host requires a value." >&2
        exit 2
      fi
      HOST="$2"
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        echo "--port requires a value." >&2
        exit 2
      fi
      PORT="$2"
      shift 2
      ;;
    --allow-legacy)
      REQUIRE_ALLOCATION=0
      shift
      ;;
    --allocation-store)
      if [[ $# -lt 2 ]]; then
        echo "--allocation-store requires a value." >&2
        exit 2
      fi
      ALLOCATION_STORE="$2"
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
    --allocation-ttl-seconds)
      if [[ $# -lt 2 ]]; then
        echo "--allocation-ttl-seconds requires a value." >&2
        exit 2
      fi
      ALLOCATION_TTL_SECONDS="$2"
      shift 2
      ;;
    --ephemeral-allocations)
      EPHEMERAL_ALLOCATIONS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --summary-json)
      if [[ $# -lt 2 ]]; then
        echo "--summary-json requires a value." >&2
        exit 2
      fi
      SUMMARY_JSON="$2"
      shift 2
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

bind_requires_token() {
  python3 - "$1" <<'PY'
import ipaddress
import sys

raw = sys.argv[1].strip()
host = raw.lower()
if host.startswith("[") and host.endswith("]"):
    host = host[1:-1]
if host in {"localhost", "localhost.", "::1"}:
    print("0")
    raise SystemExit(0)
try:
    address = ipaddress.ip_address(host)
except ValueError:
    print("1")
    raise SystemExit(0)
print("0" if address.is_loopback else "1")
PY
}

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Invalid relay port: $PORT" >&2
  exit 2
fi

if [[ -n "$ALLOCATION_TTL_SECONDS" ]] && (
  ! [[ "$ALLOCATION_TTL_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]] ||
    ! python3 -c 'import sys; raise SystemExit(0 if float(sys.argv[1]) > 0 else 1)' "$ALLOCATION_TTL_SECONDS"
); then
  echo "Invalid allocation TTL seconds: $ALLOCATION_TTL_SECONDS" >&2
  exit 2
fi

if [[ -z "$ALLOCATION_TOKEN" && "$(bind_requires_token "$HOST")" == "1" ]]; then
  echo "Allocation token required for non-loopback relay bind $HOST. Use --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN, or bind tokenless diagnostics to 127.0.0.1, ::1, or localhost." >&2
  exit 2
fi

cd "$ROOT_DIR"

if [[ -n "$SUMMARY_JSON" && "$SUMMARY_JSON" != /* ]]; then
  SUMMARY_JSON="$ROOT_DIR/$SUMMARY_JSON"
fi

write_dry_run_summary() {
  local exit_status="$1"
  if [[ -z "$SUMMARY_JSON" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$SUMMARY_JSON")"
  python3 - "$SUMMARY_JSON" "$exit_status" "$HOST" "$PORT" "$REQUIRE_ALLOCATION" "$EPHEMERAL_ALLOCATIONS" "$ALLOCATION_STORE" "$ALLOCATION_TOKEN" "$ALLOCATION_TTL_SECONDS" <<'PY'
import json
import sys

(
    summary_path,
    exit_status,
    host,
    port,
    require_allocation,
    ephemeral_allocations,
    allocation_store,
    allocation_token,
    allocation_ttl_seconds,
) = sys.argv[1:10]

allocation_required = require_allocation == "1"
summary = {
    "exit_status": int(exit_status),
    "mode": {
        "dry_run": True,
        "allow_legacy": not allocation_required,
    },
    "relay": {
        "bind_host": host,
        "bind_port": int(port),
        "development_relay_started": False,
    },
    "allocation": {
        "required": allocation_required,
        "token_present": bool(allocation_token),
        "token_redacted": bool(allocation_token),
        "store_mode": (
            "ephemeral"
            if ephemeral_allocations == "1"
            else ("custom" if allocation_store else "default")
        ),
        "ttl_seconds_present": bool(allocation_ttl_seconds),
    },
    "coverage": {
        "relay_wrapper_dry_run_summary": True,
        "development_relay_started": False,
        "production_relay": False,
        "trusted_device_relay_reachability": False,
        "trusted_device_pairing": False,
        "optical_qr_scan": False,
    },
    "caveats": [
        "dry_run_not_relay_process_proof",
        "not_production_relay_proof",
        "not_trusted_device_reachability_proof",
    ],
}
with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

if [[ "$DRY_RUN" == "1" ]]; then
  write_dry_run_summary 0
  echo "AetherLink relay dry run"
  echo "Bind address: $HOST:$PORT"
  if [[ "$REQUIRE_ALLOCATION" == "1" ]]; then
    echo "Allocation required: yes"
  else
    echo "Allocation required: no (--allow-legacy)"
    echo "WARNING: legacy mode can mask QR-only relay/bootstrap allocation failures."
  fi
  if [[ "$EPHEMERAL_ALLOCATIONS" == "1" ]]; then
    echo "Allocation store: disabled (--ephemeral-allocations)"
  elif [[ -n "$ALLOCATION_STORE" ]]; then
    echo "Allocation store: $ALLOCATION_STORE"
  else
    echo "Allocation store: AetherLinkRelay default (~/.aetherlink-relay/allocations.json)"
  fi
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    echo "Allocation token: required"
  else
    echo "Allocation token: not required for loopback bind"
  fi
  if [[ -n "$ALLOCATION_TTL_SECONDS" ]]; then
    echo "Allocation TTL: ${ALLOCATION_TTL_SECONDS}s"
  else
    echo "Allocation TTL: AetherLinkRelay default"
  fi
  echo "After the relay is running, verify the advertised host with:"
  echo "  script/run_different_network_dev_runtime.sh --relay-host <public-or-vpn-host> --relay-port $PORT --preflight-only"
  echo "Do not use the bind address as the QR relay host unless the trusted device can actually reach it."
  exit 0
fi

swift build --product AetherLinkRelay >/dev/null
RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
ARGS=("$RELAY_BIN" --host "$HOST" --port "$PORT")
if [[ "$REQUIRE_ALLOCATION" == "1" ]]; then
  ARGS+=(--require-allocation)
else
  ARGS+=(--allow-legacy)
fi
if [[ "$EPHEMERAL_ALLOCATIONS" == "1" ]]; then
  ARGS+=(--ephemeral-allocations)
elif [[ -n "$ALLOCATION_STORE" ]]; then
  ARGS+=(--allocation-store "$ALLOCATION_STORE")
fi
if [[ -n "$ALLOCATION_TTL_SECONDS" ]]; then
  ARGS+=(--allocation-ttl-seconds "$ALLOCATION_TTL_SECONDS")
fi

echo "Starting AetherLink development relay on $HOST:$PORT"
if [[ "$REQUIRE_ALLOCATION" == "1" ]]; then
  echo "Allocation is required. Unknown relay ids will be rejected."
else
  echo "Legacy mode enabled. Unknown relay ids are allowed for compatibility."
fi
if [[ "$EPHEMERAL_ALLOCATIONS" == "1" ]]; then
  echo "Allocation tickets are not persisted."
elif [[ -n "$ALLOCATION_STORE" ]]; then
  echo "Allocation tickets persist at: $ALLOCATION_STORE"
else
  echo "Allocation tickets persist at the AetherLinkRelay default store."
fi
if [[ -n "$ALLOCATION_TOKEN" ]]; then
  echo "Allocation token is required for route allocation."
else
  echo "Allocation token is not required because the relay is bound to a loopback host."
fi
if [[ -n "$ALLOCATION_TTL_SECONDS" ]]; then
  echo "Allocation leases expire after ${ALLOCATION_TTL_SECONDS}s."
else
  echo "Allocation leases use the AetherLinkRelay short default TTL."
fi
echo "Use a public, VPN, tunnel, or overlay address that both paired devices can reach."
echo "Preflight that advertised address with: script/run_different_network_dev_runtime.sh --relay-host <public-or-vpn-host> --relay-port $PORT --preflight-only"

if [[ -n "$ALLOCATION_TOKEN" ]]; then
  export AETHERLINK_RELAY_ALLOCATION_TOKEN="$ALLOCATION_TOKEN"
fi
exec "${ARGS[@]}"
