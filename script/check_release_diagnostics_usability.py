#!/usr/bin/env python3
"""Independently read back one current Release diagnostics usability result."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
from typing import Mapping, Sequence

if __package__:
    from script import run_release_diagnostics_usability as producer
else:
    import run_release_diagnostics_usability as producer


ROOT = Path(__file__).resolve().parents[1]


class EvidenceError(RuntimeError):
    """Raised when a diagnostics result does not match live Release bytes."""


class DuplicateKeyError(ValueError):
    pass


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def exact_keys(value: object, expected: set[str], label: str) -> Mapping[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise EvidenceError(f"{label} closed keys differ")
    return value


def load_result(path: Path) -> Mapping[str, object]:
    try:
        path_status = path.lstat()
    except OSError as error:
        raise EvidenceError(f"result cannot be statted: {error}") from error
    if (
        stat.S_ISLNK(path_status.st_mode)
        or not stat.S_ISREG(path_status.st_mode)
        or path_status.st_nlink != 1
        or stat.S_IMODE(path_status.st_mode) != 0o600
    ):
        raise EvidenceError("result must be one mode-0600 single-link regular file")
    try:
        raw = producer.read_regular_bytes(path, maximum_bytes=producer.RESULT_MAX_BYTES)
        value = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (producer.DiagnosticsError, DuplicateKeyError, json.JSONDecodeError) as error:
        raise EvidenceError(f"result cannot be decoded: {error}") from error
    if type(value) is not dict or raw != producer.canonical_json_bytes(value):
        raise EvidenceError("result must be canonical JSON")
    return value


def require_bool(value: object, expected: bool, label: str) -> None:
    if type(value) is not bool or value is not expected:
        raise EvidenceError(f"{label} must be {expected}")


def require_int(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise EvidenceError(f"{label} must be an integer >= {minimum}")
    return value


def require_text(
    value: object,
    label: str,
    *,
    pattern: str | None = None,
    maximum: int = 4096,
) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise EvidenceError(f"{label} must be bounded nonempty text")
    if pattern is not None and re.fullmatch(pattern, value) is None:
        raise EvidenceError(f"{label} has a noncanonical value")
    return value


def live_file_record(
    record: object,
    *,
    expected_path: Path,
    maximum_bytes: int,
    root: Path,
) -> bytes:
    value = exact_keys(record, {"path", "sha256", "size"}, str(expected_path))
    expected_relative = expected_path.as_posix()
    if value["path"] != expected_relative:
        raise EvidenceError(f"file path differs: {expected_relative}")
    require_int(value["size"], f"{expected_relative}.size")
    try:
        data = producer.read_regular_bytes(root / expected_path, maximum_bytes=maximum_bytes)
    except producer.DiagnosticsError as error:
        raise EvidenceError(f"file readback failed for {expected_relative}: {error}") from error
    expected = producer.file_record(root / expected_path, data, root=root)
    if value != expected:
        raise EvidenceError(f"file identity differs: {expected_relative}")
    return data


def live_external_tool_record(record: object, expected_path: Path) -> None:
    value = exact_keys(record, {"path", "sha256", "size"}, str(expected_path))
    require_int(value["size"], f"{expected_path}.size")
    try:
        expected = producer.tool_file_record(expected_path)
    except producer.DiagnosticsError as error:
        raise EvidenceError(f"tool readback failed for {expected_path}: {error}") from error
    if value != expected:
        raise EvidenceError(f"tool identity differs: {expected_path}")


def validate_implementation(document: Mapping[str, object], *, root: Path) -> None:
    implementation = document["implementation"]
    if type(implementation) is not list or len(implementation) != len(
        producer.IMPLEMENTATION_PATHS
    ):
        raise EvidenceError("implementation record set differs")
    for actual, relative in zip(implementation, producer.IMPLEMENTATION_PATHS):
        live_file_record(
            actual,
            expected_path=relative,
            maximum_bytes=producer.RESULT_MAX_BYTES,
            root=root,
        )


def validate_qualification(value: object) -> None:
    qualification = exact_keys(value, set(producer.QUALIFICATION), "qualification")
    for key, expected in producer.QUALIFICATION.items():
        require_bool(qualification[key], expected, f"qualification.{key}")


def source_readback(
    value: object,
    *,
    expected_roots: Sequence[Path],
    source_file: str,
    source_line: int,
    root: Path,
) -> None:
    record = exact_keys(
        value,
        {"line", "lineSha256", "path", "sha256", "size"},
        "probe.source",
    )
    recorded_line = require_int(
        record["line"],
        "probe.source.line",
        minimum=1,
    )
    if recorded_line != source_line:
        raise EvidenceError("probe source line differs")
    relative_text = require_text(record["path"], "probe.source.path")
    relative = Path(relative_text)
    if (
        relative.is_absolute()
        or relative.name != source_file
        or not any(relative == base or base in relative.parents for base in expected_roots)
    ):
        raise EvidenceError("probe source path is outside the declared source roots")
    data = live_file_record(
        {"path": relative_text, "sha256": record["sha256"], "size": record["size"]},
        expected_path=relative,
        maximum_bytes=producer.SOURCE_MAX_BYTES,
        root=root,
    )
    if b"\0" in data or b"\r" in data or not data.endswith(b"\n"):
        raise EvidenceError("probe source is not canonical UTF-8/LF text")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise EvidenceError("probe source is not UTF-8") from error
    lines = data.splitlines(keepends=True)
    if source_line > len(lines):
        raise EvidenceError("probe source line is outside the file")
    if record["lineSha256"] != producer.sha256(lines[source_line - 1]):
        raise EvidenceError("probe source line identity differs")


def validate_common(
    document: Mapping[str, object],
    *,
    expected_platform: str,
    root: Path,
) -> None:
    common = {
        "artifacts",
        "contract",
        "implementation",
        "platform",
        "prerequisiteReadbackSha256",
        "probe",
        "qualification",
        "result",
        "schemaVersion",
        "tool",
    }
    if expected_platform == "android":
        common.add("mapping")
    exact_keys(document, common, "result")
    schema_version = require_int(document["schemaVersion"], "schemaVersion", minimum=1)
    if (
        document["contract"] != producer.CONTRACT
        or schema_version != producer.SCHEMA_VERSION
        or document["platform"] != expected_platform
    ):
        raise EvidenceError("result contract, schema, or platform differs")
    require_text(
        document["prerequisiteReadbackSha256"],
        "prerequisiteReadbackSha256",
        pattern=r"[0-9a-f]{64}",
        maximum=64,
    )
    try:
        expected_prerequisite = producer.prerequisite_digest(expected_platform, root=root)
    except producer.DiagnosticsError as error:
        raise EvidenceError(f"prerequisite Release readback failed: {error}") from error
    if document["prerequisiteReadbackSha256"] != expected_prerequisite:
        raise EvidenceError("prerequisite Release readback identity differs")
    validate_implementation(document, root=root)
    validate_qualification(document["qualification"])


def validate_android(document: Mapping[str, object], *, root: Path) -> None:
    validate_common(document, expected_platform="android", root=root)
    if document["result"] != "android-r8-retrace-resolved-one-project-frame":
        raise EvidenceError("Android result marker differs")
    artifacts = exact_keys(document["artifacts"], {"aab", "apk", "mapping"}, "artifacts")
    live_file_record(
        artifacts["aab"],
        expected_path=producer.archive.ANDROID_RELEASE_AAB_RELATIVE_PATH,
        maximum_bytes=producer.ANDROID_ARTIFACT_MAX_BYTES,
        root=root,
    )
    live_file_record(
        artifacts["apk"],
        expected_path=producer.archive.ANDROID_RELEASE_APK_RELATIVE_PATH,
        maximum_bytes=producer.ANDROID_ARTIFACT_MAX_BYTES,
        root=root,
    )
    mapping = live_file_record(
        artifacts["mapping"],
        expected_path=producer.ANDROID_MAPPING_PATH,
        maximum_bytes=producer.ANDROID_MAPPING_MAX_BYTES,
        root=root,
    )
    try:
        expected_mapping = producer.android_mapping_metadata(mapping)
    except producer.DiagnosticsError as error:
        raise EvidenceError(f"mapping readback failed: {error}") from error
    mapping_record = exact_keys(
        document["mapping"],
        {"compiler", "compilerVersion", "mapHash", "mapId"},
        "mapping",
    )
    if mapping_record != expected_mapping:
        raise EvidenceError("mapping compiler metadata differs")

    probe_keys = {
        "inputSha256",
        "mappingLineSha256",
        "obfuscatedClass",
        "obfuscatedFrame",
        "obfuscatedLine",
        "obfuscatedMethod",
        "originalClass",
        "originalFrame",
        "originalMethod",
        "outputSha256",
        "source",
        "sourceFile",
        "sourceLine",
    }
    probe = exact_keys(document["probe"], probe_keys, "probe")
    obfuscated_line = require_int(probe["obfuscatedLine"], "obfuscatedLine", minimum=1)
    source_line = require_int(probe["sourceLine"], "sourceLine", minimum=1)
    source_file = require_text(
        probe["sourceFile"],
        "sourceFile",
        pattern=r"[A-Za-z0-9_+.-]+\.(?:kt|java)",
    )
    original_class = require_text(
        probe["originalClass"],
        "originalClass",
        pattern=r"com\.localagentbridge\.[A-Za-z0-9_.$]+",
    )
    obfuscated_class = require_text(
        probe["obfuscatedClass"],
        "obfuscatedClass",
        pattern=r"[A-Za-z0-9_.$]+",
    )
    original_method = require_text(
        probe["originalMethod"],
        "originalMethod",
        pattern=r"[A-Za-z_$][A-Za-z0-9_$]*",
    )
    obfuscated_method = require_text(
        probe["obfuscatedMethod"],
        "obfuscatedMethod",
        pattern=r"[A-Za-z_$][A-Za-z0-9_$]*",
    )
    if original_class == obfuscated_class or original_method == obfuscated_method:
        raise EvidenceError("Android probe must recover both class and method identity")
    expected_obfuscated = (
        f"at {obfuscated_class}.{obfuscated_method}({source_file}:{obfuscated_line})"
    )
    expected_original = (
        f"at {original_class}.{original_method}({source_file}:{source_line})"
    )
    if probe["obfuscatedFrame"] != expected_obfuscated:
        raise EvidenceError("obfuscated frame differs")
    if probe["originalFrame"] != expected_original:
        raise EvidenceError("original frame differs")
    source_readback(
        probe["source"],
        expected_roots=producer.ANDROID_SOURCE_ROOTS,
        source_file=source_file,
        source_line=source_line,
        root=root,
    )

    stack = f"{producer.ANDROID_PROBE_EXCEPTION}\n\t{expected_obfuscated}\n".encode("utf-8")
    expected_output = f"{producer.ANDROID_PROBE_EXCEPTION}\n\t{expected_original}\n".encode("utf-8")
    if probe["inputSha256"] != producer.sha256(stack):
        raise EvidenceError("Android probe input identity differs")
    if probe["outputSha256"] != producer.sha256(expected_output):
        raise EvidenceError("Android probe output identity differs")

    tool = exact_keys(
        document["tool"],
        {
            "agpVersion",
            "builderJar",
            "classpathEntryCount",
            "mainClass",
            "retraceVersion",
        },
        "tool",
    )
    if tool["agpVersion"] != producer.AGP_VERSION or tool["mainClass"] != producer.RETRACE_MAIN_CLASS:
        raise EvidenceError("Android diagnostics tool contract differs")
    try:
        java, classpath, builder, version_text = producer.android_tool(root)
        builder_data = producer.read_regular_bytes(builder, maximum_bytes=256 * 1024 * 1024)
    except producer.DiagnosticsError as error:
        raise EvidenceError(f"Android diagnostics tool readback failed: {error}") from error
    builder_record = exact_keys(tool["builderJar"], {"name", "sha256", "size"}, "builderJar")
    require_int(builder_record["size"], "builderJar.size")
    expected_builder = {
        "name": builder.name,
        "sha256": producer.sha256(builder_data),
        "size": len(builder_data),
    }
    if builder_record != expected_builder:
        raise EvidenceError("AGP builder JAR identity differs")
    if tool["retraceVersion"] != version_text:
        raise EvidenceError("Retrace version identity differs")
    classpath_entry_count = require_int(
        tool["classpathEntryCount"],
        "classpathEntryCount",
        minimum=1,
    )
    if classpath_entry_count != len(classpath.split(os.pathsep)):
        raise EvidenceError("Retrace classpath entry count differs")
    try:
        selected, selected_source, selected_stack, selected_output = (
            producer.resolve_android_probe(
                mapping,
                root=root,
                java=java,
                classpath=classpath,
                mapping_path=root / producer.ANDROID_MAPPING_PATH,
            )
        )
    except producer.DiagnosticsError as error:
        raise EvidenceError(f"Retrace execution failed: {error}") from error
    for key in (
        "mappingLineSha256",
        "obfuscatedClass",
        "obfuscatedLine",
        "obfuscatedMethod",
        "originalClass",
        "originalMethod",
        "sourceFile",
        "sourceLine",
    ):
        if probe[key] != selected[key]:
            raise EvidenceError(f"deterministic Android probe selection differs: {key}")
    if probe["source"] != selected_source:
        raise EvidenceError("deterministic Android probe source differs")
    if selected_stack != stack:
        raise EvidenceError("deterministic Android probe input differs")
    if selected_output != expected_output or selected_output == selected_stack:
        raise EvidenceError("Retrace did not reproduce the original source frame")


def validate_macos(document: Mapping[str, object], *, root: Path) -> None:
    validate_common(document, expected_platform="macos", root=root)
    if document["result"] != "macos-dsym-symbolicated-one-project-frame":
        raise EvidenceError("macOS result marker differs")
    artifacts = exact_keys(
        document["artifacts"], {"dSYM", "executable", "sourceReceipt"}, "artifacts"
    )
    live_file_record(
        artifacts["executable"],
        expected_path=producer.MACOS_EXECUTABLE_PATH,
        maximum_bytes=producer.MACOS_BINARY_MAX_BYTES,
        root=root,
    )
    live_file_record(
        artifacts["dSYM"],
        expected_path=producer.MACOS_DSYM_DWARF_PATH,
        maximum_bytes=producer.MACOS_BINARY_MAX_BYTES,
        root=root,
    )
    live_file_record(
        artifacts["sourceReceipt"],
        expected_path=producer.MACOS_SOURCE_RECEIPT_PATH,
        maximum_bytes=producer.archive.MACOS_UNSEALED_SOURCE_RECEIPT_MAX_BYTES,
        root=root,
    )
    tool = exact_keys(document["tool"], {"atos", "dwarfdump", "nm"}, "tool")
    live_external_tool_record(tool["atos"], Path("/usr/bin/atos"))
    live_external_tool_record(tool["dwarfdump"], Path("/usr/bin/dwarfdump"))
    live_external_tool_record(tool["nm"], Path("/usr/bin/nm"))

    probe = exact_keys(
        document["probe"],
        {
            "address",
            "nmSymbol",
            "source",
            "sourceFile",
            "sourceLine",
            "symbol",
            "symbolicatedFrame",
            "symbolicatedFrameSha256",
            "uuid",
        },
        "probe",
    )
    address = require_text(probe["address"], "address", pattern=r"0x[0-9a-f]{16}")
    nm_symbol = require_text(probe["nmSymbol"], "nmSymbol")
    source_file = require_text(
        probe["sourceFile"], "sourceFile", pattern=r"[A-Za-z0-9_+.-]+\.swift"
    )
    source_line = require_int(probe["sourceLine"], "sourceLine", minimum=1)
    symbol = require_text(probe["symbol"], "symbol")
    uuid = require_text(
        probe["uuid"],
        "uuid",
        pattern=r"[0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12}",
    )
    source_readback(
        probe["source"],
        expected_roots=producer.MACOS_SOURCE_ROOTS,
        source_file=source_file,
        source_line=source_line,
        root=root,
    )
    executable = root / producer.MACOS_EXECUTABLE_PATH
    dwarf = root / producer.MACOS_DSYM_DWARF_PATH
    try:
        selected_probe = producer.macos_probe(
            executable=executable,
            dwarf=dwarf,
            root=root,
        )
        if producer.macos_uuid(executable, root=root) != uuid:
            raise EvidenceError("macOS executable UUID differs")
        if producer.macos_uuid(dwarf, root=root) != uuid:
            raise EvidenceError("macOS dSYM UUID differs")
    except producer.DiagnosticsError as error:
        raise EvidenceError(f"macOS diagnostics command failed: {error}") from error
    expected_frame = f"{symbol} (in AetherLink) ({source_file}:{source_line})"
    if probe["symbolicatedFrame"] != expected_frame:
        raise EvidenceError("recorded symbolicated frame differs")
    if probe["symbolicatedFrameSha256"] != producer.sha256(
        (expected_frame + "\n").encode("utf-8")
    ):
        raise EvidenceError("symbolicated frame identity differs")
    recorded_probe = dict(probe)
    del recorded_probe["uuid"]
    if recorded_probe != selected_probe:
        raise EvidenceError("deterministic macOS probe selection differs")


def validate_result(path: Path, expected_platform: str, *, root: Path = ROOT) -> None:
    document = load_result(path)
    if expected_platform == "android":
        validate_android(document, root=root)
    elif expected_platform == "macos":
        validate_macos(document, root=root)
    else:
        raise EvidenceError(f"unsupported platform: {expected_platform}")
    final = producer.read_regular_bytes(path, maximum_bytes=producer.RESULT_MAX_BYTES)
    if final != producer.canonical_json_bytes(document):
        raise EvidenceError("result changed during independent readback")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("android", "macos"), required=True)
    parser.add_argument("result", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        validate_result(arguments.result, arguments.platform, root=ROOT)
    except (EvidenceError, producer.DiagnosticsError) as error:
        print(f"Release diagnostics readback failed: {error}", file=os.sys.stderr)
        return 1
    print(
        f"Release diagnostics readback passed for {arguments.platform}: "
        f"{arguments.result}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
