#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${AETHERLINK_RELAY_BIND_HOST:-127.0.0.1}"
PORT="${AETHERLINK_RELAY_PORT:-43171}"
ALLOCATION_STORE="${AETHERLINK_RELAY_ALLOCATION_STORE:-}"
ALLOCATION_TOKEN="${AETHERLINK_RELAY_ALLOCATION_TOKEN:-}"
ALLOCATION_TTL_SECONDS="${AETHERLINK_RELAY_ALLOCATION_TTL_SECONDS:-}"
PROBE_POLICY="${AETHERLINK_RELAY_PROBE_POLICY:-loopback-only}"
CONTROL_TIMEOUT_SECONDS="${AETHERLINK_RELAY_CONTROL_TIMEOUT_SECONDS:-10}"
MAX_CONNECTIONS="${AETHERLINK_RELAY_MAX_CONNECTIONS:-256}"
MAX_CONNECTIONS_PER_SOURCE="${AETHERLINK_RELAY_MAX_CONNECTIONS_PER_SOURCE:-64}"
MAX_WAITING_PEERS_PER_SOURCE="${AETHERLINK_RELAY_MAX_WAITING_PEERS_PER_SOURCE:-32}"
WAITING_TIMEOUT_SECONDS="${AETHERLINK_RELAY_WAITING_TIMEOUT_SECONDS:-60}"
MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY="${AETHERLINK_RELAY_MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY:-4}"
PREFLIGHT_RATE_PER_MINUTE="${AETHERLINK_RELAY_PREFLIGHT_RATE_PER_MINUTE:-120}"
PREFLIGHT_BURST="${AETHERLINK_RELAY_PREFLIGHT_BURST:-30}"
ALLOCATION_RATE_PER_MINUTE="${AETHERLINK_RELAY_ALLOCATION_RATE_PER_MINUTE:-30}"
ALLOCATION_BURST="${AETHERLINK_RELAY_ALLOCATION_BURST:-10}"
MAX_RATE_LIMIT_SOURCES="${AETHERLINK_RELAY_MAX_RATE_LIMIT_SOURCES:-4096}"
REQUIRE_ALLOCATION=1
DRY_RUN=0
EPHEMERAL_ALLOCATIONS=0
SUMMARY_JSON=""

