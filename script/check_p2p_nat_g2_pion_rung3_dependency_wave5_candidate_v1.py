#!/usr/bin/env python3
"""Project the exact externally pinned Wave3 graph frontier into Wave5.

Run only with ``python3 -I -B -S``.  The checker holds the final v3 graph
checker and its tests by descriptor, invokes the exact v3 checker in-process,
validates its exact content/input/graph/frontier bindings, and writes one
canonical Wave5 identity candidate to stdout.  It grants no authority and
performs no network, subprocess, authentication, dependency-source execution,
extraction, or file-write operation.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "Wave5 candidate checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
V3_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v3.py"
V3_CHECKER_RAW_SHA256 = (
    "94835190c28e2bb815ed033ee9b3732630ab5ce1782dd94382ead208e97f10ac"
)
V3_CHECKER_NORMALIZED_SHA256 = (
    "bd7daf846643dd0c2600ac77105224c47e9fbe5c3f76aaffc3a4b13e96c05a3e"
)
V3_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v3.py"
V3_TESTS_RAW_SHA256 = (
    "497795c9b9ae1134b12c750a1aacb56391299ef882c1372dca876e448bf912de"
)
V3_CANDIDATE_CONTENT_SHA256 = (
    "a752f444042290e51ee794db76b2ab18c9d3269bb2fb0d5c1abae11ee80b10ce"
)
V3_INPUT_SET_SHA256 = (
    "b2d981dae1576f27ae5cd292e218b0a0eb35f5bdc0d98734fb1b350408ce4eca"
)
V3_SOURCE_BINDINGS_SHA256 = (
    "025e9a401eda9fac4687ed4c2cdbefd07a0b0489d31c1b43fe9744350579ff78"
)
V3_NODE_SET_SHA256 = (
    "970144c5bd6c1a7d8a13a8bdd5c9efc63fc81afab5860ca8fa77fce49871601a"
)
V3_EDGE_SET_SHA256 = (
    "25cb01585c5d7fc4ec8840d038a195c513e0383e2a4931947312ea9e47e3db47"
)
V3_MODULE_NODE_SET_SHA256 = (
    "68b7e270a6dfea5cff0adf4f61d3e3134db9067a6df28f9662bcc9fc9e6c7876"
)
V3_MODULE_EDGE_SET_SHA256 = (
    "4a42809c785da20af511b2dd47def9119cc460d69efa6917426036ad903913d5"
)
V3_MODULE_GRAPH_AND_FRONTIER_SHA256 = (
    "e3624a30e16f95f9c106641e3d927654f72e6c6b9f8a1f9fbc578f994546a126"
)
V3_RECONSTRUCTION_PROJECTION_SHA256 = (
    "ee330142d77874457cccf78d5a9fe51652c81916f1d7aabb390f321dff51e03a"
)
V3_GRAPH_SHA256 = V3_RECONSTRUCTION_PROJECTION_SHA256
V3_FRONTIER_SHA256 = (
    "026810f158d7a8cfcef61f7a09d9a9bc964bd41e4b2f529994fce6d70cbce960"
)
CHECKER_ID = "g2-pion-ice-v4.3.0-wave5-frontier-candidate-check-v1"
CODE_MAXIMUM_BYTES = 4 * 1024 * 1024
V3_PREDECESSOR_RECONSTRUCTION_COUNT = 2
V3_DIRECT_RECONSTRUCTION_COUNT = 2
V3_TOTAL_RECONSTRUCTION_COUNT = 4
V3_PREDECESSOR_ARCHIVE_OPEN_COUNT = 102
V3_DIRECT_ARCHIVE_OPEN_COUNT = 134
V3_TOTAL_ARCHIVE_OPEN_COUNT = 236

EXPECTED_FRONTIER = [
    ("github.com/stretchr/testify", "v1.8.0", False),
    ("golang.org/x/crypto", "v0.19.0", False),
    ("golang.org/x/mod", "v0.30.0", False),
    ("golang.org/x/net", "v0.25.0", False),
    ("golang.org/x/net", "v0.47.0", False),
    ("golang.org/x/sync", "v0.18.0", False),
    ("golang.org/x/sync", "v0.7.0", False),
    ("golang.org/x/sys", "v0.17.0", False),
    ("golang.org/x/sys", "v0.20.0", False),
    ("golang.org/x/sys", "v0.38.0", False),
    (
        "golang.org/x/telemetry",
        "v0.0.0-20240228155512-f48c80bd79b2",
        False,
    ),
    (
        "golang.org/x/telemetry",
        "v0.0.0-20251111182119-bc8e575c7b54",
        False,
    ),
    ("golang.org/x/term", "v0.17.0", False),
    ("golang.org/x/text", "v0.14.0", False),
    ("golang.org/x/tools", "v0.13.0", False),
]


class Wave5CandidateFailure(RuntimeError):
    """A content-free, fail-closed checker error."""


class CliUsageFailure(RuntimeError):
    """An intentionally content-free command-line usage error."""


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise CliUsageFailure("E_CLI_USAGE")


def check(condition: bool, code: str) -> None:
    if not condition:
        raise Wave5CandidateFailure(code)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def compact_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def content_bound(
    body: Mapping[str, Any],
    scope: str,
) -> dict[str, Any]:
    result = dict(body)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": scope,
        "sha256": sha256_bytes(canonical_json_bytes(body)),
    }
    return result


def file_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def directory_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
    )


class BootstrapPinnedCodeFile:
    """Hold the exact v3 checker before any of its code is executed."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        expected_sha256: str,
    ) -> None:
        self.root_path = root
        self.root_fd = -1
        self.parent_fd = -1
        self.fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        self.raw = b""
        try:
            parts = relative_path.split("/")
            check(
                parts
                and all(part not in {"", ".", ".."} for part in parts),
                "E_V3_CHECKER_IDENTITY",
            )
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self.root_initial = os.fstat(self.root_fd)
            self._validate_directory(self.root_initial)
            current = os.dup(self.root_fd)
            for component in parts[:-1]:
                child = os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                    dir_fd=current,
                )
                info = os.fstat(child)
                self._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.parent_fd = current
            self.name = parts[-1]
            self.fd = os.open(
                self.name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=self.parent_fd,
            )
            self.initial = os.fstat(self.fd)
            self._validate_file(self.initial)
            first = self._read_pass()
            second = self._read_pass()
            check(
                first == second
                and sha256_bytes(first) == expected_sha256,
                "E_V3_CHECKER_IDENTITY",
            )
            self.raw = first
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        check(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_V3_CHECKER_IDENTITY",
        )

    @staticmethod
    def _validate_file(info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= CODE_MAXIMUM_BYTES,
            "E_V3_CHECKER_IDENTITY",
        )

    def _read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_V3_CHECKER_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_V3_CHECKER_IDENTITY")
        after = os.fstat(self.fd)
        check(
            file_identity(before) == file_identity(after),
            "E_V3_CHECKER_IDENTITY",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        try:
            held_root = os.fstat(self.root_fd)
            named_root = os.stat(
                self.root_path,
                follow_symlinks=False,
            )
        except OSError as error:
            raise Wave5CandidateFailure("E_ROOT_IDENTITY") from error
        check(
            directory_identity(held_root)
            == directory_identity(self.root_initial)
            and directory_identity(named_root)
            == directory_identity(self.root_initial),
            "E_ROOT_IDENTITY",
        )
        check(
            file_identity(os.fstat(self.fd)) == file_identity(self.initial)
            and file_identity(
                os.stat(
                    self.name,
                    dir_fd=self.parent_fd,
                    follow_symlinks=False,
                )
            )
            == file_identity(self.initial),
            "E_V3_CHECKER_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            check(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                and directory_identity(
                    os.stat(
                        component,
                        dir_fd=parent,
                        follow_symlinks=False,
                    )
                )
                == directory_identity(initial),
                "E_V3_CHECKER_IDENTITY",
            )

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        seen: set[int] = set()
        for child, _, parent, _ in reversed(self.directories):
            if child not in seen:
                os.close(child)
                seen.add(child)
            if parent not in seen:
                os.close(parent)
                seen.add(parent)
        self.directories.clear()
        if self.parent_fd >= 0 and self.parent_fd not in seen:
            os.close(self.parent_fd)
        self.parent_fd = -1
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1

    def __enter__(self) -> "BootstrapPinnedCodeFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def load_v3_checker(held: BootstrapPinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_checker_v3_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V3_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_checker_v3_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V3_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise Wave5CandidateFailure("E_V3_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "combined_identity_barrier",
        "generate_candidate",
        "sha256_bytes",
    ):
        check(callable(getattr(module, name, None)), "E_V3_CHECKER_API")
    check(
        module.CHECKER_ID
        == (
            "g2-pion-ice-v4.3.0-combined-wave1-wave2-"
            "wave3-wave4-check-v3"
        )
        and module.SELF_NORMALIZED_SHA256
        == V3_CHECKER_NORMALIZED_SHA256
        and module.V1_CHECKER_RAW_SHA256
        == "b11047fd74e8ba4b41d66590975270921a5835bf444ad2e942af357d56764f15"
        and module.V1_PROVIDER_RAW_SHA256
        == "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3",
        "E_V3_CHECKER_API",
    )
    return module


