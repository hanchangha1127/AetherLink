#!/usr/bin/env python3
"""Validate the Wave2 v1 preclaim failure and selected v2 recovery design."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
COMMON_PATH = "script/p2p_nat_g2_pion_dependency_wave2_common_v1.py"
V1_PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave2_execution_permit_v1.py"
)
RECOVERY_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-"
    "recovery-decision-v1.json"
)
RECOVERY_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-"
    "recovery-decision-v1.md"
)
EXPECTED_COMMON_RAW_SHA256 = (
    "dc25ddd3a82789bddccbd6ec57a71edc389225e003d7a73e6d371a640937f8c1"
)
EXPECTED_RECOVERY_RAW_SHA256 = (
    "97be9c7a3aa5e7ab58ea4eada5f5f5d6193a14cc0fb71208bafdf16ba4e7523f"
)
EXPECTED_RECOVERY_READER_RAW_SHA256 = (
    "2e4375b464b5a04aa25659c15be082f75b202a54afe6799d7896b553417e1eef"
)
EXPECTED_RECOVERY_CONTENT_SHA256 = (
    "9dae2cec0af345138ba58bd679f71f79c74a496ab5edc63385f8dff32e8ee4d6"
)
EXPECTED_V1_PERMIT_CHECKER_RAW_SHA256 = (
    "608cc5c067f1f48b95cfcfe69a5deb8a0a67c527bbfe8e2b844da47b048df7d4"
)
V1_REVOCATION_SENTINEL_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-2-v1-staging-revoked-by-recovery-v1"
)
EXPECTED_V1_REVOCATION_SENTINEL_RAW_SHA256 = (
    "4a45a0ebf75f5fda5bcfbfc7f6862030f23bca5ece0088c2d12b0ec11d2e081c"
)
EXPECTED_STATUS = (
    "wave2_v1_preclaim_root_identity_schema_mismatch_"
    "v2_recovery_selected_execution_not_authorized"
)
EXPECTED_RESULT = (
    "v1_abandoned_preclaim_zero_requests_"
    "v2_exact_root_identity_adapter_selected"
)
EXPECTED_NEXT_ACTION = (
    "prepare_separate_wave2_v2_runner_readback_tests_and_execution_permit"
)

V1_BINDINGS: tuple[dict[str, Any], ...] = (
    {
        "path": (
            f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
            "decision-wave2-v1.json"
        ),
        "rawSha256": (
            "e10a4b41f0dc9ab9bc13b07f6b9e238e146316a7a4846af5b22f3a57fe0cd1a1"
        ),
        "maximumBytes": 2 * 1024 * 1024,
    },
    {
        "path": (
            f"{BASE}/bounded-dependency-source-acquisition-wave2-"
            "execution-permit-v1.json"
        ),
        "rawSha256": (
            "a452c9df404e8e1d8c4049e1aa5a3307d8bf9dedf46ae58cfa570a9a89dde108"
        ),
        "maximumBytes": 2 * 1024 * 1024,
    },
    {
        "path": COMMON_PATH,
        "rawSha256": EXPECTED_COMMON_RAW_SHA256,
        "maximumBytes": 4 * 1024 * 1024,
    },
    {
        "path": V1_PERMIT_CHECKER_PATH,
        "rawSha256": EXPECTED_V1_PERMIT_CHECKER_RAW_SHA256,
        "maximumBytes": 4 * 1024 * 1024,
    },
    {
        "path": V1_REVOCATION_SENTINEL_PATH,
        "rawSha256": EXPECTED_V1_REVOCATION_SENTINEL_RAW_SHA256,
        "maximumBytes": 64 * 1024,
        "ownerOnly": True,
    },
    {
        "path": "script/acquire_p2p_nat_g2_pion_dependency_wave2_v1_once.py",
        "rawSha256": (
            "4f321463cc8bc887524a4acfc43f3fbc5de6e5c02d3b79fcc34a3112a3e16f23"
        ),
        "maximumBytes": 4 * 1024 * 1024,
    },
    {
        "path": "script/check_p2p_nat_g2_pion_dependency_wave2_success_v1.py",
        "rawSha256": (
            "ba46de1f9392714887876eccca9f084a4efd8e0d495af3eb36945b4c542ced84"
        ),
        "maximumBytes": 4 * 1024 * 1024,
    },
    {
        "path": RECOVERY_PATH,
        "rawSha256": EXPECTED_RECOVERY_RAW_SHA256,
        "maximumBytes": 2 * 1024 * 1024,
    },
    {
        "path": RECOVERY_READER_PATH,
        "rawSha256": EXPECTED_RECOVERY_READER_RAW_SHA256,
        "maximumBytes": 2 * 1024 * 1024,
    },
)

V1_TERMINAL_PATHS: tuple[str, ...] = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-2-v1.claim",
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-2-v1",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-receipt-v1.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-failure-v1.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-manifest-v1.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-v1.json",
    (
        f"{BASE}/bounded-dependency-source-acquisition-wave2-"
        "readback-manifest-v1.json"
    ),
)
V2_TERMINAL_PATHS: tuple[str, ...] = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-2-v2.claim",
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-2-v2",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-receipt-v2.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-failure-v2.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-manifest-v2.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-v2.json",
    (
        f"{BASE}/bounded-dependency-source-acquisition-wave2-"
        "readback-manifest-v2.json"
    ),
)


def bootstrap_read(relative: str, expected_sha256: str) -> bytes:
    path = ROOT / relative
    current = ROOT
    for component in relative.split("/")[:-1]:
        current /= component
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
    fd = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid not in {0, os.geteuid()}
            or stat.S_IMODE(before.st_mode) & 0o022
            or before.st_size > 4 * 1024 * 1024
        ):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                raise RuntimeError("E_BOOTSTRAP_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        if (
            os.read(fd, 1) != b""
            or hashlib.sha256(raw).hexdigest() != expected_sha256
            or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
        ):
            raise RuntimeError("E_BOOTSTRAP_IDENTITY")
        return raw
    finally:
        os.close(fd)


def execute_module(
    name: str,
    relative: str,
    raw: bytes,
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__file__": str(ROOT / relative),
            "__cached__": None,
            "__loader__": None,
            "__package__": None,
        }
    )
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(
            compile(raw, relative, "exec", dont_inherit=True, optimize=0),
            module.__dict__,
            module.__dict__,
        )
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


COMMON = execute_module(
    "g2_wave2_recovery_v1_common_trust_root",
    COMMON_PATH,
    bootstrap_read(COMMON_PATH, EXPECTED_COMMON_RAW_SHA256),
)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise COMMON.Wave2Failure(code, "preflight")


def path_absent(root: Path, relative: str) -> bool:
    try:
        os.lstat(root / relative)
    except FileNotFoundError:
        return True
    except OSError as error:
        raise COMMON.Wave2Failure("E_NAMESPACE", "preflight") from error
    return False


def validate_recovery_document(document: Mapping[str, Any]) -> None:
    require(
        type(document) is dict
        and document.get("documentType")
        == "aetherlink.g2-pion-dependency-wave2-recovery-decision"
        and document.get("schemaVersion") == "1.0"
        and document.get("decisionId")
        == "g2-pion-ice-v4.3.0-rung3-dependency-wave2-recovery-decision-v1"
        and document.get("status") == EXPECTED_STATUS
        and document.get("result") == EXPECTED_RESULT
        and document.get("nextAction") == EXPECTED_NEXT_ACTION,
        "E_RECOVERY_STATE",
    )
    COMMON.validate_content_binding(
        document,
        scope="decision_without_contentBinding",
        expected=EXPECTED_RECOVERY_CONTENT_SHA256,
    )
    observed = document.get("observedV1State")
    require(
        type(observed) is dict
        and observed.get("claimCreated") is False
        and observed.get("networkRequestAttemptCount") == 0
        and observed.get("responseBodyCompletedCount") == 0
        and observed.get("validatedAndStagedResourceCount") == 0
        and observed.get("validatedAndStagedTupleCount") == 0
        and observed.get("failureReceiptCreated") is False
        and observed.get("successReceiptCreated") is False
        and observed.get("manifestCreated") is False
        and observed.get("finalDirectoryCreated") is False
        and observed.get("permitConsumed") is False
        and observed.get("v1Disposition")
        == "abandoned_preclaim_do_not_reexecute"
        and observed.get("technicalExecutionBlocked") is True
        and observed.get("revocationSentinelCreated") is True,
        "E_V1_STATE",
    )
    cause = document.get("rootCause")
    require(
        type(cause) is dict
        and cause.get("category")
        == "repository_root_identity_schema_adapter_missing"
        and cause.get("permitCheckerSchema")
        == ["device", "inode", "uid", "mode"]
        and cause.get("legacyPrimitiveSchema")
        == ["device", "inode", "ownerUid", "mode"]
        and cause.get("runnerPassedProducerObjectWithoutAdapter") is True
        and cause.get("readbackHadSameLatentMismatch") is True
        and cause.get("authenticationRelated") is False
        and cause.get("networkRelated") is False,
        "E_ROOT_CAUSE",
    )
    policy = document.get("selectedV2Policy")
    require(
        type(policy) is dict
        and policy.get("tupleSetReusedExactly") is True
        and policy.get("tupleCount") == 15
        and policy.get("orderedRequestCount") == 30
        and policy.get("freshNamespaceRequired") is True
        and policy.get("singleExactRootIdentityAdapterRequired") is True
        and policy.get("runnerAndReadbackMustUseAdapter") is True
        and policy.get("actualRootOpenCloseCompatibilityGateRequired") is True
        and policy.get("boundedLegacyRootFailureCodePreserved") is True
        and policy.get("v1RevocationSentinelRequiredAndRetained") is True
        and policy.get("v2AcquisitionAuthorizedByThisDecision") is False,
        "E_V2_POLICY",
    )
    preservation = document.get("v1PreservationContract")
    require(
        type(preservation) is dict
        and all(value is False for value in preservation.values()),
        "E_V1_PRESERVATION",
    )
    revocation = document.get("v1RevocationContract")
    require(
        type(revocation) is dict
        and revocation.get("path") == V1_REVOCATION_SENTINEL_PATH
        and revocation.get("rawSha256")
        == EXPECTED_V1_REVOCATION_SENTINEL_RAW_SHA256
        and revocation.get("fileMode") == "0600"
        and revocation.get("linkCount") == 1
        and revocation.get("v1StagingPrefixCollisionRequired") is True
        and revocation.get("v1CleanPreflightMustFailWith")
        == "E_NAMESPACE_STAGING"
        and revocation.get("v1ClaimOrFailureArtifact") is False
        and revocation.get("retainedByV2AuthorityInputs") is True
        and revocation.get("automaticRetryAllowed") is False,
        "E_V1_REVOCATION",
    )
    boundary = document.get("personalProjectBoundary")
    require(
        type(boundary) is dict
        and boundary.get("projectOwnership") == "personal_single_owner"
        and boundary.get("repositoryOwnerIdentityProofRequired") is False
        and boundary.get("externalAuthenticationRequired") is False
        and boundary.get("userActionRequired") is False,
        "E_PERSONAL_PROJECT_BOUNDARY",
    )


def validate_repository(
    root: Path = ROOT,
    *,
    require_v2_clean: bool = True,
) -> dict[str, Any]:
    global ROOT
    ROOT = root.resolve()
    require(sys.flags.isolated == 1 and sys.dont_write_bytecode, "E_INTERPRETER")
    bindings = list(V1_BINDINGS)
    seen = {row["path"] for row in bindings}
    for row in COMMON.decision_bindings() + COMMON.primitive_bindings():
        if row["path"] not in seen:
            bindings.append(row)
            seen.add(row["path"])
    inputs = COMMON.HeldInputSet(ROOT, bindings)
    root_fd = -1
    try:
        recovery = COMMON.strict_json(inputs.raw(RECOVERY_PATH), RECOVERY_PATH)
        validate_recovery_document(recovery)
        require(
            all(path_absent(ROOT, path) for path in V1_TERMINAL_PATHS),
            "E_V1_NAMESPACE",
        )
        if require_v2_clean:
            require(
                all(path_absent(ROOT, path) for path in V2_TERMINAL_PATHS),
                "E_V2_NAMESPACE",
            )
        v1_checker = COMMON.execute_fixed_module(
            "g2_wave2_recovery_v1_permit_checker",
            V1_PERMIT_CHECKER_PATH,
            inputs.raw(V1_PERMIT_CHECKER_PATH),
            ROOT,
        )
        checked = v1_checker.validate_repository(
            ROOT,
            require_clean_namespace=False,
        )
        identity = checked.get("repositoryRootIdentity")
        require(
            type(identity) is dict
            and set(identity) == {"device", "inode", "uid", "mode"},
            "E_PRODUCER_SCHEMA",
        )
        legacy, _ = COMMON.configure_primitives(inputs, ROOT)
        try:
            legacy.open_root_directory(identity)
        except legacy.AcquisitionFailure as failure:
            require(
                failure.code == "E_FILESYSTEM_ROOT_IDENTITY",
                "E_ROOT_CAUSE_REPRODUCTION",
            )
        else:
            raise COMMON.Wave2Failure(
                "E_ROOT_CAUSE_NOT_REPRODUCED",
                "preflight",
            )
        adapted = {
            "device": identity["device"],
            "inode": identity["inode"],
            "ownerUid": identity["uid"],
            "mode": identity["mode"],
        }
        root_fd = legacy.open_root_directory(adapted)
        sentinel = COMMON.strict_json(
            inputs.raw(V1_REVOCATION_SENTINEL_PATH),
            V1_REVOCATION_SENTINEL_PATH,
        )
        require(
            sentinel
            == {
                "automaticRetryAllowed": False,
                "documentType": (
                    "aetherlink.g2-pion-dependency-wave2-v1-"
                    "revocation-sentinel"
                ),
                "networkAuthority": False,
                "permitContentSha256": (
                    "9713aeed187cfa62d37894a3e7a437d415ce39e1a4cbb0bc"
                    "fc36eff7acf7c8fe"
                ),
                "permitId": (
                    "g2-pion-ice-v4.3.0-rung3-dependency-wave2-"
                    "execution-permit-v1"
                ),
                "permitRawSha256": (
                    "a452c9df404e8e1d8c4049e1aa5a3307d8bf9dedf46ae58c"
                    "fa570a9a89dde108"
                ),
                "reason": (
                    "abandoned_preclaim_repository_root_identity_"
                    "schema_mismatch"
                ),
                "replacementNamespace": "wave-2-v2",
                "schemaVersion": "1.0",
                "status": "revoked_preclaim",
                "userActionRequired": False,
            },
            "E_V1_REVOCATION",
        )
        dependency_parent = ROOT / "build/offline-source/pion-ice-v4.3.0/dependencies"
        require(
            sorted(
                name
                for name in os.listdir(dependency_parent)
                if name.startswith(".wave-2-v1-staging-")
            )
            == [Path(V1_REVOCATION_SENTINEL_PATH).name],
            "E_V1_REVOCATION",
        )
        try:
            COMMON.require_clean_namespace(ROOT)
        except COMMON.Wave2Failure as failure:
            require(
                failure.code == "E_NAMESPACE_STAGING",
                "E_V1_REVOCATION",
            )
        else:
            raise COMMON.Wave2Failure(
                "E_V1_EXECUTION_NOT_BLOCKED",
                "preflight",
            )
        inputs.final_barrier()
        require(
            all(path_absent(ROOT, path) for path in V1_TERMINAL_PATHS),
            "E_V1_NAMESPACE",
        )
        if require_v2_clean:
            require(
                all(path_absent(ROOT, path) for path in V2_TERMINAL_PATHS),
                "E_V2_NAMESPACE",
            )
        return {
            "status": recovery["status"],
            "result": recovery["result"],
            "rootCauseReproduced": True,
            "adaptedRootOpenClosePassed": True,
            "v1ClaimPresent": False,
            "v1NetworkRequestAttemptCount": 0,
            "v1PermitConsumed": False,
            "v1RetryAuthorized": False,
            "v1TechnicalExecutionBlocked": True,
            "v1RevocationSentinelRetained": True,
            "v2ExecutionAuthorized": False,
            "v2NamespaceCleanRequired": require_v2_clean,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "networkUsed": False,
            "fileWriteCount": 0,
            "nextAction": recovery["nextAction"],
        }
    finally:
        if root_fd >= 0:
            os.close(root_fd)
        inputs.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--preflight", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate_repository(args.root)
    except COMMON.Wave2Failure as failure:
        print(f"{failure.code}:{failure.phase}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
