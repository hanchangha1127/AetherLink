#!/usr/bin/env python3
"""Mutation tests for the unpublished V1 G0 assurance readback candidate."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from script import check_v1_g0_checkpoint as CHECKER


class V1G0CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = CHECKER.CHECKPOINT_PATH.read_bytes()
        cls.document = CHECKER.parse_json_bytes(
            cls.raw,
            "checkpoint fixture",
            CHECKER.MAX_CHECKPOINT_BYTES,
        )

    def mutated(self) -> dict[str, object]:
        return copy.deepcopy(self.document)

    def assert_rejected(self, candidate: dict[str, object]) -> None:
        with self.assertRaises(CHECKER.CheckpointValidationError):
            CHECKER.validate_document(candidate)

    def test_canonical_candidate_artifact_and_live_readback_pass(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.raw).hexdigest(),
            CHECKER.EXPECTED_CHECKPOINT_BYTE_SHA256,
        )
        self.assertEqual(CHECKER.collect_failures(), [])
        CHECKER.validate_checkpoint_artifact()
        CHECKER.validate_document(self.mutated())
        self.assertEqual(
            len(self.document["sourceHashReadback"]["records"]),
            29,
        )

    def test_checkpoint_raw_hash_precedes_json_parse_and_source_readback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "docs/v1/g0/assurance-checkpoint-readback-v1.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(self.raw + b" ")
            with mock.patch.object(CHECKER, "parse_json_bytes") as parser:
                with mock.patch.object(
                    CHECKER,
                    "sha256_repository_file",
                ) as source_hasher:
                    with self.assertRaisesRegex(
                        CHECKER.CheckpointValidationError,
                        "checkpoint byte sha256",
                    ):
                        CHECKER.validate_checkpoint_artifact(root)
                    parser.assert_not_called()
                    source_hasher.assert_not_called()

    def test_duplicate_nonfinite_missing_unknown_and_type_confusion_fail(self) -> None:
        duplicate = self.raw.decode("utf-8").replace(
            '  "schemaVersion": "1.0",',
            '  "schemaVersion": "1.0",\n  "schemaVersion": "1.0",',
            1,
        )
        with self.assertRaisesRegex(
            CHECKER.CheckpointValidationError,
            "duplicate JSON name",
        ):
            CHECKER.parse_json_bytes(
                duplicate.encode("utf-8"),
                "duplicate checkpoint",
                CHECKER.MAX_CHECKPOINT_BYTES,
            )
        for token in (b"NaN", b"Infinity", b"1e999", b"-1e999"):
            nonfinite = self.raw.replace(b'"recordCount": 29', b'"recordCount": ' + token)
            with self.subTest(token=token):
                with self.assertRaisesRegex(
                    CHECKER.CheckpointValidationError,
                    "non-finite JSON number",
                ):
                    CHECKER.parse_json_bytes(
                        nonfinite,
                        "nonfinite checkpoint",
                        CHECKER.MAX_CHECKPOINT_BYTES,
                    )
        with self.assertRaisesRegex(
            CHECKER.CheckpointValidationError,
            "canonical JSON cannot encode",
        ):
            CHECKER.canonical_json_sha256({"number": float("inf")})
        oversized_integer = self.raw.replace(
            b'"recordCount": 29',
            b'"recordCount": ' + b"9" * (CHECKER.MAX_JSON_INTEGER_DIGITS + 1),
        )
        with self.assertRaisesRegex(
            CHECKER.CheckpointValidationError,
            "JSON integer exceeds 128 digits",
        ):
            CHECKER.parse_json_bytes(
                oversized_integer,
                "oversized-integer checkpoint",
                CHECKER.MAX_CHECKPOINT_BYTES,
            )

        missing = self.mutated()
        missing.pop("assuranceReadback")
        self.assert_rejected(missing)
        unknown = self.mutated()
        unknown["ownerApproval"] = "accepted"
        self.assert_rejected(unknown)
        confused = self.mutated()
        confused["sourceHashReadback"]["recordCount"] = True
        self.assert_rejected(confused)

    def test_assurance_hashes_and_ordered_source_projection_cannot_drift(self) -> None:
        for field in ("rawByteSha256", "canonicalSha256"):
            candidate = self.mutated()
            candidate["assuranceReadback"][field] = "0" * 64
            self.assert_rejected(candidate)

        mutations = []
        omitted = self.mutated()
        omitted["sourceHashReadback"]["records"].pop()
        mutations.append(omitted)
        reordered = self.mutated()
        reordered["sourceHashReadback"]["records"][0:2] = reversed(
            reordered["sourceHashReadback"]["records"][0:2]
        )
        mutations.append(reordered)
        duplicated = self.mutated()
        duplicated["sourceHashReadback"]["records"][1] = copy.deepcopy(
            duplicated["sourceHashReadback"]["records"][0]
        )
        mutations.append(duplicated)
        self_referential = self.mutated()
        self_referential["sourceHashReadback"]["records"].append(
            {
                "path": "docs/v1/g0/assurance-checkpoint-readback-v1.json",
                "role": "checkpoint_self_reference",
                "declaredSha256": CHECKER.EXPECTED_CHECKPOINT_BYTE_SHA256,
                "observedByteSha256": CHECKER.EXPECTED_CHECKPOINT_BYTE_SHA256,
                "result": "match",
            }
        )
        self_referential["sourceHashReadback"]["recordCount"] = 30
        mutations.append(self_referential)

        for field, value in (
            ("path", "docs/v1/g0/decision-v1.md"),
            ("role", "fabricated_role"),
            ("declaredSha256", "0" * 64),
            ("observedByteSha256", "0" * 64),
            ("result", "mismatch_ignored"),
        ):
            candidate = self.mutated()
            candidate["sourceHashReadback"]["records"][0][field] = value
            mutations.append(candidate)
        for candidate in mutations:
            self.assert_rejected(candidate)

    def test_live_source_bytes_are_rehashed_in_exact_assurance_order(self) -> None:
        expected_paths = [
            CHECKER.ROOT / record["path"]
            for record in self.document["sourceHashReadback"]["records"]
        ]
        observed_paths: list[Path] = []
        real_hasher = CHECKER.sha256_repository_file

        def recording_hasher(root: Path, relative_path: object, label: str) -> str:
            observed_paths.append(root / str(relative_path))
            return real_hasher(root, relative_path, label)

        with mock.patch.object(
            CHECKER,
            "sha256_repository_file",
            side_effect=recording_hasher,
        ):
            CHECKER.validate_document(self.mutated())
        self.assertEqual(observed_paths, expected_paths)

        first = expected_paths[0]

        def drifted_hasher(root: Path, relative_path: object, label: str) -> str:
            path = root / str(relative_path)
            return "0" * 64 if path == first else real_hasher(root, relative_path, label)

        with mock.patch.object(
            CHECKER,
            "sha256_repository_file",
            side_effect=drifted_hasher,
        ):
            with self.assertRaisesRegex(
                CHECKER.CheckpointValidationError,
                "current byte sha256",
            ):
                CHECKER.validate_document(self.mutated())

    def test_personal_g1a_compatibility_is_exact_hash_allowlisted(self) -> None:
        for relative_path, (
            reviewed_current_sha256,
            preserved_g0_sha256,
        ) in CHECKER.PERSONAL_G1A_HISTORICAL_SOURCE_COMPATIBILITY.items():
            self.assertEqual(
                CHECKER.historical_source_compatible_sha256(
                    relative_path,
                    reviewed_current_sha256,
                ),
                preserved_g0_sha256,
            )
            self.assertEqual(
                CHECKER.historical_source_compatible_sha256(
                    relative_path,
                    "0" * 64,
                ),
                "0" * 64,
            )
        self.assertEqual(
            CHECKER.historical_source_compatible_sha256(
                "unreviewed/source.kt",
                "1" * 64,
            ),
            "1" * 64,
        )

    def test_pairing_store_personal_g1a_allowlist_rejects_one_byte_drift(self) -> None:
        relative_path = (
            "apps/android/core/pairing/src/main/java/"
            "com/localagentbridge/android/core/pairing/PairingStore.kt"
        )
        raw = (CHECKER.ROOT / relative_path).read_bytes()
        current_sha256 = hashlib.sha256(raw).hexdigest()
        reviewed_current_sha256, _ = (
            CHECKER.PERSONAL_G1A_HISTORICAL_SOURCE_COMPATIBILITY[relative_path]
        )
        self.assertEqual(current_sha256, reviewed_current_sha256)

        drifted_sha256 = hashlib.sha256(raw + b"\n").hexdigest()
        self.assertEqual(
            CHECKER.historical_source_compatible_sha256(
                relative_path,
                drifted_sha256,
            ),
            drifted_sha256,
        )
        real_hasher = CHECKER.sha256_repository_file

        def drifted_hasher(root: Path, candidate: object, label: str) -> str:
            if str(candidate) == relative_path:
                return drifted_sha256
            return real_hasher(root, candidate, label)

        with mock.patch.object(
            CHECKER,
            "sha256_repository_file",
            side_effect=drifted_hasher,
        ):
            with self.assertRaisesRegex(
                CHECKER.CheckpointValidationError,
                r"sourceRecords\[23\] current byte sha256",
            ):
                CHECKER.validate_document(self.mutated())

    def test_path_policy_rejects_escape_missing_directory_and_symlink(self) -> None:
        def open_and_close(root: Path, value: object) -> None:
            file_descriptor = CHECKER.open_repository_file(
                root,
                value,
                "mutated source",
            )
            CHECKER.os.close(file_descriptor)

        for value in ("/tmp/escape", "../escape", "docs/../escape", "docs\\escape"):
            with self.assertRaises(CHECKER.CheckpointValidationError):
                open_and_close(CHECKER.ROOT, value)
        with self.assertRaises(CHECKER.CheckpointValidationError):
            open_and_close(CHECKER.ROOT, "missing-source")
        with self.assertRaises(CHECKER.CheckpointValidationError):
            open_and_close(CHECKER.ROOT, "docs")
        with self.assertRaises(CHECKER.CheckpointValidationError):
            open_and_close(CHECKER.ROOT, "nul\0source")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_text("safe", encoding="utf-8")
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaisesRegex(
                CHECKER.CheckpointValidationError,
                "symlink",
            ):
                open_and_close(root, "link")

    def test_same_descriptor_read_and_hash_reject_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source").write_text("stable bytes", encoding="utf-8")
            real_fstat = CHECKER.os.fstat

            def assert_drift_rejected(operation) -> None:
                call_count = 0

                def drifting_fstat(file_descriptor: int):
                    nonlocal call_count
                    call_count += 1
                    observed = real_fstat(file_descriptor)
                    if call_count != 3:
                        return observed
                    changed = mock.Mock()
                    for field in (
                        "st_dev",
                        "st_ino",
                        "st_mode",
                        "st_size",
                        "st_mtime_ns",
                        "st_ctime_ns",
                    ):
                        setattr(changed, field, getattr(observed, field))
                    changed.st_ctime_ns += 1
                    return changed

                with mock.patch.object(
                    CHECKER.os,
                    "fstat",
                    side_effect=drifting_fstat,
                ):
                    with self.assertRaisesRegex(
                        CHECKER.CheckpointValidationError,
                        "changed while it was being read",
                    ):
                        operation(root)
                self.assertEqual(call_count, 3)

            assert_drift_rejected(
                lambda root: CHECKER.read_repository_bytes(
                    root,
                    "source",
                    "mutated source",
                    1024,
                )
            )
            assert_drift_rejected(
                lambda root: CHECKER.sha256_repository_file(
                    root,
                    "source",
                    "mutated source",
                )
            )

            active_directory = root / "active"
            active_directory.mkdir()
            (active_directory / "source").write_text(
                "path-stable bytes",
                encoding="utf-8",
            )
            replacement_directory = root / "replacement-directory"
            replacement_directory.mkdir()
            (replacement_directory / "source").write_text(
                "different bytes",
                encoding="utf-8",
            )
            real_read = CHECKER.os.read
            swapped = False

            def swapping_read(file_descriptor: int, size: int) -> bytes:
                nonlocal swapped
                chunk = real_read(file_descriptor, size)
                if chunk and not swapped:
                    swapped = True
                    CHECKER.os.replace(active_directory, root / "original-directory")
                    CHECKER.os.replace(replacement_directory, active_directory)
                return chunk

            with mock.patch.object(CHECKER.os, "read", side_effect=swapping_read):
                with self.assertRaisesRegex(
                    CHECKER.CheckpointValidationError,
                    "repository path changed while it was being read",
                ):
                    CHECKER.read_repository_bytes(
                        root,
                        "active/source",
                        "mutated source",
                        1024,
                    )
            self.assertTrue(swapped)

            oversized = root / "oversized"
            with oversized.open("wb") as handle:
                handle.truncate(CHECKER.MAX_SOURCE_BYTES + 1)
            with self.assertRaisesRegex(
                CHECKER.CheckpointValidationError,
                f"exceeds {CHECKER.MAX_SOURCE_BYTES} bytes",
            ):
                CHECKER.sha256_repository_file(
                    root,
                    "oversized",
                    "oversized source",
                )

    def test_owner_publication_blockers_and_gates_cannot_be_promoted(self) -> None:
        mutations: list[dict[str, object]] = []
        for field, value in (
            ("ownerAcceptance", "accepted"),
            ("publishedCheckpoint", "present"),
            ("g0AssurancePacketStatus", "passed"),
            ("g0AssuranceBlockerClosed", True),
            ("g0ExitComplete", True),
            ("g1aMayStartNow", True),
        ):
            candidate = self.mutated()
            candidate["evidenceDisposition"][field] = value
            mutations.append(candidate)
        removed_blocker = self.mutated()
        removed_blocker["evidenceDisposition"]["remainingBlockerIds"].pop()
        mutations.append(removed_blocker)
        published = self.mutated()
        published["status"] = "published_immutable"
        mutations.append(published)
        publication_root = self.mutated()
        publication_root["immutability"]["publicationRoot"] = "git:deadbeef"
        mutations.append(publication_root)
        for candidate in mutations:
            self.assert_rejected(candidate)

    def test_every_authority_and_boolean_gate_requires_exact_type(self) -> None:
        for field, expected in CHECKER.EXPECTED_AUTHORITY.items():
            for mutation in ((not expected), int(expected)):
                candidate = self.mutated()
                candidate["authority"][field] = mutation
                self.assert_rejected(candidate)

        for section, field, mutation in (
            ("evidenceDisposition", "g0AssuranceBlockerClosed", 0),
            ("evidenceDisposition", "g0ExitComplete", 0),
            ("evidenceDisposition", "g1aMayStartNow", 0),
            ("immutability", "externalPublicationRootRequired", 1),
        ):
            candidate = self.mutated()
            candidate[section][field] = mutation
            self.assert_rejected(candidate)

    def test_assurance_raw_and_canonical_hashes_are_independently_checked(self) -> None:
        real_reader = CHECKER.read_fixed_bytes

        def whitespace_reader(
            root: Path,
            relative_path: str,
            label: str,
            maximum_bytes: int,
        ):
            raw = real_reader(root, relative_path, label, maximum_bytes)
            if relative_path == "docs/v1/g0/assurance-v1.json":
                return raw + b" "
            return raw

        with mock.patch.object(CHECKER, "read_fixed_bytes", side_effect=whitespace_reader):
            with self.assertRaisesRegex(
                CHECKER.CheckpointValidationError,
                "current assurance byte sha256",
            ):
                CHECKER.validate_document(self.mutated())

        real_parser = CHECKER.parse_json_bytes

        def semantic_parser(raw: bytes, label: str, maximum_bytes: int):
            value = real_parser(raw, label, maximum_bytes)
            if label == "G0 assurance":
                value = copy.deepcopy(value)
                value["recordedDate"] = "2026-07-21"
            return value

        with mock.patch.object(CHECKER, "parse_json_bytes", side_effect=semantic_parser):
            with self.assertRaisesRegex(
                CHECKER.CheckpointValidationError,
                "current assurance canonical sha256",
            ):
                CHECKER.validate_document(self.mutated())

    def test_validator_uses_no_glob_git_process_network_or_write_path(self) -> None:
        source = Path(CHECKER.__file__).read_text(encoding="utf-8")
        for forbidden in (
            ".glob(",
            ".rglob(",
            "subprocess",
            "import socket",
            "urllib",
            ".write_bytes(",
            ".write_text(",
            ".unlink(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
