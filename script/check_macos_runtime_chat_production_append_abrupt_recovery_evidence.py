#!/usr/bin/env python3
"""Independently validate production-append abrupt-recovery evidence bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent.parent
RESULT_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "macos-runtime-chat-sqlite-production-append-abrupt-recovery-v1"
)
REPEATABILITY_SCOPE = RESULT_SCOPE + "-repeatability"
CHECK_SCOPE = RESULT_SCOPE + "-independent-readback"
MAXIMUM_EVIDENCE_BYTES = 64 * 1_024
SOURCE_INPUT_PATHS = (
    "apps/macos/CompanionCore/Sources/SQLiteRuntimeChatEventStore.swift",
    (
        "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources/"
        "RuntimeChatSQLiteCrossProcessQA.swift"
    ),
    "script/run_macos_runtime_chat_production_append_abrupt_recovery_smoke.py",
)


class EvidenceError(RuntimeError):
    pass


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("evidence repeats a JSON key")
        result[key] = value
    return result


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def read_owner_only_json(
    path: Path,
    *,
    label: str,
) -> tuple[dict[str, Any], bytes]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise EvidenceError(f"{label} could not be opened") from error
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > MAXIMUM_EVIDENCE_BYTES
        ):
            raise EvidenceError(f"{label} identity is invalid")
        payload = bytearray()
        while len(payload) <= MAXIMUM_EVIDENCE_BYTES:
            chunk = os.read(
                descriptor,
                min(4_096, MAXIMUM_EVIDENCE_BYTES + 1 - len(payload)),
            )
            if not chunk:
                break
            payload.extend(chunk)
        after = os.fstat(descriptor)
        if (
            len(payload) != before.st_size
            or len(payload) > MAXIMUM_EVIDENCE_BYTES
            or (before.st_dev, before.st_ino, before.st_mode, before.st_size)
            != (after.st_dev, after.st_ino, after.st_mode, after.st_size)
        ):
            raise EvidenceError(f"{label} changed while being read")
    finally:
        os.close(descriptor)
    frozen = bytes(payload)
    try:
        parsed = json.loads(
            frozen,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"{label} is not canonical JSON") from error
    if type(parsed) is not dict or frozen != canonical_bytes(parsed):
        raise EvidenceError(f"{label} bytes are not canonical")
    return parsed, frozen


def exact_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            exact_equal(actual[key], value)
            for key, value in expected.items()
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            exact_equal(actual_value, expected_value)
            for actual_value, expected_value in zip(actual, expected)
        )
    return actual == expected


def current_source_inputs(
    *,
    root: Path = ROOT,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative_path in SOURCE_INPUT_PATHS:
        path = root / relative_path
        try:
            before = path.lstat()
            payload = path.read_bytes()
            after = path.lstat()
        except OSError as error:
            raise EvidenceError("source input could not be read") from error
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino, before.st_mode, before.st_size)
            != (after.st_dev, after.st_ino, after.st_mode, after.st_size)
            or len(payload) != before.st_size
        ):
            raise EvidenceError("source input identity is invalid")
        records.append({
            "byteCount": len(payload),
            "path": relative_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    return records


def expected_checkpoint() -> dict[str, Any]:
    return {
        "databaseCacheFlushed": True,
        "eventID": "qa-writer-a-event-0000",
        "ownerDeviceID": "qa-owner-a",
        "phase": "after-validated-state-and-cache-flush-before-commit",
        "requestID": "qa-writer-a-request-0000",
        "schemaVersion": 1,
        "status": "ready-for-abrupt-termination",
        "transactionOpen": True,
        "writePath": "SQLiteRuntimeChatEventStore.append",
        "writer": "writer-a",
    }


def expected_result(
    source_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "abruptTermination": {
            "checkpoint": expected_checkpoint(),
            "dirtyDatabaseBeforeRecovery": {
                "appendStateMutationRevision": 1,
                "appendStateValidatedRevision": 1,
                "eventAndFTSPresent": True,
                "eventCount": 1,
                "ftsEventCount": 1,
                "immutableReadIgnoredJournal": True,
                "searchProjectionVersion": 2,
            },
            "journal": {
                "bytesStableAcrossSignal": True,
                "hotAfterWriterTermination": True,
                "hotJournalHeaderObserved": True,
                "journalMode": "delete",
                "ownerOnlyMode": "0600",
                "pageRecordCountPositive": True,
                "pageSize": 4_096,
                "populatedBeforeSignal": True,
                "sectorSize": 512,
            },
            "processGroup": "new-session-exact-child-only",
            "terminationSignal": "SIGKILL",
            "writerProcessReaped": True,
        },
        "cleanup": "passed",
        "final": {
            "appendStateMutationRevision": 48,
            "appendStateValidatedRevision": 48,
            "eventCount": 48,
            "eventZeroCount": 1,
            "ftsEventCount": 48,
            "hotJournalCleared": True,
            "integrityCheck": "ok",
            "searchProjectionVersion": 2,
            "sequencesContiguous": True,
        },
        "finalReadbackProcess": "independent-production-store",
        "limitations": [
            "qa-forced-mid-transaction-database-cache-flush",
            "same-host-exact-child-process-termination-only",
            "not-natural-commit-timing-or-power-loss-evidence",
            "not-arbitrary-history-or-long-soak-evidence",
            "not-clean-machine-signed-distribution-or-device-evidence",
        ],
        "permissions": {
            "checkpointAndSQLiteFiles": "0600",
            "databaseRoot": "0700",
        },
        "recovered": {
            "appendStateMutationRevision": 0,
            "appendStateValidatedRevision": -1,
            "eventCount": 0,
            "eventZeroCount": 0,
            "ftsEventCount": 0,
            "hotJournalCleared": True,
            "integrityCheck": "ok",
            "searchProjectionVersion": 0,
            "sequencesContiguous": True,
        },
        "recoveryReadbackProcess": "independent-production-store",
        "retry": {
            "eventCount": 48,
            "status": "passed",
            "writer": "writer-a",
        },
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": RESULT_SCOPE,
        "sourceInputs": source_inputs,
        "status": "passed",
        "writePath": "SQLiteRuntimeChatEventStore.append",
    }


def expected_receipt(result_bytes: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(result_bytes).hexdigest()
    byte_count = len(result_bytes)
    return {
        "resultByteCount": byte_count,
        "resultSha256": digest,
        "runs": [
            {
                "ordinal": ordinal,
                "resultByteCount": byte_count,
                "resultSha256": digest,
            }
            for ordinal in (1, 2)
        ],
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": REPEATABILITY_SCOPE,
        "status": "passed",
    }


def check_evidence(
    result_path: Path,
    receipt_path: Path,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    try:
        if result_path.resolve() == receipt_path.resolve():
            raise EvidenceError("result and receipt paths must be distinct")
    except OSError as error:
        raise EvidenceError("evidence paths could not be resolved") from error
    result, result_bytes = read_owner_only_json(
        result_path,
        label="production append result",
    )
    receipt, _ = read_owner_only_json(
        receipt_path,
        label="production append repeatability receipt",
    )
    source_inputs = current_source_inputs(root=root)
    if not exact_equal(result, expected_result(source_inputs)):
        raise EvidenceError(
            "production append result differs from current source and schema"
        )
    if not exact_equal(receipt, expected_receipt(result_bytes)):
        raise EvidenceError(
            "production append repeatability receipt does not bind the result"
        )
    result_again, result_bytes_again = read_owner_only_json(
        result_path,
        label="production append result",
    )
    receipt_again, receipt_bytes_again = read_owner_only_json(
        receipt_path,
        label="production append repeatability receipt",
    )
    if (
        result_again != result
        or result_bytes_again != result_bytes
        or receipt_again != receipt
        or receipt_bytes_again != canonical_bytes(receipt)
    ):
        raise EvidenceError("evidence bytes changed across independent readback")
    return {
        "resultByteCount": len(result_bytes),
        "resultSha256": hashlib.sha256(result_bytes).hexdigest(),
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scope": CHECK_SCOPE,
        "sourceInputCount": len(source_inputs),
        "status": "passed",
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Independently check production-append abrupt-recovery evidence."
        )
    )
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument(
        "--repeatability-receipt",
        required=True,
        type=Path,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = check_evidence(
            Path(os.path.abspath(arguments.result)),
            Path(os.path.abspath(arguments.repeatability_receipt)),
        )
        print(canonical_bytes(result).decode("ascii").rstrip("\n"))
        return 0
    except EvidenceError as error:
        print(
            f"Runtime-chat production append recovery readback failed: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