usage() {
  cat <<'USAGE'
Usage:
  script/run_allocation_relay.sh [--host <bind-host>] [--port <port>] [--allocation-token <token>] [--allocation-ttl-seconds <seconds>] [--allocation-store <path>] [--ephemeral-allocations] [--allow-legacy] [--probe-policy <disabled|loopback-only|legacy-unauthenticated>] [--control-timeout-seconds <seconds>] [--waiting-timeout-seconds <seconds>] [--max-connections <count>] [--max-connections-per-source <count>] [--max-waiting-peers-per-source <count>] [--max-waiting-peers-per-authenticated-identity <count>] [--preflight-rate-per-minute <count>] [--preflight-burst <count>] [--allocation-rate-per-minute <count>] [--allocation-burst <count>] [--max-rate-limit-sources <count>] [--dry-run] [--summary-json <path>]

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
Probe is loopback-only by default. Use --probe-policy legacy-unauthenticated
only for temporary physical diagnostics that explicitly accept route-state
enumeration. Accepted sockets, including waiting and active peers, remain bounded
by --max-connections, and every control record has one absolute read deadline.
Source quotas use each accepted socket's canonical IPv4/IPv6 address. Waiting
peers count against both source quotas; active bridges remain counted against
the source connection quota, but frame forwarding is not throttled. Shared
NAT/VPN users share quotas. Defaults are development-relay guardrails, not
production capacity policy. Source quota values must be canonical positive
decimals in 1...65536 with no disable value. They need not be at most the global
maximum, but twice the waiting-peer quota must not exceed the per-source
connection quota so shared cohorts retain counterpart headroom. Effective
capacity is bounded by all applicable limits.
Unmatched peers close after a bounded waiting duration. Runtime keys and paired
client keys that have completed relay admission share a separate identity-level
waiting quota across sources; unauthenticated bootstrap clients remain covered
by source quotas only. These controls have no disable value.
Source rate limits apply only to allocation, preflight, and paired-renewal
control records. They do not throttle peer admission or encrypted forwarding.
Shared NAT/VPN users share one source bucket. Defaults are development-relay
guardrails, not production capacity policy. Rate and burst values must be
1...1000000; tracked sources must be 1...65536. Each burst must fully refill
within the fixed 900-second idle retention so cleanup cannot reset capacity.
There is no disable value.

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
    --probe-policy)
      if [[ $# -lt 2 ]]; then
        echo "--probe-policy requires a value." >&2
        exit 2
      fi
      PROBE_POLICY="$2"
      shift 2
      ;;
    --control-timeout-seconds)
      if [[ $# -lt 2 ]]; then
        echo "--control-timeout-seconds requires a value." >&2
        exit 2
      fi
      CONTROL_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --max-connections)
      if [[ $# -lt 2 ]]; then
        echo "--max-connections requires a value." >&2
        exit 2
      fi
      MAX_CONNECTIONS="$2"
      shift 2
      ;;
    --max-connections-per-source)
      if [[ $# -lt 2 ]]; then
        echo "--max-connections-per-source requires a value." >&2
        exit 2
      fi
      MAX_CONNECTIONS_PER_SOURCE="$2"
      shift 2
      ;;
    --max-waiting-peers-per-source)
      if [[ $# -lt 2 ]]; then
        echo "--max-waiting-peers-per-source requires a value." >&2
        exit 2
      fi
      MAX_WAITING_PEERS_PER_SOURCE="$2"
      shift 2
      ;;
    --waiting-timeout-seconds)
      if [[ $# -lt 2 ]]; then
        echo "--waiting-timeout-seconds requires a value." >&2
        exit 2
      fi
      WAITING_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --max-waiting-peers-per-authenticated-identity)
      if [[ $# -lt 2 ]]; then
        echo "--max-waiting-peers-per-authenticated-identity requires a value." >&2
        exit 2
      fi
      MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY="$2"
      shift 2
      ;;
    --preflight-rate-per-minute)
      if [[ $# -lt 2 ]]; then
        echo "--preflight-rate-per-minute requires a value." >&2
        exit 2
      fi
      PREFLIGHT_RATE_PER_MINUTE="$2"
      shift 2
      ;;
    --preflight-burst)
      if [[ $# -lt 2 ]]; then
        echo "--preflight-burst requires a value." >&2
        exit 2
      fi
      PREFLIGHT_BURST="$2"
      shift 2
      ;;
    --allocation-rate-per-minute)
      if [[ $# -lt 2 ]]; then
        echo "--allocation-rate-per-minute requires a value." >&2
        exit 2
      fi
      ALLOCATION_RATE_PER_MINUTE="$2"
      shift 2
      ;;
    --allocation-burst)
      if [[ $# -lt 2 ]]; then
        echo "--allocation-burst requires a value." >&2
        exit 2
      fi
      ALLOCATION_BURST="$2"
      shift 2
      ;;
    --max-rate-limit-sources)
      if [[ $# -lt 2 ]]; then
        echo "--max-rate-limit-sources requires a value." >&2
        exit 2
      fi
      MAX_RATE_LIMIT_SOURCES="$2"
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

if [[ "$PROBE_POLICY" != "disabled" && "$PROBE_POLICY" != "loopback-only" && "$PROBE_POLICY" != "legacy-unauthenticated" ]]; then
  echo "Invalid probe policy: $PROBE_POLICY" >&2
  exit 2
fi

if ! [[ "$CONTROL_TIMEOUT_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]] ||
  ! python3 -c 'import sys; value=float(sys.argv[1]); raise SystemExit(0 if 0 < value <= 300 else 1)' "$CONTROL_TIMEOUT_SECONDS"; then
  echo "Invalid control timeout seconds: $CONTROL_TIMEOUT_SECONDS" >&2
  exit 2
fi

validate_rate_limit_value() {
  local name="$1"
  local value="$2"
  local maximum="$3"
  if ! [[ "$value" =~ ^[1-9][0-9]{0,6}$ ]] || (( value > maximum )); then
    echo "Invalid $name: $value (expected 1...$maximum)" >&2
    exit 2
  fi
}

validate_rate_limit_value "maximum connections" "$MAX_CONNECTIONS" 65536
validate_rate_limit_value "maximum connections per source" "$MAX_CONNECTIONS_PER_SOURCE" 65536
validate_rate_limit_value "maximum waiting peers per source" "$MAX_WAITING_PEERS_PER_SOURCE" 65536
validate_rate_limit_value "waiting timeout seconds" "$WAITING_TIMEOUT_SECONDS" 3600
validate_rate_limit_value "maximum waiting peers per authenticated identity" "$MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY" 65536
if (( MAX_WAITING_PEERS_PER_SOURCE * 2 > MAX_CONNECTIONS_PER_SOURCE )); then
  echo "Invalid source peer quotas: twice maximum waiting peers per source must not exceed maximum connections per source." >&2
  exit 2
fi
validate_rate_limit_value "preflight rate per minute" "$PREFLIGHT_RATE_PER_MINUTE" 1000000
validate_rate_limit_value "preflight burst" "$PREFLIGHT_BURST" 1000000
validate_rate_limit_value "allocation rate per minute" "$ALLOCATION_RATE_PER_MINUTE" 1000000
validate_rate_limit_value "allocation burst" "$ALLOCATION_BURST" 1000000
validate_rate_limit_value "maximum rate-limit sources" "$MAX_RATE_LIMIT_SOURCES" 65536

validate_rate_limit_refill_window() {
  local name="$1"
  local rate_per_minute="$2"
  local burst="$3"
  if (( burst * 60 > rate_per_minute * 900 )); then
    echo "Invalid $name rate/burst combination: burst must fully refill within 900 seconds." >&2
    exit 2
  fi
}

validate_rate_limit_refill_window "preflight" "$PREFLIGHT_RATE_PER_MINUTE" "$PREFLIGHT_BURST"
validate_rate_limit_refill_window "allocation" "$ALLOCATION_RATE_PER_MINUTE" "$ALLOCATION_BURST"

if [[ -z "$ALLOCATION_TOKEN" && "$(bind_requires_token "$HOST")" == "1" ]]; then
  echo "Allocation token required for non-loopback relay bind $HOST. Use --allocation-token or AETHERLINK_RELAY_ALLOCATION_TOKEN, or bind tokenless diagnostics to 127.0.0.1, ::1, or localhost." >&2
  exit 2
fi

if [[ "$REQUIRE_ALLOCATION" == "0" && "$(bind_requires_token "$HOST")" == "1" ]]; then
  echo "Legacy unallocated relay mode is loopback-only; refusing non-loopback bind $HOST." >&2
  exit 2
fi

if [[ "$REQUIRE_ALLOCATION" == "1" && "$EPHEMERAL_ALLOCATIONS" == "1" && "$(bind_requires_token "$HOST")" == "1" ]]; then
  echo "Durable allocation storage is required for non-loopback relay bind $HOST. Remove --ephemeral-allocations or pass --allocation-store." >&2
  exit 2
fi

cd "$ROOT_DIR"

if [[ -n "$SUMMARY_JSON" && "$SUMMARY_JSON" != /* ]]; then
  SUMMARY_JSON="$ROOT_DIR/$SUMMARY_JSON"
fi

write_dry_run_summary() {
  local exit_status="$1"
  local allocation_token_present=0
  if [[ -z "$SUMMARY_JSON" ]]; then
    return 0
  fi
  if [[ -n "$ALLOCATION_TOKEN" ]]; then
    allocation_token_present=1
  fi
  mkdir -p "$(dirname "$SUMMARY_JSON")"
  python3 - "$SUMMARY_JSON" "$exit_status" "$HOST" "$PORT" "$REQUIRE_ALLOCATION" "$EPHEMERAL_ALLOCATIONS" "$ALLOCATION_STORE" "$allocation_token_present" "$ALLOCATION_TTL_SECONDS" "$PROBE_POLICY" "$CONTROL_TIMEOUT_SECONDS" "$MAX_CONNECTIONS" "$MAX_CONNECTIONS_PER_SOURCE" "$MAX_WAITING_PEERS_PER_SOURCE" "$WAITING_TIMEOUT_SECONDS" "$MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY" "$PREFLIGHT_RATE_PER_MINUTE" "$PREFLIGHT_BURST" "$ALLOCATION_RATE_PER_MINUTE" "$ALLOCATION_BURST" "$MAX_RATE_LIMIT_SOURCES" <<'PY'
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
    allocation_token_present,
    allocation_ttl_seconds,
    probe_policy,
    control_timeout_seconds,
    max_connections,
    max_connections_per_source,
    max_waiting_peers_per_source,
    waiting_timeout_seconds,
    max_waiting_peers_per_authenticated_identity,
    preflight_rate_per_minute,
    preflight_burst,
    allocation_rate_per_minute,
    allocation_burst,
    max_rate_limit_sources,
) = sys.argv[1:22]

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
        "token_present": allocation_token_present == "1",
        "token_redacted": allocation_token_present == "1",
        "store_mode": (
            "ephemeral"
            if ephemeral_allocations == "1"
            else ("custom" if allocation_store else "default")
        ),
        "ttl_seconds_present": bool(allocation_ttl_seconds),
    },
    "abuse_controls": {
        "probe_policy": probe_policy,
        "control_timeout_seconds": float(control_timeout_seconds),
        "max_connections": int(max_connections),
        "source_peer_quotas": {
            "max_concurrent_connections_per_source": int(max_connections_per_source),
            "max_waiting_peers_per_source": int(max_waiting_peers_per_source),
            "runtime_enforcement_verified": False,
            "shared_nat_vpn_bucket": True,
            "source_identity": "accepted_socket_address",
        },
        "waiting_peer_policy": {
            "max_duration_seconds": int(waiting_timeout_seconds),
            "max_waiting_peers_per_authenticated_identity": int(
                max_waiting_peers_per_authenticated_identity
            ),
            "post_authentication_only": True,
            "unauthenticated_bootstrap_clients_source_only": True,
            "runtime_enforcement_verified": False,
        },
        "source_rate_limits": {
            "preflight_rate_per_minute": int(preflight_rate_per_minute),
            "preflight_burst": int(preflight_burst),
            "allocation_rate_per_minute": int(allocation_rate_per_minute),
            "allocation_burst": int(allocation_burst),
            "max_rate_limit_sources": int(max_rate_limit_sources),
        },
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
  echo "Probe policy: $PROBE_POLICY"
  echo "Control-line deadline: ${CONTROL_TIMEOUT_SECONDS}s"
  echo "Maximum accepted connections: $MAX_CONNECTIONS"
  echo "Source quotas: connections=$MAX_CONNECTIONS_PER_SOURCE; waiting peers=$MAX_WAITING_PEERS_PER_SOURCE; identity=accepted socket canonical IPv4/IPv6"
  echo "Waiting peers count against both source quotas with counterpart headroom (2 * waiting <= connections). Active bridges remain counted against the source connection quota; frame forwarding is not throttled."
  echo "Waiting policy: timeout=${WAITING_TIMEOUT_SECONDS}s; authenticated identity waiting peers=$MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY; unauthenticated bootstrap clients remain source-only."
  echo "Source rate limits: preflight=${PREFLIGHT_RATE_PER_MINUTE}/minute burst=$PREFLIGHT_BURST; allocation/paired-renewal=${ALLOCATION_RATE_PER_MINUTE}/minute burst=$ALLOCATION_BURST; tracked sources=$MAX_RATE_LIMIT_SOURCES"
  echo "Source limits apply only to allocation, preflight, and paired-renewal control records; peer admission and encrypted forwarding are not throttled."
  echo "Shared NAT/VPN users share source quotas and rate-limit buckets. Defaults are development-relay guardrails, not production capacity policy."
  echo "After the relay is running, verify the advertised host with:"
  echo "  script/run_different_network_dev_runtime.sh --relay-host <public-or-vpn-host> --relay-port $PORT --preflight-only"
  echo "Do not use the bind address as the QR relay host unless the trusted device can actually reach it."
  exit 0
fi

swift build --product AetherLinkRelay >/dev/null
RELAY_BIN="$(swift build --show-bin-path)/AetherLinkRelay"
ARGS=("$RELAY_BIN" --host "$HOST" --port "$PORT")
ARGS+=(--probe-policy "$PROBE_POLICY")
ARGS+=(--control-timeout-seconds "$CONTROL_TIMEOUT_SECONDS")
ARGS+=(--max-connections "$MAX_CONNECTIONS")
ARGS+=(--max-connections-per-source "$MAX_CONNECTIONS_PER_SOURCE")
ARGS+=(--max-waiting-peers-per-source "$MAX_WAITING_PEERS_PER_SOURCE")
ARGS+=(--waiting-timeout-seconds "$WAITING_TIMEOUT_SECONDS")
ARGS+=(--max-waiting-peers-per-authenticated-identity "$MAX_WAITING_PEERS_PER_AUTHENTICATED_IDENTITY")
ARGS+=(--preflight-rate-per-minute "$PREFLIGHT_RATE_PER_MINUTE")
ARGS+=(--preflight-burst "$PREFLIGHT_BURST")
ARGS+=(--allocation-rate-per-minute "$ALLOCATION_RATE_PER_MINUTE")
ARGS+=(--allocation-burst "$ALLOCATION_BURST")
ARGS+=(--max-rate-limit-sources "$MAX_RATE_LIMIT_SOURCES")
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
echo "Probe policy: $PROBE_POLICY"
echo "Control-line deadline: ${CONTROL_TIMEOUT_SECONDS}s"
echo "Maximum accepted connections: $MAX_CONNECTIONS"
echo "Source quotas: connections=$MAX_CONNECTIONS_PER_SOURCE; waiting peers=$MAX_WAITING_PEERS_PER_SOURCE; identity=accepted socket canonical IPv4/IPv6"
echo "Waiting peers count against both source quotas with counterpart headroom (2 * waiting <= connections). Active bridges remain counted against the source connection quota; frame forwarding is not throttled."
echo "Source rate limits: preflight=${PREFLIGHT_RATE_PER_MINUTE}/minute burst=$PREFLIGHT_BURST; allocation/paired-renewal=${ALLOCATION_RATE_PER_MINUTE}/minute burst=$ALLOCATION_BURST; tracked sources=$MAX_RATE_LIMIT_SOURCES"
echo "Source limits apply only to allocation, preflight, and paired-renewal control records; peer admission and encrypted forwarding are not throttled."
echo "Shared NAT/VPN users share source quotas and rate-limit buckets. Defaults are development-relay guardrails, not production capacity policy."
if [[ "$PROBE_POLICY" == "legacy-unauthenticated" && "$(bind_requires_token "$HOST")" == "1" ]]; then
  echo "WARNING: exposed unauthenticated probe reveals route existence and runtime-waiting state."
fi
echo "Use a public, VPN, tunnel, or overlay address that both paired devices can reach."
echo "Preflight that advertised address with: script/run_different_network_dev_runtime.sh --relay-host <public-or-vpn-host> --relay-port $PORT --preflight-only"

if [[ -n "$ALLOCATION_TOKEN" ]]; then
  export AETHERLINK_RELAY_ALLOCATION_TOKEN="$ALLOCATION_TOKEN"
fi
exec "${ARGS[@]}"
