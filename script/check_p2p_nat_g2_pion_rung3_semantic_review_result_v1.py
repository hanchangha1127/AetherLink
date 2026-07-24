#!/usr/bin/env python3
"""Read back the bounded G2 Pion rung-three semantic-review publication.

This checker is deliberately outside the one-shot publisher.  It reads only
eight fixed repository paths, follows no symlinks, enumerates no directory,
opens neither the retained archive nor source bodies, writes nothing, and
requires no identity or user action.  Exact byte pins establish that the
published classifications, result, and atomic commit marker still bind the
review decision, pass input, two non-attesting pass records, and runner.

The successful output is evidence for this bounded publication checkpoint.
It is not a reproduction of the semantic judgments, dependency closure,
rung-three completion, library selection, or production authorization.
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
            "semantic-review readback requires unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(os.path.abspath(__file__)).parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG3 = f"{BASE}/rung-three"
RUNNER_PATH = "script/run_p2p_nat_g2_pion_rung3_semantic_review_v1.py"
DECISION_PATH = f"{RUNG3}/semantic-source-review-decision-v1.json"
PASS_INPUT_PATH = f"{RUNG3}/semantic-source-review-pass-input-v1.json"
PRIMARY_RECORD_PATH = f"{RUNG3}/semantic-source-review-primary-pass-record-v1.json"
INDEPENDENT_RECORD_PATH = (
    f"{RUNG3}/semantic-source-review-independent-pass-record-v1.json"
)
CLASSIFICATIONS_PATH = f"{RUNG3}/semantic-source-review-classifications-v1.json"
RESULT_PATH = f"{RUNG3}/semantic-source-review-result-v1.json"
MANIFEST_PATH = f"{RUNG3}/semantic-source-review-manifest-v1.json"

ALLOWED_PATHS = (
    RUNNER_PATH,
    DECISION_PATH,
    PASS_INPUT_PATH,
    PRIMARY_RECORD_PATH,
    INDEPENDENT_RECORD_PATH,
    CLASSIFICATIONS_PATH,
    RESULT_PATH,
    MANIFEST_PATH,
)
JSON_PATHS = ALLOWED_PATHS[1:]
PUBLISHED_PATHS = (CLASSIFICATIONS_PATH, RESULT_PATH, MANIFEST_PATH)

CLASSIFICATIONS_NAME = PurePosixPath(CLASSIFICATIONS_PATH).name
RESULT_NAME = PurePosixPath(RESULT_PATH).name
MANIFEST_NAME = PurePosixPath(MANIFEST_PATH).name
FAILURE_NAME = "semantic-source-review-execution-failure-v1.json"
STAGING_NAMES = (
    f".{CLASSIFICATIONS_NAME}.staging",
    f".{RESULT_NAME}.staging",
    f".{MANIFEST_NAME}.staging",
    f".{FAILURE_NAME}.staging",
)
ABSENT_NAMES = (FAILURE_NAME, *STAGING_NAMES)

EXPECTED_RAW_SHA256 = {
    RUNNER_PATH: "4537d71b3eb4583ea6d2bf62995439fe7a06a3704902c0b855fccf26786328f1",
    DECISION_PATH: "b65379bf0f97cd0558c93d818e5ecea14242a938ca5922796eb4a28f345e7cfc",
    PASS_INPUT_PATH: "21a228b16d57addfef20d0ff53ec81a7ee5846462d60d8d8fbc4ffa25addf548",
    PRIMARY_RECORD_PATH: "7d12f76bc38befc728b0f78bbda3c792e398e0984c98a86825124b3d457678fc",
    INDEPENDENT_RECORD_PATH: "b45b7a80813bafc46a3cc0d0358b6738f408dd025b092dfd2d99a17eb8a92557",
    CLASSIFICATIONS_PATH: "e76e8c9fa0a78c8c5c4beae1ebfd4c4f8144b411689a3a8bd5f8804ebf61c8c9",
    RESULT_PATH: "a01b3518f1354d438542ae77c06aa92d8f0936d516b4070d19c5bf27791e8a98",
    MANIFEST_PATH: "300da97505b4715576d665846b23dd8363b36d416ed5d24ed4a7d4e77f098e6f",
}
EXPECTED_CONTENT_SHA256 = {
    DECISION_PATH: "09ccce7ae9b0893e30d4cbf2533e947623da70f56a499e5bdd2cd3e68bc3ef6b",
    PASS_INPUT_PATH: "7240a2386d7ada48cde93792110bbcc72474b834cc1cc4c5294f945baad605be",
    PRIMARY_RECORD_PATH: "323699afbb0747ca90fc1aa5bf6e8ec20cbc319408b7e1156064e4d90799f97f",
    INDEPENDENT_RECORD_PATH: "59d5e2c09c5a3ec08b1796807b97dccadd678b5a50fcaae6d699d3b0a86868cc",
    CLASSIFICATIONS_PATH: "d7feed1bdd5a7a8ee0eead002c598157c01dafe2d429b7c1c012978d39a38886",
    RESULT_PATH: "9a7eeae26ca7538b33f805f35ade421c528dd52745fd6c737fedb7c70acf6e97",
    MANIFEST_PATH: "3812c15c57b93b7d35dde44b4cdb3d4abff4f696b517fb6e7e216dab0b45671e",
}
EXPECTED_CONTENT_SCOPE = {
    DECISION_PATH: "decision_without_contentBinding",
    PASS_INPUT_PATH: "pass_input_without_contentBinding",
    PRIMARY_RECORD_PATH: "primary_pass_record_without_contentBinding",
    INDEPENDENT_RECORD_PATH: "independent_pass_record_without_contentBinding",
    CLASSIFICATIONS_PATH: "classifications_without_contentBinding",
    RESULT_PATH: "result_without_contentBinding",
    MANIFEST_PATH: "manifest_without_contentBinding",
}
EXPECTED_PUBLISHED_BYTES = {
    CLASSIFICATIONS_PATH: 58_144,
    RESULT_PATH: 5_067,
    MANIFEST_PATH: 5_290,
}

EXPECTED_REVIEW_ID = "g2-pion-ice-v4.3.0-rung3-semantic-source-review-v1"
EXPECTED_STATUS = (
    "rung3_semantic_source_review_v1_publication_read_back_complete_"
    "semantic_closure_blocked"
)
EXPECTED_RESULT = (
    "two_non_attesting_full_coverage_semantic_passes_published_and_"
    "independently_read_back_patch_and_dependency_gaps_remain"
)
EXPECTED_NEXT_ACTION = "prepare_versioned_rung3_patch_and_dependency_closure_decision"
EXPECTED_SOURCE_TREE_SHA256 = (
    "b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244"
)
EXPECTED_PATH_SET_SHA256 = (
    "bd01854baaec6ba818b8c48829a6202a60455a49e12057b9a10e98283b7451f9"
)
EXPECTED_ARCHIVE_SHA256 = (
    "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
)
EXPECTED_CANDIDATE_DIGESTS = {
    "primary": "66481cfac724c39b2dd8a2a721b1afe939cbb3c95a7752fee62a72d61ddc4038",
    "independent": "563eb28ca3aff18aa051584255bccf257ab80dbeb4f5ec1d9319dbad0d605edf",
}
EXPECTED_CANDIDATE_COUNTS = {"primary": 14, "independent": 15}
EXPECTED_RECORD_IDS = {
    "primary": (
        "g2-pion-ice-v4.3.0-rung3-semantic-source-review-primary-pass-record-v1"
    ),
    "independent": (
        "g2-pion-ice-v4.3.0-rung3-semantic-source-review-independent-pass-record-v1"
    ),
}
EXPECTED_RECORD_PATHS = {
    "primary": PRIMARY_RECORD_PATH,
    "independent": INDEPENDENT_RECORD_PATH,
}
PASS_IDS = ("primary", "independent")

INTEGRITY_LIMITATIONS = {
    "runnerBindingAttestsLoadedExecutingCode": False,
    "runnerBindingAttestsProcessIdentity": False,
    "runnerBindingIsAuthenticationOrAuthorityProof": False,
    "runnerBindingScope": "stable_on_disk_runner_file_bytes_sha256",
    "sameUidConcurrentMutationPrevented": False,
    "sameUidMutationAfterFinalReadbackDetectedByThisRunner": False,
    "sameUidMutationDetectionLimitedToStableReadbackWindows": True,
}
LOCATION_VALIDATION_BOUNDARY = {
    "goParserUsed": False,
    "semanticSinkReachabilityProven": False,
    "sourceClassDerivedFromPathValidated": True,
    "sourcePathMembershipValidatedAgainstSnapshot": True,
    "startAndEndLineBoundsValidatedAgainstSnapshot": True,
    "symbolResolutionPerformed": False,
}
POST_RUN_EVIDENCE_BOUNDARY = {
    "independentPostRunCheckerRequiredForFinalSuccessEvidence": True,
    "independentPostRunCheckerCompleted": False,
    "finalSuccessEvidenceEstablished": False,
}
PERSONAL_PROJECT_BOUNDARY = {
    "executionPermitAuthenticationRequired": False,
    "executionPermitDocumentRequired": False,
    "externalIdentityProofRequired": False,
    "repositoryOwnerAuthenticationRequired": False,
    "userActionRequired": False,
}
PERSONAL_PROJECT_RECORD_BOUNDARY = {
    **PERSONAL_PROJECT_BOUNDARY,
    "modelIdentityIsNotAuthenticationAuthority": True,
}
PERSONAL_PROJECT_DECISION_BOUNDARY = {
    **PERSONAL_PROJECT_BOUNDARY,
    "productEndpointAuthenticationChangedByThisDecision": False,
    "technicalSafetyGatesRemainRequired": True,
}
CANDIDATE_DIGEST_CONTRACT = {
    "algorithm": "sha256",
    "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
    "payload": "exact_candidateFindings_rows_matching_passId_in_pass_input_array_order",
    "scope": "canonical_json_array_of_exact_pass_candidate_rows_in_pass_input_order",
}
EXPECTED_COVERAGE = {
    "goSourceBodyReadCount": 100,
    "goSourceFileCount": 100,
    "goSourceLogicalLineCount": 39_064,
    "goSourceTotalBytes": 1_077_591,
    "lexicalObservationCount": 4_701,
    "lexicalRuleCount": 19,
    "observationSourceClassCounts": {
        "example": 117,
        "production": 1_546,
        "test": 3_038,
    },
    "patchUnitCount": 7,
    "reviewPassCount": 2,
    "semanticSourceReviewPerformed": True,
    "sourceFileClassCounts": {"example": 4, "production": 52, "test": 44},
    "verificationUnitCount": 8,
}
EXPECTED_SEVERITY_COUNTS = {"P0": 0, "P1": 11, "P2": 3, "P3": 4, "none": 1}
EXPECTED_DISPOSITION_COUNTS = {
    "acceptable_existing": 0,
    "false_positive": 0,
    "patch_required": 7,
    "unresolved": 12,
}
EXPECTED_CLOSURE = {
    "candidateSelected": False,
    "dependencyClosureComplete": False,
    "dependencySourceReviewed": False,
    "librarySelected": False,
    "rungThreeComplete": False,
    "semanticClosureComplete": False,
}
EXPECTED_NONCLAIMS = {
    "candidateSelected": False,
    "dependencyClosureComplete": False,
    "librarySelected": False,
    "productionDeploymentAuthorized": False,
    "rungThreeComplete": False,
}
PATCH_UNITS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)
VERIFICATION_UNIT_IDS = (
    "g2-r3-egress-path-coverage",
    "g2-r3-ingress-path-coverage",
    "g2-r3-address-and-resolution-adversarial",
    "g2-r3-turn-tls-service-identity",
    "g2-r3-secure-session-promotion",
    "g2-r3-resource-and-event-bounds",
    "g2-r3-secret-free-diagnostics",
    "g2-r3-deadline-shutdown",
)
DISPOSITIONS = frozenset(
    {"false_positive", "acceptable_existing", "patch_required", "unresolved"}
)
SEVERITIES = frozenset({"P0", "P1", "P2", "P3", "none"})
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "none": 4}
FINDING_ID_HASH_DOMAIN = (
    b"aetherlink.g2.pion.semantic-source-review.v1.finding-id\x00"
)
CANDIDATE_KEYS = {
    "candidateId",
    "canonicalInvariantId",
    "dedupGroupId",
    "dependencyBlocked",
    "findingKind",
    "locations",
    "originCandidateId",
    "passId",
    "patchUnits",
    "primarySink",
    "rationale",
    "reportedDisposition",
    "reportedInvariantId",
    "reportedSeverity",
    "requiredAction",
    "sourceClasses",
    "title",
    "verificationUnitIds",
}

MAXIMUM_TRACKED_FILE_BYTES = 4_194_304
READ_CHUNK_BYTES = 65_536
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
OBSERVATION_ID = re.compile(r"^G2SR1-O-[0-9a-f]{20}$")


class CheckError(ValueError):
    """The fixed semantic-review publication failed closed validation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def same_typed_value(value: Any, expected: Any) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(value) == set(expected) and all(
            same_typed_value(value[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(value) == len(expected) and all(
            same_typed_value(left, right) for left, right in zip(value, expected)
        )
    return value == expected


def require_exact(value: Any, expected: Any, label: str) -> None:
    require(same_typed_value(value, expected), f"{label}: mismatch")


def exact_object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    require(type(value) is dict and set(value) == keys, f"{label}: exact schema mismatch")
    return value


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def reject_nonfinite(value: Any, label: str) -> None:
    if isinstance(value, float):
        require(math.isfinite(value), f"{label}: non-finite number")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(child, label)
    elif isinstance(value, list):
        for child in value:
            reject_nonfinite(child, label)


def strict_canonical_json(raw: bytes, label: str) -> dict[str, Any]:
    require(
        raw.endswith(b"\n") and not raw.endswith(b"\n\n") and b"\r" not in raw,
        f"{label}: canonical single LF required",
    )
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise CheckError(f"{label}: strict UTF-8 required") from error

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"{label}: duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CheckError(f"{label}: non-finite JSON token {token}")
            ),
        )
    except (json.JSONDecodeError, TypeError) as error:
        raise CheckError(f"{label}: strict JSON required") from error
    require(type(value) is dict, f"{label}: top-level object required")
    reject_nonfinite(value, label)
    require(canonical_json_bytes(value) == raw, f"{label}: non-canonical JSON")
    return value


def validate_content_binding(
    document: Mapping[str, Any],
    *,
    path: str,
) -> None:
    binding = exact_object(
        document.get("contentBinding"),
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{path}.contentBinding",
    )
    require_exact(binding["algorithm"], "sha256", f"{path}.algorithm")
    require_exact(
        binding["canonicalization"],
        "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        f"{path}.canonicalization",
    )
    require_exact(binding["scope"], EXPECTED_CONTENT_SCOPE[path], f"{path}.scope")
    require_exact(binding["sha256"], EXPECTED_CONTENT_SHA256[path], f"{path}.self hash")
    payload = dict(document)
    payload.pop("contentBinding")
    require_exact(
        sha256_bytes(canonical_json_bytes(payload)),
        EXPECTED_CONTENT_SHA256[path],
        f"{path}.recomputed self hash",
    )


def _allowed_parts(path: str) -> tuple[str, ...]:
    require(path in ALLOWED_PATHS, f"unlisted fixed read: {path}")
    pure = PurePosixPath(path)
    require(
        not pure.is_absolute()
        and pure.parts
        and all(part not in ("", ".", "..") for part in pure.parts)
        and pure.as_posix() == path,
        f"unsafe fixed path: {path}",
    )
    require("build" not in pure.parts, f"build read forbidden: {path}")
    return pure.parts


def stable_metadata(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def named_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
    )


class FixedTrackedReader:
    """Component-wise, no-follow, no-enumeration fixed-path reader."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.read_paths: list[str] = []
        self.absence_checks: list[str] = []

    @staticmethod
    def _directory_flags() -> int:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        nonblock = getattr(os, "O_NONBLOCK", 0)
        require(
            nofollow != 0 and directory != 0 and nonblock != 0,
            "O_NOFOLLOW, O_DIRECTORY, and O_NONBLOCK required",
        )
        return (
            os.O_RDONLY
            | nofollow
            | directory
            | nonblock
            | getattr(os, "O_CLOEXEC", 0)
        )

    @staticmethod
    def _file_flags() -> int:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        nonblock = getattr(os, "O_NONBLOCK", 0)
        require(nofollow != 0 and nonblock != 0, "safe nonblocking file flags required")
        return os.O_RDONLY | nofollow | nonblock | getattr(os, "O_CLOEXEC", 0)

    def _open_directory_child(
        self,
        parent: int,
        component: str,
    ) -> dict[str, Any]:
        descriptor = -1
        try:
            named_before = os.stat(component, dir_fd=parent, follow_symlinks=False)
            descriptor = os.open(component, self._directory_flags(), dir_fd=parent)
            identity = os.fstat(descriptor)
            self._validate_directory(identity, component)
            named_after = os.stat(component, dir_fd=parent, follow_symlinks=False)
            require(
                named_identity(named_before) == named_identity(identity)
                and named_identity(identity) == named_identity(named_after),
                f"{component}: directory identity changed while opening",
            )
            handle = {
                "descriptor": descriptor,
                "metadata": identity,
                "name": component,
            }
            descriptor = -1
            return handle
        except OSError as error:
            raise CheckError(
                f"{component}: safe child-directory open failed: {error}"
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _close_directory_chain(chain: Sequence[Mapping[str, Any]]) -> None:
        for handle in reversed(chain):
            descriptor = handle.get("descriptor", -1)
            if isinstance(descriptor, int) and descriptor >= 0:
                os.close(descriptor)

    def _open_root(self) -> list[dict[str, Any]]:
        require(self.root.is_absolute(), "absolute repository root required")
        chain: list[dict[str, Any]] = []
        descriptor = -1
        try:
            descriptor = os.open(os.sep, self._directory_flags())
            identity = os.fstat(descriptor)
            self._validate_directory(identity, "filesystem root")
            chain.append(
                {
                    "descriptor": descriptor,
                    "metadata": identity,
                    "name": None,
                }
            )
            descriptor = -1
            for component in self.root.parts[1:]:
                chain.append(
                    self._open_directory_child(chain[-1]["descriptor"], component)
                )
            return chain
        except OSError as error:
            self._close_directory_chain(chain)
            raise CheckError(f"component-wise root open failed: {error}") from error
        except BaseException:
            self._close_directory_chain(chain)
            raise
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _open_parent(self, parts: tuple[str, ...]) -> list[dict[str, Any]]:
        chain = self._open_root()
        try:
            for component in parts[:-1]:
                chain.append(
                    self._open_directory_child(chain[-1]["descriptor"], component)
                )
            return chain
        except BaseException:
            self._close_directory_chain(chain)
            raise

    @staticmethod
    def _validate_directory(identity: os.stat_result, label: str) -> None:
        require(
            stat.S_ISDIR(identity.st_mode)
            and identity.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(identity.st_mode) & 0o022 == 0,
            f"{label}: unsafe directory owner or mode",
        )

    def _validate_directory_chain(
        self,
        chain: Sequence[Mapping[str, Any]],
        label: str,
    ) -> None:
        require(bool(chain), f"{label}: empty directory chain")
        for index, handle in enumerate(chain):
            descriptor = handle.get("descriptor")
            expected = handle.get("metadata")
            name = handle.get("name")
            require(
                isinstance(descriptor, int)
                and isinstance(expected, os.stat_result),
                f"{label}: malformed directory handle",
            )
            try:
                current = os.fstat(descriptor)
                self._validate_directory(current, f"{label}: directory {index}")
                require(
                    stable_metadata(current) == stable_metadata(expected),
                    f"{label}: directory metadata drift at component {index}",
                )
                if index == 0:
                    require(name is None, f"{label}: malformed filesystem-root handle")
                    continue
                require(
                    isinstance(name, str) and PurePosixPath(name).name == name,
                    f"{label}: unsafe held directory name",
                )
                parent = chain[index - 1].get("descriptor")
                require(isinstance(parent, int), f"{label}: malformed parent handle")
                named = os.stat(name, dir_fd=parent, follow_symlinks=False)
                require(
                    named_identity(current) == named_identity(named),
                    f"{label}: directory ancestry drift at {name}",
                )
            except OSError as error:
                raise CheckError(
                    f"{label}: directory-chain validation failed: {error}"
                ) from error

    @staticmethod
    def _read_exact(descriptor: int, expected_size: int) -> bytes:
        remaining = expected_size + 1
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(READ_CHUNK_BYTES, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _open_held(self, path: str) -> tuple[bytes, os.stat_result, dict[str, Any]]:
        parts = _allowed_parts(path)
        directory_chain = self._open_parent(parts)
        parent = directory_chain[-1]["descriptor"]
        descriptor = -1
        try:
            name = parts[-1]
            named_before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            descriptor = os.open(name, self._file_flags(), dir_fd=parent)
            before = os.fstat(descriptor)
            require(
                stat.S_ISREG(before.st_mode)
                and before.st_uid == os.geteuid()
                and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) & 0o022 == 0
                and 0 < before.st_size <= MAXIMUM_TRACKED_FILE_BYTES,
                f"{path}: fixed file metadata mismatch",
            )
            if path in PUBLISHED_PATHS:
                require(
                    stat.S_IMODE(before.st_mode) == 0o600
                    and before.st_size == EXPECTED_PUBLISHED_BYTES[path],
                    f"{path}: published mode or byte count mismatch",
                )
            require(
                named_identity(named_before) == named_identity(before),
                f"{path}: named inode mismatch",
            )
            raw = self._read_exact(descriptor, before.st_size)
            after = os.fstat(descriptor)
            named_after = os.stat(name, dir_fd=parent, follow_symlinks=False)
            require(
                len(raw) == before.st_size
                and stable_metadata(before) == stable_metadata(after)
                and named_identity(after) == named_identity(named_after),
                f"{path}: unstable fixed read",
            )
            self.read_paths.append(path)
            handle = {
                "descriptor": descriptor,
                "directoryChain": directory_chain,
                "metadata": after,
                "name": name,
                "parent": parent,
                "path": path,
            }
            descriptor = -1
            directory_chain = []
            return raw, after, handle
        except OSError as error:
            raise CheckError(f"{path}: safe fixed read failed: {error}") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            self._close_directory_chain(directory_chain)

    def read(self, path: str) -> tuple[bytes, os.stat_result]:
        raw, metadata, handle = self._open_held(path)
        self.close_handles((handle,))
        return raw, metadata

    def require_absent_output_names(self) -> None:
        parts = _allowed_parts(MANIFEST_PATH)
        directory_chain = self._open_parent(parts)
        parent = directory_chain[-1]["descriptor"]
        try:
            for name in ABSENT_NAMES:
                require(PurePosixPath(name).name == name, f"unsafe absence name: {name}")
                try:
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    self.absence_checks.append(name)
                    continue
                except OSError as error:
                    raise CheckError(f"{name}: exact absence check failed: {error}") from error
                raise CheckError(f"{name}: failure or staging artifact must be absent")
        finally:
            self._close_directory_chain(directory_chain)

    def open_all_held(
        self,
    ) -> tuple[dict[str, bytes], dict[str, os.stat_result], list[dict[str, Any]]]:
        self.require_absent_output_names()
        raw: dict[str, bytes] = {}
        metadata: dict[str, os.stat_result] = {}
        handles: list[dict[str, Any]] = []
        try:
            for path in ALLOWED_PATHS:
                raw[path], metadata[path], handle = self._open_held(path)
                handles.append(handle)
            return raw, metadata, handles
        except BaseException:
            self.close_handles(handles)
            raise

    def reread_held(
        self,
        handles: Sequence[Mapping[str, Any]],
    ) -> dict[str, bytes]:
        require(
            [handle.get("path") for handle in handles] == list(ALLOWED_PATHS),
            "held descriptor order mismatch",
        )
        raw: dict[str, bytes] = {}
        for handle in handles:
            path = handle["path"]
            descriptor = handle["descriptor"]
            parent = handle["parent"]
            name = handle["name"]
            expected = handle["metadata"]
            try:
                self._validate_directory_chain(
                    handle["directoryChain"], f"{path}: before final read"
                )
                before = os.fstat(descriptor)
                named_before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                require(
                    stable_metadata(before) == stable_metadata(expected)
                    and named_identity(before) == named_identity(named_before),
                    f"{path}: held identity drifted before final read",
                )
                os.lseek(descriptor, 0, os.SEEK_SET)
                payload = self._read_exact(descriptor, before.st_size)
                after = os.fstat(descriptor)
                named_after = os.stat(name, dir_fd=parent, follow_symlinks=False)
                require(
                    len(payload) == before.st_size
                    and stable_metadata(before) == stable_metadata(after)
                    and named_identity(after) == named_identity(named_after),
                    f"{path}: held final read drifted",
                )
                self._validate_directory_chain(
                    handle["directoryChain"], f"{path}: after final read"
                )
                raw[path] = payload
                self.read_paths.append(path)
            except OSError as error:
                raise CheckError(f"{path}: held final read failed: {error}") from error
        return raw

    def final_identity_barrier(
        self,
        handles: Sequence[Mapping[str, Any]],
    ) -> None:
        for handle in handles:
            path = handle["path"]
            try:
                self._validate_directory_chain(
                    handle["directoryChain"], f"{path}: final identity barrier"
                )
                current = os.fstat(handle["descriptor"])
                named = os.stat(
                    handle["name"],
                    dir_fd=handle["parent"],
                    follow_symlinks=False,
                )
            except OSError as error:
                raise CheckError(f"{path}: final identity barrier failed: {error}") from error
            require(
                stable_metadata(current) == stable_metadata(handle["metadata"])
                and named_identity(current) == named_identity(named),
                f"{path}: final identity barrier detected drift",
            )

    @staticmethod
    def close_handles(handles: Sequence[Mapping[str, Any]]) -> None:
        for handle in reversed(handles):
            descriptor = handle.get("descriptor", -1)
            if isinstance(descriptor, int) and descriptor >= 0:
                os.close(descriptor)
            directory_chain = handle.get("directoryChain", ())
            if isinstance(directory_chain, Sequence):
                FixedTrackedReader._close_directory_chain(directory_chain)


def expected_decision_binding() -> dict[str, str]:
    return {
        "contentSha256": EXPECTED_CONTENT_SHA256[DECISION_PATH],
        "path": DECISION_PATH,
        "rawSha256": EXPECTED_RAW_SHA256[DECISION_PATH],
    }


def expected_pass_input_binding() -> dict[str, str]:
    return {
        "contentSha256": EXPECTED_CONTENT_SHA256[PASS_INPUT_PATH],
        "path": PASS_INPUT_PATH,
        "rawSha256": EXPECTED_RAW_SHA256[PASS_INPUT_PATH],
    }


def expected_runner_binding() -> dict[str, str]:
    return {"path": RUNNER_PATH, "rawSha256": EXPECTED_RAW_SHA256[RUNNER_PATH]}


def expected_record_binding(pass_id: str) -> dict[str, str]:
    path = EXPECTED_RECORD_PATHS[pass_id]
    return {
        "contentSha256": EXPECTED_CONTENT_SHA256[path],
        "passId": pass_id,
        "path": path,
        "rawSha256": EXPECTED_RAW_SHA256[path],
        "recordId": EXPECTED_RECORD_IDS[pass_id],
    }


def expected_candidate_binding(pass_id: str, *, public: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "algorithm": "sha256",
        "candidateCount": EXPECTED_CANDIDATE_COUNTS[pass_id],
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "canonical_json_array_of_exact_pass_candidate_rows_in_pass_input_order",
        "sha256": EXPECTED_CANDIDATE_DIGESTS[pass_id],
    }
    if public:
        result = {"passId": pass_id, **result}
    return result


def require_safe_source_path(value: Any, label: str) -> str:
    require(type(value) is str and value, f"{label}: nonempty path required")
    path = PurePosixPath(value)
    require(
        not path.is_absolute()
        and path.parts
        and all(part not in ("", ".", "..") for part in path.parts)
        and path.as_posix() == value,
        f"{label}: unsafe path",
    )
    return value


def validate_candidate_row(candidate: Mapping[str, Any], *, label: str) -> None:
    exact_object(candidate, CANDIDATE_KEYS, label)
    for key in (
        "candidateId",
        "canonicalInvariantId",
        "dedupGroupId",
        "findingKind",
        "rationale",
        "reportedInvariantId",
        "requiredAction",
        "title",
    ):
        require(type(candidate[key]) is str and candidate[key], f"{label}.{key}")
    require(candidate["dedupGroupId"].startswith("G-"), f"{label}.dedupGroupId")
    require(candidate["passId"] in PASS_IDS, f"{label}.passId")
    require(candidate["reportedDisposition"] in DISPOSITIONS, f"{label}.disposition")
    require(candidate["reportedSeverity"] in SEVERITIES, f"{label}.severity")
    require(type(candidate["dependencyBlocked"]) is bool, f"{label}.dependencyBlocked")
    origin = candidate["originCandidateId"]
    require(origin is None or (type(origin) is str and origin), f"{label}.originCandidateId")
    for key, allowed in (
        ("patchUnits", PATCH_UNITS),
        ("verificationUnitIds", VERIFICATION_UNIT_IDS),
    ):
        values = candidate[key]
        require(
            type(values) is list
            and len(values) == len(set(values))
            and all(type(value) is str and value in allowed for value in values),
            f"{label}.{key}",
        )
    source_classes = candidate["sourceClasses"]
    require(
        type(source_classes) is list
        and source_classes
        and len(source_classes) == len(set(source_classes))
        and all(value in {"example", "production", "test", "dependency"} for value in source_classes),
        f"{label}.sourceClasses",
    )
    locations = candidate["locations"]
    require(type(locations) is list, f"{label}.locations")
    location_keys: set[tuple[str, int, int, str]] = set()
    for index, location in enumerate(locations):
        location = exact_object(
            location,
            {"endLine", "path", "startLine", "symbol"},
            f"{label}.locations[{index}]",
        )
        path = require_safe_source_path(location["path"], f"{label}.locations[{index}].path")
        start = location["startLine"]
        end = location["endLine"]
        symbol = location["symbol"]
        require(
            type(start) is int
            and type(end) is int
            and 1 <= start <= end
            and type(symbol) is str
            and symbol,
            f"{label}.locations[{index}].bounds",
        )
        location_keys.add((path, start, end, symbol))
    require(len(location_keys) == len(locations), f"{label}.duplicate locations")
    sink = candidate["primarySink"]
    if sink is not None:
        sink = exact_object(sink, {"line", "path", "symbol"}, f"{label}.primarySink")
        require_safe_source_path(sink["path"], f"{label}.primarySink.path")
        require(
            type(sink["line"]) is int
            and sink["line"] >= 1
            and type(sink["symbol"]) is str
            and sink["symbol"],
            f"{label}.primarySink",
        )


def rebuild_findings(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate["dedupGroupId"], []).append(candidate)
    require(len(grouped) == 19, "candidate dedup group count")
    findings: list[dict[str, Any]] = []
    for group_id in sorted(grouped, key=lambda value: value.encode("utf-8")):
        rows = sorted(grouped[group_id], key=lambda row: PASS_IDS.index(row["passId"]))
        require(
            1 <= len(rows) <= 2
            and len({row["passId"] for row in rows}) == len(rows),
            f"{group_id}: duplicate pass in dedup group",
        )
        first = rows[0]
        for row in rows[1:]:
            require(
                row["canonicalInvariantId"] == first["canonicalInvariantId"]
                and row["findingKind"] == first["findingKind"]
                and same_typed_value(row["primarySink"], first["primarySink"]),
                f"{group_id}: fuzzy semantic merge",
            )
        dispositions = [row["reportedDisposition"] for row in rows]
        final_disposition = (
            dispositions[0]
            if len(rows) == 2 and dispositions[0] == dispositions[1]
            else "unresolved"
        )
        severities = [row["reportedSeverity"] for row in rows]
        final_severity = min(severities, key=lambda value: SEVERITY_ORDER[value])
        identity_payload = canonical_json_bytes(
            {
                "canonicalInvariantId": first["canonicalInvariantId"],
                "findingKind": first["findingKind"],
                "primarySink": first["primarySink"],
            }
        )
        finding_id = (
            "G2SR1-F-"
            + hashlib.sha256(FINDING_ID_HASH_DOMAIN + identity_payload).hexdigest()[:20]
        )
        location_map: dict[tuple[str, int, int, str], dict[str, Any]] = {}
        reports: list[dict[str, Any]] = []
        for row in rows:
            for location in row["locations"]:
                key = (
                    location["path"],
                    location["startLine"],
                    location["endLine"],
                    location["symbol"],
                )
                location_map[key] = dict(location)
            reports.append(
                {
                    "candidateId": row["candidateId"],
                    "passId": row["passId"],
                    "rationale": row["rationale"],
                    "reportedDisposition": row["reportedDisposition"],
                    "reportedInvariantId": row["reportedInvariantId"],
                    "reportedSeverity": row["reportedSeverity"],
                    "requiredAction": row["requiredAction"],
                    "title": row["title"],
                }
            )
        locations = [
            location_map[key]
            for key in sorted(
                location_map,
                key=lambda value: (
                    value[0].encode("utf-8"),
                    value[1],
                    value[2],
                    value[3].encode("utf-8"),
                ),
            )
        ]
        findings.append(
            {
                "canonicalInvariantId": first["canonicalInvariantId"],
                "dedupGroupId": group_id,
                "dependencyBlocked": any(row["dependencyBlocked"] for row in rows),
                "dispositionAgreement": (
                    len(rows) == 2 and dispositions[0] == dispositions[1]
                ),
                "finalDisposition": final_disposition,
                "finalSeverity": final_severity,
                "findingId": finding_id,
                "findingKind": first["findingKind"],
                "locations": locations,
                "passReports": reports,
                "patchUnits": sorted(
                    {unit for row in rows for unit in row["patchUnits"]},
                    key=lambda value: PATCH_UNITS.index(value),
                ),
                "primarySink": first["primarySink"],
                "severityAgreement": len(rows) == 2 and severities[0] == severities[1],
                "verificationUnitIds": sorted(
                    {unit for row in rows for unit in row["verificationUnitIds"]},
                    key=lambda value: VERIFICATION_UNIT_IDS.index(value),
                ),
            }
        )
    resolution = next(
        finding
        for finding in findings
        if finding["dedupGroupId"] == "G-RESOLUTION-GATHER"
    )
    require(
        resolution["finalDisposition"] == "unresolved"
        and resolution["dispositionAgreement"] is False,
        "resolution disagreement must remain unresolved",
    )
    gap = next(
        finding for finding in findings if finding["dedupGroupId"] == "G-ONE-USE-GAP"
    )
    require(
        gap["finalSeverity"] == "none"
        and gap["finalDisposition"] == "unresolved"
        and gap["locations"] == []
        and gap["primarySink"] is None,
        "one-use missing-mechanism boundary",
    )
    return findings


def validate_decision(document: Mapping[str, Any]) -> None:
    exact_object(
        document,
        {
            "archiveIdentity",
            "contentBinding",
            "decisionId",
            "documentType",
            "nextAction",
            "nonClaims",
            "operationBoundary",
            "personalProjectBoundary",
            "predecessorBindings",
            "publicationContract",
            "recordedDate",
            "resourceLimits",
            "result",
            "reviewCoverage",
            "schemaVersion",
            "semanticContract",
            "status",
        },
        "decision",
    )
    require_exact(
        document.get("documentType"),
        "aetherlink.g2-pion-rung3-semantic-source-review-decision",
        "decision.documentType",
    )
    require_exact(document.get("schemaVersion"), "1.0", "decision.schemaVersion")
    require_exact(
        document.get("decisionId"),
        "g2-pion-ice-v4.3.0-rung3-semantic-source-review-decision-v1",
        "decision.decisionId",
    )
    require_exact(
        document.get("personalProjectBoundary"),
        PERSONAL_PROJECT_DECISION_BOUNDARY,
        "decision.personalProjectBoundary",
    )
    nonclaims = document.get("nonClaims")
    require(type(nonclaims) is dict and nonclaims, "decision.nonClaims required")
    require(all(value is False for value in nonclaims.values()), "decision.nonClaims must remain false")


def validate_pass_records(
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    bindings: list[dict[str, str]] = []
    for pass_id in PASS_IDS:
        path = EXPECTED_RECORD_PATHS[pass_id]
        document = documents[path]
        exact_object(
            document,
            {
                "attempts",
                "candidateIds",
                "candidateSemanticBinding",
                "contentBinding",
                "coverage",
                "coverageAndCandidateRecordOnly",
                "dependencyBoundary",
                "documentType",
                "engineIdentityAttested",
                "inputBindings",
                "integrityLimitations",
                "locationValidationBoundary",
                "nonClaims",
                "oneUseZeroHitBoundary",
                "operationCounters",
                "passId",
                "passRecordId",
                "personalProjectBoundary",
                "recordContainsSecretValues",
                "recordContainsSourceBodies",
                "recordContainsSourceLineDigests",
                "recordIsAuthenticationAuthority",
                "recordIsSigned",
                "recordedDate",
                "reviewEngine",
                "reviewedGoSourcePathSet",
                "schemaVersion",
                "semanticJudgmentsIndependentlyReproducedByRecord",
                "status",
                "successfulAttempt",
                "writeBoundary",
            },
            f"{pass_id}.record",
        )
        require_exact(document.get("passId"), pass_id, f"{pass_id}.passId")
        require_exact(
            document.get("documentType"),
            f"aetherlink.g2-pion-rung3-semantic-source-review-{pass_id}-pass-record",
            f"{pass_id}.documentType",
        )
        require_exact(document.get("schemaVersion"), "1.0", f"{pass_id}.schemaVersion")
        require_exact(document.get("passRecordId"), EXPECTED_RECORD_IDS[pass_id], f"{pass_id}.recordId")
        require_exact(document.get("status"), "pass_completed_recorded_non_attesting", f"{pass_id}.status")
        require_exact(document.get("reviewEngine"), "gpt-5.6-sol", f"{pass_id}.reviewEngine")
        for key in (
            "engineIdentityAttested",
            "recordIsAuthenticationAuthority",
            "recordIsSigned",
            "recordContainsSecretValues",
            "recordContainsSourceBodies",
            "recordContainsSourceLineDigests",
            "semanticJudgmentsIndependentlyReproducedByRecord",
        ):
            require(document.get(key) is False, f"{pass_id}.{key} must be false")
        require(document.get("coverageAndCandidateRecordOnly") is True, f"{pass_id}.coverage boundary")
        require_exact(document.get("integrityLimitations"), INTEGRITY_LIMITATIONS, f"{pass_id}.integrity")
        require_exact(document.get("locationValidationBoundary"), LOCATION_VALIDATION_BOUNDARY, f"{pass_id}.location")
        require_exact(document.get("personalProjectBoundary"), PERSONAL_PROJECT_RECORD_BOUNDARY, f"{pass_id}.personal")
        require_exact(document.get("candidateSemanticBinding"), expected_candidate_binding(pass_id, public=False), f"{pass_id}.candidate binding")
        coverage = document.get("coverage")
        require(type(coverage) is dict, f"{pass_id}.coverage required")
        require_exact(coverage.get("goSourceFileCount"), 100, f"{pass_id}.source count")
        require_exact(coverage.get("lexicalObservationCount"), 4_701, f"{pass_id}.observation count")
        require_exact(coverage.get("patchUnitCount"), 7, f"{pass_id}.patch unit count")
        require_exact(coverage.get("lexicalRuleCount"), 19, f"{pass_id}.rule count")
        require_exact(coverage.get("verificationUnitCount"), 8, f"{pass_id}.verification count")
        require_exact(coverage.get("sourceTreeSha256"), EXPECTED_SOURCE_TREE_SHA256, f"{pass_id}.source tree")
        path_set = document.get("reviewedGoSourcePathSet")
        require(type(path_set) is dict, f"{pass_id}.path set required")
        require_exact(path_set.get("count"), 100, f"{pass_id}.path count")
        require(type(path_set.get("paths")) is list and len(path_set["paths"]) == 100, f"{pass_id}.paths")
        require_exact(path_set.get("sha256"), EXPECTED_PATH_SET_SHA256, f"{pass_id}.path-set digest")
        dependency = document.get("dependencyBoundary")
        require(type(dependency) is dict, f"{pass_id}.dependency required")
        require(dependency.get("dependencySourceReviewed") is False, f"{pass_id}.dependency review")
        require(dependency.get("dependencyClosureComplete") is False, f"{pass_id}.dependency closure")
        require_exact(dependency.get("goModRequireCount"), 19, f"{pass_id}.go.mod count")
        require_exact(dependency.get("goSumRecordCount"), 44, f"{pass_id}.go.sum count")
        nonclaims = document.get("nonClaims")
        require(type(nonclaims) is dict and nonclaims, f"{pass_id}.nonClaims required")
        require(all(value is False for value in nonclaims.values()), f"{pass_id}.nonClaims")
        bindings.append(expected_record_binding(pass_id))
    return bindings


def validate_pass_input(
    document: Mapping[str, Any],
    record_bindings: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact_object(
        document,
        {
            "candidateFindings",
            "candidateSemanticDigestContract",
            "contentBinding",
            "decisionBinding",
            "dependencyBoundary",
            "documentType",
            "inputId",
            "integrityLimitations",
            "locationValidationBoundary",
            "nonClaims",
            "passDeclarations",
            "passRecordBindings",
            "personalProjectBoundary",
            "recordedDate",
            "schemaVersion",
            "status",
            "unitDigests",
            "verificationUnitIds",
        },
        "passInput",
    )
    require_exact(
        document.get("documentType"),
        "aetherlink.g2-pion-rung3-semantic-source-review-pass-input",
        "passInput.documentType",
    )
    require_exact(document.get("schemaVersion"), "1.0", "passInput.schemaVersion")
    require_exact(
        document.get("status"),
        "two_completed_semantic_review_passes_recorded_for_prepublication_validation",
        "passInput.status",
    )
    require_exact(
        document.get("decisionBinding"),
        {
            **expected_decision_binding(),
            "decisionId": "g2-pion-ice-v4.3.0-rung3-semantic-source-review-decision-v1",
        },
        "passInput.decisionBinding",
    )
    require_exact(document.get("passRecordBindings"), list(record_bindings), "passInput.passRecordBindings")
    require_exact(document.get("candidateSemanticDigestContract"), CANDIDATE_DIGEST_CONTRACT, "passInput.digest contract")
    require_exact(document.get("integrityLimitations"), INTEGRITY_LIMITATIONS, "passInput.integrity")
    require_exact(document.get("locationValidationBoundary"), LOCATION_VALIDATION_BOUNDARY, "passInput.location")
    require_exact(document.get("personalProjectBoundary"), PERSONAL_PROJECT_RECORD_BOUNDARY, "passInput.personal")
    candidates = document.get("candidateFindings")
    require(type(candidates) is list and len(candidates) == 29, "passInput.candidate count")
    candidate_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        require(type(candidate) is dict, f"passInput.candidate[{index}]")
        validate_candidate_row(candidate, label=f"passInput.candidate[{index}]")
        candidate_id = candidate["candidateId"]
        require(candidate_id not in candidate_ids, "duplicate candidate ID")
        candidate_ids.add(candidate_id)
    public_bindings: list[dict[str, Any]] = []
    for pass_id in PASS_IDS:
        rows = [row for row in candidates if type(row) is dict and row.get("passId") == pass_id]
        require_exact(len(rows), EXPECTED_CANDIDATE_COUNTS[pass_id], f"{pass_id}.candidate count")
        digest = sha256_bytes(canonical_json_bytes(rows))
        require_exact(digest, EXPECTED_CANDIDATE_DIGESTS[pass_id], f"{pass_id}.candidate digest")
        public_bindings.append(expected_candidate_binding(pass_id, public=True))
    declarations = document.get("passDeclarations")
    require(type(declarations) is list and len(declarations) == 2, "passInput.passDeclarations")
    require_exact([row.get("passId") for row in declarations], list(PASS_IDS), "pass declaration order")
    for declaration, pass_id in zip(declarations, PASS_IDS):
        ids = declaration.get("candidateIds")
        expected_ids = [row["candidateId"] for row in candidates if row.get("passId") == pass_id]
        require_exact(ids, expected_ids, f"{pass_id}.candidate ID order")
    dependency = document.get("dependencyBoundary")
    require_exact(
        dependency,
        {
            "dependencyClosureComplete": False,
            "dependencySourceReviewed": False,
            "goModRequireCount": 19,
            "goSumRecordCount": 44,
        },
        "passInput.dependencyBoundary",
    )
    nonclaims = document.get("nonClaims")
    require(type(nonclaims) is dict and nonclaims, "passInput.nonClaims required")
    require(all(value is False for value in nonclaims.values()), "passInput.nonClaims")
    return public_bindings, rebuild_findings(candidates)


def validate_shared_output_bindings(
    document: Mapping[str, Any],
    *,
    label: str,
    record_bindings: Sequence[Mapping[str, str]],
    candidate_bindings: Sequence[Mapping[str, Any]],
) -> None:
    require_exact(document.get("runnerBinding"), expected_runner_binding(), f"{label}.runnerBinding")
    require_exact(document.get("passRecordBindings"), list(record_bindings), f"{label}.passRecordBindings")
    require_exact(document.get("passCandidateSemanticBindings"), list(candidate_bindings), f"{label}.candidate bindings")
    require(document.get("passRecordsNonAttesting") is True, f"{label}.passRecordsNonAttesting")
    require(document.get("semanticJudgmentsIndependentlyReproducedByRunner") is False, f"{label}.runner reproduction")
    require(document.get("coverageAndLocationBoundsValidatedAgainstSnapshot") is True, f"{label}.coverage bounds")
    require_exact(document.get("integrityLimitations"), INTEGRITY_LIMITATIONS, f"{label}.integrity")
    require_exact(document.get("locationValidationBoundary"), LOCATION_VALIDATION_BOUNDARY, f"{label}.location")
    require_exact(document.get("postRunEvidenceBoundary"), POST_RUN_EVIDENCE_BOUNDARY, f"{label}.postRun boundary")
    require_exact(document.get("personalProjectBoundary"), PERSONAL_PROJECT_BOUNDARY, f"{label}.personal")


def validate_classifications(
    document: Mapping[str, Any],
    *,
    record_bindings: Sequence[Mapping[str, str]],
    candidate_bindings: Sequence[Mapping[str, Any]],
    expected_findings: Sequence[Mapping[str, Any]],
) -> None:
    exact_object(
        document,
        {
            "archiveSnapshot",
            "candidateClassification",
            "contentBinding",
            "coverageAndLocationBoundsValidatedAgainstSnapshot",
            "decisionBinding",
            "dependencyBoundary",
            "documentType",
            "integrityLimitations",
            "locationValidationBoundary",
            "nonClaims",
            "observationClassification",
            "passCandidateSemanticBindings",
            "passInputBinding",
            "passRecordBindings",
            "passRecordsNonAttesting",
            "personalProjectBoundary",
            "postRunEvidenceBoundary",
            "recordedDate",
            "reviewId",
            "runnerBinding",
            "schemaVersion",
            "semanticJudgmentsIndependentlyReproducedByRunner",
            "status",
        },
        "classifications",
    )
    require_exact(document.get("documentType"), "aetherlink.g2-pion-rung3-semantic-source-review-classifications", "classifications.documentType")
    require_exact(document.get("schemaVersion"), "1.0", "classifications.schemaVersion")
    require_exact(document.get("reviewId"), EXPECTED_REVIEW_ID, "classifications.reviewId")
    require_exact(document.get("status"), "two_pass_semantic_classification_validated", "classifications.status")
    require_exact(document.get("decisionBinding"), expected_decision_binding(), "classifications.decisionBinding")
    require_exact(document.get("passInputBinding"), expected_pass_input_binding(), "classifications.passInputBinding")
    validate_shared_output_bindings(
        document,
        label="classifications",
        record_bindings=record_bindings,
        candidate_bindings=candidate_bindings,
    )
    archive = document.get("archiveSnapshot")
    require(type(archive) is dict, "classifications.archiveSnapshot")
    require_exact(archive.get("rawSha256"), EXPECTED_ARCHIVE_SHA256, "classifications.archive digest")
    require_exact(archive.get("sourceTreeSha256"), EXPECTED_SOURCE_TREE_SHA256, "classifications.source tree")
    require_exact(archive.get("entryCount"), 129, "classifications.archive entries")
    require(archive.get("filesystemExtracted") is False and archive.get("reviewedSourceExecuted") is False, "classifications.archive boundary")
    observations = document.get("observationClassification")
    require(type(observations) is dict, "classifications.observationClassification")
    require(observations.get("complete") is True, "classifications.observation completion")
    require_exact(observations.get("observationCountPerPass"), {"primary": 4_701, "independent": 4_701}, "classifications.observation counts")
    require(type(observations.get("patchUnits")) is list and len(observations["patchUnits"]) == 7, "classifications.patch units")
    crosswalks = observations.get("candidateCrosswalks")
    require(type(crosswalks) is list and len(crosswalks) == 19, "classifications.crosswalk count")
    candidates = document.get("candidateClassification")
    require(type(candidates) is dict, "classifications.candidateClassification")
    require_exact(candidates.get("inputCandidateCount"), 29, "classifications.input candidates")
    require_exact(candidates.get("deduplicatedFindingCount"), 19, "classifications.finding count")
    require_exact(candidates.get("severityCounts"), EXPECTED_SEVERITY_COUNTS, "classifications.severity counts")
    require_exact(candidates.get("dispositionCounts"), EXPECTED_DISPOSITION_COUNTS, "classifications.disposition counts")
    findings = candidates.get("findings")
    require(type(findings) is list and len(findings) == 19, "classifications.findings")
    require_exact(findings, list(expected_findings), "classifications.rebuilt findings")
    require(len({row.get("findingId") for row in findings}) == 19, "classifications.finding IDs unique")
    severity_counts = {key: 0 for key in EXPECTED_SEVERITY_COUNTS}
    disposition_counts = {key: 0 for key in EXPECTED_DISPOSITION_COUNTS}
    for finding in findings:
        require(type(finding) is dict, "classifications.finding object")
        severity = finding.get("finalSeverity")
        disposition = finding.get("finalDisposition")
        require(severity in severity_counts, "classifications.finding severity")
        require(disposition in disposition_counts, "classifications.finding disposition")
        severity_counts[severity] += 1
        disposition_counts[disposition] += 1
        locations = finding.get("locations")
        require(type(locations) is list, "classifications.finding locations")
        if not locations:
            require(finding.get("primarySink") is None, "location-free finding sink")
        else:
            require(type(finding.get("primarySink")) is dict, "located finding sink")
        require(type(finding.get("passReports")) is list and finding["passReports"], "classifications.finding reports")
    require_exact(severity_counts, EXPECTED_SEVERITY_COUNTS, "classifications.recomputed severities")
    require_exact(disposition_counts, EXPECTED_DISPOSITION_COUNTS, "classifications.recomputed dispositions")
    require_exact(
        [row.get("findingId") for row in crosswalks],
        [row["findingId"] for row in findings],
        "classifications.crosswalk finding order",
    )
    for crosswalk, finding in zip(crosswalks, findings):
        crosswalk = exact_object(
            crosswalk,
            {
                "findingId",
                "linkedObservationCount",
                "linkedObservationIds",
                "locationCount",
            },
            "classifications.crosswalk",
        )
        observation_ids = crosswalk["linkedObservationIds"]
        require(
            type(observation_ids) is list
            and observation_ids == sorted(observation_ids)
            and len(observation_ids) == len(set(observation_ids))
            and all(type(value) is str and OBSERVATION_ID.fullmatch(value) for value in observation_ids),
            "classifications.crosswalk observation IDs",
        )
        require_exact(crosswalk["linkedObservationCount"], len(observation_ids), "crosswalk observation count")
        require_exact(crosswalk["locationCount"], len(finding["locations"]), "crosswalk location count")
    require_exact(document.get("dependencyBoundary"), {"dependencyClosureComplete": False, "dependencySourceReviewed": False, "goModRequireCount": 19, "goSumRecordCount": 44}, "classifications.dependency")
    require_exact(document.get("nonClaims"), EXPECTED_NONCLAIMS, "classifications.nonClaims")


def validate_result(
    document: Mapping[str, Any],
    *,
    record_bindings: Sequence[Mapping[str, str]],
    candidate_bindings: Sequence[Mapping[str, Any]],
) -> None:
    exact_object(
        document,
        {
            "closure",
            "contentBinding",
            "coverage",
            "coverageAndLocationBoundsValidatedAgainstSnapshot",
            "decisionBinding",
            "documentType",
            "findingAudit",
            "integrityLimitations",
            "locationValidationBoundary",
            "nextAction",
            "passCandidateSemanticBindings",
            "passInputBinding",
            "passRecordBindings",
            "passRecordsNonAttesting",
            "personalProjectBoundary",
            "postRunEvidenceBoundary",
            "recordedDate",
            "result",
            "reviewId",
            "runnerBinding",
            "schemaVersion",
            "semanticJudgmentsIndependentlyReproducedByRunner",
            "status",
        },
        "result",
    )
    require_exact(document.get("documentType"), "aetherlink.g2-pion-rung3-semantic-source-review-result", "result.documentType")
    require_exact(document.get("schemaVersion"), "1.0", "result.schemaVersion")
    require_exact(document.get("reviewId"), EXPECTED_REVIEW_ID, "result.reviewId")
    require_exact(document.get("status"), "rung3_semantic_source_review_v1_executed_semantic_closure_blocked", "result.status")
    require_exact(document.get("result"), "two_pass_100_file_4701_observation_review_recorded_findings_and_dependency_gaps_remain", "result.result")
    require_exact(document.get("nextAction"), EXPECTED_NEXT_ACTION, "result.nextAction")
    require_exact(document.get("decisionBinding"), expected_decision_binding(), "result.decisionBinding")
    require_exact(document.get("passInputBinding"), expected_pass_input_binding(), "result.passInputBinding")
    validate_shared_output_bindings(
        document,
        label="result",
        record_bindings=record_bindings,
        candidate_bindings=candidate_bindings,
    )
    require_exact(document.get("coverage"), EXPECTED_COVERAGE, "result.coverage")
    require_exact(
        document.get("findingAudit"),
        {
            "deduplicatedFindingCount": 19,
            "disagreementsForcedUnresolved": True,
            "dispositionCounts": EXPECTED_DISPOSITION_COUNTS,
            "inputCandidateCount": 29,
            "oneUseMissingMechanismGapRecorded": True,
            "severityCounts": EXPECTED_SEVERITY_COUNTS,
        },
        "result.findingAudit",
    )
    require_exact(document.get("closure"), EXPECTED_CLOSURE, "result.closure")


def validate_manifest(
    document: Mapping[str, Any],
    *,
    record_bindings: Sequence[Mapping[str, str]],
    candidate_bindings: Sequence[Mapping[str, Any]],
) -> None:
    exact_object(
        document,
        {
            "artifacts",
            "contentBinding",
            "coverageAndLocationBoundsValidatedAgainstSnapshot",
            "documentType",
            "integrityLimitations",
            "locationValidationBoundary",
            "nonClaims",
            "passCandidateSemanticBindings",
            "passRecordBindings",
            "passRecordsNonAttesting",
            "personalProjectBoundary",
            "postRunEvidenceBoundary",
            "preCommitOperationCounters",
            "publicationContract",
            "recordedDate",
            "reviewId",
            "runnerBinding",
            "schemaVersion",
            "semanticJudgmentsIndependentlyReproducedByRunner",
            "status",
            "transactionalPublicationBoundary",
        },
        "manifest",
    )
    require_exact(document.get("documentType"), "aetherlink.g2-pion-rung3-semantic-source-review-manifest", "manifest.documentType")
    require_exact(document.get("schemaVersion"), "1.0", "manifest.schemaVersion")
    require_exact(document.get("reviewId"), EXPECTED_REVIEW_ID, "manifest.reviewId")
    require_exact(document.get("status"), "semantic_review_atomic_commit_marker_checker_pending", "manifest.status")
    validate_shared_output_bindings(
        document,
        label="manifest",
        record_bindings=record_bindings,
        candidate_bindings=candidate_bindings,
    )
    require_exact(
        document.get("artifacts"),
        [
            {
                "bytes": EXPECTED_PUBLISHED_BYTES[CLASSIFICATIONS_PATH],
                "name": CLASSIFICATIONS_NAME,
                "publicationOrder": 1,
                "rawSha256": EXPECTED_RAW_SHA256[CLASSIFICATIONS_PATH],
            },
            {
                "bytes": EXPECTED_PUBLISHED_BYTES[RESULT_PATH],
                "name": RESULT_NAME,
                "publicationOrder": 2,
                "rawSha256": EXPECTED_RAW_SHA256[RESULT_PATH],
            },
        ],
        "manifest.artifacts",
    )
    require_exact(
        document.get("publicationContract"),
        {
            "classificationsAndResultFullSetReadbackCompletedBeforeCommitMarker": True,
            "commitMarkerPresenceAloneIsFinalSuccessEvidence": False,
            "failureArtifactMayBePublishedAfterCommitMarker": True,
            "independentPostRunCheckerRequiredForFinalSuccessEvidence": True,
            "manifestRole": "atomic_commit_marker",
            "perArtifactStagingAndFinalReadbackRequired": True,
            "postCommitFullSetReadbackAttemptRequiredBeforeSuccessfulRunnerReturn": True,
            "postCommitFullSetReadbackCompletionPersistedByManifest": False,
        },
        "manifest.publicationContract",
    )
    require_exact(
        document.get("nonClaims"),
        {
            "candidateSelected": False,
            "dependencyClosureComplete": False,
            "finalSuccessEvidenceEstablished": False,
            "independentPostRunCheckerCompleted": False,
            "librarySelected": False,
            "postCommitFullSetReadbackCompletionPersistedByManifest": False,
            "postRunReproductionPerformed": False,
            "rungThreeComplete": False,
        },
        "manifest.nonClaims",
    )
    transactional = document.get("transactionalPublicationBoundary")
    require(type(transactional) is dict, "manifest.transactional boundary")
    require_exact(transactional.get("mode"), "0600", "manifest.mode")
    require(transactional.get("exclusiveNoReplace") is True, "manifest.no-replace")
    require(transactional.get("overwriteAllowed") is False, "manifest.overwrite boundary")
    require(transactional.get("finalArtifactDeletionAllowed") is False, "manifest.deletion boundary")


def validate_documents(
    raw: Mapping[str, bytes],
    *,
    enforce_raw_pins: bool = True,
) -> dict[str, Mapping[str, Any]]:
    require(set(raw) == set(ALLOWED_PATHS), "fixed read set mismatch")
    if enforce_raw_pins:
        for path in ALLOWED_PATHS:
            require_exact(sha256_bytes(raw[path]), EXPECTED_RAW_SHA256[path], f"{path}.rawSha256")
    parsed = {path: strict_canonical_json(raw[path], path) for path in JSON_PATHS}
    for path in JSON_PATHS:
        validate_content_binding(parsed[path], path=path)
    validate_decision(parsed[DECISION_PATH])
    record_bindings = validate_pass_records(parsed)
    candidate_bindings, expected_findings = validate_pass_input(
        parsed[PASS_INPUT_PATH], record_bindings
    )
    validate_classifications(
        parsed[CLASSIFICATIONS_PATH],
        record_bindings=record_bindings,
        candidate_bindings=candidate_bindings,
        expected_findings=expected_findings,
    )
    validate_result(
        parsed[RESULT_PATH],
        record_bindings=record_bindings,
        candidate_bindings=candidate_bindings,
    )
    validate_manifest(
        parsed[MANIFEST_PATH],
        record_bindings=record_bindings,
        candidate_bindings=candidate_bindings,
    )
    return parsed


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    reader = FixedTrackedReader(root)
    handles: list[dict[str, Any]] = []
    try:
        raw, _metadata, handles = reader.open_all_held()
        validate_documents(raw)
        final_raw = reader.reread_held(handles)
        require_exact(final_raw, raw, "final full-set stable byte readback")
        validate_documents(final_raw)
        reader.final_identity_barrier(handles)
        reader.require_absent_output_names()
        reader.final_identity_barrier(handles)
        held_directory_descriptor_count = sum(
            len(handle["directoryChain"]) for handle in handles
        )
        return {
            "documentType": (
                "aetherlink.g2-pion-rung3-semantic-source-review-v1-post-run-readback"
            ),
            "schemaVersion": "1.0",
            "status": EXPECTED_STATUS,
            "result": EXPECTED_RESULT,
            "nextAction": EXPECTED_NEXT_ACTION,
            "independentReadbackCompleted": True,
            "boundedSemanticPublicationCheckpointEvidenceEstablished": True,
            "publishedSemanticJudgmentsReadBackAndBound": True,
            "contentBindingsIndependentlyRecomputed": True,
            "candidateSemanticDigestsIndependentlyRecomputed": True,
            "findingAggregationIndependentlyRecomputed": True,
            "manifestArtifactBindingsIndependentlyRecomputed": True,
            "semanticJudgmentsIndependentlyReproducedByChecker": False,
            "lexicalObservationSetIndependentlyReproducedByChecker": False,
            "sourceLocationBoundsIndependentlyRevalidatedByChecker": False,
            "sourceSnapshotIndependentlyReopened": False,
            "dependencySourceReviewedByChecker": False,
            "semanticClosureComplete": False,
            "dependencyClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "fixedPathReadCount": len(reader.read_paths),
            "fixedPathCount": len(ALLOWED_PATHS),
            "fixedPathReadCountPerPass": len(ALLOWED_PATHS),
            "fullSetReadbackPassCount": 2,
            "heldFileDescriptorCount": len(handles),
            "heldDirectoryDescriptorCount": held_directory_descriptor_count,
            "heldDescriptorCount": len(handles) + held_directory_descriptor_count,
            "finalFullSetReadbackCompleted": True,
            "finalIdentityBarrierCompleted": True,
            "finalIdentityBarrierCount": 2,
            "repositoryPathAncestryHeldAndRevalidated": True,
            "fixedTrackedByteCount": sum(len(value) for value in final_raw.values()),
            "fixedAbsenceCheckCount": len(reader.absence_checks),
            "fixedAbsenceCheckCountPerPass": len(ABSENT_NAMES),
            "failureAndStagingAbsenceObservedBeforeAndAfterReadback": True,
            "absenceGuaranteedAfterFinalObservation": False,
            "manifestReadAndValidatedLast": reader.read_paths[-1] == MANIFEST_PATH,
            "publishedManifestStillRecordsCheckerPending": True,
            "directoryEnumerationCount": 0,
            "archiveOpenCount": 0,
            "sourceBodyReadCount": 0,
            "fileWriteCount": 0,
            "networkOperationCount": 0,
            "deviceOperationCount": 0,
            "gitOperationCount": 0,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "executionPermitAuthenticationRequired": False,
            "userActionRequired": False,
            "sameUidConcurrentMutationPrevented": False,
            "sameUidMutationAfterCheckerReturnDetected": False,
        }
    finally:
        reader.close_handles(handles)


def main(argv: Sequence[str] | None = None) -> int:
    require_isolated_interpreter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    try:
        lexical_root = Path(os.path.abspath(os.fspath(arguments.root)))
        result = check_repository(lexical_root)
    except CheckError as error:
        print(
            json.dumps(
                {
                    "documentType": (
                        "aetherlink.g2-pion-rung3-semantic-source-review-v1-"
                        "post-run-readback"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "reason": str(error),
                    "automaticRetryAllowed": False,
                    "externalIdentityProofRequired": False,
                    "repositoryOwnerAuthenticationRequired": False,
                    "executionPermitAuthenticationRequired": False,
                    "userActionRequired": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
