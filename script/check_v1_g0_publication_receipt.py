#!/usr/bin/env python3
"""Dormant, non-authorizing validation for a V2 G0 publication candidate."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Final

try:
    from script import check_v1_g0_decision as decision
    from script import check_v1_g0_checkpoint as checkpoint
except ModuleNotFoundError:
    import check_v1_g0_decision as decision
    import check_v1_g0_checkpoint as checkpoint


MAX_PUBLICATION_RECEIPT_BYTES: Final = 65_536
MAX_AMENDMENT_BYTES: Final = 1_048_576
MAX_AMENDMENT_CHECKPOINT_BYTES: Final = 1_048_576

PARENT_ASSURANCE_PATH: Final = "docs/v1/g0/assurance-v1.json"
PARENT_CHECKPOINT_PATH: Final = "docs/v1/g0/assurance-checkpoint-readback-v1.json"
AMENDMENT_PATH: Final = "docs/v1/g0/assurance-closure-amendment-v2.json"
AMENDMENT_CHECKPOINT_PATH: Final = (
    "docs/v1/g0/assurance-closure-amendment-checkpoint-v2.json"
)
COMMIT_BLOB_PATHS: Final = (
    PARENT_ASSURANCE_PATH,
    PARENT_CHECKPOINT_PATH,
    AMENDMENT_PATH,
    AMENDMENT_CHECKPOINT_PATH,
)
PUBLICATION_RECEIPT_FIELDS: Final = (
    "repositoryRef",
    "commitObjectId",
    "parentAssurancePath",
    "parentAssuranceSha256",
    "parentCheckpointPath",
    "parentCheckpointSha256",
    "amendmentPath",
    "amendmentSha256",
    "amendmentCheckpointPath",
    "amendmentCheckpointSha256",
    "effectiveAssuranceCanonicalSha256",
    "remoteReadbackAt",
    "remoteReadbackSha256",
    "result",
)

_CONTEXT_FACTORY_TOKEN = object()
_CANONICAL_UTC_PATTERN = re.compile(
    r"^(?:[0-9]{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
_PROVENANCE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,255}$")
_LOCAL_ONLY_PROVENANCE_MARKERS = (
    "origin/",
    "reflog",
    "worktree",
    "local_tracking",
    "local-tracking",
)
_PUBLICATION_CANDIDATE_DISABLED_MESSAGE = (
    "G0 composite publication receipt candidate is dormant_non_authorizing; "
    "it cannot establish publication, acceptance, or activation"
)


class _PublicationValidationContextError(ValueError):
    """Raised when independent candidate inputs cannot form a safe snapshot."""

    def __init__(self, failures: tuple[str, ...]):
        super().__init__("; ".join(failures))
        self.failures = failures


class _PublicationValidationContext(tuple):
    """Opaque immutable snapshot. It intentionally carries no authority bit."""

    __slots__ = ()

    def __new__(
        cls,
        token: object,
        repository_ref: str,
        commit_object_id: str,
        commit_blobs: tuple[tuple[str, bytes], ...],
        remote_checkpoint_bytes: bytes,
        remote_readback_at: str,
    ) -> _PublicationValidationContext:
        if token is not _CONTEXT_FACTORY_TOKEN:
            raise TypeError("publication validation contexts are factory-only")
        return tuple.__new__(
            cls,
            (
                token,
                repository_ref,
                commit_object_id,
                commit_blobs,
                remote_checkpoint_bytes,
                remote_readback_at,
            ),
        )

    @property
    def _factory_token(self) -> object:
        return self[0]

    @property
    def _repository_ref(self) -> str:
        return self[1]

    @property
    def _commit_object_id(self) -> str:
        return self[2]

    @property
    def _commit_blobs(self) -> tuple[tuple[str, bytes], ...]:
        return self[3]

    @property
    def _remote_checkpoint_bytes(self) -> bytes:
        return self[4]

    @property
    def _remote_readback_at(self) -> str:
        return self[5]


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_equal(
    actual: object,
    expected: object,
    label: str,
    failures: list[str],
) -> None:
    if not decision.exactly_equal(actual, expected):
        failures.append(f"{label} does not match the canonical V2 candidate")


def _bounded_snapshot(
    value: object,
    label: str,
    maximum_bytes: int,
    failures: list[str],
) -> bytes | None:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        failures.append(f"{label} must be bytes")
        return None
    try:
        observed_size = value.nbytes if isinstance(value, memoryview) else len(value)
    except (BufferError, TypeError, ValueError):
        failures.append(f"{label} is not a readable byte buffer")
        return None
    if observed_size == 0:
        failures.append(f"{label} must not be empty")
        return None
    if observed_size > maximum_bytes:
        failures.append(f"{label} exceeds {maximum_bytes} bytes")
        return None
    try:
        raw = bytes(value)
    except (BufferError, TypeError, ValueError):
        failures.append(f"{label} is not a readable byte buffer")
        return None
    return raw


def _parse_bounded_object(
    value: object,
    label: str,
    maximum_bytes: int,
    failures: list[str],
) -> tuple[bytes | None, dict[str, object] | None]:
    raw = _bounded_snapshot(value, label, maximum_bytes, failures)
    if raw is None:
        return None, None
    return raw, _parse_snapshot_object(raw, label, failures)


def _parse_snapshot_object(
    raw: bytes,
    label: str,
    failures: list[str],
) -> dict[str, object] | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        failures.append(f"{label} is not UTF-8: {error}")
        return None
    try:
        parsed, parse_failures = decision.parse_g0_json_object(text, label)
    except RecursionError:
        failures.append(f"{label} exceeds the supported JSON nesting depth")
        return None
    failures.extend(parse_failures)
    return None if parse_failures else parsed


def _canonical_utc(value: object) -> bool:
    if not isinstance(value, str) or _CANONICAL_UTC_PATTERN.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def _valid_opaque_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 256
        and value == value.strip()
        and not any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    )


def _valid_provenance_ref(value: object) -> bool:
    if not isinstance(value, str) or _PROVENANCE_REF_PATTERN.fullmatch(value) is None:
        return False
    lowered = value.lower()
    return not any(marker in lowered for marker in _LOCAL_ONLY_PROVENANCE_MARKERS)


def collect_amendment_bundle_failures(
    parent_assurance: object,
    parent_checkpoint: object,
    amendment: object,
    amendment_checkpoint: object,
) -> tuple[str, ...]:
    """Validate four exact commit blobs without consulting the worktree."""

    failures: list[str] = []
    parent_raw = _bounded_snapshot(
        parent_assurance,
        "G0 publication parent assurance blob",
        checkpoint.MAX_ASSURANCE_BYTES,
        failures,
    )
    parent_checkpoint_raw = _bounded_snapshot(
        parent_checkpoint,
        "G0 publication parent checkpoint blob",
        checkpoint.MAX_CHECKPOINT_BYTES,
        failures,
    )
    amendment_raw = _bounded_snapshot(
        amendment,
        "G0 publication amendment blob",
        MAX_AMENDMENT_BYTES,
        failures,
    )
    amendment_checkpoint_raw = _bounded_snapshot(
        amendment_checkpoint,
        "G0 publication amendment checkpoint blob",
        MAX_AMENDMENT_CHECKPOINT_BYTES,
        failures,
    )
    if any(
        value is None
        for value in (
            parent_raw,
            parent_checkpoint_raw,
            amendment_raw,
            amendment_checkpoint_raw,
        )
    ):
        return tuple(failures)

    assert parent_raw is not None
    assert parent_checkpoint_raw is not None
    assert amendment_raw is not None
    assert amendment_checkpoint_raw is not None

    _require_equal(
        _sha256(parent_raw),
        decision.EXPECTED_ASSURANCE_BYTE_SHA256,
        "parent assurance raw SHA-256",
        failures,
    )
    _require_equal(
        _sha256(parent_checkpoint_raw),
        decision.EXPECTED_ASSURANCE_CHECKPOINT_BYTE_SHA256,
        "parent checkpoint raw SHA-256",
        failures,
    )
    _require_equal(
        _sha256(amendment_raw),
        decision.EXPECTED_ASSURANCE_AMENDMENT_BYTE_SHA256,
        "amendment raw SHA-256",
        failures,
    )
    _require_equal(
        _sha256(amendment_checkpoint_raw),
        decision.EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_BYTE_SHA256,
        "amendment checkpoint raw SHA-256",
        failures,
    )
    if failures:
        return tuple(failures)

    parent_document = _parse_snapshot_object(
        parent_raw,
        "G0 publication parent assurance blob",
        failures,
    )
    parent_checkpoint_document = _parse_snapshot_object(
        parent_checkpoint_raw,
        "G0 publication parent checkpoint blob",
        failures,
    )
    amendment_document = _parse_snapshot_object(
        amendment_raw,
        "G0 publication amendment blob",
        failures,
    )
    amendment_checkpoint_document = _parse_snapshot_object(
        amendment_checkpoint_raw,
        "G0 publication amendment checkpoint blob",
        failures,
    )
    if any(
        value is None
        for value in (
            parent_document,
            parent_checkpoint_document,
            amendment_document,
            amendment_checkpoint_document,
        )
    ):
        return tuple(failures)

    assert parent_document is not None
    assert parent_checkpoint_document is not None
    assert amendment_document is not None
    assert amendment_checkpoint_document is not None

    _require_equal(
        decision.canonical_json_sha256(parent_document),
        decision.EXPECTED_ASSURANCE_CANONICAL_SHA256,
        "parent assurance canonical SHA-256",
        failures,
    )
    _require_equal(
        decision.canonical_json_sha256(parent_checkpoint_document),
        decision.EXPECTED_ASSURANCE_CHECKPOINT_CANONICAL_SHA256,
        "parent checkpoint canonical SHA-256",
        failures,
    )
    _require_equal(
        decision.canonical_json_sha256(amendment_document),
        decision.EXPECTED_ASSURANCE_AMENDMENT_CANONICAL_SHA256,
        "amendment canonical SHA-256",
        failures,
    )
    _require_equal(
        decision.canonical_json_sha256(amendment_checkpoint_document),
        decision.EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_CANONICAL_SHA256,
        "amendment checkpoint canonical SHA-256",
        failures,
    )

    _require_equal(
        parent_document.get("assuranceId"),
        "aetherlink_v1_g0_assurance_v1",
        "parent assurance identity",
        failures,
    )
    _require_equal(
        amendment_document.get("amendmentId"),
        "aetherlink_v1_g0_assurance_closure_amendment_v2",
        "amendment identity",
        failures,
    )
    _require_equal(
        amendment_document.get("status"),
        "candidate_not_published_not_authorized",
        "amendment status",
        failures,
    )
    parent_binding = amendment_document.get("parent")
    if not isinstance(parent_binding, dict):
        failures.append("amendment parent binding must be an object")
    else:
        for field, expected in (
            ("assurancePath", PARENT_ASSURANCE_PATH),
            ("assuranceRawByteSha256", _sha256(parent_raw)),
            (
                "assuranceCanonicalSha256",
                decision.canonical_json_sha256(parent_document),
            ),
            ("checkpointPath", PARENT_CHECKPOINT_PATH),
            ("checkpointRawByteSha256", _sha256(parent_checkpoint_raw)),
            (
                "checkpointCanonicalSha256",
                decision.canonical_json_sha256(parent_checkpoint_document),
            ),
        ):
            _require_equal(
                parent_binding.get(field),
                expected,
                f"amendment parent.{field}",
                failures,
            )

    patch_profile = amendment_document.get("patchProfile")
    if not isinstance(patch_profile, dict):
        failures.append("amendment patchProfile must be an object")
    else:
        _require_equal(
            patch_profile.get("allowedOperations"),
            [
                {"op": operation, "path": path}
                for operation, path in decision.EXPECTED_ASSURANCE_AMENDMENT_OPERATIONS
            ],
            "amendment allowed operation order",
            failures,
        )
    effective = decision.apply_assurance_amendment_operations(
        parent_document,
        amendment_document.get("operations"),
        failures,
    )
    effective_sha256 = decision.canonical_json_sha256(effective)
    _require_equal(
        effective_sha256,
        decision.EXPECTED_EFFECTIVE_ASSURANCE_V2_CANONICAL_SHA256,
        "effective assurance canonical SHA-256",
        failures,
    )
    _require_equal(
        effective.get("schemaVersion"),
        "2.0",
        "effective assurance schemaVersion",
        failures,
    )
    closure = effective.get("g0ClosureContract")
    _require_equal(
        closure.get("schemaVersion") if isinstance(closure, dict) else None,
        2,
        "effective closure schemaVersion",
        failures,
    )
    effective_record = amendment_document.get("effectiveAssurance")
    if not isinstance(effective_record, dict):
        failures.append("amendment effectiveAssurance must be an object")
    else:
        _require_equal(
            effective_record.get("canonicalSha256"),
            effective_sha256,
            "amendment effective assurance binding",
            failures,
        )

    parent_readback = amendment_checkpoint_document.get("parentReadback")
    amendment_readback = amendment_checkpoint_document.get("amendmentReadback")
    effective_readback = amendment_checkpoint_document.get("effectiveAssuranceReadback")
    if not isinstance(parent_readback, dict):
        failures.append("amendment checkpoint parentReadback must be an object")
    else:
        for field, expected in (
            ("assurancePath", PARENT_ASSURANCE_PATH),
            ("assuranceRawByteSha256", _sha256(parent_raw)),
            ("checkpointPath", PARENT_CHECKPOINT_PATH),
            ("checkpointRawByteSha256", _sha256(parent_checkpoint_raw)),
            ("result", "match"),
        ):
            _require_equal(
                parent_readback.get(field),
                expected,
                f"amendment checkpoint parentReadback.{field}",
                failures,
            )
    if not isinstance(amendment_readback, dict):
        failures.append("amendment checkpoint amendmentReadback must be an object")
    else:
        for field, expected in (
            ("amendmentPath", AMENDMENT_PATH),
            ("amendmentRawByteSha256", _sha256(amendment_raw)),
            (
                "amendmentCanonicalSha256",
                decision.canonical_json_sha256(amendment_document),
            ),
            ("result", "match"),
        ):
            _require_equal(
                amendment_readback.get(field),
                expected,
                f"amendment checkpoint amendmentReadback.{field}",
                failures,
            )
    if not isinstance(effective_readback, dict):
        failures.append("amendment checkpoint effectiveAssuranceReadback must be an object")
    else:
        _require_equal(
            effective_readback.get("canonicalSha256"),
            effective_sha256,
            "amendment checkpoint effective assurance binding",
            failures,
        )
        _require_equal(
            effective_readback.get("result"),
            "match",
            "amendment checkpoint effective assurance result",
            failures,
        )
    _require_equal(
        amendment_checkpoint_document.get("status"),
        "candidate_observed_not_immutable",
        "amendment checkpoint status",
        failures,
    )
    return tuple(failures)


def _build_candidate_publication_validation_context(
    *,
    reviewed_repository_ref: str,
    reviewed_commit_object_id: str,
    reviewed_target_provenance_ref: str,
    commit_repository_ref: str,
    resolved_commit_object_id: str,
    commit_blobs: tuple[tuple[str, object], ...],
    commit_provenance_ref: str,
    remote_repository_ref: str,
    remote_commit_object_id: str,
    remote_checkpoint_path: str,
    remote_checkpoint_bytes: object,
    remote_readback_at: str,
    remote_provenance_ref: str,
) -> _PublicationValidationContext:
    """Build a candidate-only context from three distinct evidence sources."""

    failures: list[str] = []
    for label, value in (
        ("reviewed repository reference", reviewed_repository_ref),
        ("commit repository reference", commit_repository_ref),
        ("remote repository reference", remote_repository_ref),
    ):
        if not _valid_opaque_text(value):
            failures.append(f"{label} is invalid")
    if re.fullmatch(decision.G0_GIT_OBJECT_ID_PATTERN, reviewed_commit_object_id) is None:
        failures.append("reviewed commit object ID is invalid")
    if re.fullmatch(decision.G0_GIT_OBJECT_ID_PATTERN, resolved_commit_object_id) is None:
        failures.append("resolved commit object ID is invalid")
    if re.fullmatch(decision.G0_GIT_OBJECT_ID_PATTERN, remote_commit_object_id) is None:
        failures.append("remote commit object ID is invalid")
    if reviewed_repository_ref != commit_repository_ref:
        failures.append("commit repository does not match the reviewed target")
    if reviewed_repository_ref != remote_repository_ref:
        failures.append("remote repository does not match the reviewed target")
    if reviewed_commit_object_id != resolved_commit_object_id:
        failures.append("resolved commit does not match the reviewed target")
    if reviewed_commit_object_id != remote_commit_object_id:
        failures.append("remote commit does not match the reviewed target")

    provenance_refs = (
        reviewed_target_provenance_ref,
        commit_provenance_ref,
        remote_provenance_ref,
    )
    if any(not _valid_provenance_ref(value) for value in provenance_refs):
        failures.append("publication context provenance references are invalid")
    if len(set(provenance_refs)) != len(provenance_refs):
        failures.append("review, commit-tree, and remote provenance must be distinct")

    if not isinstance(commit_blobs, tuple) or len(commit_blobs) != len(COMMIT_BLOB_PATHS):
        failures.append("commit blobs must be an ordered tuple of exactly four entries")
        commit_blobs = ()
    observed_paths: list[object] = []
    copied_blobs: list[tuple[str, bytes]] = []
    maximum_by_path = {
        PARENT_ASSURANCE_PATH: checkpoint.MAX_ASSURANCE_BYTES,
        PARENT_CHECKPOINT_PATH: checkpoint.MAX_CHECKPOINT_BYTES,
        AMENDMENT_PATH: MAX_AMENDMENT_BYTES,
        AMENDMENT_CHECKPOINT_PATH: MAX_AMENDMENT_CHECKPOINT_BYTES,
    }
    for index, entry in enumerate(commit_blobs):
        if not isinstance(entry, tuple) or len(entry) != 2:
            failures.append(f"commit blob {index} must be a path/bytes tuple")
            continue
        path, value = entry
        observed_paths.append(path)
        if not isinstance(path, str) or path not in maximum_by_path:
            failures.append(f"commit blob {index} path is not allowlisted")
            continue
        raw = _bounded_snapshot(
            value,
            f"commit blob {path}",
            maximum_by_path[path],
            failures,
        )
        if raw is not None:
            copied_blobs.append((path, raw))
    if tuple(observed_paths) != COMMIT_BLOB_PATHS:
        failures.append("commit blobs must contain the four exact paths in canonical order")

    remote_raw = _bounded_snapshot(
        remote_checkpoint_bytes,
        "remote amendment checkpoint bytes",
        MAX_AMENDMENT_CHECKPOINT_BYTES,
        failures,
    )
    if remote_checkpoint_path != AMENDMENT_CHECKPOINT_PATH:
        failures.append("remote checkpoint path is not the exact amendment checkpoint path")
    if not _canonical_utc(remote_readback_at):
        failures.append("remote readback time is not canonical RFC3339 UTC")

    if len(copied_blobs) == len(COMMIT_BLOB_PATHS):
        failures.extend(
            collect_amendment_bundle_failures(
                *(raw for _, raw in copied_blobs)
            )
        )
        committed_checkpoint = copied_blobs[-1][1]
        if remote_raw is not None and remote_raw != committed_checkpoint:
            failures.append(
                "independent remote checkpoint bytes do not match the exact commit blob"
            )
    if remote_raw is not None:
        _require_equal(
            _sha256(remote_raw),
            decision.EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_BYTE_SHA256,
            "remote amendment checkpoint raw SHA-256",
            failures,
        )

    if failures:
        raise _PublicationValidationContextError(tuple(failures))
    assert remote_raw is not None
    return _PublicationValidationContext(
        _CONTEXT_FACTORY_TOKEN,
        reviewed_repository_ref,
        reviewed_commit_object_id,
        tuple(copied_blobs),
        remote_raw,
        remote_readback_at,
    )


def _collect_composite_publication_receipt_candidate_failures(
    receipt_bytes: object,
    *,
    context: _PublicationValidationContext,
) -> tuple[str, ...]:
    """Validate a candidate receipt without accepting, storing, or activating it."""

    failures: list[str] = []
    if (
        not isinstance(context, _PublicationValidationContext)
        or len(context) != 6
        or tuple.__getitem__(context, 0) is not _CONTEXT_FACTORY_TOKEN
    ):
        return ("publication validation context is not factory-owned",)
    raw, receipt = _parse_bounded_object(
        receipt_bytes,
        "G0 composite publication receipt candidate",
        MAX_PUBLICATION_RECEIPT_BYTES,
        failures,
    )
    if raw is None or receipt is None:
        return tuple(failures)
    if tuple(receipt) != PUBLICATION_RECEIPT_FIELDS:
        failures.append("publication receipt fields or field order are not exact")
    for field in PUBLICATION_RECEIPT_FIELDS:
        if not isinstance(receipt.get(field), str):
            failures.append(f"publication receipt {field} must be a string")

    if re.fullmatch(
        decision.G0_GIT_OBJECT_ID_PATTERN,
        receipt.get("commitObjectId", "") if isinstance(receipt.get("commitObjectId"), str) else "",
    ) is None:
        failures.append("publication receipt commitObjectId is invalid")
    for field in (
        "parentAssuranceSha256",
        "parentCheckpointSha256",
        "amendmentSha256",
        "amendmentCheckpointSha256",
        "effectiveAssuranceCanonicalSha256",
        "remoteReadbackSha256",
    ):
        value = receipt.get(field)
        if not isinstance(value, str) or re.fullmatch(decision.G0_SHA256_PATTERN, value) is None:
            failures.append(f"publication receipt {field} is not lowercase SHA-256")
    if not _canonical_utc(receipt.get("remoteReadbackAt")):
        failures.append("publication receipt remoteReadbackAt is not canonical RFC3339 UTC")

    expected_values = {
        "repositoryRef": context._repository_ref,
        "commitObjectId": context._commit_object_id,
        "parentAssurancePath": PARENT_ASSURANCE_PATH,
        "parentAssuranceSha256": decision.EXPECTED_ASSURANCE_BYTE_SHA256,
        "parentCheckpointPath": PARENT_CHECKPOINT_PATH,
        "parentCheckpointSha256": decision.EXPECTED_ASSURANCE_CHECKPOINT_BYTE_SHA256,
        "amendmentPath": AMENDMENT_PATH,
        "amendmentSha256": decision.EXPECTED_ASSURANCE_AMENDMENT_BYTE_SHA256,
        "amendmentCheckpointPath": AMENDMENT_CHECKPOINT_PATH,
        "amendmentCheckpointSha256": (
            decision.EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_BYTE_SHA256
        ),
        "effectiveAssuranceCanonicalSha256": (
            decision.EXPECTED_EFFECTIVE_ASSURANCE_V2_CANONICAL_SHA256
        ),
        "remoteReadbackAt": context._remote_readback_at,
        "remoteReadbackSha256": _sha256(context._remote_checkpoint_bytes),
        "result": "verified",
    }
    for field, expected in expected_values.items():
        if receipt.get(field) != expected:
            failures.append(f"publication receipt {field} does not match independent evidence")

    failures.extend(
        collect_amendment_bundle_failures(
            *(raw_value for _, raw_value in context._commit_blobs)
        )
    )
    if context._remote_checkpoint_bytes != context._commit_blobs[-1][1]:
        failures.append("context remote bytes no longer match the commit checkpoint blob")
    failures.append(_PUBLICATION_CANDIDATE_DISABLED_MESSAGE)
    return tuple(failures)


__all__ = ["collect_amendment_bundle_failures"]
