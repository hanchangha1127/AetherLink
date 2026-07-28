#!/usr/bin/env python3
"""Validate the shared Android/macOS release version ledger and its consumers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import plistlib
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "release/version-ledger.tsv"
ANDROID_BUILD_PATH = ROOT / "apps/android/app/build.gradle.kts"
MACOS_BUILD_PATH = ROOT / "script/build_and_run.sh"
G0_DECISION_PATH = ROOT / "docs/v1/g0/decision-v1.json"
ANDROID_RELEASE_METADATA_PATH = (
    ROOT / "apps/android/app/build/outputs/apk/release/output-metadata.json"
)
MACOS_INFO_PLIST_PATH = ROOT / "dist/AetherLink.app/Contents/Info.plist"

LEDGER_HEADER = "build_number\tmarketing_version"
MAX_ANDROID_VERSION_CODE = 2_100_000_000
MAX_MARKETING_VERSION_COMPONENT = 2_147_483_647
BUILD_NUMBER_PATTERN = re.compile(r"[1-9][0-9]*\Z")
MARKETING_VERSION_PATTERN = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z"
)


@dataclass(frozen=True)
class ReleaseVersion:
    build_number: int
    marketing_version: str
    semantic_version: tuple[int, int, int]


class LedgerError(ValueError):
    """Raised when the release version ledger violates its closed format."""


def parse_release_version_ledger(raw: bytes) -> tuple[ReleaseVersion, ...]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise LedgerError("UTF-8 BOM is not allowed")
    if b"\r" in raw:
        raise LedgerError("only LF line endings are allowed")
    if not raw.endswith(b"\n"):
        raise LedgerError("ledger must end with one LF")
    if any(
        (byte < 0x20 and byte not in (0x09, 0x0A)) or byte > 0x7E
        for byte in raw
    ):
        raise LedgerError(
            "ledger may contain only printable ASCII, tab, and LF"
        )

    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise LedgerError("ledger must be ASCII") from error

    lines = text.split("\n")[:-1]
    if not lines or lines[0] != LEDGER_HEADER:
        raise LedgerError(f"first line must be exactly {LEDGER_HEADER!r}")
    if len(lines) < 2:
        raise LedgerError("ledger must contain at least one release entry")

    entries: list[ReleaseVersion] = []
    previous_build_number = 0
    previous_semantic_version = (0, 0, 0)
    for line_number, line in enumerate(lines[1:], start=2):
        fields = line.split("\t")
        if len(fields) != 2 or any(not field for field in fields):
            raise LedgerError(
                f"line {line_number} must contain exactly two nonempty tab-separated fields"
            )

        build_number_text, marketing_version = fields
        if BUILD_NUMBER_PATTERN.fullmatch(build_number_text) is None:
            raise LedgerError(f"line {line_number} has an invalid build_number")
        build_number = int(build_number_text)
        if build_number > MAX_ANDROID_VERSION_CODE:
            raise LedgerError(
                f"line {line_number} exceeds Android versionCode limit "
                f"{MAX_ANDROID_VERSION_CODE}"
            )
        if build_number <= previous_build_number:
            raise LedgerError(
                f"line {line_number} build_number must be strictly increasing"
            )

        version_match = MARKETING_VERSION_PATTERN.fullmatch(marketing_version)
        if version_match is None:
            raise LedgerError(
                f"line {line_number} marketing_version must be numeric major.minor.patch"
            )
        semantic_version = tuple(int(part) for part in version_match.groups())
        if any(
            component > MAX_MARKETING_VERSION_COMPONENT
            for component in semantic_version
        ):
            raise LedgerError(
                f"line {line_number} has an oversized marketing_version component"
            )
        if semantic_version < previous_semantic_version:
            raise LedgerError(
                f"line {line_number} marketing_version must not decrease"
            )

        entries.append(
            ReleaseVersion(
                build_number=build_number,
                marketing_version=marketing_version,
                semantic_version=semantic_version,
            )
        )
        previous_build_number = build_number
        previous_semantic_version = semantic_version

    return tuple(entries)


def load_release_version_ledger(path: Path = LEDGER_PATH) -> tuple[ReleaseVersion, ...]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise LedgerError(f"cannot read {path}: {error}") from error
    return parse_release_version_ledger(raw)


def source_contract_failures(current: ReleaseVersion) -> list[str]:
    failures: list[str] = []

    try:
        decision = json.loads(G0_DECISION_PATH.read_text(encoding="utf-8"))
        g0_product_version = decision["productScope"]["releaseVersion"]
        g0_policy_version = decision["releasePolicy"]["versioning"]["marketingVersion"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        failures.append(f"cannot read G0 release version decision: {error}")
    else:
        if g0_product_version != current.marketing_version:
            failures.append(
                "ledger marketing version does not match G0 product releaseVersion "
                f"({current.marketing_version!r} != {g0_product_version!r})"
            )
        if g0_policy_version != current.marketing_version:
            failures.append(
                "ledger marketing version does not match G0 versioning policy "
                f"({current.marketing_version!r} != {g0_policy_version!r})"
            )

    try:
        android_build = ANDROID_BUILD_PATH.read_text(encoding="utf-8")
    except OSError as error:
        failures.append(f"cannot read Android build configuration: {error}")
    else:
        for snippet in (
            'rootProject.file("release/version-ledger.tsv")',
            "loadReleaseVersionLedger(",
            "Release version ledger may contain only printable ASCII, tab, and LF",
            "val releaseVersionProvider = providers.provider {",
            'selector().withBuildType("release")',
            "output.versionCode.set(releaseVersionProvider.map { it.buildNumber })",
            "output.versionName.set(releaseVersionProvider.map { it.marketingVersion })",
            'applicationId = "com.localagentbridge.android"',
            "versionCode = 1",
            'versionName = "0.1.0"',
        ):
            if snippet not in android_build:
                failures.append(
                    f"{ANDROID_BUILD_PATH.relative_to(ROOT)} is missing {snippet!r}"
                )

    try:
        macos_build = MACOS_BUILD_PATH.read_text(encoding="utf-8")
    except OSError as error:
        failures.append(f"cannot read macOS build script: {error}")
    else:
        for snippet in (
            'RELEASE_VERSION_LEDGER="$ROOT_DIR/release/version-ledger.tsv"',
            "load_release_version_metadata",
            'load_release_version_metadata "$RELEASE_VERSION_LEDGER"',
            '/usr/bin/od -An -v -t u1 "$ledger_path"',
            "release version ledger may contain only printable ASCII, tab, and LF",
            "MAX_ANDROID_VERSION_CODE=2100000000",
            'BUNDLE_ID="dev.aetherlink.companion"',
            "CFBundleShortVersionString",
            "CFBundleVersion",
        ):
            if snippet not in macos_build:
                failures.append(
                    f"{MACOS_BUILD_PATH.relative_to(ROOT)} is missing {snippet!r}"
                )
        for forbidden in (
            "AETHERLINK_MARKETING_VERSION",
            "AETHERLINK_BUILD_NUMBER",
        ):
            if forbidden in macos_build:
                failures.append(
                    f"{MACOS_BUILD_PATH.relative_to(ROOT)} retains version override {forbidden}"
                )

    return failures


def artifact_contract_failures(current: ReleaseVersion) -> list[str]:
    failures: list[str] = []

    try:
        metadata = json.loads(
            ANDROID_RELEASE_METADATA_PATH.read_text(encoding="utf-8")
        )
        elements = metadata["elements"]
        if type(elements) is not list or len(elements) != 1:
            raise ValueError("expected exactly one Android release output")
        android_output = elements[0]
        android_version_code = android_output["versionCode"]
        android_version_name = android_output["versionName"]
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        failures.append(f"cannot read Android release output metadata: {error}")
    else:
        if type(android_version_code) is not int or (
            android_version_code != current.build_number
        ):
            failures.append(
                "Android release versionCode does not match the ledger "
                f"({android_version_code!r} != {current.build_number})"
            )
        if android_version_name != current.marketing_version:
            failures.append(
                "Android release versionName does not match the ledger "
                f"({android_version_name!r} != {current.marketing_version!r})"
            )

    try:
        with MACOS_INFO_PLIST_PATH.open("rb") as handle:
            info = plistlib.load(handle)
        macos_marketing_version = info["CFBundleShortVersionString"]
        macos_build_number = info["CFBundleVersion"]
    except (OSError, plistlib.InvalidFileException, KeyError, TypeError) as error:
        failures.append(f"cannot read macOS release Info.plist: {error}")
    else:
        if macos_marketing_version != current.marketing_version:
            failures.append(
                "macOS release marketing version does not match the ledger "
                f"({macos_marketing_version!r} != {current.marketing_version!r})"
            )
        if macos_build_number != str(current.build_number):
            failures.append(
                "macOS release build number does not match the ledger "
                f"({macos_build_number!r} != {str(current.build_number)!r})"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifacts",
        action="store_true",
        help="also compare current Android and macOS local package metadata",
    )
    arguments = parser.parse_args()

    try:
        entries = load_release_version_ledger()
    except LedgerError as error:
        print(f"Release version ledger failed: {error}", file=sys.stderr)
        return 1

    current = entries[-1]
    failures = source_contract_failures(current)
    if arguments.artifacts:
        failures.extend(artifact_contract_failures(current))
    if failures:
        print("Release version ledger failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    scope = "source and artifact" if arguments.artifacts else "source"
    print(
        "Release version ledger OK for "
        f"{len(entries)} entry/entries; current={current.marketing_version}"
        f"+{current.build_number}; scope={scope}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
