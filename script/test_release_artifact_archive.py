#!/usr/bin/env python3
"""Regression tests for deterministic local release evidence archives."""

from __future__ import annotations

import copy
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

import script.check_release_artifact_archive as readback_module
import script.package_release_artifacts as builder_module
from script.check_release_artifact_archive import (
    ReleaseArchiveVerificationError,
    expected_release_id,
    ledger_prefix_bytes_for_release,
    manifest_contract_for_build,
    archive_normalizations_for_build,
    parse_aapt2_apk_backup_policy as parse_readback_apk_backup_policy,
    parse_aapt2_badging as parse_readback_aapt2_badging,
    parse_bundletool_manifest as parse_readback_bundletool_manifest,
    parse_gradle_lockfile as parse_readback_gradle_lockfile,
    canonicalize_r8_line_artifact as canonicalize_readback_r8_lines,
    canonicalize_r8_resources as canonicalize_readback_r8_resources,
    canonicalize_r8_mapping_prt as canonicalize_readback_r8_prt,
    parse_canonical_json,
    require_exact_int,
    validate_canonical_r8_configuration,
    validate_member_path as validate_readback_member_path,
    verify_canonical_container,
    verify_dependency_lock_source_identity,
    verify_release_archive,
    verify_release_mode,
    verify_source_snapshot,
)
from script.package_release_artifacts import (
    ArchiveMember,
    ReleaseArchiveError,
    canonical_json_bytes,
    canonicalize_r8_configuration,
    canonicalize_r8_line_artifact as canonicalize_builder_r8_lines,
    canonicalize_r8_resources as canonicalize_builder_r8_resources,
    canonicalize_r8_mapping_prt as canonicalize_builder_r8_prt,
    member_record,
    parse_aapt2_apk_backup_policy as parse_builder_apk_backup_policy,
    parse_aapt2_badging as parse_builder_aapt2_badging,
    parse_bundletool_manifest as parse_builder_bundletool_manifest,
    parse_gradle_lockfile as parse_builder_gradle_lockfile,
    publish_archive_directory,
    resolve_macos_package_output_root,
    resolve_macos_dsym_path,
    validate_member_path,
    write_canonical_zip,
)


ENTRY_POINT_SHARE_MIME_TYPES = (
    "application/epub+zip",
    "application/haansofthwp",
    "application/hwp+zip",
    "application/json",
    "application/jsonl",
    "application/msword",
    "application/pdf",
    "application/rtf",
    "application/toml",
    "application/vnd.apple.keynote",
    "application/vnd.apple.numbers",
    "application/vnd.apple.pages",
    "application/vnd.hancom.hwpml",
    "application/vnd.hancom.hwpx",
    "application/vnd.ms-excel",
    "application/vnd.ms-excel.sheet.macroenabled.12",
    "application/vnd.ms-excel.template.macroenabled.12",
    "application/vnd.ms-powerpoint",
    "application/vnd.ms-powerpoint.presentation.macroenabled.12",
    "application/vnd.ms-powerpoint.slideshow.macroenabled.12",
    "application/vnd.ms-powerpoint.template.macroenabled.12",
    "application/vnd.ms-word.document.macroenabled.12",
    "application/vnd.ms-word.template.macroenabled.12",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
    "application/vnd.openxmlformats-officedocument.presentationml.template",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.template",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    "application/x-hwp",
    "application/x-hwpml",
    "application/x-ndjson",
    "application/x-toml",
    "application/x-webarchive",
    "application/x-yaml",
    "application/xhtml+xml",
    "application/xml",
    "application/yaml",
    "image/*",
    "text/*",
)


def expected_entry_point_topology() -> dict[str, object]:
    return {
        "activity": {
            "documentLaunchMode": "never",
            "exported": True,
            "launchMode": "singleTask",
            "name": "com.localagentbridge.android.MainActivity",
        },
        "deepLink": {
            "action": "android.intent.action.VIEW",
            "categories": [
                "android.intent.category.BROWSABLE",
                "android.intent.category.DEFAULT",
            ],
            "host": "pair",
            "scheme": "aetherlink",
        },
        "launcher": {
            "action": "android.intent.action.MAIN",
            "category": "android.intent.category.LAUNCHER",
        },
        "share": {
            "actions": [
                "android.intent.action.SEND",
                "android.intent.action.SEND_MULTIPLE",
            ],
            "category": "android.intent.category.DEFAULT",
            "mimeTypes": list(ENTRY_POINT_SHARE_MIME_TYPES),
        },
    }


def aapt2_entry_point_xmltree(
    mime_types: tuple[str, ...] = ENTRY_POINT_SHARE_MIME_TYPES,
) -> str:
    android = "http://schemas.android.com/apk/res/android:"

    def string_attribute(
        indent: str,
        name: str,
        resource_id: str,
        value: str,
    ) -> str:
        return (
            f'{indent}A: {android}{name}({resource_id})="{value}" '
            f'(Raw: "{value}")\n'
        )

    def action_filter(
        line: int,
        action: str,
        categories: tuple[str, ...],
        data: tuple[
            tuple[tuple[str, str, str], ...],
            ...,
        ] = (),
    ) -> str:
        result = f"              E: intent-filter (line={line})\n"
        result += f"                  E: action (line={line + 1})\n"
        result += string_attribute(
            "                    ",
            "name",
            "0x01010003",
            action,
        )
        next_line = line + 2
        for category in categories:
            result += f"                  E: category (line={next_line})\n"
            result += string_attribute(
                "                    ",
                "name",
                "0x01010003",
                category,
            )
            next_line += 1
        for record in data:
            result += f"                  E: data (line={next_line})\n"
            for name, resource_id, value in record:
                result += string_attribute(
                    "                    ",
                    name,
                    resource_id,
                    value,
                )
            next_line += 1
        return result

    mime_data = tuple(
        (("mimeType", "0x01010026", mime_type),)
        for mime_type in mime_types
    )
    return (
        "N: android=http://schemas.android.com/apk/res/android (line=2)\n"
        "  E: manifest (line=2)\n"
        "      E: application (line=27)\n"
        "        A: http://schemas.android.com/apk/res/android:"
        "allowBackup(0x01010280)=false\n"
        "        A: http://schemas.android.com/apk/res/android:"
        "fullBackupContent(0x010104eb)=@0x7f110000\n"
        "        A: http://schemas.android.com/apk/res/android:"
        "dataExtractionRules(0x0101063e)=@0x7f110001\n"
        "          E: activity (line=38)\n"
        + string_attribute(
            "            ",
            "name",
            "0x01010003",
            "com.localagentbridge.android.MainActivity",
        )
        + "            A: http://schemas.android.com/apk/res/android:"
        "exported(0x01010010)=true\n"
        + "            A: http://schemas.android.com/apk/res/android:"
        "launchMode(0x0101001d)=2\n"
        + "            A: http://schemas.android.com/apk/res/android:"
        "documentLaunchMode(0x01010445)=3\n"
        + action_filter(
            43,
            "android.intent.action.MAIN",
            ("android.intent.category.LAUNCHER",),
        )
        + action_filter(
            48,
            "android.intent.action.VIEW",
            (
                "android.intent.category.DEFAULT",
                "android.intent.category.BROWSABLE",
            ),
            (
                (
                    ("scheme", "0x01010027", "aetherlink"),
                    ("host", "0x01010028", "pair"),
                ),
            ),
        )
        + action_filter(
            58,
            "android.intent.action.SEND",
            ("android.intent.category.DEFAULT",),
            mime_data,
        )
        + action_filter(
            108,
            "android.intent.action.SEND_MULTIPLE",
            ("android.intent.category.DEFAULT",),
            mime_data,
        )
    )


def bundletool_entry_point_manifest(
    mime_types: tuple[str, ...] = ENTRY_POINT_SHARE_MIME_TYPES,
) -> str:
    mime_data = "".join(
        f'<data android:mimeType="{mime_type}"/>'
        for mime_type in mime_types
    )
    return (
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
        'android:versionCode="1" android:versionName="1.0.0" '
        'package="com.localagentbridge.android">'
        '<uses-sdk android:minSdkVersion="26" '
        'android:targetSdkVersion="36"/>'
        '<application android:allowBackup="false" '
        'android:dataExtractionRules="@xml/data_extraction_rules" '
        'android:fullBackupContent="@xml/backup_rules">'
        '<activity android:documentLaunchMode="3" android:exported="true" '
        'android:launchMode="2" '
        'android:name="com.localagentbridge.android.MainActivity">'
        '<intent-filter>'
        '<action android:name="android.intent.action.MAIN"/>'
        '<category android:name="android.intent.category.LAUNCHER"/>'
        '</intent-filter>'
        '<intent-filter>'
        '<action android:name="android.intent.action.VIEW"/>'
        '<category android:name="android.intent.category.DEFAULT"/>'
        '<category android:name="android.intent.category.BROWSABLE"/>'
        '<data android:host="pair" android:scheme="aetherlink"/>'
        '</intent-filter>'
        '<intent-filter>'
        '<action android:name="android.intent.action.SEND"/>'
        '<category android:name="android.intent.category.DEFAULT"/>'
        f"{mime_data}"
        '</intent-filter>'
        '<intent-filter>'
        '<action android:name="android.intent.action.SEND_MULTIPLE"/>'
        '<category android:name="android.intent.category.DEFAULT"/>'
        f"{mime_data}"
        '</intent-filter>'
        '</activity>'
        '</application>'
        '</manifest>'
    )


