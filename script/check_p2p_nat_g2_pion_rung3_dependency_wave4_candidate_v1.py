#!/usr/bin/env python3
"""Project the exact externally pinned Wave3 graph frontier into Wave4.

Run only with ``python3 -I -B -S``.  The checker holds the final v2 graph
checker and its tests by descriptor, invokes the exact v2 checker in-process,
validates its exact content/input/graph/frontier bindings, and writes one
canonical Wave4 identity candidate to stdout.  It grants no authority and
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
            "Wave4 candidate checker requires unoptimized "
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
V2_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v2.py"
V2_CHECKER_RAW_SHA256 = (
    "1d42ffae2945bde3406bfab577ff361286859e9815e487a20cbc14282e83acf4"
)
V2_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v2.py"
V2_TESTS_RAW_SHA256 = (
    "e6a747d824829fa0d456c132f90048abbd4ecb36f9782116d0a2d60870b4990b"
)
V2_CANDIDATE_CONTENT_SHA256 = (
    "fa67dfc9a8d49304bcc9b001e0233582e547313cc17b61934674f776ab9df215"
)
V2_INPUT_SET_SHA256 = (
    "5d79f81dfdc835c0552c0c301a2ef8e669ebcb7d13c0674d9d9cc47929d21a97"
)
V2_NODE_SET_SHA256 = (
    "970144c5bd6c1a7d8a13a8bdd5c9efc63fc81afab5860ca8fa77fce49871601a"
)
V2_EDGE_SET_SHA256 = (
    "25cb01585c5d7fc4ec8840d038a195c513e0383e2a4931947312ea9e47e3db47"
)
V2_MODULE_NODE_SET_SHA256 = (
    "c28bd8fd5499381466b9a32f5574162e32966527d921da976e0a42118e2af148"
)
V2_MODULE_EDGE_SET_SHA256 = (
    "9c79640ccabf8fa415bfefa0ca4908bf9cfed05d48821f65873e27f929fc770c"
)
V2_MODULE_GRAPH_AND_FRONTIER_SHA256 = (
    "5022008181e58b433604617df013a8998b21eeba20f9ea8d4c96a767d161090d"
)
V2_RECONSTRUCTION_PROJECTION_SHA256 = (
    "a824e5e3bf5fe0ede2c795192c3102a5f8d607309b3409073163de1313a23fb5"
)
V2_GRAPH_SHA256 = V2_RECONSTRUCTION_PROJECTION_SHA256
V2_FRONTIER_SHA256 = (
    "568ad0362707a384511c9e23e870bd34ae2ff58faa1043e3afe7e0273227491d"
)
CHECKER_ID = "g2-pion-ice-v4.3.0-wave4-frontier-candidate-check-v1"
CODE_MAXIMUM_BYTES = 4 * 1024 * 1024

EXPECTED_FRONTIER = [
    ("github.com/google/go-cmp", "v0.6.0", True),
    ("github.com/stretchr/objx", "v0.5.0", False),
    ("github.com/yuin/goldmark", "v1.4.13", True),
    ("golang.org/x/crypto", "v0.46.0", False),
    ("golang.org/x/mod", "v0.17.0", False),
    ("golang.org/x/net", "v0.21.0", False),
    ("golang.org/x/sync", "v0.10.0", False),
    ("golang.org/x/sync", "v0.11.0", False),
    ("golang.org/x/sys", "v0.39.0", False),
    (
        "golang.org/x/telemetry",
        "v0.0.0-20251203150158-8fff8a5912fc",
        False,
    ),
    (
        "golang.org/x/telemetry",
        "v0.0.0-20260109210033-bd525da824e2",
        True,
    ),
    ("golang.org/x/term", "v0.38.0", False),
    ("golang.org/x/text", "v0.32.0", False),
    ("golang.org/x/time", "v0.10.0", False),
    (
        "golang.org/x/tools",
        "v0.21.1-0.20240508182429-e35e4ccd0d2d",
        False,
    ),
    ("golang.org/x/tools", "v0.39.0", False),
]


class Wave4CandidateFailure(RuntimeError):
    """A content-free, fail-closed checker error."""


class CliUsageFailure(RuntimeError):
    """An intentionally content-free command-line usage error."""


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise CliUsageFailure("E_CLI_USAGE")


def check(condition: bool, code: str) -> None:
    if not condition:
        raise Wave4CandidateFailure(code)


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
    """Hold the exact v2 checker before any of its code is executed."""

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
                "E_V2_CHECKER_IDENTITY",
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
                "E_V2_CHECKER_IDENTITY",
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
            "E_V2_CHECKER_IDENTITY",
        )

    @staticmethod
    def _validate_file(info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= CODE_MAXIMUM_BYTES,
            "E_V2_CHECKER_IDENTITY",
        )

    def _read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_V2_CHECKER_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_V2_CHECKER_IDENTITY")
        after = os.fstat(self.fd)
        check(
            file_identity(before) == file_identity(after),
            "E_V2_CHECKER_IDENTITY",
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
            raise Wave4CandidateFailure("E_ROOT_IDENTITY") from error
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
            "E_V2_CHECKER_IDENTITY",
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
                "E_V2_CHECKER_IDENTITY",
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


def load_v2_checker(held: BootstrapPinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_checker_v2_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V2_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_checker_v2_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V2_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise Wave4CandidateFailure("E_V2_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "combined_identity_barrier",
        "generate_candidate",
        "sha256_bytes",
    ):
        check(callable(getattr(module, name, None)), "E_V2_CHECKER_API")
    check(
        module.CHECKER_ID
        == "g2-pion-ice-v4.3.0-combined-wave1-wave2-wave3-check-v2"
        and module.V1_CHECKER_RAW_SHA256
        == "b11047fd74e8ba4b41d66590975270921a5835bf444ad2e942af357d56764f15"
        and module.V1_PROVIDER_RAW_SHA256
        == "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3",
        "E_V2_CHECKER_API",
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


def verify_v2_content_binding(candidate: Mapping[str, Any]) -> None:
    binding = candidate.get("contentBinding")
    check(
        type(binding) is dict
        and binding.get("algorithm") == "sha256"
        and binding.get("canonicalization")
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and binding.get("scope") == "candidate_without_contentBinding"
        and binding.get("sha256") == V2_CANDIDATE_CONTENT_SHA256,
        "E_V2_CONTENT",
    )
    without = dict(candidate)
    without.pop("contentBinding", None)
    check(
        sha256_bytes(canonical_json_bytes(without))
        == V2_CANDIDATE_CONTENT_SHA256,
        "E_V2_CONTENT",
    )


def validate_v2_candidate(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    check(type(candidate) is dict, "E_V2_CANDIDATE")
    verify_v2_content_binding(candidate)
    input_set = candidate.get("inputSet")
    graph = candidate.get("graphDiscovery")
    coverage = candidate.get("coverage")
    authority = candidate.get("authority")
    check(
        candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-wave3-"
            "fixed-point-candidate"
        )
        and candidate.get("schemaVersion") == "2.0"
        and candidate.get("status")
        == "combined_graph_discovery_complete_next_wave_required"
        and candidate.get("route") == "next_wave_required"
        and candidate.get("verificationOnly") is True
        and candidate.get("recordModeExposed") is False,
        "E_V2_CANDIDATE",
    )
    check(
        type(input_set) is dict
        and input_set.get("heldSourceInputCount") == 101
        and input_set.get("resourceCount") == 100
        and input_set.get("modCount") == 50
        and input_set.get("zipCount") == 50
        and input_set.get("uniqueModuleVersionTupleCount") == 50
        and input_set.get("aggregateRawByteSize") == 73_022_054
        and input_set.get("combinedInputSetSha256") == V2_INPUT_SET_SHA256,
        "E_V2_INPUT",
    )
    expected_hashes = {
        "nodeSetSha256": V2_NODE_SET_SHA256,
        "edgeSetSha256": V2_EDGE_SET_SHA256,
        "moduleNodeSetSha256": V2_MODULE_NODE_SET_SHA256,
        "moduleEdgeSetSha256": V2_MODULE_EDGE_SET_SHA256,
        "moduleGraphAndFrontierSha256":
            V2_MODULE_GRAPH_AND_FRONTIER_SHA256,
        "reconstructionProjectionSha256":
            V2_RECONSTRUCTION_PROJECTION_SHA256,
        "graphSha256": V2_GRAPH_SHA256,
    }
    check(
        type(graph) is dict
        and graph.get("newTupleCount") == 16
        and graph.get("fixedPointReached") is False
        and graph.get("graphNodeCount") == 132
        and graph.get("graphEdgeCount") == 1_047
        and graph.get("moduleNodeCount") == 67
        and graph.get("moduleEdgeCount") == 181
        and all(graph.get(key) == value for key, value in expected_hashes.items()),
        "E_V2_GRAPH",
    )
    frontier = graph.get("exactFrontier")
    check(
        frontier == expected_frontier_rows()
        and sha256_bytes(canonical_json_bytes(frontier))
        == V2_FRONTIER_SHA256,
        "E_V2_FRONTIER",
    )
    check(
        type(coverage) is dict
        and coverage.get("archiveCount") == 51
        and coverage.get("aggregateEntryCount") == 14_836
        and coverage.get("aggregateUncompressedByteCount") == 269_029_720
        and coverage.get("goSourceFileCount") == 11_820
        and coverage.get("semanticParsedGoSourceCount") == 10_953
        and coverage.get("testdataSemanticExclusionCount") == 867
        and coverage.get("semanticParsedGoSourceCount")
        + coverage.get("testdataSemanticExclusionCount")
        == coverage.get("goSourceFileCount"),
        "E_V2_COVERAGE",
    )
    check(
        type(authority) is dict
        and bool(authority)
        and all(value is False for value in authority.values()),
        "E_V2_AUTHORITY",
    )
    return frontier


def wave4_rows(frontier: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    check(
        list(frontier) == expected_frontier_rows(),
        "E_V2_FRONTIER",
    )
    result: list[dict[str, Any]] = []
    for order, row in enumerate(frontier, 1):
        digest = sha256_bytes(
            f"{row['module']}\n{row['version']}\n".encode("utf-8")
        )
        result.append(
            {
                "tupleOrder": order,
                "tupleId": f"wave4-{order:03d}-{digest[:12]}",
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
        len(result) == 16
        and [row["tupleOrder"] for row in result] == list(range(1, 17))
        and len({row["tupleId"] for row in result}) == 16
        and sum(row["selectedByGraphAlgorithm"] for row in result) == 3,
        "E_WAVE4_PROJECTION",
    )
    return result


def generate_wave4_candidate(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    with BootstrapPinnedCodeFile(
        root,
        V2_CHECKER_PATH,
        V2_CHECKER_RAW_SHA256,
    ) as checker_held:
        v2 = load_v2_checker(checker_held)
        with v2.PinnedCodeFile(
            root,
            V2_TESTS_PATH,
            V2_TESTS_RAW_SHA256,
        ) as tests_held:
            held = (checker_held, tests_held)
            v2.combined_identity_barrier(root, held)
            candidate = v2.generate_candidate(root)
            v2.combined_identity_barrier(root, held)
            frontier = validate_v2_candidate(candidate)
            rows = wave4_rows(frontier)
            v2.combined_identity_barrier(root, held)
            body = {
                "documentType": (
                    "aetherlink.g2-pion-rung3-wave4-frontier-"
                    "identity-candidate"
                ),
                "schemaVersion": "1.0",
                "checkerId": CHECKER_ID,
                "status": (
                    "exact_16_wave4_frontier_identity_candidates_"
                    "prepared_without_authority"
                ),
                "result": (
                    "externally_pinned_v2_frontier_projected_"
                    "to_wave4_identity_candidates"
                ),
                "verificationOnly": True,
                "recordModeExposed": False,
                "producerPackageBindings": [
                    {
                        "role": "combined_fixed_point_v2_checker",
                        "path": V2_CHECKER_PATH,
                        "rawSha256": V2_CHECKER_RAW_SHA256,
                    },
                    {
                        "role": "combined_fixed_point_v2_tests",
                        "path": V2_TESTS_PATH,
                        "rawSha256": V2_TESTS_RAW_SHA256,
                    },
                ],
                "sourceCandidateBinding": {
                    "contentSha256": V2_CANDIDATE_CONTENT_SHA256,
                    "combinedInputSetSha256": V2_INPUT_SET_SHA256,
                    "graphSha256": V2_GRAPH_SHA256,
                    "moduleGraphAndFrontierSha256":
                        V2_MODULE_GRAPH_AND_FRONTIER_SHA256,
                    "exactFrontierCanonicalSha256": V2_FRONTIER_SHA256,
                    "route": "next_wave_required",
                    "newTupleCount": 16,
                    "fixedPointReached": False,
                },
                "wave": {
                    "waveId": (
                        "g2-pion-ice-v4.3.0-dependency-source-wave4-"
                        "candidate-v1"
                    ),
                    "tupleCount": 16,
                    "graphSelectedTupleCount": 3,
                    "versionSpecificNonSelectedTupleCount": 13,
                    "identityResolvedTupleCount": 0,
                    "acquisitionReadyTupleCount": 0,
                    "tuples": rows,
                },
                "nextAction": (
                    "prepare_separate_wave4_identity_and_acquisition_"
                    "decision"
                ),
                "operationCounters": {
                    "v2CandidateInvocationCount": 1,
                    "inheritedFullSourceReconstructionCount": 2,
                    "inheritedArchiveOpenCount": 102,
                    "networkOperationCount": 0,
                    "subprocessCount": 0,
                    "dependencySourceExecutionCount": 0,
                    "archiveExtractionCount": 0,
                    "fileWriteCount": 0,
                },
                "closure": {
                    "dependencyFixedPointReached": False,
                    "dependencyClosureComplete": False,
                    "wave4IdentityResolved": False,
                    "wave4AcquisitionReady": False,
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
                "wave4_candidate_without_contentBinding",
            )
            v2.combined_identity_barrier(root, held)
            return result


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def error_document_bytes() -> bytes:
    return canonical_json_bytes(
        {
            "documentType": (
                "aetherlink.g2-pion-rung3-wave4-frontier-"
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
        candidate = generate_wave4_candidate(ROOT)
    except Exception:
        sys.stdout.buffer.write(error_document_bytes())
        return 1
    sys.stdout.buffer.write(canonical_json_bytes(candidate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
