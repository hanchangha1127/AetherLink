#!/usr/bin/env python3
"""Validate the decision-only replacement recovery selection v3."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("v3 decision checker requires `python3 -I -B -S`")

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v3.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v3.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v3.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v3.py"
)
V2_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-execution-permit-v2.json"
)
V2_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-execution-permit-v2.md"
)
V2_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v2.py"
)
V2_CHECKER_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v2.py"
)
V2_RECORDER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "success_v1_recovery_v2.py"
)
V2_RECORDER_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "success_v1_recovery_v2.py"
)
V2_EXPECTED_RAW = {
    V2_PERMIT_PATH: (
        "b8a56f364887e2b2699f4dc93c1718d73dad992ee680c963843229edb7f7ff2a"
    ),
    V2_READER_PATH: (
        "1604eaa5ac1f95c0f7208b4d0eab47daa8ae25d11c18c99cf4adc8951813594f"
    ),
    V2_CHECKER_PATH: (
        "0dbee20b227c685c14d27178173a01eeab365579066ea904c1fea87c3c941fac"
    ),
    V2_CHECKER_TESTS_PATH: (
        "d3090cd1bddf3663baf0c033296433be41d29617c1b2abebac883da07416cbd6"
    ),
    V2_RECORDER_PATH: (
        "219a27581d99469f2d978ae7ca8043823f01699c24d48ec2d2574ace12718c3a"
    ),
    V2_RECORDER_TESTS_PATH: (
        "f61d771f39e6c55909a847fff347440c6984c114993c4e4131b5e4fcf86e5467"
    ),
}
V2_EXPECTED_CONTENT = (
    "a2f0a5dd0b761834758ec8ed2d309e7654518926e4df604f04513b506996680c"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
V3_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.combined-fixed-point-readback-v3.claim"
V3_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-readback-v3.json"
)
V3_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-failure-v3.json"
)
V3_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-manifest-v3.json"
)
V3_OUTPUT_PATHS = (
    V3_CLAIM_PATH,
    V3_RECEIPT_PATH,
    V3_FAILURE_PATH,
    V3_MANIFEST_PATH,
)
V3_STAGING_PREFIX = ".combined-fixed-point-readback-v3-staging-"
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-fixed-point-"
    "readback-recovery-decision-v3"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024

READER_BYTES = b"""# Combined fixed-point replacement recovery decision v3

This decision selects a replacement recovery path after the v2 diagnostic
readback authority was closed as consumed or uncertain. It does not authorize
a permit, recording, execution, archive-member decode, writes, network use,
source execution, subprocesses, Git, devices, deployment, authentication,
credentials, signatures, or user action.

