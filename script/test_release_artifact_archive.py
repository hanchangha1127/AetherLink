#!/usr/bin/env python3
"""Regression tests for deterministic local release evidence archives."""

from __future__ import annotations

import copy
import hashlib
import io
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import tempfile
import unittest
from unittest import mock
import warnings
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


def expected_application_shell() -> dict[str, object]:
    return {
        "manifestResources": {
            "icon": "@mipmap/ic_launcher",
            "label": "@string/app_name",
            "localeConfig": "@xml/locales_config",
            "roundIcon": "@mipmap/ic_launcher_round",
            "theme": "@style/AppTheme",
        },
        "localeConfigLocales": [
            "en",
            "ko",
            "ja",
            "zh-CN",
            "fr",
        ],
        "localizedString": {
            "resource": "@string/status_title",
            "values": {
                "default": "Pairing & Connection",
                "en": "Pairing & Connection",
                "fr": "Jumelage et connexion",
                "ja": "ペアリングと接続",
                "ko": "페어링 및 연결",
                "zh-CN": "配对与连接",
            },
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


def aapt2_application_shell_xmltree() -> str:
    android = "http://schemas.android.com/apk/res/android:"
    return (
        "N: android=http://schemas.android.com/apk/res/android (line=2)\n"
        "  E: manifest (line=2)\n"
        "      E: application (line=27)\n"
        f"        A: {android}icon(0x01010002)=@0x7f0e0000\n"
        f"        A: {android}label(0x01010001)=@0x7f120000\n"
        f"        A: {android}localeConfig(0x01010654)=@0x7f110002\n"
        f"        A: {android}roundIcon(0x0101052c)=@0x7f0e0001\n"
        f"        A: {android}theme(0x01010000)=@0x7f130000\n"
    )


def bundletool_application_shell_manifest() -> str:
    return (
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
        'android:versionCode="1" android:versionName="1.0.0" '
        'package="com.localagentbridge.android">'
        '<uses-sdk android:minSdkVersion="26" '
        'android:targetSdkVersion="36"/>'
        '<application android:allowBackup="false" '
        'android:dataExtractionRules="@xml/data_extraction_rules" '
        'android:fullBackupContent="@xml/backup_rules" '
        'android:icon="@mipmap/ic_launcher" '
        'android:label="@string/app_name" '
        'android:localeConfig="@xml/locales_config" '
        'android:roundIcon="@mipmap/ic_launcher_round" '
        'android:theme="@style/AppTheme"/>'
        "</manifest>"
    )


class ReleaseArtifactArchiveTests(unittest.TestCase):
    FIXTURE_R8_MAPPING_SHA256 = (
        "a06cdac1eb82c67f7e9650ca4d9b92caff4e85b4ef8e5803ed01c45fd7f8a615"
    )
    FIXTURE_R8_MAPPING_PRT_LOGICAL_SHA256 = (
        "26e7744547ccac092db58c3d6f234e851f9511a56d04a64d307f7007659d68c8"
    )
    FIXTURE_SDK_DEPENDENCIES_SHA256 = (
        "5137d605c2ac08c0a877a3fe689cf046bed147f82fe3689d915bf6d8bcf8ad1f"
    )
    FIXTURE_APK_BASELINE_PROFILE_SHA256 = (
        "ed6be521fa2abc15b040335bf532c7925121ecaaa280678390a8f0204a0468b2"
    )
    FIXTURE_APK_BASELINE_PROFILE_METADATA_SHA256 = (
        "3c57e8ecf0ea89efef57df5e1ef70be6ca197ee934e5cf7948b299a3339992a5"
    )
    FIXTURE_API31_DM_PROFILE_SHA256 = (
        "905ee8a9e450ac9e4a85b3f22401e0fad71bcda7439ceca4a6bd9ae20ba973df"
    )
    FIXTURE_SDK_DEPENDENCIES_PROTOBUF_SHA256 = (
        "4b7b7d5edfe5d28948eb601ea70c1b7516d28ad737ae3924484fd5aeba816ca8"
    )
    FIXTURE_DEX_SHA256 = (
        "d39e091649939bd0712ae83aa7169e154e5c4b1361c3245f8e0097fb53e50ba3"
    )
    FIXTURE_MACOS_SOURCE_SUMMARY = {
        "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
        "fileCount": 3,
        "sha256": "b" * 64,
    }

    AAPT2_ENTRY_POINT_XMLTREE = aapt2_entry_point_xmltree()
    BUNDLETOOL_ENTRY_POINT_MANIFEST = bundletool_entry_point_manifest()
    AAPT2_APPLICATION_SHELL_XMLTREE = (
        aapt2_application_shell_xmltree()
    )
    BUNDLETOOL_APPLICATION_SHELL_MANIFEST = (
        bundletool_application_shell_manifest()
    )
    AAPT2_APPLICATION_SHELL_RESOURCES = (
        "Package name=com.localagentbridge.android id=7f\n"
        "  type mipmap id=0e entryCount=2\n"
        "    resource 0x7f0e0000 mipmap/ic_launcher\n"
        "    resource 0x7f0e0001 mipmap/ic_launcher_round\n"
        "  type string id=12 entryCount=2\n"
        "    resource 0x7f120000 string/app_name\n"
        "    resource 0x7f120001 string/status_title\n"
        "  type style id=13 entryCount=1\n"
        "    resource 0x7f130000 style/AppTheme\n"
        "  type xml id=11 entryCount=3\n"
        "    resource 0x7f110000 xml/backup_rules\n"
        "    resource 0x7f110001 xml/data_extraction_rules\n"
        "    resource 0x7f110002 xml/locales_config\n"
    )
    AAPT2_LOCALE_CONFIG_XMLTREE = (
        "N: android=http://schemas.android.com/apk/res/android (line=2)\n"
        "  E: locale-config (line=2)\n"
        "      E: locale (line=3)\n"
        "        A: http://schemas.android.com/apk/res/android:"
        'name(0x01010003)="en" (Raw: "en")\n'
        "      E: locale (line=4)\n"
        "        A: http://schemas.android.com/apk/res/android:"
        'name(0x01010003)="ko" (Raw: "ko")\n'
        "      E: locale (line=5)\n"
        "        A: http://schemas.android.com/apk/res/android:"
        'name(0x01010003)="ja" (Raw: "ja")\n'
        "      E: locale (line=6)\n"
        "        A: http://schemas.android.com/apk/res/android:"
        'name(0x01010003)="zh-CN" (Raw: "zh-CN")\n'
        "      E: locale (line=7)\n"
        "        A: http://schemas.android.com/apk/res/android:"
        'name(0x01010003)="fr" (Raw: "fr")\n'
    )
    AAPT2_LOCALIZED_STRING_RESOURCES = (
        "Package name=com.localagentbridge.android id=7f\n"
        "  type string id=12 entryCount=2\n"
        "    resource 0x7f120000 string/app_name\n"
        '      () "AetherLink"\n'
        "    resource 0x7f120001 string/status_title\n"
        '      () "Pairing & Connection"\n'
        '      (en) "Pairing & Connection"\n'
        '      (fr) "Jumelage et connexion"\n'
        '      (ja) "ペアリングと接続"\n'
        '      (ko) "페어링 및 연결"\n'
        '      (zh-rCN) "配对与连接"\n'
    )
    BUNDLETOOL_LOCALIZED_STRING = (
        "Package 'com.localagentbridge.android':\n"
        "0x7f120001 - string/status_title\n"
        '\t(default) - [STR] "Pairing & Connection"\n'
        '\tlocale: "en" - [STR] "Pairing & Connection"\n'
        '\tlocale: "fr" - [STR] "Jumelage et connexion"\n'
        '\tlocale: "ja" - [STR] "ペアリングと接続"\n'
        '\tlocale: "ko" - [STR] "페어링 및 연결"\n'
        '\tlocale: "zh-CN" - [STR] "配对与连接"\n'
    )
    BUNDLETOOL_LANGUAGE_SPLIT_CONFIG = (
        '{"optimizations":{"splitsConfig":{"splitDimension":'
        '[{"negate":true,"value":"LANGUAGE"}]}}}'
    )
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
    AAPT2_COMPILED_APPLICATION_SHELL_XMLTREE = (
        AAPT2_ENTRY_POINT_XMLTREE.replace(
            "        A: http://schemas.android.com/apk/res/android:"
            "dataExtractionRules(0x0101063e)=@0x7f110001\n",
            "        A: http://schemas.android.com/apk/res/android:"
            "dataExtractionRules(0x0101063e)=@0x7f110001\n"
            "        A: http://schemas.android.com/apk/res/android:"
            "icon(0x01010002)=@0x7f0e0000\n"
            "        A: http://schemas.android.com/apk/res/android:"
            "label(0x01010001)=@0x7f120000\n"
            "        A: http://schemas.android.com/apk/res/android:"
            "localeConfig(0x01010654)=@0x7f110002\n"
            "        A: http://schemas.android.com/apk/res/android:"
            "roundIcon(0x0101052c)=@0x7f0e0001\n"
            "        A: http://schemas.android.com/apk/res/android:"
            "theme(0x01010000)=@0x7f130000\n",
        )
    )
    AAPT2_APPLICATION_SHELL_RESOURCES_WITH_VALUES = (
        AAPT2_RESOURCES_WITH_VALUES
        + "  type string id=12 entryCount=2\n"
        + "    resource 0x7f120000 string/app_name\n"
        + '      () "AetherLink"\n'
        + "    resource 0x7f120001 string/status_title\n"
        + '      () "Pairing & Connection"\n'
        + '      (en) "Pairing & Connection"\n'
        + '      (fr) "Jumelage et connexion"\n'
        + '      (ja) "ペアリングと接続"\n'
        + '      (ko) "페어링 및 연결"\n'
        + '      (zh-rCN) "配对与连接"\n'
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

    @staticmethod
    def corrupt_zip_member_payload(path: Path, member_name: str) -> None:
        data = bytearray(path.read_bytes())
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            info = archive.getinfo(member_name)
        header_offset = info.header_offset
        if data[header_offset : header_offset + 4] != b"PK\x03\x04":
            raise AssertionError("fixture ZIP local header is missing")
        name_length = int.from_bytes(
            data[header_offset + 26 : header_offset + 28],
            "little",
        )
        extra_length = int.from_bytes(
            data[header_offset + 28 : header_offset + 30],
            "little",
        )
        payload_offset = header_offset + 30 + name_length + extra_length
        if info.compress_size < 1:
            raise AssertionError("fixture ZIP member payload is empty")
        data[payload_offset + info.compress_size // 2] ^= 0x01
        path.write_bytes(data)

    @staticmethod
    def write_fixture_zip_members(
        path: Path,
        members: list[tuple[str, bytes]],
    ) -> None:
        output = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(
                output,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                for name, payload in members:
                    archive.writestr(name, payload)
        path.write_bytes(output.getvalue())

    @classmethod
    def replace_fixture_zip_member(
        cls,
        path: Path,
        member_name: str,
        payload: bytes,
    ) -> None:
        with zipfile.ZipFile(path, "r") as archive:
            members = [
                (
                    info.filename,
                    payload
                    if info.filename == member_name
                    else archive.read(info),
                )
                for info in archive.infolist()
            ]
        if sum(name == member_name for name, _ in members) != 1:
            raise AssertionError("fixture ZIP replacement target differs")
        cls.write_fixture_zip_members(path, members)

    def write_android_release_build_output_fixture(
        self,
        root: Path,
        *,
        aab_mapping: bytes | None = None,
        aab_abi: str = "arm64-v8a",
        embedded_symbol: bytes | None = None,
        embedded_symbol_name: str | None = None,
        sdk_coordinate: tuple[str, str, str] = (
            "com.example",
            "fixture",
            "1.0",
        ),
    ) -> dict[str, object]:
        build_number = 24
        marketing_version = "1.0.0"
        mapping_body = (
            b"fixture.Source -> a:\n"
            b"    void run() -> a\n"
        )
        mapping_id = hashlib.sha256(b"fixture-map-id\n").hexdigest().encode(
            "ascii"
        )
        mapping_body_hash = hashlib.sha256(mapping_body).hexdigest().encode(
            "ascii"
        )
        mapping_header = (
            b"# compiler: R8\n"
            b"# compiler_version: 9.2.14\n"
            b"# min_api: 26\n"
            b"# common_typos_disable\n"
            b'# {"id":"com.android.tools.r8.mapping","version":"2.2"}\n'
            b"# pg_map_id: "
            + mapping_id
            + b"\n# pg_map_hash: SHA-256 "
            + mapping_body_hash
            + b"\n"
        )
        mapping = mapping_header + mapping_body
        mapping_prt_header = mapping_header.replace(
            b"# pg_map_hash: SHA-256 " + mapping_body_hash,
            b"# pg_map_hash: SHA-256 " + mapping_id,
        )
        partition_names = b"a"
        package_names = b"\nfixture\n"
        mapping_prt_tail = (
            (2).to_bytes(2, "big")
            + (0).to_bytes(4, "big")
            + len(mapping_prt_header).to_bytes(2, "big")
            + mapping_prt_header
            + (1).to_bytes(2, "big")
            + len(package_names).to_bytes(4, "big")
            + package_names
        )
        mapping_prt_metadata = (
            b"\xaa\xa8"
            + (1).to_bytes(2, "big")
            + (3).to_bytes(2, "big")
            + b"2.2"
            + len(partition_names).to_bytes(4, "big")
            + partition_names
            + len(mapping_prt_tail).to_bytes(4, "big")
            + mapping_prt_tail
        )
        native = b"\x7fELFfixture-native"
        baseline_profile = b"pro\x00010\x00fixture-baseline-profile\n"
        converted_baseline_profile = (
            b"pro\x00015\x00fixture-converted-baseline-profile\n"
        )
        baseline_profile_metadata = (
            b"prm\x00002\x00fixture-baseline-profile-metadata\n"
        )
        ledger = root / "release/version-ledger.tsv"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            "build_number\tmarketing_version\n24\t1.0.0\n",
            encoding="ascii",
        )
        lock_data = (
            "# This is a Gradle generated file for dependency locking.\n"
            "# Manual edits can break the build and are not advised.\n"
            "# This file is expected to be part of source control.\n"
            "com.example:fixture:1.0=releaseRuntimeClasspath\n"
            "empty=releaseAnnotationProcessorClasspath\n"
        ).encode("ascii")
        for relative in readback_module.GRADLE_LOCK_PATHS:
            lock_path = root / relative
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_bytes(lock_data)

        apk_directory = (
            root
            / "apps/android/app/build/outputs/apk/release"
        )
        apk_directory.mkdir(parents=True)
        apk_path = apk_directory / "app-release-unsigned.apk"
        apk_output = io.BytesIO()
        with zipfile.ZipFile(
            apk_output,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as apk:
            apk.writestr("classes.dex", b"dex\nfixture\n")
            apk.writestr("lib/arm64-v8a/libfixture.so", native)
            apk.writestr(
                "assets/dexopt/baseline.prof",
                baseline_profile,
            )
            apk.writestr(
                "assets/dexopt/baseline.profm",
                baseline_profile_metadata,
            )
        apk_path.write_bytes(apk_output.getvalue())
        baseline_paths = (
            "baselineProfiles/1/app-release-unsigned.dm",
            "baselineProfiles/0/app-release-unsigned.dm",
        )
        for index, relative in enumerate(baseline_paths):
            profile_path = apk_directory / relative
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_output = io.BytesIO()
            with zipfile.ZipFile(
                profile_output,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as profile:
                profile.writestr(
                    "primary.prof",
                    baseline_profile
                    if index == 0
                    else converted_baseline_profile,
                )
                profile.writestr(
                    "primary.profm",
                    baseline_profile_metadata,
                )
            profile_path.write_bytes(profile_output.getvalue())
        metadata_path = apk_directory / "output-metadata.json"
        metadata_path.write_bytes(
            canonical_json_bytes(
                {
                    "applicationId": "com.localagentbridge.android",
                    "artifactType": {
                        "kind": "Directory",
                        "type": "APK",
                    },
                    "baselineProfiles": [
                        {
                            "baselineProfiles": [baseline_paths[0]],
                            "maxApi": 30,
                            "minApi": 28,
                        },
                        {
                            "baselineProfiles": [baseline_paths[1]],
                            "maxApi": 2_147_483_647,
                            "minApi": 31,
                        },
                    ],
                    "elementType": "File",
                    "elements": [
                        {
                            "attributes": [],
                            "filters": [],
                            "outputFile": "app-release-unsigned.apk",
                            "type": "SINGLE",
                            "versionCode": build_number,
                            "versionName": marketing_version,
                        }
                    ],
                    "minSdkVersionForDexing": 26,
                    "variantName": "release",
                    "version": 3,
                }
            )
        )

        mapping_directory = (
            root
            / "apps/android/app/build/outputs/mapping/release"
        )
        mapping_directory.mkdir(parents=True)
        mapping_prt = io.BytesIO()
        with zipfile.ZipFile(mapping_prt, "w") as archive:
            archive.writestr("a", mapping_body)
            archive.writestr("METADATA", mapping_prt_metadata)
        mapping_outputs = {
            "configuration.txt": b"-dontobfuscate\r\n",
            "mapping.prt": mapping_prt.getvalue(),
            "mapping.txt": mapping,
            "resources.txt": b"fixture:type:1 reachable from root\n",
            "seeds.txt": b"zeta\nalpha\n",
            "usage.txt": b"fixture.Unused\n",
        }
        for name, data in mapping_outputs.items():
            (mapping_directory / name).write_bytes(data)

        aab_directory = (
            root
            / "apps/android/app/build/outputs/bundle/release"
        )
        aab_directory.mkdir(parents=True)
        aab_path = aab_directory / "app-release.aab"
        aab_output = io.BytesIO()
        with zipfile.ZipFile(aab_output, "w") as bundle:
            bundle.writestr(
                "base/dex/classes.dex",
                b"dex\nfixture\n",
                compress_type=zipfile.ZIP_DEFLATED,
            )
            bundle.writestr(
                (
                    "BUNDLE-METADATA/com.android.tools.build.obfuscation/"
                    "proguard.map"
                ),
                mapping if aab_mapping is None else aab_mapping,
            )
            bundle.writestr(
                f"base/lib/{aab_abi}/libfixture.so",
                native,
            )
            bundle.writestr(
                (
                    "BUNDLE-METADATA/com.android.tools.build.profiles/"
                    "baseline.prof"
                ),
                baseline_profile,
            )
            bundle.writestr(
                (
                    "BUNDLE-METADATA/com.android.tools.build.profiles/"
                    "baseline.profm"
                ),
                baseline_profile_metadata,
            )
            bundle.writestr(
                (
                    "BUNDLE-METADATA/com.android.tools.build.libraries/"
                    "dependencies.pb"
                ),
                b"fixture-sdk-dependencies-protobuf\n",
            )
            if embedded_symbol is not None:
                bundle.writestr(
                    (
                        "BUNDLE-METADATA/com.android.tools.build.debugsymbols/"
                        + (
                            embedded_symbol_name
                            if embedded_symbol_name is not None
                            else f"{aab_abi}/libfixture.so.sym"
                        )
                    ),
                    embedded_symbol,
                )
        aab_path.write_bytes(aab_output.getvalue())

        group, artifact, version = sdk_coordinate
        sdk_directory = (
            root
            / "apps/android/app/build/outputs/sdk-dependencies/release"
        )
        sdk_directory.mkdir(parents=True)
        sdk_path = sdk_directory / "sdkDependencies.txt"
        sdk_path.write_text(
            "# List of SDK dependencies of this app, this information is also "
            "included in an encrypted form in the APK.\n"
            "# For more information visit: "
            "https://d.android.com/r/tools/dependency-metadata\n\n"
            "library {\n"
            "  maven_library {\n"
            f'    groupId: "{group}"\n'
            f'    artifactId: "{artifact}"\n'
            f'    version: "{version}"\n'
            "  }\n"
            "  digests {\n"
            '    sha256: "0123456789abcdef0123456789abcdef"\n'
            "  }\n"
            "  repo_index {\n"
            "    value: 1\n"
            "  }\n"
            "}\n"
            "module_dependencies {\n"
            '  module_name: "base"\n'
            "  dependency_index: 0\n"
            "}\n"
            "repositories {\n"
            "  maven_repo {\n"
            '    url: "https://dl.google.com/dl/android/maven2/"\n'
            "  }\n"
            "}\n"
            "repositories {\n"
            "  maven_repo {\n"
            '    url: "https://repo.maven.apache.org/maven2/"\n'
            "  }\n"
            "}\n",
            encoding="ascii",
        )

        for relative_root in (
            readback_module.ANDROID_RELEASE_MERGED_NATIVE_RELATIVE_PATH,
            readback_module.ANDROID_RELEASE_STRIPPED_NATIVE_RELATIVE_PATH,
        ):
            native_path = (
                root / relative_root / "arm64-v8a/libfixture.so"
            )
            native_path.parent.mkdir(parents=True, exist_ok=True)
            native_path.write_bytes(native)
        return {
            "aabPath": aab_path,
            "apkPath": apk_path,
            "mappingDirectory": mapping_directory,
            "metadataPath": metadata_path,
            "native": native,
            "sdkPath": sdk_path,
            "baselineProfile": baseline_profile,
            "baselineProfileMetadata": baseline_profile_metadata,
        }

    def verify_android_release_build_output_fixture(
        self,
        root: Path,
        *,
        apk_badging: dict[str, object] | None = None,
        apk_policy: dict[str, object] | None = None,
        aab_manifest: dict[str, object] | None = None,
        elf_result: tuple[str | None, bool] = (
            "0123456789abcdef",
            False,
        ),
    ) -> dict[str, object]:
        topology = expected_entry_point_topology()
        application_shell = expected_application_shell()
        expected_badging: dict[str, object] = {
            "applicationId": "com.localagentbridge.android",
            "minSdk": 26,
            "nativeAbis": ["arm64-v8a"],
            "targetSdk": 36,
            "versionCode": 24,
            "versionName": "1.0.0",
        }
        expected_policy: dict[str, object] = {
            "allowBackup": False,
            "applicationShell": application_shell,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "entryPointTopology": topology,
            "fullBackupContent": "@xml/backup_rules",
        }
        expected_aab: dict[str, object] = {
            "allowBackup": False,
            "applicationId": "com.localagentbridge.android",
            "applicationShell": application_shell,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "entryPointTopology": topology,
            "fullBackupContent": "@xml/backup_rules",
            "minSdk": 26,
            "targetSdk": 36,
            "versionCode": 24,
            "versionName": "1.0.0",
        }
        with (
            mock.patch.object(
                readback_module,
                "inspect_apk_badging",
                return_value=(
                    expected_badging
                    if apk_badging is None
                    else apk_badging
                ),
            ),
            mock.patch.object(
                readback_module,
                "inspect_apk_backup_policy",
                return_value=(
                    expected_policy if apk_policy is None else apk_policy
                ),
            ),
            mock.patch.object(
                readback_module,
                "inspect_aab_manifest",
                return_value=(
                    expected_aab if aab_manifest is None else aab_manifest
                ),
            ),
            mock.patch.object(
                readback_module,
                "bundletool_version",
                return_value=readback_module.BUNDLETOOL_VERSION,
            ),
            mock.patch.object(
                readback_module,
                "find_llvm_readelf",
                return_value=Path("/fixture/llvm-readelf"),
            ),
            mock.patch.object(
                readback_module,
                "inspect_elf",
                return_value=elf_result,
            ),
            mock.patch.object(
                readback_module,
                "ANDROID_RELEASE_R8_MAPPING_SHA256",
                self.FIXTURE_R8_MAPPING_SHA256,
            ),
            mock.patch.object(
                readback_module,
                "ANDROID_RELEASE_R8_MAPPING_PRT_LOGICAL_SHA256",
                self.FIXTURE_R8_MAPPING_PRT_LOGICAL_SHA256,
            ),
            mock.patch.object(
                readback_module,
                "ANDROID_RELEASE_SDK_DEPENDENCIES_SHA256",
                self.FIXTURE_SDK_DEPENDENCIES_SHA256,
            ),
            mock.patch.object(
                readback_module,
                "ANDROID_RELEASE_API31_DM_PROFILE_SHA256",
                self.FIXTURE_API31_DM_PROFILE_SHA256,
            ),
            mock.patch.object(
                readback_module,
                "ANDROID_RELEASE_APK_BASELINE_PROFILE_SHA256",
                self.FIXTURE_APK_BASELINE_PROFILE_SHA256,
            ),
            mock.patch.object(
                readback_module,
                "ANDROID_RELEASE_APK_BASELINE_PROFILE_METADATA_SHA256",
                self.FIXTURE_APK_BASELINE_PROFILE_METADATA_SHA256,
            ),
            mock.patch.object(
                readback_module,
                "ANDROID_RELEASE_SDK_DEPENDENCIES_PROTOBUF_SHA256",
                self.FIXTURE_SDK_DEPENDENCIES_PROTOBUF_SHA256,
            ),
            mock.patch.object(
                readback_module,
                "ANDROID_RELEASE_DEX_SHA256",
                self.FIXTURE_DEX_SHA256,
            ),
        ):
            return readback_module.verify_android_release_build_outputs(root)

    def write_macos_unsealed_release_build_output_fixture(
        self,
        root: Path,
    ) -> dict[str, Path]:
        ledger = root / "release/version-ledger.tsv"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            "build_number\tmarketing_version\n24\t1.0.0\n",
            encoding="ascii",
        )
        output = root / readback_module.MACOS_UNSEALED_OUTPUT_RELATIVE_PATH
        app = output / "AetherLink.app"
        dsym = output / "AetherLink.dSYM"
        output.mkdir(parents=True)
        (
            output / readback_module.MACOS_UNSEALED_SOURCE_RECEIPT_NAME
        ).write_bytes(
            readback_module.canonical_json_bytes(
                {
                    "build": {
                        "buildNumber": 24,
                        "configuration": "release",
                        "marketingVersion": "1.0.0",
                        "mode": "unsealed-package-only",
                    },
                    "outputContract": (
                        readback_module.MACOS_UNSEALED_OUTPUT_CONTRACT
                    ),
                    "schemaVersion": (
                        readback_module
                        .MACOS_UNSEALED_SOURCE_RECEIPT_SCHEMA_VERSION
                    ),
                    "source": self.FIXTURE_MACOS_SOURCE_SUMMARY,
                }
            )
        )

        app_info = {
            "CFBundleDevelopmentRegion": "en",
            "CFBundleExecutable": "AetherLink",
            "CFBundleIconFile": "AppIcon",
            "CFBundleIdentifier": "dev.aetherlink.companion",
            "CFBundleLocalizations": ["en", "ko", "ja", "zh-Hans", "fr"],
            "CFBundleName": "AetherLink",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "24",
            "LSMinimumSystemVersion": "14.0",
            "NSPrincipalClass": "NSApplication",
        }
        resource_info = {"CFBundleDevelopmentRegion": "en"}
        dsym_info = {
            "CFBundleDevelopmentRegion": "English",
            "CFBundleIdentifier": "com.apple.xcode.dsym.AetherLink",
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundlePackageType": "dSYM",
            "CFBundleShortVersionString": "1.0",
            "CFBundleSignature": "????",
            "CFBundleVersion": "1",
        }
        files: dict[Path, bytes] = {
            app / "Contents/Info.plist": plistlib.dumps(
                app_info,
                fmt=plistlib.FMT_XML,
                sort_keys=True,
            ),
            app / "Contents/MacOS/AetherLink": b"fixture-mach-o-app\n",
            app / "Contents/Resources/AppIcon.icns": b"fixture-icon\n",
            (
                app
                / "Contents/Resources/AetherLink_LocalAgentBridge.bundle/Info.plist"
            ): plistlib.dumps(
                resource_info,
                fmt=plistlib.FMT_XML,
                sort_keys=True,
            ),
            dsym / "Contents/Info.plist": plistlib.dumps(
                dsym_info,
                fmt=plistlib.FMT_XML,
                sort_keys=True,
            ),
            (
                dsym / "Contents/Resources/DWARF/AetherLink"
            ): b"fixture-mach-o-dwarf\n",
            (
                dsym
                / "Contents/Resources/Relocations/aarch64/AetherLink.yml"
            ): b"fixture-relocations\n",
        }
        for locale in ("en", "fr", "ja", "ko", "zh-hans"):
            files[
                app
                / "Contents/Resources/AetherLink_LocalAgentBridge.bundle"
                / f"{locale}.lproj/Localizable.strings"
            ] = f'"fixture" = "{locale}";\n'.encode("utf-8")
        for path, data in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(
                0o755
                if path == app / "Contents/MacOS/AetherLink"
                else 0o644
            )
        return {"app": app, "dSYM": dsym, "output": output}

    def verify_macos_unsealed_release_build_output_fixture(
        self,
        root: Path,
        *,
        app_architecture: str = "arm64",
        dsym_architecture: str = "arm64",
        app_uuid: str = "01234567-89AB-CDEF-0123-456789ABCDEF",
        dsym_uuid: str = "01234567-89AB-CDEF-0123-456789ABCDEF",
        source_summary: dict[str, object] | None = None,
        calls: list[tuple[list[str], Path]] | None = None,
    ) -> dict[str, object]:
        def run_tool(command: list[str], cwd: Path) -> str:
            if calls is not None:
                calls.append((command, cwd))
            target = Path(command[-1])
            self.assertTrue(target.is_relative_to(cwd))
            self.assertFalse(target.is_relative_to(root))
            is_dsym = "AetherLink.dSYM" in target.parts
            if command[:2] == ["/usr/bin/lipo", "-archs"]:
                return dsym_architecture if is_dsym else app_architecture
            if command[:2] == ["/usr/bin/dwarfdump", "--uuid"]:
                uuid = dsym_uuid if is_dsym else app_uuid
                architecture = (
                    dsym_architecture if is_dsym else app_architecture
                )
                return f"UUID: {uuid} ({architecture}) {target}"
            raise AssertionError(f"unexpected macOS tool command: {command!r}")

        with (
            mock.patch.object(
                readback_module,
                "run_macos_readback_tool",
                side_effect=run_tool,
            ),
            mock.patch.object(
                readback_module,
                "current_source_snapshot_summary",
                return_value=(
                    self.FIXTURE_MACOS_SOURCE_SUMMARY
                    if source_summary is None
                    else source_summary
                ),
            ),
        ):
            return readback_module.verify_macos_release_build_outputs(root)

    def test_macos_unsealed_release_build_output_direct_readback_passes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_macos_unsealed_release_build_output_fixture(
                root
            )
            output = fixture["output"]
            before = {
                path.relative_to(output).as_posix(): (
                    path.read_bytes(),
                    stat.S_IMODE(path.stat().st_mode),
                )
                for path in output.rglob("*")
                if path.is_file()
            }
            calls: list[tuple[list[str], Path]] = []

            result = self.verify_macos_unsealed_release_build_output_fixture(
                root,
                calls=calls,
            )

            after = {
                path.relative_to(output).as_posix(): (
                    path.read_bytes(),
                    stat.S_IMODE(path.stat().st_mode),
                )
                for path in output.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual(result["bundleId"], "dev.aetherlink.companion")
            self.assertEqual(result["marketingVersion"], "1.0.0")
            self.assertEqual(result["buildNumber"], 24)
            self.assertEqual(result["architecture"], "arm64")
            self.assertEqual(result["outerBundleSeal"], "absent")
            self.assertEqual(
                result["source"],
                self.FIXTURE_MACOS_SOURCE_SUMMARY,
            )
            self.assertEqual(
                result["sourceReceipt"]["size"],
                (
                    output / readback_module.MACOS_UNSEALED_SOURCE_RECEIPT_NAME
                ).stat().st_size,
            )
            self.assertEqual(result["app"]["fileCount"], 9)
            self.assertEqual(result["dSYM"]["fileCount"], 3)
            self.assertRegex(result["app"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(result["dSYM"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(len(calls), 4)

    def test_macos_unsealed_release_build_output_rejects_stale_source_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_macos_unsealed_release_build_output_fixture(root)
            stale_current_source = {
                **self.FIXTURE_MACOS_SOURCE_SUMMARY,
                "sha256": "c" * 64,
            }

            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "differs from current source",
            ):
                self.verify_macos_unsealed_release_build_output_fixture(
                    root,
                    source_summary=stale_current_source,
                )

    def test_macos_unsealed_release_build_output_rejects_receipt_drift(
        self,
    ) -> None:
        for mutation in (
            "boolean-schema",
            "source-digest",
            "extra-key",
            "executable-mode",
            "symlink",
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = self.write_macos_unsealed_release_build_output_fixture(
                    root
                )
                receipt_path = (
                    fixture["output"]
                    / readback_module.MACOS_UNSEALED_SOURCE_RECEIPT_NAME
                )
                if mutation == "symlink":
                    outside = root / "outside-receipt.json"
                    outside.write_bytes(receipt_path.read_bytes())
                    receipt_path.unlink()
                    receipt_path.symlink_to(outside)
                elif mutation == "executable-mode":
                    receipt_path.chmod(0o755)
                else:
                    receipt = readback_module.parse_canonical_json(
                        receipt_path.read_bytes(),
                        "fixture source receipt",
                    )
                    if mutation == "boolean-schema":
                        receipt["schemaVersion"] = True
                    elif mutation == "source-digest":
                        receipt["source"]["sha256"] = "d" * 64
                    else:
                        receipt["unexpected"] = False
                    receipt_path.write_bytes(
                        readback_module.canonical_json_bytes(receipt)
                    )

                with self.assertRaises(ReleaseArchiveVerificationError):
                    self.verify_macos_unsealed_release_build_output_fixture(
                        root
                    )

    def test_macos_unsealed_release_build_output_rejects_closed_tree_drift(
        self,
    ) -> None:
        mutations = ("extra-root", "outer-seal", "symlink", "special")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = self.write_macos_unsealed_release_build_output_fixture(
                    root
                )
                app = fixture["app"]
                output = fixture["output"]
                if mutation == "extra-root":
                    (output / "unexpected.txt").write_bytes(b"unexpected\n")
                elif mutation == "outer-seal":
                    signature = app / "Contents/_CodeSignature/CodeResources"
                    signature.parent.mkdir()
                    signature.write_bytes(b"not-allowed\n")
                elif mutation == "symlink":
                    icon = app / "Contents/Resources/AppIcon.icns"
                    target = root / "outside-icon"
                    target.write_bytes(icon.read_bytes())
                    icon.unlink()
                    icon.symlink_to(target)
                else:
                    strings = (
                        app
                        / "Contents/Resources/AetherLink_LocalAgentBridge.bundle"
                        / "en.lproj/Localizable.strings"
                    )
                    strings.unlink()
                    os.mkfifo(strings)

                with self.assertRaises(ReleaseArchiveVerificationError):
                    self.verify_macos_unsealed_release_build_output_fixture(
                        root
                    )

    def test_macos_unsealed_release_build_output_rejects_mode_and_plist_drift(
        self,
    ) -> None:
        for mutation in ("executable-mode", "resource-mode", "version", "duplicate-key"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = self.write_macos_unsealed_release_build_output_fixture(
                    root
                )
                app = fixture["app"]
                executable = app / "Contents/MacOS/AetherLink"
                resource = app / "Contents/Resources/AppIcon.icns"
                info_path = app / "Contents/Info.plist"
                if mutation == "executable-mode":
                    executable.chmod(0o644)
                elif mutation == "resource-mode":
                    resource.chmod(0o755)
                elif mutation == "version":
                    with info_path.open("rb") as handle:
                        info = plistlib.load(handle)
                    info["CFBundleVersion"] = "23"
                    info_path.write_bytes(
                        plistlib.dumps(
                            info,
                            fmt=plistlib.FMT_XML,
                            sort_keys=True,
                        )
                    )
                else:
                    data = info_path.read_bytes()
                    marker = b"\t<key>CFBundleExecutable</key>\n"
                    duplicate = (
                        marker
                        + b"\t<string>AetherLink</string>\n"
                    )
                    self.assertIn(marker, data)
                    info_path.write_bytes(
                        data.replace(marker, duplicate + marker, 1)
                    )

                with self.assertRaises(ReleaseArchiveVerificationError):
                    self.verify_macos_unsealed_release_build_output_fixture(
                        root
                    )

    def test_macos_unsealed_release_build_output_rejects_architecture_and_uuid_drift(
        self,
    ) -> None:
        cases = {
            "app-x86": {"app_architecture": "x86_64"},
            "dsym-x86": {"dsym_architecture": "x86_64"},
            "uuid": {
                "dsym_uuid": "FEDCBA98-7654-3210-FEDC-BA9876543210"
            },
        }
        for label, overrides in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.write_macos_unsealed_release_build_output_fixture(root)
                with self.assertRaises(ReleaseArchiveVerificationError):
                    self.verify_macos_unsealed_release_build_output_fixture(
                        root,
                        **overrides,
                    )

    def test_macos_readback_tool_rejects_process_and_output_failures(
        self,
    ) -> None:
        command = ["/usr/bin/fixture-tool", "--version"]
        cases = {
            "timeout": subprocess.TimeoutExpired(command, 30),
            "launch": OSError("injected launch failure"),
            "nonzero": subprocess.CompletedProcess(
                command,
                7,
                stdout=b"failed\n",
                stderr=b"detail\n",
            ),
            "oversized": subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    b"x"
                    * (
                        readback_module.MACOS_READBACK_TOOL_MAX_OUTPUT_BYTES
                        + 1
                    )
                ),
                stderr=b"",
            ),
            "non-utf8": subprocess.CompletedProcess(
                command,
                0,
                stdout=b"\xff",
                stderr=b"",
            ),
        }
        for label, result_or_error in cases.items():
            with (
                self.subTest(label=label),
                mock.patch.object(
                    readback_module.subprocess,
                    "run",
                    side_effect=(
                        result_or_error
                        if isinstance(result_or_error, BaseException)
                        else None
                    ),
                    return_value=(
                        None
                        if isinstance(result_or_error, BaseException)
                        else result_or_error
                    ),
                ),
                self.assertRaises(ReleaseArchiveVerificationError),
            ):
                readback_module.run_macos_readback_tool(
                    command,
                    Path("/tmp"),
                )

    def test_macos_uuid_parser_rejects_missing_and_duplicate_records(
        self,
    ) -> None:
        valid = (
            "UUID: 01234567-89AB-CDEF-0123-456789ABCDEF "
            "(arm64) /tmp/AetherLink"
        )
        self.assertEqual(
            readback_module.parse_macos_dwarfdump_uuid_output(
                valid,
                "fixture",
            ),
            ("01234567-89AB-CDEF-0123-456789ABCDEF", "arm64"),
        )
        for output in ("", f"{valid}\n{valid}"):
            with self.assertRaises(ReleaseArchiveVerificationError):
                readback_module.parse_macos_dwarfdump_uuid_output(
                    output,
                    "fixture",
                )

    def test_macos_build_output_cli_modes_are_closed(self) -> None:
        command = [
            os.sys.executable,
            str(
                readback_module.ROOT
                / "script/check_release_artifact_archive.py"
            ),
        ]
        mutually_exclusive = subprocess.run(
            command + ["--android-build-outputs", "--macos-build-outputs"],
            cwd=readback_module.ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(mutually_exclusive.returncode, 2)
        self.assertIn("not allowed with argument", mutually_exclusive.stderr)

        archive_conflict = subprocess.run(
            command
            + [
                "--macos-build-outputs",
                "--archive-dir",
                str(
                    readback_module.ROOT
                    / "dist/releases/not-the-current-release"
                ),
            ],
            cwd=readback_module.ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(archive_conflict.returncode, 1)
        self.assertIn(
            "--archive-dir is not valid with --macos-build-outputs",
            archive_conflict.stderr,
        )

    def test_android_release_build_output_direct_readback_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            result = self.verify_android_release_build_output_fixture(root)
            self.assertEqual(result["applicationId"], "com.localagentbridge.android")
            self.assertEqual(result["versionCode"], 24)
            self.assertEqual(result["versionName"], "1.0.0")
            self.assertEqual(result["baselineProfileCount"], 2)
            self.assertEqual(result["mappingFileCount"], 6)
            self.assertEqual(result["nativeLibraryCount"], 1)
            self.assertEqual(result["sdkDependencyCount"], 1)
            self.assertEqual(
                result["nativeSymbolStatus"],
                "unavailable-upstream-prestripped",
            )

            mapping_directory = fixture["mappingDirectory"]
            assert isinstance(mapping_directory, Path)
            raw_prt = (mapping_directory / "mapping.prt").read_bytes()
            raw_resources = (
                mapping_directory / "resources.txt"
            ).read_bytes()
            raw_seeds = (mapping_directory / "seeds.txt").read_bytes()
            self.assertNotEqual(
                raw_prt,
                readback_module.canonicalize_r8_mapping_prt(
                    raw_prt,
                    "fixture mapping.prt",
                ),
            )
            self.assertNotEqual(
                raw_resources,
                readback_module.canonicalize_r8_resources(
                    raw_resources,
                    "fixture resources.txt",
                ),
            )
            self.assertNotEqual(
                raw_seeds,
                readback_module.canonicalize_r8_line_artifact(
                    raw_seeds,
                    "fixture seeds.txt",
                ),
            )

    def test_android_release_build_output_readback_rejects_file_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            aab_path = fixture["aabPath"]
            assert isinstance(aab_path, Path)
            aab_path.unlink()
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "AAB output directory.*missing",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            metadata_path = fixture["metadataPath"]
            assert isinstance(metadata_path, Path)
            metadata_path.write_text(
                metadata_path.read_text(encoding="ascii").replace(
                    '"version":3',
                    '"unexpected":NaN,"version":3',
                    1,
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "nonstandard JSON constant 'NaN'",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            metadata_path = fixture["metadataPath"]
            assert isinstance(metadata_path, Path)
            metadata = metadata_path.read_text(encoding="ascii")
            metadata_path.write_text(
                metadata.replace(
                    '"version":3',
                    '"version":3,"version":3',
                    1,
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "duplicate JSON key 'version'",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            metadata_path = fixture["metadataPath"]
            assert isinstance(metadata_path, Path)
            metadata = metadata_path.read_text(encoding="ascii")
            metadata_path.write_text(
                metadata.replace(
                    '"versionCode":24',
                    '"versionCode":true',
                    1,
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "versionCode must be an integer",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            assert isinstance(apk_path, Path)
            profile = (
                apk_path.parent
                / "baselineProfiles/0/app-release-unsigned.dm"
            )
            profile.unlink()
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "baseline profile.*cannot be inspected",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            assert isinstance(apk_path, Path)
            profile = (
                apk_path.parent
                / "baselineProfiles/0/app-release-unsigned.dm"
            )
            profile.write_bytes(b"not-a-profile-zip")
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "baseline profile.*is not a readable ZIP",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            baseline_profile_metadata = fixture["baselineProfileMetadata"]
            assert isinstance(apk_path, Path)
            assert isinstance(baseline_profile_metadata, bytes)
            profile = (
                apk_path.parent
                / "baselineProfiles/0/app-release-unsigned.dm"
            )
            self.write_fixture_zip_members(
                profile,
                [
                    (
                        "primary.prof",
                        b"pro\x00015\x00tampered-converted-profile\n",
                    ),
                    ("primary.profm", baseline_profile_metadata),
                ],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "pinned V1 converted-profile identity",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            aab_path = fixture["aabPath"]
            assert isinstance(apk_path, Path)
            assert isinstance(aab_path, Path)
            tampered_profile = b"pro\x00010\x00coordinated-profile-drift\n"
            tampered_metadata = b"prm\x00002\x00coordinated-metadata-drift\n"
            self.replace_fixture_zip_member(
                apk_path,
                "assets/dexopt/baseline.prof",
                tampered_profile,
            )
            self.replace_fixture_zip_member(
                apk_path,
                "assets/dexopt/baseline.profm",
                tampered_metadata,
            )
            self.replace_fixture_zip_member(
                aab_path,
                (
                    "BUNDLE-METADATA/com.android.tools.build.profiles/"
                    "baseline.prof"
                ),
                tampered_profile,
            )
            self.replace_fixture_zip_member(
                aab_path,
                (
                    "BUNDLE-METADATA/com.android.tools.build.profiles/"
                    "baseline.profm"
                ),
                tampered_metadata,
            )
            api_28_profile = (
                apk_path.parent
                / "baselineProfiles/1/app-release-unsigned.dm"
            )
            self.write_fixture_zip_members(
                api_28_profile,
                [
                    ("primary.prof", tampered_profile),
                    ("primary.profm", tampered_metadata),
                ],
            )
            api_31_profile = (
                apk_path.parent
                / "baselineProfiles/0/app-release-unsigned.dm"
            )
            with zipfile.ZipFile(api_31_profile, "r") as archive:
                converted_profile = archive.read("primary.prof")
            self.write_fixture_zip_members(
                api_31_profile,
                [
                    ("primary.prof", converted_profile),
                    ("primary.profm", tampered_metadata),
                ],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "pinned V1 profile identities",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            assert isinstance(apk_path, Path)
            baseline_root = apk_path.parent / "baselineProfiles"
            moved_root = root / "moved-baseline-profiles"
            baseline_root.rename(moved_root)
            baseline_root.symlink_to(moved_root, target_is_directory=True)
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "baseline profile root must be a non-symlink directory",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            mapping_directory = fixture["mappingDirectory"]
            assert isinstance(mapping_directory, Path)
            (mapping_directory / "unexpected.txt").write_text(
                "unexpected\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "R8 output directory inventory differs",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            mapping_directory = fixture["mappingDirectory"]
            assert isinstance(mapping_directory, Path)
            seeds = mapping_directory / "seeds.txt"
            replacement = root / "replacement-seeds.txt"
            replacement.write_text("seed\n", encoding="ascii")
            seeds.unlink()
            seeds.symlink_to(replacement)
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "must be a regular non-symlink file",
            ):
                self.verify_android_release_build_output_fixture(root)

    def test_android_release_build_output_readback_rejects_content_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(
                root,
                aab_mapping=b"different.Mapping -> z:\n",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "AAB R8 mapping differs",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(
                root,
                embedded_symbol=b"not-an-elf-symbol-file",
            )
            symbol_path = (
                root
                / readback_module.ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH
            )
            symbol_path.parent.mkdir(parents=True)
            self.write_fixture_zip_members(
                symbol_path,
                [
                    (
                        "arm64-v8a/libfixture.so.sym",
                        b"not-an-elf-symbol-file",
                    )
                ],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "native symbol.*is not an ELF file",
            ):
                self.verify_android_release_build_output_fixture(
                    root,
                    elf_result=("0123456789abcdef", True),
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            symbol_data = b"\x7fELFfixture-symbols"
            self.write_android_release_build_output_fixture(
                root,
                embedded_symbol=symbol_data,
            )
            symbol_path = (
                root
                / readback_module.ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH
            )
            symbol_path.parent.mkdir(parents=True)
            self.write_fixture_zip_members(
                symbol_path,
                [("arm64-v8a/libfixture.so.sym", symbol_data)],
            )
            result = self.verify_android_release_build_output_fixture(
                root,
                elf_result=("0123456789abcdef", True),
            )
            self.assertEqual(result["nativeSymbolStatus"], "available")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            symbol_data = b"\x7fELFfixture-symbols"
            self.write_android_release_build_output_fixture(
                root,
                embedded_symbol=symbol_data,
                embedded_symbol_name="arm64-v8a/libghost.so.sym",
            )
            symbol_path = (
                root
                / readback_module.ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH
            )
            symbol_path.parent.mkdir(parents=True)
            self.write_fixture_zip_members(
                symbol_path,
                [("arm64-v8a/libghost.so.sym", symbol_data)],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "native-symbol members differ from JNI libraries",
            ):
                self.verify_android_release_build_output_fixture(
                    root,
                    elf_result=("0123456789abcdef", True),
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(
                root,
                aab_abi="x86_64",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "JNI ABI set must be arm64-v8a-only",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(root)
            wrong_badging: dict[str, object] = {
                "applicationId": "com.localagentbridge.android",
                "minSdk": 26,
                "nativeAbis": ["x86_64"],
                "targetSdk": 36,
                "versionCode": 24,
                "versionName": "1.0.0",
            }
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "APK badging differs",
            ):
                self.verify_android_release_build_output_fixture(
                    root,
                    apk_badging=wrong_badging,
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(root)
            wrong_shell = expected_application_shell()
            localized = wrong_shell["localizedString"]
            assert isinstance(localized, dict)
            values = localized["values"]
            assert isinstance(values, dict)
            values["ko"] = "변조"
            wrong_manifest: dict[str, object] = {
                "allowBackup": False,
                "applicationId": "com.localagentbridge.android",
                "applicationShell": wrong_shell,
                "dataExtractionRules": "@xml/data_extraction_rules",
                "entryPointTopology": expected_entry_point_topology(),
                "fullBackupContent": "@xml/backup_rules",
                "minSdk": 26,
                "targetSdk": 36,
                "versionCode": 24,
                "versionName": "1.0.0",
            }
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "AAB manifest/config/resources differ",
            ):
                self.verify_android_release_build_output_fixture(
                    root,
                    aab_manifest=wrong_manifest,
                )

    def test_android_release_build_output_readback_rejects_zip_and_apk_jni_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            native = fixture["native"]
            assert isinstance(apk_path, Path)
            assert isinstance(native, bytes)
            self.replace_fixture_zip_member(
                apk_path,
                "lib/arm64-v8a/libfixture.so",
                native + b"-changed",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "APK and AAB JNI members differ.*byteDifferences",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            native = fixture["native"]
            assert isinstance(apk_path, Path)
            assert isinstance(native, bytes)
            with zipfile.ZipFile(apk_path, "r") as archive:
                members = [
                    (info.filename, archive.read(info))
                    for info in archive.infolist()
                ]
            self.write_fixture_zip_members(
                apk_path,
                members + [("lib/arm64-v8a/libextra.so", native)],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "APK and AAB JNI members differ.*extra=.*libextra",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            aab_path = fixture["aabPath"]
            assert isinstance(apk_path, Path)
            assert isinstance(aab_path, Path)
            coordinated_dex = b"dex\ncoordinated-drift\n"
            self.replace_fixture_zip_member(
                apk_path,
                "classes.dex",
                coordinated_dex,
            )
            self.replace_fixture_zip_member(
                aab_path,
                "base/dex/classes.dex",
                coordinated_dex,
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "DEX differs from the pinned V1 byte identity",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            apk_path = fixture["apkPath"]
            native = fixture["native"]
            assert isinstance(apk_path, Path)
            assert isinstance(native, bytes)
            self.write_fixture_zip_members(
                apk_path,
                [
                    ("classes.dex", b"first"),
                    ("classes.dex", b"second"),
                    ("lib/arm64-v8a/libfixture.so", native),
                ],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "APK must contain unique members",
            ):
                self.verify_android_release_build_output_fixture(root)

        for artifact_key, member_name, label in (
            ("apkPath", "classes.dex", "APK"),
            ("aabPath", "base/dex/classes.dex", "AAB"),
        ):
            with self.subTest(artifact=label):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    fixture = self.write_android_release_build_output_fixture(
                        root
                    )
                    artifact_path = fixture[artifact_key]
                    assert isinstance(artifact_path, Path)
                    self.corrupt_zip_member_payload(
                        artifact_path,
                        member_name,
                    )
                    with self.assertRaisesRegex(
                        ReleaseArchiveVerificationError,
                        f"Android Release {label} is not a readable ZIP",
                    ):
                        self.verify_android_release_build_output_fixture(root)

    def test_safe_zip_member_readback_enforces_resource_bounds(self) -> None:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("one", b"1234")
            archive.writestr("two", b"5678")
        data = output.getvalue()
        with self.assertRaisesRegex(
            ReleaseArchiveVerificationError,
            "exceeds the 1-member limit",
        ):
            readback_module.read_safe_zip_members(
                data,
                "fixture ZIP",
                maximum_members=1,
            )
        with self.assertRaisesRegex(
            ReleaseArchiveVerificationError,
            "member exceeds the 3-byte limit",
        ):
            readback_module.read_safe_zip_members(
                data,
                "fixture ZIP",
                maximum_member_bytes=3,
            )
        with self.assertRaisesRegex(
            ReleaseArchiveVerificationError,
            "exceeds the 7-byte total uncompressed limit",
        ):
            readback_module.read_safe_zip_members(
                data,
                "fixture ZIP",
                maximum_total_uncompressed_bytes=7,
            )
        with self.assertRaisesRegex(
            ReleaseArchiveVerificationError,
            "limit must be a positive integer",
        ):
            readback_module.read_safe_zip_members(
                data,
                "fixture ZIP",
                maximum_members=True,
            )

    def test_android_release_tool_resolution_is_exactly_pinned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            sdk = Path(temporary) / "sdk"
            root.mkdir()
            (root / "local.properties").write_text(
                f"sdk.dir={sdk}\n",
                encoding="utf-8",
            )
            pinned_aapt2 = (
                sdk
                / "build-tools"
                / readback_module.ANDROID_BUILD_TOOLS_VERSION
                / "aapt2"
            )
            newer_aapt2 = sdk / "build-tools/99.0.0/aapt2"
            for path in (pinned_aapt2, newer_aapt2):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
                path.chmod(0o755)
            self.assertEqual(
                readback_module.find_android_build_tool("aapt2", root),
                pinned_aapt2,
            )
            self.assertEqual(
                builder_module.find_android_build_tool("aapt2", root),
                pinned_aapt2,
            )

            pinned_readelf = (
                sdk
                / "ndk"
                / readback_module.ANDROID_NDK_VERSION
                / "toolchains/llvm/prebuilt/fixture-host/bin/llvm-readelf"
            )
            newer_readelf = (
                sdk
                / "ndk/99.0.0/toolchains/llvm/prebuilt/fixture-host/bin/"
                "llvm-readelf"
            )
            for path in (pinned_readelf, newer_readelf):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
                path.chmod(0o755)
            self.assertEqual(
                readback_module.find_llvm_readelf(root),
                pinned_readelf,
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            sdk = Path(temporary) / "sdk"
            root.mkdir()
            (root / "local.properties").write_text(
                f"sdk.dir={sdk}\n",
                encoding="utf-8",
            )
            newer_aapt2 = sdk / "build-tools/99.0.0/aapt2"
            newer_aapt2.parent.mkdir(parents=True)
            newer_aapt2.write_text(
                "#!/bin/sh\nexit 0\n",
                encoding="ascii",
            )
            newer_aapt2.chmod(0o755)
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "cannot locate pinned Build Tools",
            ):
                readback_module.find_android_build_tool("aapt2", root)

    def test_android_release_build_output_readback_rejects_dependency_and_symbol_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            sdk_path = fixture["sdkPath"]
            assert isinstance(sdk_path, Path)
            sdk_path.write_bytes(
                sdk_path.read_bytes().replace(
                    b"0123456789abcdef0123456789abcdef",
                    b"1123456789abcdef0123456789abcdef",
                    1,
                )
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "pinned V1 byte identity",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            sdk_path = fixture["sdkPath"]
            assert isinstance(sdk_path, Path)
            sdk_path.write_bytes(
                sdk_path.read_bytes().replace(
                    b'module_dependencies {\n  module_name: "base"\n'
                    b"  dependency_index: 0\n}\n",
                    b"",
                    1,
                )
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "top-level block shape differs",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            aab_path = fixture["aabPath"]
            assert isinstance(aab_path, Path)
            self.replace_fixture_zip_member(
                aab_path,
                (
                    "BUNDLE-METADATA/com.android.tools.build.libraries/"
                    "dependencies.pb"
                ),
                b"tampered-sdk-dependencies-protobuf\n",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "SDK dependency protobuf differs from the pinned V1",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(
                root,
                sdk_coordinate=("com.example", "unlocked", "9.9"),
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "contains unlocked modules",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(root)
            app_lock = root / "apps/android/app/gradle.lockfile"
            app_lock.write_text(
                app_lock.read_text(encoding="ascii").replace(
                    "empty=releaseAnnotationProcessorClasspath\n",
                    "com.example:second:2.0=releaseRuntimeClasspath\n"
                    "empty=releaseAnnotationProcessorClasspath\n",
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "exact Release runtime lock closure.*missing=.*second",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(root)
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "debug metadata.*native-symbol archive is missing",
            ):
                self.verify_android_release_build_output_fixture(
                    root,
                    elf_result=("0123456789abcdef", True),
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(root)
            symbol_path = (
                root
                / readback_module.ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH
            )
            symbol_path.parent.mkdir(parents=True)
            (symbol_path.parent / "unexpected.txt").write_bytes(b"unexpected")
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "native-symbol output directory inventory differs",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(root)
            symbol_path = (
                root
                / readback_module.ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH
            )
            symbol_path.parent.mkdir(parents=True)
            symbol_archive = io.BytesIO()
            with zipfile.ZipFile(symbol_archive, "w") as archive:
                archive.writestr(
                    "arm64-v8a/libfixture.so.sym",
                    b"symbols",
                )
            symbol_path.write_bytes(symbol_archive.getvalue())
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "standalone and embedded native symbols differ",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_android_release_build_output_fixture(
                root,
                embedded_symbol=b"symbols",
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "embeds native symbols without the standalone archive",
            ):
                self.verify_android_release_build_output_fixture(root)

    def test_android_release_build_output_readback_rejects_coordinated_r8_drift(
        self,
    ) -> None:
        mapping_member = (
            "BUNDLE-METADATA/com.android.tools.build.obfuscation/"
            "proguard.map"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            mapping_directory = fixture["mappingDirectory"]
            aab_path = fixture["aabPath"]
            assert isinstance(mapping_directory, Path)
            assert isinstance(aab_path, Path)
            (mapping_directory / "mapping.txt").write_bytes(b"x\n")
            self.replace_fixture_zip_member(aab_path, mapping_member, b"x\n")
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "mapping.txt R8 header differs",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            mapping_directory = fixture["mappingDirectory"]
            aab_path = fixture["aabPath"]
            assert isinstance(mapping_directory, Path)
            assert isinstance(aab_path, Path)
            mapping_path = mapping_directory / "mapping.txt"
            mapping = mapping_path.read_bytes().replace(
                b"fixture.Source",
                b"fixture.Tampered",
            )
            mapping_path.write_bytes(mapping)
            self.replace_fixture_zip_member(aab_path, mapping_member, mapping)
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "pg_map_hash differs from its body",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            mapping_directory = fixture["mappingDirectory"]
            assert isinstance(mapping_directory, Path)
            self.write_fixture_zip_members(
                mapping_directory / "mapping.prt",
                [("METADATA", b"fixture-metadata\n")],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "mapping.prt must contain class partitions",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            mapping_directory = fixture["mappingDirectory"]
            assert isinstance(mapping_directory, Path)
            mapping_prt = mapping_directory / "mapping.prt"
            with zipfile.ZipFile(mapping_prt, "r") as archive:
                metadata = archive.read("METADATA")
            self.write_fixture_zip_members(
                mapping_prt,
                [("a", b"x"), ("METADATA", metadata)],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "partition payload differs from mapping.txt",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            mapping_directory = fixture["mappingDirectory"]
            assert isinstance(mapping_directory, Path)
            mapping_prt = mapping_directory / "mapping.prt"
            mapping = (mapping_directory / "mapping.txt").read_bytes()
            mapping_body = b"".join(mapping.splitlines(keepends=True)[7:])
            with zipfile.ZipFile(mapping_prt, "r") as archive:
                metadata = archive.read("METADATA")
            source_prefix = (
                b'# {"id":"partitionSourceFiles","fileNameMappings":'
                b'{"fixture.Source":"Renamed.kt"}}\n'
            )
            self.write_fixture_zip_members(
                mapping_prt,
                [
                    ("a", source_prefix + mapping_body),
                    ("METADATA", metadata),
                ],
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "pinned V1 logical identity",
            ):
                self.verify_android_release_build_output_fixture(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.write_android_release_build_output_fixture(root)
            mapping_directory = fixture["mappingDirectory"]
            aab_path = fixture["aabPath"]
            assert isinstance(mapping_directory, Path)
            assert isinstance(aab_path, Path)
            mapping_path = mapping_directory / "mapping.txt"
            mapping = mapping_path.read_bytes()
            mapping_header = b"".join(mapping.splitlines(keepends=True)[:7])
            mapping_body = b"".join(mapping.splitlines(keepends=True)[7:])
            mapping_body += b"fixture.ComposeStackTrace -> $$compose:\n"
            old_hash = re.search(
                rb"# pg_map_hash: SHA-256 ([0-9a-f]{64})\n",
                mapping_header,
            )
            assert old_hash is not None
            mapping_header = mapping_header.replace(
                old_hash.group(1),
                hashlib.sha256(mapping_body).hexdigest().encode("ascii"),
            )
            coordinated_mapping = mapping_header + mapping_body
            mapping_path.write_bytes(coordinated_mapping)
            self.replace_fixture_zip_member(
                aab_path,
                (
                    "BUNDLE-METADATA/com.android.tools.build.obfuscation/"
                    "proguard.map"
                ),
                coordinated_mapping,
            )
            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "mapping.txt differs from the pinned V1 byte identity",
            ):
                self.verify_android_release_build_output_fixture(root)

    def android_metadata_fixture(
        self,
        build_number: int,
    ) -> tuple[
        dict[str, object],
        bytes,
        bytes,
        bytes,
        list[tuple[bool, bool]],
        list[tuple[bool, bool, bool]],
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
        application_shell = expected_application_shell()
        apk_requirements: list[tuple[bool, bool]] = []
        aab_requirements: list[tuple[bool, bool, bool]] = []

        def inspect_apk_policy(
            apk_data: bytes,
            root: Path,
            *,
            entry_point_topology_required: bool = False,
            application_shell_required: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(apk_data, b"fixture-apk")
            apk_requirements.append(
                (
                    entry_point_topology_required,
                    application_shell_required,
                )
            )
            result: dict[str, object] = {
                "allowBackup": False,
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
            }
            if entry_point_topology_required:
                result["entryPointTopology"] = copy.deepcopy(topology)
            if application_shell_required:
                result["applicationShell"] = copy.deepcopy(
                    application_shell
                )
            return result

        def inspect_aab(
            aab_data: bytes,
            root: Path,
            *,
            backup_policy_required: bool = False,
            entry_point_topology_required: bool = False,
            application_shell_required: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(aab_data, aab)
            aab_requirements.append(
                (
                    backup_policy_required,
                    entry_point_topology_required,
                    application_shell_required,
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
            if application_shell_required:
                result["applicationShell"] = copy.deepcopy(
                    application_shell
                )
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
        apk_application_shell: dict[str, object] | None = None,
        aab_application_shell: dict[str, object] | None = None,
    ) -> tuple[
        list[tuple[bool, bool]],
        list[tuple[bool, bool, bool]],
    ]:
        topology = expected_entry_point_topology()
        application_shell = expected_application_shell()
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
        apk_application_shell = (
            copy.deepcopy(application_shell)
            if apk_application_shell is None
            else apk_application_shell
        )
        aab_application_shell = (
            copy.deepcopy(application_shell)
            if aab_application_shell is None
            else aab_application_shell
        )
        apk_requirements: list[tuple[bool, bool]] = []
        aab_requirements: list[tuple[bool, bool, bool]] = []

        def inspect_apk_policy(
            apk_data: bytes,
            *,
            entry_point_topology_required: bool = False,
            application_shell_required: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(apk_data, b"fixture-apk")
            apk_requirements.append(
                (
                    entry_point_topology_required,
                    application_shell_required,
                )
            )
            result: dict[str, object] = {
                "allowBackup": False,
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
            }
            if entry_point_topology_required:
                result["entryPointTopology"] = copy.deepcopy(
                    apk_topology
                )
            if application_shell_required:
                result["applicationShell"] = copy.deepcopy(
                    apk_application_shell
                )
            return result

        def inspect_aab(
            aab_data: bytes,
            *,
            backup_policy_required: bool = False,
            entry_point_topology_required: bool = False,
            application_shell_required: bool = False,
        ) -> dict[str, object]:
            self.assertEqual(aab_data, aab)
            aab_requirements.append(
                (
                    backup_policy_required,
                    entry_point_topology_required,
                    application_shell_required,
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
            if application_shell_required:
                result["applicationShell"] = copy.deepcopy(
                    aab_application_shell
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
            (root / builder_module.SOURCE_REQUIRED_FILES[0]).write_bytes(b"")

            snapshot = builder_module.source_snapshot(root)
            self.assertEqual(
                readback_module.current_source_snapshot_summary(root),
                {
                    key: snapshot[key]
                    for key in ("algorithm", "fileCount", "sha256")
                },
            )
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

    def test_current_source_g6_lifecycle_closure_is_required_once(
        self,
    ) -> None:
        required = (
            "script/run_clean_release_reproducibility.py",
            "script/run_macos_build24_idle_resource_stability_smoke.py",
            (
                "script/run_macos_current_source_lane_a_"
                "idle_resource_stability_smoke.py"
            ),
            (
                "script/test_run_macos_current_source_lane_a_"
                "idle_resource_stability_smoke.py"
            ),
        )
        self.assertEqual(
            readback_module.SOURCE_REQUIRED_FILES,
            builder_module.SOURCE_REQUIRED_FILES,
        )
        self.assertEqual(readback_module.ROOT, builder_module.ROOT)
        for relative in required:
            with self.subTest(relative=relative):
                self.assertEqual(
                    builder_module.SOURCE_REQUIRED_FILES.count(relative),
                    1,
                )
                self.assertEqual(
                    readback_module.SOURCE_REQUIRED_FILES.count(relative),
                    1,
                )
                status = (builder_module.ROOT / relative).lstat()
                self.assertTrue(stat.S_ISREG(status.st_mode))

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

    def test_unsealed_macos_output_publication_is_atomic_and_fail_closed(
        self,
    ) -> None:
        with mock.patch.object(builder_module.sys, "platform", "darwin"):
            self.assertEqual(
                builder_module._renameat_platform_contract(),
                ("renameatx_np", -2),
            )
        with mock.patch.object(builder_module.sys, "platform", "linux"):
            self.assertEqual(
                builder_module._renameat_platform_contract(),
                ("renameat2", -100),
            )
        with (
            mock.patch.object(builder_module.sys, "platform", "freebsd"),
            self.assertRaisesRegex(
                builder_module.ReleaseArchiveError,
                "unsupported on freebsd",
            ),
        ):
            builder_module._renameat_platform_contract()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "dist"
            parent.mkdir()
            destination = parent / "unsealed-package-only"
            destination.mkdir()
            (destination / "old.txt").write_bytes(b"old\n")
            staging = parent / ".unsealed-package-only.stage-fixture"
            staging.mkdir()
            (staging / "AetherLink.app").mkdir()
            (staging / "AetherLink.dSYM").mkdir()
            (
                staging / builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME
            ).write_bytes(b"{}\n")

            with mock.patch.object(
                readback_module,
                "verify_macos_release_build_outputs",
                return_value={"verified": True},
            ) as verify_staging:
                replaced = builder_module.publish_unsealed_macos_output(
                    staging,
                    root=root,
                )

            self.assertTrue(replaced)
            self.assertEqual(
                verify_staging.call_args_list,
                [
                    mock.call(root=root, output_root=staging),
                    mock.call(root=root, output_root=destination),
                ],
            )
            self.assertEqual(
                {path.name for path in destination.iterdir()},
                {
                    "AetherLink.app",
                    "AetherLink.dSYM",
                    builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME,
                },
            )
            self.assertFalse(staging.exists())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "dist"
            parent.mkdir()
            destination = parent / "unsealed-package-only"
            destination.mkdir()
            old = destination / "old.txt"
            old.write_bytes(b"old\n")
            staging = parent / ".unsealed-package-only.stage-fixture"
            staging.mkdir()
            (staging / "AetherLink.app").mkdir()
            (staging / "AetherLink.dSYM").mkdir()
            (
                staging / builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME
            ).write_bytes(b"{}\n")

            with (
                mock.patch.object(
                    readback_module,
                    "verify_macos_release_build_outputs",
                    return_value={"verified": True},
                ),
                mock.patch.object(
                    builder_module,
                    "_atomic_exchange_directories",
                    side_effect=builder_module.ReleaseArchiveError(
                        "injected exchange failure"
                    ),
                ),
                self.assertRaisesRegex(
                    builder_module.ReleaseArchiveError,
                    "injected exchange failure",
                ),
            ):
                builder_module.publish_unsealed_macos_output(
                    staging,
                    root=root,
                )

            self.assertEqual(old.read_bytes(), b"old\n")
            self.assertTrue(staging.is_dir())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "dist"
            parent.mkdir()
            destination = parent / "unsealed-package-only"
            destination.mkdir()
            old = destination / "old.txt"
            old.write_bytes(b"old\n")
            staging = parent / ".unsealed-package-only.stage-fixture"
            staging.mkdir()
            (staging / "AetherLink.app").mkdir()
            (staging / "AetherLink.dSYM").mkdir()
            (
                staging / builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME
            ).write_bytes(b"{}\n")

            with (
                mock.patch.object(
                    readback_module,
                    "verify_macos_release_build_outputs",
                    side_effect=(
                        {"verified": True},
                        ReleaseArchiveVerificationError(
                            "injected post-publication failure"
                        ),
                    ),
                ),
                self.assertRaisesRegex(
                    builder_module.ReleaseArchiveError,
                    "previous generation was restored",
                ),
            ):
                builder_module.publish_unsealed_macos_output(
                    staging,
                    root=root,
                )

            self.assertEqual(old.read_bytes(), b"old\n")
            self.assertEqual(
                {path.name for path in staging.iterdir()},
                {
                    "AetherLink.app",
                    "AetherLink.dSYM",
                    builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME,
                },
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "dist"
            parent.mkdir()
            destination = parent / "unsealed-package-only"
            destination.mkdir()
            (destination / "old.txt").write_bytes(b"old\n")
            staging = parent / ".unsealed-package-only.stage-fixture"
            staging.mkdir()
            (staging / "AetherLink.app").mkdir()
            (staging / "AetherLink.dSYM").mkdir()
            (
                staging / builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME
            ).write_bytes(b"{}\n")
            real_exchange = builder_module._atomic_exchange_directories
            exchange_count = 0

            def fail_rollback(first: Path, second: Path) -> None:
                nonlocal exchange_count
                exchange_count += 1
                if exchange_count == 1:
                    real_exchange(first, second)
                    return
                raise builder_module.ReleaseArchiveError(
                    "injected rollback failure"
                )

            with (
                mock.patch.object(
                    readback_module,
                    "verify_macos_release_build_outputs",
                    side_effect=(
                        {"verified": True},
                        ReleaseArchiveVerificationError(
                            "injected post-publication failure"
                        ),
                    ),
                ),
                mock.patch.object(
                    builder_module,
                    "_atomic_exchange_directories",
                    side_effect=fail_rollback,
                ),
                self.assertRaisesRegex(
                    builder_module.ReleaseArchiveError,
                    "previous generation was preserved at",
                ),
            ):
                builder_module.publish_unsealed_macos_output(
                    staging,
                    root=root,
                )

            recovery = parent / ".unsealed-package-only.recovery-fixture"
            self.assertEqual((recovery / "old.txt").read_bytes(), b"old\n")
            self.assertFalse(staging.exists())
            self.assertEqual(
                {path.name for path in destination.iterdir()},
                {
                    "AetherLink.app",
                    "AetherLink.dSYM",
                    builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME,
                },
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "dist"
            parent.mkdir()
            destination = parent / "unsealed-package-only"
            destination.mkdir()
            (destination / "old.txt").write_bytes(b"old\n")
            staging = parent / ".unsealed-package-only.stage-fixture"
            staging.mkdir()
            (staging / "AetherLink.app").mkdir()
            (staging / "AetherLink.dSYM").mkdir()
            (
                staging / builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME
            ).write_bytes(b"{}\n")
            stderr = io.StringIO()

            with (
                mock.patch.object(
                    readback_module,
                    "verify_macos_release_build_outputs",
                    return_value={"verified": True},
                ),
                mock.patch.object(
                    builder_module.shutil,
                    "rmtree",
                    side_effect=OSError("injected cleanup failure"),
                ),
                mock.patch("sys.stderr", stderr),
            ):
                replaced = builder_module.publish_unsealed_macos_output(
                    staging,
                    root=root,
                )

            self.assertTrue(replaced)
            self.assertEqual(
                {path.name for path in destination.iterdir()},
                {
                    "AetherLink.app",
                    "AetherLink.dSYM",
                    builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME,
                },
            )
            self.assertEqual((staging / "old.txt").read_bytes(), b"old\n")
            self.assertIn("passed post-publication readback", stderr.getvalue())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "dist"
            parent.mkdir()
            destination = parent / "unsealed-package-only"
            destination.mkdir()
            old = destination / "old.txt"
            old.write_bytes(b"old\n")
            staging = parent / ".unsealed-package-only.stage-fixture"
            staging.mkdir()
            (staging / "AetherLink.app").mkdir()
            (staging / "AetherLink.dSYM").mkdir()
            (
                staging / builder_module.UNSEALED_MACOS_SOURCE_RECEIPT_NAME
            ).write_bytes(b"{}\n")

            with (
                mock.patch.object(
                    readback_module,
                    "verify_macos_release_build_outputs",
                    side_effect=ReleaseArchiveVerificationError(
                        "invalid staged generation"
                    ),
                ),
                self.assertRaisesRegex(
                    builder_module.ReleaseArchiveError,
                    "failed independent readback: invalid staged generation",
                ),
            ):
                builder_module.publish_unsealed_macos_output(
                    staging,
                    root=root,
                )

            self.assertEqual(old.read_bytes(), b"old\n")
            self.assertTrue(staging.is_dir())

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

    def test_apk_inspectors_read_exact_compiled_application_shell(
        self,
    ) -> None:
        expected = {
            "allowBackup": False,
            "applicationShell": expected_application_shell(),
            "dataExtractionRules": "@xml/data_extraction_rules",
            "entryPointTopology": expected_entry_point_topology(),
            "fullBackupContent": "@xml/backup_rules",
        }
        for module in (builder_module, readback_module):
            temporary_paths: list[Path] = []
            commands: list[tuple[str, str]] = []

            def fake_dump(command: list[str], root: Path) -> str:
                temporary_path = Path(command[-1])
                self.assertEqual(
                    temporary_path.read_bytes(),
                    b"fixture-apk",
                )
                temporary_paths.append(temporary_path)
                if command[2] == "xmltree":
                    file_name = command[4]
                    commands.append(("xmltree", file_name))
                    return {
                        "AndroidManifest.xml": (
                            self.AAPT2_COMPILED_APPLICATION_SHELL_XMLTREE
                        ),
                        "res/Qq.xml": self.AAPT2_BACKUP_RULES_XMLTREE,
                        "res/4j.xml": (
                            self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE
                        ),
                        "res/Br.xml": self.AAPT2_LOCALE_CONFIG_XMLTREE,
                    }[file_name]
                stage = (
                    "no-values"
                    if "--no-values" in command
                    else "values"
                )
                commands.append(("resources", stage))
                return (
                    self.AAPT2_APPLICATION_SHELL_RESOURCES
                    if stage == "no-values"
                    else self.AAPT2_APPLICATION_SHELL_RESOURCES_WITH_VALUES
                )

            with (
                self.subTest(module=module.__name__),
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
                        application_shell_required=True,
                    ),
                    expected,
                )
            self.assertEqual(
                commands,
                [
                    ("xmltree", "AndroidManifest.xml"),
                    ("resources", "no-values"),
                    ("resources", "values"),
                    ("xmltree", "res/Qq.xml"),
                    ("xmltree", "res/4j.xml"),
                    ("xmltree", "res/Br.xml"),
                ],
            )
            self.assertEqual(len(set(temporary_paths)), 1)
            self.assertTrue(
                all(not path.exists() for path in temporary_paths)
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
                self.assertEqual(
                    module.parse_aapt2_xml_resource_paths(
                        self.AAPT2_RESOURCES_WITH_VALUES,
                        application_shell_required=True,
                    ),
                    {
                        **expected_paths,
                        "locales_config": "res/Br.xml",
                    },
                )
                module.validate_aapt2_backup_policy_xmltrees(
                    self.AAPT2_BACKUP_RULES_XMLTREE,
                    self.AAPT2_DATA_EXTRACTION_RULES_XMLTREE,
                )
                with self.assertRaises(error_type):
                    module.parse_aapt2_xml_resource_paths(
                        self.AAPT2_RESOURCES_WITH_VALUES,
                        application_shell_required=1,
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

    def test_builder_and_readback_parse_exact_application_shell(
        self,
    ) -> None:
        expected = expected_application_shell()
        for module, error_type in (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        ):
            with self.subTest(module=module.__name__):
                self.assertEqual(
                    module.parse_aapt2_application_shell_manifest(
                        self.AAPT2_APPLICATION_SHELL_XMLTREE,
                        self.AAPT2_APPLICATION_SHELL_RESOURCES,
                    ),
                    expected["manifestResources"],
                )
                self.assertEqual(
                    module.parse_aapt2_locale_config(
                        self.AAPT2_LOCALE_CONFIG_XMLTREE
                    ),
                    expected["localeConfigLocales"],
                )
                self.assertEqual(
                    module.parse_aapt2_localized_string(
                        self.AAPT2_LOCALIZED_STRING_RESOURCES
                    ),
                    expected["localizedString"],
                )
                self.assertEqual(
                    module.parse_bundletool_localized_string(
                        self.BUNDLETOOL_LOCALIZED_STRING
                    ),
                    expected["localizedString"],
                )
                self.assertIsNone(
                    module.parse_bundletool_language_split_contract(
                        self.BUNDLETOOL_LANGUAGE_SPLIT_CONFIG
                    )
                )
                parsed_manifest = module.parse_bundletool_manifest(
                    self.BUNDLETOOL_APPLICATION_SHELL_MANIFEST,
                    backup_policy_required=True,
                    application_shell_required=True,
                )
                self.assertEqual(
                    parsed_manifest["applicationShell"],
                    {
                        "manifestResources": (
                            expected["manifestResources"]
                        )
                    },
                )
                historical = module.parse_bundletool_manifest(
                    self.BUNDLETOOL_APPLICATION_SHELL_MANIFEST,
                    backup_policy_required=True,
                )
                self.assertNotIn("applicationShell", historical)
                with self.assertRaises(error_type):
                    module.parse_bundletool_manifest(
                        self.BUNDLETOOL_APPLICATION_SHELL_MANIFEST,
                        backup_policy_required=True,
                        application_shell_required=1,
                    )

    def test_aapt2_application_shell_parsers_reject_mutations(
        self,
    ) -> None:
        expected = expected_application_shell()
        manifest = self.AAPT2_APPLICATION_SHELL_XMLTREE
        resources = self.AAPT2_APPLICATION_SHELL_RESOURCES
        android = "http://schemas.android.com/apk/res/android:"
        manifest_lines = {
            "icon": f"        A: {android}icon(0x01010002)=@0x7f0e0000\n",
            "label": f"        A: {android}label(0x01010001)=@0x7f120000\n",
            "localeConfig": (
                f"        A: {android}localeConfig(0x01010654)"
                "=@0x7f110002\n"
            ),
            "roundIcon": (
                f"        A: {android}roundIcon(0x0101052c)"
                "=@0x7f0e0001\n"
            ),
            "theme": (
                f"        A: {android}theme(0x01010000)=@0x7f130000\n"
            ),
        }
        invalid_manifest_pairs: list[tuple[str, str]] = []
        for line in manifest_lines.values():
            invalid_manifest_pairs.extend(
                (
                    (manifest.replace(line, ""), resources),
                    (
                        manifest.replace(
                            line,
                            line.replace(android, ""),
                        ),
                        resources,
                    ),
                    (manifest.replace(line, line + line), resources),
                    (
                        manifest.replace(
                            line,
                            line + line.replace(android, ""),
                        ),
                        resources,
                    ),
                )
            )
        invalid_manifest_pairs.extend(
            (
                (
                    manifest.replace("@0x7f0e0000", "@0x7f0e0001"),
                    resources,
                ),
                (
                    manifest,
                    resources.replace(
                        "mipmap/ic_launcher\n",
                        "drawable/ic_launcher\n",
                    ),
                ),
                (
                    manifest,
                    resources.replace(
                        "    resource 0x7f130000 style/AppTheme\n",
                        "",
                    ),
                ),
                (
                    manifest,
                    resources
                    + "    resource 0x7f130000 style/AppTheme\n",
                ),
            )
        )

        invalid_locale_configs = (
            self.AAPT2_LOCALE_CONFIG_XMLTREE.replace(
                "      E: locale (line=7)\n"
                "        A: http://schemas.android.com/apk/res/android:"
                'name(0x01010003)="fr" (Raw: "fr")\n',
                "",
            ),
            self.AAPT2_LOCALE_CONFIG_XMLTREE
            + "      E: locale (line=8)\n"
            + "        A: http://schemas.android.com/apk/res/android:"
            + 'name(0x01010003)="de" (Raw: "de")\n',
            self.AAPT2_LOCALE_CONFIG_XMLTREE.replace(
                'name(0x01010003)="fr" (Raw: "fr")',
                'name(0x01010003)="zh-CN" (Raw: "zh-CN")',
            ),
            self.AAPT2_LOCALE_CONFIG_XMLTREE.replace(
                'name(0x01010003)="en" (Raw: "en")',
                "__LOCALE_PLACEHOLDER__",
            ).replace(
                'name(0x01010003)="ko" (Raw: "ko")',
                'name(0x01010003)="en" (Raw: "en")',
            ).replace(
                "__LOCALE_PLACEHOLDER__",
                'name(0x01010003)="ko" (Raw: "ko")',
            ),
            self.AAPT2_LOCALE_CONFIG_XMLTREE.replace(
                "http://schemas.android.com/apk/res/android:name",
                "name",
                1,
            ),
            self.AAPT2_LOCALE_CONFIG_XMLTREE.replace(
                '(Raw: "zh-CN")',
                '(Raw: "zh-rCN")',
            ),
        )
        invalid_localized_resources = (
            self.AAPT2_LOCALIZED_STRING_RESOURCES.replace(
                '      (fr) "Jumelage et connexion"\n',
                "",
            ),
            self.AAPT2_LOCALIZED_STRING_RESOURCES
            + '      (de) "Kopplung und Verbindung"\n',
            self.AAPT2_LOCALIZED_STRING_RESOURCES.replace(
                '      (en) "Pairing & Connection"\n',
                '      (en) "Pairing & Connection"\n'
                '      (en) "Pairing & Connection"\n',
            ),
            self.AAPT2_LOCALIZED_STRING_RESOURCES.replace(
                '      (ko) "페어링 및 연결"',
                '      (ko) "연결"',
            ),
            self.AAPT2_LOCALIZED_STRING_RESOURCES.replace(
                "string/status_title",
                "string/status",
            ),
            self.AAPT2_LOCALIZED_STRING_RESOURCES.replace(
                "(zh-rCN)",
                "(zh-CN)",
            ),
        )

        for module, error_type in (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        ):
            for changed_manifest, changed_resources in (
                invalid_manifest_pairs
            ):
                with (
                    self.subTest(
                        module=module.__name__,
                        manifest=changed_manifest,
                        resources=changed_resources,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.parse_aapt2_application_shell_manifest(
                        changed_manifest,
                        changed_resources,
                    )
            for changed_locale_config in invalid_locale_configs:
                with (
                    self.subTest(
                        module=module.__name__,
                        locale_config=changed_locale_config,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.parse_aapt2_locale_config(
                        changed_locale_config
                    )
            for changed_resources in invalid_localized_resources:
                with (
                    self.subTest(
                        module=module.__name__,
                        resources=changed_resources,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.parse_aapt2_localized_string(
                        changed_resources
                    )

        self.assertEqual(
            expected["localeConfigLocales"],
            ["en", "ko", "ja", "zh-CN", "fr"],
        )

    def test_bundletool_application_shell_parsers_reject_mutations(
        self,
    ) -> None:
        manifest = self.BUNDLETOOL_APPLICATION_SHELL_MANIFEST
        manifest_attributes = (
            'android:icon="@mipmap/ic_launcher"',
            'android:label="@string/app_name"',
            'android:localeConfig="@xml/locales_config"',
            'android:roundIcon="@mipmap/ic_launcher_round"',
            'android:theme="@style/AppTheme"',
        )
        invalid_manifests: list[str] = []
        for attribute in manifest_attributes:
            invalid_manifests.extend(
                (
                    manifest.replace(f" {attribute}", ""),
                    manifest.replace(attribute, attribute.replace("android:", "")),
                    manifest.replace(attribute, f"{attribute} {attribute}"),
                    manifest.replace(
                        attribute,
                        f"{attribute} {attribute.replace('android:', '')}",
                    ),
                    manifest.replace(
                        attribute,
                        attribute.replace("@", "@drawable/changed#", 1),
                    ),
                )
            )

        localized_string = self.BUNDLETOOL_LOCALIZED_STRING
        invalid_localized_strings = (
            localized_string.replace(
                '\tlocale: "fr" - [STR] "Jumelage et connexion"\n',
                "",
            ),
            localized_string
            + '\tlocale: "de" - [STR] "Kopplung und Verbindung"\n',
            localized_string.replace(
                '\tlocale: "en" - [STR] "Pairing & Connection"\n',
                '\tlocale: "en" - [STR] "Pairing & Connection"\n'
                '\tlocale: "en" - [STR] "Pairing & Connection"\n',
            ),
            localized_string.replace(
                '"ja" - [STR] "ペアリングと接続"',
                '"ja" - [STR] "接続"',
            ),
            localized_string.replace(
                "string/status_title",
                "string/status",
            ),
            localized_string.replace(
                'locale: "zh-CN"',
                'locale: "zh-rCN"',
            ),
        )
        invalid_language_configs = (
            '{"optimizations":{"splitsConfig":{"splitDimension":'
            '[{"value":"LANGUAGE"}]}}}',
            '{"optimizations":{"splitsConfig":{"splitDimension":'
            '[{"negate":false,"value":"LANGUAGE"}]}}}',
            '{"optimizations":{"splitsConfig":{"splitDimension":'
            '[{"negate":true,"value":"ABI"}]}}}',
            '{"optimizations":{"splitsConfig":{"splitDimension":'
            '[{"negate":true,"value":"LANGUAGE"},'
            '{"negate":true,"value":"LANGUAGE"}]}}}',
            '{"optimizations":{"splitsConfig":{"splitDimension":'
            '[0,{"negate":true,"value":"LANGUAGE"}]}}}',
        )

        for module, error_type in (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        ):
            for changed_manifest in invalid_manifests:
                with (
                    self.subTest(
                        module=module.__name__,
                        manifest=changed_manifest,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.parse_bundletool_manifest(
                        changed_manifest,
                        backup_policy_required=True,
                        application_shell_required=True,
                    )
            for changed_localized_string in invalid_localized_strings:
                with (
                    self.subTest(
                        module=module.__name__,
                        localized_string=changed_localized_string,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.parse_bundletool_localized_string(
                        changed_localized_string
                    )
            for changed_config in invalid_language_configs:
                with (
                    self.subTest(
                        module=module.__name__,
                        config=changed_config,
                    ),
                    self.assertRaises(error_type),
                ):
                    module.parse_bundletool_language_split_contract(
                        changed_config
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

    def test_application_shell_claim_is_exact_typed_and_build_gated(
        self,
    ) -> None:
        expected = expected_application_shell()
        self.assertEqual(
            readback_module.verify_android_application_shell_claim(
                copy.deepcopy(expected)
            ),
            expected,
        )

        invalid: list[object] = [None, [], "applicationShell"]
        for key in expected:
            missing = copy.deepcopy(expected)
            del missing[key]
            invalid.append(missing)
        extra_root = copy.deepcopy(expected)
        extra_root["renderedOnDevice"] = True
        invalid.append(extra_root)

        manifest_resources = expected["manifestResources"]
        assert isinstance(manifest_resources, dict)
        non_object_manifest = copy.deepcopy(expected)
        non_object_manifest["manifestResources"] = []
        invalid.append(non_object_manifest)
        for key in manifest_resources:
            missing = copy.deepcopy(expected)
            del missing["manifestResources"][key]
            invalid.append(missing)
            wrong = copy.deepcopy(expected)
            wrong["manifestResources"][key] = True
            invalid.append(wrong)
        extra_manifest_key = copy.deepcopy(expected)
        extra_manifest_key["manifestResources"]["banner"] = (
            "@drawable/banner"
        )
        invalid.append(extra_manifest_key)

        tuple_locales = copy.deepcopy(expected)
        tuple_locales["localeConfigLocales"] = tuple(
            tuple_locales["localeConfigLocales"]
        )
        invalid.append(tuple_locales)
        for locales in (
            ["en", "ko", "ja", "fr"],
            ["en", "ko", "ja", "zh-CN", "fr", "de"],
            ["en", "ko", "ja", "zh-CN", "zh-CN"],
            ["fr", "zh-CN", "ja", "ko", "en"],
            ["en", "ko", "ja", "zh-rCN", "fr"],
            ["en", "ko", "ja", "zh-CN", 1],
        ):
            changed = copy.deepcopy(expected)
            changed["localeConfigLocales"] = locales
            invalid.append(changed)

        localized_string = expected["localizedString"]
        assert isinstance(localized_string, dict)
        non_object_localized = copy.deepcopy(expected)
        non_object_localized["localizedString"] = []
        invalid.append(non_object_localized)
        for key in localized_string:
            missing = copy.deepcopy(expected)
            del missing["localizedString"][key]
            invalid.append(missing)
        extra_localized_key = copy.deepcopy(expected)
        extra_localized_key["localizedString"]["formatted"] = False
        invalid.append(extra_localized_key)
        wrong_resource = copy.deepcopy(expected)
        wrong_resource["localizedString"]["resource"] = (
            "@string/app_name"
        )
        invalid.append(wrong_resource)
        non_object_values = copy.deepcopy(expected)
        non_object_values["localizedString"]["values"] = []
        invalid.append(non_object_values)
        localized_values = localized_string["values"]
        assert isinstance(localized_values, dict)
        for key in localized_values:
            missing = copy.deepcopy(expected)
            del missing["localizedString"]["values"][key]
            invalid.append(missing)
            wrong = copy.deepcopy(expected)
            wrong["localizedString"]["values"][key] = True
            invalid.append(wrong)
        extra_value = copy.deepcopy(expected)
        extra_value["localizedString"]["values"]["de"] = (
            "Kopplung und Verbindung"
        )
        invalid.append(extra_value)

        for value in invalid:
            with self.subTest(value=value), self.assertRaises(
                ReleaseArchiveVerificationError
            ):
                readback_module.verify_android_application_shell_claim(
                    value
                )

        for build_number in range(1, 23):
            with self.subTest(build_number=build_number):
                self.assertNotIn(
                    "applicationShell",
                    readback_module.expected_android_manifest_keys(
                        build_number
                    ),
                )
        self.assertIn(
            "applicationShell",
            readback_module.expected_android_manifest_keys(23),
        )
        self.assertEqual(
            builder_module.ANDROID_APPLICATION_SHELL_BUILD,
            23,
        )
        self.assertEqual(
            readback_module.ANDROID_APPLICATION_SHELL_BUILD,
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
                application_shell_required = build_number >= 23
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
                    "applicationShell" in metadata,
                    application_shell_required,
                )
                self.assertEqual(
                    builder_apk_requirements,
                    [
                        (
                            topology_required,
                            application_shell_required,
                        )
                    ],
                )
                self.assertEqual(
                    builder_aab_requirements,
                    [
                        (
                            True,
                            topology_required,
                            application_shell_required,
                        )
                    ],
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
                    *(
                        builder_module
                        .APPLICATION_SHELL_MANIFEST_VERIFIED_FIELDS
                        if application_shell_required
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
                    *(
                        builder_module
                        .APPLICATION_SHELL_MANIFEST_VERIFIED_FIELDS
                        if application_shell_required
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
                    [
                        (
                            topology_required,
                            application_shell_required,
                        )
                    ],
                )
                self.assertEqual(
                    readback_aab_requirements,
                    [
                        (
                            True,
                            topology_required,
                            application_shell_required,
                        )
                    ],
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

    def test_android_readback_rejects_build23_application_shell_wiring_drift(
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

        def changed_application_shell() -> dict[str, object]:
            value = expected_application_shell()
            value["localizedString"]["values"]["fr"] = "Connexion"
            return value

        changed_claim = copy.deepcopy(metadata)
        changed_claim["applicationShell"] = changed_application_shell()
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
                apk_application_shell=changed_application_shell(),
            )

        with self.assertRaises(ReleaseArchiveVerificationError):
            self.verify_android_metadata_fixture(
                metadata,
                build_number=23,
                aab=aab,
                mapping=mapping,
                native=native,
                aab_application_shell=changed_application_shell(),
            )

        for readback_key in (
            "bundleManifestReadback",
            "apkManifestReadback",
        ):
            missing_verified_field = copy.deepcopy(metadata)
            missing_verified_field[readback_key][
                "verifiedFields"
            ].remove("applicationShell")
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
        del missing_claim["applicationShell"]
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
        historical_metadata["applicationShell"] = (
            expected_application_shell()
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
                *,
                application_shell_required: bool = False,
            ) -> dict[str, object]:
                self.assertEqual(path.read_bytes(), b"fixture-aab")
                self.assertFalse(application_shell_required)
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

    def test_aab_inspectors_read_direct_and_universal_application_shell(
        self,
    ) -> None:
        application_shell = expected_application_shell()
        expected = {
            "allowBackup": False,
            "applicationId": "com.localagentbridge.android",
            "applicationShell": application_shell,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "fullBackupContent": "@xml/backup_rules",
            "minSdk": 26,
            "targetSdk": 36,
            "versionCode": 1,
            "versionName": "1.0.0",
        }
        for module, error_type in (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        ):
            commands: list[list[str]] = []
            temporary_paths: list[Path] = []

            def fake_run(
                arguments: list[str],
                *,
                root: Path,
            ) -> str:
                commands.append(list(arguments))
                bundle_argument = next(
                    argument
                    for argument in arguments
                    if argument.startswith("--bundle=")
                )
                bundle_path = Path(
                    bundle_argument.removeprefix("--bundle=")
                )
                self.assertEqual(bundle_path.read_bytes(), b"fixture-aab")
                temporary_paths.append(bundle_path)
                if arguments[0] == "validate":
                    return self.BUNDLETOOL_VALIDATE_OUTPUT
                if arguments[1] == "manifest":
                    return self.BUNDLETOOL_APPLICATION_SHELL_MANIFEST
                if arguments[1] == "resources":
                    return self.BUNDLETOOL_LOCALIZED_STRING
                if arguments[1] == "config":
                    return self.BUNDLETOOL_LANGUAGE_SPLIT_CONFIG
                self.fail(f"unexpected bundletool arguments: {arguments!r}")

            universal_requirements: list[bool] = []

            def fake_universal_readback(
                path: Path,
                root: Path,
                *,
                application_shell_required: bool = False,
            ) -> dict[str, object]:
                self.assertEqual(path.read_bytes(), b"fixture-aab")
                universal_requirements.append(
                    application_shell_required
                )
                return {
                    "allowBackup": False,
                    "applicationShell": copy.deepcopy(
                        application_shell
                    ),
                    "dataExtractionRules": (
                        "@xml/data_extraction_rules"
                    ),
                    "fullBackupContent": "@xml/backup_rules",
                }

            with (
                self.subTest(module=module.__name__),
                mock.patch.object(
                    module,
                    "run_bundletool",
                    side_effect=fake_run,
                ),
                mock.patch.object(
                    module,
                    "inspect_aab_backup_policy",
                    side_effect=fake_universal_readback,
                ),
            ):
                self.assertEqual(
                    module.inspect_aab_manifest(
                        b"fixture-aab",
                        backup_policy_required=True,
                        application_shell_required=True,
                    ),
                    expected,
                )
            self.assertEqual(universal_requirements, [True])
            self.assertEqual(
                [command[:2] for command in commands],
                [
                    ["validate", commands[0][1]],
                    ["dump", "manifest"],
                    ["dump", "resources"],
                    ["dump", "config"],
                ],
            )
            self.assertIn(
                "--resource=string/status_title",
                commands[2],
            )
            self.assertIn("--values", commands[2])
            self.assertEqual(len(set(temporary_paths)), 1)
            self.assertTrue(
                all(not path.exists() for path in temporary_paths)
            )

            changed_shell = copy.deepcopy(application_shell)
            changed_shell["localizedString"]["values"]["ko"] = "연결"
            with (
                self.subTest(module=module.__name__, drift="universal"),
                mock.patch.object(
                    module,
                    "run_bundletool",
                    side_effect=fake_run,
                ),
                mock.patch.object(
                    module,
                    "inspect_aab_backup_policy",
                    return_value={
                        "allowBackup": False,
                        "applicationShell": changed_shell,
                        "dataExtractionRules": (
                            "@xml/data_extraction_rules"
                        ),
                        "fullBackupContent": "@xml/backup_rules",
                    },
                ),
                self.assertRaises(error_type),
            ):
                module.inspect_aab_manifest(
                    b"fixture-aab",
                    backup_policy_required=True,
                    application_shell_required=True,
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
        release_commands = (
            "python3 script/check_release_version_ledger.py --artifacts",
            (
                "python3 script/check_release_artifact_archive.py "
                "--android-build-outputs"
            ),
            "python3 script/package_release_artifacts.py create",
            "python3 script/check_release_artifact_archive.py",
        )
        self.assertEqual(
            tuple(release_script.splitlines()[-4:]),
            release_commands,
        )
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
