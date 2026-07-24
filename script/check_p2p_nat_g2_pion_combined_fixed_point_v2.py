#!/usr/bin/env python3
"""Recompute the bounded Wave1+Wave2+Wave3 graph without publishing.

Run only with ``python3 -I -B -S``.  This checker holds the exact v1
read-only checker and its exact graph provider, the terminal evidence, and
101 source inputs by descriptor.  It writes only one canonical candidate to
stdout.  It grants no authority and performs no network, subprocess, source
execution, extraction, authentication, or file-write operation.

The only source-inspection change from v1 is deliberately narrow: a Go file
whose relative path has an exact lowercase ``testdata`` directory component
is retained in the byte/hash/archive inventory but is not strictly decoded or
parsed for graph build expressions or imports.  The existing lossy prefix scan
for special-class telemetry still runs.  Case variants, suffix variants, test
files, examples, and tools retain the strict v1 parsing behaviour.
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
            "combined fixed-point v2 checker requires unoptimized "
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
V1_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py"
V1_CHECKER_RAW_SHA256 = (
    "b11047fd74e8ba4b41d66590975270921a5835bf444ad2e942af357d56764f15"
)
V1_PROVIDER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
V1_PROVIDER_RAW_SHA256 = (
    "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
)
CHECKER_ID = "g2-pion-ice-v4.3.0-combined-wave1-wave2-wave3-check-v2"
SOURCE_INSPECTION_POLICY = (
    "exact_lowercase_testdata_component_preparse_exclusion_v2"
)
CODE_MAXIMUM_BYTES = 4 * 1024 * 1024
JSON_MAXIMUM_BYTES = 8 * 1024 * 1024

WAVE3_IDENTITY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave3-v2.json"
)
WAVE3_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-decision-v1.json"
)
WAVE3_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "execution-permit-v1.json"
)
WAVE3_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-receipt-v1.json"
)
WAVE3_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-manifest-v1.json"
)
WAVE3_READBACK_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "readback-execution-permit-v1.json"
)
WAVE3_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-readback-v1.json"
)
WAVE3_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "readback-manifest-v1.json"
)
WAVE3_ACCEPTED_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-3-v1/accepted"
)

WAVE3_CONTROL_SHA256 = {
    WAVE3_IDENTITY_DECISION_PATH:
        "34d07a07dffe0c480f965192d8d81bc1961fd1ea2847e5ec5b0a2ca361d1c350",
    WAVE3_DECISION_PATH:
        "05ecc22e13fab8a0b213d27d17b4a728fa5bc8bebd088b2b2a7204fdedc03071",
    WAVE3_PERMIT_PATH:
        "8c3c0b56f96e856b7098d414f46294c9d587da7525222d8b2b707a730c12f657",
    WAVE3_RECEIPT_PATH:
        "c0d1c4a4c7a658418976446237e45e0f3955fcc600f8c5b82b51295313e14f18",
    WAVE3_MANIFEST_PATH:
        "7e1508a1fbd6e927377a1aeb709ffe44f484efcabe95c7fb739db42b56207552",
    WAVE3_READBACK_PERMIT_PATH:
        "079095911df26a7d7428b7edb212f832a9e840ba1eb18f8d8f1365e809180076",
    WAVE3_READBACK_PATH:
        "a8cce2871287fccf8d75a42abb472b75b0940e13faa6c7b10528c92b235aafca",
    WAVE3_READBACK_MANIFEST_PATH:
        "7a750e64465f762fa8160539b084565ba01e2ffd63cbe65b10fad477db3f961a",
}
WAVE3_CONTENT_SHA256 = {
    WAVE3_IDENTITY_DECISION_PATH:
        "83f97eeece6f5802f4b2fc807469a8abd08971cc8712a3bad415e801258d2e9f",
    WAVE3_DECISION_PATH:
        "0ae8b961c0aada02c3a10a9fae231e03baa7d23928abf5b14488d30b88c9de78",
    WAVE3_PERMIT_PATH:
        "a93ca38a634153feda1479fd93963b08811d20df90d7300c5bf9216c7cb66548",
    WAVE3_READBACK_PERMIT_PATH:
        "e0822ad22140a8a104e3f6a4a017e93dd7b8f7beb111ae2e54c56402ef3c4183",
    WAVE3_READBACK_PATH:
        "4fee6c64579133e67fb084242c335ca666267e73f87653fc8d899c78405df462",
    WAVE3_READBACK_MANIFEST_PATH:
        "067cac261cd7b6c5ba962a5ae53e77a85b0311cf7808e2a700cb25ecc38154c5",
}
WAVE3_RESOURCE_SET_SHA256 = (
    "38c6d44eb855352164d4a3360435c8b6a41b1e5e42c2898085643c0d8defdcf3"
)
WAVE3_ATTEMPT_ID = "47d76c38d865e40c7f16961c6fe8b31a"


class CombinedCheckFailure(RuntimeError):
    """A content-free, fail-closed checker error."""


class CliUsageFailure(RuntimeError):
    """An intentionally content-free command-line usage failure."""


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise CliUsageFailure("E_CLI_USAGE")


def check(condition: bool, code: str) -> None:
    if not condition:
        raise CombinedCheckFailure(code)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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


def combined_identity_barrier(
    root: Path,
    held_inputs: Sequence[Any],
) -> None:
    """Bind every held input set to the same currently named workspace root."""

    try:
        named_before = os.stat(root, follow_symlinks=False)
        check(stat.S_ISDIR(named_before.st_mode), "E_ROOT_IDENTITY")
        expected = directory_identity(named_before)
        for held in held_inputs:
            root_fd = getattr(held, "root_fd", -1)
            check(
                type(root_fd) is int
                and root_fd >= 0
                and directory_identity(os.fstat(root_fd)) == expected,
                "E_ROOT_IDENTITY",
            )
        for held in held_inputs:
            held.final_barrier()
        named_after = os.stat(root, follow_symlinks=False)
        check(
            directory_identity(named_after) == expected,
            "E_ROOT_IDENTITY",
        )
    except OSError as error:
        raise CombinedCheckFailure("E_ROOT_IDENTITY") from error


class PinnedCodeFile:
    """Open, hold, verify, and later re-check one exact Python source file."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        expected_sha256: str,
    ) -> None:
        self.relative_path = relative_path
        self.expected_sha256 = expected_sha256
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
                "E_V1_CHECKER_IDENTITY",
            )
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self._validate_directory(os.fstat(self.root_fd))
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
                and sha256_bytes(first) == self.expected_sha256,
                "E_V1_CHECKER_IDENTITY",
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
            "E_V1_CHECKER_IDENTITY",
        )

    @staticmethod
    def _validate_file(info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= CODE_MAXIMUM_BYTES,
            "E_V1_CHECKER_IDENTITY",
        )

    def _read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_V1_CHECKER_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_V1_CHECKER_IDENTITY")
        after = os.fstat(self.fd)
        check(
            file_identity(before) == file_identity(after),
            "E_V1_CHECKER_IDENTITY",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        current = os.fstat(self.fd)
        named = os.stat(
            self.name,
            dir_fd=self.parent_fd,
            follow_symlinks=False,
        )
        check(
            file_identity(current) == file_identity(self.initial)
            and file_identity(named) == file_identity(self.initial),
            "E_V1_CHECKER_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            check(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                and directory_identity(
                    os.stat(component, dir_fd=parent, follow_symlinks=False)
                )
                == directory_identity(initial),
                "E_V1_CHECKER_IDENTITY",
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

    def __enter__(self) -> "PinnedCodeFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def load_v1_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_checker_v1_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V1_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_checker_v1_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V1_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V1_CHECKER_LOAD") from error
    for name in (
        "PinnedRunnerFile",
        "load_pinned_runner",
        "control_bindings",
        "parse_control_documents",
        "validate_terminal_documents",
        "source_bindings",
        "graph_limits",
        "route_for_graph",
        "source_projection",
    ):
        check(callable(getattr(module, name, None)), "E_V1_CHECKER_API")
    check(
        module.RUNNER_PATH == V1_PROVIDER_PATH
        and module.RUNNER_SHA256 == V1_PROVIDER_RAW_SHA256,
        "E_V1_CHECKER_API",
    )
    return module


