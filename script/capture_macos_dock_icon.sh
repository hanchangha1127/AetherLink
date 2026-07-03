#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_PATH="$ROOT_DIR/build/qa/aetherlink-macos-dock-visible.png"
SUMMARY_JSON=""
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: script/capture_macos_dock_icon.sh [--output <png-path>] [--summary-json <path>] [--dry-run]

Builds and launches dist/AetherLink.app, makes the Dock visible when it is
temporarily hidden by user settings, captures the real macOS desktop, and
restores the Dock autohide setting before exit.

With --dry-run, validates the expected capture contract and writes summary JSON
without building, launching, changing Dock settings, or taking a screenshot.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      if [[ $# -lt 2 ]]; then
        echo "--output requires a value." >&2
        exit 2
      fi
      OUTPUT_PATH="$2"
      shift 2
      ;;
    --summary-json)
      if [[ $# -lt 2 ]]; then
        echo "--summary-json requires a value." >&2
        exit 2
      fi
      SUMMARY_JSON="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
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

if [[ "$OUTPUT_PATH" != /* ]]; then
  OUTPUT_PATH="$ROOT_DIR/$OUTPUT_PATH"
fi

if [[ -n "$SUMMARY_JSON" && "$SUMMARY_JSON" != /* ]]; then
  SUMMARY_JSON="$ROOT_DIR/$SUMMARY_JSON"
fi

write_summary() {
  local exit_status="$1"
  local dock_capture_verified="$2"
  local dock_autohide_changed="${3:-0}"
  local bundle_path="$ROOT_DIR/dist/AetherLink.app"
  local info_plist="$bundle_path/Contents/Info.plist"
  local bundle_icon_file=""

  if [[ -z "$SUMMARY_JSON" ]]; then
    return 0
  fi

  if [[ -f "$info_plist" ]]; then
    bundle_icon_file="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIconFile' "$info_plist" 2>/dev/null || true)"
  fi

  mkdir -p "$(dirname "$SUMMARY_JSON")"
  python3 - "$SUMMARY_JSON" "$OUTPUT_PATH" "$bundle_path" "$bundle_icon_file" "$DRY_RUN" "$exit_status" "$dock_capture_verified" "$dock_autohide_changed" <<'PY'
import json
import os
import sys

summary_path, output_path, bundle_path, bundle_icon_file, dry_run, exit_status, dock_capture_verified, dock_autohide_changed = sys.argv[1:9]
dry_run_enabled = dry_run == "1"
screenshot_present = os.path.exists(output_path)
capture_verified = (not dry_run_enabled) and dock_capture_verified == "1" and screenshot_present
caveats = []
if dry_run_enabled:
    caveats.append("dry_run_not_macos_dock_screenshot_proof")
elif not capture_verified:
    caveats.append("macos_dock_capture_not_verified")

summary = {
    "exit_status": int(exit_status),
    "mode": {
        "dry_run": dry_run_enabled,
    },
    "paths": {
        "output": output_path,
        "bundle": bundle_path,
    },
    "bundle": {
        "exists": os.path.isdir(bundle_path),
        "cf_bundle_icon_file": bundle_icon_file or None,
    },
    "coverage": {
        "macos_dock_capture_dry_run": dry_run_enabled,
        "macos_dock_capture_verified": capture_verified,
        "macos_dock_screenshot_artifact_present": screenshot_present and not dry_run_enabled,
        "physical_macos_dock_screenshot": capture_verified,
        "dock_autohide_changed": dock_autohide_changed == "1",
    },
    "caveats": caveats,
}
with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

if [[ "$DRY_RUN" == "1" ]]; then
  write_summary 0 0 0
  echo "Dock capture dry-run summary: ${SUMMARY_JSON:-<not-written>}"
  echo "Not a macOS Dock screenshot proof."
  exit 0
fi

ORIGINAL_AUTOHIDE="$(defaults read com.apple.dock autohide 2>/dev/null || true)"
DOCK_AUTOHIDE_CHANGED=0

restore_dock() {
  if [[ "$DOCK_AUTOHIDE_CHANGED" == "1" ]]; then
    defaults write com.apple.dock autohide -bool true >/dev/null
    killall Dock >/dev/null 2>&1 || true
  fi
}

trap restore_dock EXIT

cd "$ROOT_DIR"

./script/build_and_run.sh --verify

if [[ "$ORIGINAL_AUTOHIDE" == "1" ]]; then
  defaults write com.apple.dock autohide -bool false >/dev/null
  DOCK_AUTOHIDE_CHANGED=1
  killall Dock >/dev/null 2>&1 || true
  sleep 2
fi

sleep 2

mkdir -p "$(dirname "$OUTPUT_PATH")"
screencapture -x "$OUTPUT_PATH"

echo "Dock screenshot: $OUTPUT_PATH"
echo "Bundle: $ROOT_DIR/dist/AetherLink.app"
/usr/libexec/PlistBuddy -c 'Print :CFBundleIconFile' "$ROOT_DIR/dist/AetherLink.app/Contents/Info.plist" \
  | sed 's/^/CFBundleIconFile: /'
write_summary 0 1 "$DOCK_AUTOHIDE_CHANGED"