def expected_frontier_rows() -> list[dict[str, Any]]:
    return [
        {
            "acquisitionAuthorized": False,
            "module": module,
            "requiresSeparateWaveDecision": True,
            "selectedByGraphAlgorithm": selected,
            "version": version,
        }
        for module, version, selected in EXPECTED_FRONTIER
    ]


def verify_v3_content_binding(candidate: Mapping[str, Any]) -> None:
    binding = candidate.get("contentBinding")
    check(
        type(binding) is dict
        and binding.get("algorithm") == "sha256"
        and binding.get("canonicalization")
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and binding.get("scope") == "candidate_without_contentBinding"
        and binding.get("sha256") == V3_CANDIDATE_CONTENT_SHA256,
        "E_V3_CONTENT",
    )
    without = dict(candidate)
    without.pop("contentBinding", None)
    check(
        sha256_bytes(canonical_json_bytes(without))
        == V3_CANDIDATE_CONTENT_SHA256,
        "E_V3_CONTENT",
    )


def validate_v3_candidate(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    check(type(candidate) is dict, "E_V3_CANDIDATE")
    verify_v3_content_binding(candidate)
    input_set = candidate.get("inputSet")
    graph = candidate.get("graphDiscovery")
    coverage = candidate.get("coverage")
    checker_verification = candidate.get("checkerVerification")
    operation_counters = candidate.get("operationCounters")
    authority = candidate.get("authority")
    check(
        candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-"
            "wave3-wave4-fixed-point-candidate"
        )
        and candidate.get("schemaVersion") == "3.0"
        and candidate.get("status")
        == "combined_graph_discovery_complete_next_wave_required"
        and candidate.get("route") == "next_wave_required"
        and candidate.get("verificationOnly") is True
        and candidate.get("recordModeExposed") is False,
        "E_V3_CANDIDATE",
    )
    check(
        type(input_set) is dict
        and input_set.get("heldSourceInputCount") == 133
        and input_set.get("resourceCount") == 132
        and input_set.get("modCount") == 66
        and input_set.get("zipCount") == 66
        and input_set.get("uniqueModuleVersionTupleCount") == 66
        and input_set.get("aggregateRawByteSize") == 97_140_866
        and input_set.get("combinedInputSetSha256") == V3_INPUT_SET_SHA256
        and sha256_bytes(compact_json_bytes(input_set.get("sourceBindings")))
        == V3_SOURCE_BINDINGS_SHA256,
        "E_V3_INPUT",
    )
    expected_hashes = {
        "nodeSetSha256": V3_NODE_SET_SHA256,
        "edgeSetSha256": V3_EDGE_SET_SHA256,
        "moduleNodeSetSha256": V3_MODULE_NODE_SET_SHA256,
        "moduleEdgeSetSha256": V3_MODULE_EDGE_SET_SHA256,
        "moduleGraphAndFrontierSha256":
            V3_MODULE_GRAPH_AND_FRONTIER_SHA256,
        "reconstructionProjectionSha256":
            V3_RECONSTRUCTION_PROJECTION_SHA256,
        "graphSha256": V3_GRAPH_SHA256,
    }
    check(
        type(graph) is dict
        and graph.get("newTupleCount") == 15
        and graph.get("fixedPointReached") is False
        and graph.get("graphNodeCount") == 132
        and graph.get("graphEdgeCount") == 1_047
        and graph.get("moduleNodeCount") == 82
        and graph.get("moduleEdgeCount") == 215
        and all(graph.get(key) == value for key, value in expected_hashes.items()),
        "E_V3_GRAPH",
    )
    frontier = graph.get("exactFrontier")
    check(
        frontier == expected_frontier_rows()
        and sha256_bytes(canonical_json_bytes(frontier))
        == V3_FRONTIER_SHA256,
        "E_V3_FRONTIER",
    )
    check(
        type(coverage) is dict
        and coverage.get("archiveCount") == 67
        and coverage.get("aggregateEntryCount") == 20_772
        and coverage.get("aggregateUncompressedByteCount") == 356_904_520
        and coverage.get("goSourceFileCount") == 16_479
        and coverage.get("semanticParsedGoSourceCount") == 14_850
        and coverage.get("testdataSemanticExclusionCount") == 1_629
        and coverage.get("semanticParsedGoSourceCount")
        + coverage.get("testdataSemanticExclusionCount")
        == coverage.get("goSourceFileCount"),
        "E_V3_COVERAGE",
    )
    check(
        type(checker_verification) is dict
        and checker_verification.get("fullInputReconstructionCount")
        == V3_DIRECT_RECONSTRUCTION_COUNT
        and checker_verification.get(
            "predecessorFullInputReconstructionCount"
        ) == V3_PREDECESSOR_RECONSTRUCTION_COUNT
        and checker_verification.get("totalFullInputReconstructionCount")
        == V3_TOTAL_RECONSTRUCTION_COUNT
        and checker_verification.get(
            "underlyingIndependentGraphAlgorithmCount"
        ) == 8
        and checker_verification.get("pinnedV2PredecessorExecuted") is True
        and checker_verification.get(
            "canonicalGraphEqualityVerified"
        ) is True
        and checker_verification.get(
            "calculatedFixedPointCandidate"
        ) is False,
        "E_V3_RECONSTRUCTION_LINEAGE",
    )
    check(
        type(operation_counters) is dict
        and operation_counters.get("heldSourceInputCount") == 133
        and operation_counters.get("heldTerminalEvidenceCount") == 24
        and operation_counters.get("heldToolInputCount") == 4
        and operation_counters.get("stableReadPassesPerHeldInput") == 2
        and operation_counters.get("fullSourceReconstructionCount")
        == V3_TOTAL_RECONSTRUCTION_COUNT
        and operation_counters.get("archiveOpenCount")
        == V3_TOTAL_ARCHIVE_OPEN_COUNT
        and V3_DIRECT_RECONSTRUCTION_COUNT * coverage["archiveCount"]
        == V3_DIRECT_ARCHIVE_OPEN_COUNT
        and operation_counters["archiveOpenCount"]
        - V3_DIRECT_ARCHIVE_OPEN_COUNT
        == V3_PREDECESSOR_ARCHIVE_OPEN_COUNT
        and operation_counters.get("archiveExtractionCount") == 0
        and operation_counters.get("sourceExecutionCount") == 0
        and operation_counters.get("subprocessCount") == 0
        and operation_counters.get("networkOperationCount") == 0
        and operation_counters.get("fileWriteCount") == 0,
        "E_V3_OPERATION_LINEAGE",
    )
    check(
        type(authority) is dict
        and bool(authority)
        and all(value is False for value in authority.values()),
        "E_V3_AUTHORITY",
    )
    return frontier


