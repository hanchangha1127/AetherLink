#!/usr/bin/env python3
"""Validate the verification-only Wave18 identity decision.

Run only with ``python3 -I -B -S``. The checker binds the verified combined-v16
seals and reads only the exact retained x/tools ``go.mod`` and ZIP-contained
``go.sum`` metadata needed for three Wave18 tuples. It does not import,
compile, execute, or invoke combined-v16; reconstruct dependency source;
acquire source; access the network; extract files; load or execute dependency
code; write files; or compile dependency code.
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
            "Wave18 decision checker requires unoptimized "
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
    "decision-wave18-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave18-v1.md"
)
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_decision_v1.py"
)
SELF_NORMALIZED_SHA256 = (
    "0bdec01037fd269627cfbc3e6a0c968a5a16d2c946016ee552ca07727fc3379d"
)
READER_RAW_SHA256 = (
    "862ac89248970b9b4d59230e6b9f894b3fc49ed82f151608687e82cb8b1d1a2d"
)
V16_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v16.py"
V16_CHECKER_RAW_SHA256 = (
    "2e388d466c5346fa6f82b7fd23fa6dca24009acadacdd62f1fe2ba25b0a10879"
)
V16_CHECKER_NORMALIZED_SHA256 = (
    "7dd2c81a2032a374192f7c502afc65305d97f7c1e3699654e416b60bf64c6bd5"
)
V16_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v16.py"
V16_TESTS_RAW_SHA256 = (
    "15cf4d56a68b9f0cfd61554b24e781357066b27e63c90c871dfb0cde19c80889"
)
V16_CANDIDATE_CONTENT_SHA256 = (
    "90928eb85eded2938b25a0beec82c00ebcd69147bf92733bc65a528d26c00e03"
)
V16_GRAPH_SHA256 = (
    "db7e36664afd819c72e9c9916bd7053782282954ed4f359c550b7972b74147a2"
)
V16_FRONTIER_SHA256 = (
    "fe15a3ea57682b276a6f11a2c2fd998d9120640fac40038fc9c1f100e50750b5"
)
V16_INPUT_SET_SHA256 = (
    "15705de20633cdf4bf473c82a634136f481a2c131e7960a0a6cbdeccf10397a7"
)
V16_SOURCE_BINDINGS_SHA256 = (
    "401a3e85faacc150944d883495fca4b22e4cac1933c0308aedaec228a7c872ea"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
NAMESPACE_ANCHOR_PATH = f"{DEPENDENCY_ROOT}/.wave-17-v1.claim"
NAMESPACE_ANCHOR_RAW_SHA256 = (
    "3090e729d99c46c4b4d1e4242d6f25c08e2345062dfb6c15e1e87d3edf632fad"
)
WAVE18_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-18-v1.claim"
WAVE18_STAGING_PREFIX = ".wave-18-v1-staging-"
WAVE18_NAMESPACE_PATH = f"{DEPENDENCY_ROOT}/wave-18-v1"
WAVE18_ACCEPTED_DIRECTORY = f"{WAVE18_NAMESPACE_PATH}/accepted"
X_TOOLS_MOD_PATH = (
    f"{DEPENDENCY_ROOT}/wave-17-v1/accepted/"
    "001-8bd04ea612cec9787131.mod"
)
X_TOOLS_MOD_RAW_SHA256 = (
    "428571a10aab7586a67da2c9375e8ae480def8d2fa11de8c6fff28a696b9591f"
)
X_TOOLS_ZIP_PATH = (
    f"{DEPENDENCY_ROOT}/wave-17-v1/accepted/"
    "001-8bd04ea612cec9787131.zip"
)
X_TOOLS_ZIP_RAW_SHA256 = (
    "da7a76d9db0956f30dd7f9957eead7aab5aa132dbca78a6d578436f94fdfee84"
)
X_TOOLS_GO_SUM_PATH = "golang.org/x/tools@v0.33.0/go.sum"
CHECKER_ID = "g2-pion-ice-v4.3.0-wave18-identity-acquisition-decision-check-v1"
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-identity-and-"
    "acquisition-decision-wave18-v1"
)
COMPACT_IDENTITY_SHA256 = (
    "53a711ff8b8771d698ac0df4448a6155eddc69179e1895d8619afd104f7623d7"
)
FULL_WITNESS_SHA256 = (
    "c95159a8c9b5fbf06f54830a06c59c2f358b8ec5901c3a467fabd0ad64ef5419"
)
REQUEST_SET_SHA256 = (
    "3c13b764b7267efe885528d9f7d4fe31d6b7bdac48839f95e60bb5bd45a7d836"
)
MAXIMUM_FILE_BYTES = 256 * 1024 * 1024
MAXIMUM_DECISION_BYTES = 8 * 1024 * 1024
MAXIMUM_GO_SUM_BYTES = 4 * 1024 * 1024

TUPLES = (
    {
        "module": "golang.org/x/mod",
        "version": "v0.24.0",
        "goModH1": "h1:IXM97Txy2VM4PJ3gI61r1YEk/gAj6zAHN3AdZt6S9Ww=",
        "moduleZipH1": "h1:ZfthKaKaT4NrhGVZHO1/WDTwGES4De8KtWO0SIbNJMU=",
        "tupleDigest": (
            "bb2025870bcef7a0c287192f498f0138c441987a31a5c93bbe69ac05c5d349e7"
        ),
        "parentLine": "\tgolang.org/x/mod v0.24.0",
    },
    {
        "module": "golang.org/x/net",
        "version": "v0.40.0",
        "goModH1": "h1:y0hY0exeL2Pku80/zKK7tpntoX23cqL3Oa6njdgRtds=",
        "moduleZipH1": "h1:79Xs7wF06Gbdcg4kdCCIQArK11Z1hr5POQ6+fIYHNuY=",
        "tupleDigest": (
            "3c84a9eecca520aed886113ab5bf71b0c60c4f09df0144e66e385dae973eda2b"
        ),
        "parentLine": "\tgolang.org/x/net v0.40.0",
    },
    {
        "module": "golang.org/x/sync",
        "version": "v0.14.0",
        "goModH1": "h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=",
        "moduleZipH1": "h1:woo0S4Yywslg6hp4eUFjTVOyKt0RookbpAHG4c1HmhQ=",
        "tupleDigest": (
            "4615480e24f0c4184e4c21ec74e129cb39fbe55c729ca6c997146da3a3924000"
        ),
        "parentLine": "\tgolang.org/x/sync v0.14.0",
    },
)

EXPECTED_HOLD_PATHS = (
    SELF_PATH,
    DECISION_PATH,
    READER_PATH,
    V16_CHECKER_PATH,
    V16_TESTS_PATH,
    NAMESPACE_ANCHOR_PATH,
    X_TOOLS_MOD_PATH,
    X_TOOLS_ZIP_PATH,
)

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
    "productRuntimeNetworkAuthorized": False,
    "publicationAuthorityGranted": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "socketAuthorized": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}
EXPECTED_CLOSURE = {
    "candidateSelected": False,
    "dependencyClosureComplete": False,
    "dependencyFixedPointReached": False,
    "librarySelected": False,
    "releaseReady": False,
    "rungThreeComplete": False,
    "semanticClosureComplete": False,
    "wave18AcquisitionComplete": False,
    "wave18AcquisitionReady": True,
    "wave18IdentityResolved": True,
}
EXPECTED_NON_CLAIMS = [
    "retained_go_sum_h1_is_not_fresh_checksum_database_inclusion_proof",
    "wave18_dependency_source_not_acquired",
    "dependency_source_not_extracted_loaded_executed_or_compiled",
    "combined_v16_not_executed_by_this_checker",
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
EXPECTED_COUNTERS = {
    "archiveExtractionCount": 0,
    "authenticationOperationCount": 0,
    "combinedV16CandidateInvocationCount": 0,
    "dependencySourceCompileCount": 0,
    "dependencySourceExecutionCount": 0,
    "dependencySourceLoadCount": 0,
    "dependencySourceReconstructionCount": 0,
    "fileWriteCount": 0,
    "metadataArchiveOpenCount": 2,
    "metadataScanCount": 2,
    "namespaceSnapshotCount": 2,
    "networkOperationCount": 0,
    "predecessorFullSourceReconstructionCount": 30,
    "predecessorGraphArchiveOpenCount": 4056,
    "productRuntimeNetworkOperationCount": 0,
    "socketOperationCount": 0,
    "subprocessCount": 0,
}


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


def normalized_v16_bytes(raw: bytes) -> bytes:
    marker = re.compile(
        br'(SELF_NORMALIZED_SHA256 = \(\n    ")[0-9a-f]{64}("\n\))'
    )
    normalized, count = marker.subn(
        rb"\g<1>" + b"0" * 64 + rb"\g<2>",
        raw,
    )
    check(count == 1, "E_V16_NORMALIZATION")
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
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            check(type(key) is str and key not in result, f"E_JSON:{path}")
            result[key] = value
        return result

    def reject_float(_: str) -> float:
        raise ValueError("floating-point JSON values are forbidden")

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=object_pairs,
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


def expected_v16_frontier_projection() -> list[dict[str, Any]]:
    projection = [
        {
            "acquisitionAuthorized": False,
            "module": source["module"],
            "requiresSeparateWaveDecision": True,
            "selectedByGraphAlgorithm": False,
            "version": source["version"],
        }
        for source in TUPLES
    ]
    check(
        sha256_bytes(canonical_json_bytes(projection))
        == V16_FRONTIER_SHA256,
        "E_V16_FRONTIER_PROJECTION",
    )
    return projection


def expected_identity_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order, source in enumerate(TUPLES, 1):
        rows.append(
            {
                "acquisitionAuthorized": False,
                "acquisitionReady": True,
                "goModH1": source["goModH1"],
                "goModH1WitnessCount": 1,
                "identityConflict": False,
                "identityPairComplete": True,
                "module": source["module"],
                "moduleZipH1": source["moduleZipH1"],
                "moduleZipH1WitnessCount": 1,
                "parentDeclarationComplete": True,
                "parentDeclarationCount": 1,
                "selectedByGraphAlgorithm": False,
                "tupleOrder": order,
                "version": source["version"],
            }
        )
    return rows


def expected_request_set() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order, source in enumerate(TUPLES, 1):
        digest = sha256_bytes(
            f"{source['module']}\n{source['version']}\n".encode("utf-8")
        )
        check(digest == source["tupleDigest"], "E_REQUEST_SET")
        common = {
            "acquisitionAuthorized": False,
            "authenticationRequired": False,
            "host": "proxy.golang.org",
            "method": "GET",
            "module": source["module"],
            "networkAuthorized": False,
            "selectedByGraphAlgorithm": False,
            "tupleOrder": order,
            "version": source["version"],
        }
        for kind, h1, maximum in (
            ("mod", source["goModH1"], 1_048_576),
            ("zip", source["moduleZipH1"], 16_777_216),
        ):
            rows.append(
                {
                    **common,
                    "acceptedFileName": (
                        f"{order:03d}-{digest[:20]}.{kind}"
                    ),
                    "expectedH1": h1,
                    "maximumResponseBytes": maximum,
                    "requestOrdinal": len(rows) + 1,
                    "resourceKind": kind,
                    "url": (
                        f"https://proxy.golang.org/{source['module']}/"
                        f"@v/{source['version']}.{kind}"
                    ),
                }
            )
    return rows


def expected_compact_identity() -> list[dict[str, Any]]:
    return [
        {
            "goModH1": source["goModH1"],
            "module": source["module"],
            "moduleZipH1": source["moduleZipH1"],
            "selectedByGraphAlgorithm": False,
            "version": source["version"],
        }
        for source in TUPLES
    ]


def expected_full_witness() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in TUPLES:
        module = source["module"]
        version = source["version"]
        result.append(
            {
                "goModH1": {
                    "line": (
                        f"{module} {version}/go.mod {source['goModH1']}"
                    ),
                    "path": X_TOOLS_GO_SUM_PATH,
                    "retainedArchivePath": X_TOOLS_ZIP_PATH,
                    "witnessCount": 1,
                },
                "moduleZipH1": {
                    "line": (
                        f"{module} {version} {source['moduleZipH1']}"
                    ),
                    "path": X_TOOLS_GO_SUM_PATH,
                    "retainedArchivePath": X_TOOLS_ZIP_PATH,
                    "witnessCount": 1,
                },
                "parentDeclaration": {
                    "line": source["parentLine"],
                    "retainedModPath": X_TOOLS_MOD_PATH,
                    "witnessCount": 1,
                },
            }
        )
    return result


def scan_retained_metadata(
    mod_raw: bytes,
    zip_raw: bytes,
) -> list[dict[str, Any]]:
    try:
        mod_lines = mod_raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise DecisionCheckFailure("E_METADATA") from error
    check(
        mod_lines.count("require (") == 1
        and mod_lines.count(")") == 1,
        "E_METADATA",
    )
    logical_mod_lines = [
        tuple(line.split())
        for line in mod_lines
        if line.split()
    ]
    for source in TUPLES:
        module = source["module"]
        parent_matches = [
            tokens
            for tokens in logical_mod_lines
            if (
                tokens[0] == module
                or (
                    len(tokens) >= 2
                    and tokens[0] == "require"
                    and tokens[1] == module
                )
            )
        ]
        check(
            parent_matches == [(module, source["version"])],
            "E_METADATA",
        )
    try:
        with zipfile.ZipFile(io.BytesIO(zip_raw), mode="r") as archive:
            matches = [
                info
                for info in archive.infolist()
                if info.filename == X_TOOLS_GO_SUM_PATH
            ]
            check(
                len(matches) == 1
                and not matches[0].is_dir()
                and matches[0].file_size <= MAXIMUM_GO_SUM_BYTES
                and matches[0].flag_bits & 0x1 == 0,
                "E_METADATA",
            )
            go_sum_raw = archive.read(matches[0])
    except (
        zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
    ) as error:
        raise DecisionCheckFailure("E_METADATA") from error
    try:
        go_sum_lines = go_sum_raw.decode(
            "utf-8",
            errors="strict",
        ).splitlines()
    except UnicodeDecodeError as error:
        raise DecisionCheckFailure("E_METADATA") from error
    logical_go_sum_lines = [
        tuple(line.split())
        for line in go_sum_lines
        if line.split()
    ]
    for source in TUPLES:
        module = source["module"]
        version = source["version"]
        expected_zip_line = (module, version, source["moduleZipH1"])
        expected_mod_line = (
            module,
            f"{version}/go.mod",
            source["goModH1"],
        )
        zip_h1_matches = [
            tokens
            for tokens in logical_go_sum_lines
            if (
                len(tokens) >= 2
                and tokens[0] == module
                and tokens[1] == version
            )
        ]
        mod_h1_matches = [
            tokens
            for tokens in logical_go_sum_lines
            if (
                len(tokens) >= 2
                and tokens[0] == module
                and tokens[1] == f"{version}/go.mod"
            )
        ]
        check(
            zip_h1_matches == [expected_zip_line]
            and mod_h1_matches == [expected_mod_line],
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
    try:
        names = tuple(sorted(os.listdir(root / DEPENDENCY_ROOT)))
    except OSError as error:
        raise DecisionCheckFailure("E_NAMESPACE") from error
    check(
        Path(WAVE18_CLAIM_PATH).name not in names
        and Path(WAVE18_NAMESPACE_PATH).name not in names
        and not any(name.startswith(WAVE18_STAGING_PREFIX) for name in names),
        "E_NAMESPACE",
    )
    return names


def expected_predecessor() -> dict[str, Any]:
    expected_v16_frontier_projection()
    return {
        "combinedFixedPointV16": {
            "checkerNormalizedSha256": V16_CHECKER_NORMALIZED_SHA256,
            "checkerPath": V16_CHECKER_PATH,
            "checkerRawSha256": V16_CHECKER_RAW_SHA256,
            "combinedInputSetSha256": V16_INPUT_SET_SHA256,
            "contentSha256": V16_CANDIDATE_CONTENT_SHA256,
            "fixedPointReached": False,
            "frontierSha256": V16_FRONTIER_SHA256,
            "frontierTupleCount": 3,
            "graphSha256": V16_GRAPH_SHA256,
            "sourceBindingCount": 359,
            "sourceBindingsSha256": V16_SOURCE_BINDINGS_SHA256,
            "testsPath": V16_TESTS_PATH,
            "testsRawSha256": V16_TESTS_RAW_SHA256,
            "totalFullSourceReconstructionCount": 30,
            "totalGraphArchiveOpenCount": 4056,
            "wave17NamespaceAnchor": {
                "path": NAMESPACE_ANCHOR_PATH,
                "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
            },
        }
    }


def expected_identity_resolution() -> dict[str, Any]:
    rows = expected_identity_rows()
    return {
        "blockedTupleCount": 0,
        "compactIdentityCanonicalization": (
            "utf8_unescaped_sorted_keys_compact_no_trailing_lf"
        ),
        "compactIdentitySha256": COMPACT_IDENTITY_SHA256,
        "completeIdentityPairCount": 3,
        "conflictingIdentityCount": 0,
        "fullWitnessCanonicalization": (
            "utf8_unescaped_sorted_keys_compact_no_trailing_lf"
        ),
        "fullWitnessMaterializedInDecision": False,
        "fullWitnessReproducibleByPinnedChecker": True,
        "fullWitnessSha256": FULL_WITNESS_SHA256,
        "goModH1WitnessCount": 3,
        "graphSelectedTupleCount": 0,
        "moduleZipH1WitnessCount": 3,
        "parentDeclarationCount": 3,
        "tupleCount": 3,
        "tuples": rows,
        "versionSpecificNonSelectedTupleCount": 3,
    }


def expected_acquisition_preparation() -> dict[str, Any]:
    requests = expected_request_set()
    return {
        "acceptedDirectoryPath": WAVE18_ACCEPTED_DIRECTORY,
        "acquisitionAuthorizedByThisDecision": False,
        "acquisitionReady": True,
        "claimPath": WAVE18_CLAIM_PATH,
        "namespaceCheckIsPointInTimeOnly": True,
        "namespaceCleanAtDecisionCheck": True,
        "namespaceReservationClaimed": False,
        "permitOrRunnerCreated": False,
        "proxyHost": "proxy.golang.org",
        "requestCount": 6,
        "requestOrder": "tuple_order_ascending_mod_then_zip",
        "requestSet": requests,
        "requestSetCanonicalSha256": REQUEST_SET_SHA256,
        "separateOneUseExecutionPermitRequired": True,
        "stagingDirectoryPrefix": WAVE18_STAGING_PREFIX,
    }


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
            "and-acquisition-decision-wave18"
        )
        and decision.get("schemaVersion") == "1.0"
        and decision.get("date") == "2026-07-28"
        and decision.get("decisionId") == DECISION_ID
        and decision.get("checkerId") == CHECKER_ID
        and decision.get("verificationOnly") is True
        and decision.get("recordModeExposed") is False,
        "E_HEADER",
    )
    without_binding = dict(decision)
    binding = without_binding.pop("contentBinding", None)
    check(
        exact_json_equal(
            binding,
            {
                "algorithm": "sha256",
                "canonicalization": (
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf"
                ),
                "scope": "decision_without_contentBinding",
                "sha256": sha256_bytes(
                    canonical_json_bytes(without_binding)
                ),
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
    check(
        exact_json_equal(
            decision.get("predecessorBindings"),
            expected_predecessor(),
        ),
        "E_PREDECESSOR",
    )
    identity = decision.get("identityResolution")
    check(
        exact_json_equal(identity, expected_identity_resolution()),
        "E_IDENTITY",
    )
    check(
        sha256_bytes(
            canonical_compact_bytes(expected_compact_identity())
        )
        == COMPACT_IDENTITY_SHA256,
        "E_IDENTITY",
    )
    for row in expected_identity_rows():
        validate_h1(row["goModH1"])
        validate_h1(row["moduleZipH1"])
    acquisition = expected_acquisition_preparation()
    acquisition["namespaceCleanAtDecisionCheck"] = namespace_clean
    check(
        exact_json_equal(
            decision.get("sourceAcquisitionPreparation"),
            acquisition,
        )
        and sha256_bytes(
            canonical_compact_bytes(expected_request_set())
        )
        == REQUEST_SET_SHA256,
        "E_ACQUISITION",
    )
    check(
        exact_json_equal(decision.get("closure"), EXPECTED_CLOSURE),
        "E_CLOSURE",
    )
    check(
        exact_json_equal(
            decision.get("operationCounters"),
            EXPECTED_COUNTERS,
        ),
        "E_COUNTERS",
    )
    check(
        exact_json_equal(
            decision.get("retainedMetadataEvidence"),
            {
                "allEvidenceInputsReadTwice": True,
                "goSumEntryPath": X_TOOLS_GO_SUM_PATH,
                "metadataScanCount": 2,
                "retainedModPath": X_TOOLS_MOD_PATH,
                "retainedModRawSha256": X_TOOLS_MOD_RAW_SHA256,
                "retainedZipPath": X_TOOLS_ZIP_PATH,
                "retainedZipRawSha256": X_TOOLS_ZIP_RAW_SHA256,
                "sourceCodeInspected": False,
                "sourceReconstructionPerformed": False,
            },
        ),
        "E_METADATA_BINDING",
    )
    check(
        exact_json_equal(
            decision.get("toolBindings"),
            [
                {
                    "normalizedSha256": SELF_NORMALIZED_SHA256,
                    "path": SELF_PATH,
                    "role": "current_wave18_decision_checker",
                },
                {
                    "normalizedSha256": V16_CHECKER_NORMALIZED_SHA256,
                    "path": V16_CHECKER_PATH,
                    "rawSha256": V16_CHECKER_RAW_SHA256,
                    "role": "immutable_combined_v16_checker",
                },
                {
                    "path": V16_TESTS_PATH,
                    "rawSha256": V16_TESTS_RAW_SHA256,
                    "role": "immutable_combined_v16_tests",
                },
            ],
        )
        and exact_json_equal(
            decision.get("readerDocumentBinding"),
            {
                "path": READER_PATH,
                "rawSha256": READER_RAW_SHA256,
            },
        ),
        "E_BINDINGS",
    )
    check(
        decision.get("status")
        == (
            "wave18_exact_3_frontier_identity_classified_3_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and decision.get("result")
        == (
            "exact_3_version_vertices_0_selected_3_nonselected_"
            "3_complete_h1_pairs_acquisition_ready_not_authorized"
        )
        and decision.get("nextAction")
        == "independent_review_of_wave18_decision_package",
        "E_RESULT",
    )


def run_check(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    with ExitStack() as stack:
        held: list[HeldFile] = []

        def hold(
            path: str,
            digest: str | None,
            maximum: int = MAXIMUM_FILE_BYTES,
        ) -> HeldFile:
            value = stack.enter_context(
                HeldFile(root, path, digest, maximum)
            )
            held.append(value)
            return value

        self_held = hold(SELF_PATH, None, 4 * 1024 * 1024)
        check(
            sha256_bytes(normalized_self_bytes(self_held.raw))
            == SELF_NORMALIZED_SHA256,
            "E_SELF_IDENTITY",
        )
        decision_held = hold(
            DECISION_PATH,
            None,
            MAXIMUM_DECISION_BYTES,
        )
        hold(READER_PATH, READER_RAW_SHA256, 4 * 1024 * 1024)
        v16_held = hold(V16_CHECKER_PATH, V16_CHECKER_RAW_SHA256)
        check(
            sha256_bytes(normalized_v16_bytes(v16_held.raw))
            == V16_CHECKER_NORMALIZED_SHA256,
            "E_V16_IDENTITY",
        )
        expected_v16_frontier_projection()
        hold(V16_TESTS_PATH, V16_TESTS_RAW_SHA256)
        hold(NAMESPACE_ANCHOR_PATH, NAMESPACE_ANCHOR_RAW_SHA256)
        mod_held = hold(X_TOOLS_MOD_PATH, X_TOOLS_MOD_RAW_SHA256)
        zip_held = hold(X_TOOLS_ZIP_PATH, X_TOOLS_ZIP_RAW_SHA256)
        check(
            len(held) == 8
            and tuple(value.relative_path for value in held)
            == EXPECTED_HOLD_PATHS,
            "E_HOLD_PATHS",
        )

        before = namespace_snapshot(root)
        first = scan_retained_metadata(mod_held.raw, zip_held.raw)
        second = scan_retained_metadata(mod_held.raw, zip_held.raw)
        check(first == second, "E_REPRODUCTION")
        after = namespace_snapshot(root)
        check(before == after, "E_NAMESPACE")
        decision = dict(strict_json(decision_held.raw, DECISION_PATH))
        validate_decision(decision, namespace_clean=True)
        for value in held:
            value.final_barrier()
        return decision


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parse_arguments(argv)
    try:
        decision = run_check(ROOT)
    except DecisionCheckFailure as error:
        payload = {
            "checkerId": CHECKER_ID,
            "error": str(error),
            "externalAuthenticationRequired": False,
            "status": "wave18_decision_check_failed",
            "userActionRequired": False,
        }
        sys.stdout.buffer.write(canonical_json_bytes(payload))
        return 1
    except OSError:
        payload = {
            "checkerId": CHECKER_ID,
            "error": "E_OS",
            "externalAuthenticationRequired": False,
            "status": "wave18_decision_check_failed",
            "userActionRequired": False,
        }
        sys.stdout.buffer.write(canonical_json_bytes(payload))
        return 1
    sys.stdout.buffer.write(canonical_json_bytes(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
