#!/usr/bin/env python3
"""Recompute the bounded Wave1+Wave2 dependency graph without publishing.

Run only with ``python3 -I -B -S``.  The checker opens immutable, hash-bound
evidence and 69 retained source inputs, parses ZIP members in memory, invokes
the pinned Wave1 graph implementation twice, and emits one canonical candidate
to stdout.  It does not grant authority or write a result, permit, claim, or
manifest.
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
            "combined fixed-point checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
RUNNER_PATH = "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
RUNNER_SHA256 = "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
RUNNER_MAXIMUM_BYTES = 4 * 1024 * 1024
JSON_MAXIMUM_BYTES = 8 * 1024 * 1024
CHECKER_ID = "g2-pion-ice-v4.3.0-combined-wave1-wave2-fixed-point-check-v1"

WAVE1_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v3.json"
)
WAVE1_RESULT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-result-v3.json"
)
WAVE1_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-manifest-v3.json"
)
WAVE1_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-v3.json"
)
WAVE1_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-manifest-v3.json"
)
WAVE2_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-receipt-v3.json"
)
WAVE2_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-manifest-v3.json"
)
WAVE2_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-v3.json"
)
WAVE2_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-manifest-v3.json"
)

CONTROL_SHA256 = {
    WAVE1_PERMIT_PATH:
        "e9b92730e558fc128ab919f8b1e1da73625d2a14df8288f119a1802f269a63ef",
    WAVE1_RESULT_PATH:
        "cd7bba257995bb98199a336d343bf98859e661a1abc0dbac5666c314d8fd519f",
    WAVE1_MANIFEST_PATH:
        "4559c8fc207cad88b2d963e23b4132b7a053aeb77bfc7aa758fb58199c58b933",
    WAVE1_READBACK_PATH:
        "938ab9dc83e3580c6801c8d569a25389eae591c21b3a82df03980a06db812a5a",
    WAVE1_READBACK_MANIFEST_PATH:
        "ad5a633713f45d273f905cb7f02a5b08f884b1b98e48eb1ba478e6bce59b479c",
    WAVE2_RECEIPT_PATH:
        "0f991b54cd5155c26b235d5c3847a8132975569f80267195a0882001ecd9bd97",
    WAVE2_MANIFEST_PATH:
        "ec6f65f857f4c4de4c1ccf649348f20bcd0e37518d2db945f0b75f3495717b34",
    WAVE2_READBACK_PATH:
        "a9366ccdb94e0841a22cbea93766c6808bfe94116fdc267d3d1421aa7f3bf804",
    WAVE2_READBACK_MANIFEST_PATH:
        "ccd31e0127de093abb1234e5a2a1d6abe6910a20b9c67ec77fa3bec9eb215a71",
}

WAVE1_INPUT_KEYS = frozenset(
    {
        "acquisitionReceipt",
        "aggregateEntryCount",
        "aggregateRawByteSize",
        "aggregateUncompressedByteCount",
        "dependencyDirectory",
        "modCount",
        "orderedSourceSetSha256",
        "resourceCount",
        "resources",
        "rootArchive",
        "zipCount",
    }
)
WAVE1_ROOT_KEYS = frozenset({"byteSize", "path", "rawSha256"})
WAVE1_RESOURCE_KEYS = frozenset(
    {
        "byteSize",
        "kind",
        "module",
        "order",
        "path",
        "rawSha256",
        "tupleId",
        "tupleOrder",
        "version",
    }
)
WAVE2_SOURCE_KEYS = frozenset(
    {
        "compressionTelemetry",
        "embeddedGoModByteParity",
        "embeddedGoModPresent",
        "entryCount",
        "goModH1",
        "modLinkCount",
        "modMode",
        "modOutputFileName",
        "modRawByteSize",
        "modRawSha256",
        "modRequestOrdinal",
        "modUrl",
        "module",
        "modulePrefix",
        "moduleZipH1",
        "order",
        "selectedByGraphAlgorithm",
        "tupleId",
        "uncompressedByteCount",
        "version",
        "zipLinkCount",
        "zipMode",
        "zipOutputFileName",
        "zipRawByteSize",
        "zipRawSha256",
        "zipRequestOrdinal",
        "zipUrl",
    }
)
FRONTIER_KEYS = frozenset(
    {
        "acquisitionAuthorized",
        "module",
        "requiresSeparateWaveDecision",
        "selectedByGraphAlgorithm",
        "version",
    }
)


class CombinedCheckFailure(RuntimeError):
    """A content-free, fail-closed checker error."""


class CliUsageFailure(RuntimeError):
    """An intentionally content-free command-line usage failure."""


class CanonicalArgumentParser(argparse.ArgumentParser):
    """Preserve normal help while keeping invalid usage off stderr."""

    def error(self, message: str) -> None:
        del message
        raise CliUsageFailure("E_CLI_USAGE")


def check(condition: bool, code: str) -> None:
    if not condition:
        raise CombinedCheckFailure(code)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def exact_keys(value: Any, expected: frozenset[str], code: str) -> None:
    check(type(value) is dict and frozenset(value) == expected, code)


def safe_relative(value: Any) -> str:
    check(
        type(value) is str
        and bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and "\x00" not in value,
        "E_PATH",
    )
    parts = value.split("/")
    check(
        all(part not in {"", ".", ".."} for part in parts)
        and PurePosixPath(value).as_posix() == value,
        "E_PATH",
    )
    return value


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


class PinnedRunnerFile:
    """Hold the graph provider before executing its exact pinned bytes."""

    def __init__(self, root: Path) -> None:
        self.root_fd = -1
        self.fd = -1
        self.parent_fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        self.raw = b""
        try:
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            root_info = os.fstat(self.root_fd)
            self._validate_directory(root_info)
            current = os.dup(self.root_fd)
            for component in safe_relative(RUNNER_PATH).split("/")[:-1]:
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
            name = RUNNER_PATH.rsplit("/", 1)[1]
            self.fd = os.open(
                name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=self.parent_fd,
            )
            self.name = name
            self.initial = os.fstat(self.fd)
            self._validate_file(self.initial)
            first = self._read_pass()
            second = self._read_pass()
            check(
                first == second and sha256_bytes(first) == RUNNER_SHA256,
                "E_RUNNER_IDENTITY",
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
            "E_RUNNER_IDENTITY",
        )

    @staticmethod
    def _validate_file(info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= RUNNER_MAXIMUM_BYTES,
            "E_RUNNER_IDENTITY",
        )

    def _read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_RUNNER_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_RUNNER_IDENTITY")
        after = os.fstat(self.fd)
        check(file_identity(before) == file_identity(after), "E_RUNNER_IDENTITY")
        return b"".join(chunks)

    def final_barrier(self) -> None:
        current = os.fstat(self.fd)
        named = os.stat(self.name, dir_fd=self.parent_fd, follow_symlinks=False)
        check(
            file_identity(current) == file_identity(self.initial)
            and file_identity(named) == file_identity(self.initial),
            "E_RUNNER_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            current_dir = os.fstat(child)
            named_dir = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            check(
                directory_identity(current_dir) == directory_identity(initial)
                and directory_identity(named_dir) == directory_identity(initial),
                "E_RUNNER_IDENTITY",
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

    def __enter__(self) -> "PinnedRunnerFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def load_pinned_runner(held: PinnedRunnerFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_graph_provider_v1")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / RUNNER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_graph_provider_v1",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            RUNNER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_RUNNER_LOAD") from error
    for name in (
        "HeldInputSet",
        "strict_json",
        "canonical_json_bytes",
        "content_bound",
        "go_proxy_escape",
        "parse_go_mod",
        "inspect_zip_bytes",
        "profile_rows",
        "build_graph",
    ):
        check(callable(getattr(module, name, None)), "E_RUNNER_API")
    check(
        getattr(module, "GRAPH_ALGORITHM", None)
        == "go1.24_mvs_profile_union_fixed_point_v1",
        "E_RUNNER_API",
    )
    return module


def control_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": JSON_MAXIMUM_BYTES,
            "ownerOnly": False,
            "kind": "terminal_evidence",
        }
        for path, digest in CONTROL_SHA256.items()
    ]


def parse_control_documents(
    runner: types.ModuleType,
    held: Any,
) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for path in CONTROL_SHA256:
        value = runner.strict_json(held.raw[path], path)
        check(type(value) is dict, "E_CONTROL_JSON")
        documents[path] = value
    return documents


def verify_content_binding(
    runner: types.ModuleType,
    document: Mapping[str, Any],
) -> None:
    binding = document.get("contentBinding")
    check(
        type(binding) is dict
        and binding.get("algorithm") == "sha256"
        and binding.get("canonicalization")
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and is_sha256(binding.get("sha256")),
        "E_CONTENT_BINDING",
    )
    without = dict(document)
    without.pop("contentBinding", None)
    check(
        binding["sha256"]
        == sha256_bytes(runner.canonical_json_bytes(without)),
        "E_CONTENT_BINDING",
    )


def frontier_projection(rows: Any) -> list[dict[str, Any]]:
    check(type(rows) is list and len(rows) == 15, "E_FRONTIER")
    result: list[dict[str, Any]] = []
    for row in rows:
        exact_keys(row, FRONTIER_KEYS, "E_FRONTIER")
        check(
            row.get("acquisitionAuthorized") is False
            and row.get("requiresSeparateWaveDecision") is True
            and type(row.get("module")) is str
            and type(row.get("version")) is str
            and type(row.get("selectedByGraphAlgorithm")) is bool,
            "E_FRONTIER",
        )
        result.append(
            {
                "module": row["module"],
                "version": row["version"],
                "selectedByGraphAlgorithm": row["selectedByGraphAlgorithm"],
            }
        )
    return result


def wave2_projection(rows: Any) -> list[dict[str, Any]]:
    check(type(rows) is list and len(rows) == 15, "E_WAVE2_SOURCE")
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        exact_keys(row, WAVE2_SOURCE_KEYS, "E_WAVE2_SOURCE")
        check(
            row.get("order") == index
            and row.get("modRequestOrdinal") == 2 * index - 1
            and row.get("zipRequestOrdinal") == 2 * index
            and row.get("modMode") == "0600"
            and row.get("zipMode") == "0600"
            and row.get("modLinkCount") == 1
            and row.get("zipLinkCount") == 1
            and row.get("embeddedGoModByteParity") is True
            and type(row.get("embeddedGoModPresent")) is bool
            and type(row.get("selectedByGraphAlgorithm")) is bool
            and type(row.get("module")) is str
            and type(row.get("version")) is str
            and type(row.get("tupleId")) is str
            and type(row.get("modulePrefix")) is str
            and type(row.get("modOutputFileName")) is str
            and "/" not in row["modOutputFileName"]
            and type(row.get("zipOutputFileName")) is str
            and "/" not in row["zipOutputFileName"]
            and type(row.get("modRawByteSize")) is int
            and row["modRawByteSize"] > 0
            and type(row.get("zipRawByteSize")) is int
            and row["zipRawByteSize"] > 0
            and is_sha256(row.get("modRawSha256"))
            and is_sha256(row.get("zipRawSha256"))
            and type(row.get("goModH1")) is str
            and row["goModH1"].startswith("h1:")
            and type(row.get("moduleZipH1")) is str
            and row["moduleZipH1"].startswith("h1:"),
            "E_WAVE2_SOURCE",
        )
        result.append(
            {
                "module": row["module"],
                "version": row["version"],
                "selectedByGraphAlgorithm": row["selectedByGraphAlgorithm"],
            }
        )
    check(len({(row["module"], row["version"]) for row in result}) == 15, "E_WAVE2_SOURCE")
    return result


def validate_terminal_documents(
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    permit = documents[WAVE1_PERMIT_PATH]
    result = documents[WAVE1_RESULT_PATH]
    manifest = documents[WAVE1_MANIFEST_PATH]
    readback = documents[WAVE1_READBACK_PATH]
    readback_manifest = documents[WAVE1_READBACK_MANIFEST_PATH]
    receipt = documents[WAVE2_RECEIPT_PATH]
    wave2_manifest = documents[WAVE2_MANIFEST_PATH]
    wave2_readback = documents[WAVE2_READBACK_PATH]
    wave2_readback_manifest = documents[WAVE2_READBACK_MANIFEST_PATH]

    for document in (permit, result, manifest, readback, readback_manifest):
        verify_content_binding(runner, document)
    check(
        permit.get("permitId")
        == (
            "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-"
            "execution-permit-v3"
        ),
        "E_WAVE1_TERMINAL",
    )
    tools = permit.get("toolBindings")
    check(type(tools) is list, "E_WAVE1_TERMINAL")
    pinned = [
        row
        for row in tools
        if type(row) is dict and row.get("role") == "review_runner"
    ]
    check(
        len(pinned) == 1
        and pinned[0].get("path") == RUNNER_PATH
        and pinned[0].get("rawSha256") == RUNNER_SHA256,
        "E_WAVE1_TERMINAL",
    )
    graph = result.get("graphDiscovery")
    check(
        result.get("status") == "wave1_graph_discovery_complete_new_wave_required"
        and type(graph) is dict
        and graph.get("fixedPointReached") is False
        and graph.get("newTupleCount") == 15
        and graph.get("unmappedExternalImportCount") == 0
        and graph.get("unresolvedDeclaredExternalImportCount") == 0,
        "E_WAVE1_TERMINAL",
    )
    check(
        manifest.get("manifestWrittenLast") is True
        and manifest.get("resultPath") == WAVE1_RESULT_PATH
        and manifest.get("resultRawSha256")
        == CONTROL_SHA256[WAVE1_RESULT_PATH],
        "E_WAVE1_TERMINAL",
    )
    check(
        readback.get("status")
        == (
            "dependency_source_review_wave1_readback_complete_"
            "new_tuple_wave_required_manifest_pending"
        )
        and readback.get("graphVerification", {}).get(
            "sourceGraphAlgorithmsReexecuted"
        )
        is False
        and readback.get("graphVerification", {}).get("archiveMembersReopened")
        is False,
        "E_WAVE1_TERMINAL",
    )
    check(
        readback_manifest.get("manifestWrittenLast") is True
        and readback_manifest.get("independentReadbackPassed") is True
        and readback_manifest.get("route") == "new_tuple_wave_required"
        and readback_manifest.get("reviewResultBinding", {}).get("rawSha256")
        == CONTROL_SHA256[WAVE1_RESULT_PATH]
        and readback_manifest.get("readbackReceiptBinding", {}).get("rawSha256")
        == CONTROL_SHA256[WAVE1_READBACK_PATH],
        "E_WAVE1_TERMINAL",
    )

    check(
        receipt.get("status") == "acquired_pending_independent_readback"
        and receipt.get("acceptedTupleCount") == 15
        and receipt.get("acceptedArtifactCount") == 30
        and receipt.get("validatedAndStagedTupleCount") == 15
        and receipt.get("validatedAndStagedResourceCount") == 30
        and receipt.get("validatedModResourceCount") == 15
        and receipt.get("validatedZipResourceCount") == 15
        and receipt.get("networkRequestAttemptCount") == 30
        and receipt.get("responseBodyCompletedCount") == 30
        and receipt.get("dependencyFixedPointReached") is False
        and receipt.get("dependencySourceReviewed") is False
        and receipt.get("candidateSelected") is False
        and receipt.get("librarySelected") is False,
        "E_WAVE2_TERMINAL",
    )
    check(
        wave2_manifest.get("status")
        == "wave2_v3_acquisition_publication_complete_pending_independent_readback"
        and wave2_manifest.get("manifestWrittenLast") is True
        and wave2_manifest.get("successReceiptPath") == WAVE2_RECEIPT_PATH
        and wave2_manifest.get("successReceiptRawSha256")
        == CONTROL_SHA256[WAVE2_RECEIPT_PATH],
        "E_WAVE2_TERMINAL",
    )
    check(
        wave2_readback.get("status") == "wave2_v3_independent_readback_complete"
        and wave2_readback.get("independentReadbackPassed") is True
        and wave2_readback.get("stableReadPassCount") == 3
        and wave2_readback.get("tupleCount") == 15
        and wave2_readback.get("resourceCount") == 30
        and wave2_readback.get("networkUsed") is False
        and wave2_readback.get("sourceExecutionUsed") is False
        and wave2_readback.get("sourceExtractionUsed") is False
        and wave2_readback.get("acquisitionReceiptRawSha256")
        == CONTROL_SHA256[WAVE2_RECEIPT_PATH]
        and wave2_readback.get("acquisitionManifestRawSha256")
        == CONTROL_SHA256[WAVE2_MANIFEST_PATH],
        "E_WAVE2_TERMINAL",
    )
    check(
        wave2_readback_manifest.get("status")
        == "wave2_v3_independent_readback_published"
        and wave2_readback_manifest.get("manifestWrittenLast") is True
        and wave2_readback_manifest.get("independentReadbackPassed") is True
        and wave2_readback_manifest.get("tupleCount") == 15
        and wave2_readback_manifest.get("resourceCount") == 30
        and wave2_readback_manifest.get("nextAction")
        == "rerun_combined_wave1_wave2_fixed_point_dependency_graph"
        and wave2_readback_manifest.get("readbackReceiptPath")
        == WAVE2_READBACK_PATH
        and wave2_readback_manifest.get("readbackReceiptRawSha256")
        == CONTROL_SHA256[WAVE2_READBACK_PATH]
        and wave2_readback_manifest.get("acquisitionManifestRawSha256")
        == CONTROL_SHA256[WAVE2_MANIFEST_PATH],
        "E_WAVE2_TERMINAL",
    )
    check(
        frontier_projection(graph.get("exactFrontier"))
        == wave2_projection(receipt.get("sources")),
        "E_FRONTIER_BINDING",
    )


def source_bindings(
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    permit = documents[WAVE1_PERMIT_PATH]
    inputs = permit.get("inputBindings")
    exact_keys(inputs, WAVE1_INPUT_KEYS, "E_WAVE1_INPUT")
    root = inputs["rootArchive"]
    exact_keys(root, WAVE1_ROOT_KEYS, "E_WAVE1_INPUT")
    check(
        type(root.get("byteSize")) is int
        and root["byteSize"] > 0
        and is_sha256(root.get("rawSha256")),
        "E_WAVE1_INPUT",
    )
    bindings: list[dict[str, Any]] = [
        {
            "wave": "root",
            "path": safe_relative(root["path"]),
            "rawSha256": root["rawSha256"],
            "maximumBytes": root["byteSize"],
            "ownerOnly": True,
            "kind": "root_zip",
            "module": "github.com/pion/ice/v4",
            "version": "v4.3.0",
            "modulePrefix": "github.com/pion/ice/v4@v4.3.0/",
            "tupleId": "root",
            "tupleOrder": 0,
        }
    ]
    resources = inputs.get("resources")
    check(type(resources) is list and len(resources) == 38, "E_WAVE1_INPUT")
    pairs: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for index, value in enumerate(resources, 1):
        exact_keys(value, WAVE1_RESOURCE_KEYS, "E_WAVE1_INPUT")
        check(
            value.get("order") == index
            and value.get("kind") in {"mod", "zip"}
            and type(value.get("module")) is str
            and type(value.get("version")) is str
            and type(value.get("tupleId")) is str
            and type(value.get("tupleOrder")) is int
            and 1 <= value["tupleOrder"] <= 19
            and type(value.get("byteSize")) is int
            and value["byteSize"] > 0
            and is_sha256(value.get("rawSha256")),
            "E_WAVE1_INPUT",
        )
        pairs[value["tupleId"]].append(value)
        row = {
            **dict(value),
            "wave": "wave1",
            "path": safe_relative(value["path"]),
            "maximumBytes": value["byteSize"],
            "ownerOnly": True,
        }
        if value["kind"] == "zip":
            row["modulePrefix"] = (
                f"{runner.go_proxy_escape(value['module'])}@"
                f"{runner.go_proxy_escape(value['version'])}/"
            )
        bindings.append(row)
    check(
        inputs.get("resourceCount") == 38
        and inputs.get("modCount") == 19
        and inputs.get("zipCount") == 19
        and len(pairs) == 19,
        "E_WAVE1_INPUT",
    )
    for rows in pairs.values():
        check(
            len(rows) == 2
            and {row["kind"] for row in rows} == {"mod", "zip"}
            and len(
                {
                    (
                        row["module"],
                        row["version"],
                        row["tupleOrder"],
                    )
                    for row in rows
                }
            )
            == 1,
            "E_WAVE1_INPUT",
        )

    receipt = documents[WAVE2_RECEIPT_PATH]
    wave2_manifest = documents[WAVE2_MANIFEST_PATH]
    final_directory = safe_relative(wave2_manifest.get("finalDirectoryPath"))
    check(
        final_directory
        == "build/offline-source/pion-ice-v4.3.0/dependencies/wave-2-v3/accepted",
        "E_WAVE2_INPUT",
    )
    sources = receipt.get("sources")
    wave2_projection(sources)
    for value in sources:
        common = {
            "wave": "wave2",
            "module": value["module"],
            "version": value["version"],
            "tupleId": value["tupleId"],
            "tupleOrder": 19 + value["order"],
            "ownerOnly": True,
        }
        bindings.append(
            {
                **common,
                "path": safe_relative(
                    f"{final_directory}/{value['modOutputFileName']}"
                ),
                "rawSha256": value["modRawSha256"],
                "maximumBytes": value["modRawByteSize"],
                "kind": "mod",
                "order": value["modRequestOrdinal"],
            }
        )
        bindings.append(
            {
                **common,
                "path": safe_relative(
                    f"{final_directory}/{value['zipOutputFileName']}"
                ),
                "rawSha256": value["zipRawSha256"],
                "maximumBytes": value["zipRawByteSize"],
                "kind": "zip",
                "order": value["zipRequestOrdinal"],
                "modulePrefix": value["modulePrefix"],
            }
        )

    check(
        len(bindings) == 69
        and sum(row["kind"] == "root_zip" for row in bindings) == 1
        and sum(row["kind"] == "mod" for row in bindings) == 34
        and sum(row["kind"] == "zip" for row in bindings) == 34,
        "E_COMBINED_INPUT",
    )
    check(
        len({row["path"] for row in bindings}) == 69
        and len({row["tupleId"] for row in bindings if row["kind"] != "root_zip"})
        == 34,
        "E_COMBINED_INPUT",
    )
    tuple_pairs: dict[str, set[tuple[str, str]]] = defaultdict(set)
    tuple_kinds: dict[str, set[str]] = defaultdict(set)
    for row in bindings:
        if row["kind"] == "root_zip":
            continue
        tuple_pairs[row["tupleId"]].add((row["module"], row["version"]))
        tuple_kinds[row["tupleId"]].add(row["kind"])
    check(
        all(len(value) == 1 for value in tuple_pairs.values())
        and all(value == {"mod", "zip"} for value in tuple_kinds.values())
        and len(
            {
                next(iter(value))
                for value in tuple_pairs.values()
            }
        )
        == 34,
        "E_COMBINED_INPUT",
    )
    return bindings


def graph_limits(runner: types.ModuleType) -> dict[str, int]:
    return {
        "maximumArchiveBytes": runner.DEFAULT_MAXIMUM_ARCHIVE_BYTES,
        "maximumSingleFileBytes": runner.DEFAULT_MAXIMUM_ENTRY_BYTES,
        "maximumEntriesPerArchive": runner.DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE,
        "maximumAggregateEntries": runner.DEFAULT_MAXIMUM_AGGREGATE_ENTRIES,
        "maximumAggregateUncompressedBytes": (
            runner.DEFAULT_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
        ),
        "maximumGraphNodes": runner.DEFAULT_MAXIMUM_GRAPH_NODES,
        "maximumGraphEdges": runner.DEFAULT_MAXIMUM_GRAPH_EDGES,
    }


def reconstruct_graph(
    runner: types.ModuleType,
    permit: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
    held: Any,
) -> tuple[dict[str, Any], dict[str, int]]:
    limits = graph_limits(runner)
    metadata_rows: list[dict[str, Any]] = []
    archive_rows: list[dict[str, Any]] = []
    pairs: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    aggregate_entries = 0
    aggregate_uncompressed = 0
    for binding in bindings:
        kind = binding["kind"]
        if kind in {"mod", "zip"}:
            pairs[binding["tupleId"]][kind] = binding
        if kind == "mod":
            metadata = runner.parse_go_mod(
                held.raw[binding["path"]],
                binding["module"],
            )
            metadata_rows.append(
                {
                    "tupleId": binding["tupleId"],
                    "tupleOrder": binding["tupleOrder"],
                    "module": binding["module"],
                    "version": binding["version"],
                    "metadata": metadata,
                    "externalModRawSha256": binding["rawSha256"],
                }
            )
        elif kind in {"zip", "root_zip"}:
            archive = runner.inspect_zip_bytes(
                held.raw[binding["path"]],
                binding,
                limits,
            )
            archive["kind"] = kind
            archive_rows.append(archive)
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
    check(
        aggregate_entries <= limits["maximumAggregateEntries"]
        and aggregate_uncompressed
        <= limits["maximumAggregateUncompressedBytes"],
        "E_ARCHIVE_AGGREGATE",
    )
    root_archives = [row for row in archive_rows if row["kind"] == "root_zip"]
    check(len(root_archives) == 1, "E_ROOT_ARCHIVE")
    embedded_root = root_archives[0].pop("embeddedGoMod")
    check(type(embedded_root) is bytes, "E_ROOT_ARCHIVE")
    root_metadata = runner.parse_go_mod(
        embedded_root,
        root_archives[0]["module"],
    )
    metadata_rows.append(
        {
            "tupleId": "root",
            "tupleOrder": 0,
            "module": root_archives[0]["module"],
            "version": root_archives[0]["version"],
            "metadata": root_metadata,
            "externalModRawSha256": None,
        }
    )
    for tuple_id, pair in pairs.items():
        check(set(pair) == {"mod", "zip"}, "E_TUPLE_PAIR")
        matches = [
            row for row in archive_rows if row.get("tupleId") == tuple_id
        ]
        check(len(matches) == 1, "E_TUPLE_PAIR")
        embedded = matches[0].pop("embeddedGoMod")
        if embedded is not None:
            check(
                embedded == held.raw[pair["mod"]["path"]],
                "E_EMBEDDED_MOD_PARITY",
            )
    graph = runner.build_graph(
        archive_rows,
        metadata_rows,
        runner.profile_rows(permit),
        limits,
    )
    return graph, {
        "archiveCount": len(archive_rows),
        "aggregateEntryCount": aggregate_entries,
        "aggregateUncompressedByteCount": aggregate_uncompressed,
    }


def route_for_graph(graph: Mapping[str, Any]) -> dict[str, str]:
    check(
        graph.get("independentReproductionPassed") is True
        and graph.get("reconstructionCount") == 2,
        "E_GRAPH",
    )
    if graph.get("newTupleCount", 0) > 0:
        return {
            "route": "next_wave_required",
            "status": "combined_graph_discovery_complete_next_wave_required",
            "nextAction": (
                "prepare_separate_versioned_dependency_wave_identity_and_"
                "acquisition_decision"
            ),
        }
    if (
        graph.get("unmappedExternalImportCount", 0) > 0
        or graph.get("unresolvedDeclaredExternalImportCount", 0) > 0
    ):
        return {
            "route": "external_import_resolution_required",
            "status": (
                "combined_graph_discovery_complete_external_import_"
                "resolution_required"
            ),
            "nextAction": (
                "prepare_separate_external_import_resolution_decision"
            ),
        }
    check(graph.get("fixedPointReached") is True, "E_GRAPH")
    return {
        "route": "fixed_point_candidate",
        "status": "combined_graph_discovery_complete_fixed_point_candidate",
        "nextAction": (
            "prepare_separate_combined_fixed_point_closure_review_decision"
        ),
    }


def source_projection(bindings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "kind": row["kind"],
            "module": row["module"],
            "path": row["path"],
            "rawSha256": row["rawSha256"],
            "tupleId": row["tupleId"],
            "tupleOrder": row["tupleOrder"],
            "version": row["version"],
            "wave": row["wave"],
        }
        for row in sorted(
            bindings,
            key=lambda value: (
                value["tupleOrder"],
                value["kind"],
                value["path"],
            ),
        )
    ]


def generate_candidate(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    with PinnedRunnerFile(root) as runner_held:
        runner = load_pinned_runner(runner_held)
        with runner.HeldInputSet(root, control_bindings()) as control_held:
            documents = parse_control_documents(runner, control_held)
            validate_terminal_documents(runner, documents)
            bindings = source_bindings(runner, documents)
            with runner.HeldInputSet(root, bindings) as source_held:
                runner_held.final_barrier()
                control_held.final_barrier()
                source_held.final_barrier()
                first_graph, first_coverage = reconstruct_graph(
                    runner,
                    documents[WAVE1_PERMIT_PATH],
                    bindings,
                    source_held,
                )
                runner_held.final_barrier()
                control_held.final_barrier()
                source_held.final_barrier()
                second_graph, second_coverage = reconstruct_graph(
                    runner,
                    documents[WAVE1_PERMIT_PATH],
                    bindings,
                    source_held,
                )
                check(
                    runner.canonical_json_bytes(first_graph)
                    == runner.canonical_json_bytes(second_graph)
                    and first_coverage == second_coverage,
                    "E_REPRODUCTION",
                )
                runner_held.final_barrier()
                control_held.final_barrier()
                source_held.final_barrier()
                projection = source_projection(bindings)
                route = route_for_graph(first_graph)
                body = {
                    "documentType": (
                        "aetherlink.g2-pion-combined-wave1-wave2-"
                        "fixed-point-candidate"
                    ),
                    "schemaVersion": "1.0",
                    "checkerId": CHECKER_ID,
                    "status": route["status"],
                    "result": (
                        "combined_graph_recomputed_twice_from_exact_"
                        "wave1_and_wave2_source_bytes"
                    ),
                    "verificationOnly": True,
                    "recordModeExposed": False,
                    "inputSet": {
                        "heldSourceInputCount": 69,
                        "rootArchiveCount": 1,
                        "resourceCount": 68,
                        "modCount": 34,
                        "zipCount": 34,
                        "wave1ResourceCount": 38,
                        "wave2ResourceCount": 30,
                        "sourceBindings": projection,
                        "combinedInputSetSha256": sha256_bytes(
                            runner.canonical_json_bytes(projection)
                        ),
                        "wave1OrderedSourceSetSha256": documents[
                            WAVE1_PERMIT_PATH
                        ]["inputBindings"]["orderedSourceSetSha256"],
                        "wave2OrderedSourceSetSha256": documents[
                            WAVE2_RECEIPT_PATH
                        ]["orderedSourceSetSha256"],
                    },
                    "toolBinding": {
                        "role": "immutable_wave1_graph_provider",
                        "path": RUNNER_PATH,
                        "rawSha256": RUNNER_SHA256,
                    },
                    "terminalEvidenceBindings": [
                        {
                            "path": path,
                            "rawSha256": digest,
                        }
                        for path, digest in CONTROL_SHA256.items()
                    ],
                    "coverage": first_coverage,
                    "profiles": runner.profile_rows(
                        documents[WAVE1_PERMIT_PATH]
                    ),
                    "graphDiscovery": first_graph,
                    "checkerVerification": {
                        "fullInputReconstructionCount": 2,
                        "underlyingIndependentGraphAlgorithmCount": 4,
                        "canonicalGraphEqualityVerified": True,
                        "frontierBoundToWave2TupleRows": True,
                        "barrierBeforeReconstructionCompleted": True,
                        "barrierBetweenReconstructionsCompleted": True,
                        "barrierAfterReconstructionCompleted": True,
                        "calculatedFixedPointCandidate": first_graph[
                            "fixedPointReached"
                        ],
                    },
                    "route": route["route"],
                    "nextAction": route["nextAction"],
                    "operationCounters": {
                        "heldSourceInputCount": 69,
                        "stableReadPassesPerHeldInput": 2,
                        "fullSourceReconstructionCount": 2,
                        "archiveOpenCount": 70,
                        "archiveExtractionCount": 0,
                        "sourceExecutionCount": 0,
                        "subprocessCount": 0,
                        "networkOperationCount": 0,
                        "fileWriteCount": 0,
                    },
                    "closure": {
                        "dependencyFixedPointReached": False,
                        "dependencySourceReviewed": False,
                        "dependencyClosureComplete": False,
                        "semanticClosureComplete": False,
                        "licenseCompatibilityReviewed": False,
                        "securityReviewComplete": False,
                        "rungThreeComplete": False,
                        "candidateSelected": False,
                        "librarySelected": False,
                        "releaseReady": False,
                    },
                    "authority": {
                        "decisionAuthorityGranted": False,
                        "executionAuthorityGranted": False,
                        "acquisitionAuthorityGranted": False,
                        "publicationAuthorityGranted": False,
                        "networkAuthorized": False,
                        "sourceExecutionAuthorized": False,
                        "filesystemExtractionAuthorized": False,
                        "subprocessAuthorized": False,
                        "fileWriteAuthorized": False,
                        "gitWriteAuthorized": False,
                        "repositoryOwnerIdentityProofRequired": False,
                        "externalAuthenticationRequired": False,
                        "userActionRequired": False,
                    },
                }
                candidate = runner.content_bound(
                    body,
                    "candidate_without_contentBinding",
                )
                runner_held.final_barrier()
                control_held.final_barrier()
                source_held.final_barrier()
                return candidate


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def error_document_bytes() -> bytes:
    error = {
        "documentType": (
            "aetherlink.g2-pion-combined-wave1-wave2-"
            "fixed-point-check-error"
        ),
        "schemaVersion": "1.0",
        "status": "failed_closed_without_publication",
        "networkOperationCount": 0,
        "sourceExecutionCount": 0,
        "fileWriteCount": 0,
    }
    return (
        json.dumps(
            error,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parse_arguments(argv)
    except CliUsageFailure:
        sys.stdout.buffer.write(error_document_bytes())
        return 2
    try:
        candidate = generate_candidate(ROOT)
    except Exception:
        sys.stdout.buffer.write(error_document_bytes())
        return 1
    sys.stdout.buffer.write(
        json.dumps(
            candidate,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
