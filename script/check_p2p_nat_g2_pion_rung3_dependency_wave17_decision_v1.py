#!/usr/bin/env python3
"""Validate the verification-only Wave17 identity decision.

Run only with ``python3 -I -B -S``. The checker binds the verified combined-v15
seals and reads only the exact retained x/text ``go.mod`` and ZIP-contained
``go.sum`` metadata needed for ``golang.org/x/tools@v0.33.0``. It does not
execute combined-v15, reconstruct dependency source, acquire source, access
the network, extract files, load or execute dependency code, or compile it.
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
            "Wave17 decision checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
import base64
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.md"
)
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_decision_v1.py"
)
SELF_NORMALIZED_SHA256 = (
    "226cb948492708f50e695c9d5e849c4f0acff11143625f473372c1bb59cec269"
)
READER_RAW_SHA256 = (
    "3af49874bd518628971566d6067331c75e2f4fbcf7ac36bafee914938873ef51"
)
V15_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v15.py"
V15_CHECKER_RAW_SHA256 = (
    "e0a8353e5bd4f40b587c2b62c563c0b679ca5261345e577d71d00fb868f08fb5"
)
V15_CHECKER_NORMALIZED_SHA256 = (
    "63198050500264a07082d205172c21993a309289649a5459e1c638b53fb22bf7"
)
V15_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v15.py"
V15_TESTS_RAW_SHA256 = (
    "65d7f435cef11da2cccae7e31a3c410d7a3038f6bc3261552753801a0de431b1"
)
V15_CANDIDATE_CONTENT_SHA256 = (
    "4666c802e40734bb1b5b91489eb24aa782cb346710caec9605be4e0e005553ee"
)
V15_GRAPH_SHA256 = (
    "ffe9f910669401198b88752663055ca2e6622d19e171f2d20a2b303d06c989d7"
)
V15_FRONTIER_SHA256 = (
    "ce1be1152aabf580a211f038d80aeaf9249418117b7d12ff26ffc909f1e4d593"
)
V15_INPUT_SET_SHA256 = (
    "4b12b7ca7f0a8b1556c692522e8832af033f9d2a1f00fbeb7469623a00541f1e"
)
V15_SOURCE_BINDINGS_SHA256 = (
    "86512fdc6c5b8ff8b1d79e500e32c6c35c36f6c097aca5385f8ff1e06ffe18fd"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
NAMESPACE_ANCHOR_PATH = f"{DEPENDENCY_ROOT}/.wave-16-v1.claim"
NAMESPACE_ANCHOR_RAW_SHA256 = (
    "df97f5d9bf8c56f3bbf08635b8332bbc18b25babd0e5f35742fee3657555f4b8"
)
WAVE17_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-17-v1.claim"
WAVE17_STAGING_PREFIX = ".wave-17-v1-staging-"
WAVE17_ACCEPTED_PATH = f"{DEPENDENCY_ROOT}/wave-17-v1"
X_TEXT_MOD_PATH = (
    f"{DEPENDENCY_ROOT}/wave-16-v1/accepted/"
    "003-d0a18208476fea968bb8.mod"
)
X_TEXT_MOD_RAW_SHA256 = (
    "178b8e330288183eabcb6e776a3f01099b5926661fc866b750acec7cb8402dc2"
)
X_TEXT_ZIP_PATH = (
    f"{DEPENDENCY_ROOT}/wave-16-v1/accepted/"
    "003-d0a18208476fea968bb8.zip"
)
X_TEXT_ZIP_RAW_SHA256 = (
    "c524f4ace2e1f35b75d9e6177b1597cf31736c81064df5978a4d61300d7626c8"
)
X_TEXT_GO_SUM_PATH = "golang.org/x/text@v0.26.0/go.sum"
MODULE = "golang.org/x/tools"
VERSION = "v0.33.0"
GO_MOD_H1 = "h1:CIJMaWEY88juyUfo7UbgPqbC8rU2OqfAV1h2Qp0oMYI="
MODULE_ZIP_H1 = "h1:4qz2S3zmRxbGIhDIAgjxvFutSvH5EfnsYrRBj0UI0bc="
TUPLE_DIGEST = (
    "8bd04ea612cec978713135c7452cb52e20350f82cd8b2a17691e3c431b43973c"
)
COMPACT_IDENTITY_SHA256 = (
    "813ac6030c903b716fb5f68852468a53ebb0bcfe60c7c11582d2f2ffb18041ca"
)
FULL_WITNESS_SHA256 = (
    "ee3f4b0e1072a8bc0e1eb6e53b83fe8d749fdfd8c13bec54c60774dc3755dc54"
)
REQUEST_SET_SHA256 = (
    "acf64af2352fb4d82325f3e5bd2a3e913b8ef95db553fa0015bc71a239f3fb35"
)
CHECKER_ID = "g2-pion-ice-v4.3.0-wave17-identity-acquisition-decision-check-v1"
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-identity-and-"
    "acquisition-decision-wave17-v1"
)
MAXIMUM_FILE_BYTES = 256 * 1024 * 1024
MAXIMUM_DECISION_BYTES = 8 * 1024 * 1024
MAXIMUM_GO_SUM_BYTES = 4 * 1024 * 1024

EXPECTED_AUTHORITY = {
    "acquisitionAuthorityGranted": False,
    "authenticationRequired": False,
    "compileAuthorized": False,
    "decisionAuthorityGranted": False,
    "deploymentAuthorized": False,
    "dependencySourceExecutionAuthorized": False,
    "deviceInteractionRequired": False,
    "dnsAuthorized": False,
    "executionAuthorityGranted": False,
    "externalAuthenticationRequired": False,
    "fileWriteAuthorized": False,
    "filesystemExtractionAuthorized": False,
    "gitWriteAuthorized": False,
    "networkAuthorized": False,
    "ownerProofRequired": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "publicationAuthorityGranted": False,
    "productRuntimeNetworkAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "socketAuthorized": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}
EXPECTED_NON_CLAIMS = [
    "retained_go_sum_h1_is_not_fresh_checksum_database_inclusion_proof",
    "wave17_dependency_source_not_acquired",
    "dependency_source_not_extracted_loaded_executed_or_compiled",
    "combined_v15_not_executed_by_this_checker",
    "dependency_source_not_reconstructed_by_this_checker",
    "dependency_fixed_point_not_reached",
    "dependency_and_semantic_closure_not_complete",
    "candidate_and_library_not_selected",
    "release_not_ready",
    (
        "namespace_check_is_point_in_time_only_and_does_not_prevent_"
        "same_uid_concurrent_replacement"
    ),
]


class DecisionCheckFailure(RuntimeError):
    pass


def check(condition: Any, code: str) -> None:
    if not condition:
        raise DecisionCheckFailure(code)


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


def canonical_compact_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def exact_json_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON values without Python's bool/int equality alias."""

    try:
        return canonical_json_bytes(actual) == canonical_json_bytes(expected)
    except (TypeError, ValueError):
        return False


