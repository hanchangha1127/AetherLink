#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}"
ADB="${ADB:-$ANDROID_HOME/platform-tools/adb}"
GRADLE="${GRADLE:-$ROOT_DIR/gradlew}"
PACKAGE_NAME="com.localagentbridge.android"
PORT="${LOCAL_AGENT_BRIDGE_PORT:-43170}"
GRADLE_USER_HOME="${GRADLE_USER_HOME:-$ROOT_DIR/.gradle}"
APK_PATH="$ROOT_DIR/apps/android/app/build/outputs/apk/debug/app-debug.apk"
REQUESTED_SERIAL="${ANDROID_SERIAL:-}"

usage() {
  cat <<'EOF'
Usage: script/android_usb_install.sh [--serial <adb-serial>]

Select a specific authorized Android device when more than one is attached.
ANDROID_SERIAL may be used instead of --serial.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --serial)
      if [[ "$#" -lt 2 || -z "$2" ]]; then
        echo "--serial requires a non-empty adb serial." >&2
        exit 2
      fi
      if [[ -n "$REQUESTED_SERIAL" && "$REQUESTED_SERIAL" != "$2" ]]; then
        echo "--serial does not match ANDROID_SERIAL." >&2
        exit 2
      fi
      REQUESTED_SERIAL="$2"
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

export ANDROID_HOME
export JAVA_HOME
export GRADLE_USER_HOME
export PATH="$ANDROID_HOME/platform-tools:$JAVA_HOME/bin:$PATH"

if [[ ! -x "$ADB" ]]; then
  echo "adb not found at $ADB" >&2
  echo "Set ANDROID_HOME or ADB to the Android SDK platform-tools adb path." >&2
  exit 2
fi

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "Java runtime not found at $JAVA_HOME/bin/java" >&2
  echo "Set JAVA_HOME to a JDK path. Android Studio's bundled JBR usually works." >&2
  exit 2
fi

if [[ ! -x "$GRADLE" ]]; then
  echo "Gradle wrapper not found at $GRADLE" >&2
  exit 2
fi

cd "$ROOT_DIR"

echo "Android devices visible to adb:"
"$ADB" devices -l
echo

DEVICE_LINES="$("$ADB" devices | awk 'NR > 1 && NF >= 2 { print $1 " " $2 }')"
if [[ -z "$DEVICE_LINES" ]]; then
  echo "No Android device found. Connect a phone with USB debugging enabled." >&2
  exit 3
fi

if [[ -n "$REQUESTED_SERIAL" ]]; then
  REQUESTED_STATE="$(echo "$DEVICE_LINES" | awk -v serial="$REQUESTED_SERIAL" '$1 == serial { print $2; exit }')"
  if [[ -z "$REQUESTED_STATE" ]]; then
    echo "Requested Android device $REQUESTED_SERIAL is not visible to adb." >&2
    "$ADB" devices -l >&2
    exit 3
  fi
  if [[ "$REQUESTED_STATE" == "unauthorized" ]]; then
    echo "Requested Android device $REQUESTED_SERIAL is unauthorized." >&2
    echo "Unlock the phone and approve the USB debugging prompt, then rerun this script." >&2
    exit 4
  fi
  if [[ "$REQUESTED_STATE" != "device" ]]; then
    echo "Requested Android device $REQUESTED_SERIAL is not ready: $REQUESTED_STATE" >&2
    exit 5
  fi
  SERIAL="$REQUESTED_SERIAL"
else
  AUTHORIZED_SERIALS="$(echo "$DEVICE_LINES" | awk '$2 == "device" { print $1 }')"
  AUTHORIZED_COUNT="$(printf '%s\n' "$AUTHORIZED_SERIALS" | awk 'NF { count += 1 } END { print count + 0 }')"
  if [[ "$AUTHORIZED_COUNT" -eq 0 ]]; then
    if echo "$DEVICE_LINES" | awk '$2 == "unauthorized" { found = 1 } END { exit found ? 0 : 1 }'; then
      echo "Android device is connected but unauthorized." >&2
      echo "Unlock the phone and approve the USB debugging prompt, then rerun this script." >&2
      exit 4
    fi
    echo "No authorized Android device is available." >&2
    "$ADB" devices -l >&2
    exit 5
  fi
  if [[ "$AUTHORIZED_COUNT" -gt 1 ]]; then
    echo "Multiple authorized Android devices are attached; choose one with --serial or ANDROID_SERIAL." >&2
    printf '%s\n' "$AUTHORIZED_SERIALS" >&2
    exit 5
  fi
  SERIAL="$AUTHORIZED_SERIALS"
fi

export ANDROID_SERIAL="$SERIAL"

echo "Using Android device $SERIAL"
echo "Preparing USB diagnostic loopback to AetherLink Runtime port $PORT"
"$ADB" -s "$SERIAL" reverse "tcp:$PORT" "tcp:$PORT"

echo "Building and installing debug APK"
"$GRADLE" --no-daemon :app:installDebug --console=plain

if [[ -f "$APK_PATH" ]]; then
  echo "Installed APK built at: $(stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S' "$APK_PATH")"
fi

ACTIVITY="$("$ADB" -s "$SERIAL" shell cmd package resolve-activity --brief "$PACKAGE_NAME" | tail -n 1 | tr -d '\r')"
if [[ -z "$ACTIVITY" || "$ACTIVITY" == "No activity found" ]]; then
  echo "Could not resolve launcher activity for $PACKAGE_NAME" >&2
  exit 6
fi

echo "Launching $ACTIVITY"
"$ADB" -s "$SERIAL" shell am start -n "$ACTIVITY"

echo "Android app launched."
echo "For this USB-only diagnostic run, use the prepared USB diagnostic route in AetherLink Settings."