The original 69-source and consumed-success terminal evidence remains frozen.
All v2 and prospective v3 readback outputs must remain absent. The only next
action is to prepare a separate v3 one-use execution-permit package.
"""


class DecisionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(value: bool, code: str) -> None:
    if not value:
        raise DecisionError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "E_JSON")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(
                DecisionError("E_JSON")
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                DecisionError("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def bootstrap_read(path: str, expected: str) -> bytes:
    current = ROOT
    for component in path.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_BOOTSTRAP",
        )
    fd = os.open(
        ROOT / path,
        os.O_RDONLY
        | os.O_NOFOLLOW
        | os.O_NONBLOCK
        | os.O_CLOEXEC,
    )
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_BOOTSTRAP",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_BOOTSTRAP")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_BOOTSTRAP")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        require(
            (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_nlink,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_nlink,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            and sha256(raw) == expected,
            "E_BOOTSTRAP",
        )
        return raw
    finally:
        os.close(fd)


def execute_module(name: str, path: str, raw: bytes) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / path),
            "__loader__": None,
            "__name__": name,
            "__package__": None,
        }
    )
    try:
        exec(
            compile(raw, path, "exec", dont_inherit=True, optimize=0),
            module.__dict__,
            module.__dict__,
        )
    except Exception as error:
        raise DecisionError("E_BOOTSTRAP") from error
    return module


V2 = execute_module(
    "combined_readback_v2_closure_frozen",
    V2_CHECKER_PATH,
    bootstrap_read(V2_CHECKER_PATH, V2_EXPECTED_RAW[V2_CHECKER_PATH]),
)


def v3_package_bindings(include_decision: bool) -> list[dict[str, Any]]:
    paths = [READER_PATH, THIS_CHECKER_PATH, THIS_TESTS_PATH]
    if include_decision:
        paths.append(DECISION_PATH)
    return [
        {
            "path": path,
            "maximumBytes": (
                MAXIMUM_JSON_BYTES if path.startswith("docs/") else MAXIMUM_TOOL_BYTES
            ),
            "ownerOnly": False,
        }
        for path in paths
    ]


def v2_closure_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": (
                MAXIMUM_JSON_BYTES if path.startswith("docs/") else MAXIMUM_TOOL_BYTES
            ),
            "ownerOnly": False,
        }
        for path, digest in V2_EXPECTED_RAW.items()
    ]


class DecisionContext:
    def __init__(self, root: Path, *, include_decision: bool) -> None:
        self.root = root
        self.authority = None
        self.v2_closure = None
        self.package = None
        try:
            self.authority = V2.ExecutionAuthorityContext(
                root,
                include_permit=True,
                phase="recordable",
            )
            self.v2_closure = self.authority.decision_checker.HeldSet(
                root,
                v2_closure_bindings(),
            )
            self.package = self.authority.decision_checker.HeldSet(
                root,
                v3_package_bindings(include_decision),
            )
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def require_namespace(self) -> None:
        self.authority.final_barrier("recordable")
        namespace = self.authority.namespace
        for path in V3_OUTPUT_PATHS:
            require(
                V2.RECOVERY.absent_from_held_namespace(namespace, path),
                "E_NAMESPACE",
            )
        names = V2.RECOVERY.held_dependency_names(namespace)
        require(
            not any(name.startswith(V3_STAGING_PREFIX) for name in names),
            "E_NAMESPACE",
        )
        self.authority.final_barrier("recordable")

    def final_barrier(self) -> None:
        require(
            self.authority is not None
            and self.v2_closure is not None
            and self.package is not None,
            "E_CONTEXT",
        )
        self.require_namespace()
        self.v2_closure.final_barrier()
        self.package.final_barrier()
        self.authority.final_barrier("recordable")

    def close(self) -> None:
        if self.package is not None:
            self.package.close()
        if self.v2_closure is not None:
            self.v2_closure.close()
        if self.authority is not None:
            self.authority.close()


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def expected_payload(context: DecisionContext) -> dict[str, Any]:
    package = context.package.raw
    require(package[READER_PATH] == READER_BYTES, "E_READER")
    v2_raw = context.v2_closure.raw[V2_PERMIT_PATH]
    v2_document = strict_json(v2_raw)
    require(
        v2_document["contentBinding"]["sha256"] == V2_EXPECTED_CONTENT
        and v2_document["status"]
        == "diagnostic_readback_authority_consumed_or_uncertain"
        and v2_document["nextAction"]
        == "prepare_separate_v3_recovery_decision_and_one_use_permit",
        "E_V2_CLOSURE",
    )
    authority = context.authority
    payload = {
        "documentType": (
            "aetherlink.g2-pion-combined-fixed-point-"
            "readback-recovery-decision"
        ),
        "schemaVersion": "3.0",
        "decisionId": DECISION_ID,
        "recordedDate": "2026-07-24",
        "status": "replacement_recovery_selected_execution_not_authorized",
        "result": "replacement_recovery_selected_execution_not_authorized",
        "v2RecoveryDecisionBinding": {
            "contentSha256": V2.EXPECTED_RECOVERY_CONTENT,
            "files": [
                {
                    "path": path,
                    "rawSha256": digest,
                }
                for path, digest in (
                    (
                        V2.RECOVERY_DECISION_PATH,
                        V2.EXPECTED_RECOVERY_RAW,
                    ),
                    (
                        V2.RECOVERY_READER_PATH,
                        V2.EXPECTED_RECOVERY_READER_RAW,
                    ),
                    (
                        V2.RECOVERY_CHECKER_PATH,
                        V2.EXPECTED_RECOVERY_CHECKER_RAW,
                    ),
                    (
                        V2.RECOVERY_TESTS_PATH,
                        V2.EXPECTED_RECOVERY_TESTS_RAW,
                    ),
                )
            ],
        },
        "v2ClosureBinding": {
            "permitContentSha256": V2_EXPECTED_CONTENT,
            "status": v2_document["status"],
            "authorityConsumptionState": v2_document[
                "priorDraftDiagnosticObservation"
            ]["authorityConsumptionState"],
            "files": [
                {"path": path, "rawSha256": V2_EXPECTED_RAW[path]}
                for path in V2_EXPECTED_RAW
            ],
        },
        "historicalDraftObservation": v2_document[
            "priorDraftDiagnosticObservation"
        ],
        "originalEvidenceBinding": {
            "heldSourceInputCount": 69,
            "decisionId": authority.decision["decisionId"],
            "decisionContentSha256": authority.decision[
                "contentBinding"
            ]["sha256"],
            "originalPermitId": authority.original_permit["permitId"],
            "originalPermitContentSha256": authority.original_permit[
                "contentBinding"
            ]["sha256"],
            "decisionHeldBindingSetSha256": (
                V2.RECOVERY.EXPECTED_HELD_BINDING_SET_SHA256
            ),
            "candidateSourceProjectionSha256": (
                V2.RECOVERY.EXPECTED_CANDIDATE_PROJECTION_SHA256
            ),
            "claimRawSha256": V2.RECOVERY.EXPECTED_CLAIM_RAW_SHA256,
            "resultRawSha256": V2.RECOVERY.EXPECTED_RESULT_RAW_SHA256,
            "resultContentSha256": (
                V2.RECOVERY.EXPECTED_RESULT_CONTENT_SHA256
            ),
            "manifestRawSha256": V2.RECOVERY.EXPECTED_MANIFEST_RAW_SHA256,
            "graphSha256": V2.RECOVERY.EXPECTED_GRAPH_SHA256,
            "newTupleCount": 16,
            "fixedPointReached": False,
        },
        "currentNamespace": {
            "v1ReadbackClaimPresent": False,
            "v1ReadbackReceiptPresent": False,
            "v1ReadbackFailurePresent": False,
            "v1ReadbackManifestPresent": False,
            "v2ClaimPresent": False,
            "v2ReceiptPresent": False,
            "v2FailurePresent": False,
            "v2ManifestPresent": False,
            "v3ClaimPresent": False,
            "v3ReceiptPresent": False,
            "v3FailurePresent": False,
            "v3ManifestPresent": False,
            "v1V2V3StagingPresent": False,
        },
        "toolBindings": {
            "reader": {
                "path": READER_PATH,
                "rawSha256": sha256(package[READER_PATH]),
            },
            "checker": {
                "path": THIS_CHECKER_PATH,
                "rawSha256": sha256(package[THIS_CHECKER_PATH]),
            },
            "tests": {
                "path": THIS_TESTS_PATH,
                "rawSha256": sha256(package[THIS_TESTS_PATH]),
            },
        },
        "authority": {
            "permitPreparationAuthorized": False,
            "readbackRecordingAuthorized": False,
            "executionAuthorized": False,
            "archiveMemberDecodeAuthorized": False,
            "fileWriteAuthorized": False,
            "networkAuthorized": False,
            "gitWriteAuthorized": False,
            "sourceExecutionAuthorized": False,
            "subprocessAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        },
        "nextAction": "prepare_separate_v3_one_use_execution_permit_package",
    }
    return payload


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    context = DecisionContext(ROOT, include_decision=verify_disk)
    try:
        expected = content_bound(expected_payload(context))
        if verify_disk:
            raw = context.package.raw[DECISION_PATH]
            actual = strict_json(raw)
            require(
                raw == canonical_bytes(actual) and actual == expected,
                "E_DECISION",
            )
        context.final_barrier()
        return expected, {
            "documentType": (
                "aetherlink.g2-pion-combined-fixed-point-"
                "readback-recovery-decision-v3-check"
            ),
            "schemaVersion": "3.0",
            "status": "validated_replacement_selected_execution_not_authorized",
            "validationPassed": True,
            "heldSourceInputCount": 69,
            "readbackRecordingAuthorized": False,
            "executionAuthorized": False,
            "archiveMemberDecodeCount": 0,
            "fileWriteCount": 0,
            "networkUsed": False,
            "sourceExecutionUsed": False,
            "subprocessCount": 0,
            "gitWriteAuthorized": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        context.close()


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise DecisionError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        parser.add_argument("--print-expected", action="store_true")
        args = parser.parse_args(argv)
        if args.print_expected:
            expected, _ = evaluate(False)
            sys.stdout.buffer.write(canonical_bytes(expected))
        else:
            _, summary = evaluate(True)
            sys.stdout.buffer.write(canonical_bytes(summary))
        return 0
    except DecisionError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.g2-pion-combined-fixed-point-"
                        "readback-recovery-decision-v3-error"
                    ),
                    "schemaVersion": "3.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "readbackRecordingAuthorized": False,
                    "executionAuthorized": False,
                    "archiveMemberDecodeCount": 0,
                    "fileWriteCount": 0,
                    "networkUsed": False,
                    "sourceExecutionUsed": False,
                    "subprocessCount": 0,
                    "gitWriteAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.g2-pion-combined-fixed-point-"
                        "readback-recovery-decision-v3-error"
                    ),
                    "schemaVersion": "3.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "readbackRecordingAuthorized": False,
                    "executionAuthorized": False,
                    "archiveMemberDecodeCount": 0,
                    "fileWriteCount": 0,
                    "networkUsed": False,
                    "sourceExecutionUsed": False,
                    "subprocessCount": 0,
                    "gitWriteAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
