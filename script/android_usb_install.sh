#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}"
ADB="${ADB:-$ANDROID_HOME/platform-tools/adb}"
PACKAGE_NAME="com.localagentbridge.android"
PORT="${LOCAL_AGENT_BRIDGE_PORT:-43170}"
GRADLE_USER_HOME="${GRADLE_USER_HOME:-$ROOT_DIR/.gradle}"
APK_PATH="$ROOT_DIR/apps/android/app/build/outputs/apk/debug/app-debug.apk"

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

cd "$ROOT_DIR"

echo "Android devices visible to adb:"
"$ADB" devices -l
echo

DEVICE_LINES="$("$ADB" devices | awk 'NR > 1 && NF >= 2 { print $1 " " $2 }')"
if [[ -z "$DEVICE_LINES" ]]; then
  echo "No Android device found. Connect a phone with USB debugging enabled." >&2
  exit 3
fi

if echo "$DEVICE_LINES" | awk '$2 == "unauthorized" { found = 1 } END { exit found ? 0 : 1 }'; then
  echo "Android device is connected but unauthorized." >&2
  echo "Unlock the phone and approve the USB debugging prompt, then rerun this script." >&2
  "$ADB" devices -l >&2
  exit 4
fi

SERIAL="$(echo "$DEVICE_LINES" | awk '$2 == "device" { print $1; exit }')"
if [[ -z "$SERIAL" ]]; then
  echo "No authorized Android device is available." >&2
  "$ADB" devices -l >&2
  exit 5
fi

echo "Using Android device $SERIAL"
echo "Preparing USB diagnostic loopback to AetherLink Runtime port $PORT"
"$ADB" -s "$SERIAL" reverse "tcp:$PORT" "tcp:$PORT"

echo "Building and installing debug APK"
./gradlew --no-daemon :app:installDebug --console=plain

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
