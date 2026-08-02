#!/usr/bin/env python3
"""Compose the V2 Merge-full evidence with the current V3 Swift add-on.

The V2 candidate remains immutable evidence for its 71 executed commands.  This
successor runs only the four V3 add-on commands against an exact evidence-only
source delta, records those four commands truthfully, and publishes a composed
local candidate.  It does not claim canonical Merge-full, G7 exit, RC, GA, or
V1 qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Sequence

if __package__:
    from script import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
    from script import run_g7_nonsecurity_merge_full_candidate_v2 as base
else:
    import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
    import run_g7_nonsecurity_merge_full_candidate_v2 as base


ROOT = Path(__file__).resolve().parents[1]
runtime = base.base
CONTRACT = "aetherlink-g7-nonsecurity-merge-full-local-candidate-v3"
SCHEMA_VERSION = 1
RESULT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v3/candidate.json"
)
RESULT_MAX_BYTES = 1024 * 1024

ANTECEDENT_COMMAND_COUNT = 71
ANTECEDENT_COMMAND_IDS_MANIFEST_SHA256 = (
    "57ff84413ed39d9680c3f0fd44d31c79c0581baf622ebcb6180655d38789e4c5"
)
COMPOSED_COMMAND_EVIDENCE_COUNT = 75
V2_SOURCE = {
    "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
    "fileCount": 1_002,
    "sha256": (
        "19b15cd5549da9eb20bf1f2dcc7d1541fa32f502a331ddc6bac5616f50a019d4"
    ),
    "size": 67_619_351,
}

LIMITATIONS = dict(base.LIMITATIONS)
COVERAGE = {
    **base.COVERAGE,
    "swiftDistinctNonsecurityTests": 1_120,
    "swiftExcludedByScopeTests": 966,
    "swiftExternalOrSocketExcludedTests": 87,
    "swiftNotExecutedTests": 1_053,
    "swiftReviewedAddonTests": 723,
    "swiftReviewedMethodTests": 412,
    "swiftRunnerReviewedBeforeExclusion": 808,
    "swiftUnclassifiedTests": 0,
}

V3_IMPLEMENTATION_PATHS = (
    Path("script/check_g7_nonsecurity_merge_full_candidate_v3.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v3.py"),
    Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v3.txt"),
    Path("script/run_g7_nonsecurity_merge_full_candidate_v3.py"),
    Path("script/test_check_g7_reviewed_nonsecurity_swift_addon_v3.py"),
    Path("script/test_g7_nonsecurity_merge_full_candidate_v3.py"),
)
IMPLEMENTATION_PATHS = tuple(
    sorted(
        set(base.IMPLEMENTATION_PATHS) | set(V3_IMPLEMENTATION_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

V2_CANDIDATE_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v2/candidate.json"
)
EXPECTED_V2_CANDIDATE_RECORD = {
    "mode": 0o600,
    "path": V2_CANDIDATE_RELATIVE_PATH.as_posix(),
    "sha256": "4a05156b1f1d06d613a40d456f34af793c6d7647b6f639937bdf2190aaf24f45",
    "size": 45_797,
}
ADDON_OUTPUT_PARENT = Path(".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v3")
V3_ADDON_RESULT_RELATIVE_PATH = ADDON_OUTPUT_PARENT / "result.json"
EXPECTED_ADDON_ARTIFACT_RELATIVE_PATHS = (
    ADDON_OUTPUT_PARENT / "binding.json",
    ADDON_OUTPUT_PARENT / "console.log",
    ADDON_OUTPUT_PARENT / "execution-contract.json",
    V3_ADDON_RESULT_RELATIVE_PATH,
    ADDON_OUTPUT_PARENT / "run-marker.json",
    Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v3.txt"),
)
V3_ADDON_ARTIFACT_PATHS = (
    V2_CANDIDATE_RELATIVE_PATH,
    *EXPECTED_ADDON_ARTIFACT_RELATIVE_PATHS,
)
ARTIFACT_PATHS = tuple(
    sorted(
        set(base.ARTIFACT_PATHS) | set(V3_ADDON_ARTIFACT_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

ADDON_SCRIPT = "script/check_g7_reviewed_nonsecurity_swift_addon_v3.py"
ADDITIONAL_GATES = (
    runtime.python_gate(
        "g7-reviewed-nonsecurity-swift-addon-v3-prepare",
        ADDON_SCRIPT,
        "--prepare",
    ),
    runtime.python_gate(
        "g7-reviewed-nonsecurity-swift-addon-v3-run",
        ADDON_SCRIPT,
        "--run",
        timeout_seconds=1_500,
    ),
    runtime.python_gate(
        "g7-reviewed-nonsecurity-swift-addon-v3-write-binding",
        ADDON_SCRIPT,
        "--write-binding",
    ),
    runtime.python_gate(
        "g7-reviewed-nonsecurity-swift-addon-v3-results",
        ADDON_SCRIPT,
        "--results",
    ),
)
ALL_GATES = ADDITIONAL_GATES
EXPECTED_COMMAND_IDS = tuple(gate.identifier for gate in ALL_GATES)


CandidateError = runtime.CandidateError


def ensure_private_output_directory(
    path: Path,
    *,
    root: Path = ROOT,
) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise CandidateError("output directory must remain below the repository root") from error
    if not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
        raise CandidateError("output directory must be a canonical repository path")
    try:
        root_status = root.lstat()
    except OSError as error:
        raise CandidateError(f"repository root cannot be inspected: {error}") from error
    if stat.S_ISLNK(root_status.st_mode) or not stat.S_ISDIR(root_status.st_mode):
        raise CandidateError("repository root must be a physical directory")

    current = root
    for index, component in enumerate(relative.parts):
        current /= component
        final = index == len(relative.parts) - 1
        try:
            value = current.lstat()
        except FileNotFoundError:
            if not final:
                raise CandidateError(
                    f"output directory ancestor is missing: {current}"
                )
            try:
                current.mkdir(mode=0o700)
                value = current.lstat()
            except OSError as error:
                raise CandidateError(
                    f"output directory cannot be created: {current}: {error}"
                ) from error
        except OSError as error:
            raise CandidateError(
                f"output directory cannot be inspected: {current}: {error}"
            ) from error
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
            raise CandidateError(
                f"output directory chain must be physical: {current}"
            )
        if final and stat.S_IMODE(value.st_mode) != 0o700:
            raise CandidateError(f"output directory mode must be 0700: {current}")


def ordered_identity_manifest(values: Sequence[str]) -> str:
    payload = json.dumps(
        list(values),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def validate_static_contract() -> None:
    base.validate_static_contract()
    if base.CONTRACT != "aetherlink-g7-nonsecurity-merge-full-local-candidate-v2":
        raise CandidateError("V2 candidate contract identity changed")
    if base.RESULT_RELATIVE_PATH != V2_CANDIDATE_RELATIVE_PATH:
        raise CandidateError("V2 candidate result path changed")
    if len(base.EXPECTED_COMMAND_IDS) != ANTECEDENT_COMMAND_COUNT:
        raise CandidateError("V2 antecedent command count changed")
    if (
        ordered_identity_manifest(base.EXPECTED_COMMAND_IDS)
        != ANTECEDENT_COMMAND_IDS_MANIFEST_SHA256
    ):
        raise CandidateError("V2 antecedent command identity manifest changed")
    if len(EXPECTED_COMMAND_IDS) != 4 or len(set(EXPECTED_COMMAND_IDS)) != 4:
        raise CandidateError("V3 successor must execute four unique commands")
    if COMPOSED_COMMAND_EVIDENCE_COUNT != (
        ANTECEDENT_COMMAND_COUNT + len(EXPECTED_COMMAND_IDS)
    ):
        raise CandidateError("composed command evidence arithmetic differs")
    if tuple(
        sorted(ARTIFACT_PATHS, key=lambda path: path.as_posix().encode("ascii"))
    ) != ARTIFACT_PATHS:
        raise CandidateError("V3 artifact paths must be sorted")
    if len(ARTIFACT_PATHS) != 39 or len(set(ARTIFACT_PATHS)) != 39:
        raise CandidateError("V3 artifact paths must contain exactly 39 entries")
    if tuple(
        sorted(
            IMPLEMENTATION_PATHS,
            key=lambda path: path.as_posix().encode("ascii"),
        )
    ) != IMPLEMENTATION_PATHS:
        raise CandidateError("V3 implementation paths must be sorted")
    if len(IMPLEMENTATION_PATHS) != 17 or len(set(IMPLEMENTATION_PATHS)) != 17:
        raise CandidateError("V3 implementation paths must contain exactly 17 entries")
    if tuple(addon_v3.ANTECEDENT_PROJECTION_RELATIVE_PATHS) != V3_IMPLEMENTATION_PATHS:
        raise CandidateError("V3 evidence-only source delta differs")
    observed_addon_artifacts = tuple(
        sorted(
            (
                addon_v3.BINDING_PATH.relative_to(ROOT),
                addon_v3.CONSOLE_PATH.relative_to(ROOT),
                addon_v3.EXECUTION_CONTRACT_PATH.relative_to(ROOT),
                addon_v3.RESULT_PATH.relative_to(ROOT),
                addon_v3.RUN_MARKER_PATH.relative_to(ROOT),
                addon_v3.REVIEWED_IDENTITY_RELATIVE_PATH,
            ),
            key=lambda path: path.as_posix().encode("ascii"),
        )
    )
    if observed_addon_artifacts != EXPECTED_ADDON_ARTIFACT_RELATIVE_PATHS:
        raise CandidateError("V3 add-on artifact path contract differs")
    if addon_v3.OUTPUT_ROOT != ROOT / ADDON_OUTPUT_PARENT:
        raise CandidateError("V3 add-on output root contract differs")
    if RESULT_RELATIVE_PATH in ARTIFACT_PATHS:
        raise CandidateError("V3 candidate must not recursively record itself")
    if RESULT_RELATIVE_PATH in IMPLEMENTATION_PATHS:
        raise CandidateError("V3 candidate result must not be an implementation input")


def evidence_composition(
    *,
    v2_candidate: dict[str, object],
    v3_addon_result: dict[str, object],
) -> dict[str, object]:
    return {
        "antecedent": {
            "candidate": dict(v2_candidate),
            "commands": ANTECEDENT_COMMAND_COUNT,
            "swiftDistinctNonsecurityTests": 1_023,
        },
        "composedCommandEvidence": COMPOSED_COMMAND_EVIDENCE_COUNT,
        "evidenceOnlySourceDelta": [
            path.as_posix()
            for path in addon_v3.ANTECEDENT_PROJECTION_RELATIVE_PATHS
        ],
        "executionModel": "immutable-v2-antecedent-plus-v3-addon-v1",
        "projectedV2Source": dict(V2_SOURCE),
        "runtimeProductSourceChanged": False,
        "successor": {
            "commands": len(ALL_GATES),
            "result": dict(v3_addon_result),
            "swiftNewTests": addon_v3.NEW_TEST_COUNT,
        },
    }


def current_v3_addon_failures() -> list[str]:
    partition, failures = addon_v3.contract_inputs()
    if partition is None:
        return failures or ["V3 add-on contract inputs are unavailable"]
    failures.extend(addon_v3.result_failures(partition))
    return failures


def candidate_payload(
    *,
    source: dict[str, object],
    commands: Sequence[dict[str, object]],
    artifacts: Sequence[dict[str, object]],
    implementation: Sequence[dict[str, object]],
    pid_preservation: dict[str, object],
    v2_artifact_preservation: dict[str, object],
    composition: dict[str, object],
) -> dict[str, object]:
    return {
        "artifacts": list(artifacts),
        "commands": list(commands),
        "contract": CONTRACT,
        "coverage": dict(COVERAGE),
        "evidenceComposition": composition,
        "implementation": list(implementation),
        "limitations": dict(LIMITATIONS),
        "pidPreservation": pid_preservation,
        "result": "passed",
        "schemaVersion": SCHEMA_VERSION,
        "source": source,
        "v2ArtifactPreservation": v2_artifact_preservation,
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
            "candidate result must use the exact canonical V3 result path"
        )

    ensure_private_output_directory(result_path.parent, root=root)
    source_before = runtime.source_snapshot(root=root)
    v2_candidate_before = runtime.stable_file_record(
        V2_CANDIDATE_RELATIVE_PATH,
        root=root,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if v2_candidate_before != EXPECTED_V2_CANDIDATE_RECORD:
        raise CandidateError("V2 antecedent candidate identity differs before execution")
    antecedent_failures = addon_v3.candidate_antecedent_failures()
    if antecedent_failures:
        raise CandidateError(
            "V3 source projection failed before execution: "
            + "; ".join(antecedent_failures)
        )
    pid_before = runtime.process_identity(preserve_pid) if preserve_pid is not None else ""
    environment = runtime.command_environment()
    command_records: list[dict[str, object]] = []

    for gate in ALL_GATES:
        if gate.identifier == "g7-reviewed-nonsecurity-swift-addon-v3-prepare":
            ensure_private_output_directory(root / ADDON_OUTPUT_PARENT, root=root)
        record, _stdout, _stderr = runtime.run_gate_with_managed_release_scratch(
            gate,
            root=root,
            environment=environment,
        )
        command_records.append(record)

    runtime.validate_zero_lint_issues(root=root)
    artifacts_before_postflight = tuple(
        runtime.stable_file_record(path, root=root) for path in ARTIFACT_PATHS
    )
    implementation = tuple(
        runtime.stable_file_record(
            path,
            root=root,
            maximum_bytes=4 * 1024 * 1024,
        )
        for path in IMPLEMENTATION_PATHS
    )
    v2_candidate_after = runtime.stable_file_record(
        V2_CANDIDATE_RELATIVE_PATH,
        root=root,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if v2_candidate_after != v2_candidate_before:
        raise CandidateError("V2 antecedent candidate changed during execution")
    v2_artifact_preservation = {
        "after": v2_candidate_after,
        "before": v2_candidate_before,
        "preservedDuringRun": True,
    }
    postflight_failures = current_v3_addon_failures()
    if postflight_failures:
        raise CandidateError(
            "V2/V3 antecedent evidence changed during execution: "
            + "; ".join(postflight_failures)
        )
    artifacts = tuple(
        runtime.stable_file_record(path, root=root) for path in ARTIFACT_PATHS
    )
    if artifacts != artifacts_before_postflight:
        raise CandidateError("V2/V3 artifact bytes changed during postflight")
    v3_addon_result = next(
        record
        for record in artifacts
        if record["path"] == V3_ADDON_RESULT_RELATIVE_PATH.as_posix()
    )
    source_after = runtime.source_snapshot(root=root)
    if source_after != source_before:
        raise CandidateError("candidate source changed during execution")
    pid_after = runtime.process_identity(preserve_pid) if preserve_pid is not None else ""
    preservation = runtime.pid_record(preserve_pid, pid_before, pid_after)
    if preserve_pid is not None and not preservation["preservedDuringRun"]:
        raise CandidateError(f"preserved PID {preserve_pid} changed during execution")
    payload = candidate_payload(
        source=source_before,
        commands=command_records,
        artifacts=artifacts,
        implementation=implementation,
        pid_preservation=preservation,
        v2_artifact_preservation=v2_artifact_preservation,
        composition=evidence_composition(
            v2_candidate=v2_candidate_after,
            v3_addon_result=v3_addon_result,
        ),
    )
    encoded = runtime.canonical_json_bytes(payload)
    if len(encoded) > RESULT_MAX_BYTES:
        raise CandidateError("candidate result exceeds its byte limit")
    ensure_private_output_directory(result_path.parent, root=root)
    runtime.atomic_write(result_path, encoded)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result",
        type=Path,
        default=RESULT_RELATIVE_PATH,
        help="exact canonical V3 result path (alternate paths are rejected)",
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
        print(
            f"G7 non-security Merge-full V3 candidate failed: {error}",
            file=os.sys.stderr,
        )
        return 1
    print(
        "G7 non-security Merge-full V3 composed candidate published: "
        f"{len(payload['commands'])} new commands, "
        f"{COMPOSED_COMMAND_EVIDENCE_COUNT} composed command evidence, "
        f"{payload['coverage']['swiftDistinctNonsecurityTests']} distinct Swift, "
        f"{payload['coverage']['androidFullAppTests']} Android app tests."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
