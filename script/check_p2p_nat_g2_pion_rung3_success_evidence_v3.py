#!/usr/bin/env python3
"""Validate only the tracked canonical G2 Pion rung-three v3 success evidence.

The checker never reads runtime output, ``build/``, an archive, a device, the
network, or Git state.  It opens a fixed allowlist of tracked files without
following symlinks, validates every byte pin and cross-document binding, and
reuses only the pure result/manifest validators from the hash-pinned post-run
checker.  It performs no writes.
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
        raise RuntimeError("canonical v3 evidence check requires unoptimized `python3 -I -B -S`")


require_isolated_interpreter()

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(os.path.abspath(__file__)).parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three"

RESULT_PATH = f"{BASE}/offline-source-review-result-v3.json"
RUNTIME_MANIFEST_PATH = f"{BASE}/offline-source-review-runtime-manifest-v3.json"
RECEIPT_PATH = f"{BASE}/offline-source-review-execution-receipt-v3.json"
PROGRESS_PATH = f"{BASE}/offline-source-review-progress-v4.json"
SUPERSESSION_PATH = f"{BASE}/canonical-document-supersession-v4.json"
MANIFEST_PATH = f"{BASE}/evidence-manifest-v11.json"
PERMIT_PATH = f"{BASE}/offline-source-review-execution-permit-v3.json"
PREVIOUS_PROGRESS_PATH = f"{BASE}/offline-source-review-progress-v3.json"
PREVIOUS_SUPERSESSION_PATH = f"{BASE}/canonical-document-supersession-v3.json"
PREDECESSOR_MANIFEST_PATH = f"{BASE}/execution-permit-checker-manifest-v10.json"
POSTRUN_CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_post_run_v3.py"
POSTRUN_TEST_PATH = "script/test_p2p_nat_g2_pion_rung3_post_run_v3.py"

ALLOWED_PATHS = (
    RESULT_PATH,
    RUNTIME_MANIFEST_PATH,
    RECEIPT_PATH,
    PROGRESS_PATH,
    SUPERSESSION_PATH,
    MANIFEST_PATH,
    PERMIT_PATH,
    PREVIOUS_PROGRESS_PATH,
    PREVIOUS_SUPERSESSION_PATH,
    PREDECESSOR_MANIFEST_PATH,
    POSTRUN_CHECKER_PATH,
    POSTRUN_TEST_PATH,
)

EXPECTED_RAW_SHA256 = {
    RESULT_PATH: "ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933",
    RUNTIME_MANIFEST_PATH: "2dace9b59b7374423754f1f9a7345eda76db9130728d1c0579797e5a0c829055",
    RECEIPT_PATH: "dbb46cb6ffacbe14b15118488e07ea71ceb242f652dda17cc42b233f8c966d71",
    PROGRESS_PATH: "08fd7def7fc0c6f9623ffaaf8dbe5157f4128d228e16c55552f1e8a8613f0a10",
    SUPERSESSION_PATH: "5b7735f57a6e97f512d469e683ba6d86a0c195bc16168b56ad1f2ad381120f19",
    MANIFEST_PATH: "24cb2e406f0e8be7664eda6cf677a9034113712734a19c4a27aea94278ee0895",
    PERMIT_PATH: "62652843477ca36dcdd3bf14d2aad42c33a694c8ffb7b4a51f7ce3ece5d476ae",
    PREVIOUS_PROGRESS_PATH: "2b4a3a5c89bf5f1d9821f1ed83e78f8953d775f8d49d385a1177acb572c6dd00",
    PREVIOUS_SUPERSESSION_PATH: "7a2bf9d692396d356db4b98318fa066f9ff0af000b8b75ebe2b12c568ebbc938",
    PREDECESSOR_MANIFEST_PATH: "84ca9e464f7f03bbe5522b45893a44ae05502a15a379b5359c5cb551c8c19f06",
    POSTRUN_CHECKER_PATH: "049c632530cb94d63e09a53ac00514dbe6c0090ef3a091fa1d6263d23cc1c559",
    POSTRUN_TEST_PATH: "c3bacb05c8673b61c6b8ebea0794c8b489ca59f8ec5f9f3c91d442a0f2b65381",
}

EXPECTED_SEMANTIC_SHA256 = {
    RESULT_PATH: "614a4f7f18e2bcdb8d1ab1ebf405c0687bb338aaee58db8113528c49e920f7c9",
    RUNTIME_MANIFEST_PATH: "132ef74158703df380260749b5070c0695db6f71f08f7cd1f97b5e4a6283b322",
    RECEIPT_PATH: "268d501e2756cca3b983d6043c5f3cee07f081878dfe7034ba685944a9eeee40",
    PROGRESS_PATH: "867eecb40cd549107438410cff6f806abeb6350c8ae6b5d600d529bcd482f98b",
    SUPERSESSION_PATH: "c698bcb4e33db90352d5f309f2ef4f8874ccbd7f3916b2c78fb5d383fdf8e433",
    MANIFEST_PATH: "c9a784319f47e31b0fd08a2f766a849b09a10b723e9c86b7b8e2e75166d66e6b",
    PERMIT_PATH: "d763a8ed9f681b66c9d6d3551fc5038e360173fee453eb6dee2a7cff3a1d8fe8",
    PREVIOUS_PROGRESS_PATH: "4b677f1e6a91db2c91109b8952851be7ae46650e0dbf75272f14e969c566bbb1",
    PREVIOUS_SUPERSESSION_PATH: "f82345cfbfb73933f54ff6879c428b7675f62b03cc03697cc77c93b3d4c555f0",
    PREDECESSOR_MANIFEST_PATH: "ee85d0205a44ac37c38e765d3cfdabb172cec8f5101b17413db2cfa6834e722c",
}

CLAIM_SHA256 = "2349d57dab677ba7631bd566e0890ba815a3bc4d7d678a0cf5759561898b33c8"
EXPECTED_SOURCE_TREE_SHA256 = "b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244"
EXPECTED_COLLECTION_SHA256 = "d5f09ef15eeadda4308e948e27413e742390977f3a758dd6ca9ac7c552b9e227"
EXPECTED_PREDECESSOR_COLLECTION_SHA256 = "f2c93ed6d633a8c396416cb8197918bd69e5cb301fb740a48a7709b52b581ded"
EXPECTED_RESULT_CONTENT_SHA256 = "ceffb7b9856a5eca635f0f797d341796776a7221a124c97b85c65fc936b02d48"
EXPECTED_RUNTIME_MANIFEST_CONTENT_SHA256 = "292dbb92599f00d673e6367ac1afb118849a912f81c2781f8a4cd846a3c6aefb"
EXPECTED_RECEIPT_CONTENT_SHA256 = "71c1c56a92878c97bd91d21e4ff66f8468c7fdb5d46bbd4b9627be2edf9f123f"
EXPECTED_PROGRESS_CONTENT_SHA256 = "159fda6dec8533991296b989b012c0066f075c9aada28003db6f444db40cb23c"
EXPECTED_SUPERSESSION_CONTENT_SHA256 = "d156b80b6014ec8089ceb29b13dbbc3111908c895283e4c3795cc76a2e8dfdab"

PATCH_UNIT_TOTALS = [606, 600, 482, 1056, 1356, 278, 323]
VERIFICATION_IDS = [
    "g2-r3-egress-path-coverage",
    "g2-r3-ingress-path-coverage",
    "g2-r3-address-and-resolution-adversarial",
    "g2-r3-turn-tls-service-identity",
    "g2-r3-secure-session-promotion",
    "g2-r3-resource-and-event-bounds",
    "g2-r3-secret-free-diagnostics",
    "g2-r3-deadline-shutdown",
]
EXPECTED_STATUS = "rung3_v3_publication_read_back_complete"
EXPECTED_RESULT = (
    "bounded_v3_exact_candidate_totals_digests_and_ranked_representatives_"
    "publication_committed_semantic_review_not_performed"
)
EXPECTED_NEXT_ACTION = "prepare_separate_versioned_rung3_semantic_source_review_decision"
MAXIMUM_TRACKED_FILE_BYTES = 4_194_304
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z")


class CheckError(ValueError):
    """Tracked canonical evidence failed closed validation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def require_exact(value: Any, expected: Any, label: str) -> None:
    require(type(value) is type(expected) and value == expected, f"{label}: mismatch")