def wave3_control_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": JSON_MAXIMUM_BYTES,
            "ownerOnly": False,
            "kind": "terminal_evidence",
        }
        for path, digest in WAVE3_CONTROL_SHA256.items()
    ]


def verify_content_binding(
    runner: types.ModuleType,
    document: Mapping[str, Any],
    expected_sha256: str,
) -> None:
    binding = document.get("contentBinding")
    check(
        type(binding) is dict
        and set(binding) == {"algorithm", "sha256"}
        and binding.get("algorithm")
        == "sha256(canonical-json-without-contentBinding)"
        and binding.get("sha256") == expected_sha256,
        "E_WAVE3_CONTENT_BINDING",
    )
    without = dict(document)
    without.pop("contentBinding", None)
    check(
        sha256_bytes(runner.canonical_json_bytes(without)) == expected_sha256,
        "E_WAVE3_CONTENT_BINDING",
    )


def parse_wave3_documents(
    runner: types.ModuleType,
    held: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in WAVE3_CONTROL_SHA256:
        value = runner.strict_json(held.raw[path], path)
        check(type(value) is dict, "E_WAVE3_JSON")
        result[path] = value
    return result


def wave3_request_resources(
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    identity = documents[WAVE3_IDENTITY_DECISION_PATH]
    decision = documents[WAVE3_DECISION_PATH]
    permit = documents[WAVE3_PERMIT_PATH]
    receipt = documents[WAVE3_RECEIPT_PATH]
    manifest = documents[WAVE3_MANIFEST_PATH]
    readback_permit = documents[WAVE3_READBACK_PERMIT_PATH]
    readback = documents[WAVE3_READBACK_PATH]
    readback_manifest = documents[WAVE3_READBACK_MANIFEST_PATH]

    for path, expected in WAVE3_CONTENT_SHA256.items():
        verify_content_binding(runner, documents[path], expected)
    check(
        identity.get("status")
        == (
            "wave3_exact_16_frontier_identity_classified_16_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and identity.get("graphBinding", {}).get("newTupleCount") == 16
        and identity.get("graphBinding", {}).get("fixedPointReached") is False,
        "E_WAVE3_IDENTITY",
    )
    identity_binding = decision.get("wave3IdentityDecisionBinding")
    check(
        type(identity_binding) is dict
        and identity_binding.get("contentSha256")
        == WAVE3_CONTENT_SHA256[WAVE3_IDENTITY_DECISION_PATH]
        and any(
            type(row) is dict
            and row.get("path") == WAVE3_IDENTITY_DECISION_PATH
            and row.get("rawSha256")
            == WAVE3_CONTROL_SHA256[WAVE3_IDENTITY_DECISION_PATH]
            for row in identity_binding.get("files", [])
        ),
        "E_WAVE3_IDENTITY",
    )
    request_set = decision.get("requestSet")
    permit_contract = permit.get("requestContract")
    check(
        decision.get("status")
        == "exact_32_resource_contract_prepared_acquisition_not_authorized"
        and type(request_set) is dict
        and request_set.get("requestCount") == 32
        and request_set.get("tupleCount") == 16
        and request_set.get("resourcesPerTuple") == 2
        and request_set.get("order") == "tuple_order_ascending_mod_then_zip"
        and type(permit_contract) is dict
        and permit_contract.get("requestCount") == 32
        and permit_contract.get("resources")
        == request_set.get("resources"),
        "E_WAVE3_REQUEST",
    )
    resources = request_set["resources"]
    check(type(resources) is list and len(resources) == 32, "E_WAVE3_REQUEST")

    decision_binding = permit.get("decisionBinding")
    check(
        permit.get("status") == "authorized_not_consumed"
        and type(decision_binding) is dict
        and decision_binding.get("path") == WAVE3_DECISION_PATH
        and decision_binding.get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_DECISION_PATH]
        and decision_binding.get("contentSha256")
        == WAVE3_CONTENT_SHA256[WAVE3_DECISION_PATH],
        "E_WAVE3_PERMIT",
    )
    check(
        receipt.get("status") == "consumed_success_pending_readback"
        and receipt.get("attemptId") == WAVE3_ATTEMPT_ID
        and receipt.get("acceptedResourceCount") == 32
        and receipt.get("modCount") == 16
        and receipt.get("zipCount") == 16
        and receipt.get("aggregateResponseBytes") == 32_425_130
        and receipt.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE3_RESOURCE_SET_SHA256,
        "E_WAVE3_RECEIPT",
    )
    check(
        manifest.get("status") == "consumed_success_pending_readback"
        and manifest.get("attemptId") == WAVE3_ATTEMPT_ID
        and manifest.get("manifestWrittenLast") is True
        and manifest.get("receiptPath") == WAVE3_RECEIPT_PATH
        and manifest.get("receiptRawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_RECEIPT_PATH],
        "E_WAVE3_MANIFEST",
    )

    snapshot = readback_permit.get("frozenAcquisitionSnapshot")
    check(
        readback_permit.get("status") == "authorized_not_consumed"
        and type(snapshot) is dict
        and snapshot.get("attemptId") == WAVE3_ATTEMPT_ID
        and snapshot.get("acceptedResourceCount") == 32
        and snapshot.get("modCount") == 16
        and snapshot.get("zipCount") == 16
        and snapshot.get("aggregateAcceptedBytes") == 32_425_130
        and snapshot.get("aggregateModBytes") == 2_555
        and snapshot.get("aggregateZipBytes") == 32_422_575
        and snapshot.get("acquisitionReceipt", {}).get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_RECEIPT_PATH]
        and snapshot.get("acquisitionManifest", {}).get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_MANIFEST_PATH],
        "E_WAVE3_READBACK_PERMIT",
    )
    accepted = snapshot.get("acceptedDirectory")
    accepted_files = accepted.get("files") if type(accepted) is dict else None
    check(
        type(accepted) is dict
        and accepted.get("path") == WAVE3_ACCEPTED_DIRECTORY
        and accepted.get("exactFileCount") == 32
        and type(accepted_files) is list
        and len(accepted_files) == 32,
        "E_WAVE3_READBACK_PERMIT",
    )
    verified = readback.get("verified")
    check(
        readback.get("status") == "wave3_acquisition_independently_read_back"
        and readback.get("offline") is True
        and readback.get("externalAuthenticationRequired") is False
        and readback.get("userActionRequired") is False
        and readback.get("networkRequestAttemptCount") == 0
        and readback.get("sourceAcquisitionCount") == 0
        and readback.get("verificationPassCount") == 2
        and type(verified) is dict
        and verified.get("status") == "wave3_acquisition_independently_verified"
        and verified.get("acceptedResourceCount") == 32
        and verified.get("modCount") == 16
        and verified.get("zipCount") == 16
        and verified.get("aggregateAcceptedBytes") == 32_425_130
        and verified.get("aggregateModBytes") == 2_555
        and verified.get("aggregateZipBytes") == 32_422_575
        and verified.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE3_RESOURCE_SET_SHA256,
        "E_WAVE3_READBACK",
    )
    authority = readback.get("authorityBinding")
    manifest_authority = readback_manifest.get("authorityBinding")
    check(
        authority == manifest_authority
        and type(authority) is dict
        and authority.get("permit", {}).get("path")
        == WAVE3_READBACK_PERMIT_PATH
        and authority.get("permit", {}).get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_READBACK_PERMIT_PATH]
        and authority.get("permit", {}).get("contentSha256")
        == WAVE3_CONTENT_SHA256[WAVE3_READBACK_PERMIT_PATH],
        "E_WAVE3_READBACK",
    )
    check(
        readback_manifest.get("status")
        == "wave3_acquisition_readback_publication_complete"
        and readback_manifest.get("manifestWrittenLast") is True
        and readback_manifest.get("offline") is True
        and readback_manifest.get("externalAuthenticationRequired") is False
        and readback_manifest.get("userActionRequired") is False
        and readback_manifest.get("networkRequestAttemptCount") == 0
        and readback_manifest.get("sourceAcquisitionCount") == 0
        and readback_manifest.get("receipt", {}).get("path")
        == WAVE3_READBACK_PATH
        and readback_manifest.get("receipt", {}).get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_READBACK_PATH]
        and readback_manifest.get("receipt", {}).get("contentSha256")
        == WAVE3_CONTENT_SHA256[WAVE3_READBACK_PATH],
        "E_WAVE3_READBACK_MANIFEST",
    )

    accepted_by_name = {
        PurePosixPath(row.get("path", "")).name: row
        for row in accepted_files
        if type(row) is dict
    }
    verified_rows = verified.get("resources")
    check(
        len(accepted_by_name) == 32
        and type(verified_rows) is list
        and len(verified_rows) == 32,
        "E_WAVE3_RESOURCE",
    )
    verified_by_name = {
        row.get("acceptedFileName"): row
        for row in verified_rows
        if type(row) is dict
    }
    check(len(verified_by_name) == 32, "E_WAVE3_RESOURCE")

    result: list[dict[str, Any]] = []
    tuple_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, value in enumerate(resources, 1):
        check(
            type(value) is dict
            and value.get("requestOrdinal") == index
            and value.get("tupleOrder") == (index + 1) // 2
            and value.get("kind") == ("mod" if index % 2 else "zip")
            and type(value.get("module")) is str
            and type(value.get("version")) is str
            and type(value.get("tupleId")) is str
            and type(value.get("acceptedFileName")) is str
            and "/" not in value["acceptedFileName"],
            "E_WAVE3_RESOURCE",
        )
        accepted_row = accepted_by_name.get(value["acceptedFileName"])
        verified_row = verified_by_name.get(value["acceptedFileName"])
        check(
            type(accepted_row) is dict
            and type(verified_row) is dict
            and accepted_row.get("path")
            == f"{WAVE3_ACCEPTED_DIRECTORY}/{value['acceptedFileName']}"
            and accepted_row.get("mode") == "0600"
            and accepted_row.get("linkCount") == 1
            and type(accepted_row.get("bytes")) is int
            and accepted_row["bytes"] > 0
            and verified_row.get("requestOrdinal") == index
            and verified_row.get("tupleId") == value["tupleId"]
            and verified_row.get("kind") == value["kind"]
            and verified_row.get("url") == value["url"]
            and verified_row.get("byteCount") == accepted_row["bytes"]
            and verified_row.get("rawSha256") == accepted_row.get("rawSha256"),
            "E_WAVE3_RESOURCE",
        )
        row = {
            "wave": "wave3",
            "path": accepted_row["path"],
            "rawSha256": accepted_row["rawSha256"],
            "maximumBytes": accepted_row["bytes"],
            "ownerOnly": True,
            "kind": value["kind"],
            "module": value["module"],
            "version": value["version"],
            "tupleId": value["tupleId"],
            "tupleOrder": 34 + value["tupleOrder"],
            "order": index,
        }
        if value["kind"] == "zip":
            row["modulePrefix"] = (
                f"{runner.go_proxy_escape(value['module'])}@"
                f"{runner.go_proxy_escape(value['version'])}/"
            )
        tuple_rows[value["tupleId"]].append(row)
        result.append(row)
    check(
        len(tuple_rows) == 16
        and all(
            len(rows) == 2
            and {row["kind"] for row in rows} == {"mod", "zip"}
            and len({(row["module"], row["version"]) for row in rows}) == 1
            for rows in tuple_rows.values()
        ),
        "E_WAVE3_RESOURCE",
    )
    return result