class ReleaseArtifactArchiveTests(unittest.TestCase):
    AAPT2_ENTRY_POINT_XMLTREE = aapt2_entry_point_xmltree()
    BUNDLETOOL_ENTRY_POINT_MANIFEST = bundletool_entry_point_manifest()
    AAPT2_BADGING = (
        "package: name='com.localagentbridge.android' versionCode='1' "
        "versionName='1.0.0' platformBuildVersionName='16'\n"
        "minSdkVersion:'26'\n"
        "targetSdkVersion:'36'\n"
        "native-code: 'arm64-v8a'\n"
    )
    AAPT2_XMLTREE = (
        "N: android=http://schemas.android.com/apk/res/android (line=2)\n"
        "  E: manifest (line=2)\n"
        "      E: application (line=27)\n"
        "        A: http://schemas.android.com/apk/res/android:"
        "allowBackup(0x01010280)=false\n"
        "        A: http://schemas.android.com/apk/res/android:"
        "fullBackupContent(0x010104eb)=@0x7f110000\n"
        "        A: http://schemas.android.com/apk/res/android:"
        "dataExtractionRules(0x0101063e)=@0x7f110001\n"
        "          E: activity (line=38)\n"
    )
    AAPT2_RESOURCES = (
        "Package name=com.localagentbridge.android id=7f\n"
        "  type xml id=11 entryCount=3\n"
        "    resource 0x7f110000 xml/backup_rules\n"
        "    resource 0x7f110001 xml/data_extraction_rules\n"
        "    resource 0x7f110002 xml/locales_config\n"
    )
    AAPT2_RESOURCES_WITH_VALUES = (
        "Package name=com.localagentbridge.android id=7f\n"
        "  type xml id=11 entryCount=3\n"
        "    resource 0x7f110000 xml/backup_rules\n"
        "      () (file) res/Qq.xml type=XML\n"
        "    resource 0x7f110001 xml/data_extraction_rules\n"
        "      () (file) res/4j.xml type=XML\n"
        "    resource 0x7f110002 xml/locales_config\n"
        "      () (file) res/Br.xml type=XML\n"
    )
    AAPT2_BACKUP_RULES_XMLTREE = (
        "E: full-backup-content (line=2)\n"
        "    E: exclude (line=3)\n"
        '      A: domain="root" (Raw: "root")\n'
        '      A: path="." (Raw: ".")\n'
        "    E: exclude (line=4)\n"
        '      A: domain="file" (Raw: "file")\n'
        '      A: path="." (Raw: ".")\n'
        "    E: exclude (line=5)\n"
        '      A: domain="database" (Raw: "database")\n'
        '      A: path="." (Raw: ".")\n'
        "    E: exclude (line=6)\n"
        '      A: domain="sharedpref" (Raw: "sharedpref")\n'
        '      A: path="." (Raw: ".")\n'
        "    E: exclude (line=7)\n"
        '      A: domain="external" (Raw: "external")\n'
        '      A: path="." (Raw: ".")\n'
    )
    AAPT2_DATA_EXTRACTION_RULES_XMLTREE = (
        "E: data-extraction-rules (line=2)\n"
        "    E: cloud-backup (line=3)\n"
        "        E: exclude (line=4)\n"
        '          A: domain="root" (Raw: "root")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=5)\n"
        '          A: domain="file" (Raw: "file")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=6)\n"
        '          A: domain="database" (Raw: "database")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=7)\n"
        '          A: domain="sharedpref" (Raw: "sharedpref")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=8)\n"
        '          A: domain="external" (Raw: "external")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=9)\n"
        '          A: domain="device_root" (Raw: "device_root")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=10)\n"
        '          A: domain="device_file" (Raw: "device_file")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=11)\n"
        '          A: domain="device_database" (Raw: "device_database")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=12)\n"
        '          A: domain="device_sharedpref" (Raw: "device_sharedpref")\n'
        '          A: path="." (Raw: ".")\n'
        "    E: device-transfer (line=14)\n"
        "        E: exclude (line=15)\n"
        '          A: domain="root" (Raw: "root")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=16)\n"
        '          A: domain="file" (Raw: "file")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=17)\n"
        '          A: domain="database" (Raw: "database")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=18)\n"
        '          A: domain="sharedpref" (Raw: "sharedpref")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=19)\n"
        '          A: domain="external" (Raw: "external")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=20)\n"
        '          A: domain="device_root" (Raw: "device_root")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=21)\n"
        '          A: domain="device_file" (Raw: "device_file")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=22)\n"
        '          A: domain="device_database" (Raw: "device_database")\n'
        '          A: path="." (Raw: ".")\n'
        "        E: exclude (line=23)\n"
        '          A: domain="device_sharedpref" (Raw: "device_sharedpref")\n'
        '          A: path="." (Raw: ".")\n'
    )
    BUNDLETOOL_MANIFEST = (
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
        'android:versionCode="1" android:versionName="1.0.0" '
        'package="com.localagentbridge.android">'
        '<uses-sdk android:minSdkVersion="26" '
        'android:targetSdkVersion="36"/>'
        '<application android:allowBackup="false" '
        'android:dataExtractionRules="@xml/data_extraction_rules" '
        'android:fullBackupContent="@xml/backup_rules"/>'
        "</manifest>"
    )
    BUNDLETOOL_VALIDATE_OUTPUT = (
        "App Bundle information\n"
        "------------\n"
        "Feature modules:\n"
        "\tFeature module: base\n"
        "\t\tFile: dex/classes.dex"
    )
    GRADLE_LOCKFILE = (
        "# This is a Gradle generated file for dependency locking.\n"
        "# Manual edits can break the build and are not advised.\n"
        "# This file is expected to be part of source control.\n"
        "com.example:alpha:1.0=releaseCompileClasspath,"
        "releaseRuntimeClasspath\n"
        "com.example:beta:2.0=releaseRuntimeClasspath\n"
        "empty=releaseAnnotationProcessorClasspath\n"
    ).encode("ascii")
    EMPTY_ONLY_GRADLE_LOCKFILE = (
        "# This is a Gradle generated file for dependency locking.\n"
        "# Manual edits can break the build and are not advised.\n"
        "# This file is expected to be part of source control.\n"
        "empty=incomingCatalogForLibs0\n"
    ).encode("ascii")

    def fixture(
        self,
    ) -> tuple[list[ArchiveMember], bytes]:
        members = [
            ArchiveMember("payload/a.txt", b"alpha\n", 0o644),
            ArchiveMember("payload/run", b"#!/bin/sh\nexit 0\n", 0o755),
        ]
        manifest = {
            "members": [member_record(member) for member in members],
            "schemaVersion": 1,
        }
        return members, canonical_json_bytes(manifest)

    def android_metadata_fixture(
        self,
        build_number: int,
    ) -> tuple[
        dict[str, object],
        bytes,
        bytes,
        bytes,
        list[bool],
        list[tuple[bool, bool]],
    ]:
        mapping = b"fixture-mapping\n"
        native = b"\x7fELFfixture-native"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as bundle:
            bundle.writestr(
                (
                    "BUNDLE-METADATA/com.android.tools.build.obfuscation/"
                    "proguard.map"
                ),
                mapping,
            )
            bundle.writestr(
                "base/lib/arm64-v8a/libfixture.so",
                native,
            )
        aab = output.getvalue()
        current = builder_module.ReleaseVersion(
            build_number=build_number,
            marketing_version="1.0.0",
            semantic_version=(1, 0, 0),
        )
        topology = expected_entry_point_topology()
        apk_requirements: list[bool] = []
        aab_requirements: list[tuple[bool, bool]] = []

        def inspect_apk_policy(
            apk_data: bytes,
            root: Path,
            *,
            entry_point_topology_required: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(apk_data, b"fixture-apk")
            apk_requirements.append(entry_point_topology_required)
            result: dict[str, object] = {
                "allowBackup": False,
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
            }
            if entry_point_topology_required:
                result["entryPointTopology"] = copy.deepcopy(topology)
            return result

        def inspect_aab(
            aab_data: bytes,
            root: Path,
            *,
            backup_policy_required: bool = False,
            entry_point_topology_required: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(aab_data, aab)
            aab_requirements.append(
                (
                    backup_policy_required,
                    entry_point_topology_required,
                )
            )
            result: dict[str, object] = {
                "allowBackup": False,
                "applicationId": "com.localagentbridge.android",
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
                "minSdk": 26,
                "targetSdk": 36,
                "versionCode": build_number,
                "versionName": "1.0.0",
            }
            if entry_point_topology_required:
                result["entryPointTopology"] = copy.deepcopy(topology)
            return result

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_metadata = root / "output-metadata.json"
            output_metadata.write_bytes(
                canonical_json_bytes(
                    {
                        "applicationId": "com.localagentbridge.android",
                        "elements": [
                            {
                                "versionCode": build_number,
                                "versionName": "1.0.0",
                            }
                        ],
                        "variantName": "release",
                    }
                )
            )
            with (
                mock.patch.object(
                    builder_module,
                    "ANDROID_APK_METADATA",
                    output_metadata,
                ),
                mock.patch.object(
                    builder_module,
                    "ANDROID_NATIVE_SYMBOL_ARCHIVE",
                    root / "missing-native-symbols.zip",
                ),
                mock.patch.object(
                    builder_module,
                    "inspect_apk_badging",
                    return_value={
                        "applicationId": "com.localagentbridge.android",
                        "minSdk": 26,
                        "nativeAbis": ["arm64-v8a"],
                        "targetSdk": 36,
                        "versionCode": build_number,
                        "versionName": "1.0.0",
                    },
                ),
                mock.patch.object(
                    builder_module,
                    "inspect_apk_backup_policy",
                    side_effect=inspect_apk_policy,
                ),
                mock.patch.object(
                    builder_module,
                    "inspect_aab_manifest",
                    side_effect=inspect_aab,
                ),
                mock.patch.object(
                    builder_module,
                    "find_llvm_readelf",
                    return_value=Path("/fixture/llvm-readelf"),
                ),
                mock.patch.object(
                    builder_module,
                    "inspect_elf",
                    return_value=("0123456789abcdef", False),
                ),
                mock.patch.object(
                    builder_module,
                    "read_stable_regular_file",
                    return_value=(native, 0o644),
                ),
            ):
                metadata = builder_module.android_metadata(
                    b"fixture-apk",
                    aab,
                    mapping,
                    current,
                )
        return (
            metadata,
            aab,
            mapping,
            native,
            apk_requirements,
            aab_requirements,
        )

    def verify_android_metadata_fixture(
        self,
        metadata: dict[str, object],
        *,
        build_number: int,
        aab: bytes,
        mapping: bytes,
        native: bytes,
        apk_topology: dict[str, object] | None = None,
        aab_topology: dict[str, object] | None = None,
    ) -> tuple[list[bool], list[tuple[bool, bool]]]:
        topology = expected_entry_point_topology()
        apk_topology = (
            copy.deepcopy(topology)
            if apk_topology is None
            else apk_topology
        )
        aab_topology = (
            copy.deepcopy(topology)
            if aab_topology is None
            else aab_topology
        )
        apk_requirements: list[bool] = []
        aab_requirements: list[tuple[bool, bool]] = []

        def inspect_apk_policy(
            apk_data: bytes,
            *,
            entry_point_topology_required: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(apk_data, b"fixture-apk")
            apk_requirements.append(entry_point_topology_required)
            result: dict[str, object] = {
                "allowBackup": False,
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
            }
            if entry_point_topology_required:
                result["entryPointTopology"] = copy.deepcopy(
                    apk_topology
                )
            return result

        def inspect_aab(
            aab_data: bytes,
            *,
            backup_policy_required: bool = False,
            entry_point_topology_required: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(aab_data, aab)
            aab_requirements.append(
                (
                    backup_policy_required,
                    entry_point_topology_required,
                )
            )
            result: dict[str, object] = {
                "allowBackup": False,
                "applicationId": "com.localagentbridge.android",
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
                "minSdk": 26,
                "targetSdk": 36,
                "versionCode": build_number,
                "versionName": "1.0.0",
            }
            if entry_point_topology_required:
                result["entryPointTopology"] = copy.deepcopy(
                    aab_topology
                )
            return result

        output_metadata = canonical_json_bytes(
            {
                "applicationId": "com.localagentbridge.android",
                "elements": [
                    {
                        "versionCode": build_number,
                        "versionName": "1.0.0",
                    }
                ],
                "variantName": "release",
            }
        )
        payload = {
            "android/apk/app-release-unsigned.apk": b"fixture-apk",
            "android/apk/output-metadata.json": output_metadata,
            "android/bundle/app-release.aab": aab,
            "android/mapping/configuration.txt": b"fixture-configuration\n",
            "android/mapping/mapping.prt": b"fixture-prt\n",
            "android/mapping/mapping.txt": mapping,
            "android/mapping/resources.txt": b"fixture-resources\n",
            "android/mapping/seeds.txt": b"fixture-seeds\n",
            "android/native-symbol-status.json": canonical_json_bytes(
                {
                    "nativeLibraries": metadata["nativeLibraries"],
                    "nativeSymbols": metadata["nativeSymbols"],
                    "schemaVersion": 1,
                }
            ),
        }
        manifest = {
            "platforms": {
                "android": copy.deepcopy(metadata),
                "macos": {},
            },
            "release": {
                "buildNumber": build_number,
                "marketingVersion": "1.0.0",
            },
        }
        with (
            mock.patch.object(
                readback_module,
                "validate_canonical_r8_configuration",
            ),
            mock.patch.object(
                readback_module,
                "canonicalize_r8_mapping_prt",
                side_effect=lambda data, label: data,
            ),
            mock.patch.object(
                readback_module,
                "canonicalize_r8_resources",
                side_effect=lambda data, label: data,
            ),
            mock.patch.object(
                readback_module,
                "canonicalize_r8_line_artifact",
                side_effect=lambda data, label: data,
            ),
            mock.patch.object(
                readback_module,
                "inspect_apk_badging",
                return_value={
                    "applicationId": "com.localagentbridge.android",
                    "minSdk": 26,
                    "nativeAbis": ["arm64-v8a"],
                    "targetSdk": 36,
                    "versionCode": build_number,
                    "versionName": "1.0.0",
                },
            ),
            mock.patch.object(
                readback_module,
                "inspect_apk_backup_policy",
                side_effect=inspect_apk_policy,
            ),
            mock.patch.object(
                readback_module,
                "inspect_aab_manifest",
                side_effect=inspect_aab,
            ),
        ):
            readback_module.verify_android_relationships(
                manifest,
                payload,
            )
        self.assertEqual(
            hashlib.sha256(native).hexdigest(),
            metadata["nativeLibraries"][0]["sha256"],
        )
        return apk_requirements, aab_requirements

    def test_macos_package_output_root_is_dedicated_and_physical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "dist").mkdir()
            expected = root / "dist/package-only"
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(
                    resolve_macos_package_output_root(root, None),
                    expected,
                )
            custom = root / "dist/release-package"
            self.assertEqual(
                resolve_macos_package_output_root(root, str(custom)),
                custom,
            )
            outside = root.parent / "outside-package"
            for configured in (
                "relative/package",
                str(root / "dist"),
                str(root / "dist/AetherLink.app"),
                str(root / "dist/LocalAgentBridge.app"),
                str(root / "dist/Other.APP"),
                str(root / "dist/bad\troot"),
                str(root / "dist/bad\vroot"),
                str(root / "dist/bad\froot"),
                str(root / "dist/bad\x7froot"),
                str(root / "dist/nested/package"),
                str(outside),
            ):
                with self.subTest(configured=configured):
                    with self.assertRaises(ReleaseArchiveError):
                        resolve_macos_package_output_root(root, configured)

            physical = root / "dist/physical"
            physical.mkdir()
            linked = root / "dist/linked"
            linked.symlink_to(physical, target_is_directory=True)
            with self.assertRaises(ReleaseArchiveError):
                resolve_macos_package_output_root(root, str(linked))

    def test_canonical_zip_is_reproducible_and_reads_back(self) -> None:
        members, manifest = self.fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.zip"
            second = root / "second.zip"
            external = root / "manifest.json"
            external.write_bytes(manifest)

            write_canonical_zip(first, manifest, members)
            write_canonical_zip(second, manifest, members)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            parsed, payload, modes = verify_canonical_container(first, external)
            self.assertEqual(parsed["schemaVersion"], 1)
            self.assertEqual(payload["payload/a.txt"], b"alpha\n")
            self.assertEqual(modes["payload/run"], 0o755)

    def test_r8_unordered_line_artifacts_are_canonicalized(self) -> None:
        source = b"zeta\nalpha\nbeta\n"
        expected = b"alpha\nbeta\nzeta\n"
        self.assertEqual(
            canonicalize_builder_r8_lines(source, "fixture"),
            expected,
        )
        self.assertEqual(
            canonicalize_readback_r8_lines(source, "fixture"),
            expected,
        )
        for invalid in (
            b"",
            b"alpha",
            b"alpha\r\n",
            b"alpha\nalpha\n",
            b"alpha\n\n",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ReleaseArchiveError):
                    canonicalize_builder_r8_lines(invalid, "fixture")
                with self.assertRaises(
                    ReleaseArchiveVerificationError
                ):
                    canonicalize_readback_r8_lines(
                        invalid,
                        "fixture",
                    )

    def test_r8_resource_reasons_normalize_to_semantic_state(self) -> None:
        first = (
            b"attr:textLocale:2130903326 reachable from "
            b"Field int[] androidx.appcompat.R$styleable.AppCompatTextView\n"
            b"anim:abc_fade_in:2130771968 is not reachable.\n"
        )
        second = (
            b"anim:abc_fade_in:2130771968 is not reachable.\n"
            b"attr:textLocale:2130903326 reachable from "
            b"Field int[] androidx.appcompat.R$styleable.TextAppearance\n"
        )
        expected = (
            b"anim:abc_fade_in:2130771968 is not reachable.\n"
            b"attr:textLocale:2130903326 is reachable.\n"
        )
        for canonicalize in (
            canonicalize_builder_r8_resources,
            canonicalize_readback_r8_resources,
        ):
            with self.subTest(canonicalize=canonicalize.__module__):
                self.assertEqual(canonicalize(first, "fixture"), expected)
                self.assertEqual(canonicalize(second, "fixture"), expected)
                self.assertEqual(canonicalize(expected, "fixture"), expected)

        duplicate = (
            b"attr:textLocale:2130903326 reachable from First\n"
            b"attr:textLocale:2130903326 reachable from Second\n"
        )
        malformed = (
            b"attr:textLocale:2130903326 reachable from \n"
        )
        for invalid in (duplicate, malformed, b"attr:textLocale:1 unknown\n"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ReleaseArchiveError):
                    canonicalize_builder_r8_resources(invalid, "fixture")
                with self.assertRaises(
                    ReleaseArchiveVerificationError
                ):
                    canonicalize_readback_r8_resources(
                        invalid,
                        "fixture",
                    )

    def test_archive_normalizations_preserve_historical_builds(self) -> None:
        self.assertNotIn(
            "android/mapping/configuration.txt:"
            "declared-extracted-file-root-markers",
            archive_normalizations_for_build(3),
        )
        self.assertIn(
            "android/mapping/resources.txt:bytewise-sorted-unique-lines",
            archive_normalizations_for_build(4),
        )
        self.assertIn(
            "android/mapping/resources.txt:"
            "semantic-reachability-sorted-unique-lines",
            archive_normalizations_for_build(5),
        )

    def test_manifest_schema_two_starts_at_build_seven(self) -> None:
        for build_number in range(1, 7):
            schema, keys = manifest_contract_for_build(build_number)
            self.assertEqual(schema, 1)
            self.assertNotIn("compliance", keys)
        schema, keys = manifest_contract_for_build(7)
        self.assertEqual(schema, 2)
        self.assertIn("compliance", keys)
        with self.assertRaises(ReleaseArchiveVerificationError):
            manifest_contract_for_build(True)

    def test_r8_configuration_roots_and_sections_are_canonicalized(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source_root = root / "source"
            gradle_root = root / "gradle"
            source_root.mkdir()
            gradle_root.mkdir()
            source_path = (
                source_root
                / "apps/android/app/build/generated/default-proguard.txt"
            )
            gradle_path = (
                gradle_root
                / "caches/transforms/example/transformed/proguard.txt"
            )

            def section(identity: bytes, path: Path, rule: bytes) -> bytes:
                encoded = os.fsencode(path)
                return (
                    b"# The proguard configuration file for the following "
                    b"section is "
                    + identity
                    + b" (extracted file: "
                    + encoded
                    + b")\n"
                    + rule
                    + b"\n# End of content from "
                    + identity
                    + b" (extracted file: "
                    + encoded
                    + b")\n"
                )

            raw = (
                section(b"Android Gradle plugin", source_path, b"-keep source")
                + section(
                    b"dependency",
                    gradle_path,
                    b"-keep dependency\r",
                )
            )
            with (
                mock.patch.object(builder_module, "ROOT", source_root),
                mock.patch.dict(
                    os.environ,
                    {"GRADLE_USER_HOME": str(gradle_root)},
                    clear=False,
                ),
            ):
                canonical = canonicalize_r8_configuration(raw, "fixture")

            self.assertNotIn(os.fsencode(source_root), canonical)
            self.assertNotIn(os.fsencode(gradle_root), canonical)
            self.assertEqual(canonical.count(b"<SOURCE_ROOT>"), 2)
            self.assertEqual(canonical.count(b"<GRADLE_USER_HOME>"), 2)
            self.assertIn(b"-keep dependency\r\n", canonical)
            validate_canonical_r8_configuration(canonical, "fixture")
            self.assertEqual(
                builder_module.ARCHIVE_NORMALIZATIONS,
                readback_module.ARCHIVE_NORMALIZATIONS,
            )

            changed_rule = raw.replace(b"-keep source", b"-keep changed")
            with (
                mock.patch.object(builder_module, "ROOT", source_root),
                mock.patch.dict(
                    os.environ,
                    {"GRADLE_USER_HOME": str(gradle_root)},
                    clear=False,
                ),
            ):
                changed = canonicalize_r8_configuration(
                    changed_rule,
                    "fixture",
                )
            self.assertNotEqual(canonical, changed)

            unknown = raw.replace(
                os.fsencode(source_path),
                b"/outside/default-proguard.txt",
            )
            with (
                mock.patch.object(builder_module, "ROOT", source_root),
                mock.patch.dict(
                    os.environ,
                    {"GRADLE_USER_HOME": str(gradle_root)},
                    clear=False,
                ),
                self.assertRaisesRegex(
                    ReleaseArchiveError,
                    "outside declared roots",
                ),
            ):
                canonicalize_r8_configuration(unknown, "fixture")

    def test_r8_configuration_readback_rejects_path_and_pair_mutations(
        self,
    ) -> None:
        canonical = (
            b"# The proguard configuration file for the following section is "
            b"source (extracted file: <SOURCE_ROOT>/rules/source.pro)\n"
            b"-keep source\n"
            b"# End of content from source "
            b"(extracted file: <SOURCE_ROOT>/rules/source.pro)\n"
            b"# The proguard configuration file for the following section is "
            b"dependency "
            b"(extracted file: <GRADLE_USER_HOME>/caches/dependency.pro)\n"
            b"-keep dependency\n"
            b"# End of content from dependency "
            b"(extracted file: <GRADLE_USER_HOME>/caches/dependency.pro)\n"
        )
        validate_canonical_r8_configuration(canonical, "fixture")
        mutations = {
            "raw_root": canonical.replace(
                b"<SOURCE_ROOT>/rules",
                b"/tmp/source/rules",
                1,
            ),
            "parent_escape": canonical.replace(
                b"<SOURCE_ROOT>/rules/source.pro",
                b"<SOURCE_ROOT>/../source.pro",
                1,
            ),
            "double_slash": canonical.replace(
                b"<SOURCE_ROOT>/rules/source.pro",
                b"<SOURCE_ROOT>//source.pro",
                1,
            ),
            "backslash": canonical.replace(
                b"<SOURCE_ROOT>/rules/source.pro",
                b"<SOURCE_ROOT>/rules\\source.pro",
                1,
            ),
            "mismatched_identity": canonical.replace(
                b"# End of content from source ",
                b"# End of content from other ",
                1,
            ),
            "mismatched_path": canonical.replace(
                b"<SOURCE_ROOT>/rules/source.pro",
                b"<SOURCE_ROOT>/rules/other.pro",
                1,
            ),
            "missing_closing": canonical.replace(
                b"# End of content from dependency "
                b"(extracted file: <GRADLE_USER_HOME>/caches/dependency.pro)\n",
                b"",
                1,
            ),
            "closing_before_opening": (
                b"# End of content from source "
                b"(extracted file: <SOURCE_ROOT>/rules/source.pro)\n"
                + canonical
            ),
            "nul": canonical.replace(b"-keep source", b"-keep\0source", 1),
        }
        for label, mutated in mutations.items():
            with self.subTest(label=label), self.assertRaises(
                ReleaseArchiveVerificationError
            ):
                validate_canonical_r8_configuration(mutated, "fixture")

    def test_external_macos_dsym_scratch_is_exact_and_physical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            scratch = root / "scratch"
            scratch.mkdir()
            with (
                mock.patch.object(
                    builder_module,
                    "REPRO_SWIFT_SCRATCH_PATH",
                    scratch,
                ),
                mock.patch.dict(
                    os.environ,
                    {"AETHERLINK_REPRO_SWIFT_SCRATCH_PATH": str(scratch)},
                    clear=False,
                ),
            ):
                self.assertEqual(
                    resolve_macos_dsym_path(),
                    scratch
                    / "arm64-apple-macosx/release/AetherLink.dSYM",
                )

            absent = root / "absent"
            with (
                mock.patch.object(
                    builder_module,
                    "REPRO_SWIFT_SCRATCH_PATH",
                    absent,
                ),
                mock.patch.dict(
                    os.environ,
                    {"AETHERLINK_REPRO_SWIFT_SCRATCH_PATH": str(absent)},
                    clear=False,
                ),
                self.assertRaisesRegex(
                    ReleaseArchiveError,
                    "cannot inspect reproducible Swift scratch",
                ),
            ):
                resolve_macos_dsym_path()

            link = root / "linked-scratch"
            link.symlink_to(scratch, target_is_directory=True)
            with (
                mock.patch.object(
                    builder_module,
                    "REPRO_SWIFT_SCRATCH_PATH",
                    link,
                ),
                mock.patch.dict(
                    os.environ,
                    {"AETHERLINK_REPRO_SWIFT_SCRATCH_PATH": str(link)},
                    clear=False,
                ),
                self.assertRaisesRegex(
                    ReleaseArchiveError,
                    "physical owner-controlled directory",
                ),
            ):
                resolve_macos_dsym_path()

    def test_r8_mapping_partition_zip_is_canonicalized(self) -> None:
        def make_zip(
            entries: list[tuple[str, bytes]],
            timestamp: tuple[int, int, int, int, int, int],
        ) -> bytes:
            output = io.BytesIO()
            with zipfile.ZipFile(
                output,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                for name, data in entries:
                    info = zipfile.ZipInfo(name, timestamp)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data)
            return output.getvalue()

        first = make_zip(
            [("zeta", b"z"), ("alpha", b"a")],
            (2025, 1, 2, 3, 4, 6),
        )
        second = make_zip(
            [("alpha", b"a"), ("zeta", b"z")],
            (2026, 7, 8, 9, 10, 12),
        )
        builder_first = canonicalize_builder_r8_prt(
            first,
            "fixture",
        )
        builder_second = canonicalize_builder_r8_prt(
            second,
            "fixture",
        )
        self.assertEqual(builder_first, builder_second)
        self.assertEqual(
            canonicalize_readback_r8_prt(first, "fixture"),
            builder_first,
        )
        self.assertEqual(
            canonicalize_readback_r8_prt(builder_first, "fixture"),
            builder_first,
        )

    def test_readback_rejects_payload_tampering(self) -> None:
        members, manifest = self.fixture()
        tampered = [
            ArchiveMember("payload/a.txt", b"tampered\n", 0o644),
            members[1],
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive.zip"
            external = root / "manifest.json"
            external.write_bytes(manifest)
            write_canonical_zip(archive, manifest, tampered)

            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "byte identity differs",
            ):
                verify_canonical_container(archive, external)

    def test_readback_rejects_noncanonical_zip_metadata(self) -> None:
        members, manifest = self.fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive.zip"
            external = root / "manifest.json"
            external.write_bytes(manifest)
            with zipfile.ZipFile(
                archive,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as output:
                output.writestr("manifest.json", manifest)
                for member in members:
                    output.writestr(member.path, member.data)

            with self.assertRaises(ReleaseArchiveVerificationError):
                verify_canonical_container(archive, external)

    def test_readback_reports_unicode_zip_member_as_a_controlled_error(self) -> None:
        manifest = canonical_json_bytes({"members": [], "schemaVersion": 1})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive.zip"
            external = root / "manifest.json"
            external.write_bytes(manifest)
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("manifest.json", manifest)
                output.writestr("payload/한글", b"not canonical")

            with self.assertRaises(ReleaseArchiveVerificationError):
                verify_canonical_container(archive, external)

    def test_readback_rejects_unsorted_or_extended_member_records(self) -> None:
        members, _ = self.fixture()
        invalid_manifests = (
            {
                "members": [
                    member_record(members[1]),
                    member_record(members[0]),
                ],
                "schemaVersion": 1,
            },
            {
                "members": [
                    {
                        **member_record(members[0]),
                        "unexpected": "field",
                    },
                    member_record(members[1]),
                ],
                "schemaVersion": 1,
            },
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, manifest_value in enumerate(invalid_manifests):
                manifest = canonical_json_bytes(manifest_value)
                archive = root / f"archive-{index}.zip"
                external = root / f"manifest-{index}.json"
                external.write_bytes(manifest)
                write_canonical_zip(archive, manifest, members)
                with self.assertRaises(ReleaseArchiveVerificationError):
                    verify_canonical_container(archive, external)

    def test_member_paths_reject_escape_absolute_unicode_and_backslash(self) -> None:
        invalid = (
            "../escape",
            "/absolute",
            "payload/../escape",
            "payload\\file",
            "payload/한글",
            "",
        )
        for path in invalid:
            with self.subTest(path=path):
                with self.assertRaises((ReleaseArchiveError, ValueError)):
                    validate_member_path(path)
                with self.assertRaises(
                    (ReleaseArchiveVerificationError, ValueError)
                ):
                    validate_readback_member_path(path)

    def test_current_source_readback_rejects_new_inventory_path(
        self,
    ) -> None:
        self.assertEqual(
            readback_module.SOURCE_REQUIRED_FILES,
            builder_module.SOURCE_REQUIRED_FILES,
        )
        self.assertEqual(
            readback_module.SOURCE_OPTIONAL_FILES,
            builder_module.SOURCE_OPTIONAL_FILES,
        )
        self.assertEqual(
            readback_module.SOURCE_ROOTS,
            builder_module.SOURCE_ROOTS,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in builder_module.SOURCE_REQUIRED_FILES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture\n")
            for relative in builder_module.SOURCE_ROOTS:
                path = root / relative / "Fixture.swift"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture\n")

            snapshot = builder_module.source_snapshot(root)
            payload = {
                "source-files.json": canonical_json_bytes(
                    {
                        "schemaVersion": 1,
                        "snapshot": snapshot,
                    }
                )
            }
            manifest = {
                "source": {
                    "fileCount": snapshot["fileCount"],
                    "head": "0" * 40,
                    "member": "source-files.json",
                    "originMain": "0" * 40,
                    "snapshotAlgorithm": snapshot["algorithm"],
                    "snapshotSha256": snapshot["sha256"],
                    "worktreeState": "dirty-content-snapshot",
                }
            }
            source_identities = verify_source_snapshot(
                manifest,
                payload,
                root,
                compare_current_source=True,
            )
            lock_path = "apps/android/app/gradle.lockfile"
            lock_size, lock_digest = source_identities[lock_path]
            verify_dependency_lock_source_identity(
                path=lock_path,
                size=lock_size,
                digest=lock_digest,
                source_identities=source_identities,
            )
            for wrong_size, wrong_digest in (
                (lock_size + 1, lock_digest),
                (lock_size, "0" * 64),
            ):
                with self.subTest(
                    wrong_size=wrong_size,
                    wrong_digest=wrong_digest,
                ):
                    with self.assertRaisesRegex(
                        ReleaseArchiveVerificationError,
                        "differs from archived source snapshot",
                    ):
                        verify_dependency_lock_source_identity(
                            path=lock_path,
                            size=wrong_size,
                            digest=wrong_digest,
                            source_identities=source_identities,
                        )

            added_source = (
                root
                / "apps/macos/OllamaBackend/Sources/NewProductionFile.swift"
            )
            added_source.write_bytes(b"new production source\n")
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "current source path set differs from archive",
            ):
                verify_source_snapshot(
                    manifest,
                    payload,
                    root,
                    compare_current_source=True,
                )

    def test_historical_ledger_prefix_is_exact_and_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "version-ledger.tsv"
            ledger_path.write_bytes(
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\n"
                b"2\t1.0.0\n"
                b"4\t1.1.0\n"
            )
            first_prefix, first_is_current = ledger_prefix_bytes_for_release(
                1,
                "1.0.0",
                ledger_path,
            )
            self.assertEqual(
                first_prefix,
                b"build_number\tmarketing_version\n1\t1.0.0\n",
            )
            self.assertFalse(first_is_current)

            current_prefix, current_is_current = (
                ledger_prefix_bytes_for_release(
                    4,
                    "1.1.0",
                    ledger_path,
                )
            )
            self.assertEqual(current_prefix, ledger_path.read_bytes())
            self.assertTrue(current_is_current)

            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "not an exact ledger entry",
            ):
                ledger_prefix_bytes_for_release(
                    3,
                    "1.0.0",
                    ledger_path,
                )

    def test_release_mode_requires_exact_current_or_historical_lane(
        self,
    ) -> None:
        verify_release_mode(
            is_current_release=True,
            require_current_release=True,
        )
        verify_release_mode(
            is_current_release=False,
            require_current_release=False,
        )
        for is_current_release, require_current_release in (
            (False, True),
            (True, False),
        ):
            with self.subTest(
                is_current_release=is_current_release,
                require_current_release=require_current_release,
            ):
                with self.assertRaises(
                    ReleaseArchiveVerificationError
                ):
                    verify_release_mode(
                        is_current_release=is_current_release,
                        require_current_release=require_current_release,
                    )

    def test_present_historical_archive_rejects_lock_source_contradiction(
        self,
    ) -> None:
        archive_id = "aetherlink-1.0.0+1-local-v1"
        source_directory = (
            readback_module.DEFAULT_OUTPUT_ROOT / archive_id
        )
        source_archive = source_directory / f"{archive_id}.zip"
        source_manifest = (
            source_directory / f"{archive_id}.manifest.json"
        )
        if not source_archive.is_file() or not source_manifest.is_file():
            self.skipTest("build 1 historical archive is not present")

        manifest, payload, modes = verify_canonical_container(
            source_archive,
            source_manifest,
        )
        mutated_manifest = copy.deepcopy(manifest)
        first_lock = mutated_manifest["dependencyLocking"]["gradle"][
            "lockFiles"
        ][0]
        first_lock["size"] = 1
        first_lock["sha256"] = "0" * 64
        manifest_bytes = canonical_json_bytes(mutated_manifest)
        members = [
            ArchiveMember(path, data, modes[path])
            for path, data in payload.items()
            if path != "manifest.json"
        ]

        with tempfile.TemporaryDirectory() as temporary:
            archive_directory = Path(temporary) / archive_id
            archive_directory.mkdir()
            archive_path = archive_directory / f"{archive_id}.zip"
            manifest_path = (
                archive_directory / f"{archive_id}.manifest.json"
            )
            checksum_path = (
                archive_directory / f"{archive_id}.zip.sha256"
            )
            write_canonical_zip(
                archive_path,
                manifest_bytes,
                members,
            )
            manifest_path.write_bytes(manifest_bytes)
            checksum_path.write_text(
                f"{hashlib.sha256(archive_path.read_bytes()).hexdigest()}"
                f"  {archive_path.name}\n",
                encoding="ascii",
            )

            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "differs from archived source snapshot",
            ):
                verify_release_archive(
                    archive_directory,
                    compare_current_source=False,
                    require_current_release=False,
                )

    def test_present_current_archive_is_not_accepted_as_historical(
        self,
    ) -> None:
        archive_directory = (
            readback_module.DEFAULT_OUTPUT_ROOT / expected_release_id()
        )
        if not archive_directory.is_dir():
            self.skipTest("current release archive is not present")
        with self.assertRaisesRegex(
            ReleaseArchiveVerificationError,
            "historical readback requires a non-current ledger entry",
        ):
            verify_release_archive(
                archive_directory,
                compare_current_source=False,
                require_current_release=False,
            )

    def test_present_build_seven_uses_frozen_historical_compliance_profile(
        self,
    ) -> None:
        archive_id = "aetherlink-1.0.0+7-local-v1"
        archive_directory = readback_module.DEFAULT_OUTPUT_ROOT / archive_id
        if not archive_directory.is_dir():
            self.skipTest("build 7 historical archive is not present")
        manifest = verify_release_archive(
            archive_directory,
            compare_current_source=False,
            require_current_release=False,
        )
        compliance = manifest["compliance"]
        self.assertNotIn("profile", compliance)
        self.assertNotIn("schemaVersion", compliance)
        self.assertEqual(compliance["spdx"]["relationshipCount"], 350)

    def test_publish_is_idempotent_and_never_overwrites_different_bytes(
        self,
    ) -> None:
        manifest = canonical_json_bytes({"members": [], "schemaVersion": 1})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            source = root / "archive.zip"
            source.write_bytes(b"first archive")

            directory, existed = publish_archive_directory(
                output,
                "aetherlink-1.0.0+1-local-v1",
                source,
                manifest,
            )
            self.assertFalse(existed)
            first_archive = (
                directory / "aetherlink-1.0.0+1-local-v1.zip"
            ).read_bytes()

            same_directory, existed = publish_archive_directory(
                output,
                "aetherlink-1.0.0+1-local-v1",
                source,
                manifest,
            )
            self.assertTrue(existed)
            self.assertEqual(same_directory, directory)

            source.write_bytes(b"different archive")
            with self.assertRaisesRegex(
                ReleaseArchiveError,
                "increment the shared build number",
            ):
                publish_archive_directory(
                    output,
                    "aetherlink-1.0.0+1-local-v1",
                    source,
                    manifest,
                )
            self.assertEqual(
                (
                    directory / "aetherlink-1.0.0+1-local-v1.zip"
                ).read_bytes(),
                first_archive,
            )

    def test_publish_requires_exact_qualified_sidecar_identities(self) -> None:
        archive_id = "aetherlink-1.0.0+1-local-v1"
        archive_name = f"{archive_id}.zip"
        manifest_name = f"{archive_id}.manifest.json"
        checksum_name = f"{archive_id}.zip.sha256"
        archive_bytes = b"qualified archive"
        manifest = canonical_json_bytes({"members": [], "schemaVersion": 1})
        checksum = (
            f"{hashlib.sha256(archive_bytes).hexdigest()}  {archive_name}\n"
        ).encode("ascii")
        expected = {
            archive_name: (
                len(archive_bytes),
                hashlib.sha256(archive_bytes).hexdigest(),
            ),
            manifest_name: (
                len(manifest),
                hashlib.sha256(manifest).hexdigest(),
            ),
            checksum_name: (
                len(checksum),
                hashlib.sha256(checksum).hexdigest(),
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            source = root / archive_name
            source.write_bytes(archive_bytes)
            directory, existed = publish_archive_directory(
                output,
                archive_id,
                source,
                manifest,
                expected_sidecars=expected,
            )
            self.assertFalse(existed)
            self.assertTrue(directory.is_dir())

        mutated = dict(expected)
        mutated[archive_name] = (len(archive_bytes), "0" * 64)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            source = root / archive_name
            source.write_bytes(archive_bytes)
            with self.assertRaisesRegex(
                ReleaseArchiveError,
                "differs from the qualified sidecar identities",
            ):
                publish_archive_directory(
                    output,
                    archive_id,
                    source,
                    manifest,
                    expected_sidecars=mutated,
                )
            self.assertFalse((output / archive_id).exists())
            self.assertEqual(list(output.iterdir()), [])

    def test_json_rejects_duplicate_keys_and_noncanonical_encoding(self) -> None:
        invalid_documents = (
            b'{"schemaVersion":1,"schemaVersion":1}\n',
            b'{ "schemaVersion":1}\n',
            b'{"schemaVersion":NaN}\n',
            b"\xef\xbb\xbf{}\n",
            b"{}\r\n",
        )
        for document in invalid_documents:
            with self.subTest(document=document):
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_canonical_json(document, "fixture")

    def test_integer_fields_reject_boolean_and_float_confusion(self) -> None:
        for value in (True, False, 1.0, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(ReleaseArchiveVerificationError):
                    require_exact_int(value, "fixture.count")
        self.assertEqual(require_exact_int(1, "fixture.count"), 1)

    def test_builder_and_readback_parse_exact_apk_badging(self) -> None:
        expected = {
            "applicationId": "com.localagentbridge.android",
            "minSdk": 26,
            "nativeAbis": ["arm64-v8a"],
            "targetSdk": 36,
            "versionCode": 1,
            "versionName": "1.0.0",
        }
        self.assertEqual(
            parse_builder_aapt2_badging(self.AAPT2_BADGING),
            expected,
        )
        self.assertEqual(
            parse_readback_aapt2_badging(self.AAPT2_BADGING),
            expected,
        )

    def test_apk_badging_parsers_reject_missing_duplicate_and_nondecimal_fields(
        self,
    ) -> None:
        invalid = (
            self.AAPT2_BADGING.replace("minSdkVersion:'26'\n", ""),
            self.AAPT2_BADGING + "targetSdkVersion:'36'\n",
            self.AAPT2_BADGING.replace("versionCode='1'", "versionCode='01'"),
            self.AAPT2_BADGING.replace(
                "native-code: 'arm64-v8a'",
                "native-code:",
            ),
        )
        for document in invalid:
            with self.subTest(document=document):
                with self.assertRaises(ReleaseArchiveError):
                    parse_builder_aapt2_badging(document)
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_readback_aapt2_badging(document)

    def test_builder_and_readback_parse_exact_apk_backup_policy(self) -> None:
        expected = {
            "allowBackup": False,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "fullBackupContent": "@xml/backup_rules",
        }
        self.assertEqual(
            parse_builder_apk_backup_policy(
                self.AAPT2_XMLTREE,
                self.AAPT2_RESOURCES,
            ),
            expected,
        )
        self.assertEqual(
            parse_readback_apk_backup_policy(
                self.AAPT2_XMLTREE,
                self.AAPT2_RESOURCES,
            ),
            expected,
        )

    def test_apk_backup_policy_parsers_reject_noncanonical_readback(
        self,
    ) -> None:
        allow_backup = (
            "        A: http://schemas.android.com/apk/res/android:"
            "allowBackup(0x01010280)=false\n"
        )
        full_backup = (
            "        A: http://schemas.android.com/apk/res/android:"
            "fullBackupContent(0x010104eb)=@0x7f110000\n"
        )
        data_extraction = (
            "        A: http://schemas.android.com/apk/res/android:"
            "dataExtractionRules(0x0101063e)=@0x7f110001\n"
        )
        invalid = (
            (self.AAPT2_XMLTREE.replace("  E: manifest (line=2)\n", ""), self.AAPT2_RESOURCES),
            (
                self.AAPT2_XMLTREE
                + "      E: application (line=40)\n",
                self.AAPT2_RESOURCES,
            ),
            (
                self.AAPT2_XMLTREE.replace(
                    "      E: application (line=27)",
                    "        E: application (line=27)",
                ),
                self.AAPT2_RESOURCES,
            ),
            (self.AAPT2_XMLTREE.replace(allow_backup, ""), self.AAPT2_RESOURCES),
            (
                self.AAPT2_XMLTREE.replace(
                    allow_backup,
                    allow_backup + allow_backup,
                ),
                self.AAPT2_RESOURCES,
            ),
            (
                self.AAPT2_XMLTREE.replace(
                    "allowBackup(0x01010280)=false",
                    "allowBackup(0x01010280)=true",
                ),
                self.AAPT2_RESOURCES,
            ),
            (self.AAPT2_XMLTREE.replace(full_backup, ""), self.AAPT2_RESOURCES),
            (self.AAPT2_XMLTREE.replace(data_extraction, ""), self.AAPT2_RESOURCES),
            (
                self.AAPT2_XMLTREE.replace(
                    "@0x7f110000",
                    "@xml/backup_rules",
                ),
                self.AAPT2_RESOURCES,
            ),
            (
                self.AAPT2_XMLTREE.replace(
                    "fullBackupContent(0x010104eb)=@0x7f110000",
                    "fullBackupContent(0x010104eb)=@0x7f110001",
                ).replace(
                    "dataExtractionRules(0x0101063e)=@0x7f110001",
                    "dataExtractionRules(0x0101063e)=@0x7f110000",
                ),
                self.AAPT2_RESOURCES,
            ),
            (
                self.AAPT2_XMLTREE.replace(
                    "dataExtractionRules(0x0101063e)=@0x7f110001",
                    "dataExtractionRules(0x0101063e)=@0x7f110000",
                ),
                self.AAPT2_RESOURCES,
            ),
            (
                self.AAPT2_XMLTREE,
                self.AAPT2_RESOURCES.replace(
                    "    resource 0x7f110000 xml/backup_rules\n",
                    "",
                ),
            ),
            (
                self.AAPT2_XMLTREE,
                self.AAPT2_RESOURCES.replace(
                    "xml/backup_rules",
                    "xml/not_backup_rules",
                ),
            ),
            (
                self.AAPT2_XMLTREE,
                self.AAPT2_RESOURCES
                + "    resource 0x7f110000 xml/backup_rules\n",
            ),
            (
                self.AAPT2_XMLTREE.replace(
                    full_backup,
                    "            " + full_backup.lstrip(),
                ),
                self.AAPT2_RESOURCES,
            ),
        )
        for xmltree, resources in invalid:
            with self.subTest(xmltree=xmltree, resources=resources):
                with self.assertRaises(ReleaseArchiveError):
                    parse_builder_apk_backup_policy(xmltree, resources)
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_readback_apk_backup_policy(xmltree, resources)

    def test_apk_backup_policy_parsers_accept_reordered_fields(self) -> None:
        lines = self.AAPT2_XMLTREE.splitlines()
        reordered = "\n".join(
            [
                *lines[:3],
                lines[5],
                lines[3],
                lines[4],
                *lines[6:],
            ]
        )
        resource_lines = self.AAPT2_RESOURCES.splitlines()
        reordered_resources = "\n".join(
            [
                *resource_lines[:2],
                resource_lines[3],
                resource_lines[2],
                *resource_lines[4:],
            ]
        )
        expected = {
            "allowBackup": False,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "fullBackupContent": "@xml/backup_rules",
        }
        self.assertEqual(
            parse_builder_apk_backup_policy(
                reordered,
                reordered_resources,
            ),
            expected,
        )
        self.assertEqual(
            parse_readback_apk_backup_policy(
                reordered,
                reordered_resources,
            ),
            expected,
        )

    def test_apk_backup_policy_inspectors_use_exact_dumps_and_cleanup(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        expected = {
            "allowBackup": False,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "entryPointTopology": expected_entry_point_topology(),
            "fullBackupContent": "@xml/backup_rules",
        }
        for module, error_type in modules:
            temporary_paths: list[Path] = []
            commands: list[list[str]] = []

            def fake_dump(command: list[str], root: Path) -> str:
                commands.append(list(command))
                temporary_path = Path(command[-1])
                self.assertEqual(
                    temporary_path.read_bytes(),
                    b"fixture-apk",
                )
                temporary_paths.append(temporary_path)
                if command[2] == "xmltree":
                    file_name = command[4]
                    if file_name == "AndroidManifest.xml":
                        return self.AAPT2_ENTRY_POINT_XMLTREE
                    if file_name == "res/Qq.xml":
                        return self.AAPT2_BACKUP_RULES_XMLTREE
                    if file_name == "res/4j.xml":
                        return self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE
                    self.fail(f"unexpected aapt2 XML file {file_name!r}")
                if "--no-values" in command:
                    return self.AAPT2_RESOURCES
                return self.AAPT2_RESOURCES_WITH_VALUES

            with (
                mock.patch.object(
                    module,
                    "find_android_build_tool",
                    return_value=Path("/fixture/aapt2"),
                ),
                mock.patch.object(
                    module,
                    "run_aapt2_dump",
                    side_effect=fake_dump,
                ),
            ):
                self.assertEqual(
                    module.inspect_apk_backup_policy(
                        b"fixture-apk",
                        entry_point_topology_required=True,
                    ),
                    expected,
                )
            self.assertEqual(
                [
                    (
                        command[2],
                        command[4] if command[2] == "xmltree" else (
                            "no-values"
                            if "--no-values" in command
                            else "values"
                        ),
                    )
                    for command in commands
                ],
                [
                    ("xmltree", "AndroidManifest.xml"),
                    ("resources", "no-values"),
                    ("resources", "values"),
                    ("xmltree", "res/Qq.xml"),
                    ("xmltree", "res/4j.xml"),
                ],
            )
            self.assertEqual(len(set(temporary_paths)), 1)
            self.assertTrue(
                all(not path.exists() for path in temporary_paths)
            )

            for failing_stage in (
                "manifest",
                "resources-no-values",
                "resources-values",
                "backup-rules",
                "data-extraction-rules",
            ):
                failed_paths: list[Path] = []

                def fail_dump(command: list[str], root: Path) -> str:
                    failed_paths.append(Path(command[-1]))
                    if command[2] == "xmltree":
                        file_name = command[4]
                        stage = {
                            "AndroidManifest.xml": "manifest",
                            "res/Qq.xml": "backup-rules",
                            "res/4j.xml": "data-extraction-rules",
                        }[file_name]
                        output = {
                            "AndroidManifest.xml": self.AAPT2_XMLTREE,
                            "res/Qq.xml": (
                                self.AAPT2_BACKUP_RULES_XMLTREE
                            ),
                            "res/4j.xml": (
                                self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE
                            ),
                        }[file_name]
                    elif "--no-values" in command:
                        stage = "resources-no-values"
                        output = self.AAPT2_RESOURCES
                    else:
                        stage = "resources-values"
                        output = self.AAPT2_RESOURCES_WITH_VALUES
                    if stage == failing_stage:
                        raise error_type("fixture aapt2 failure")
                    return output

                with (
                    self.subTest(
                        module=module.__name__,
                        failing_stage=failing_stage,
                    ),
                    mock.patch.object(
                        module,
                        "find_android_build_tool",
                        return_value=Path("/fixture/aapt2"),
                    ),
                    mock.patch.object(
                        module,
                        "run_aapt2_dump",
                        side_effect=fail_dump,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.inspect_apk_backup_policy(b"fixture-apk")
                self.assertTrue(failed_paths)
                self.assertTrue(
                    all(not path.exists() for path in failed_paths)
                )

    def test_packaged_backup_policy_body_parsers_fail_closed(self) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        expected_paths = {
            "backup_rules": "res/Qq.xml",
            "data_extraction_rules": "res/4j.xml",
        }
        for module, error_type in modules:
            with self.subTest(module=module.__name__):
                self.assertEqual(
                    module.parse_aapt2_xml_resource_paths(
                        self.AAPT2_RESOURCES_WITH_VALUES
                    ),
                    expected_paths,
                )
                module.validate_aapt2_backup_policy_xmltrees(
                    self.AAPT2_BACKUP_RULES_XMLTREE,
                    self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE,
                )

            invalid_resources = (
                self.AAPT2_RESOURCES_WITH_VALUES.replace(
                    "      () (file) res/Qq.xml type=XML\n",
                    "",
                ),
                self.AAPT2_RESOURCES_WITH_VALUES.replace(
                    "res/4j.xml",
                    "res/Qq.xml",
                ),
                self.AAPT2_RESOURCES_WITH_VALUES
                + (
                    "    resource 0x7f110003 xml/backup_rules\n"
                    "      () (file) res/Xx.xml type=XML\n"
                ),
            )
            for resources in invalid_resources:
                with self.subTest(
                    module=module.__name__,
                    resources=resources,
                ), self.assertRaises(error_type):
                    module.parse_aapt2_xml_resource_paths(resources)

            invalid_trees = (
                (
                    self.AAPT2_BACKUP_RULES_XMLTREE.replace(
                        'domain="external" (Raw: "external")',
                        'domain="file" (Raw: "file")',
                    ),
                    self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE,
                ),
                (
                    self.AAPT2_BACKUP_RULES_XMLTREE.replace(
                        'path="." (Raw: ".")',
                        'path="cache" (Raw: "cache")',
                        1,
                    ),
                    self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE,
                ),
                (
                    self.AAPT2_BACKUP_RULES_XMLTREE
                    + "    E: include (line=8)\n",
                    self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE,
                ),
                (
                    self.AAPT2_BACKUP_RULES_XMLTREE,
                    self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE.replace(
                        "    E: device-transfer (line=14)\n",
                        "",
                    ),
                ),
                (
                    self.AAPT2_BACKUP_RULES_XMLTREE,
                    self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE.replace(
                        'domain="device_sharedpref" '
                        '(Raw: "device_sharedpref")\n',
                        "",
                        1,
                    ),
                ),
            )
            for backup_rules, data_extraction_rules in invalid_trees:
                with self.subTest(
                    module=module.__name__,
                    backup_rules=backup_rules,
                    data_extraction_rules=data_extraction_rules,
                ), self.assertRaises(error_type):
                    module.validate_aapt2_backup_policy_xmltrees(
                        backup_rules,
                        data_extraction_rules,
                    )

    def test_aapt2_dump_runner_fails_closed(self) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        command = ["/fixture/aapt2", "dump", "resources", "fixture.apk"]
        for module, error_type in modules:
            with mock.patch.object(
                module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="fixture",
                    stderr="unexpected",
                ),
            ), self.assertRaisesRegex(error_type, "unexpected stderr"):
                module.run_aapt2_dump(command)
            with mock.patch.object(
                module.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(
                    command,
                    module.AAPT2_TIMEOUT_SECONDS,
                ),
            ), self.assertRaisesRegex(error_type, "timed out"):
                module.run_aapt2_dump(command)
            with mock.patch.object(
                module.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, command),
            ), self.assertRaisesRegex(error_type, "readback failed"):
                module.run_aapt2_dump(command)

    def test_builder_and_readback_parse_exact_bundletool_manifest(self) -> None:
        expected = {
            "allowBackup": False,
            "applicationId": "com.localagentbridge.android",
            "dataExtractionRules": "@xml/data_extraction_rules",
            "fullBackupContent": "@xml/backup_rules",
            "minSdk": 26,
            "targetSdk": 36,
            "versionCode": 1,
            "versionName": "1.0.0",
        }
        self.assertEqual(
            parse_builder_bundletool_manifest(
                self.BUNDLETOOL_MANIFEST,
                backup_policy_required=True,
            ),
            expected,
        )
        self.assertEqual(
            parse_readback_bundletool_manifest(
                self.BUNDLETOOL_MANIFEST,
                backup_policy_required=True,
            ),
            expected,
        )
        historical = self.BUNDLETOOL_MANIFEST.replace(
            ' android:dataExtractionRules="@xml/data_extraction_rules"'
            ' android:fullBackupContent="@xml/backup_rules"',
            "",
        )
        expected_historical = {
            key: value
            for key, value in expected.items()
            if key not in {
                "allowBackup",
                "dataExtractionRules",
                "fullBackupContent",
            }
        }
        self.assertEqual(
            parse_builder_bundletool_manifest(historical),
            expected_historical,
        )
        self.assertEqual(
            parse_readback_bundletool_manifest(historical),
            expected_historical,
        )

    def test_builder_and_readback_parse_exact_entry_point_topology(
        self,
    ) -> None:
        expected = expected_entry_point_topology()
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        for module, error_type in modules:
            with self.subTest(module=module.__name__):
                self.assertEqual(
                    module.parse_aapt2_entry_point_topology(
                        self.AAPT2_ENTRY_POINT_XMLTREE
                    ),
                    expected,
                )
                parsed = module.parse_bundletool_manifest(
                    self.BUNDLETOOL_ENTRY_POINT_MANIFEST,
                    backup_policy_required=True,
                    entry_point_topology_required=True,
                )
                self.assertEqual(
                    parsed["entryPointTopology"],
                    expected,
                )
                historical = module.parse_bundletool_manifest(
                    self.BUNDLETOOL_ENTRY_POINT_MANIFEST,
                    backup_policy_required=True,
                )
                self.assertNotIn("entryPointTopology", historical)
                apk_with_dependency_activity = (
                    self.AAPT2_ENTRY_POINT_XMLTREE
                    + "          E: activity (line=200)\n"
                    + "            A: "
                    + "http://schemas.android.com/apk/res/android:"
                    + 'name(0x01010003)="com.example.OtherActivity" '
                    + '(Raw: "com.example.OtherActivity")\n'
                )
                self.assertEqual(
                    module.parse_aapt2_entry_point_topology(
                        apk_with_dependency_activity
                    ),
                    expected,
                )
                aab_with_dependency_activity = (
                    self.BUNDLETOOL_ENTRY_POINT_MANIFEST.replace(
                        "</application>",
                        '<activity android:exported="false" '
                        'android:name="com.example.OtherActivity"/>'
                        "</application>",
                    )
                )
                self.assertEqual(
                    module.parse_bundletool_manifest(
                        aab_with_dependency_activity,
                        backup_policy_required=True,
                        entry_point_topology_required=True,
                    )["entryPointTopology"],
                    expected,
                )
                with self.assertRaises(error_type):
                    module.parse_bundletool_manifest(
                        self.BUNDLETOOL_ENTRY_POINT_MANIFEST,
                        backup_policy_required=True,
                        entry_point_topology_required=1,
                    )

    def test_entry_point_topology_parsers_canonicalize_mime_order(
        self,
    ) -> None:
        expected = expected_entry_point_topology()
        reversed_mime_types = tuple(
            reversed(ENTRY_POINT_SHARE_MIME_TYPES)
        )
        aapt2 = aapt2_entry_point_xmltree(reversed_mime_types)
        bundletool = bundletool_entry_point_manifest(
            reversed_mime_types
        )
        for module in (builder_module, readback_module):
            with self.subTest(module=module.__name__):
                self.assertEqual(
                    module.parse_aapt2_entry_point_topology(aapt2),
                    expected,
                )
                self.assertEqual(
                    module.parse_bundletool_manifest(
                        bundletool,
                        backup_policy_required=True,
                        entry_point_topology_required=True,
                    )["entryPointTopology"],
                    expected,
                )

    def test_aapt2_entry_point_topology_mutations_fail_closed(
        self,
    ) -> None:
        base = self.AAPT2_ENTRY_POINT_XMLTREE
        invalid = (
            base.replace(
                "exported(0x01010010)=true",
                "exported(0x01010010)=false",
            ),
            base.replace(
                "http://schemas.android.com/apk/res/android:"
                "exported(0x01010010)=true",
                "exported(0x01010010)=true",
            ),
            base.replace(
                "exported(0x01010010)=true\n",
                "exported(0x01010010)=true\n"
                "            A: "
                "http://schemas.android.com/apk/res/android:"
                "exported(0x01010010)=true\n",
            ),
            base.replace(
                "            A: http://schemas.android.com/apk/res/android:"
                "launchMode(0x0101001d)=2\n",
                "",
            ),
            base.replace(
                "documentLaunchMode(0x01010445)=3",
                "documentLaunchMode(0x01010445)=0",
            ),
            base.replace(
                "android.intent.action.MAIN",
                "android.intent.action.UNKNOWN",
            ),
            base.replace(
                "android.intent.category.LAUNCHER",
                "android.intent.category.DEFAULT",
            ),
            base.replace(
                '"pair" (Raw: "pair")',
                '"other" (Raw: "other")',
            ),
            base.replace(
                '"application/pdf" (Raw: "application/pdf")',
                '"application/zip" (Raw: "application/zip")',
                1,
            ),
            base.replace(
                '"application/pdf" (Raw: "application/pdf")',
                '"text/*" (Raw: "text/*")',
                1,
            ),
            base.replace(
                '(Raw: "pair")',
                '(Raw: "other")',
                1,
            ),
            base
            + "          E: activity-alias (line=200)\n",
            base
            + "              E: intent-filter (line=200)\n"
            + "                  E: action (line=201)\n"
            + "                    A: "
            + "http://schemas.android.com/apk/res/android:"
            + 'name(0x01010003)="android.intent.action.UNKNOWN" '
            + '(Raw: "android.intent.action.UNKNOWN")\n',
        )
        for module, error_type in (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        ):
            for document in invalid:
                with (
                    self.subTest(
                        module=module.__name__,
                        document=document,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.parse_aapt2_entry_point_topology(document)

    def test_bundletool_entry_point_topology_mutations_fail_closed(
        self,
    ) -> None:
        base = self.BUNDLETOOL_ENTRY_POINT_MANIFEST
        invalid = (
            base.replace(
                'android:exported="true"',
                'android:exported="false"',
            ),
            base.replace(
                'android:exported="true"',
                'exported="true"',
            ),
            base.replace(
                'android:exported="true"',
                'android:exported="true" android:exported="true"',
            ),
            base.replace(' android:launchMode="2"', ""),
            base.replace(
                'android:documentLaunchMode="3"',
                'android:documentLaunchMode="0"',
            ),
            base.replace(
                "android.intent.action.MAIN",
                "android.intent.action.UNKNOWN",
            ),
            base.replace(
                "android.intent.category.LAUNCHER",
                "android.intent.category.DEFAULT",
            ),
            base.replace(
                'android:host="pair"',
                'android:host="other"',
            ),
            base.replace(
                '<data android:mimeType="application/pdf"/>',
                "",
                1,
            ),
            base.replace(
                '<data android:mimeType="application/pdf"/>',
                '<data android:mimeType="text/*"/>',
                1,
            ),
            base.replace(
                '<data android:host="pair" android:scheme="aetherlink"/>',
                '<data android:host="pair" android:path="/" '
                'android:scheme="aetherlink"/>',
            ),
            base.replace(
                "</application>",
                '<activity-alias android:name="Alias" '
                'android:targetActivity="'
                'com.localagentbridge.android.MainActivity"/>'
                "</application>",
            ),
            base.replace(
                "</activity>",
                '<intent-filter><action android:name="'
                'android.intent.action.UNKNOWN"/></intent-filter>'
                "</activity>",
            ),
            base.replace(
                "</application>",
                '<activity android:documentLaunchMode="3" '
                'android:exported="true" android:launchMode="2" '
                'android:name="com.localagentbridge.android.MainActivity"/>'
                "</application>",
            ),
        )
        for module, error_type in (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        ):
            for document in invalid:
                with (
                    self.subTest(
                        module=module.__name__,
                        document=document,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.parse_bundletool_manifest(
                        document,
                        backup_policy_required=True,
                        entry_point_topology_required=True,
                    )

    def test_entry_point_topology_claim_is_exact_typed_and_build_gated(
        self,
    ) -> None:
        expected = expected_entry_point_topology()
        self.assertEqual(
            readback_module.verify_android_entry_point_topology_claim(
                copy.deepcopy(expected)
            ),
            expected,
        )
        invalid: list[object] = []
        wrong_exported = copy.deepcopy(expected)
        wrong_exported["activity"]["exported"] = 1
        invalid.append(wrong_exported)
        tuple_mime_types = copy.deepcopy(expected)
        tuple_mime_types["share"]["mimeTypes"] = tuple(
            tuple_mime_types["share"]["mimeTypes"]
        )
        invalid.append(tuple_mime_types)
        unsorted_mime_types = copy.deepcopy(expected)
        unsorted_mime_types["share"]["mimeTypes"] = list(
            reversed(unsorted_mime_types["share"]["mimeTypes"])
        )
        invalid.append(unsorted_mime_types)
        extra_key = copy.deepcopy(expected)
        extra_key["launcher"]["data"] = []
        invalid.append(extra_key)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(
                ReleaseArchiveVerificationError
            ):
                readback_module.verify_android_entry_point_topology_claim(
                    value
                )

        self.assertNotIn(
            "entryPointTopology",
            readback_module.expected_android_manifest_keys(22),
        )
        self.assertIn(
            "entryPointTopology",
            readback_module.expected_android_manifest_keys(23),
        )
        self.assertEqual(
            builder_module.ANDROID_ENTRY_POINT_TOPOLOGY_BUILD,
            23,
        )
        self.assertEqual(
            readback_module.ANDROID_ENTRY_POINT_TOPOLOGY_BUILD,
            23,
        )

    def test_android_metadata_and_readback_wire_build22_and_build23(
        self,
    ) -> None:
        for build_number in (22, 23):
            with self.subTest(build_number=build_number):
                (
                    metadata,
                    aab,
                    mapping,
                    native,
                    builder_apk_requirements,
                    builder_aab_requirements,
                ) = self.android_metadata_fixture(build_number)
                topology_required = build_number >= 23
                self.assertEqual(
                    set(metadata),
                    readback_module.expected_android_manifest_keys(
                        build_number
                    ),
                )
                self.assertEqual(
                    "entryPointTopology" in metadata,
                    topology_required,
                )
                self.assertEqual(
                    builder_apk_requirements,
                    [topology_required],
                )
                self.assertEqual(
                    builder_aab_requirements,
                    [(True, topology_required)],
                )
                expected_bundle_fields = [
                    *builder_module.BASE_BUNDLE_MANIFEST_VERIFIED_FIELDS,
                    *builder_module
                    .BACKUP_POLICY_BUNDLE_MANIFEST_VERIFIED_FIELDS,
                    *(
                        builder_module
                        .ENTRY_POINT_TOPOLOGY_MANIFEST_VERIFIED_FIELDS
                        if topology_required
                        else ()
                    ),
                ]
                self.assertEqual(
                    metadata["bundleManifestReadback"][
                        "verifiedFields"
                    ],
                    expected_bundle_fields,
                )
                expected_apk_fields = [
                    *builder_module
                    .BACKUP_POLICY_APK_MANIFEST_VERIFIED_FIELDS,
                    *(
                        builder_module
                        .ENTRY_POINT_TOPOLOGY_MANIFEST_VERIFIED_FIELDS
                        if topology_required
                        else ()
                    ),
                ]
                self.assertEqual(
                    metadata["apkManifestReadback"]["verifiedFields"],
                    expected_apk_fields,
                )
                (
                    readback_apk_requirements,
                    readback_aab_requirements,
                ) = self.verify_android_metadata_fixture(
                    metadata,
                    build_number=build_number,
                    aab=aab,
                    mapping=mapping,
                    native=native,
                )
                self.assertEqual(
                    readback_apk_requirements,
                    [topology_required],
                )
                self.assertEqual(
                    readback_aab_requirements,
                    [(True, topology_required)],
                )

    def test_android_readback_rejects_build23_topology_wiring_drift(
        self,
    ) -> None:
        (
            metadata,
            aab,
            mapping,
            native,
            _,
            _,
        ) = self.android_metadata_fixture(23)

        def changed_topology() -> dict[str, object]:
            value = expected_entry_point_topology()
            value["deepLink"]["host"] = "other"
            return value

        changed_claim = copy.deepcopy(metadata)
        changed_claim["entryPointTopology"] = changed_topology()
        with self.assertRaises(ReleaseArchiveVerificationError):
            self.verify_android_metadata_fixture(
                changed_claim,
                build_number=23,
                aab=aab,
                mapping=mapping,
                native=native,
            )

        with self.assertRaises(ReleaseArchiveVerificationError):
            self.verify_android_metadata_fixture(
                metadata,
                build_number=23,
                aab=aab,
                mapping=mapping,
                native=native,
                apk_topology=changed_topology(),
            )

        with self.assertRaises(ReleaseArchiveVerificationError):
            self.verify_android_metadata_fixture(
                metadata,
                build_number=23,
                aab=aab,
                mapping=mapping,
                native=native,
                aab_topology=changed_topology(),
            )

        for readback_key in (
            "bundleManifestReadback",
            "apkManifestReadback",
        ):
            missing_verified_field = copy.deepcopy(metadata)
            missing_verified_field[readback_key][
                "verifiedFields"
            ].remove("entryPointTopology")
            with (
                self.subTest(readback_key=readback_key),
                self.assertRaises(ReleaseArchiveVerificationError),
            ):
                self.verify_android_metadata_fixture(
                    missing_verified_field,
                    build_number=23,
                    aab=aab,
                    mapping=mapping,
                    native=native,
                )

        missing_claim = copy.deepcopy(metadata)
        del missing_claim["entryPointTopology"]
        with self.assertRaises(ReleaseArchiveVerificationError):
            self.verify_android_metadata_fixture(
                missing_claim,
                build_number=23,
                aab=aab,
                mapping=mapping,
                native=native,
            )

        (
            historical_metadata,
            historical_aab,
            historical_mapping,
            historical_native,
            _,
            _,
        ) = self.android_metadata_fixture(22)
        historical_metadata["entryPointTopology"] = (
            expected_entry_point_topology()
        )
        with self.assertRaises(ReleaseArchiveVerificationError):
            self.verify_android_metadata_fixture(
                historical_metadata,
                build_number=22,
                aab=historical_aab,
                mapping=historical_mapping,
                native=historical_native,
            )

    def test_bundletool_manifest_parsers_reject_noncanonical_identity(
        self,
    ) -> None:
        invalid = (
            self.BUNDLETOOL_MANIFEST.replace(
                '<uses-sdk android:minSdkVersion="26" '
                'android:targetSdkVersion="36"/>',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                "</manifest>",
                '<uses-sdk android:minSdkVersion="26" '
                'android:targetSdkVersion="36"/></manifest>',
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                'android:versionCode="1"',
                'android:versionCode="01"',
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                ' android:versionName="1.0.0"',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                ' package="com.localagentbridge.android"',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                'android:minSdkVersion="26"',
                'android:minSdkVersion="026"',
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                ' android:targetSdkVersion="36"',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                '<application android:allowBackup="false" '
                'android:dataExtractionRules="@xml/data_extraction_rules" '
                'android:fullBackupContent="@xml/backup_rules"/>',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                "</manifest>",
                '<application android:allowBackup="false" '
                'android:dataExtractionRules="@xml/data_extraction_rules" '
                'android:fullBackupContent="@xml/backup_rules"/>'
                "</manifest>",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                'android:allowBackup="false"',
                'android:allowBackup="true"',
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                ' android:dataExtractionRules="@xml/data_extraction_rules"',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                ' android:fullBackupContent="@xml/backup_rules"',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                "@xml/data_extraction_rules",
                "@xml/unexpected_rules",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                "@xml/backup_rules",
                "@xml/unexpected_rules",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                "<manifest ",
                "<application ",
            ).replace("</manifest>", "</application>"),
            self.BUNDLETOOL_MANIFEST.removesuffix("</manifest>"),
        )
        for document in invalid:
            with self.subTest(document=document):
                with self.assertRaises(ReleaseArchiveError):
                    parse_builder_bundletool_manifest(
                        document,
                        backup_policy_required=True,
                    )
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_readback_bundletool_manifest(
                        document,
                        backup_policy_required=True,
                    )
        with self.assertRaises(ReleaseArchiveError):
            parse_builder_bundletool_manifest(
                self.BUNDLETOOL_MANIFEST,
                backup_policy_required=1,
            )
        with self.assertRaises(ReleaseArchiveVerificationError):
            parse_readback_bundletool_manifest(
                self.BUNDLETOOL_MANIFEST,
                backup_policy_required=1,
            )

    def test_bundletool_validate_output_requires_one_base_module(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        invalid = (
            "",
            self.BUNDLETOOL_VALIDATE_OUTPUT.replace(
                "App Bundle information",
                "Bundle information",
            ),
            self.BUNDLETOOL_VALIDATE_OUTPUT.replace(
                "\tFeature module: base\n",
                "",
            ),
            self.BUNDLETOOL_VALIDATE_OUTPUT.replace(
                "\tFeature module: base\n",
                "\tFeature module: base\n\tFeature module: feature\n",
            ),
            self.BUNDLETOOL_VALIDATE_OUTPUT.replace(
                "\tFeature module: base\n",
                "\tFeature module: base\n\tFeature module: base\n",
            ),
        )
        for module, error_type in modules:
            module.validate_bundletool_validation_output(
                self.BUNDLETOOL_VALIDATE_OUTPUT
            )
            for output in invalid:
                with self.subTest(
                    module=module.__name__,
                    output=output,
                ), self.assertRaises(error_type):
                    module.validate_bundletool_validation_output(output)

    def test_bundle_structure_validation_claim_starts_at_build_11(
        self,
    ) -> None:
        claim = {
            "member": "android/bundle/app-release.aab",
            "moduleSet": ["base"],
            "status": "passed",
            "tool": "bundletool validate",
        }
        self.assertIsNone(
            builder_module.bundle_structure_validation_claim_for_build(10)
        )
        self.assertEqual(
            builder_module.bundle_structure_validation_claim_for_build(11),
            claim,
        )
        self.assertNotIn(
            "bundleStructureValidation",
            readback_module.expected_android_manifest_keys(10),
        )
        self.assertIn(
            "bundleStructureValidation",
            readback_module.expected_android_manifest_keys(11),
        )
        self.assertNotIn(
            "apkManifestReadback",
            readback_module.expected_android_manifest_keys(14),
        )
        self.assertIn(
            "apkManifestReadback",
            readback_module.expected_android_manifest_keys(15),
        )
        readback_module.verify_bundle_structure_validation_claim(
            {"bundleStructureValidation": claim},
            11,
        )
        readback_module.verify_bundle_structure_validation_claim({}, 10)

        invalid_build_numbers = (True, 0, -1)
        for build_number in invalid_build_numbers:
            with self.subTest(
                implementation="builder",
                build_number=build_number,
            ), self.assertRaises(ReleaseArchiveError):
                builder_module.bundle_structure_validation_claim_for_build(
                    build_number
                )
            with self.subTest(
                implementation="readback-keys",
                build_number=build_number,
            ), self.assertRaises(ReleaseArchiveVerificationError):
                readback_module.expected_android_manifest_keys(build_number)
            with self.subTest(
                implementation="readback-claim",
                build_number=build_number,
            ), self.assertRaises(ReleaseArchiveVerificationError):
                readback_module.verify_bundle_structure_validation_claim(
                    {},
                    build_number,
                )

        with self.assertRaisesRegex(
            ReleaseArchiveVerificationError,
            "future validation claim",
        ):
            readback_module.verify_bundle_structure_validation_claim(
                {"bundleStructureValidation": claim},
                10,
            )

        for label, invalid_claim in (
            (
                "missing",
                {},
            ),
            (
                "extra",
                {
                    **claim,
                    "unexpected": "value",
                },
            ),
            (
                "status-type",
                {
                    **claim,
                    "status": True,
                },
            ),
            (
                "module-set-type",
                {
                    **claim,
                    "moduleSet": ("base",),
                },
            ),
            (
                "module-set-value",
                {
                    **claim,
                    "moduleSet": ["base", "feature"],
                },
            ),
            (
                "tool",
                {
                    **claim,
                    "tool": "bundletool dump manifest",
                },
            ),
        ):
            with self.subTest(label=label), self.assertRaises(
                ReleaseArchiveVerificationError
            ):
                readback_module.verify_bundle_structure_validation_claim(
                    (
                        invalid_claim
                        if label == "missing"
                        else {"bundleStructureValidation": invalid_claim}
                    ),
                    11,
                )

    def test_bundletool_runtime_classpath_is_closed_and_version_pinned(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundletool = root / "bundletool-1.18.3.jar"
            dependency = root / "dependency.jar"
            wrong_bundletool = root / "bundletool-1.18.2.jar"
            non_jar = root / "dependency.txt"
            for path in (
                bundletool,
                dependency,
                wrong_bundletool,
                non_jar,
            ):
                path.write_bytes(b"fixture")
            valid = os.pathsep.join((str(bundletool), str(dependency)))
            invalid = (
                "",
                f"noise\nAETHERLINK_BUNDLETOOL_CLASSPATH={valid}",
                os.pathsep.join((str(bundletool), str(bundletool))),
                os.pathsep.join((str(wrong_bundletool), str(dependency))),
                os.pathsep.join((str(bundletool), str(non_jar))),
            )
            for module, error_type in modules:
                module.bundletool_runtime_classpath.cache_clear()
                with mock.patch.object(
                    module,
                    "run_text",
                    return_value=(
                        "AETHERLINK_BUNDLETOOL_CLASSPATH=" + valid
                    ),
                ) as run_text:
                    self.assertEqual(
                        module.bundletool_runtime_classpath(root),
                        valid,
                    )
                    command = run_text.call_args.args[0]
                    self.assertEqual(command[1:5], [
                        "--offline",
                        "--no-daemon",
                        "--console=plain",
                        "--quiet",
                    ])
                    self.assertEqual(
                        command[-1],
                        "printBundletoolRuntimeClasspath",
                    )
                for output in invalid:
                    module.bundletool_runtime_classpath.cache_clear()
                    with self.subTest(
                        module=module.__name__,
                        output=output,
                    ), mock.patch.object(
                        module,
                        "run_text",
                        return_value=output,
                    ):
                        with self.assertRaises(error_type):
                            module.bundletool_runtime_classpath(root)
                module.bundletool_runtime_classpath.cache_clear()

    def test_bundletool_version_is_exact_and_aab_temp_file_is_removed(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        expected_policy = {
            "allowBackup": False,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "fullBackupContent": "@xml/backup_rules",
        }
        for module, error_type in modules:
            with mock.patch.object(
                module,
                "run_bundletool",
                return_value="1.18.3",
            ):
                self.assertEqual(module.bundletool_version(), "1.18.3")
            for version in ("1.18.2", "1.18.3\nunexpected", ""):
                with self.subTest(
                    module=module.__name__,
                    version=version,
                ), mock.patch.object(
                    module,
                    "run_bundletool",
                    return_value=version,
                ):
                    with self.assertRaises(error_type):
                        module.bundletool_version()

            temporary_paths: list[Path] = []
            commands: list[list[str]] = []

            def fake_run(
                arguments: list[str],
                *,
                root: Path,
            ) -> str:
                commands.append(list(arguments))
                path_argument = (
                    arguments[1]
                    if arguments[0] == "validate"
                    else arguments[2]
                )
                bundle_path = Path(
                    path_argument.removeprefix("--bundle=")
                )
                self.assertEqual(bundle_path.read_bytes(), b"fixture-aab")
                temporary_paths.append(bundle_path)
                if arguments[0] == "validate":
                    self.assertEqual(
                        arguments,
                        ["validate", f"--bundle={bundle_path}"],
                    )
                    return self.BUNDLETOOL_VALIDATE_OUTPUT
                self.assertEqual(
                    arguments,
                    [
                        "dump",
                        "manifest",
                        f"--bundle={bundle_path}",
                        "--module=base",
                    ],
                )
                return self.BUNDLETOOL_MANIFEST

            inspected_policy_paths: list[Path] = []

            def fake_policy_readback(
                path: Path,
                root: Path,
            ) -> dict[str, object]:
                self.assertEqual(path.read_bytes(), b"fixture-aab")
                inspected_policy_paths.append(path)
                return expected_policy

            with (
                mock.patch.object(
                    module,
                    "run_bundletool",
                    side_effect=fake_run,
                ),
                mock.patch.object(
                    module,
                    "inspect_aab_backup_policy",
                    side_effect=fake_policy_readback,
                ),
            ):
                self.assertEqual(
                    module.inspect_aab_manifest(
                        b"fixture-aab",
                        backup_policy_required=True,
                    ),
                    {
                        "allowBackup": False,
                        "applicationId": "com.localagentbridge.android",
                        "dataExtractionRules": (
                            "@xml/data_extraction_rules"
                        ),
                        "fullBackupContent": "@xml/backup_rules",
                        "minSdk": 26,
                        "targetSdk": 36,
                        "versionCode": 1,
                        "versionName": "1.0.0",
                    },
                )
            self.assertTrue(temporary_paths)
            self.assertEqual(
                inspected_policy_paths,
                [temporary_paths[0]],
            )
            self.assertEqual(
                [command[0] for command in commands],
                ["validate", "dump"],
            )
            self.assertEqual(len(set(temporary_paths)), 1)
            self.assertTrue(
                all(not path.exists() for path in temporary_paths)
            )

            for failing_stage in ("validate", "dump"):
                failed_paths: list[Path] = []

                def fail_run(
                    arguments: list[str],
                    *,
                    root: Path,
                ) -> str:
                    path_argument = (
                        arguments[1]
                        if arguments[0] == "validate"
                        else arguments[2]
                    )
                    failed_paths.append(
                        Path(path_argument.removeprefix("--bundle="))
                    )
                    if arguments[0] == failing_stage:
                        raise error_type("fixture bundletool failure")
                    if arguments[0] == "validate":
                        return self.BUNDLETOOL_VALIDATE_OUTPUT
                    return self.BUNDLETOOL_MANIFEST

                with self.subTest(
                    module=module.__name__,
                    failing_stage=failing_stage,
                ), mock.patch.object(
                    module,
                    "run_bundletool",
                    side_effect=fail_run,
                ):
                    with self.assertRaises(error_type):
                        module.inspect_aab_manifest(b"fixture-aab")
                self.assertTrue(failed_paths)
                self.assertTrue(
                    all(not path.exists() for path in failed_paths)
                )

            with (
                mock.patch.object(
                    module,
                    "run_bundletool",
                    side_effect=fake_run,
                ),
                mock.patch.object(
                    module,
                    "inspect_aab_backup_policy",
                    return_value={
                        **expected_policy,
                        "fullBackupContent": "@xml/not_backup_rules",
                    },
                ),
                self.assertRaisesRegex(
                    error_type,
                    "differs from the bundle manifest",
                ),
            ):
                module.inspect_aab_manifest(
                    b"fixture-aab",
                    backup_policy_required=True,
                )

    def test_bundletool_subprocess_failure_and_stderr_fail_closed(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        arguments = ["validate", "--bundle=/tmp/fixture.aab"]
        self.assertEqual(
            builder_module.BUNDLETOOL_TIMEOUT_SECONDS,
            readback_module.BUNDLETOOL_TIMEOUT_SECONDS,
        )
        for module, error_type in modules:
            with (
                mock.patch.object(
                    module,
                    "java_executable",
                    return_value=Path("/fixture/java"),
                ),
                mock.patch.object(
                    module,
                    "bundletool_runtime_classpath",
                    return_value="/fixture/classpath",
                ),
                mock.patch.object(
                    module.subprocess,
                    "run",
                    side_effect=subprocess.TimeoutExpired(
                        ["/fixture/java", "/fixture/classpath"],
                        module.BUNDLETOOL_TIMEOUT_SECONDS,
                    ),
                ) as timed_run,
            ):
                with self.assertRaises(error_type) as captured:
                    module.run_bundletool(arguments)
            self.assertIn("timed out after 60 seconds", str(captured.exception))
            self.assertIn("validate", str(captured.exception))
            self.assertNotIn("/fixture/classpath", str(captured.exception))
            self.assertEqual(
                timed_run.call_args.kwargs["timeout"],
                module.BUNDLETOOL_TIMEOUT_SECONDS,
            )

            with (
                mock.patch.object(
                    module,
                    "java_executable",
                    return_value=Path("/fixture/java"),
                ),
                mock.patch.object(
                    module,
                    "bundletool_runtime_classpath",
                    return_value="/fixture/classpath",
                ),
                mock.patch.object(
                    module.subprocess,
                    "run",
                    side_effect=subprocess.CalledProcessError(
                        1,
                        ["bundletool", *arguments],
                        stderr="invalid bundle fixture",
                    ),
                ),
            ):
                with self.assertRaises(error_type) as captured:
                    module.run_bundletool(arguments)
            self.assertIn("validate", str(captured.exception))
            self.assertIn("invalid bundle fixture", str(captured.exception))
            self.assertNotIn("/fixture/classpath", str(captured.exception))

            completed = subprocess.CompletedProcess(
                ["bundletool", *arguments],
                0,
                stdout=self.BUNDLETOOL_VALIDATE_OUTPUT,
                stderr="unexpected warning",
            )
            with (
                mock.patch.object(
                    module,
                    "java_executable",
                    return_value=Path("/fixture/java"),
                ),
                mock.patch.object(
                    module,
                    "bundletool_runtime_classpath",
                    return_value="/fixture/classpath",
                ),
                mock.patch.object(
                    module.subprocess,
                    "run",
                    return_value=completed,
                ) as run,
                self.assertRaisesRegex(
                    error_type,
                    "standard-error",
                ),
            ):
                module.run_bundletool(arguments)
            command = run.call_args.args[0]
            self.assertEqual(
                command[-2:],
                arguments,
            )
            self.assertEqual(
                run.call_args.kwargs["timeout"],
                module.BUNDLETOOL_TIMEOUT_SECONDS,
            )

    def test_builder_and_readback_parse_exact_gradle_lockfile(self) -> None:
        expected = {
            "configurationCount": 3,
            "emptyConfigurationCount": 1,
            "moduleCount": 2,
        }
        self.assertEqual(
            parse_builder_gradle_lockfile(
                self.GRADLE_LOCKFILE,
                "fixture",
            ),
            expected,
        )
        self.assertEqual(
            parse_readback_gradle_lockfile(
                self.GRADLE_LOCKFILE,
                "fixture",
            ),
            expected,
        )

    def test_gradle_lockfile_parsers_reject_noncanonical_shapes(
        self,
    ) -> None:
        invalid = (
            self.GRADLE_LOCKFILE.rstrip(b"\n"),
            self.GRADLE_LOCKFILE.replace(b"\n", b"\r\n"),
            self.GRADLE_LOCKFILE.replace(
                b"com.example:alpha:1.0=releaseCompileClasspath,"
                b"releaseRuntimeClasspath\n"
                b"com.example:beta:2.0=releaseRuntimeClasspath\n",
                b"com.example:beta:2.0=releaseRuntimeClasspath\n"
                b"com.example:alpha:1.0=releaseCompileClasspath,"
                b"releaseRuntimeClasspath\n",
            ),
            self.GRADLE_LOCKFILE.replace(
                b"com.example:beta:2.0=releaseRuntimeClasspath",
                b"com.example:alpha:1.0=releaseRuntimeClasspath",
            ),
            self.GRADLE_LOCKFILE.replace(
                b"releaseCompileClasspath,releaseRuntimeClasspath",
                b"releaseRuntimeClasspath,releaseCompileClasspath",
            ),
            self.GRADLE_LOCKFILE.replace(
                b"empty=releaseAnnotationProcessorClasspath\n",
                b"empty=releaseAnnotationProcessorClasspath\n"
                b"com.example:zeta:3.0=releaseRuntimeClasspath\n",
            ),
            self.GRADLE_LOCKFILE.replace(
                b"com.example:beta:2.0=releaseRuntimeClasspath",
                b"com.example:beta:2.0=",
            ),
            b"\xef\xbb\xbf" + self.GRADLE_LOCKFILE,
            self.EMPTY_ONLY_GRADLE_LOCKFILE.replace(
                b"empty=incomingCatalogForLibs0\n",
                b"empty=\n",
            ),
        )
        for document in invalid:
            with self.subTest(document=document):
                with self.assertRaises(ReleaseArchiveError):
                    parse_builder_gradle_lockfile(document, "fixture")
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_readback_gradle_lockfile(document, "fixture")

    def test_gradle_lockfile_parsers_accept_empty_only_configuration(
        self,
    ) -> None:
        expected = {
            "configurationCount": 1,
            "emptyConfigurationCount": 1,
            "moduleCount": 0,
        }
        self.assertEqual(
            parse_builder_gradle_lockfile(
                self.EMPTY_ONLY_GRADLE_LOCKFILE,
                "fixture",
            ),
            expected,
        )
        self.assertEqual(
            parse_readback_gradle_lockfile(
                self.EMPTY_ONLY_GRADLE_LOCKFILE,
                "fixture",
            ),
            expected,
        )

    def test_dependency_lock_inventory_tracks_gradle_and_swiftpm_state(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        for module, error_type in modules:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for relative in module.GRADLE_LOCK_PATHS:
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(self.GRADLE_LOCKFILE)
                with mock.patch.object(
                    module,
                    "swift_package_dump",
                    return_value={
                        "dependencies": [],
                        "name": "AetherLink",
                    },
                ):
                    metadata = module.dependency_locking_metadata(root)
                    self.assertEqual(
                        len(metadata["gradle"]["lockFiles"]),
                        len(module.GRADLE_LOCK_PATHS),
                    )
                    self.assertEqual(
                        metadata["gradle"]["ignoredDependencies"],
                        [
                            "org.jetbrains.kotlin:"
                            "kotlin-stdlib-common"
                        ],
                    )
                    self.assertEqual(
                        metadata["swiftPackageManager"],
                        {
                            "externalDependencyCount": 0,
                            "packageResolved": None,
                            "status": (
                                "not-applicable-no-external-dependencies"
                            ),
                        },
                    )

                    (root / "Package.resolved").write_bytes(b"stale\n")
                    with self.assertRaises(error_type):
                        module.dependency_locking_metadata(root)

                (root / "Package.resolved").unlink()
                with mock.patch.object(
                    module,
                    "swift_package_dump",
                    return_value={
                        "dependencies": [{"sourceControl": []}],
                        "name": "AetherLink",
                    },
                ):
                    with self.assertRaises(error_type):
                        module.dependency_locking_metadata(root)
                    resolved = root / "Package.resolved"
                    resolved.write_bytes(b'{"version":3}\n')
                    metadata = module.dependency_locking_metadata(root)
                    self.assertEqual(
                        metadata["swiftPackageManager"][
                            "externalDependencyCount"
                        ],
                        1,
                    )
                    self.assertEqual(
                        metadata["swiftPackageManager"]["packageResolved"][
                            "path"
                        ],
                        "Package.resolved",
                    )

    def test_release_script_requires_strict_read_only_dependency_locks(
        self,
    ) -> None:
        release_script = (
            Path(__file__).resolve().parents[1]
            / "script/build_release_artifacts.sh"
        ).read_text(encoding="utf-8")
        root_build = (
            Path(__file__).resolve().parents[1]
            / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "-PaetherlinkStrictReleaseDependencyLocks=true",
            release_script,
        )
        self.assertIn(
            'RELEASE_MACOS_PACKAGE_OUTPUT_ROOT="$ROOT_DIR/dist/release-package"',
            release_script,
        )
        self.assertIn(
            'export AETHERLINK_PACKAGE_OUTPUT_ROOT="$RELEASE_MACOS_PACKAGE_OUTPUT_ROOT"',
            release_script,
        )
        self.assertNotIn(
            'RELEASE_MACOS_PACKAGE_OUTPUT_ROOT="$ROOT_DIR/dist"',
            release_script,
        )
        self.assertNotIn("--write-locks", release_script)
        for clean_task in (
            ":app:clean",
            ":core:pairing:clean",
            ":core:protocol:clean",
            ":core:transport:clean",
        ):
            self.assertIn(clean_task, release_script)
        self.assertIn("lockAllConfigurations()", root_build)
        self.assertIn("lockMode.set(LockMode.STRICT)", root_build)
        self.assertIn(
            "resolutionStrategy.activateDependencyLocking()",
            root_build,
        )
        self.assertIn(
            '"org.jetbrains.kotlin:kotlin-stdlib-common"',
            root_build,
        )
        self.assertIn('"buildscript-gradle.lockfile"', root_build)
        self.assertIn('"settings-gradle.lockfile"', root_build)


if __name__ == "__main__":
    unittest.main()
