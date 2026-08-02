#!/usr/bin/env python3
"""Generic lifecycle engine for exact G7 non-security Swift successors.

The engine owns only the mechanical prepare/run/bind/result lifecycle.  A
versioned configuration module owns the frozen identities, antecedent evidence,
partition arithmetic, and claim boundary.  Candidate producers and candidate
checkers deliberately do not use this module so that publication and readback
do not share one payload oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import os
import re
import stat
import sys
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class SuccessorConfig:
    root: Path
    version_label: str
    contract: str
    execution_contract: str
    schema_version: int
    product_ci: Any
    candidate_base: Any
    test_list_path: Path
    reviewed_identity_path: Path
    antecedent_path: Path
    output_root: Path
    run_marker_path: Path
    console_path: Path
    binding_path: Path
    result_path: Path
    execution_contract_path: Path
    result_max_bytes: int
    command_and_environment_max_bytes: int
    run_timeout_seconds: int
    exact_source_files: tuple[Path, ...]
    limitations: Mapping[str, bool]
    selected_module_counts: Mapping[str, int]
    selected_class_counts: Mapping[str, int]
    selected_class_prefix_counts: Mapping[str, int]
    discovered_test_count: int
    discovered_test_manifest_sha256: str
    antecedent_distinct_test_count: int
    antecedent_distinct_test_manifest_sha256: str
    reviewed_input_test_count: int
    reviewed_input_test_manifest_sha256: str
    new_test_count: int
    new_test_manifest_sha256: str
    excluded_by_scope_test_count: int
    excluded_by_scope_test_manifest_sha256: str
    excluded_external_test_count: int
    excluded_external_test_manifest_sha256: str
    remaining_test_count: int
    remaining_test_manifest_sha256: str
    distinct_after_addon_test_count: int
    distinct_after_addon_test_manifest_sha256: str
    canonical_json_bytes: Callable[[object], bytes]
    exact_filter: Callable[[tuple[str, ...]], str]
    contract_inputs: Callable[[], tuple[Any | None, list[str]]]
    candidate_antecedent_failures: Callable[[], list[str]]
    extra_self_test: Callable[[Any], list[str]]


def _label(config: SuccessorConfig) -> str:
    return f"G7 reviewed Swift {config.version_label}"


def physical_output_directory_failures(
    config: SuccessorConfig,
    directory: Path,
    *,
    create: bool,
) -> list[str]:
    try:
        relative = directory.relative_to(config.root)
    except ValueError:
        return [f"{config.version_label} output directory must remain inside the repository"]
    if not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
        return [f"{config.version_label} output directory path must be canonical"]
    try:
        root_status = config.root.lstat()
    except OSError as error:
        return [f"repository root cannot be inspected: {error}"]
    if stat.S_ISLNK(root_status.st_mode) or not stat.S_ISDIR(root_status.st_mode):
        return ["repository root must be a physical directory"]
    current = config.root
    for index, component in enumerate(relative.parts):
        current /= component
        final = index == len(relative.parts) - 1
        try:
            value = current.lstat()
        except FileNotFoundError:
            if create and final:
                try:
                    current.mkdir(mode=0o700)
                    value = current.lstat()
                except OSError as error:
                    return [
                        f"{config.version_label} output directory cannot be created: {error}"
                    ]
            else:
                return [
                    f"{config.version_label} output directory component is missing: {current}"
                ]
        except OSError as error:
            return [
                f"{config.version_label} output directory cannot be inspected: "
                f"{current}: {error}"
            ]
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
            return [
                f"{config.version_label} output directory must be a physical directory: "
                f"{current}"
            ]
        if final and stat.S_IMODE(value.st_mode) != 0o700:
            return [
                f"{config.version_label} output directory mode must be 0700: {current}"
            ]
    return []


def runner_command(
    config: SuccessorConfig,
    partition: Any,
) -> tuple[tuple[str, ...] | None, list[str]]:
    failures: list[str] = []
    filter_pattern = config.exact_filter(partition.selected)
    command = (
        "/usr/bin/sandbox-exec",
        "-p",
        config.product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
        "/usr/bin/swift",
        "test",
        "--disable-sandbox",
        "--no-parallel",
        "--filter",
        filter_pattern,
    )
    try:
        selected_by_command = {
            identity
            for identity in partition.discovered
            if re.search(command[8], identity)
        }
    except re.error as error:
        failures.append(f"runner exact filter regex is invalid: {error}")
        selected_by_command = set()
    if selected_by_command != set(partition.selected):
        failures.append(
            f"runner exact filter differs from the {config.new_test_count}-test reviewed set"
        )
    if "--skip" in command:
        failures.append(f"{config.version_label} runner must not use a skip filter")
    return (None if failures else command), failures


def selection_count_failures(
    config: SuccessorConfig,
    partition: Any,
) -> list[str]:
    failures: list[str] = []
    selected = tuple(partition.selected)
    for prefix, expected in config.selected_module_counts.items():
        if type(prefix) is not str or type(expected) is not int or expected < 0:
            failures.append(f"selected module count must be an exact integer: {prefix}")
            continue
        observed = sum(identity.startswith(prefix) for identity in selected)
        if observed != expected:
            failures.append(f"selected module count differs: {prefix}")
    module_values_are_exact = all(
        type(value) is int and value >= 0
        for value in config.selected_module_counts.values()
    )
    if module_values_are_exact and (
        sum(config.selected_module_counts.values()) != config.new_test_count
    ):
        failures.append("selected module count total differs")

    derived_class_counts: dict[str, int] = {}
    for prefix, expected in config.selected_class_prefix_counts.items():
        if type(prefix) is not str or type(expected) is not int or expected < 0:
            failures.append(f"selected class count must be an exact integer: {prefix}")
            continue
        observed = sum(identity.startswith(prefix) for identity in selected)
        if observed != expected:
            failures.append(f"selected class count differs: {prefix}")
        class_name = prefix.rstrip("/").rsplit(".", 1)[-1]
        if class_name in derived_class_counts:
            failures.append(f"selected class display key is duplicated: {class_name}")
        derived_class_counts[class_name] = expected
    if any(
        type(key) is not str or type(value) is not int or value < 0
        for key, value in config.selected_class_counts.items()
    ):
        failures.append("selected class result counts must use string/exact-integer pairs")
    if dict(config.selected_class_counts) != derived_class_counts:
        failures.append("selected class result counts differ from exact prefix counts")
    class_prefix_values_are_exact = all(
        type(value) is int and value >= 0
        for value in config.selected_class_prefix_counts.values()
    )
    if class_prefix_values_are_exact and (
        sum(config.selected_class_prefix_counts.values()) != config.new_test_count
    ):
        failures.append("selected class count total differs")
    return failures


def command_environment_footprint(
    config: SuccessorConfig,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> int:
    return sum(len(os.fsencode(value)) + 1 for value in command) + sum(
        len(os.fsencode(key)) + len(os.fsencode(value)) + 2
        for key, value in environment.items()
    )


def runner_contract(
    config: SuccessorConfig,
    partition: Any,
) -> tuple[tuple[str, ...] | None, dict[str, str] | None, list[str]]:
    command, failures = runner_command(config, partition)
    failures.extend(selection_count_failures(config, partition))
    failures.extend(config.candidate_antecedent_failures())
    environment, environment_failures = (
        config.product_ci.g7_nonsecurity_swift_environment()
    )
    failures.extend(environment_failures)
    failures.extend(config.product_ci.g7_nonsecurity_swift_network_sandbox_self_test())
    if command is None:
        return None, None, failures
    for executable in (Path(command[0]), Path(command[3])):
        try:
            value = executable.lstat()
        except OSError as error:
            failures.append(f"runner executable cannot be inspected: {executable}: {error}")
            continue
        if (
            stat.S_ISLNK(value.st_mode)
            or not stat.S_ISREG(value.st_mode)
            or not os.access(executable, os.X_OK)
        ):
            failures.append(f"runner executable must be physical: {executable}")
    if environment is not None and (
        command_environment_footprint(config, command, environment)
        > config.command_and_environment_max_bytes
    ):
        failures.append("runner argv/environment footprint exceeds fixed bound")
    if failures or environment is None:
        return None, None, failures
    return command, environment, []


def execution_contract_payload(
    config: SuccessorConfig,
    partition: Any,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> dict[str, object]:
    return {
        "command": list(command),
        "commandAndEnvironmentBytes": command_environment_footprint(
            config, command, environment
        ),
        "commandAndEnvironmentMaximumBytes": (
            config.command_and_environment_max_bytes
        ),
        "contract": config.execution_contract,
        "environment": environment,
        "filterExcluded": 0,
        "networkDenyProbePassed": True,
        "networkDenyProfile": (
            config.product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE
        ),
        "runtimeExpected": {
            "errors": 0,
            "failures": 0,
            "skipped": 0,
            "testcaseManifestSha256": config.new_test_manifest_sha256,
            "tests": config.new_test_count,
        },
        "selection": {
            "antecedentDistinctManifestSha256": (
                config.antecedent_distinct_test_manifest_sha256
            ),
            "antecedentDistinctTests": config.antecedent_distinct_test_count,
            "excludedByScopeManifestSha256": (
                config.excluded_by_scope_test_manifest_sha256
            ),
            "excludedByScopeTests": config.excluded_by_scope_test_count,
            "excludedExternalManifestSha256": (
                config.excluded_external_test_manifest_sha256
            ),
            "excludedExternalTests": config.excluded_external_test_count,
            "newManifestSha256": config.new_test_manifest_sha256,
            "newTests": config.new_test_count,
            "remainingManifestSha256": config.remaining_test_manifest_sha256,
            "remainingTests": config.remaining_test_count,
            "reviewedInputManifestSha256": (
                config.reviewed_input_test_manifest_sha256
            ),
            "reviewedInputTests": config.reviewed_input_test_count,
        },
        "schemaVersion": config.schema_version,
    }


def execution_contract_failures(
    config: SuccessorConfig,
    partition: Any,
    command: tuple[str, ...],
    *,
    expected_environment: dict[str, str] | None = None,
) -> list[str]:
    directory_failures = physical_output_directory_failures(
        config, config.execution_contract_path.parent, create=False
    )
    if directory_failures:
        return directory_failures
    try:
        data, mode = config.candidate_base.read_stable_regular_file(
            config.root,
            config.execution_contract_path.relative_to(config.root),
            maximum_bytes=config.command_and_environment_max_bytes,
        )
    except config.candidate_base.CandidateError as error:
        return [f"{config.version_label} execution contract cannot be read: {error}"]
    failures: list[str] = []
    if mode != 0o600:
        failures.append(f"{config.version_label} execution contract mode must be 0600")
    try:
        document = json.loads(
            data,
            object_pairs_hook=config.candidate_base.reject_duplicate_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        config.candidate_base.DuplicateKeyError,
    ) as error:
        return failures + [
            f"{config.version_label} execution contract JSON cannot be decoded: {error}"
        ]
    if type(document) is not dict or data != config.canonical_json_bytes(document):
        failures.append(
            f"{config.version_label} execution contract must be canonical JSON"
        )
        return failures
    recorded_environment = document.get("environment")
    if type(recorded_environment) is not dict or any(
        type(key) is not str or type(value) is not str
        for key, value in (
            recorded_environment.items()
            if type(recorded_environment) is dict
            else ()
        )
    ):
        failures.append(
            f"{config.version_label} execution contract environment must be a string mapping"
        )
        recorded_environment = {}
    normalized_environment, environment_failures = (
        config.product_ci.g7_nonsecurity_swift_environment(recorded_environment)
    )
    failures.extend(
        f"{config.version_label} execution contract environment: {failure}"
        for failure in environment_failures
    )
    if normalized_environment != recorded_environment:
        failures.append(
            f"{config.version_label} execution contract environment is not the exact allowlist"
        )
    if expected_environment is not None and recorded_environment != expected_environment:
        failures.append(
            f"{config.version_label} execution contract environment differs from this run"
        )
    expected = execution_contract_payload(
        config, partition, command, recorded_environment
    )
    if data != config.canonical_json_bytes(expected):
        failures.append(
            f"{config.version_label} execution contract command/profile/selection differs"
        )
    return failures


def write_execution_contract(
    config: SuccessorConfig,
    partition: Any,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> list[str]:
    failures = physical_output_directory_failures(
        config, config.execution_contract_path.parent, create=True
    )
    if failures:
        return failures
    failures = config.product_ci.write_canonical_json_payload(
        config.execution_contract_path,
        execution_contract_payload(config, partition, command, environment),
        label=f"G7 reviewed non-security Swift {config.version_label} execution contract",
    )
    if not failures:
        failures.extend(
            execution_contract_failures(
                config,
                partition,
                command,
                expected_environment=environment,
            )
        )
    return failures


def generic_arguments(config: SuccessorConfig, partition: Any) -> dict[str, object]:
    return {
        "binding_path": config.binding_path,
        "marker_path": config.run_marker_path,
        "log_path": config.console_path,
        "test_list_path": config.test_list_path,
        "filter_pattern": config.exact_filter(partition.selected),
        "expected_count": config.new_test_count,
        "expected_manifest_sha256": config.new_test_manifest_sha256,
        "excluded_tests": (),
        "exact_files": config.exact_source_files,
    }


def run_addon_tests(
    config: SuccessorConfig,
    partition: Any,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> tuple[int, list[str]]:
    directory_failures = physical_output_directory_failures(
        config, config.console_path.parent, create=False
    )
    if directory_failures:
        return 1, directory_failures
    common = generic_arguments(config, partition)
    marker_failures = config.product_ci.swift_focused_test_run_marker_failures(
        **{key: value for key, value in common.items() if key != "binding_path"},
        require_log=False,
    )
    if marker_failures:
        return 1, marker_failures
    _, expected_tests, selection_failures = (
        config.product_ci.swift_focused_test_list_snapshot(
            test_list_path=config.test_list_path,
            filter_pattern=config.exact_filter(partition.selected),
            expected_count=config.new_test_count,
            expected_manifest_sha256=config.new_test_manifest_sha256,
            excluded_tests=(),
        )
    )
    if expected_tests is None:
        return 1, selection_failures

    def validate_log_context(candidate_log_path: Path) -> list[str]:
        return config.product_ci.swift_focused_test_run_marker_failures(
            marker_path=config.run_marker_path,
            log_path=candidate_log_path,
            test_list_path=config.test_list_path,
            filter_pattern=config.exact_filter(partition.selected),
            expected_count=config.new_test_count,
            expected_manifest_sha256=config.new_test_manifest_sha256,
            excluded_tests=(),
            exact_files=config.exact_source_files,
        )

    return config.product_ci.run_and_publish_swift_focused_log(
        command=command,
        cwd=config.root,
        log_path=config.console_path,
        expected_tests=expected_tests,
        log_context_failures=validate_log_context,
        timeout_seconds=config.run_timeout_seconds,
        environment=environment,
    )


def stable_record(
    config: SuccessorConfig,
    path: Path,
    *,
    maximum_bytes: int,
) -> dict[str, object]:
    relative = path.relative_to(config.root)
    data, mode = config.candidate_base.read_stable_regular_file(
        config.root,
        relative,
        maximum_bytes=maximum_bytes,
    )
    import hashlib

    return {
        "bytes": len(data),
        "mode": mode,
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def partition_record(tests: int, digest: str) -> dict[str, object]:
    return {"manifestSha256": digest, "tests": tests}


def result_payload(
    config: SuccessorConfig,
    partition: Any,
) -> tuple[dict[str, object] | None, list[str]]:
    selection_failures = selection_count_failures(config, partition)
    if selection_failures:
        return None, selection_failures
    directory_failures = physical_output_directory_failures(
        config, config.result_path.parent, create=False
    )
    if directory_failures:
        return None, directory_failures
    try:
        artifacts = {
            "antecedentCandidate": stable_record(
                config, config.antecedent_path, maximum_bytes=config.result_max_bytes
            ),
            "binding": stable_record(
                config, config.binding_path, maximum_bytes=config.result_max_bytes
            ),
            "console": stable_record(
                config,
                config.console_path,
                maximum_bytes=config.product_ci.SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
            ),
            "executionContract": stable_record(
                config,
                config.execution_contract_path,
                maximum_bytes=config.command_and_environment_max_bytes,
            ),
            "reviewedIdentityManifest": stable_record(
                config,
                config.reviewed_identity_path,
                maximum_bytes=config.result_max_bytes,
            ),
            "runMarker": stable_record(
                config, config.run_marker_path, maximum_bytes=config.result_max_bytes
            ),
            "testList": stable_record(
                config, config.test_list_path, maximum_bytes=config.result_max_bytes
            ),
        }
    except (ValueError, config.candidate_base.CandidateError) as error:
        return None, [
            f"{config.version_label} add-on result artifact cannot be read: {error}"
        ]
    expected_modes = {
        "antecedentCandidate": 0o600,
        "binding": 0o600,
        "console": 0o600,
        "executionContract": 0o600,
        "reviewedIdentityManifest": 0o644,
        "runMarker": 0o600,
        "testList": 0o600,
    }
    mode_failures = [
        f"{config.version_label} add-on artifact mode differs: {label}"
        for label, expected_mode in expected_modes.items()
        if artifacts[label]["mode"] != expected_mode
    ]
    if mode_failures:
        return None, mode_failures
    return (
        {
            "artifacts": artifacts,
            "contract": config.contract,
            "limitations": dict(config.limitations),
            "partition": {
                "antecedentDistinct": partition_record(
                    config.antecedent_distinct_test_count,
                    config.antecedent_distinct_test_manifest_sha256,
                ),
                "discovered": partition_record(
                    config.discovered_test_count,
                    config.discovered_test_manifest_sha256,
                ),
                "distinctAfterAddon": partition_record(
                    config.distinct_after_addon_test_count,
                    config.distinct_after_addon_test_manifest_sha256,
                ),
                "excludedByScope": partition_record(
                    config.excluded_by_scope_test_count,
                    config.excluded_by_scope_test_manifest_sha256,
                ),
                "excludedExternal": partition_record(
                    config.excluded_external_test_count,
                    config.excluded_external_test_manifest_sha256,
                ),
                "newExecuted": partition_record(
                    config.new_test_count,
                    config.new_test_manifest_sha256,
                ),
                "remaining": partition_record(
                    config.remaining_test_count,
                    config.remaining_test_manifest_sha256,
                ),
                "reviewedInput": partition_record(
                    config.reviewed_input_test_count,
                    config.reviewed_input_test_manifest_sha256,
                ),
            },
            "result": "passed",
            "schemaVersion": config.schema_version,
            "scope": {
                "classifiedReviewedInputTests": config.reviewed_input_test_count,
                "selectedByClass": dict(config.selected_class_counts),
                "selectedByModule": dict(config.selected_module_counts),
                "securityAuthenticationOrSecureChannelSuitesExecuted": False,
                "unclassifiedTests": 0,
            },
        },
        [],
    )


def result_failures(config: SuccessorConfig, partition: Any) -> list[str]:
    failures = physical_output_directory_failures(
        config, config.result_path.parent, create=False
    )
    failures.extend(config.candidate_antecedent_failures())
    command, command_failures = runner_command(config, partition)
    failures.extend(command_failures)
    if command is not None:
        failures.extend(execution_contract_failures(config, partition, command))
    failures.extend(
        config.product_ci.swift_focused_test_binding_failures(
            **generic_arguments(config, partition)
        )
    )
    expected, payload_failures = result_payload(config, partition)
    failures.extend(payload_failures)
    if expected is None:
        return failures
    try:
        data, mode = config.candidate_base.read_stable_regular_file(
            config.root,
            config.result_path.relative_to(config.root),
            maximum_bytes=config.result_max_bytes,
        )
    except config.candidate_base.CandidateError as error:
        failures.append(f"{config.version_label} add-on result cannot be read: {error}")
        return failures
    if mode != 0o600:
        failures.append(f"{config.version_label} add-on result mode must be 0600")
    try:
        observed = json.loads(
            data,
            object_pairs_hook=config.candidate_base.reject_duplicate_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        config.candidate_base.DuplicateKeyError,
    ) as error:
        failures.append(
            f"{config.version_label} add-on result JSON cannot be decoded: {error}"
        )
        return failures
    if type(observed) is not dict or data != config.canonical_json_bytes(observed):
        failures.append(f"{config.version_label} add-on result must be canonical JSON")
    if data != config.canonical_json_bytes(expected):
        failures.append(
            f"{config.version_label} add-on result must exactly bind current evidence bytes"
        )
    return failures


def write_result(config: SuccessorConfig, partition: Any) -> list[str]:
    failures = physical_output_directory_failures(
        config, config.result_path.parent, create=False
    )
    failures.extend(
        config.product_ci.swift_focused_test_binding_failures(
            **generic_arguments(config, partition)
        )
    )
    failures.extend(config.candidate_antecedent_failures())
    command, command_failures = runner_command(config, partition)
    failures.extend(command_failures)
    if command is not None:
        failures.extend(execution_contract_failures(config, partition, command))
    payload, payload_failures = result_payload(config, partition)
    failures.extend(payload_failures)
    if payload is None or failures:
        return failures
    failures.extend(
        config.product_ci.write_canonical_json_payload(
            config.result_path,
            payload,
            label=(
                f"G7 reviewed non-security Swift {config.version_label} add-on result"
            ),
        )
    )
    if not failures:
        failures.extend(result_failures(config, partition))
    return failures


def self_test(config: SuccessorConfig) -> list[str]:
    partition, failures = config.contract_inputs()
    if partition is None:
        return failures
    command, environment, runner_failures = runner_contract(config, partition)
    failures.extend(runner_failures)
    if command is None or environment is None:
        return failures
    if command[:4] != (
        "/usr/bin/sandbox-exec",
        "-p",
        "(version 1)(allow default)(deny network*)",
        "/usr/bin/swift",
    ):
        failures.append(f"{config.version_label} runner sandbox prefix differs")
    if command[4:8] != (
        "test",
        "--disable-sandbox",
        "--no-parallel",
        "--filter",
    ):
        failures.append(
            f"{config.version_label} runner serial exact-filter contract differs"
        )
    if command[8] != config.exact_filter(partition.selected) or "--skip" in command:
        failures.append(f"{config.version_label} runner selection contract differs")
    failures.extend(config.extra_self_test(partition))
    return failures


def print_failures(prefix: str, failures: list[str]) -> int:
    for failure in failures:
        print(f"{prefix}: {failure}", file=sys.stderr)
    return 1


def main(config: SuccessorConfig, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--write-binding", action="store_true")
    mode.add_argument("--results", action="store_true")
    args = parser.parse_args(argv)

    partition, failures = config.contract_inputs()
    if partition is None:
        return print_failures(f"{_label(config)} add-on preflight failed", failures)

    if args.self_test:
        failures = self_test(config)
        if failures:
            return print_failures(f"{_label(config)} self-test failed", failures)
        print(
            f"G7 reviewed non-security Swift {config.version_label} contract "
            "self-test passed."
        )
        return 0

    common = generic_arguments(config, partition)
    if args.prepare:
        command, environment, runner_failures = runner_contract(config, partition)
        failures.extend(runner_failures)
        if command is not None and environment is not None and not failures:
            failures.extend(
                write_execution_contract(config, partition, command, environment)
            )
        if not failures:
            failures.extend(
                config.product_ci.write_swift_focused_test_run_marker(
                    **{
                        key: value
                        for key, value in common.items()
                        if key not in ("binding_path", "log_path")
                    }
                )
            )
        if failures:
            return print_failures(f"{_label(config)} preparation failed", failures)
        print(
            f"{_label(config)} marker passed: {config.new_test_count} new tests."
        )
        return 0

    if args.run:
        command, environment, runner_failures = runner_contract(config, partition)
        failures.extend(runner_failures)
        if command is None or environment is None:
            return print_failures(f"{_label(config)} runner failed", failures)
        failures.extend(
            execution_contract_failures(
                config,
                partition,
                command,
                expected_environment=environment,
            )
        )
        if failures:
            return print_failures(f"{_label(config)} runner failed", failures)
        status, run_failures = run_addon_tests(
            config, partition, command, environment
        )
        failures.extend(run_failures)
        if status != 0 or failures:
            return print_failures(f"{_label(config)} runner failed", failures)
        print(
            f"{_label(config)} run passed: {config.new_test_count}/"
            f"{config.new_test_count}; runtimeSkipped=0; failures=0; "
            "network-deny profile applied."
        )
        return 0

    if args.write_binding:
        command, command_failures = runner_command(config, partition)
        failures.extend(command_failures)
        if command is not None:
            failures.extend(
                execution_contract_failures(config, partition, command)
            )
        failures.extend(
            physical_output_directory_failures(
                config, config.binding_path.parent, create=False
            )
        )
        if not failures:
            failures.extend(
                config.product_ci.write_swift_focused_test_binding(**common)
            )
        if not failures:
            failures.extend(write_result(config, partition))
        if failures:
            return print_failures(f"{_label(config)} binding failed", failures)
        print(
            f"{_label(config)} binding passed: {config.new_test_count}/"
            f"{config.new_test_count}; distinct local Swift evidence "
            f"{config.distinct_after_addon_test_count}."
        )
        return 0

    failures.extend(result_failures(config, partition))
    if failures:
        return print_failures(f"{_label(config)} readback failed", failures)
    print(
        f"{_label(config)} readback passed: {config.new_test_count}/"
        f"{config.new_test_count}; distinct local Swift evidence "
        f"{config.distinct_after_addon_test_count}; canonical G7 remains unclaimed."
    )
    return 0


__all__ = [
    "SuccessorConfig",
    "command_environment_footprint",
    "execution_contract_failures",
    "execution_contract_payload",
    "generic_arguments",
    "main",
    "physical_output_directory_failures",
    "result_failures",
    "result_payload",
    "run_addon_tests",
    "runner_command",
    "runner_contract",
    "selection_count_failures",
    "self_test",
    "stable_record",
    "write_execution_contract",
    "write_result",
]
