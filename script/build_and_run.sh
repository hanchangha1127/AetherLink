#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"

usage() {
  echo "usage: $0 [run|--debug|--logs|--telemetry|--verify|--package-only]" >&2
}

validate_mode() {
  case "$1" in
    run|--debug|debug|--logs|logs|--telemetry|telemetry|--verify|verify|--package-only|package-only)
      ;;
    *)
      usage
      return 2
      ;;
  esac
}

validate_mode "$MODE"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PHYSICAL_ROOT_DIR="$(cd "$ROOT_DIR" && pwd -P)"

is_package_only() {
  case "$MODE" in
    --package-only|package-only)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

PRODUCT_NAME="AetherLink"
TARGET_EXECUTABLE_NAME="LocalAgentBridge"
APP_NAME="AetherLink"
BUNDLE_ID="dev.aetherlink.companion"
MIN_SYSTEM_VERSION="14.0"
REPRO_SWIFT_SCRATCH_PATH="/private/tmp/aetherlink-g6-swift-scratch-v1"
RELEASE_VERSION_LEDGER="$ROOT_DIR/release/version-ledger.tsv"
MAX_ANDROID_VERSION_CODE=2100000000
MAX_MARKETING_VERSION_COMPONENT=2147483647
MARKETING_VERSION=""
BUILD_NUMBER=""
DEBUG_RUNTIME_IDENTITY_FILE="${AETHERLINK_RUNTIME_IDENTITY_FILE:-$HOME/Library/Application Support/AetherLink/debug-runtime-identity.json}"
APP_LAUNCH_SETTLE_SECONDS=5