def exact_lowercase_testdata_component(relative: str) -> bool:
    parts = relative.split("/")
    return any(part == "testdata" for part in parts[:-1])


def inspect_zip_bytes_v2(
    runner: types.ModuleType,
    raw: bytes,
    binding: Mapping[str, Any],
    limits: Mapping[str, Any],
) -> dict[str, Any]:
    """The v1 archive inspection with one pre-parse testdata exclusion."""

    tuple_id = binding.get("tupleId")
    tuple_order = binding.get("tupleOrder")
    kind = binding.get("kind")
    maximum_archive = runner.exact_int(
        limits.get("maximumArchiveBytes", runner.DEFAULT_MAXIMUM_ARCHIVE_BYTES),
        minimum=1,
    )
    runner.require(
        len(raw) <= maximum_archive and runner._eocd_exact(raw),
        "E_ARCHIVE_BOUND",
        "archive",
        tuple_id=tuple_id if type(tuple_id) is str else None,
        tuple_order=tuple_order if type(tuple_order) is int else None,
        resource_kind=kind if type(kind) is str else None,
    )
    expected_prefix = binding.get("modulePrefix")
    runner.require(
        type(expected_prefix) is str and expected_prefix.endswith("/"),
        "E_MODULE_IDENTITY",
        "archive",
    )
    max_entries = runner.exact_int(
        limits.get(
            "maximumEntriesPerArchive",
            runner.DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE,
        ),
        minimum=1,
    )
    max_file = runner.exact_int(
        limits.get(
            "maximumSingleFileBytes",
            runner.DEFAULT_MAXIMUM_ENTRY_BYTES,
        ),
        minimum=1,
    )
    entries: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    licenses: list[dict[str, Any]] = []
    special: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    names: set[str] = set()
    folded: set[str] = set()
    total_uncompressed = 0
    embedded_mod: bytes | None = None
    try:
        with runner.zipfile.ZipFile(
            runner.io.BytesIO(raw),
            mode="r",
            allowZip64=False,
        ) as archive:
            infos = archive.infolist()
            runner.require(
                0 < len(infos) <= max_entries,
                "E_ARCHIVE_BOUND",
                "archive",
            )
            runner.require(
                min(info.header_offset for info in infos) == 0,
                "E_ARCHIVE_STRUCTURE",
                "archive",
            )
            for info in infos:
                name = runner.safe_archive_name(info.filename, expected_prefix)
                relative = name[len(expected_prefix) :]
                folded_name = name.casefold()
                runner.require(
                    name not in names and folded_name not in folded,
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                names.add(name)
                folded.add(folded_name)
                runner.require(
                    not (info.flag_bits & 0x1)
                    and info.compress_type
                    in {runner.zipfile.ZIP_STORED, runner.zipfile.ZIP_DEFLATED}
                    and not runner.has_zip64_extra(info.extra),
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                mode = (info.external_attr >> 16) & 0xFFFF
                runner.require(
                    mode == 0 or stat.S_ISREG(mode),
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                runner.require(
                    0 <= info.file_size <= max_file,
                    "E_ARCHIVE_BOUND",
                    "archive",
                )
                total_uncompressed += info.file_size
                payload = archive.read(info)
                runner.require(
                    len(payload) == info.file_size,
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                row = {
                    "relativePath": relative,
                    "rawByteSize": len(payload),
                    "rawSha256": sha256_bytes(payload),
                }
                entries.append(row)
                if relative == "go.mod":
                    embedded_mod = payload
                if relative.endswith(".go"):
                    source_class = runner.source_class(relative)
                    if exact_lowercase_testdata_component(relative):
                        sources.append(
                            {
                                **row,
                                "sourceClass": source_class,
                                "buildExpression": None,
                                "imports": [],
                                "semanticParsingPerformed": False,
                                "graphExclusionReason": (
                                    "exact_lowercase_testdata_directory_"
                                    "component"
                                ),
                            }
                        )
                        exclusions.append(dict(row))
                    else:
                        try:
                            text = payload.decode("utf-8", errors="strict")
                        except UnicodeDecodeError as error:
                            raise runner.ReviewFailure(
                                "E_IMPORT_PARSE",
                                "source_inventory",
                                tuple_id=(
                                    tuple_id
                                    if type(tuple_id) is str
                                    else None
                                ),
                            ) from error
                        sources.append(
                            {
                                **row,
                                "sourceClass": source_class,
                                "buildExpression":
                                    runner.extract_build_expression(text),
                                "imports": runner.parse_go_imports(text),
                                "semanticParsingPerformed": True,
                                "graphExclusionReason": None,
                            }
                        )
                if runner.is_license_path(relative):
                    licenses.append(row)
                classes = runner.special_classes(relative, payload)
                if classes:
                    special.append({**row, "classes": classes})
    except runner.ReviewFailure as error:
        raise runner.ReviewFailure(
            error.code,
            error.phase,
            tuple_id=(
                error.tuple_id
                if error.tuple_id is not None
                else (tuple_id if type(tuple_id) is str else None)
            ),
            tuple_order=(
                error.tuple_order
                if error.tuple_order is not None
                else (tuple_order if type(tuple_order) is int else None)
            ),
            resource_kind=(
                error.resource_kind
                if error.resource_kind is not None
                else (kind if type(kind) is str else None)
            ),
            observations=error.observations,
        ) from error
    except (
        runner.zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
    ) as error:
        raise runner.ReviewFailure(
            "E_ARCHIVE_STRUCTURE",
            "archive",
            tuple_id=tuple_id if type(tuple_id) is str else None,
            tuple_order=tuple_order if type(tuple_order) is int else None,
            resource_kind=kind if type(kind) is str else None,
        ) from error
    return {
        "module": binding.get("module"),
        "version": binding.get("version"),
        "tupleId": tuple_id,
        "tupleOrder": tuple_order,
        "modulePrefix": expected_prefix,
        "entryCount": len(entries),
        "uncompressedByteCount": total_uncompressed,
        "entrySetSha256": sha256_bytes(runner.canonical_json_bytes(entries)),
        "sources": sources,
        "licenses": licenses,
        "special": special,
        "embeddedGoMod": embedded_mod,
        "testdataSemanticExclusions": exclusions,
    }


def reconstruct_graph_v2(
    runner: types.ModuleType,
    permit: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
    held: Any,
    limits: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata_rows: list[dict[str, Any]] = []
    archive_rows: list[dict[str, Any]] = []
    pairs: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    aggregate_entries = 0
    aggregate_uncompressed = 0
    go_source_files = 0
    exclusions: list[dict[str, Any]] = []
    for binding in bindings:
        kind = binding["kind"]
        if kind in {"mod", "zip"}:
            pairs[binding["tupleId"]][kind] = binding
        if kind == "mod":
            metadata_rows.append(
                {
                    "tupleId": binding["tupleId"],
                    "tupleOrder": binding["tupleOrder"],
                    "module": binding["module"],
                    "version": binding["version"],
                    "metadata": runner.parse_go_mod(
                        held.raw[binding["path"]],
                        binding["module"],
                    ),
                    "externalModRawSha256": binding["rawSha256"],
                }
            )
        elif kind in {"zip", "root_zip"}:
            archive = inspect_zip_bytes_v2(
                runner,
                held.raw[binding["path"]],
                binding,
                limits,
            )
            archive["kind"] = kind
            go_source_files += len(archive["sources"])
            for row in archive.pop("testdataSemanticExclusions"):
                exclusions.append(
                    {
                        "archivePath": binding["path"],
                        "module": binding["module"],
                        "version": binding["version"],
                        **row,
                    }
                )
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
    metadata_rows.append(
        {
            "tupleId": "root",
            "tupleOrder": 0,
            "module": root_archives[0]["module"],
            "version": root_archives[0]["version"],
            "metadata": runner.parse_go_mod(
                embedded_root,
                root_archives[0]["module"],
            ),
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
    exclusions.sort(
        key=lambda row: (
            row["archivePath"],
            row["relativePath"],
            row["rawSha256"],
        )
    )
    return graph, {
        "archiveCount": len(archive_rows),
        "aggregateEntryCount": aggregate_entries,
        "aggregateUncompressedByteCount": aggregate_uncompressed,
        "goSourceFileCount": go_source_files,
        "semanticParsedGoSourceCount": go_source_files - len(exclusions),
        "testdataSemanticExclusionCount": len(exclusions),
        "testdataSemanticExclusionSetSha256": sha256_bytes(
            runner.canonical_json_bytes(exclusions)
        ),
    }


def combined_source_bindings(
    v1: types.ModuleType,
    runner: types.ModuleType,
    v1_documents: Mapping[str, Mapping[str, Any]],
    wave3_documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    bindings = v1.source_bindings(runner, v1_documents)
    bindings.extend(
        wave3_request_resources(runner, wave3_documents)
    )
    check(
        len(bindings) == 101
        and sum(row["kind"] == "root_zip" for row in bindings) == 1
        and sum(row["kind"] == "mod" for row in bindings) == 50
        and sum(row["kind"] == "zip" for row in bindings) == 50
        and sum(row["wave"] == "wave1" for row in bindings) == 38
        and sum(row["wave"] == "wave2" for row in bindings) == 30
        and sum(row["wave"] == "wave3" for row in bindings) == 32,
        "E_COMBINED_INPUT",
    )
    check(
        len({row["path"] for row in bindings}) == 101
        and len(
            {
                (row["module"], row["version"])
                for row in bindings
                if row["kind"] != "root_zip"
            }
        )
        == 50,
        "E_COMBINED_INPUT",
    )
    pair_kinds: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in bindings:
        if row["kind"] != "root_zip":
            pair_kinds[
                (row["module"], row["version"], row["tupleOrder"])
            ].add(row["kind"])
    check(
        len(pair_kinds) == 50
        and all(kinds == {"mod", "zip"} for kinds in pair_kinds.values())
        and sorted(order for _, _, order in pair_kinds) == list(range(1, 51)),
        "E_COMBINED_INPUT",
    )
    return bindings


def generate_candidate(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    with PinnedCodeFile(
        root,
        V1_CHECKER_PATH,
        V1_CHECKER_RAW_SHA256,
    ) as v1_held:
        v1 = load_v1_checker(v1_held)
        with v1.PinnedRunnerFile(root) as provider_held:
            runner = v1.load_pinned_runner(provider_held)
            controls = v1.control_bindings() + wave3_control_bindings()
            with runner.HeldInputSet(root, controls) as control_held:
                v1_documents = v1.parse_control_documents(
                    runner,
                    control_held,
                )
                v1.validate_terminal_documents(runner, v1_documents)
                wave3_documents = parse_wave3_documents(
                    runner,
                    control_held,
                )
                bindings = combined_source_bindings(
                    v1,
                    runner,
                    v1_documents,
                    wave3_documents,
                )
                with runner.HeldInputSet(root, bindings) as source_held:
                    held_inputs = (
                        v1_held,
                        provider_held,
                        control_held,
                        source_held,
                    )
                    combined_identity_barrier(root, held_inputs)
                    limits = v1.graph_limits(runner)
                    first_graph, first_coverage = reconstruct_graph_v2(
                        runner,
                        v1_documents[v1.WAVE1_PERMIT_PATH],
                        bindings,
                        source_held,
                        limits,
                    )
                    combined_identity_barrier(root, held_inputs)
                    second_graph, second_coverage = reconstruct_graph_v2(
                        runner,
                        v1_documents[v1.WAVE1_PERMIT_PATH],
                        bindings,
                        source_held,
                        limits,
                    )
                    check(
                        runner.canonical_json_bytes(first_graph)
                        == runner.canonical_json_bytes(second_graph)
                        and first_coverage == second_coverage,
                        "E_REPRODUCTION",
                    )
                    combined_identity_barrier(root, held_inputs)
                    projection = v1.source_projection(bindings)
                    route = v1.route_for_graph(first_graph)
                    fixed_point = first_graph["fixedPointReached"]
                    body = {
                        "documentType": (
                            "aetherlink.g2-pion-combined-wave1-wave2-"
                            "wave3-fixed-point-candidate"
                        ),
                        "schemaVersion": "2.0",
                        "checkerId": CHECKER_ID,
                        "status": route["status"],
                        "result": (
                            "combined_graph_recomputed_twice_from_exact_"
                            "wave1_wave2_and_wave3_source_bytes"
                        ),
                        "verificationOnly": True,
                        "recordModeExposed": False,
                        "sourceInspectionPolicy": {
                            "policyId": SOURCE_INSPECTION_POLICY,
                            "exactLowercaseTestdataDirectoryExcludedBeforeParsing":
                                True,
                            "excludedBytesRemainInArchiveInventory": True,
                            "caseVariantsExcludedBeforeParsing": False,
                            "testFilesExcludedBeforeParsing": False,
                            "exampleDirectoriesExcludedBeforeParsing": False,
                            "toolDirectoriesExcludedBeforeParsing": False,
                        },
                        "inputSet": {
                            "heldSourceInputCount": 101,
                            "rootArchiveCount": 1,
                            "resourceCount": 100,
                            "modCount": 50,
                            "zipCount": 50,
                            "wave1ResourceCount": 38,
                            "wave2ResourceCount": 30,
                            "wave3ResourceCount": 32,
                            "uniqueModuleVersionTupleCount": 50,
                            "aggregateRawByteSize": sum(
                                row["maximumBytes"] for row in bindings
                            ),
                            "sourceBindings": projection,
                            "combinedInputSetSha256": sha256_bytes(
                                runner.canonical_json_bytes(projection)
                            ),
                            "wave1OrderedSourceSetSha256": v1_documents[
                                v1.WAVE1_PERMIT_PATH
                            ]["inputBindings"]["orderedSourceSetSha256"],
                            "wave2OrderedSourceSetSha256": v1_documents[
                                v1.WAVE2_RECEIPT_PATH
                            ]["orderedSourceSetSha256"],
                            "wave3AcceptedResourceSetSha256":
                                WAVE3_RESOURCE_SET_SHA256,
                        },
                        "toolBindings": [
                            {
                                "role": "immutable_v1_combined_checker",
                                "path": V1_CHECKER_PATH,
                                "rawSha256": V1_CHECKER_RAW_SHA256,
                            },
                            {
                                "role": "immutable_wave1_graph_provider",
                                "path": V1_PROVIDER_PATH,
                                "rawSha256": V1_PROVIDER_RAW_SHA256,
                            },
                        ],
                        "terminalEvidenceBindings": [
                            {
                                "path": row["path"],
                                "rawSha256": row["rawSha256"],
                            }
                            for row in controls
                        ],
                        "coverage": first_coverage,
                        "profiles": runner.profile_rows(
                            v1_documents[v1.WAVE1_PERMIT_PATH]
                        ),
                        "graphDiscovery": first_graph,
                        "checkerVerification": {
                            "fullInputReconstructionCount": 2,
                            "underlyingIndependentGraphAlgorithmCount": 4,
                            "canonicalGraphEqualityVerified": True,
                            "barrierBeforeReconstructionCompleted": True,
                            "barrierBetweenReconstructionsCompleted": True,
                            "barrierAfterReconstructionCompleted": True,
                            "workspaceRootIdentityBoundAcrossAllInputs": True,
                            "calculatedFixedPointCandidate": fixed_point,
                        },
                        "route": route["route"],
                        "nextAction": route["nextAction"],
                        "operationCounters": {
                            "heldSourceInputCount": 101,
                            "heldTerminalEvidenceCount": len(controls),
                            "heldToolInputCount": 2,
                            "stableReadPassesPerHeldInput": 2,
                            "fullSourceReconstructionCount": 2,
                            "archiveOpenCount": 102,
                            "archiveExtractionCount": 0,
                            "sourceExecutionCount": 0,
                            "subprocessCount": 0,
                            "networkOperationCount": 0,
                            "fileWriteCount": 0,
                        },
                        "closure": {
                            "dependencyFixedPointReached": fixed_point,
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
                            "passwordRequired": False,
                            "privateKeyRequired": False,
                            "signatureRequired": False,
                            "tokenRequired": False,
                            "userActionRequired": False,
                        },
                    }
                    candidate = runner.content_bound(
                        body,
                        "candidate_without_contentBinding",
                    )
                    combined_identity_barrier(root, held_inputs)
                    return candidate


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def error_document_bytes() -> bytes:
    return (
        json.dumps(
            {
                "documentType": (
                    "aetherlink.g2-pion-combined-wave1-wave2-wave3-"
                    "fixed-point-check-error"
                ),
                "schemaVersion": "2.0",
                "status": "failed_closed_without_publication",
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
                "networkOperationCount": 0,
                "sourceExecutionCount": 0,
                "fileWriteCount": 0,
            },
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
