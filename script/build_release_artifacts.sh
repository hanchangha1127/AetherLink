#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_STUDIO_JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
RELEASE_MACOS_PACKAGE_OUTPUT_ROOT="$ROOT_DIR/dist/release-package"

cd "$ROOT_DIR"

if [[ -z "${JAVA_HOME:-}" && -d "$ANDROID_STUDIO_JAVA_HOME" ]]; then
  export JAVA_HOME="$ANDROID_STUDIO_JAVA_HOME"
fi
export AETHERLINK_PACKAGE_OUTPUT_ROOT="$RELEASE_MACOS_PACKAGE_OUTPUT_ROOT"

source_before="$(
  python3 script/package_release_artifacts.py source-digest
)"

./gradlew \
  --offline \
  --no-daemon \
  --console=plain \
  -PaetherlinkStrictReleaseDependencyLocks=true \
  :app:clean \
  :core:pairing:clean \
  :core:protocol:clean \
  :core:transport:clean \
  :app:assembleRelease \
  :app:bundleRelease \
  :app:lintRelease

./script/build_and_run.sh --package-only

source_after="$(
  python3 script/package_release_artifacts.py source-digest
)"
if [[ "$source_before" != "$source_after" ]]; then
  echo "error: release build inputs changed while artifacts were built" >&2
  exit 2
fi

python3 script/check_release_version_ledger.py --artifacts
python3 script/check_release_artifact_archive.py --android-build-outputs
python3 script/package_release_artifacts.py create
python3 script/check_release_artifact_archive.py
