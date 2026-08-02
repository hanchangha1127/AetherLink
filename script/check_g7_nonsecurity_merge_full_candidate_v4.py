#!/usr/bin/env python3
"""Independently verify the composed local G7 Merge-full V4 candidate."""

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
    from script import check_g7_nonsecurity_merge_full_candidate_v3 as base
    from script import check_g7_reviewed_nonsecurity_swift_addon_v4 as addon_v4
else:
    import check_g7_nonsecurity_merge_full_candidate_v3 as base
    import check_g7_reviewed_nonsecurity_swift_addon_v4 as addon_v4


ROOT = Path(__file__).resolve().parents[1]
candidate_base = base.candidate_base
CONTRACT = "aetherlink-g7-nonsecurity-merge-full-local-candidate-v4"
SCHEMA_VERSION = 1
RESULT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v4/candidate.json"
)
RESULT_MAX_BYTES = 1024 * 1024

ANTECEDENT_CANDIDATE_COMMAND_COUNT = 4
ANTECEDENT_COMMAND_COUNT = 75
ANTECEDENT_COMMAND_IDS_MANIFEST_SHA256 = (
    "629a2612d57d83565c01fa75fd10fabe3b851f7ad39695c8d9d0736f89c821d0"
)
COMPOSED_COMMAND_EVIDENCE_COUNT = 79
V3_SOURCE = {
    "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
    "fileCount": 1_008,
    "sha256": "7281eacaf6eec1876c81945f0e61302da243357663a75ce4bf6c1d36be1883e5",
    "size": 67_776_947,
}
V3_CANDIDATE_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v3/candidate.json"
)
EXPECTED_V3_CANDIDATE_RECORD = {
    "mode": 0o600,
    "path": V3_CANDIDATE_RELATIVE_PATH.as_posix(),
    "sha256": "b43b6ff584216466380a16a84dcf35cb9bc9129deda8d1d31c431610946f1575",
    "size": 14_457,
}

EXPECTED_COVERAGE = {
    **base.EXPECTED_COVERAGE,
    "swiftDistinctNonsecurityTests": 1_173,
    "swiftExcludedByScopeTests": 913,
    "swiftExternalOrSocketExcludedTests": 87,
    "swiftNotExecutedTests": 1_000,
    "swiftReviewedAddonTests": 776,
    "swiftReviewedMethodTests": 465,
    "swiftRunnerReviewedBeforeExclusion": 861,
    "swiftUnclassifiedTests": 0,
}
EXPECTED_LIMITATIONS = dict(base.EXPECTED_LIMITATIONS)