def exact_object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    require(type(value) is dict and set(value) == keys, f"{label}: exact object schema mismatch")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def canonical_pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def semantic_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)


def reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite number")
    elif type(value) is list:
        for index, child in enumerate(value):
            reject_nonfinite(child, f"{label}[{index}]")
    elif type(value) is dict:
        for key, child in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(child, f"{label}.{key}")


def strict_canonical_json(data: bytes, label: str) -> Any:
    require(
        data.endswith(b"\n") and not data.endswith(b"\n\n") and b"\r" not in data,
        f"{label}: exactly one trailing LF required",
    )

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in items:
            require(key not in output, f"{label}: duplicate key")
            output[key] = value
        return output

    try:
        parsed = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CheckError(f"{label}: non-finite {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{label}: invalid JSON") from error
    reject_nonfinite(parsed, label)
    return parsed


def validate_content_binding(
    document: Mapping[str, Any],
    *,
    scope: str,
    expected_sha256: str,
    label: str,
) -> None:
    binding = exact_object(
        document.get("contentBinding"),
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}.contentBinding",
    )
    require_exact(binding["algorithm"], "sha256", f"{label}.contentBinding.algorithm")
    require_exact(
        binding["canonicalization"],
        "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        f"{label}.contentBinding.canonicalization",
    )
    require_exact(binding["scope"], scope, f"{label}.contentBinding.scope")
    payload = dict(document)
    payload.pop("contentBinding")
    calculated = sha256_bytes(canonical_json_bytes(payload))
    require_exact(binding["sha256"], calculated, f"{label}.contentBinding.sha256")
    require_exact(calculated, expected_sha256, f"{label}.expectedContentSha256")


def _validate_allowed_path(path: str) -> tuple[str, ...]:
    require(path in ALLOWED_PATHS, f"unlisted tracked read: {path}")
    pure = PurePosixPath(path)
    require(
        not pure.is_absolute()
        and pure.parts
        and all(part not in ("", ".", "..") for part in pure.parts)
        and pure.as_posix() == path,
        f"unsafe tracked path: {path}",
    )
    require("build" not in pure.parts, f"build read forbidden: {path}")
    require(not path.casefold().endswith(ARCHIVE_SUFFIXES), f"archive read forbidden: {path}")
    return pure.parts


