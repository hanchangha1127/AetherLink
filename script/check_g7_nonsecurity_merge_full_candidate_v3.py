#!/usr/bin/env python3
"""Independently verify the composed local G7 Merge-full V3 candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Mapping, Sequence

if __package__:
    from script import check_g7_nonsecurity_merge_full_candidate_v2 as base
    from script import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3
else:
    import check_g7_nonsecurity_merge_full_candidate_v2 as base
    import check_g7_reviewed_nonsecurity_swift_addon_v3 as addon_v3


ROOT = Path(__file__).resolve().parents[1]
candidate_base = base.base
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
V2_CANDIDATE_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v2/candidate.json"
)
EXPECTED_V2_CANDIDATE_RECORD = {
    "mode": 0o600,
    "path": V2_CANDIDATE_RELATIVE_PATH.as_posix(),
    "sha256": "4a05156b1f1d06d613a40d456f34af793c6d7647b6f639937bdf2190aaf24f45",
    "size": 45_797,
}

EXPECTED_COVERAGE = {
    **base.EXPECTED_COVERAGE,
    "swiftDistinctNonsecurityTests": 1_120,
    "swiftExcludedByScopeTests": 966,
    "swiftExternalOrSocketExcludedTests": 87,
    "swiftNotExecutedTests": 1_053,
    "swiftReviewedAddonTests": 723,
    "swiftReviewedMethodTests": 412,
    "swiftRunnerReviewedBeforeExclusion": 808,
    "swiftUnclassifiedTests": 0,
}
EXPECTED_LIMITATIONS = dict(base.EXPECTED_LIMITATIONS)

V3_IMPLEMENTATION_PATHS = (
    Path("script/check_g7_nonsecurity_merge_full_candidate_v3.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v3.py"),
    Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v3.txt"),
    Path("script/run_g7_nonsecurity_merge_full_candidate_v3.py"),
    Path("script/test_check_g7_reviewed_nonsecurity_swift_addon_v3.py"),
    Path("script/test_g7_nonsecurity_merge_full_candidate_v3.py"),
)
EXPECTED_IMPLEMENTATION_PATHS = tuple(
    sorted(
        set(base.EXPECTED_IMPLEMENTATION_PATHS) | set(V3_IMPLEMENTATION_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)
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
EXPECTED_ARTIFACT_PATHS = tuple(
    sorted(
        set(base.EXPECTED_ARTIFACT_PATHS) | set(V3_ADDON_ARTIFACT_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

ADDON_SCRIPT = "script/check_g7_reviewed_nonsecurity_swift_addon_v3.py"
ADDITIONAL_COMMAND_SPECS = (
    (
        "g7-reviewed-nonsecurity-swift-addon-v3-prepare",
        ("python3", "-B", ADDON_SCRIPT, "--prepare"),
        600,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v3-run",
        ("python3", "-B", ADDON_SCRIPT, "--run"),
        1_500,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v3-write-binding",
        ("python3", "-B", ADDON_SCRIPT, "--write-binding"),
        600,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v3-results",
        ("python3", "-B", ADDON_SCRIPT, "--results"),
        600,
    ),
)
EXPECTED_COMMAND_IDS = tuple(
    identifier for identifier, _argv, _timeout in ADDITIONAL_COMMAND_SPECS
)
ADDON_READBACK_COMMAND = (
    "python3",
    "-B",
    ADDON_SCRIPT,
    "--results",
)


CandidateError = candidate_base.CandidateError


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
        raise CandidateError("V3 successor command sequence must contain four entries")
    if COMPOSED_COMMAND_EVIDENCE_COUNT != (
        ANTECEDENT_COMMAND_COUNT + len(EXPECTED_COMMAND_IDS)
    ):
        raise CandidateError("composed command evidence arithmetic differs")
    if tuple(
        sorted(
            EXPECTED_ARTIFACT_PATHS,
            key=lambda path: path.as_posix().encode("ascii"),
        )
    ) != EXPECTED_ARTIFACT_PATHS:
        raise CandidateError("V3 artifact paths must be sorted")
    if len(EXPECTED_ARTIFACT_PATHS) != 39 or len(set(EXPECTED_ARTIFACT_PATHS)) != 39:
        raise CandidateError("V3 artifact paths must contain exactly 39 entries")
    if tuple(
        sorted(
            EXPECTED_IMPLEMENTATION_PATHS,
            key=lambda path: path.as_posix().encode("ascii"),
        )
    ) != EXPECTED_IMPLEMENTATION_PATHS:
        raise CandidateError("V3 implementation paths must be sorted")
    if (
        len(EXPECTED_IMPLEMENTATION_PATHS) != 17
        or len(set(EXPECTED_IMPLEMENTATION_PATHS)) != 17
    ):
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


def current_antecedent_records(
    *,
    root: Path = ROOT,
) -> tuple[dict[str, object], dict[str, object]]:
    validate_static_contract()
    if root != ROOT:
        raise CandidateError("antecedent readback must use the canonical repository root")
    partition, failures = addon_v3.contract_inputs()
    if partition is None:
        raise CandidateError("V3 add-on contract inputs differ: " + "; ".join(failures))
    failures.extend(addon_v3.result_failures(partition))
    if failures:
        raise CandidateError("V3 add-on result differs: " + "; ".join(failures))
    v2_record = candidate_base.file_record(
        root,
        V2_CANDIDATE_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if v2_record != EXPECTED_V2_CANDIDATE_RECORD:
        raise CandidateError("V2 antecedent candidate current bytes differ")
    v3_record = candidate_base.file_record(
        root,
        V3_ADDON_RESULT_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    return v2_record, v3_record


def expected_composition(
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
            "commands": len(EXPECTED_COMMAND_IDS),
            "result": dict(v3_addon_result),
            "swiftNewTests": addon_v3.NEW_TEST_COUNT,
        },
    }


def validate_embedded_file_record(
    value: object,
    *,
    expected: Mapping[str, object],
    label: str,
) -> None:
    row = candidate_base.exact_mapping(
        value,
        {"mode", "path", "sha256", "size"},
        label,
    )
    candidate_base.require_exact_int(
        row["mode"],
        f"{label}.mode",
        maximum=0o7777,
    )
    candidate_base.validate_relative_path(row["path"], f"{label}.path")
    candidate_base.require_sha256(row["sha256"], f"{label}.sha256")
    candidate_base.require_exact_int(
        row["size"],
        f"{label}.size",
        maximum=RESULT_MAX_BYTES,
    )
    if row != expected:
        raise CandidateError(f"{label} differs")


def validate_evidence_composition(
    value: object,
    *,
    v2_candidate: Mapping[str, object],
    v3_addon_result: Mapping[str, object],
) -> None:
    row = candidate_base.exact_mapping(
        value,
        {
            "antecedent",
            "composedCommandEvidence",
            "evidenceOnlySourceDelta",
            "executionModel",
            "projectedV2Source",
            "runtimeProductSourceChanged",
            "successor",
        },
        "evidenceComposition",
    )
    antecedent = candidate_base.exact_mapping(
        row["antecedent"],
        {"candidate", "commands", "swiftDistinctNonsecurityTests"},
        "evidenceComposition.antecedent",
    )
    validate_embedded_file_record(
        antecedent["candidate"],
        expected=v2_candidate,
        label="evidenceComposition.antecedent.candidate",
    )
    if candidate_base.require_exact_int(
        antecedent["commands"],
        "evidenceComposition.antecedent.commands",
    ) != ANTECEDENT_COMMAND_COUNT:
        raise CandidateError("evidenceComposition.antecedent.commands differs")
    if candidate_base.require_exact_int(
        antecedent["swiftDistinctNonsecurityTests"],
        "evidenceComposition.antecedent.swiftDistinctNonsecurityTests",
    ) != 1_023:
        raise CandidateError(
            "evidenceComposition.antecedent.swiftDistinctNonsecurityTests differs"
        )
    if candidate_base.require_exact_int(
        row["composedCommandEvidence"],
        "evidenceComposition.composedCommandEvidence",
    ) != COMPOSED_COMMAND_EVIDENCE_COUNT:
        raise CandidateError("evidenceComposition.composedCommandEvidence differs")
    expected_delta = [
        path.as_posix()
        for path in addon_v3.ANTECEDENT_PROJECTION_RELATIVE_PATHS
    ]
    if type(row["evidenceOnlySourceDelta"]) is not list or row[
        "evidenceOnlySourceDelta"
    ] != expected_delta:
        raise CandidateError("evidenceComposition.evidenceOnlySourceDelta differs")
    if row["executionModel"] != "immutable-v2-antecedent-plus-v3-addon-v1":
        raise CandidateError("evidenceComposition.executionModel differs")
    projected_source = candidate_base.exact_mapping(
        row["projectedV2Source"],
        {"algorithm", "fileCount", "sha256", "size"},
        "evidenceComposition.projectedV2Source",
    )
    if projected_source["algorithm"] != V2_SOURCE["algorithm"]:
        raise CandidateError("evidenceComposition.projectedV2Source.algorithm differs")
    candidate_base.require_exact_int(
        projected_source["fileCount"],
        "evidenceComposition.projectedV2Source.fileCount",
        minimum=1,
    )
    candidate_base.require_sha256(
        projected_source["sha256"],
        "evidenceComposition.projectedV2Source.sha256",
    )
    candidate_base.require_exact_int(
        projected_source["size"],
        "evidenceComposition.projectedV2Source.size",
        maximum=candidate_base.SOURCE_TOTAL_MAX_BYTES,
    )
    if projected_source != V2_SOURCE:
        raise CandidateError("evidenceComposition.projectedV2Source differs")
    candidate_base.require_bool(
        row["runtimeProductSourceChanged"],
        False,
        "evidenceComposition.runtimeProductSourceChanged",
    )
    successor = candidate_base.exact_mapping(
        row["successor"],
        {"commands", "result", "swiftNewTests"},
        "evidenceComposition.successor",
    )
    if candidate_base.require_exact_int(
        successor["commands"],
        "evidenceComposition.successor.commands",
    ) != len(EXPECTED_COMMAND_IDS):
        raise CandidateError("evidenceComposition.successor.commands differs")
    validate_embedded_file_record(
        successor["result"],
        expected=v3_addon_result,
        label="evidenceComposition.successor.result",
    )
    if candidate_base.require_exact_int(
        successor["swiftNewTests"],
        "evidenceComposition.successor.swiftNewTests",
    ) != addon_v3.NEW_TEST_COUNT:
        raise CandidateError("evidenceComposition.successor.swiftNewTests differs")

    expected = expected_composition(
        v2_candidate=dict(v2_candidate),
        v3_addon_result=dict(v3_addon_result),
    )
    if row != expected:
        raise CandidateError("candidate evidence composition differs")


def validate_pid_preservation(value: object) -> None:
    candidate_base.validate_pid_preservation(value)
    row = candidate_base.exact_mapping(
        value,
        {"after", "before", "pid", "preservedDuringRun", "requested"},
        "pidPreservation",
    )
    candidate_base.require_bool(
        row["requested"],
        row["requested"],
        "pidPreservation.requested",
    )
    if row["requested"] is False:
        if candidate_base.require_exact_int(row["pid"], "pidPreservation.pid") != 0:
            raise CandidateError("pidPreservation.pid must be exactly zero when unrequested")
        candidate_base.require_bool(
            row["preservedDuringRun"],
            False,
            "pidPreservation.preservedDuringRun",
        )


def validate_commands(value: object) -> None:
    if type(value) is not list or len(value) != len(EXPECTED_COMMAND_IDS):
        raise CandidateError("commands record count differs")
    for index, (identifier, argv, timeout) in enumerate(ADDITIONAL_COMMAND_SPECS):
        base.validate_additional_command(
            value[index],
            index=index,
            expected_id=identifier,
            expected_argv=argv,
            expected_timeout=timeout,
        )


def run_addon_readback(root: Path) -> None:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    environment["PYTHONPATH"] = str(root)
    try:
        process = subprocess.Popen(
            ADDON_READBACK_COMMAND,
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        raise CandidateError(f"V3 add-on readback could not run: {error}") from error
    _stdout, stderr = candidate_base.bounded_child_output(
        process,
        command=ADDON_READBACK_COMMAND,
        timeout_seconds=candidate_base.READBACK_TIMEOUT_SECONDS,
        maximum_bytes=candidate_base.READBACK_STREAM_MAX_BYTES,
    )
    if process.returncode != 0:
        detail = stderr[:4096].decode("utf-8", errors="replace")
        raise CandidateError(f"V3 add-on readback failed: {detail}")


def validate_document(
    document: object,
    *,
    root: Path = ROOT,
    run_readbacks: bool = False,
) -> None:
    validate_static_contract()
    row = candidate_base.exact_mapping(
        document,
        {
            "artifacts",
            "commands",
            "contract",
            "coverage",
            "evidenceComposition",
            "implementation",
            "limitations",
            "pidPreservation",
            "result",
            "schemaVersion",
            "source",
            "v2ArtifactPreservation",
        },
        "result",
    )
    if row["contract"] != CONTRACT:
        raise CandidateError("candidate contract differs")
    if candidate_base.require_exact_int(
        row["schemaVersion"],
        "schemaVersion",
        minimum=1,
    ) != SCHEMA_VERSION:
        raise CandidateError("candidate schema version differs")
    if row["result"] != "passed":
        raise CandidateError("candidate result must be passed")

    coverage = candidate_base.exact_mapping(
        row["coverage"],
        set(EXPECTED_COVERAGE),
        "coverage",
    )
    for key, expected in EXPECTED_COVERAGE.items():
        if candidate_base.require_exact_int(coverage[key], f"coverage.{key}") != expected:
            raise CandidateError(f"coverage.{key} differs")
    limitations = candidate_base.exact_mapping(
        row["limitations"],
        set(EXPECTED_LIMITATIONS),
        "limitations",
    )
    for key, expected in EXPECTED_LIMITATIONS.items():
        candidate_base.require_bool(limitations[key], expected, f"limitations.{key}")

    recorded_source = candidate_base.exact_mapping(
        row["source"],
        {"algorithm", "fileCount", "sha256", "size"},
        "source",
    )
    if recorded_source["algorithm"] != candidate_base.SOURCE_ALGORITHM:
        raise CandidateError("source algorithm differs")
    candidate_base.require_exact_int(recorded_source["fileCount"], "source.fileCount", minimum=1)
    candidate_base.require_exact_int(
        recorded_source["size"],
        "source.size",
        maximum=candidate_base.SOURCE_TOTAL_MAX_BYTES,
    )
    candidate_base.require_sha256(recorded_source["sha256"], "source.sha256")
    if recorded_source != candidate_base.source_snapshot(root):
        raise CandidateError("source snapshot differs from current repository bytes")

    candidate_base.validate_file_records(
        row["artifacts"],
        expected_paths=EXPECTED_ARTIFACT_PATHS,
        label="artifacts",
        root=root,
    )
    candidate_base.validate_file_records(
        row["implementation"],
        expected_paths=EXPECTED_IMPLEMENTATION_PATHS,
        label="implementation",
        root=root,
    )
    validate_commands(row["commands"])
    validate_pid_preservation(row["pidPreservation"])

    v2_record, v3_record = current_antecedent_records(root=root)
    preservation = candidate_base.exact_mapping(
        row["v2ArtifactPreservation"],
        {"after", "before", "preservedDuringRun"},
        "v2ArtifactPreservation",
    )
    candidate_base.require_bool(
        preservation["preservedDuringRun"],
        True,
        "v2ArtifactPreservation.preservedDuringRun",
    )
    if preservation["before"] != v2_record or preservation["after"] != v2_record:
        raise CandidateError("V2 antecedent candidate preservation record differs")
    validate_evidence_composition(
        row["evidenceComposition"],
        v2_candidate=v2_record,
        v3_addon_result=v3_record,
    )

    candidate_base.validate_android_lint(root)
    if run_readbacks:
        run_addon_readback(root)
    if recorded_source != candidate_base.source_snapshot(root):
        raise CandidateError("source snapshot changed during complete readback")
    candidate_base.validate_file_records(
        row["artifacts"],
        expected_paths=EXPECTED_ARTIFACT_PATHS,
        label="artifacts final readback",
        root=root,
    )


def load_result(path: Path, *, root: Path = ROOT) -> Mapping[str, object]:
    return candidate_base.load_result(path, root=root)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--antecedents", action="store_true")
    parser.add_argument("result", nargs="?", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    if arguments.antecedents:
        if arguments.result is not None:
            print(
                "G7 V3 antecedent readback failed: result path is not valid with "
                "--antecedents",
                file=sys.stderr,
            )
            return 1
        try:
            current_antecedent_records(root=ROOT)
        except (CandidateError, OSError, ValueError) as error:
            print(f"G7 V3 antecedent readback failed: {error}", file=sys.stderr)
            return 1
        print(
            "G7 V3 antecedent readback passed: V2 command evidence 71, "
            "V3 Swift add-on 97/97."
        )
        return 0

    result_path = arguments.result or (ROOT / RESULT_RELATIVE_PATH)
    if not result_path.is_absolute():
        result_path = ROOT / result_path
    try:
        if result_path != ROOT / RESULT_RELATIVE_PATH:
            raise CandidateError(
                "candidate readback must use the exact canonical V3 result path"
            )
        document = load_result(result_path, root=ROOT)
        validate_document(document, root=ROOT, run_readbacks=True)
        if load_result(result_path, root=ROOT) != document:
            raise CandidateError("candidate result changed during complete readback")
    except (CandidateError, OSError, ValueError) as error:
        print(f"G7 non-security Merge-full V3 readback failed: {error}", file=sys.stderr)
        return 1
    print(
        "G7 non-security Merge-full V3 composed candidate readback passed; "
        "canonical Merge-full, G7 exit, and V1 remain unclaimed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
