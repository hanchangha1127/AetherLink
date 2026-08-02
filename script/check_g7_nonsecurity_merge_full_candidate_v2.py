#!/usr/bin/env python3
"""Independently verify the local G7 non-security Merge-full V2 candidate."""

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
    from script import check_g7_nonsecurity_merge_full_candidate as base
else:
    import check_g7_nonsecurity_merge_full_candidate as base


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

EXPECTED_IMPLEMENTATION_PATHS = tuple(
    sorted(
        set(base.EXPECTED_IMPLEMENTATION_PATHS)
        | {
            Path("script/check_g7_nonsecurity_merge_full_candidate_v2.py"),
            Path("script/check_g7_reviewed_nonsecurity_swift_addon.py"),
            Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v2.txt"),
            Path("script/run_g7_nonsecurity_merge_full_candidate_v2.py"),
            Path("script/test_check_g7_reviewed_nonsecurity_swift_addon.py"),
            Path("script/test_g7_nonsecurity_merge_full_candidate_v2.py"),
        },
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
EXPECTED_ARTIFACT_PATHS = tuple(
    sorted(
        set(base.EXPECTED_ARTIFACT_PATHS) | set(ADDON_ARTIFACT_PATHS),
        key=lambda path: path.as_posix().encode("ascii"),
    )
)

EXPECTED_COVERAGE = {
    **base.EXPECTED_COVERAGE,
    "swiftDiscoveredTests": 2_173,
    "swiftDistinctNonsecurityTests": 1_023,
    "swiftNotExecutedTests": 1_150,
    "swiftReviewedAddonTests": 626,
    "swiftReviewedMethodTests": 315,
    "swiftRunnerReviewedBeforeExclusion": 711,
}
EXPECTED_LIMITATIONS = {
    "canonicalG7ExitClaimed": False,
    "canonicalMergeFullClaimed": False,
    "completeSwiftSuiteClaimed": False,
    "deviceOrNetworkClaimed": False,
    "hostedCiClaimed": False,
    "securityAuthenticationCryptographyExecuted": False,
    "signedArtifactsClaimed": False,
    "v1Claimed": False,
}

ADDON_SCRIPT = "script/check_g7_reviewed_nonsecurity_swift_addon.py"
ADDITIONAL_COMMAND_SPECS = (
    (
        "g7-reviewed-nonsecurity-swift-addon-v2-prepare",
        ("python3", "-B", ADDON_SCRIPT, "--prepare"),
        600,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v2-run",
        ("python3", "-B", ADDON_SCRIPT, "--run"),
        1_500,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v2-write-binding",
        ("python3", "-B", ADDON_SCRIPT, "--write-binding"),
        600,
    ),
    (
        "g7-reviewed-nonsecurity-swift-addon-v2-results",
        ("python3", "-B", ADDON_SCRIPT, "--results"),
        600,
    ),
)
EXPECTED_COMMAND_IDS = base.EXPECTED_COMMAND_IDS + tuple(
    identifier for identifier, _argv, _timeout in ADDITIONAL_COMMAND_SPECS
)
V1_CANDIDATE_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/candidate.json"
)
EXPECTED_V1_CANDIDATE_RECORD = {
    "mode": 0o600,
    "path": V1_CANDIDATE_RELATIVE_PATH.as_posix(),
    "sha256": "d48ac61a355ecb381100941881a72945144acc16926c27671c3c7ebde4020301",
    "size": 41_459,
}
ADDON_READBACK_COMMAND = (
    "python3",
    "-B",
    ADDON_SCRIPT,
    "--results",
)


CandidateError = base.CandidateError


def ordered_identity_manifest(values: Sequence[str]) -> str:
    payload = json.dumps(
        list(values),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def validate_static_contract() -> None:
    if len(base.EXPECTED_COMMAND_IDS) != BASE_COMMAND_COUNT:
        raise CandidateError("V1 command count changed")
    if (
        ordered_identity_manifest(base.EXPECTED_COMMAND_IDS)
        != BASE_COMMAND_IDS_MANIFEST_SHA256
    ):
        raise CandidateError("V1 command identity manifest changed")
    if len(EXPECTED_COMMAND_IDS) != 71 or len(set(EXPECTED_COMMAND_IDS)) != 71:
        raise CandidateError("V2 command sequence must contain 71 unique commands")
    if EXPECTED_COMMAND_IDS[:BASE_COMMAND_COUNT] != base.EXPECTED_COMMAND_IDS:
        raise CandidateError("V2 does not preserve the exact V1 command prefix")
    if tuple(sorted(EXPECTED_ARTIFACT_PATHS, key=lambda path: path.as_posix())) != (
        EXPECTED_ARTIFACT_PATHS
    ):
        raise CandidateError("V2 artifact paths must be sorted")
    if len(EXPECTED_ARTIFACT_PATHS) != 32 or len(set(EXPECTED_ARTIFACT_PATHS)) != 32:
        raise CandidateError("V2 artifact paths must contain exactly 32 entries")
    if tuple(sorted(EXPECTED_IMPLEMENTATION_PATHS, key=lambda path: path.as_posix())) != (
        EXPECTED_IMPLEMENTATION_PATHS
    ):
        raise CandidateError("V2 implementation paths must be sorted")
    if (
        len(EXPECTED_IMPLEMENTATION_PATHS) != 11
        or len(set(EXPECTED_IMPLEMENTATION_PATHS)) != 11
    ):
        raise CandidateError("V2 implementation paths must contain exactly 11 entries")


def validate_additional_command(
    value: object,
    *,
    index: int,
    expected_id: str,
    expected_argv: tuple[str, ...],
    expected_timeout: int,
) -> None:
    row = base.exact_mapping(
        value,
        {
            "argv",
            "cwd",
            "elapsedMilliseconds",
            "exitCode",
            "id",
            "stderr",
            "stdout",
            "timeoutSeconds",
        },
        f"commands[{index}]",
    )
    if row["id"] != expected_id:
        raise CandidateError(f"command id differs at index {index}")
    argv = row["argv"]
    if type(argv) is not list or tuple(argv) != expected_argv:
        raise CandidateError(f"commands[{index}].argv differs for {expected_id}")
    if row["cwd"] != ".":
        raise CandidateError(f"commands[{index}].cwd must be repository root '.'")
    if base.require_exact_int(row["timeoutSeconds"], f"commands[{index}].timeoutSeconds") != (
        expected_timeout
    ):
        raise CandidateError(f"commands[{index}].timeout differs for {expected_id}")
    base.require_exact_int(
        row["elapsedMilliseconds"],
        f"commands[{index}].elapsedMilliseconds",
        minimum=1,
        maximum=expected_timeout * 1000 + 60_000,
    )
    if base.require_exact_int(row["exitCode"], f"commands[{index}].exitCode") != 0:
        raise CandidateError(f"commands[{index}] did not exit successfully")
    base.validate_stream_record(row["stdout"], f"commands[{index}].stdout")
    base.validate_stream_record(row["stderr"], f"commands[{index}].stderr")


def validate_commands(value: object) -> None:
    if type(value) is not list or len(value) != len(EXPECTED_COMMAND_IDS):
        raise CandidateError("commands record count differs")
    base.validate_commands(value[:BASE_COMMAND_COUNT])
    for offset, (expected_id, expected_argv, expected_timeout) in enumerate(
        ADDITIONAL_COMMAND_SPECS,
        start=BASE_COMMAND_COUNT,
    ):
        validate_additional_command(
            value[offset],
            index=offset,
            expected_id=expected_id,
            expected_argv=expected_argv,
            expected_timeout=expected_timeout,
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
        raise CandidateError(f"add-on readback could not run: {error}") from error
    _stdout, stderr = base.bounded_child_output(
        process,
        command=ADDON_READBACK_COMMAND,
        timeout_seconds=base.READBACK_TIMEOUT_SECONDS,
        maximum_bytes=base.READBACK_STREAM_MAX_BYTES,
    )
    if process.returncode != 0:
        detail = stderr[:4096].decode("utf-8", errors="replace")
        raise CandidateError(f"add-on readback failed: {detail}")


def validate_document(
    document: object,
    *,
    root: Path = ROOT,
    run_readbacks: bool = False,
) -> None:
    validate_static_contract()
    row = base.exact_mapping(
        document,
        {
            "artifacts",
            "commands",
            "contract",
            "coverage",
            "implementation",
            "limitations",
            "pidPreservation",
            "result",
            "schemaVersion",
            "source",
            "v1ArtifactPreservation",
        },
        "result",
    )
    if row["contract"] != CONTRACT:
        raise CandidateError("candidate contract differs")
    if base.require_exact_int(row["schemaVersion"], "schemaVersion", minimum=1) != (
        SCHEMA_VERSION
    ):
        raise CandidateError("candidate schema version differs")
    if row["result"] != "passed":
        raise CandidateError("candidate result must be passed")

    coverage = base.exact_mapping(row["coverage"], set(EXPECTED_COVERAGE), "coverage")
    for key, expected in EXPECTED_COVERAGE.items():
        if base.require_exact_int(coverage[key], f"coverage.{key}") != expected:
            raise CandidateError(f"coverage.{key} differs")
    limitations = base.exact_mapping(
        row["limitations"],
        set(EXPECTED_LIMITATIONS),
        "limitations",
    )
    for key, expected in EXPECTED_LIMITATIONS.items():
        base.require_bool(limitations[key], expected, f"limitations.{key}")

    recorded_source = base.exact_mapping(
        row["source"],
        {"algorithm", "fileCount", "sha256", "size"},
        "source",
    )
    if recorded_source["algorithm"] != base.SOURCE_ALGORITHM:
        raise CandidateError("source algorithm differs")
    base.require_exact_int(recorded_source["fileCount"], "source.fileCount", minimum=1)
    base.require_exact_int(
        recorded_source["size"],
        "source.size",
        maximum=base.SOURCE_TOTAL_MAX_BYTES,
    )
    base.require_sha256(recorded_source["sha256"], "source.sha256")
    if recorded_source != base.source_snapshot(root):
        raise CandidateError("source snapshot differs from current repository bytes")

    base.validate_file_records(
        row["artifacts"],
        expected_paths=EXPECTED_ARTIFACT_PATHS,
        label="artifacts",
        root=root,
    )
    base.validate_file_records(
        row["implementation"],
        expected_paths=EXPECTED_IMPLEMENTATION_PATHS,
        label="implementation",
        root=root,
    )
    validate_commands(row["commands"])
    base.validate_pid_preservation(row["pidPreservation"])
    v1_preservation = base.exact_mapping(
        row["v1ArtifactPreservation"],
        {"after", "before", "preservedDuringRun"},
        "v1ArtifactPreservation",
    )
    base.require_bool(
        v1_preservation["preservedDuringRun"],
        True,
        "v1ArtifactPreservation.preservedDuringRun",
    )
    if (
        v1_preservation["before"] != EXPECTED_V1_CANDIDATE_RECORD
        or v1_preservation["after"] != EXPECTED_V1_CANDIDATE_RECORD
    ):
        raise CandidateError("V1 antecedent candidate preservation record differs")
    if base.file_record(
        root,
        V1_CANDIDATE_RELATIVE_PATH,
        maximum_bytes=RESULT_MAX_BYTES,
    ) != EXPECTED_V1_CANDIDATE_RECORD:
        raise CandidateError("V1 antecedent candidate current bytes differ")
    base.validate_android_lint(root)
    if run_readbacks:
        base.run_child_readbacks(root)
        run_addon_readback(root)
    if recorded_source != base.source_snapshot(root):
        raise CandidateError("source snapshot changed during complete readback")
    base.validate_file_records(
        row["artifacts"],
        expected_paths=EXPECTED_ARTIFACT_PATHS,
        label="artifacts final readback",
        root=root,
    )


def load_result(path: Path, *, root: Path = ROOT) -> Mapping[str, object]:
    return base.load_result(path, root=root)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", nargs="?", type=Path, default=ROOT / RESULT_RELATIVE_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    result_path = arguments.result
    if not result_path.is_absolute():
        result_path = ROOT / result_path
    try:
        document = load_result(result_path, root=ROOT)
        validate_document(document, root=ROOT, run_readbacks=True)
        if load_result(result_path, root=ROOT) != document:
            raise CandidateError("candidate result changed during complete readback")
    except (CandidateError, OSError, ValueError) as error:
        print(f"G7 non-security Merge-full V2 readback failed: {error}", file=sys.stderr)
        return 1
    print(
        "G7 non-security Merge-full V2 local candidate readback passed; "
        "canonical Merge-full, G7 exit, and V1 remain unclaimed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