V4_IMPLEMENTATION_PATHS = (
    Path("script/check_g7_nonsecurity_merge_full_candidate_v4.py"),
    Path("script/check_g7_reviewed_nonsecurity_swift_addon_v4.py"),
    Path("script/g7_nonsecurity_swift_successor_engine.py"),
    Path("script/run_g7_nonsecurity_merge_full_candidate_v4.py"),
    Path("script/test_check_g7_reviewed_nonsecurity_swift_addon_v4.py"),
    Path("script/test_g7_nonsecurity_merge_full_candidate_v4.py"),
)
EXPECTED_IMPLEMENTATION_PATHS = tuple(
    sorted(
        set(base.EXPECTED_IMPLEMENTATION_PATHS) | set(V4_IMPLEMENTATION_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)
ADDON_OUTPUT_PARENT = Path(".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v4")
V4_ADDON_RESULT_RELATIVE_PATH = ADDON_OUTPUT_PARENT / "result.json"
EXPECTED_ADDON_ARTIFACT_RELATIVE_PATHS = (
    ADDON_OUTPUT_PARENT / "binding.json",
    ADDON_OUTPUT_PARENT / "console.log",
    ADDON_OUTPUT_PARENT / "execution-contract.json",
    V4_ADDON_RESULT_RELATIVE_PATH,
    ADDON_OUTPUT_PARENT / "run-marker.json",
    addon_v4.REVIEWED_IDENTITY_RELATIVE_PATH,
)
V4_ADDON_ARTIFACT_PATHS = (
    V3_CANDIDATE_RELATIVE_PATH,
    *EXPECTED_ADDON_ARTIFACT_RELATIVE_PATHS,
)
EXPECTED_ARTIFACT_PATHS = tuple(
    sorted(
        set(base.EXPECTED_ARTIFACT_PATHS) | set(V4_ADDON_ARTIFACT_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

ADDON_SCRIPT = "script/check_g7_reviewed_nonsecurity_swift_addon_v4.py"
ADDITIONAL_COMMAND_SPECS = (
    (
        "g7-reviewed-nonsecurity-swift-addon-v4-prepare",
        ("python3", "-B", ADDON_SCRIPT, "--prepare"),
        600,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v4-run",
        ("python3", "-B", ADDON_SCRIPT, "--run"),
        1_500,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v4-write-binding",
        ("python3", "-B", ADDON_SCRIPT, "--write-binding"),
        600,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v4-results",
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
    if base.CONTRACT != "aetherlink-g7-nonsecurity-merge-full-local-candidate-v3":
        raise CandidateError("V3 candidate contract identity changed")
    if base.RESULT_RELATIVE_PATH != V3_CANDIDATE_RELATIVE_PATH:
        raise CandidateError("V3 candidate result path changed")
    if len(base.EXPECTED_COMMAND_IDS) != ANTECEDENT_CANDIDATE_COMMAND_COUNT:
        raise CandidateError("V3 antecedent command count changed")
    if (
        ordered_identity_manifest(base.EXPECTED_COMMAND_IDS)
        != ANTECEDENT_COMMAND_IDS_MANIFEST_SHA256
    ):
        raise CandidateError("V3 antecedent command identity manifest changed")
    if len(EXPECTED_COMMAND_IDS) != 4 or len(set(EXPECTED_COMMAND_IDS)) != 4:
        raise CandidateError("V4 successor command sequence must contain four entries")
    if base.COMPOSED_COMMAND_EVIDENCE_COUNT != ANTECEDENT_COMMAND_COUNT:
        raise CandidateError("V3 antecedent composed command count changed")
    if COMPOSED_COMMAND_EVIDENCE_COUNT != ANTECEDENT_COMMAND_COUNT + len(
        EXPECTED_COMMAND_IDS
    ):
        raise CandidateError("composed command evidence arithmetic differs")
    if tuple(
        sorted(
            EXPECTED_ARTIFACT_PATHS,
            key=lambda path: path.as_posix().encode("ascii"),
        )
    ) != EXPECTED_ARTIFACT_PATHS:
        raise CandidateError("V4 artifact paths must be sorted")
    if len(EXPECTED_ARTIFACT_PATHS) != 46 or len(set(EXPECTED_ARTIFACT_PATHS)) != 46:
        raise CandidateError("V4 artifact paths must contain exactly 46 entries")
    if tuple(
        sorted(
            EXPECTED_IMPLEMENTATION_PATHS,
            key=lambda path: path.as_posix().encode("ascii"),
        )
    ) != EXPECTED_IMPLEMENTATION_PATHS:
        raise CandidateError("V4 implementation paths must be sorted")
    if (
        len(EXPECTED_IMPLEMENTATION_PATHS) != 23
        or len(set(EXPECTED_IMPLEMENTATION_PATHS)) != 23
    ):
        raise CandidateError("V4 implementation paths must contain exactly 23 entries")
    if tuple(addon_v4.ANTECEDENT_PROJECTION_RELATIVE_PATHS) != V4_IMPLEMENTATION_PATHS:
        raise CandidateError("V4 evidence-only source delta differs")
    observed_addon_artifacts = tuple(
        sorted(
            (
                addon_v4.BINDING_PATH.relative_to(ROOT),
                addon_v4.CONSOLE_PATH.relative_to(ROOT),
                addon_v4.EXECUTION_CONTRACT_PATH.relative_to(ROOT),
                addon_v4.RESULT_PATH.relative_to(ROOT),
                addon_v4.RUN_MARKER_PATH.relative_to(ROOT),
                addon_v4.REVIEWED_IDENTITY_RELATIVE_PATH,
            ),
            key=lambda path: path.as_posix().encode("ascii"),
        )
    )
    if observed_addon_artifacts != EXPECTED_ADDON_ARTIFACT_RELATIVE_PATHS:
        raise CandidateError("V4 add-on artifact path contract differs")
    if addon_v4.OUTPUT_ROOT != ROOT / ADDON_OUTPUT_PARENT:
        raise CandidateError("V4 add-on output root contract differs")


def _current_addon_artifact_record(
    relative: Path,
    *,
    maximum_bytes: int = RESULT_MAX_BYTES,
) -> dict[str, object]:
    data, mode = candidate_base.read_stable_regular_file(
        ROOT,
        relative,
        maximum_bytes=maximum_bytes,
    )
    return {
        "bytes": len(data),
        "mode": mode,
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _validate_addon_artifact_record(
    value: object,
    *,
    expected: Mapping[str, object],
    label: str,
) -> None:
    row = candidate_base.exact_mapping(
        value,
        {"bytes", "mode", "path", "sha256"},
        label,
    )
    candidate_base.require_exact_int(row["bytes"], f"{label}.bytes")
    candidate_base.require_exact_int(
        row["mode"],
        f"{label}.mode",
        maximum=0o7777,
    )
    candidate_base.validate_relative_path(row["path"], f"{label}.path")
    candidate_base.require_sha256(row["sha256"], f"{label}.sha256")
    if row != expected:
        raise CandidateError(f"{label} differs from current bytes")


def _validate_partition_record(
    value: object,
    *,
    expected_tests: int,
    expected_sha256: str,
    label: str,
) -> None:
    row = candidate_base.exact_mapping(
        value,
        {"manifestSha256", "tests"},
        label,
    )
    if candidate_base.require_exact_int(row["tests"], f"{label}.tests") != expected_tests:
        raise CandidateError(f"{label}.tests differs")
    candidate_base.require_sha256(
        row["manifestSha256"],
        f"{label}.manifestSha256",
    )
    if row["manifestSha256"] != expected_sha256:
        raise CandidateError(f"{label}.manifestSha256 differs")


def validate_v4_addon_result_document(document: object) -> None:
    row = candidate_base.exact_mapping(
        document,
        {
            "artifacts",
            "contract",
            "limitations",
            "partition",
            "result",
            "schemaVersion",
            "scope",
        },
        "V4 add-on result",
    )
    if row["contract"] != "aetherlink-g7-reviewed-nonsecurity-swift-addon-v4":
        raise CandidateError("V4 add-on result contract differs")
    if candidate_base.require_exact_int(
        row["schemaVersion"],
        "V4 add-on result.schemaVersion",
        minimum=1,
    ) != 1:
        raise CandidateError("V4 add-on result schema version differs")
    if row["result"] != "passed":
        raise CandidateError("V4 add-on result must remain passed")

    limitations = candidate_base.exact_mapping(
        row["limitations"],
        {
            "canonicalG7ExitClaimed",
            "canonicalMergeFullClaimed",
            "completeSwiftSuiteClaimed",
            "deviceOrNetworkClaimed",
            "hostedCiClaimed",
            "securityAuthenticationOrSecureChannelSuitesExecuted",
            "signedArtifactsClaimed",
            "v1Claimed",
        },
        "V4 add-on result.limitations",
    )
    for key, value in limitations.items():
        candidate_base.require_bool(
            value,
            False,
            f"V4 add-on result.limitations.{key}",
        )

    partition = candidate_base.exact_mapping(
        row["partition"],
        {
            "antecedentDistinct",
            "discovered",
            "distinctAfterAddon",
            "excludedByScope",
            "excludedExternal",
            "newExecuted",
            "remaining",
            "reviewedInput",
        },
        "V4 add-on result.partition",
    )
    partition_contract = {
        "antecedentDistinct": (
            1_120,
            "aaa5bfb601c28f89e52ab8d1d8da95c81b876eb4d5ea2cc0d1afb8f2ccd2bf18",
        ),
        "discovered": (
            2_173,
            "0a550e58480f4733abc264d0ec572e9511492a43dae6ea2dd5459c03548f4e65",
        ),
        "distinctAfterAddon": (
            1_173,
            "533de55b52fcda0f8af1871585e11fa846fdec6055c868791981ad5388711e67",
        ),
        "excludedByScope": (
            913,
            "c67806715d2ebbbc48395eaec9308d2c62946dd4c82ae1438aec157b05ebb488",
        ),
        "excludedExternal": (
            87,
            "0a641f6aa0d29985b3ac2f942cd8e78267c95d65c362cf0a03ee3ace1fb1585a",
        ),
        "newExecuted": (
            53,
            "0f625c53d1045b750b8a925c969df6d3a902b9d4bd5ed65c3fb283d518f1ca4e",
        ),
        "remaining": (
            1_000,
            "21353f330c03455a4cb66b55bc80846809c3505a1edfa77ea0695188fa908ee8",
        ),
        "reviewedInput": (
            1_053,
            "bc896a061126bb1958ac7c50ea6558ad174bb82418a7d2687cf99e2489d1e697",
        ),
    }
    for key, (tests, digest) in partition_contract.items():
        _validate_partition_record(
            partition[key],
            expected_tests=tests,
            expected_sha256=digest,
            label=f"V4 add-on result.partition.{key}",
        )

    scope = candidate_base.exact_mapping(
        row["scope"],
        {
            "classifiedReviewedInputTests",
            "selectedByClass",
            "selectedByModule",
            "securityAuthenticationOrSecureChannelSuitesExecuted",
            "unclassifiedTests",
        },
        "V4 add-on result.scope",
    )
    if candidate_base.require_exact_int(
        scope["classifiedReviewedInputTests"],
        "V4 add-on result.scope.classifiedReviewedInputTests",
    ) != 1_053:
        raise CandidateError("V4 add-on classified reviewed-input count differs")
    if candidate_base.require_exact_int(
        scope["unclassifiedTests"],
        "V4 add-on result.scope.unclassifiedTests",
    ) != 0:
        raise CandidateError("V4 add-on unclassified count differs")
    candidate_base.require_bool(
        scope["securityAuthenticationOrSecureChannelSuitesExecuted"],
        False,
        "V4 add-on result.scope.securityAuthenticationOrSecureChannelSuitesExecuted",
    )
    expected_modules = {"CompanionCoreTests.": 1, "LocalAgentBridgeTests.": 52}
    selected_modules = candidate_base.exact_mapping(
        scope["selectedByModule"],
        set(expected_modules),
        "V4 add-on result.scope.selectedByModule",
    )
    for key, expected in expected_modules.items():
        if candidate_base.require_exact_int(
            selected_modules[key],
            f"V4 add-on result.scope.selectedByModule.{key}",
        ) != expected:
            raise CandidateError(f"V4 add-on selected module count differs: {key}")
    expected_classes = {
        "AccessibilityAnnouncementTests": 1,
        "AetherLinkLocalizationTests": 39,
        "AetherLinkRenderSmokeTests": 11,
        "LocalRuntimeMessageRouterTests": 1,
        "PairingRouteNoticeTests": 1,
    }
    selected_classes = candidate_base.exact_mapping(
        scope["selectedByClass"],
        set(expected_classes),
        "V4 add-on result.scope.selectedByClass",
    )
    for key, expected in expected_classes.items():
        if candidate_base.require_exact_int(
            selected_classes[key],
            f"V4 add-on result.scope.selectedByClass.{key}",
        ) != expected:
            raise CandidateError(f"V4 add-on selected class count differs: {key}")

    artifact_paths = {
        "antecedentCandidate": V3_CANDIDATE_RELATIVE_PATH,
        "binding": ADDON_OUTPUT_PARENT / "binding.json",
        "console": ADDON_OUTPUT_PARENT / "console.log",
        "executionContract": ADDON_OUTPUT_PARENT / "execution-contract.json",
        "reviewedIdentityManifest": addon_v4.REVIEWED_IDENTITY_RELATIVE_PATH,
        "runMarker": ADDON_OUTPUT_PARENT / "run-marker.json",
        "testList": addon_v4.TEST_LIST_PATH.relative_to(ROOT),
    }
    artifacts = candidate_base.exact_mapping(
        row["artifacts"],
        set(artifact_paths),
        "V4 add-on result.artifacts",
    )
    for key, relative in artifact_paths.items():
        maximum = (
            addon_v4.product_ci.SWIFT_FOCUSED_TEST_MAX_LOG_BYTES
            if key == "console"
            else RESULT_MAX_BYTES
        )
        expected = _current_addon_artifact_record(
            relative,
            maximum_bytes=maximum,
        )
        _validate_addon_artifact_record(
            artifacts[key],
            expected=expected,
            label=f"V4 add-on result.artifacts.{key}",
        )


def load_and_validate_v4_addon_result() -> dict[str, object]:
    data, mode = candidate_base.read_stable_regular_file(
        ROOT,
        V4_ADDON_RESULT_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if mode != 0o600:
        raise CandidateError("V4 add-on result mode must be 0600")
    try:
        document = json.loads(
            data,
            object_pairs_hook=candidate_base.reject_duplicate_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        candidate_base.DuplicateKeyError,
    ) as error:
        raise CandidateError(f"V4 add-on result JSON cannot be decoded: {error}") from error
    if type(document) is not dict or candidate_base.canonical_json_bytes(document) != data:
        raise CandidateError("V4 add-on result must be canonical JSON")
    validate_v4_addon_result_document(document)
    return document


def current_v3_antecedent_record(
    *,
    root: Path = ROOT,
) -> dict[str, object]:
    validate_static_contract()
    if root != ROOT:
        raise CandidateError("antecedent readback must use the canonical repository root")
    failures = addon_v4.candidate_antecedent_failures()
    if failures:
        raise CandidateError("V3 antecedent evidence differs: " + "; ".join(failures))
    partition, selector_failures = addon_v4.contract_inputs()
    if partition is None or selector_failures:
        raise CandidateError(
            "V4 selector contract differs: "
            + "; ".join(selector_failures or ["partition unavailable"])
        )
    if len(partition.selected) != 53:
        raise CandidateError("V4 selector must contain exactly 53 identities")
    v3_record = candidate_base.file_record(
        root,
        V3_CANDIDATE_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    if v3_record != EXPECTED_V3_CANDIDATE_RECORD:
        raise CandidateError("V3 antecedent candidate current bytes differ")
    return v3_record


def current_antecedent_records(
    *,
    root: Path = ROOT,
) -> tuple[dict[str, object], dict[str, object]]:
    v3_record = current_v3_antecedent_record(root=root)
    partition, failures = addon_v4.contract_inputs()
    if partition is None:
        raise CandidateError("V4 add-on contract inputs differ: " + "; ".join(failures))
    failures.extend(addon_v4.result_failures(partition))
    if failures:
        raise CandidateError("V4 add-on result differs: " + "; ".join(failures))
    load_and_validate_v4_addon_result()
    v4_record = candidate_base.file_record(
        root,
        V4_ADDON_RESULT_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    )
    return v3_record, v4_record


def expected_composition(
    *,
    v3_candidate: dict[str, object],
    v4_addon_result: dict[str, object],
) -> dict[str, object]:
    return {
        "antecedent": {
            "candidate": dict(v3_candidate),
            "commands": ANTECEDENT_COMMAND_COUNT,
            "swiftDistinctNonsecurityTests": 1_120,
        },
        "composedCommandEvidence": COMPOSED_COMMAND_EVIDENCE_COUNT,
        "evidenceOnlySourceDelta": [
            path.as_posix()
            for path in addon_v4.ANTECEDENT_PROJECTION_RELATIVE_PATHS
        ],
        "executionModel": "immutable-v3-antecedent-plus-v4-addon-v1",
        "projectedV3Source": dict(V3_SOURCE),
        "runtimeProductSourceChanged": False,
        "successor": {
            "commands": len(EXPECTED_COMMAND_IDS),
            "result": dict(v4_addon_result),
            "swiftNewTests": addon_v4.NEW_TEST_COUNT,
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
    v3_candidate: Mapping[str, object],
    v4_addon_result: Mapping[str, object],
) -> None:
    row = candidate_base.exact_mapping(
        value,
        {
            "antecedent",
            "composedCommandEvidence",
            "evidenceOnlySourceDelta",
            "executionModel",
            "projectedV3Source",
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
        expected=v3_candidate,
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
    ) != 1_120:
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
        for path in addon_v4.ANTECEDENT_PROJECTION_RELATIVE_PATHS
    ]
    if type(row["evidenceOnlySourceDelta"]) is not list or row[
        "evidenceOnlySourceDelta"
    ] != expected_delta:
        raise CandidateError("evidenceComposition.evidenceOnlySourceDelta differs")
    if row["executionModel"] != "immutable-v3-antecedent-plus-v4-addon-v1":
        raise CandidateError("evidenceComposition.executionModel differs")
    projected_source = candidate_base.exact_mapping(
        row["projectedV3Source"],
        {"algorithm", "fileCount", "sha256", "size"},
        "evidenceComposition.projectedV3Source",
    )
    if projected_source["algorithm"] != V3_SOURCE["algorithm"]:
        raise CandidateError("evidenceComposition.projectedV3Source.algorithm differs")
    candidate_base.require_exact_int(
        projected_source["fileCount"],
        "evidenceComposition.projectedV3Source.fileCount",
        minimum=1,
    )
    candidate_base.require_sha256(
        projected_source["sha256"],
        "evidenceComposition.projectedV3Source.sha256",
    )
    candidate_base.require_exact_int(
        projected_source["size"],
        "evidenceComposition.projectedV3Source.size",
        maximum=candidate_base.SOURCE_TOTAL_MAX_BYTES,
    )
    if projected_source != V3_SOURCE:
        raise CandidateError("evidenceComposition.projectedV3Source differs")
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
        expected=v4_addon_result,
        label="evidenceComposition.successor.result",
    )
    if candidate_base.require_exact_int(
        successor["swiftNewTests"],
        "evidenceComposition.successor.swiftNewTests",
    ) != addon_v4.NEW_TEST_COUNT:
        raise CandidateError("evidenceComposition.successor.swiftNewTests differs")

    expected = expected_composition(
        v3_candidate=dict(v3_candidate),
        v4_addon_result=dict(v4_addon_result),
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
        base.base.validate_additional_command(
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
        raise CandidateError(f"V4 add-on readback could not run: {error}") from error
    _stdout, stderr = candidate_base.bounded_child_output(
        process,
        command=ADDON_READBACK_COMMAND,
        timeout_seconds=candidate_base.READBACK_TIMEOUT_SECONDS,
        maximum_bytes=candidate_base.READBACK_STREAM_MAX_BYTES,
    )
    if process.returncode != 0:
        detail = stderr[:4096].decode("utf-8", errors="replace")
        raise CandidateError(f"V4 add-on readback failed: {detail}")


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
            "v3ArtifactPreservation",
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
    if recorded_source["fileCount"] != 1_014:
        raise CandidateError("V4 source file count must be exactly 1014")
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

    v3_record, v4_record = current_antecedent_records(root=root)
    preservation = candidate_base.exact_mapping(
        row["v3ArtifactPreservation"],
        {"after", "before", "preservedDuringRun"},
        "v3ArtifactPreservation",
    )
    candidate_base.require_bool(
        preservation["preservedDuringRun"],
        True,
        "v3ArtifactPreservation.preservedDuringRun",
    )
    validate_embedded_file_record(
        preservation["before"],
        expected=v3_record,
        label="v3ArtifactPreservation.before",
    )
    validate_embedded_file_record(
        preservation["after"],
        expected=v3_record,
        label="v3ArtifactPreservation.after",
    )
    if preservation["before"] != v3_record or preservation["after"] != v3_record:
        raise CandidateError("V3 antecedent candidate preservation record differs")
    validate_evidence_composition(
        row["evidenceComposition"],
        v3_candidate=v3_record,
        v4_addon_result=v4_record,
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
    candidate_base.validate_file_records(
        row["implementation"],
        expected_paths=EXPECTED_IMPLEMENTATION_PATHS,
        label="implementation final readback",
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
                "G7 V4 antecedent readback failed: result path is not valid with "
                "--antecedents",
                file=sys.stderr,
            )
            return 1
        try:
            current_v3_antecedent_record(root=ROOT)
        except (CandidateError, OSError, ValueError) as error:
            print(f"G7 V4 antecedent readback failed: {error}", file=sys.stderr)
            return 1
        print(
            "G7 V4 antecedent readback passed: V3 composed command evidence 75, "
            "V4 exact selector ready for 53 tests (not yet executed by this mode)."
        )
        return 0

    result_path = arguments.result or (ROOT / RESULT_RELATIVE_PATH)
    if not result_path.is_absolute():
        result_path = ROOT / result_path
    try:
        if result_path != ROOT / RESULT_RELATIVE_PATH:
            raise CandidateError(
                "candidate readback must use the exact canonical V4 result path"
            )
        document = load_result(result_path, root=ROOT)
        validate_document(document, root=ROOT, run_readbacks=True)
        if load_result(result_path, root=ROOT) != document:
            raise CandidateError("candidate result changed during complete readback")
    except (CandidateError, OSError, ValueError) as error:
        print(f"G7 non-security Merge-full V4 readback failed: {error}", file=sys.stderr)
        return 1
    print(
        "G7 non-security Merge-full V4 composed candidate readback passed; "
        "canonical Merge-full, G7 exit, and V1 remain unclaimed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
