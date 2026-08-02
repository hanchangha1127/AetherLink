#!/usr/bin/env python3
"""Run the reviewed non-security Swift union once on the current checkout.

Historical V1-V4 candidates remain immutable snapshot evidence.  This runner
reconstructs their reviewed identity union from tracked selector inputs, then
executes all 1,173 identities in one serial network-denied Swift invocation.
It does not claim the complete Swift suite, canonical Merge-full, G7 exit, RC,
GA, or V1 qualification.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Iterable, Sequence

if __package__:
    from script import check_g7_reviewed_nonsecurity_swift_addon as addon_v2
    from script import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
    from script import check_g7_reviewed_nonsecurity_swift_addon_v4 as addon_v4
    from script import check_product_ci as product_ci
else:
    import check_g7_reviewed_nonsecurity_swift_addon as addon_v2
    import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
    import check_g7_reviewed_nonsecurity_swift_addon_v4 as addon_v4
    import check_product_ci as product_ci


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
CONTRACT = "aetherlink-g7-nonsecurity-merge-full-current-run-v1"
EXECUTION_CONTRACT = (
    "aetherlink-g7-nonsecurity-merge-full-current-run-execution-v1"
)
OUTPUT_ROOT = ROOT / (
    ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1"
)
EXECUTION_CONTRACT_PATH = OUTPUT_ROOT / "execution-contract.json"
RUN_MARKER_PATH = OUTPUT_ROOT / "run-marker.json"
CONSOLE_PATH = OUTPUT_ROOT / "console.log"
BINDING_PATH = OUTPUT_ROOT / "binding.json"
RESULT_PATH = OUTPUT_ROOT / "result.json"
TEST_LIST_PATH = product_ci.SWIFT_TEST_LIST_PATH

DISCOVERED_TEST_COUNT = addon_v4.DISCOVERED_TEST_COUNT
DISCOVERED_TEST_MANIFEST_SHA256 = addon_v4.DISCOVERED_TEST_MANIFEST_SHA256
SELECTED_TEST_COUNT = addon_v4.DISTINCT_AFTER_ADDON_TEST_COUNT
SELECTED_TEST_MANIFEST_SHA256 = (
    addon_v4.DISTINCT_AFTER_ADDON_TEST_MANIFEST_SHA256
)
NOT_EXECUTED_TEST_COUNT = addon_v4.REMAINING_TEST_COUNT
NOT_EXECUTED_TEST_MANIFEST_SHA256 = addon_v4.REMAINING_TEST_MANIFEST_SHA256
BASE_DISTINCT_TEST_COUNT = addon_v2.ANTECEDENT_TEST_COUNT
BASE_DISTINCT_TEST_MANIFEST_SHA256 = addon_v2.ANTECEDENT_TEST_MANIFEST_SHA256
FOCUSED_EXPANDED_OVERLAP_COUNT = (
    product_ci.G7_NONSECURITY_SWIFT_FOCUSED_OVERLAP_COUNT
)

RUN_TIMEOUT_SECONDS = 30 * 60
RESULT_MAX_BYTES = 2 * 1024 * 1024
EXECUTION_CONTRACT_MAX_BYTES = 128 * 1024
FILTER_MAX_BYTES = 64 * 1024
COMMAND_AND_ENVIRONMENT_MAX_BYTES = 96 * 1024

TRACKED_EXACT_SOURCE_RELATIVE_PATHS = (
    Path(".github/workflows/product-quality.yml"),
    Path("Package.swift"),
    Path("docs/evidence/g7-reviewed-nonsecurity-swift-addon-identities-v4-proposal.txt"),
    Path("script/check_g7_nonsecurity_merge_full_current.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v3.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v4.py"),
    Path("script/check_product_ci.py"),
    Path("script/g7_nonsecurity_swift_successor_engine.py"),
    Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v2.txt"),
    Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v3.txt"),
    Path("script/run_g7_nonsecurity_merge_full_current.py"),
    Path("script/test_check_g7_nonsecurity_merge_full_current.py"),
    Path("script/test_run_g7_nonsecurity_merge_full_current.py"),
)
EXACT_SOURCE_FILES = tuple(
    ROOT / relative
    for relative in TRACKED_EXACT_SOURCE_RELATIVE_PATHS
) + (EXECUTION_CONTRACT_PATH,)

LIMITATIONS = {
    "canonicalG7ExitClaimed": False,
    "canonicalMergeFullClaimed": False,
    "completeSwiftSuiteClaimed": False,
    "deviceOrProductNetworkClaimed": False,
    "hostedCiExecutionClaimed": False,
    "securityAuthenticationOrCryptographyExecuted": False,
    "signedArtifactsClaimed": False,
    "v1Claimed": False,
}


@dataclass(frozen=True)
class CurrentRunPartition:
    discovered: tuple[str, ...]
    focused: tuple[str, ...]
    expanded: tuple[str, ...]
    base_distinct: tuple[str, ...]
    v2_new: tuple[str, ...]
    v3_new: tuple[str, ...]
    v4_new: tuple[str, ...]
    selected: tuple[str, ...]
    not_executed: tuple[str, ...]
    v2_partition: addon_v2.Partition
    v3_partition: addon_v3.Partition
    v4_partition: addon_v4.Partition


def canonical_json_bytes(value: object) -> bytes:
    return product_ci.canonical_json_bytes(value)


def manifest_sha256(identities: Iterable[str]) -> str:
    return product_ci.swift_test_selection_manifest_sha256(tuple(identities))


def exact_set_failures(
    label: str,
    identities: tuple[str, ...],
    expected_count: int,
    expected_manifest_sha256: str,
    *,
    require_sorted: bool = True,
) -> list[str]:
    failures: list[str] = []
    if len(identities) != expected_count:
        failures.append(
            f"{label} must contain {expected_count} identities, found "
            f"{len(identities)}"
        )
    if manifest_sha256(identities) != expected_manifest_sha256:
        failures.append(f"{label} manifest SHA-256 differs")
    if require_sorted and tuple(sorted(identities)) != identities:
        failures.append(f"{label} identities must be sorted")
    if len(set(identities)) != len(identities):
        failures.append(f"{label} identities must be unique")
    return failures


def reconstruct_partition() -> tuple[CurrentRunPartition | None, list[str]]:
    discovered, failures = addon_v2.load_discovered_tests()
    if discovered is None:
        return None, failures
    v2_partition, v2_failures = addon_v2.partition_shape_failures(discovered)
    failures.extend(v2_failures)
    if v2_partition is None:
        return None, failures
    v3_partition, v3_failures = addon_v3.partition_shape_failures(
        discovered,
        v2_partition,
    )
    failures.extend(v3_failures)
    if v3_partition is None:
        return None, failures
    v4_partition, v4_failures = addon_v4.partition_shape_failures(
        discovered,
        v3_partition,
    )
    failures.extend(v4_failures)
    if v4_partition is None:
        return None, failures

    focused = tuple(
        sorted(
            identity
            for identity in discovered
            if re.search(product_ci.SWIFT_FILTER, identity)
        )
    )
    expanded = tuple(
        sorted(
            identity
            for identity in discovered
            if re.search(product_ci.G7_NONSECURITY_SWIFT_FILTER, identity)
            and identity not in product_ci.G7_NONSECURITY_SWIFT_LIVE_TESTS
        )
    )
    base_distinct = tuple(sorted(set(focused) | set(expanded)))
    partition = CurrentRunPartition(
        discovered=tuple(discovered),
        focused=focused,
        expanded=expanded,
        base_distinct=base_distinct,
        v2_new=tuple(v2_partition.new),
        v3_new=tuple(v3_partition.selected),
        v4_new=tuple(v4_partition.selected),
        selected=tuple(v4_partition.distinct_after_addon),
        not_executed=tuple(v4_partition.remaining),
        v2_partition=v2_partition,
        v3_partition=v3_partition,
        v4_partition=v4_partition,
    )
    exact_contracts = (
        (
            "discovered Swift",
            partition.discovered,
            DISCOVERED_TEST_COUNT,
            DISCOVERED_TEST_MANIFEST_SHA256,
            False,
        ),
        (
            "focused Swift",
            partition.focused,
            product_ci.SWIFT_PRODUCT_TEST_COUNT,
            product_ci.SWIFT_PRODUCT_TEST_MANIFEST_SHA256,
        ),
        (
            "expanded Swift",
            partition.expanded,
            product_ci.G7_NONSECURITY_SWIFT_TEST_COUNT,
            product_ci.G7_NONSECURITY_SWIFT_TEST_MANIFEST_SHA256,
        ),
        (
            "base distinct Swift",
            partition.base_distinct,
            BASE_DISTINCT_TEST_COUNT,
            BASE_DISTINCT_TEST_MANIFEST_SHA256,
        ),
        (
            "V2 new Swift",
            partition.v2_new,
            addon_v2.NEW_TEST_COUNT,
            addon_v2.NEW_TEST_MANIFEST_SHA256,
        ),
        (
            "V3 new Swift",
            partition.v3_new,
            addon_v3.NEW_TEST_COUNT,
            addon_v3.NEW_TEST_MANIFEST_SHA256,
        ),
        (
            "V4 new Swift",
            partition.v4_new,
            addon_v4.NEW_TEST_COUNT,
            addon_v4.NEW_TEST_MANIFEST_SHA256,
        ),
        (
            "current-run selected Swift",
            partition.selected,
            SELECTED_TEST_COUNT,
            SELECTED_TEST_MANIFEST_SHA256,
        ),
        (
            "current-run not-executed Swift",
            partition.not_executed,
            NOT_EXECUTED_TEST_COUNT,
            NOT_EXECUTED_TEST_MANIFEST_SHA256,
        ),
    )
    for contract in exact_contracts:
        label, identities, count, digest, *options = contract
        failures.extend(
            exact_set_failures(
                label,
                identities,
                count,
                digest,
                require_sorted=options[0] if options else True,
            )
        )

    component_sets = (
        set(partition.base_distinct),
        set(partition.v2_new),
        set(partition.v3_new),
        set(partition.v4_new),
    )
    if any(
        left & right
        for index, left in enumerate(component_sets)
        for right in component_sets[index + 1 :]
    ):
        failures.append("current-run additive selection components overlap")
    if set().union(*component_sets) != set(partition.selected):
        failures.append("current-run selection component union differs")
    if len(set(partition.focused) & set(partition.expanded)) != (
        FOCUSED_EXPANDED_OVERLAP_COUNT
    ):
        failures.append("focused/expanded overlap differs")
    if set(partition.selected) & set(partition.not_executed):
        failures.append("selected and not-executed Swift sets overlap")
    if set(partition.selected) | set(partition.not_executed) != set(
        partition.discovered
    ):
        failures.append("current-run Swift partition does not cover discovery")
    return (None if failures else partition), failures


def combined_filter(partition: CurrentRunPartition) -> str:
    components = (
        product_ci.SWIFT_FILTER,
        product_ci.G7_NONSECURITY_SWIFT_SAFE_MODULE_FILTER,
        product_ci.G7_NONSECURITY_SWIFT_UI_FILTER,
        addon_v2.runner_include_filter(partition.v2_partition),
        addon_v3.exact_filter(partition.v3_new),
        addon_v4.exact_filter(partition.v4_new),
    )
    return "(?:" + "|".join(components) + ")"


def command_and_filter_failures(
    partition: CurrentRunPartition,
) -> tuple[tuple[str, ...] | None, list[str]]:
    failures: list[str] = []
    filter_pattern = combined_filter(partition)
    if len(filter_pattern.encode("utf-8")) > FILTER_MAX_BYTES:
        failures.append("current-run Swift filter exceeds its byte bound")
    try:
        selected_by_filter = tuple(
            sorted(
                identity
                for identity in partition.discovered
                if re.search(filter_pattern, identity)
            )
        )
    except re.error as error:
        failures.append(f"current-run Swift filter is invalid: {error}")
        selected_by_filter = ()
    if selected_by_filter != partition.selected:
        failures.append("current-run Swift filter differs from the 1,173-test union")
    command = (
        "/usr/bin/sandbox-exec",
        "-p",
        product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
        "/usr/bin/swift",
        "test",
        "--disable-sandbox",
        "--no-parallel",
        "--filter",
        filter_pattern,
    )
    if "--skip" in command:
        failures.append("current-run Swift command must not use a skip filter")
    return (None if failures else command), failures


def command_environment_footprint(
    command: tuple[str, ...],
    environment: dict[str, str],
) -> int:
    return sum(len(os.fsencode(value)) + 1 for value in command) + sum(
        len(os.fsencode(key)) + len(os.fsencode(value)) + 2
        for key, value in environment.items()
    )


def command_environment(
    partition: CurrentRunPartition,
    *,
    run_network_probe: bool,
) -> tuple[tuple[str, ...] | None, dict[str, str] | None, list[str]]:
    command, failures = command_and_filter_failures(partition)
    environment, environment_failures = product_ci.g7_nonsecurity_swift_environment()
    failures.extend(environment_failures)
    if run_network_probe:
        failures.extend(product_ci.g7_nonsecurity_swift_network_sandbox_self_test())
    if command is not None:
        for executable in (Path(command[0]), Path(command[3])):
            try:
                value = executable.lstat()
            except OSError as error:
                failures.append(
                    f"current-run Swift executable cannot be inspected: "
                    f"{executable}: {error}"
                )
                continue
            if (
                stat.S_ISLNK(value.st_mode)
                or not stat.S_ISREG(value.st_mode)
                or not os.access(executable, os.X_OK)
            ):
                failures.append(
                    f"current-run Swift executable must be physical: {executable}"
                )
    if command is not None and environment is not None:
        if command_environment_footprint(command, environment) > (
            COMMAND_AND_ENVIRONMENT_MAX_BYTES
        ):
            failures.append("current-run Swift argv/environment exceeds its bound")
    if failures:
        return None, None, failures
    return command, environment, []


def partition_record(identities: tuple[str, ...]) -> dict[str, object]:
    return {
        "manifestSha256": manifest_sha256(identities),
        "tests": len(identities),
    }


def execution_contract_payload(
    partition: CurrentRunPartition,
    command: tuple[str, ...],
    environment: dict[str, str],
) -> dict[str, object]:
    return {
        "command": list(command),
        "commandAndEnvironmentBytes": command_environment_footprint(
            command,
            environment,
        ),
        "commandAndEnvironmentMaximumBytes": (
            COMMAND_AND_ENVIRONMENT_MAX_BYTES
        ),
        "contract": EXECUTION_CONTRACT,
        "environment": environment,
        "networkDenyProbePassed": True,
        "networkDenyProfile": product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE,
        "schemaVersion": SCHEMA_VERSION,
        "selection": {
            "baseDistinct": partition_record(partition.base_distinct),
            "discovered": partition_record(partition.discovered),
            "expanded": partition_record(partition.expanded),
            "focused": partition_record(partition.focused),
            "focusedExpandedOverlap": FOCUSED_EXPANDED_OVERLAP_COUNT,
            "notExecuted": partition_record(partition.not_executed),
            "selected": partition_record(partition.selected),
            "v2New": partition_record(partition.v2_new),
            "v3New": partition_record(partition.v3_new),
            "v4New": partition_record(partition.v4_new),
        },
        "singleSwiftInvocation": True,
    }


def read_canonical_json(
    path: Path,
    *,
    maximum_bytes: int,
) -> tuple[dict[str, object] | None, bytes | None, list[str]]:
    try:
        value = path.lstat()
        data = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        return None, None, [f"{path.relative_to(ROOT)} cannot be read: {error}"]
    failures: list[str] = []
    if not stat.S_ISREG(value.st_mode) or stat.S_ISLNK(value.st_mode):
        failures.append(f"{path.relative_to(ROOT)} must be a physical file")
    if value.st_nlink != 1:
        failures.append(f"{path.relative_to(ROOT)} must have one link")
    if len(data) > maximum_bytes:
        failures.append(f"{path.relative_to(ROOT)} exceeds its byte bound")
    if (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        failures.append(f"{path.relative_to(ROOT)} changed during read")
    try:
        document = json.loads(
            data,
            object_pairs_hook=addon_v4.candidate_base.reject_duplicate_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        addon_v4.candidate_base.DuplicateKeyError,
    ) as error:
        return None, data, failures + [
            f"{path.relative_to(ROOT)} is invalid JSON: {error}"
        ]
    if type(document) is not dict or canonical_json_bytes(document) != data:
        failures.append(f"{path.relative_to(ROOT)} must be canonical JSON")
    return (document if type(document) is dict else None), data, failures


def execution_contract_failures(
    partition: CurrentRunPartition,
    *,
    expected_environment: dict[str, str] | None = None,
) -> list[str]:
    command, command_failures = command_and_filter_failures(partition)
    if command is None:
        return command_failures
    document, _data, failures = read_canonical_json(
        EXECUTION_CONTRACT_PATH,
        maximum_bytes=EXECUTION_CONTRACT_MAX_BYTES,
    )
    failures.extend(command_failures)
    if document is None:
        return failures
    environment = document.get("environment")
    if type(environment) is not dict or any(
        type(key) is not str or type(value) is not str
        for key, value in (
            environment.items() if type(environment) is dict else ()
        )
    ):
        failures.append("execution contract environment must be string mapping")
        return failures
    normalized, environment_failures = (
        product_ci.g7_nonsecurity_swift_environment(environment)
    )
    failures.extend(environment_failures)
    if normalized != environment:
        failures.append("execution contract environment is not the exact allowlist")
    if expected_environment is not None and environment != expected_environment:
        failures.append("execution contract environment differs from this run")
    if document != execution_contract_payload(partition, command, environment):
        failures.append("execution contract payload differs")
    return failures


def ensure_output_directory(*, create: bool) -> list[str]:
    try:
        value = OUTPUT_ROOT.lstat()
    except FileNotFoundError:
        if not create:
            return ["current-run output directory is missing"]
        try:
            OUTPUT_ROOT.mkdir(mode=0o700)
            value = OUTPUT_ROOT.lstat()
        except OSError as error:
            return [f"current-run output directory cannot be created: {error}"]
    except OSError as error:
        return [f"current-run output directory cannot be inspected: {error}"]
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
        return ["current-run output directory must be physical"]
    if stat.S_IMODE(value.st_mode) != 0o700:
        return ["current-run output directory mode must be 0700"]
    return []


def common_arguments(partition: CurrentRunPartition) -> dict[str, object]:
    return {
        "binding_path": BINDING_PATH,
        "marker_path": RUN_MARKER_PATH,
        "log_path": CONSOLE_PATH,
        "test_list_path": TEST_LIST_PATH,
        "filter_pattern": combined_filter(partition),
        "expected_count": SELECTED_TEST_COUNT,
        "expected_manifest_sha256": SELECTED_TEST_MANIFEST_SHA256,
        "excluded_tests": (),
        "exact_files": EXACT_SOURCE_FILES,
    }


def prepare(partition: CurrentRunPartition) -> list[str]:
    failures = ensure_output_directory(create=True)
    command, environment, contract_failures = command_environment(
        partition,
        run_network_probe=True,
    )
    failures.extend(contract_failures)
    if command is None or environment is None or failures:
        return failures
    failures.extend(
        product_ci.write_canonical_json_payload(
            EXECUTION_CONTRACT_PATH,
            execution_contract_payload(partition, command, environment),
            label="G7 current-run execution contract",
        )
    )
    if not failures:
        failures.extend(
            execution_contract_failures(
                partition,
                expected_environment=environment,
            )
        )
    if not failures:
        marker_arguments = dict(common_arguments(partition))
        marker_arguments.pop("binding_path")
        marker_arguments.pop("log_path")
        failures.extend(
            product_ci.write_swift_focused_test_run_marker(**marker_arguments)
        )
    return failures


def run(partition: CurrentRunPartition) -> tuple[int, list[str]]:
    failures = ensure_output_directory(create=False)
    command, environment, contract_failures = command_environment(
        partition,
        run_network_probe=True,
    )
    failures.extend(contract_failures)
    if command is None or environment is None:
        return 1, failures
    failures.extend(
        execution_contract_failures(
            partition,
            expected_environment=environment,
        )
    )
    arguments = common_arguments(partition)
    marker_arguments = {
        key: value
        for key, value in arguments.items()
        if key not in ("binding_path",)
    }
    marker_arguments["require_log"] = False
    failures.extend(
        product_ci.swift_focused_test_run_marker_failures(**marker_arguments)
    )
    if failures:
        return 1, failures
    _, expected_tests, selection_failures = (
        product_ci.swift_focused_test_list_snapshot(
            test_list_path=TEST_LIST_PATH,
            filter_pattern=combined_filter(partition),
            expected_count=SELECTED_TEST_COUNT,
            expected_manifest_sha256=SELECTED_TEST_MANIFEST_SHA256,
            excluded_tests=(),
        )
    )
    failures.extend(selection_failures)
    if expected_tests is None or failures:
        return 1, failures

    def validate_log_context(candidate_log_path: Path) -> list[str]:
        return product_ci.swift_focused_test_run_marker_failures(
            marker_path=RUN_MARKER_PATH,
            log_path=candidate_log_path,
            test_list_path=TEST_LIST_PATH,
            filter_pattern=combined_filter(partition),
            expected_count=SELECTED_TEST_COUNT,
            expected_manifest_sha256=SELECTED_TEST_MANIFEST_SHA256,
            excluded_tests=(),
            exact_files=EXACT_SOURCE_FILES,
        )

    return product_ci.run_and_publish_swift_focused_log(
        command=command,
        cwd=ROOT,
        log_path=CONSOLE_PATH,
        expected_tests=expected_tests,
        log_context_failures=validate_log_context,
        timeout_seconds=RUN_TIMEOUT_SECONDS,
        environment=environment,
    )


def file_record(path: Path, *, maximum_bytes: int) -> dict[str, object]:
    try:
        value = path.lstat()
        data = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise RuntimeError(f"{path.relative_to(ROOT)} cannot be read: {error}") from error
    if (
        stat.S_ISLNK(value.st_mode)
        or not stat.S_ISREG(value.st_mode)
        or value.st_nlink != 1
        or len(data) > maximum_bytes
        or (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise RuntimeError(f"{path.relative_to(ROOT)} is not a stable single-link file")
    return {
        "bytes": len(data),
        "mode": stat.S_IMODE(value.st_mode),
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def result_payload(
    partition: CurrentRunPartition,
) -> tuple[dict[str, object] | None, list[str]]:
    binding, _binding_bytes, failures = read_canonical_json(
        BINDING_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if binding is None:
        return None, failures
    source_inputs = binding.get("sourceInputs")
    if (
        type(source_inputs) is not dict
        or set(source_inputs) != {"count", "sha256"}
        or type(source_inputs.get("count")) is not int
        or type(source_inputs.get("sha256")) is not str
    ):
        return None, failures + ["binding sourceInputs shape differs"]
    try:
        artifacts = {
            "binding": file_record(BINDING_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "console": file_record(
                CONSOLE_PATH,
                maximum_bytes=product_ci.SWIFT_FOCUSED_TEST_MAX_LOG_BYTES,
            ),
            "executionContract": file_record(
                EXECUTION_CONTRACT_PATH,
                maximum_bytes=EXECUTION_CONTRACT_MAX_BYTES,
            ),
            "runMarker": file_record(RUN_MARKER_PATH, maximum_bytes=RESULT_MAX_BYTES),
            "testList": file_record(TEST_LIST_PATH, maximum_bytes=RESULT_MAX_BYTES),
        }
    except RuntimeError as error:
        return None, failures + [str(error)]
    command, command_failures = command_and_filter_failures(partition)
    failures.extend(command_failures)
    if command is None:
        return None, failures
    execution_document, _data, execution_failures = read_canonical_json(
        EXECUTION_CONTRACT_PATH,
        maximum_bytes=EXECUTION_CONTRACT_MAX_BYTES,
    )
    failures.extend(execution_failures)
    if execution_document is None:
        return None, failures
    return (
        {
            "artifacts": artifacts,
            "contract": CONTRACT,
            "coverage": {
                "baseDistinct": partition_record(partition.base_distinct),
                "discovered": partition_record(partition.discovered),
                "expanded": partition_record(partition.expanded),
                "focused": partition_record(partition.focused),
                "focusedExpandedOverlap": FOCUSED_EXPANDED_OVERLAP_COUNT,
                "notExecuted": partition_record(partition.not_executed),
                "selected": partition_record(partition.selected),
                "v2New": partition_record(partition.v2_new),
                "v3New": partition_record(partition.v3_new),
                "v4New": partition_record(partition.v4_new),
            },
            "execution": {
                "commandAndEnvironmentBytes": execution_document.get(
                    "commandAndEnvironmentBytes"
                ),
                "filterBytes": len(combined_filter(partition).encode("utf-8")),
                "networkDenyProfile": (
                    product_ci.G7_NONSECURITY_SWIFT_SANDBOX_PROFILE
                ),
                "singleSwiftInvocation": True,
            },
            "limitations": LIMITATIONS,
            "result": "passed",
            "schemaVersion": SCHEMA_VERSION,
            "sourceInputs": source_inputs,
        },
        failures,
    )


def result_failures(partition: CurrentRunPartition) -> list[str]:
    failures = ensure_output_directory(create=False)
    failures.extend(execution_contract_failures(partition))
    failures.extend(
        product_ci.swift_focused_test_binding_failures(
            **common_arguments(partition)
        )
    )
    expected, payload_failures = result_payload(partition)
    failures.extend(payload_failures)
    if expected is None:
        return failures
    observed, data, result_read_failures = read_canonical_json(
        RESULT_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    failures.extend(result_read_failures)
    if observed is not None and data != canonical_json_bytes(expected):
        failures.append("current-run result does not exactly bind current evidence")
    try:
        result_mode = stat.S_IMODE(RESULT_PATH.lstat().st_mode)
    except OSError:
        result_mode = -1
    if result_mode != 0o600:
        failures.append("current-run result mode must be 0600")
    return failures


def write_binding_and_result(partition: CurrentRunPartition) -> list[str]:
    failures = ensure_output_directory(create=False)
    failures.extend(execution_contract_failures(partition))
    if not failures:
        failures.extend(
            product_ci.write_swift_focused_test_binding(
                **common_arguments(partition)
            )
        )
    payload, payload_failures = result_payload(partition)
    failures.extend(payload_failures)
    if payload is not None and not failures:
        failures.extend(
            product_ci.write_canonical_json_payload(
                RESULT_PATH,
                payload,
                label="G7 current-run aggregate result",
            )
        )
    if not failures:
        failures.extend(result_failures(partition))
    return failures


def print_failures(prefix: str, failures: list[str]) -> int:
    for failure in failures:
        print(f"{prefix}: {failure}", file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--write-binding", action="store_true")
    mode.add_argument("--results", action="store_true")
    arguments = parser.parse_args(argv)

    partition, failures = reconstruct_partition()
    if partition is None:
        return print_failures("G7 current-run preflight failed", failures)
    if arguments.self_test:
        command, environment, contract_failures = command_environment(
            partition,
            run_network_probe=True,
        )
        failures.extend(contract_failures)
        if command is None or environment is None or failures:
            return print_failures("G7 current-run self-test failed", failures)
        print(
            "G7 current-run contract self-test passed: "
            f"{SELECTED_TEST_COUNT}/{DISCOVERED_TEST_COUNT} selected."
        )
        return 0
    if arguments.prepare:
        failures = prepare(partition)
        if failures:
            return print_failures("G7 current-run preparation failed", failures)
        print(
            "G7 current-run source marker passed: "
            f"{SELECTED_TEST_COUNT} selected, {NOT_EXECUTED_TEST_COUNT} excluded."
        )
        return 0
    if arguments.run:
        status, failures = run(partition)
        if status != 0 or failures:
            return print_failures("G7 current-run execution failed", failures)
        print(
            "G7 current-run Swift execution passed: "
            f"{SELECTED_TEST_COUNT}/{SELECTED_TEST_COUNT}; skipped=0; "
            "failures=0; network denied."
        )
        return 0
    if arguments.write_binding:
        failures = write_binding_and_result(partition)
        if failures:
            return print_failures("G7 current-run binding failed", failures)
        print(
            "G7 current-run result bound: "
            f"{SELECTED_TEST_COUNT}/{DISCOVERED_TEST_COUNT} current-source tests."
        )
        return 0
    failures = result_failures(partition)
    if failures:
        return print_failures("G7 current-run readback failed", failures)
    print(
        "G7 current-run producer readback passed: "
        f"{SELECTED_TEST_COUNT}/{SELECTED_TEST_COUNT}; canonical G7 remains open."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