def wave5_rows(frontier: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    check(
        list(frontier) == expected_frontier_rows(),
        "E_V3_FRONTIER",
    )
    result: list[dict[str, Any]] = []
    for order, row in enumerate(frontier, 1):
        digest = sha256_bytes(
            f"{row['module']}\n{row['version']}\n".encode("utf-8")
        )
        result.append(
            {
                "tupleOrder": order,
                "tupleId": f"wave5-{order:03d}-{digest[:12]}",
                "tupleDigestAlgorithm": "sha256(module_lf_version_lf)",
                "tupleDigestSha256": digest,
                "module": row["module"],
                "version": row["version"],
                "selectedByGraphAlgorithm":
                    row["selectedByGraphAlgorithm"],
                "versionSpecificVertexRetained": True,
                "candidateForIdentityResolution": True,
                "acquisitionAuthorized": False,
                "identityResolutionAuthorized": False,
                "requiresSeparateIdentityDecision": True,
            }
        )
    check(
        len(result) == 15
        and [row["tupleOrder"] for row in result] == list(range(1, 16))
        and len({row["tupleId"] for row in result}) == 15
        and sum(row["selectedByGraphAlgorithm"] for row in result) == 0,
        "E_WAVE5_PROJECTION",
    )
    return result


def generate_wave5_candidate(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    with BootstrapPinnedCodeFile(
        root,
        V3_CHECKER_PATH,
        V3_CHECKER_RAW_SHA256,
    ) as checker_held:
        v3 = load_v3_checker(checker_held)
        with v3.PinnedCodeFile(
            root,
            V3_TESTS_PATH,
            V3_TESTS_RAW_SHA256,
        ) as tests_held:
            held = (checker_held, tests_held)
            v3.combined_identity_barrier(root, held)
            candidate = v3.generate_candidate(root)
            v3.combined_identity_barrier(root, held)
            frontier = validate_v3_candidate(candidate)
            rows = wave5_rows(frontier)
            v3.combined_identity_barrier(root, held)
            body = {
                "documentType": (
                    "aetherlink.g2-pion-rung3-wave5-frontier-"
                    "identity-candidate"
                ),
                "schemaVersion": "1.0",
                "checkerId": CHECKER_ID,
                "status": (
                    "exact_15_wave5_frontier_identity_candidates_"
                    "prepared_without_authority"
                ),
                "result": (
                    "externally_pinned_v3_frontier_projected_"
                    "to_wave5_identity_candidates"
                ),
                "verificationOnly": True,
                "recordModeExposed": False,
                "producerPackageBindings": [
                    {
                        "role": "combined_fixed_point_v3_checker",
                        "path": V3_CHECKER_PATH,
                        "rawSha256": V3_CHECKER_RAW_SHA256,
                        "normalizedSha256":
                            V3_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "combined_fixed_point_v3_tests",
                        "path": V3_TESTS_PATH,
                        "rawSha256": V3_TESTS_RAW_SHA256,
                    },
                ],
                "sourceCandidateBinding": {
                    "contentSha256": V3_CANDIDATE_CONTENT_SHA256,
                    "combinedInputSetSha256": V3_INPUT_SET_SHA256,
                    "sourceBindingsSha256":
                        V3_SOURCE_BINDINGS_SHA256,
                    "graphSha256": V3_GRAPH_SHA256,
                    "moduleGraphAndFrontierSha256":
                        V3_MODULE_GRAPH_AND_FRONTIER_SHA256,
                    "exactFrontierCanonicalSha256": V3_FRONTIER_SHA256,
                    "route": "next_wave_required",
                    "newTupleCount": 15,
                    "fixedPointReached": False,
                },
                "wave": {
                    "waveId": (
                        "g2-pion-ice-v4.3.0-dependency-source-wave5-"
                        "candidate-v1"
                    ),
                    "tupleCount": 15,
                    "graphSelectedTupleCount": 0,
                    "versionSpecificNonSelectedTupleCount": 15,
                    "identityResolvedTupleCount": 0,
                    "acquisitionReadyTupleCount": 0,
                    "tuples": rows,
                },
                "nextAction": (
                    "prepare_separate_wave5_identity_and_acquisition_"
                    "decision"
                ),
                "operationCounters": {
                    "v3CandidateInvocationCount": 1,
                    "predecessorFullSourceReconstructionCount":
                        V3_PREDECESSOR_RECONSTRUCTION_COUNT,
                    "directV3FullSourceReconstructionCount":
                        V3_DIRECT_RECONSTRUCTION_COUNT,
                    "totalFullSourceReconstructionCount":
                        V3_TOTAL_RECONSTRUCTION_COUNT,
                    "predecessorArchiveOpenCount":
                        V3_PREDECESSOR_ARCHIVE_OPEN_COUNT,
                    "directV3ArchiveOpenCount":
                        V3_DIRECT_ARCHIVE_OPEN_COUNT,
                    "totalArchiveOpenCount":
                        V3_TOTAL_ARCHIVE_OPEN_COUNT,
                    "inheritedFullSourceReconstructionCount":
                        V3_TOTAL_RECONSTRUCTION_COUNT,
                    "inheritedArchiveOpenCount":
                        V3_TOTAL_ARCHIVE_OPEN_COUNT,
                    "networkOperationCount": 0,
                    "subprocessCount": 0,
                    "dependencySourceExecutionCount": 0,
                    "archiveExtractionCount": 0,
                    "fileWriteCount": 0,
                },
                "closure": {
                    "dependencyFixedPointReached": False,
                    "dependencyClosureComplete": False,
                    "wave5IdentityResolved": False,
                    "wave5AcquisitionReady": False,
                    "semanticClosureComplete": False,
                    "candidateSelected": False,
                    "librarySelected": False,
                    "rungThreeComplete": False,
                    "releaseReady": False,
                },
                "authority": {
                    "decisionAuthorityGranted": False,
                    "executionAuthorityGranted": False,
                    "identityResolutionAuthorityGranted": False,
                    "acquisitionAuthorityGranted": False,
                    "publicationAuthorityGranted": False,
                    "networkAuthorized": False,
                    "dependencySourceExecutionAuthorized": False,
                    "filesystemExtractionAuthorized": False,
                    "subprocessAuthorized": False,
                    "fileWriteAuthorized": False,
                    "gitWriteAuthorized": False,
                    "repositoryOwnerIdentityProofRequired": False,
                    "externalAuthenticationRequired": False,
                    "passwordRequired": False,
                    "privateKeyRequired": False,
                    "signatureRequired": False,
                    "tokenRequired": False,
                    "userActionRequired": False,
                },
                "nonClaims": {
                    "frontierIdentityResolved": False,
                    "sourceAcquisitionAuthorized": False,
                    "dependencyClosureComplete": False,
                    "fixedPointReached": False,
                    "candidateOrLibrarySelected": False,
                    "releaseReady": False,
                },
            }
            result = content_bound(
                body,
                "wave5_candidate_without_contentBinding",
            )
            v3.combined_identity_barrier(root, held)
            return result


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def error_document_bytes() -> bytes:
    return canonical_json_bytes(
        {
            "documentType": (
                "aetherlink.g2-pion-rung3-wave5-frontier-"
                "candidate-check-error"
            ),
            "schemaVersion": "1.0",
            "status": "failed_closed_without_publication",
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "networkOperationCount": 0,
            "dependencySourceExecutionCount": 0,
            "fileWriteCount": 0,
        }
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parse_arguments(argv)
    except CliUsageFailure:
        sys.stdout.buffer.write(error_document_bytes())
        return 2
    try:
        candidate = generate_wave5_candidate(ROOT)
    except Exception:
        sys.stdout.buffer.write(error_document_bytes())
        return 1
    sys.stdout.buffer.write(canonical_json_bytes(candidate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