def normalized_self_bytes(raw: bytes) -> bytes:
    marker = re.compile(
        br'(SELF_NORMALIZED_SHA256 = \(\n    ")[0-9a-f]{64}("\n\))'
    )
    normalized, count = marker.subn(
        rb"\g<1>" + b"0" * 64 + rb"\g<2>",
        raw,
    )
    check(count == 1, "E_SELF_NORMALIZATION")
    return normalized


def normalized_v15_bytes(raw: bytes) -> bytes:
    marker = re.compile(
        br'(SELF_NORMALIZED_SHA256 = \(\n    ")[0-9a-f]{64}("\n\))'
    )
    normalized, count = marker.subn(
        rb"\g<1>" + b"0" * 64 + rb"\g<2>",
        raw,
    )
    check(count == 1, "E_V15_NORMALIZATION")
    return normalized


class HeldFile:
    """Read one exact regular file twice and retain its descriptor."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        expected_sha256: str | None,
        maximum_bytes: int = MAXIMUM_FILE_BYTES,
    ) -> None:
        check(
            type(relative_path) is str
            and relative_path
            and not relative_path.startswith("/")
            and ".." not in Path(relative_path).parts,
            "E_PATH",
        )
        self.relative_path = relative_path
        self.path = root / relative_path
        self.expected_sha256 = expected_sha256
        self.fd = -1
        self.initial: os.stat_result | None = None
        self.raw = b""
        flags = os.O_RDONLY | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            self.fd = os.open(self.path, flags)
            self.initial = os.fstat(self.fd)
            self._validate(self.initial, maximum_bytes)
            first = self._read()
            second = self._read()
            check(first == second, "E_STABLE_READ")
            if expected_sha256 is not None:
                check(
                    sha256_bytes(first) == expected_sha256,
                    "E_FILE_IDENTITY",
                )
            self.raw = first
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _validate(info: os.stat_result, maximum_bytes: int) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= maximum_bytes,
            "E_FILE_IDENTITY",
        )

    def _read(self) -> bytes:
        check(self.fd >= 0 and self.initial is not None, "E_FILE_IDENTITY")
        os.lseek(self.fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = self.initial.st_size
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_STABLE_READ")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_STABLE_READ")
        return b"".join(chunks)

    def final_barrier(self) -> None:
        check(self.fd >= 0 and self.initial is not None, "E_FILE_IDENTITY")
        current = os.fstat(self.fd)
        named = os.stat(self.path, follow_symlinks=False)
        fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        check(
            tuple(getattr(current, name) for name in fields)
            == tuple(getattr(named, name) for name in fields)
            == tuple(getattr(self.initial, name) for name in fields),
            "E_FILE_IDENTITY",
        )

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> "HeldFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def strict_json(raw: bytes, path: str) -> Mapping[str, Any]:
    def reject_float(_: str) -> float:
        raise ValueError("floating-point JSON values are forbidden")

    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise DecisionCheckFailure(f"E_JSON:{path}") from error
    check(type(value) is dict, f"E_JSON:{path}")
    check(canonical_json_bytes(value) == raw, f"E_CANONICAL_JSON:{path}")
    return value


def validate_h1(value: Any) -> None:
    check(type(value) is str and value.startswith("h1:"), "E_H1")
    try:
        decoded = base64.b64decode(value[3:], validate=True)
    except ValueError as error:
        raise DecisionCheckFailure("E_H1") from error
    check(len(decoded) == 32, "E_H1")


def expected_identity_row() -> dict[str, Any]:
    return {
        "acquisitionAuthorized": False,
        "acquisitionReady": True,
        "goModH1": GO_MOD_H1,
        "goModH1WitnessCount": 1,
        "identityConflict": False,
        "identityPairComplete": True,
        "module": MODULE,
        "moduleZipH1": MODULE_ZIP_H1,
        "moduleZipH1WitnessCount": 1,
        "parentDeclarationComplete": True,
        "parentDeclarationCount": 1,
        "selectedByGraphAlgorithm": False,
        "tupleOrder": 1,
        "version": VERSION,
    }


def expected_request_set() -> list[dict[str, Any]]:
    common = {
        "acquisitionAuthorized": False,
        "authenticationRequired": False,
        "host": "proxy.golang.org",
        "method": "GET",
        "module": MODULE,
        "networkAuthorized": False,
        "selectedByGraphAlgorithm": False,
        "tupleOrder": 1,
        "version": VERSION,
    }
    return [
        {
            **common,
            "acceptedFileName": "001-8bd04ea612cec9787131.mod",
            "expectedH1": GO_MOD_H1,
            "maximumResponseBytes": 1_048_576,
            "requestOrdinal": 1,
            "resourceKind": "mod",
            "url": "https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.mod",
        },
        {
            **common,
            "acceptedFileName": "001-8bd04ea612cec9787131.zip",
            "expectedH1": MODULE_ZIP_H1,
            "maximumResponseBytes": 16_777_216,
            "requestOrdinal": 2,
            "resourceKind": "zip",
            "url": "https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.zip",
        },
    ]


def expected_compact_identity() -> list[dict[str, Any]]:
    return [
        {
            "goModH1": GO_MOD_H1,
            "module": MODULE,
            "moduleZipH1": MODULE_ZIP_H1,
            "selectedByGraphAlgorithm": False,
            "version": VERSION,
        }
    ]


def expected_full_witness() -> dict[str, Any]:
    return {
        "goModH1": {
            "line": f"{MODULE} {VERSION}/go.mod {GO_MOD_H1}",
            "path": X_TEXT_GO_SUM_PATH,
            "retainedArchivePath": X_TEXT_ZIP_PATH,
            "witnessCount": 1,
        },
        "moduleZipH1": {
            "line": f"{MODULE} {VERSION} {MODULE_ZIP_H1}",
            "path": X_TEXT_GO_SUM_PATH,
            "retainedArchivePath": X_TEXT_ZIP_PATH,
            "witnessCount": 1,
        },
        "parentDeclaration": {
            "line": f"require {MODULE} {VERSION} // tagx:ignore",
            "retainedModPath": X_TEXT_MOD_PATH,
            "witnessCount": 1,
        },
    }


def scan_retained_metadata(
    mod_raw: bytes,
    zip_raw: bytes,
) -> dict[str, Any]:
    try:
        mod_text = mod_raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise DecisionCheckFailure("E_METADATA") from error
    declaration = f"require {MODULE} {VERSION} // tagx:ignore"
    check(mod_text.splitlines().count(declaration) == 1, "E_METADATA")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_raw), mode="r") as archive:
            matches = [
                info
                for info in archive.infolist()
                if info.filename == X_TEXT_GO_SUM_PATH
            ]
            check(
                len(matches) == 1
                and matches[0].file_size <= MAXIMUM_GO_SUM_BYTES
                and matches[0].flag_bits & 0x1 == 0,
                "E_METADATA",
            )
            go_sum_raw = archive.read(matches[0])
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise DecisionCheckFailure("E_METADATA") from error
    try:
        lines = go_sum_raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise DecisionCheckFailure("E_METADATA") from error
    module_line = f"{MODULE} {VERSION} {MODULE_ZIP_H1}"
    mod_line = f"{MODULE} {VERSION}/go.mod {GO_MOD_H1}"
    check(
        lines.count(module_line) == 1
        and lines.count(mod_line) == 1,
        "E_METADATA",
    )
    witness = expected_full_witness()
    check(
        sha256_bytes(canonical_compact_bytes(witness))
        == FULL_WITNESS_SHA256,
        "E_WITNESS",
    )
    return witness


def namespace_snapshot(root: Path) -> tuple[str, ...]:
    dependency_root = root / DEPENDENCY_ROOT
    try:
        names = tuple(sorted(os.listdir(dependency_root)))
    except OSError as error:
        raise DecisionCheckFailure("E_NAMESPACE") from error
    check(
        Path(WAVE17_CLAIM_PATH).name not in names
        and Path(WAVE17_ACCEPTED_PATH).name not in names
        and not any(name.startswith(WAVE17_STAGING_PREFIX) for name in names),
        "E_NAMESPACE",
    )
    return names


def validate_decision(
    decision: Mapping[str, Any],
    *,
    namespace_clean: bool,
) -> None:
    check(
        set(decision)
        == {
            "authority",
            "checkerId",
            "closure",
            "contentBinding",
            "date",
            "decisionId",
            "documentType",
            "identityResolution",
            "nextAction",
            "nonClaims",
            "operationCounters",
            "predecessorBindings",
            "readerDocumentBinding",
            "recordModeExposed",
            "result",
            "retainedMetadataEvidence",
            "schemaVersion",
            "sourceAcquisitionPreparation",
            "status",
            "toolBindings",
            "verificationOnly",
        },
        "E_TOP_LEVEL_KEYS",
    )
    check(
        decision.get("documentType")
        == (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-identity-"
            "and-acquisition-decision-wave17"
        )
        and decision.get("schemaVersion") == "1.0"
        and decision.get("date") == "2026-07-27"
        and decision.get("decisionId") == DECISION_ID
        and decision.get("checkerId") == CHECKER_ID
        and decision.get("verificationOnly") is True
        and decision.get("recordModeExposed") is False,
        "E_HEADER",
    )
    binding = decision.get("contentBinding")
    without = dict(decision)
    without.pop("contentBinding", None)
    check(
        type(binding) is dict
        and exact_json_equal(
            binding,
            {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "decision_without_contentBinding",
            "sha256": sha256_bytes(canonical_json_bytes(without)),
            },
        ),
        "E_CONTENT_BINDING",
    )
    check(
        exact_json_equal(decision.get("authority"), EXPECTED_AUTHORITY),
        "E_AUTHORITY",
    )
    check(
        exact_json_equal(decision.get("nonClaims"), EXPECTED_NON_CLAIMS),
        "E_NON_CLAIMS",
    )
    predecessor = decision.get("predecessorBindings")
    expected_predecessor = {
        "combinedFixedPointV15": {
            "checkerNormalizedSha256": V15_CHECKER_NORMALIZED_SHA256,
            "checkerPath": V15_CHECKER_PATH,
            "checkerRawSha256": V15_CHECKER_RAW_SHA256,
            "combinedInputSetSha256": V15_INPUT_SET_SHA256,
            "contentSha256": V15_CANDIDATE_CONTENT_SHA256,
            "fixedPointReached": False,
            "frontierSha256": V15_FRONTIER_SHA256,
            "frontierTupleCount": 1,
            "graphSha256": V15_GRAPH_SHA256,
            "sourceBindingCount": 357,
            "sourceBindingsSha256": V15_SOURCE_BINDINGS_SHA256,
            "testsPath": V15_TESTS_PATH,
            "testsRawSha256": V15_TESTS_RAW_SHA256,
            "totalFullSourceReconstructionCount": 28,
            "totalGraphArchiveOpenCount": 3696,
            "wave16NamespaceAnchor": {
                "path": NAMESPACE_ANCHOR_PATH,
                "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
            },
        }
    }
    check(
        exact_json_equal(predecessor, expected_predecessor),
        "E_PREDECESSOR",
    )
    identity = decision.get("identityResolution")
    expected_identity = {
        "blockedTupleCount": 0,
        "compactIdentityCanonicalization":
            "utf8_unescaped_sorted_keys_compact_no_trailing_lf",
        "compactIdentitySha256": COMPACT_IDENTITY_SHA256,
        "completeIdentityPairCount": 1,
        "conflictingIdentityCount": 0,
        "fullWitnessCanonicalization":
            "utf8_unescaped_sorted_keys_compact_no_trailing_lf",
        "fullWitnessMaterializedInDecision": False,
        "fullWitnessReproducibleByPinnedChecker": True,
        "fullWitnessSha256": FULL_WITNESS_SHA256,
        "goModH1WitnessCount": 1,
        "graphSelectedTupleCount": 0,
        "moduleZipH1WitnessCount": 1,
        "parentDeclarationCount": 1,
        "tupleCount": 1,
        "tuples": [expected_identity_row()],
        "versionSpecificNonSelectedTupleCount": 1,
    }
    check(
        type(identity) is dict
        and exact_json_equal(identity, expected_identity),
        "E_IDENTITY",
    )
    validate_h1(identity["tuples"][0]["goModH1"])
    validate_h1(identity["tuples"][0]["moduleZipH1"])
    acquisition = decision.get("sourceAcquisitionPreparation")
    requests = expected_request_set()
    expected_acquisition = {
        "acceptedDirectoryPath": f"{DEPENDENCY_ROOT}/wave-17-v1/accepted",
        "acquisitionAuthorizedByThisDecision": False,
        "acquisitionReady": True,
        "claimPath": WAVE17_CLAIM_PATH,
        "namespaceCheckIsPointInTimeOnly": True,
        "namespaceCleanAtDecisionCheck": namespace_clean,
        "namespaceReservationClaimed": False,
        "permitOrRunnerCreated": False,
        "proxyHost": "proxy.golang.org",
        "requestCount": 2,
        "requestOrder": "tuple_order_ascending_mod_then_zip",
        "requestSet": requests,
        "requestSetCanonicalSha256": REQUEST_SET_SHA256,
        "separateOneUseExecutionPermitRequired": True,
        "stagingDirectoryPrefix": WAVE17_STAGING_PREFIX,
    }
    check(
        type(acquisition) is dict
        and exact_json_equal(acquisition, expected_acquisition),
        "E_ACQUISITION",
    )
    check(
        sha256_bytes(canonical_compact_bytes(requests))
        == REQUEST_SET_SHA256,
        "E_ACQUISITION",
    )
    closure = decision.get("closure")
    check(
        exact_json_equal(
            closure,
            {
            "candidateSelected": False,
            "dependencyClosureComplete": False,
            "dependencyFixedPointReached": False,
            "librarySelected": False,
            "releaseReady": False,
            "rungThreeComplete": False,
            "semanticClosureComplete": False,
            "wave17AcquisitionComplete": False,
            "wave17AcquisitionReady": True,
            "wave17IdentityResolved": True,
            },
        ),
        "E_CLOSURE",
    )
    counters = decision.get("operationCounters")
    check(
        exact_json_equal(
            counters,
            {
            "archiveExtractionCount": 0,
            "authenticationOperationCount": 0,
            "combinedV15CandidateInvocationCount": 0,
            "dependencySourceCompileCount": 0,
            "dependencySourceExecutionCount": 0,
            "dependencySourceLoadCount": 0,
            "dependencySourceReconstructionCount": 0,
            "fileWriteCount": 0,
            "metadataArchiveOpenCount": 2,
            "metadataScanCount": 2,
            "namespaceSnapshotCount": 2,
            "networkOperationCount": 0,
            "predecessorFullSourceReconstructionCount": 28,
            "predecessorGraphArchiveOpenCount": 3696,
            "productRuntimeNetworkOperationCount": 0,
            "socketOperationCount": 0,
            "subprocessCount": 0,
            },
        ),
        "E_COUNTERS",
    )
    check(
        decision.get("status")
        == (
            "wave17_exact_1_frontier_identity_classified_1_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and decision.get("result")
        == (
            "exact_1_version_vertex_0_selected_1_nonselected_"
            "1_complete_h1_pair_acquisition_ready_not_authorized"
        )
        and decision.get("nextAction")
        == "independent_review_of_wave17_decision_package",
        "E_RESULT",
    )
    check(
        exact_json_equal(
            decision.get("readerDocumentBinding"),
            {"path": READER_PATH, "rawSha256": READER_RAW_SHA256},
        )
        and exact_json_equal(
            decision.get("toolBindings"),
            [
            {
                "normalizedSha256": SELF_NORMALIZED_SHA256,
                "path": SELF_PATH,
                "role": "current_wave17_decision_checker",
            },
            {
                "normalizedSha256": V15_CHECKER_NORMALIZED_SHA256,
                "path": V15_CHECKER_PATH,
                "rawSha256": V15_CHECKER_RAW_SHA256,
                "role": "immutable_combined_v15_checker",
            },
            {
                "path": V15_TESTS_PATH,
                "rawSha256": V15_TESTS_RAW_SHA256,
                "role": "immutable_combined_v15_tests",
            },
            ],
        ),
        "E_BINDINGS",
    )
    check(
        exact_json_equal(
            decision.get("retainedMetadataEvidence"),
            {
            "allEvidenceInputsReadTwice": True,
            "goSumEntryPath": X_TEXT_GO_SUM_PATH,
            "metadataScanCount": 2,
            "retainedModPath": X_TEXT_MOD_PATH,
            "retainedModRawSha256": X_TEXT_MOD_RAW_SHA256,
            "retainedZipPath": X_TEXT_ZIP_PATH,
            "retainedZipRawSha256": X_TEXT_ZIP_RAW_SHA256,
            "sourceCodeInspected": False,
            "sourceReconstructionPerformed": False,
            },
        ),
        "E_METADATA_BINDING",
    )


def run_check(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    with ExitStack() as stack:
        self_held = stack.enter_context(
            HeldFile(root, SELF_PATH, None, 4 * 1024 * 1024)
        )
        check(
            sha256_bytes(normalized_self_bytes(self_held.raw))
            == SELF_NORMALIZED_SHA256,
            "E_SELF_IDENTITY",
        )
        decision_held = stack.enter_context(
            HeldFile(root, DECISION_PATH, None, MAXIMUM_DECISION_BYTES)
        )
        reader_held = stack.enter_context(
            HeldFile(root, READER_PATH, READER_RAW_SHA256, 4 * 1024 * 1024)
        )
        v15_held = stack.enter_context(
            HeldFile(root, V15_CHECKER_PATH, V15_CHECKER_RAW_SHA256)
        )
        check(
            sha256_bytes(normalized_v15_bytes(v15_held.raw))
            == V15_CHECKER_NORMALIZED_SHA256,
            "E_V15_IDENTITY",
        )
        stack.enter_context(
            HeldFile(root, V15_TESTS_PATH, V15_TESTS_RAW_SHA256)
        )
        stack.enter_context(
            HeldFile(root, NAMESPACE_ANCHOR_PATH, NAMESPACE_ANCHOR_RAW_SHA256)
        )
        mod_held = stack.enter_context(
            HeldFile(root, X_TEXT_MOD_PATH, X_TEXT_MOD_RAW_SHA256)
        )
        zip_held = stack.enter_context(
            HeldFile(root, X_TEXT_ZIP_PATH, X_TEXT_ZIP_RAW_SHA256)
        )
        before = namespace_snapshot(root)
        first_witness = scan_retained_metadata(mod_held.raw, zip_held.raw)
        second_witness = scan_retained_metadata(mod_held.raw, zip_held.raw)
        check(first_witness == second_witness, "E_REPRODUCTION")
        after = namespace_snapshot(root)
        check(before == after, "E_NAMESPACE")
        check(
            sha256_bytes(canonical_compact_bytes(expected_compact_identity()))
            == COMPACT_IDENTITY_SHA256,
            "E_IDENTITY",
        )
        decision = dict(strict_json(decision_held.raw, DECISION_PATH))
        validate_decision(decision, namespace_clean=True)
        for held in (
            self_held,
            decision_held,
            reader_held,
            v15_held,
            mod_held,
            zip_held,
        ):
            held.final_barrier()
        return decision


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parse_arguments(argv)
    try:
        decision = run_check(ROOT)
    except (DecisionCheckFailure, OSError) as error:
        sys.stdout.buffer.write(
            canonical_json_bytes(
                {
                    "externalAuthenticationRequired": False,
                    "checkerId": CHECKER_ID,
                    "error": str(error),
                    "status": "wave17_decision_check_failed",
                    "userActionRequired": False,
                }
            )
        )
        return 1
    sys.stdout.buffer.write(canonical_json_bytes(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