def _stable_metadata(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


class FixedTrackedReader:
    """No-follow, no-enumeration reader for the exact tracked allowlist."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.read_paths: list[str] = []
        self.directory_enumeration_count = 0
        self.build_read_count = 0
        self.archive_read_or_stat_count = 0
        self.write_count = 0

    @staticmethod
    def _directory_flags() -> int:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        require(nofollow != 0 and directory != 0, "O_NOFOLLOW and O_DIRECTORY required")
        return os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0)

    def _open_root(self) -> int:
        require(self.root.is_absolute(), "absolute repository root required")
        current = -1
        try:
            current = os.open(os.sep, self._directory_flags())
            for component in self.root.parts[1:]:
                next_fd = os.open(component, self._directory_flags(), dir_fd=current)
                identity = os.fstat(next_fd)
                require(stat.S_ISDIR(identity.st_mode), f"{component}: directory required")
                os.close(current)
                current = next_fd
            result = current
            current = -1
            return result
        except OSError as error:
            raise CheckError(f"component-wise repository root open failed: {error}") from error
        finally:
            if current >= 0:
                os.close(current)

    def _open_parent(self, parts: tuple[str, ...]) -> int:
        current = -1
        try:
            current = self._open_root()
            root_stat = os.fstat(current)
            require(stat.S_ISDIR(root_stat.st_mode), "repository root is not a directory")
            for component in parts[:-1]:
                next_fd = os.open(component, self._directory_flags(), dir_fd=current)
                identity = os.fstat(next_fd)
                require(stat.S_ISDIR(identity.st_mode), f"{component}: directory required")
                os.close(current)
                current = next_fd
            result = current
            current = -1
            return result
        except OSError as error:
            raise CheckError(f"safe directory open failed: {error}") from error
        finally:
            if current >= 0:
                os.close(current)

    def read(self, path: str) -> bytes:
        parts = _validate_allowed_path(path)
        parent = self._open_parent(parts)
        descriptor = -1
        try:
            name = parts[-1]
            named_before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(name, flags, dir_fd=parent)
            before = os.fstat(descriptor)
            require(
                stat.S_ISREG(before.st_mode)
                and before.st_uid == os.geteuid()
                and stat.S_IMODE(before.st_mode) & 0o022 == 0
                and 0 < before.st_size <= MAXIMUM_TRACKED_FILE_BYTES,
                f"{path}: tracked file metadata mismatch",
            )
            require(
                (named_before.st_dev, named_before.st_ino, named_before.st_mode, named_before.st_size)
                == (before.st_dev, before.st_ino, before.st_mode, before.st_size),
                f"{path}: named inode mismatch",
            )
            remaining = before.st_size + 1
            chunks: list[bytes] = []
            while remaining:
                chunk = os.read(descriptor, min(65_536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            after = os.fstat(descriptor)
            named_after = os.stat(name, dir_fd=parent, follow_symlinks=False)
            require(
                len(raw) == before.st_size
                and _stable_metadata(before) == _stable_metadata(after)
                and (after.st_dev, after.st_ino, after.st_mode, after.st_size)
                == (named_after.st_dev, named_after.st_ino, named_after.st_mode, named_after.st_size),
                f"{path}: unstable tracked read",
            )
            self.read_paths.append(path)
            return raw
        except OSError as error:
            raise CheckError(f"{path}: safe tracked read failed: {error}") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(parent)

    def read_all(self) -> dict[str, bytes]:
        return {path: self.read(path) for path in ALLOWED_PATHS}


def load_postrun_namespace(source: bytes) -> dict[str, Any]:
    require_exact(sha256_bytes(source), EXPECTED_RAW_SHA256[POSTRUN_CHECKER_PATH], "postrun checker")
    namespace: dict[str, Any] = {
        "__file__": os.fspath(ROOT / POSTRUN_CHECKER_PATH),
        "__name__": "_aetherlink_hash_pinned_postrun_v3",
        "__package__": None,
    }
    try:
        exec(compile(source, POSTRUN_CHECKER_PATH, "exec", dont_inherit=True, optimize=0), namespace)
    except Exception as error:
        raise CheckError(f"hash-pinned postrun checker failed to load: {error}") from error
    require(callable(namespace.get("validate_result")), "postrun validate_result unavailable")
    require(callable(namespace.get("validate_manifest")), "postrun validate_manifest unavailable")
    return namespace


def _remaining_verification() -> list[dict[str, str]]:
    return [{"id": item, "status": "required_check_not_executed"} for item in VERIFICATION_IDS]


def validate_receipt(receipt: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    exact_object(
        receipt,
        {
            "documentType", "schemaVersion", "receiptId", "recordedDate", "status",
            "result", "nextAction", "contentBinding", "permitBinding",
            "runtimePublication", "postRunReadback", "runnerIndependentRecomputation",
            "postRunIndependentReproductionBoundary", "trackedCanonicalCopies",
            "candidateSummary", "sourceAndMetadataSummary", "remainingVerification",
            "executionBoundary", "personalProjectBoundary", "forwardOnlyBindings",
        },
        "receipt",
    )
    validate_content_binding(
        receipt,
        scope="receipt_without_contentBinding",
        expected_sha256=EXPECTED_RECEIPT_CONTENT_SHA256,
        label="receipt",
    )
    for key, expected in {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-execution-receipt",
        "schemaVersion": "3.0",
        "receiptId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-receipt-v3",
        "recordedDate": "2026-07-23",
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
    }.items():
        require_exact(receipt[key], expected, f"receipt.{key}")
    require_exact(
        receipt["candidateSummary"],
        {
            "goSourceFileCount": 100,
            "goSourceTotalBytes": 1_077_591,
            "goSourceLogicalLineCount": 39_064,
            "totalHitCount": 4_701,
            "recordedRepresentativeCount": 144,
            "omittedHitCount": 4_557,
            "truncated": True,
            "patchUnitTotalsInPolicyOrder": PATCH_UNIT_TOTALS,
        },
        "receipt.candidateSummary",
    )
    require_exact(
        receipt["sourceAndMetadataSummary"],
        {
            "entryCount": 129,
            "sourceTreeSha256": EXPECTED_SOURCE_TREE_SHA256,
            "creatorPolicyVersion": "2.0",
            "msDosCreatorEntryCount": 129,
            "unixCreatorEntryCount": 0,
            "goModRequireCount": 19,
            "goSumRecordCount": 44,
            "licenseAndNoticeFileCount": 1,
        },
        "receipt.sourceAndMetadataSummary",
    )
    candidate = result["patchUnitCandidateInventory"]
    require_exact(
        [
            candidate["sourceEntryCount"],
            candidate["sourceTotalBytes"],
            candidate["sourceLogicalLineCount"],
            candidate["totals"]["hitCount"],
            candidate["totals"]["recordedRepresentativeCount"],
            candidate["totals"]["omittedHitCount"],
            candidate["totals"]["truncated"],
            [unit["totalHitCount"] for unit in candidate["patchUnits"]],
        ],
        [100, 1_077_591, 39_064, 4_701, 144, 4_557, True, PATCH_UNIT_TOTALS],
        "receipt/result candidate cross-binding",
    )
    require_exact(result["sourceInventory"]["treeSha256"], EXPECTED_SOURCE_TREE_SHA256, "result source tree")
    require_exact(result["creatorMetadataPolicy"]["msDosRegularFileCount"], 129, "result DOS count")
    require_exact(result["creatorMetadataPolicy"]["unixEntryCount"], 0, "result Unix count")
    require_exact(len(result["dependencyMetadata"]["goMod"]["requires"]), 19, "result requires count")
    require_exact(result["dependencyMetadata"]["goSum"]["recordCount"], 44, "result go.sum count")
    require_exact(result["licenseAndNoticeInventory"]["fileCount"], 1, "result license count")
    require_exact(
        receipt["runnerIndependentRecomputation"],
        {
            "performed": True,
            "performedInProcessBeforePublication": True,
            "evidenceClass": (
                "runner_in_process_independent_recomputation_bound_by_published_result_"
                "and_tests_not_postrun_reproduction"
            ),
            "archiveReadPassCount": 1,
            "secondArchiveReadPerformed": False,
            "candidateAggregatorInvocationCount": 1,
            "candidateIndependentValidationPassCount": 1,
            "candidateCountsIndependentlyRecomputed": True,
            "completeObservationDigestsIndependentlyRecomputed": True,
            "candidateRepresentativeRuleMatchesIndependentlyRecomputed": True,
            "candidateLowestRankSelectionIndependentlyRecomputed": True,
            "exactAggregatorObjectCompared": True,
        },
        "receipt.runnerIndependentRecomputation",
    )
    require_exact(
        receipt["postRunIndependentReproductionBoundary"],
        {
            "sourceBodiesAvailableToPostRunChecker": False,
            "candidateCompleteObservationDigestIndependentlyReproduced": False,
            "candidateCountsIndependentlyReproduced": False,
            "candidateRepresentativeRuleMatchesIndependentlyReproduced": False,
            "candidateLowestRankSelectionIndependentlyReproduced": False,
            "validationPerformed": (
                "runtime_result_structure_arithmetic_rank_format_and_publication_hash_binding_only"
            ),
        },
        "receipt.postRunIndependentReproductionBoundary",
    )
    require_exact(
        receipt["postRunReadback"],
        {
            "result": "passed",
            "checkerPath": POSTRUN_CHECKER_PATH,
            "checkerRawSha256": EXPECTED_RAW_SHA256[POSTRUN_CHECKER_PATH],
            "checkerTestPath": POSTRUN_TEST_PATH,
            "checkerTestRawSha256": EXPECTED_RAW_SHA256[POSTRUN_TEST_PATH],
            "fixedNameReadCount": 5,
            "directoryEnumerationCount": 0,
            "archiveOpenCount": 0,
            "archiveReadPassCount": 0,
            "fileWriteCount": 0,
            "manifestWasValidatedLastAsSoleCompletionMarker": True,
        },
        "receipt.postRunReadback",
    )
    runtime = receipt["runtimePublication"]
    require_exact(
        runtime,
        {
            "directory": "build/offline-source/pion-ice-v4.3.0/review-v3",
            "directoryMode": "0700",
            "directoryEnumerated": False,
            "claim": {
                "name": ".g2-pion-ice-v4.3.0-rung3-offline-review-v3.claim",
                "bytes": 446,
                "rawSha256": CLAIM_SHA256,
                "mode": "0600",
                "linkCount": 1,
                "retained": True,
            },
            "result": {
                "temporaryName": ".offline-source-review-result-v3.json.tmp",
                "finalName": "offline-source-review-result-v3.json",
                "bytes": 76_685,
                "rawSha256": EXPECTED_RAW_SHA256[RESULT_PATH],
                "mode": "0600",
                "finalLinkCount": 2,
                "temporaryAndFinalSameInode": True,
                "temporaryAndFinalBytesIdentical": True,
            },
            "manifest": {
                "temporaryName": ".offline-source-review-manifest-v3.json.tmp",
                "finalName": "offline-source-review-manifest-v3.json",
                "bytes": 2_458,
                "rawSha256": EXPECTED_RAW_SHA256[RUNTIME_MANIFEST_PATH],
                "mode": "0600",
                "finalLinkCount": 2,
                "temporaryAndFinalSameInode": True,
                "temporaryAndFinalBytesIdentical": True,
                "soleCompletionMarker": True,
                "validatedLast": True,
            },
        },
        "receipt.runtimePublication",
    )
    copies = receipt["trackedCanonicalCopies"]
    require_exact(
        copies,
        {
            "runtimeResult": {
                "path": RESULT_PATH,
                "bytes": 76_685,
                "rawSha256": EXPECTED_RAW_SHA256[RESULT_PATH],
                "semanticSha256": EXPECTED_SEMANTIC_SHA256[RESULT_PATH],
                "contentSha256": EXPECTED_RESULT_CONTENT_SHA256,
                "byteIdenticalToRuntime": True,
            },
            "runtimeManifest": {
                "path": RUNTIME_MANIFEST_PATH,
                "bytes": 2_458,
                "rawSha256": EXPECTED_RAW_SHA256[RUNTIME_MANIFEST_PATH],
                "semanticSha256": EXPECTED_SEMANTIC_SHA256[RUNTIME_MANIFEST_PATH],
                "contentSha256": EXPECTED_RUNTIME_MANIFEST_CONTENT_SHA256,
                "byteIdenticalToRuntime": True,
            },
        },
        "receipt.trackedCanonicalCopies",
    )
    require_exact(receipt["remainingVerification"], _remaining_verification(), "receipt.remainingVerification")
    require_exact(
        receipt["personalProjectBoundary"],
        {
            "technicalSafetyGatesRemainRequired": True,
            "executionPermitAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationChangedByThisEvidence": False,
        },
        "receipt.personalProjectBoundary",
    )
    require_exact(
        receipt["executionBoundary"],
        {
            "boundedCandidateLocationInventoryCompleted": True,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "sourceMaterialized": False,
            "sourcePatched": False,
            "sourceExecuted": False,
            "dependencyInstalled": False,
            "reviewedSourceCompiled": False,
            "networkUsed": False,
            "socketCreated": False,
            "gitOperationPerformed": False,
            "deviceOperationPerformed": False,
            "productionDeploymentAuthorized": False,
        },
        "receipt.executionBoundary",
    )


def validate_progress(progress: Mapping[str, Any]) -> None:
    exact_object(
        progress,
        {
            "documentType", "schemaVersion", "progressId", "recordedDate", "status",
            "result", "nextAction", "contentBinding", "previousProgressBinding",
            "executionReceiptBinding", "canonicalRuntimeBindings", "completionSummary",
            "independentValidationBoundary", "remainingVerification", "executionBoundary",
            "personalProjectBoundary", "forwardOnlyBindings",
        },
        "progress",
    )
    validate_content_binding(
        progress,
        scope="progress_without_contentBinding",
        expected_sha256=EXPECTED_PROGRESS_CONTENT_SHA256,
        label="progress",
    )
    for key, expected in {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-progress",
        "schemaVersion": "3.0",
        "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v4",
        "recordedDate": "2026-07-23",
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
    }.items():
        require_exact(progress[key], expected, f"progress.{key}")
    require_exact(
        progress["previousProgressBinding"],
        {
            "path": PREVIOUS_PROGRESS_PATH,
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v3",
            "rawSha256": EXPECTED_RAW_SHA256[PREVIOUS_PROGRESS_PATH],
            "semanticSha256": EXPECTED_SEMANTIC_SHA256[PREVIOUS_PROGRESS_PATH],
            "recordedStatus": "rung3_bounded_static_inventory_permit_v2_consumed_failed_closed",
        },
        "progress.previousProgressBinding",
    )
    require_exact(
        progress["executionReceiptBinding"],
        {
            "path": RECEIPT_PATH,
            "receiptId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-receipt-v3",
            "rawSha256": EXPECTED_RAW_SHA256[RECEIPT_PATH],
            "semanticSha256": EXPECTED_SEMANTIC_SHA256[RECEIPT_PATH],
            "requiredStatus": EXPECTED_STATUS,
        },
        "progress.executionReceiptBinding",
    )
    require_exact(
        progress["canonicalRuntimeBindings"],
        {
            "result": {
                "path": RESULT_PATH,
                "rawSha256": EXPECTED_RAW_SHA256[RESULT_PATH],
                "semanticSha256": EXPECTED_SEMANTIC_SHA256[RESULT_PATH],
            },
            "manifest": {
                "path": RUNTIME_MANIFEST_PATH,
                "rawSha256": EXPECTED_RAW_SHA256[RUNTIME_MANIFEST_PATH],
                "semanticSha256": EXPECTED_SEMANTIC_SHA256[RUNTIME_MANIFEST_PATH],
            },
        },
        "progress.canonicalRuntimeBindings",
    )
    require_exact(
        progress["completionSummary"],
        {
            "permitVersion": 3,
            "permitConsumed": True,
            "claimRetained": True,
            "completionManifestPublished": True,
            "completionManifestReadBack": True,
            "boundedCandidateLocationInventoryCompleted": True,
            "candidateTotalHitCount": 4_701,
            "candidateRecordedRepresentativeCount": 144,
            "candidateOmittedHitCount": 4_557,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
        },
        "progress.completionSummary",
    )
    require_exact(
        progress["independentValidationBoundary"],
        {
            "runnerCandidateRecomputationPerformedBeforePublication": True,
            "postRunCandidateCountsReproduced": False,
            "postRunCompleteObservationDigestsReproduced": False,
            "postRunRepresentativeRuleMatchesReproduced": False,
            "postRunLowestRankSelectionReproduced": False,
        },
        "progress.independentValidationBoundary",
    )
    require_exact(progress["remainingVerification"], _remaining_verification(), "progress.remainingVerification")
    require_exact(
        progress["personalProjectBoundary"],
        {
            "technicalSafetyGatesRemainRequired": True,
            "executionPermitAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationChangedByThisEvidence": False,
        },
        "progress.personalProjectBoundary",
    )
    require_exact(
        progress["executionBoundary"],
        {
            "boundedCandidateLocationInventoryCompleted": True,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "sourceMaterialized": False,
            "sourcePatched": False,
            "sourceExecuted": False,
            "dependencyInstalled": False,
            "reviewedSourceCompiled": False,
            "networkUsed": False,
            "socketCreated": False,
            "gitOperationPerformed": False,
            "deviceOperationPerformed": False,
            "productionDeploymentAuthorized": False,
        },
        "progress.executionBoundary",
    )


def validate_supersession(supersession: Mapping[str, Any]) -> None:
    exact_object(
        supersession,
        {
            "documentType", "schemaVersion", "supersessionId", "recordedDate",
            "status", "result", "nextAction", "reason", "contentBinding",
            "predecessorSupersessionBinding", "predecessorManifestBinding",
            "executionReceiptBinding", "progressBinding", "canonicalRuntimeBindings",
            "forwardOnlyManifestBinding", "supersededStates", "currentState",
            "semanticGuard", "executionBoundary",
        },
        "supersession",
    )
    validate_content_binding(
        supersession,
        scope="supersession_without_contentBinding",
        expected_sha256=EXPECTED_SUPERSESSION_CONTENT_SHA256,
        label="supersession",
    )
    for key, expected in {
        "documentType": "aetherlink.g2-canonical-document-supersession",
        "schemaVersion": "3.0",
        "supersessionId": "g2-pion-rung3-canonical-document-supersession-v4",
        "recordedDate": "2026-07-23",
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
    }.items():
        require_exact(supersession[key], expected, f"supersession.{key}")
    require_exact(
        supersession["predecessorSupersessionBinding"],
        {
            "path": PREVIOUS_SUPERSESSION_PATH,
            "supersessionId": "g2-pion-rung3-canonical-document-supersession-v3",
            "rawSha256": EXPECTED_RAW_SHA256[PREVIOUS_SUPERSESSION_PATH],
            "semanticSha256": EXPECTED_SEMANTIC_SHA256[PREVIOUS_SUPERSESSION_PATH],
        },
        "supersession.predecessorSupersessionBinding",
    )
    require_exact(
        supersession["predecessorManifestBinding"],
        {
            "path": PREDECESSOR_MANIFEST_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[PREDECESSOR_MANIFEST_PATH],
            "semanticSha256": EXPECTED_SEMANTIC_SHA256[PREDECESSOR_MANIFEST_PATH],
            "collectionSha256": EXPECTED_PREDECESSOR_COLLECTION_SHA256,
        },
        "supersession.predecessorManifestBinding",
    )
    require_exact(
        supersession["executionReceiptBinding"],
        {
            "path": RECEIPT_PATH,
            "receiptId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-execution-receipt-v3",
            "rawSha256": EXPECTED_RAW_SHA256[RECEIPT_PATH],
            "semanticSha256": EXPECTED_SEMANTIC_SHA256[RECEIPT_PATH],
        },
        "supersession.executionReceiptBinding",
    )
    require_exact(
        supersession["progressBinding"],
        {
            "path": PROGRESS_PATH,
            "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v4",
            "rawSha256": EXPECTED_RAW_SHA256[PROGRESS_PATH],
            "semanticSha256": EXPECTED_SEMANTIC_SHA256[PROGRESS_PATH],
        },
        "supersession.progressBinding",
    )
    require_exact(
        supersession["canonicalRuntimeBindings"],
        {
            "result": {"path": RESULT_PATH, "rawSha256": EXPECTED_RAW_SHA256[RESULT_PATH]},
            "manifest": {
                "path": RUNTIME_MANIFEST_PATH,
                "rawSha256": EXPECTED_RAW_SHA256[RUNTIME_MANIFEST_PATH],
            },
        },
        "supersession.canonicalRuntimeBindings",
    )
    require_exact(
        supersession["semanticGuard"],
        {
            "historicalEvidenceRewritten": False,
            "v2FailureReinterpretedAsSuccess": False,
            "runnerIndependentRecomputationPerformedBeforePublication": True,
            "candidateCountsReproducedByPostRunChecker": False,
            "completeObservationDigestsReproducedByPostRunChecker": False,
            "representativeRuleMatchesReproducedByPostRunChecker": False,
            "lowestRankSelectionReproducedByPostRunChecker": False,
            "semanticSourceReviewPerformed": False,
            "requiredCurrentStatus": EXPECTED_STATUS,
            "requiredCurrentNextAction": EXPECTED_NEXT_ACTION,
        },
        "supersession.semanticGuard",
    )
    require_exact(
        supersession["executionBoundary"],
        {
            "boundedCandidateLocationInventoryCompleted": True,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "dependencyClosureComplete": False,
            "reviewedSourceCompileAuthorized": False,
            "runtimeNetworkAuthorized": False,
            "productionDeploymentAuthorized": False,
            "permitVersionThreeConsumed": True,
            "permitVersionThreeReusable": False,
            "executionPermitAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "supersession.executionBoundary",
    )


def collection_sha256(artifacts: Sequence[Mapping[str, Any]]) -> str:
    rows = [
        f"{row['evidenceId']}\t{row['sha256']}\t{row['path']}\n".encode("utf-8")
        for row in artifacts
    ]
    return sha256_bytes(b"".join(rows))


def validate_manifest_v11(manifest: Mapping[str, Any], raw: Mapping[str, bytes]) -> None:
    exact_object(
        manifest,
        {
            "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
            "result", "nextAction", "artifactScope", "artifactCount", "orderingRule",
            "collectionDigestAlgorithm", "collectionSha256", "predecessorManifestBinding",
            "artifacts", "successBoundary", "trustBoundary", "canonicalCheckerBoundary",
        },
        "manifestV11",
    )
    for key, expected in {
        "documentType": "aetherlink.g2-pion-rung3-success-evidence-manifest",
        "schemaVersion": "3.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung3-success-evidence-manifest-v11",
        "recordedDate": "2026-07-23",
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
        "artifactCount": 7,
        "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": (
            "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_repo_relative_path_newline"
        ),
        "collectionSha256": EXPECTED_COLLECTION_SHA256,
    }.items():
        require_exact(manifest[key], expected, f"manifestV11.{key}")
    expected_artifacts = [
        ("G2R3E061", RESULT_PATH, "byte_identical_canonical_tracked_v3_runtime_result"),
        (
            "G2R3E062",
            RUNTIME_MANIFEST_PATH,
            "byte_identical_canonical_tracked_v3_runtime_completion_manifest",
        ),
        (
            "G2R3E063",
            RECEIPT_PATH,
            "v3_success_execution_and_fixed_name_postrun_readback_receipt",
        ),
        ("G2R3E064", PROGRESS_PATH, "current_v3_publication_readback_complete_progress"),
        ("G2R3E065", SUPERSESSION_PATH, "canonical_v3_success_state_supersession"),
        (
            "G2R3E066",
            POSTRUN_CHECKER_PATH,
            "fixed_name_no_archive_v3_runtime_postrun_readback_checker",
        ),
        ("G2R3E067", POSTRUN_TEST_PATH, "synthetic_v3_postrun_readback_mutation_tests"),
    ]
    artifacts = manifest["artifacts"]
    require(type(artifacts) is list and len(artifacts) == 7, "manifestV11.artifacts")
    for index, (evidence_id, path, role) in enumerate(expected_artifacts):
        row = exact_object(
            artifacts[index], {"evidenceId", "path", "role", "sha256"}, f"artifact[{index}]"
        )
        require_exact(
            row,
            {
                "evidenceId": evidence_id,
                "path": path,
                "role": role,
                "sha256": sha256_bytes(raw[path]),
            },
            f"artifact[{index}]",
        )
    require_exact(collection_sha256(artifacts), EXPECTED_COLLECTION_SHA256, "manifest collection")
    require_exact(
        manifest["predecessorManifestBinding"],
        {
            "path": PREDECESSOR_MANIFEST_PATH,
            "rawSha256": EXPECTED_RAW_SHA256[PREDECESSOR_MANIFEST_PATH],
            "semanticSha256": EXPECTED_SEMANTIC_SHA256[PREDECESSOR_MANIFEST_PATH],
            "collectionSha256": EXPECTED_PREDECESSOR_COLLECTION_SHA256,
        },
        "manifestV11.predecessorManifestBinding",
    )
    require_exact(
        manifest["successBoundary"],
        {
            "permitVersionThreeConsumed": True,
            "automaticRetryAllowed": False,
            "claimRetained": True,
            "completionManifestPublished": True,
            "completionManifestReadBack": True,
            "boundedCandidateLocationInventoryCompleted": True,
            "runnerIndependentCandidateRecomputationPerformed": True,
            "postRunCandidateCountsIndependentlyReproduced": False,
            "postRunCompleteObservationDigestsIndependentlyReproduced": False,
            "postRunRepresentativeRuleMatchesIndependentlyReproduced": False,
            "postRunLowestRankSelectionIndependentlyReproduced": False,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "manifestV11.successBoundary",
    )
    require_exact(
        manifest["trustBoundary"],
        {
            "trackedFilesOnly": True,
            "runtimeOutputReadAllowed": False,
            "archiveOpenReadOrStatAllowed": False,
            "buildDirectoryEnumerationAllowed": False,
            "networkAllowed": False,
            "deviceAllowed": False,
            "gitAllowed": False,
            "executionPermitAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
            "checkerSelfAuthenticationClaimed": False,
            "invokedCanonicalCheckerBytesAreLocalTrustRoot": True,
        },
        "manifestV11.trustBoundary",
    )
    require_exact(
        manifest["canonicalCheckerBoundary"],
        {
            "checkerPath": "script/check_p2p_nat_g2_pion_rung3_success_evidence_v3.py",
            "checkerTestPath": "script/test_p2p_nat_g2_pion_rung3_success_evidence_v3.py",
            "includedAsManifestArtifacts": False,
            "reason": (
                "invoked_checker_and_test_remain_outside_the_manifest_to_avoid_"
                "self_referential_digest_cycles"
            ),
            "checkerReadsTrackedFilesOnly": True,
            "buildReadAllowed": False,
            "archiveReadOrStatAllowed": False,
        },
        "manifestV11.canonicalCheckerBoundary",
    )


def validate_documents(
    raw: Mapping[str, bytes],
    *,
    enforce_pins: bool = True,
    postrun_namespace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    require(set(raw) == set(ALLOWED_PATHS), "tracked read set mismatch")
    parsed: dict[str, Any] = {}
    for path in ALLOWED_PATHS:
        if enforce_pins:
            require_exact(sha256_bytes(raw[path]), EXPECTED_RAW_SHA256[path], f"{path}.rawSha256")
        if path.endswith(".json"):
            parsed[path] = strict_canonical_json(raw[path], path)
            if enforce_pins and path in EXPECTED_SEMANTIC_SHA256:
                require_exact(
                    semantic_json_sha256(parsed[path]),
                    EXPECTED_SEMANTIC_SHA256[path],
                    f"{path}.semanticSha256",
                )
    namespace = (
        dict(postrun_namespace)
        if postrun_namespace is not None
        else load_postrun_namespace(raw[POSTRUN_CHECKER_PATH])
    )
    try:
        result = namespace["validate_result"](raw[RESULT_PATH], CLAIM_SHA256)
        runtime_manifest = namespace["validate_manifest"](
            raw[RUNTIME_MANIFEST_PATH], raw[RESULT_PATH], CLAIM_SHA256, result
        )
    except Exception as error:
        raise CheckError(f"pure postrun schema validation failed: {error}") from error
    validate_receipt(parsed[RECEIPT_PATH], result)
    validate_progress(parsed[PROGRESS_PATH])
    validate_supersession(parsed[SUPERSESSION_PATH])
    validate_manifest_v11(parsed[MANIFEST_PATH], raw)
    require_exact(runtime_manifest["result"], EXPECTED_RESULT, "runtime manifest result")
    return {
        "documentType": "aetherlink.g2-pion-rung3-success-evidence-v3-canonical-check",
        "schemaVersion": "1.0",
        "status": "passed",
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
        "trackedFileReadCount": len(ALLOWED_PATHS),
        "runtimeOutputReadCount": 0,
        "buildReadCount": 0,
        "buildDirectoryEnumerationCount": 0,
        "archiveOpenReadOrStatCount": 0,
        "fileWriteCount": 0,
        "resultAndRuntimeManifestFullSchemaValidated": True,
        "postrunFilesystemReadbackInvoked": False,
        "candidateCountsIndependentlyReproducedByThisChecker": False,
        "completeObservationDigestsIndependentlyReproducedByThisChecker": False,
        "representativeRuleMatchesIndependentlyReproducedByThisChecker": False,
        "lowestRankSelectionIndependentlyReproducedByThisChecker": False,
        "externalIdentityProofRequired": False,
        "repositoryOwnerAuthenticationRequired": False,
        "userActionRequired": False,
    }


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    reader = FixedTrackedReader(root)
    result = validate_documents(reader.read_all())
    require_exact(reader.read_paths, list(ALLOWED_PATHS), "tracked read order")
    require_exact(reader.directory_enumeration_count, 0, "directory enumeration count")
    require_exact(reader.build_read_count, 0, "build read count")
    require_exact(reader.archive_read_or_stat_count, 0, "archive read/stat count")
    require_exact(reader.write_count, 0, "write count")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    require_isolated_interpreter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = validate_repository(Path(os.path.abspath(args.root)))
    except CheckError as error:
        print(
            json.dumps(
                {
                    "documentType": "aetherlink.g2-pion-rung3-success-evidence-v3-canonical-check",
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "reason": str(error),
                    "externalIdentityProofRequired": False,
                    "repositoryOwnerAuthenticationRequired": False,
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
