#!/usr/bin/env python3
"""Produce the source-stable G7 non-security Merge-full V2 candidate.

V2 preserves the original 67-command matrix as an exact prefix and appends the
reviewed Swift add-on contract, execution, binding, and readback.  It remains a
local non-security candidate and makes no canonical G7, RC, GA, or V1 claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Sequence

if __package__:
    from script import run_g7_nonsecurity_merge_full_candidate as base
else:
    import run_g7_nonsecurity_merge_full_candidate as base


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetherlink-g7-nonsecurity-merge-full-local-candidate-v2"
SCHEMA_VERSION = 1
RESULT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v2/candidate.json"
)
RESULT_MAX_BYTES = 1024 * 1024
BASE_COMMAND_COUNT = 67
BASE_COMMAND_IDS_MANIFEST_SHA256 = (
    "6f8c3054b877ab856f5ac32e40cba9156439545ad4bdba76d404a5aa24a4ba1d"
)

LIMITATIONS = dict(base.LIMITATIONS)
COVERAGE = {
    **base.COVERAGE,
    "swiftDiscoveredTests": 2_173,
    "swiftDistinctNonsecurityTests": 1_023,
    "swiftNotExecutedTests": 1_150,
    "swiftReviewedAddonTests": 626,
    "swiftReviewedMethodTests": 315,
    "swiftRunnerReviewedBeforeExclusion": 711,
}

V2_IMPLEMENTATION_PATHS = (
    Path("script/check_g7_nonsecurity_merge_full_candidate_v2.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon.py"),
    Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v2.txt"),
    Path("script/run_g7_nonsecurity_merge_full_candidate_v2.py"),
    Path("script/test_check_g7_reviewed_nonsecurity_swift_addon.py"),
    Path("script/test_g7_nonsecurity_merge_full_candidate_v2.py"),
)
IMPLEMENTATION_PATHS = tuple(
    sorted(
        set(base.IMPLEMENTATION_PATHS) | set(V2_IMPLEMENTATION_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

ADDON_ARTIFACT_PATHS = tuple(
    Path(value)
    for value in (
        ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/candidate.json",
        ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v2/binding.json",
        ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v2/console.log",
        (
            ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v2/"
            "execution-contract.json"
        ),
        ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v2/result.json",
        ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v2/run-marker.json",
    )
)
ARTIFACT_PATHS = tuple(
    sorted(
        set(base.ARTIFACT_PATHS) | set(ADDON_ARTIFACT_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

ADDON_SCRIPT = "script/check_g7_reviewed_nonsecurity_swift_addon.py"
ADDON_OUTPUT_PARENT = Path(
    ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v2"
)
ADDITIONAL_GATES = (
    base.python_gate(
        "g7-reviewed-nonsecurity-swift-addon-v2-prepare",
        ADDON_SCRIPT,
        "--prepare",
    ),
    base.python_gate(
        "g7-reviewed-nonsecurity-swift-addon-v2-run",
        ADDON_SCRIPT,
        "--run",
        timeout_seconds=1_500,
    ),
    base.python_gate(
        "g7-reviewed-nonsecurity-swift-addon-v2-write-binding",
        ADDON_SCRIPT,
        "--write-binding",
    ),
    base.python_gate(
        "g7-reviewed-nonsecurity-swift-addon-v2-results",
        ADDON_SCRIPT,
        "--results",
    ),
)
ALL_GATES = base.ALL_GATES + ADDITIONAL_GATES
EXPECTED_COMMAND_IDS = tuple(gate.identifier for gate in ALL_GATES)
V1_CANDIDATE_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/candidate.json"
)
EXPECTED_V1_CANDIDATE_RECORD = {
    "mode": 0o600,
    "path": V1_CANDIDATE_RELATIVE_PATH.as_posix(),
    "sha256": "d48ac61a355ecb381100941881a72945144acc16926c27671c3c7ebde4020301",
    "size": 41_459,
}


CandidateError = base.CandidateError


def ordered_identity_manifest(values: Sequence[str]) -> str:
    payload = json.dumps(
        list(values),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def validate_static_contract() -> None:
    if base.CONTRACT != "aetherlink-g7-nonsecurity-merge-full-local-candidate-v1":
        raise CandidateError("V1 candidate contract identity changed")
    if base.RESULT_RELATIVE_PATH != Path(
        ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/candidate.json"
    ):
        raise CandidateError("V1 candidate result path changed")
    if len(base.EXPECTED_COMMAND_IDS) != BASE_COMMAND_COUNT:
        raise CandidateError("V1 command count changed")
    if tuple(base.EXPECTED_COMMAND_IDS) != tuple(
        gate.identifier for gate in base.ALL_GATES
    ):
        raise CandidateError("V1 command sequence differs from its gates")
    if (
        ordered_identity_manifest(base.EXPECTED_COMMAND_IDS)
        != BASE_COMMAND_IDS_MANIFEST_SHA256
    ):
        raise CandidateError("V1 command identity manifest changed")
    if EXPECTED_COMMAND_IDS[:BASE_COMMAND_COUNT] != base.EXPECTED_COMMAND_IDS:
        raise CandidateError("V2 does not preserve the exact V1 command prefix")
    if len(EXPECTED_COMMAND_IDS) != 71 or len(set(EXPECTED_COMMAND_IDS)) != 71:
        raise CandidateError("V2 command sequence must contain 71 unique commands")
    if tuple(sorted(ARTIFACT_PATHS, key=lambda path: path.as_posix())) != ARTIFACT_PATHS:
        raise CandidateError("V2 artifact paths must be sorted")
    if len(ARTIFACT_PATHS) != 32 or len(set(ARTIFACT_PATHS)) != 32:
        raise CandidateError("V2 artifact paths must contain exactly 32 entries")
    if tuple(sorted(IMPLEMENTATION_PATHS, key=lambda path: path.as_posix())) != (
        IMPLEMENTATION_PATHS
    ):
        raise CandidateError("V2 implementation paths must be sorted")
    if len(IMPLEMENTATION_PATHS) != 11 or len(set(IMPLEMENTATION_PATHS)) != 11:
        raise CandidateError("V2 implementation paths must contain exactly 11 entries")
    if RESULT_RELATIVE_PATH == base.RESULT_RELATIVE_PATH or CONTRACT == base.CONTRACT:
        raise CandidateError("V2 must remain isolated from V1 result bytes")


def candidate_payload(
    *,
    source: dict[str, object],
    commands: Sequence[dict[str, object]],
    artifacts: Sequence[dict[str, object]],
    implementation: Sequence[dict[str, object]],
    pid_preservation: dict[str, object],
    v1_artifact_preservation: dict[str, object],
) -> dict[str, object]:
    return {
        "artifacts": list(artifacts),
        "commands": list(commands),
        "contract": CONTRACT,
        "coverage": dict(COVERAGE),
        "implementation": list(implementation),
        "limitations": dict(LIMITATIONS),
        "pidPreservation": pid_preservation,
        "result": "passed",
        "schemaVersion": SCHEMA_VERSION,
        "source": source,
        "v1ArtifactPreservation": v1_artifact_preservation,
    }


def produce_candidate(
    *,
    root: Path = ROOT,
    result_path: Path,
    preserve_pid: int | None,
) -> dict[str, object]:
    validate_static_contract()
    canonical_result_path = root / RESULT_RELATIVE_PATH
    if not result_path.is_absolute():
        result_path = root / result_path
    if result_path != canonical_result_path:
        raise CandidateError(
            "candidate result must use the exact canonical V2 result path"
        )

    base.ensure_directory(result_path.parent)
    source_before = base.source_snapshot(root=root)
    v1_candidate_before = base.stable_file_record(
        V1_CANDIDATE_RELATIVE_PATH,
        root=root,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if v1_candidate_before != EXPECTED_V1_CANDIDATE_RECORD:
        raise CandidateError("V1 antecedent candidate identity differs before execution")
    pid_before = base.process_identity(preserve_pid) if preserve_pid is not None else ""
    command_records: list[dict[str, object]] = []
    macos_source_before: str | None = None
    macos_source_after: str | None = None
    environment = base.command_environment()

    for gate in ALL_GATES:
        if gate.identifier == "g7-reviewed-nonsecurity-swift-addon-v2-prepare":
            base.ensure_directory(root / ADDON_OUTPUT_PARENT)
        output_parent = base.OUTPUT_PARENT_BY_PRODUCER_ID.get(gate.identifier)
        if output_parent is not None:
            base.ensure_directory(root / output_parent)
        record, stdout, _stderr = base.run_gate_with_managed_release_scratch(
            gate,
            root=root,
            environment=environment,
        )
        command_records.append(record)
        if gate.identifier == "macos-release-source-before":
            macos_source_before = stdout.decode("ascii", errors="strict").strip()
        elif gate.identifier == "macos-release-source-after":
            macos_source_after = stdout.decode("ascii", errors="strict").strip()
            if (
                macos_source_before is None
                or macos_source_after != macos_source_before
                or len(macos_source_after) != 64
            ):
                raise CandidateError("macOS Release source changed during packaging")
        elif gate.identifier == "android-release-build":
            base.validate_zero_lint_issues(root=root)

    base.validate_zero_lint_issues(root=root)
    artifacts = tuple(base.stable_file_record(path, root=root) for path in ARTIFACT_PATHS)
    implementation = tuple(
        base.stable_file_record(path, root=root, maximum_bytes=4 * 1024 * 1024)
        for path in IMPLEMENTATION_PATHS
    )
    v1_candidate_after = base.stable_file_record(
        V1_CANDIDATE_RELATIVE_PATH,
        root=root,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if v1_candidate_after != v1_candidate_before:
        raise CandidateError("V1 antecedent candidate changed during execution")
    v1_artifact_preservation = {
        "after": v1_candidate_after,
        "before": v1_candidate_before,
        "preservedDuringRun": True,
    }
    source_after = base.source_snapshot(root=root)
    if source_after != source_before:
        raise CandidateError("candidate source changed during execution")
    pid_after = base.process_identity(preserve_pid) if preserve_pid is not None else ""
    preservation = base.pid_record(preserve_pid, pid_before, pid_after)
    if preserve_pid is not None and not preservation["preservedDuringRun"]:
        raise CandidateError(f"preserved PID {preserve_pid} changed during execution")
    payload = candidate_payload(
        source=source_before,
        commands=command_records,
        artifacts=artifacts,
        implementation=implementation,
        pid_preservation=preservation,
        v1_artifact_preservation=v1_artifact_preservation,
    )
    encoded = base.canonical_json_bytes(payload)
    if len(encoded) > RESULT_MAX_BYTES:
        raise CandidateError("candidate result exceeds its byte limit")
    base.atomic_write(result_path, encoded)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result",
        type=Path,
        default=RESULT_RELATIVE_PATH,
        help="exact canonical V2 result path (alternate paths are rejected)",
    )
    parser.add_argument(
        "--preserve-pid",
        type=int,
        help="existing unrelated AetherLink PID that must survive the run",
    )
    arguments = parser.parse_args()
    try:
        payload = produce_candidate(
            result_path=arguments.result,
            preserve_pid=arguments.preserve_pid,
        )
    except CandidateError as error:
        print(f"G7 non-security Merge-full V2 candidate failed: {error}", file=os.sys.stderr)
        return 1
    print(
        "G7 non-security Merge-full V2 local candidate published: "
        f"{len(payload['commands'])} commands, "
        f"{payload['coverage']['swiftDistinctNonsecurityTests']} distinct Swift, "
        f"{payload['coverage']['androidFullAppTests']} Android app tests."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
