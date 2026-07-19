#!/usr/bin/env bash
set -uo pipefail

if [[ "${AETHERLINK_OWNED_PROCESS_SIGNALS_RESET:-0}" != "1" ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to normalize inherited signal dispositions." >&2
    exit 2
  fi
  export AETHERLINK_OWNED_PROCESS_SIGNALS_RESET=1
  exec python3 -c '
import os
import signal
import sys

for name in ("SIGTERM", "SIGINT", "SIGHUP"):
    signal.signal(getattr(signal, name), signal.SIG_DFL)
os.execv(sys.argv[1], sys.argv[1:])
' "$0" "$@"
fi
unset AETHERLINK_OWNED_PROCESS_SIGNALS_RESET

OWNER_PID=""
PID_FILE=""
GRACE_SECONDS=3
CHILD_PID=""
SHUTTING_DOWN=0

usage() {
  cat <<'USAGE' >&2
Usage:
  script/owned_process_supervisor.sh --owner-pid <pid> --pid-file <path> [--grace-seconds <seconds>] -- <command> [args...]

Runs one foreground child while its explicit outer owner remains the
supervisor's direct parent. The supervisor forwards TERM, INT, and HUP, then
uses KILL if the child has not exited within the bounded grace period.
USAGE
}

process_parent_pid() {
  local pid="$1"
  local parent_pid

  parent_pid="$(ps -o ppid= -p "$pid" 2>/dev/null)" || return 1
  parent_pid="${parent_pid//[[:space:]]/}"
  [[ "$parent_pid" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "$parent_pid"
}

child_is_owned_and_running() {
  local parent_pid
  local state
  local snapshot

  [[ -n "$CHILD_PID" ]] || return 1
  snapshot="$(ps -o ppid= -o state= -p "$CHILD_PID" 2>/dev/null)" || return 1
  read -r parent_pid state <<<"$snapshot"
  [[ "$parent_pid" =~ ^[0-9]+$ ]] || return 1
  [[ "$parent_pid" == "$$" ]] || return 1
  [[ -n "$state" ]] || return 1
  [[ "$state" != Z* ]]
}

write_child_pid() {
  local pid_file_dir
  local temporary_file

  pid_file_dir="$(dirname "$PID_FILE")"
  [[ -d "$pid_file_dir" ]] || {
    echo "PID file directory does not exist: $pid_file_dir" >&2
    return 1
  }

  umask 077
  temporary_file="$(mktemp "${PID_FILE}.tmp.XXXXXX")" || return 1
  if ! printf '%s\n' "$CHILD_PID" >"$temporary_file"; then
    rm -f "$temporary_file"
    return 1
  fi
  chmod 600 "$temporary_file" || {
    rm -f "$temporary_file"
    return 1
  }
  if ! mv -f "$temporary_file" "$PID_FILE"; then
    rm -f "$temporary_file"
    return 1
  fi
}

reap_child() {
  local child_status

  [[ -n "$CHILD_PID" ]] || return 0
  wait "$CHILD_PID" 2>/dev/null
  child_status=$?
  CHILD_PID=""
  return "$child_status"
}

terminate_child() {
  local forwarded_signal="$1"
  local term_remaining_checks=$((GRACE_SECONDS * 20))
  local kill_remaining_checks=40

  if child_is_owned_and_running; then
    kill -s "$forwarded_signal" "$CHILD_PID" 2>/dev/null || true
  fi

  while child_is_owned_and_running && ((term_remaining_checks > 0)); do
    sleep 0.05
    ((term_remaining_checks -= 1))
  done
  if child_is_owned_and_running; then
    kill -KILL "$CHILD_PID" 2>/dev/null || true
  fi

  while child_is_owned_and_running && ((kill_remaining_checks > 0)); do
    sleep 0.05
    ((kill_remaining_checks -= 1))
  done
  if child_is_owned_and_running; then
    CHILD_PID=""
    return 1
  fi
  reap_child >/dev/null 2>&1 || true
}

shutdown_for_signal() {
  local forwarded_signal="$1"
  local exit_status="$2"

  if ((SHUTTING_DOWN == 1)); then
    return
  fi
  SHUTTING_DOWN=1
  trap - TERM INT HUP
  terminate_child "$forwarded_signal"
  exit "$exit_status"
}

cleanup() {
  if [[ -n "$CHILD_PID" ]]; then
    terminate_child TERM
  fi
}

start_child_with_default_signals() {
  python3 -c '
import os
import signal
import sys

for name in ("SIGTERM", "SIGINT", "SIGHUP"):
    signal.signal(getattr(signal, name), signal.SIG_DFL)
os.execvp(sys.argv[1], sys.argv[1:])
' "$@" &
  CHILD_PID="$!"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner-pid)
      [[ $# -ge 2 ]] || {
        echo "--owner-pid requires a value." >&2
        usage
        exit 2
      }
      OWNER_PID="$2"
      shift 2
      ;;
    --pid-file)
      [[ $# -ge 2 ]] || {
        echo "--pid-file requires a value." >&2
        usage
        exit 2
      }
      PID_FILE="$2"
      shift 2
      ;;
    --grace-seconds)
      [[ $# -ge 2 ]] || {
        echo "--grace-seconds requires a value." >&2
        usage
        exit 2
      }
      GRACE_SECONDS="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if ! [[ "$OWNER_PID" =~ ^[1-9][0-9]*$ ]] || ((OWNER_PID <= 1)); then
  echo "--owner-pid must be a canonical process ID greater than 1." >&2
  exit 2
fi
if [[ -z "$PID_FILE" ]]; then
  echo "--pid-file is required." >&2
  exit 2
fi
if ! [[ "$GRACE_SECONDS" =~ ^[1-9][0-9]*$ ]] || ((GRACE_SECONDS > 60)); then
  echo "--grace-seconds must be a canonical integer in 1...60." >&2
  exit 2
fi
if [[ $# -eq 0 ]]; then
  echo "A child command is required after --." >&2
  exit 2
fi

CURRENT_PARENT_PID="$(process_parent_pid "$$")" || {
  echo "Could not determine supervisor parent process." >&2
  exit 2
}
if [[ "$CURRENT_PARENT_PID" != "$OWNER_PID" ]]; then
  echo "The explicit owner PID must be the supervisor's direct parent." >&2
  exit 2
fi
if ! kill -0 "$OWNER_PID" 2>/dev/null; then
  echo "The explicit owner process is not alive." >&2
  exit 2
fi

trap cleanup EXIT
trap 'shutdown_for_signal TERM 143' TERM
trap 'shutdown_for_signal INT 130' INT
trap 'shutdown_for_signal HUP 129' HUP

start_child_with_default_signals "$@"
if ! write_child_pid; then
  echo "Could not record supervised child PID safely: $PID_FILE" >&2
  exit 1
fi

while true; do
  CURRENT_PARENT_PID="$(process_parent_pid "$$")" || CURRENT_PARENT_PID=""
  if [[ "$CURRENT_PARENT_PID" != "$OWNER_PID" ]]; then
    shutdown_for_signal TERM 125
  fi

  if ! child_is_owned_and_running; then
    wait "$CHILD_PID"
    CHILD_STATUS=$?
    CHILD_PID=""
    exit "$CHILD_STATUS"
  fi
  sleep 0.5
done