decimal_is_at_most() {
  local value="$1"
  local limit="$2"
  if (( ${#value} < ${#limit} )); then
    return 0
  fi
  if (( ${#value} > ${#limit} )); then
    return 1
  fi
  [[ "$value" == "$limit" || "$value" < "$limit" ]]
}

load_release_version_metadata() {
  local ledger_path="$1"
  local last_byte
  local line
  local line_number=0
  local candidate_build
  local candidate_marketing_version
  local candidate_major
  local candidate_minor
  local candidate_patch
  local component
  local previous_build=0
  local previous_major=0
  local previous_minor=0
  local previous_patch=0
  local entry_count=0

  if [[ ! -f "$ledger_path" || -L "$ledger_path" ]]; then
    echo "error: release version ledger must be a regular non-symlink file" >&2
    return 2
  fi
  last_byte="$(
    /usr/bin/tail -c 1 "$ledger_path" \
      | /usr/bin/od -An -t u1 \
      | /usr/bin/tr -d '[:space:]'
  )"
  if [[ "$last_byte" != "10" ]]; then
    echo "error: release version ledger must end with one LF" >&2
    return 2
  fi
  if ! LC_ALL=C /usr/bin/od -An -v -t u1 "$ledger_path" \
    | /usr/bin/awk '
        {
          for (field = 1; field <= NF; field += 1) {
            byte = $field + 0
            if ((byte < 32 && byte != 9 && byte != 10) || byte > 126) {
              exit 1
            }
          }
        }
      '; then
    echo "error: release version ledger may contain only printable ASCII, tab, and LF" >&2
    return 2
  fi

  while IFS= read -r line; do
    ((line_number += 1))
    if (( line_number == 1 )); then
      if [[ "$line" != $'build_number\tmarketing_version' ]]; then
        echo "error: release version ledger header is invalid" >&2
        return 2
      fi
      continue
    fi

    if [[ "$line" != *$'\t'* || "${line#*$'\t'}" == *$'\t'* ]]; then
      echo "error: release version ledger line $line_number must have exactly two fields" >&2
      return 2
    fi
    candidate_build="${line%%$'\t'*}"
    candidate_marketing_version="${line#*$'\t'}"
    if [[ ! "$candidate_build" =~ ^[1-9][0-9]*$ ]] \
      || ! decimal_is_at_most "$candidate_build" "$MAX_ANDROID_VERSION_CODE"; then
      echo "error: release version ledger line $line_number has an invalid build number" >&2
      return 2
    fi
    if [[ ! "$candidate_marketing_version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
      echo "error: release version ledger line $line_number has an invalid marketing version" >&2
      return 2
    fi

    IFS=. read -r candidate_major candidate_minor candidate_patch \
      <<<"$candidate_marketing_version"
    for component in "$candidate_major" "$candidate_minor" "$candidate_patch"; do
      if ! decimal_is_at_most "$component" "$MAX_MARKETING_VERSION_COMPONENT"; then
        echo "error: release version ledger line $line_number has an oversized marketing version" >&2
        return 2
      fi
    done

    if (( entry_count > 0 )); then
      if (( candidate_build <= previous_build )); then
        echo "error: release version ledger build numbers must be strictly increasing" >&2
        return 2
      fi
      if (( candidate_major < previous_major )) \
        || {
          (( candidate_major == previous_major )) \
            && (( candidate_minor < previous_minor ))
        } \
        || {
          (( candidate_major == previous_major )) \
            && (( candidate_minor == previous_minor )) \
            && (( candidate_patch < previous_patch ))
        }; then
        echo "error: release version ledger marketing versions must not decrease" >&2
        return 2
      fi
    fi

    BUILD_NUMBER="$candidate_build"
    MARKETING_VERSION="$candidate_marketing_version"
    previous_build="$candidate_build"
    previous_major="$candidate_major"
    previous_minor="$candidate_minor"
    previous_patch="$candidate_patch"
    ((entry_count += 1))
  done <"$ledger_path"

  if (( line_number == 0 || entry_count == 0 )); then
    echo "error: release version ledger has no entries" >&2
    return 2
  fi
}

validate_version_metadata() {
  if [[ ! "$MARKETING_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "error: ledger marketing version must be a numeric major.minor.patch value" >&2
    return 2
  fi
  if [[ ! "$BUILD_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
    echo "error: ledger build number must be a positive decimal integer" >&2
    return 2
  fi
}

load_release_version_metadata "$RELEASE_VERSION_LEDGER"
validate_version_metadata

DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
ICON_SOURCE="$ROOT_DIR/apps/macos/LocalAgentBridgeApp/Sources/Resources/AppIcon.icns"
ICON_NAME="AppIcon"
ICON_DEST="$APP_RESOURCES/$ICON_NAME.icns"

cd "$ROOT_DIR"

BUILD_CONFIGURATION="debug"
if is_package_only; then
  BUILD_CONFIGURATION="release"
else
  pkill -x "$APP_NAME" >/dev/null 2>&1 || true
fi

SWIFT_BUILD_OPTIONS=(-c "$BUILD_CONFIGURATION")
if is_package_only && [[ -n "${AETHERLINK_REPRO_SWIFT_SCRATCH_PATH:-}" ]]; then
  if [[ "$AETHERLINK_REPRO_SWIFT_SCRATCH_PATH" != "$REPRO_SWIFT_SCRATCH_PATH" ]]; then
    echo "error: reproducible Swift scratch path differs from the fixed release path" >&2
    exit 2
  fi
  if [[ "$AETHERLINK_REPRO_SWIFT_SCRATCH_PATH" != /* ]]; then
    echo "error: reproducible Swift scratch path must be absolute" >&2
    exit 2
  fi
  scratch_parent="${AETHERLINK_REPRO_SWIFT_SCRATCH_PATH%/*}"
  scratch_name="${AETHERLINK_REPRO_SWIFT_SCRATCH_PATH##*/}"
  if [[ -z "$scratch_parent" || -z "$scratch_name" || "$scratch_name" == "." || "$scratch_name" == ".." ]]; then
    echo "error: reproducible Swift scratch path is invalid" >&2
    exit 2
  fi
  if [[ ! -d "$scratch_parent" || -L "$scratch_parent" ]]; then
    echo "error: reproducible Swift scratch parent must be a physical directory" >&2
    exit 2
  fi
  physical_scratch_parent="$(cd "$scratch_parent" && pwd -P)"
  physical_scratch_path="$physical_scratch_parent/$scratch_name"
  if [[ "$physical_scratch_path" != "$AETHERLINK_REPRO_SWIFT_SCRATCH_PATH" ]]; then
    echo "error: reproducible Swift scratch path must use its physical parent" >&2
    exit 2
  fi
  case "$physical_scratch_path/" in
    "$PHYSICAL_ROOT_DIR/"*)
      echo "error: reproducible Swift scratch path must be outside the source root" >&2
      exit 2
      ;;
  esac
  if [[ -e "$physical_scratch_path" || -L "$physical_scratch_path" ]]; then
    echo "error: reproducible Swift scratch path must not already exist" >&2
    exit 2
  fi
  SWIFT_BUILD_OPTIONS+=(
    --jobs 1
    --scratch-path "$physical_scratch_path"
    -Xswiftc -num-threads
    -Xswiftc 1
    -Xswiftc -file-prefix-map
    -Xswiftc "$PHYSICAL_ROOT_DIR=/aetherlink/source"
    -Xswiftc -file-compilation-dir
    -Xswiftc /aetherlink/source
    -Xswiftc -prefix-serialized-debugging-options
    -Xcc -working-directory
    -Xcc "$physical_scratch_path"
    -Xcc -Xclang
    -Xcc -fdebug-compilation-dir=/aetherlink/source
    -Xcc -Xclang
    -Xcc -fdisable-module-hash
    -Xcc -Xclang
    -Xcc -fbuild-session-timestamp=0
    -Xcc -Xclang
    -Xcc -fno-pch-timestamp
    -Xlinker -reproducible
  )
fi

swift build "${SWIFT_BUILD_OPTIONS[@]}" --product "$PRODUCT_NAME"
BUILD_BIN_PATH="$(swift build "${SWIFT_BUILD_OPTIONS[@]}" --show-bin-path)"
BUILD_BINARY="$BUILD_BIN_PATH/$PRODUCT_NAME"
if [[ ! -x "$BUILD_BINARY" ]]; then
  BUILD_BINARY="$BUILD_BIN_PATH/$TARGET_EXECUTABLE_NAME"
fi

if [[ ! -x "$BUILD_BINARY" ]]; then
  echo "error: built executable not found for product $PRODUCT_NAME" >&2
  exit 1
fi

RESOURCE_BUNDLE_CANDIDATES=()
while IFS= read -r -d '' candidate; do
  RESOURCE_BUNDLE_CANDIDATES+=("$candidate")
done < <(
  find "$BUILD_BIN_PATH" \
    -maxdepth 1 \
    -type d \
    -name "*_${TARGET_EXECUTABLE_NAME}.bundle" \
    -print0
)
if [[ "${#RESOURCE_BUNDLE_CANDIDATES[@]}" -ne 1 ]]; then
  echo "error: expected exactly one SwiftPM resource bundle for $TARGET_EXECUTABLE_NAME; found ${#RESOURCE_BUNDLE_CANDIDATES[@]}" >&2
  exit 1
fi
RESOURCE_BUNDLE_SOURCE="${RESOURCE_BUNDLE_CANDIDATES[0]}"
RESOURCE_BUNDLE_DESTINATION="$APP_RESOURCES/$(basename "$RESOURCE_BUNDLE_SOURCE")"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"
cp -R "$RESOURCE_BUNDLE_SOURCE" "$APP_RESOURCES/"
# SwiftPM can retain a formerly processed resource in an incremental build
# directory. The app icon belongs to the outer app bundle, not the localization
# bundle, so normalize the copied payload even when the build cache is stale.
rm -f "$RESOURCE_BUNDLE_DESTINATION/AppIcon.icns"

if [[ -f "$ICON_SOURCE" ]]; then
  cp "$ICON_SOURCE" "$ICON_DEST"
else
  echo "warning: app icon not found at $ICON_SOURCE" >&2
fi

cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleShortVersionString</key>
  <string>$MARKETING_VERSION</string>
  <key>CFBundleVersion</key>
  <string>$BUILD_NUMBER</string>
  <key>CFBundleIconFile</key>
  <string>$ICON_NAME</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleLocalizations</key>
  <array>
    <string>en</string>
    <string>ko</string>
    <string>ja</string>
    <string>zh-Hans</string>
    <string>fr</string>
  </array>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>$MIN_SYSTEM_VERSION</string>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

/usr/bin/codesign --force --deep --sign - "$APP_BUNDLE"
/usr/bin/codesign --verify --deep --strict "$APP_BUNDLE"

open_app() {
  /usr/bin/nohup /usr/bin/env \
    AETHERLINK_RUNTIME_IDENTITY_FILE="$DEBUG_RUNTIME_IDENTITY_FILE" \
    "$APP_BINARY" >/dev/null 2>&1 &
  local launch_pid=$!
  sleep "$APP_LAUNCH_SETTLE_SECONDS"
  if ! kill -0 "$launch_pid" >/dev/null 2>&1; then
    echo "error: $APP_NAME exited during launch" >&2
    return 1
  fi
}

case "$MODE" in
  run)
    open_app
    ;;
  --debug|debug)
    /usr/bin/env AETHERLINK_RUNTIME_IDENTITY_FILE="$DEBUG_RUNTIME_IDENTITY_FILE" \
      lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    open_app
    ;;
  --package-only|package-only)
    echo "Packaged self-contained release app at $APP_BUNDLE"
    ;;
  *)
    usage
    exit 2
    ;;
esac
