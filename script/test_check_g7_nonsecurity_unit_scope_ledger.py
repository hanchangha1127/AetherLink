from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from script import check_g7_nonsecurity_unit_scope_ledger as checker


def write_bytes(path: Path, data: bytes, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def write_json(path: Path, value: object, *, mode: int) -> None:
    write_bytes(path, checker.canonical_json_bytes(value), mode=mode)


class ScopeLedgerPrimitiveTests(unittest.TestCase):
    def test_exact_integer_rejects_boolean(self) -> None:
        with self.assertRaises(checker.ScopeLedgerError):
            checker.exact_int(True, "count")
        self.assertEqual(checker.exact_int(1, "count"), 1)

    def test_manifest_is_sorted_canonical_ascii_json(self) -> None:
        self.assertEqual(
            checker.manifest_sha256(("z", "a")),
            hashlib.sha256(b'["a","z"]').hexdigest(),
        )

    def test_duplicate_json_key_is_rejected(self) -> None:
        with self.assertRaises(checker.ScopeLedgerError):
            checker.parse_canonical_json(b'{"a":1,"a":2}\n', "fixture")

    def test_held_reader_rejects_symlink_and_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            write_bytes(source, b"x")
            symlink = root / "symlink"
            symlink.symlink_to(source)
            with self.assertRaises(checker.ScopeLedgerError):
                checker.read_stable_file(symlink, maximum_bytes=10)
            hardlink = root / "hardlink"
            os.link(source, hardlink)
            with self.assertRaises(checker.ScopeLedgerError):
                checker.read_stable_file(source, maximum_bytes=10)


class ScopeLedgerFixtureTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            swift_identity = "FixtureTests.FixtureTests/testValue"
            android_identity = (
                "protocol:com.localagentbridge.android.core.protocol."
                "ProtocolFixtureTest.encodesValue"
            )
            swift_source = Path("apps/macos/Fixture/Tests/FixtureTests.swift")
            android_source = Path(
                "apps/android/core/protocol/src/test/java/"
                "com/localagentbridge/android/core/protocol/"
                "ProtocolFixtureTest.kt"
            )
            write_bytes(root / "Package.swift", b"// fixture\n")
            write_bytes(
                root / swift_source,
                b"import XCTest\nfinal class FixtureTests: XCTestCase {\n"
                b"    func testValue() { XCTAssertTrue(true) }\n}\n",
            )
            write_bytes(
                root / android_source,
                b"package com.localagentbridge.android.core.protocol\n\n"
                b"import org.junit.Test\n\nclass ProtocolFixtureTest {\n"
                b"    @Test\n    fun encodesValue() = Unit\n}\n",
            )
            write_bytes(
                root / checker.SWIFT_TEST_LIST_RELATIVE_PATH,
                (swift_identity + "\n").encode("ascii"),
                mode=0o600,
            )
            source_closure = checker.source_closure(root)
            ledger = {
                "androidCore": {
                    "discovery": {
                        "manifestSha256": checker.manifest_sha256(
                            (android_identity,)
                        ),
                        "tests": 1,
                    },
                    "entries": [
                        {
                            "auditReasonCode": "fixture_reviewed_execution",
                            "className": (
                                "com.localagentbridge.android.core.protocol."
                                "ProtocolFixtureTest"
                            ),
                            "disposition": "eligible_nonsecurity_no_socket",
                            "identity": android_identity,
                            "methodName": "encodesValue",
                            "reasonCode": "reviewed_no_socket_execution",
                            "sourcePath": android_source.as_posix(),
                            "triggerSymbols": ["encodesValue"],
                        }
                    ],
                },
                "claims": dict(checker.CLAIMS),
                "review": {
                    "method": "per-test-source-and-execution-path-review-v1",
                    "reviewedAt": "2026-08-03",
                    "reviewerModel": "gpt-5.6-sol",
                    "semanticJudgementReproduced": False,
                },
                "schemaVersion": 1,
                "scope": checker.SCOPE,
                "sourceClosure": source_closure,
                "swift": {
                    "discovery": {
                        "manifestSha256": checker.manifest_sha256(
                            (swift_identity,)
                        ),
                        "tests": 1,
                    },
                    "entries": [
                        {
                            "auditReasonCode": "fixture_reviewed_execution",
                            "className": "FixtureTests",
                            "disposition": "eligible_nonsecurity_no_socket",
                            "identity": swift_identity,
                            "methodName": "testValue",
                            "reasonCode": "reviewed_no_socket_execution",
                            "sourcePath": swift_source.as_posix(),
                            "triggerSymbols": ["testValue"],
                        }
                    ],
                },
            }
            ledger_path = root / checker.LEDGER_RELATIVE_PATH
            write_json(ledger_path, ledger, mode=0o644)
            ledger_bytes = ledger_path.read_bytes()
            with (
                mock.patch.object(checker, "SWIFT_DISCOVERY_COUNT", 1),
                mock.patch.object(
                    checker,
                    "SWIFT_DISCOVERY_MANIFEST_SHA256",
                    checker.manifest_sha256((swift_identity,)),
                ),
                mock.patch.object(checker, "ANDROID_CORE_DISCOVERY_COUNT", 1),
                mock.patch.object(
                    checker,
                    "ANDROID_CORE_DISCOVERY_MANIFEST_SHA256",
                    checker.manifest_sha256((android_identity,)),
                ),
                mock.patch.object(checker, "LEDGER_BYTES", len(ledger_bytes)),
                mock.patch.object(
                    checker,
                    "LEDGER_SHA256",
                    hashlib.sha256(ledger_bytes).hexdigest(),
                ),
            ):
                yield {
                    "root": root,
                    "ledger": ledger_path,
                    "document": ledger,
                    "swift_identity": swift_identity,
                    "android_identity": android_identity,
                    "swift_source": root / swift_source,
                }

    def validate(self, fixture: dict[str, object]):
        return checker.read_and_validate_ledger(root=fixture["root"])

    def test_complete_fixture_passes(self) -> None:
        with self.fixture() as fixture:
            _ledger, swift, android = self.validate(fixture)
            self.assertEqual(len(swift), 1)
            self.assertEqual(len(android), 1)
            summary = checker.scope_summary(
                swift,
                android,
                evidence_validated=False,
            )
            self.assertEqual(summary["swift"]["eligibleTests"], 1)
            self.assertEqual(summary["androidCore"]["unclassifiedTests"], 0)

    def test_boolean_schema_version_is_rejected(self) -> None:
        with self.fixture() as fixture:
            document = fixture["document"]
            document["schemaVersion"] = True
            write_json(fixture["ledger"], document, mode=0o644)
            with self.assertRaisesRegex(
                checker.ScopeLedgerError,
                "exact integer",
            ):
                checker.read_and_validate_ledger(
                    root=fixture["root"],
                    require_pin=False,
                )

    def test_unknown_disposition_is_rejected(self) -> None:
        with self.fixture() as fixture:
            document = fixture["document"]
            document["swift"]["entries"][0]["disposition"] = "other"
            write_json(fixture["ledger"], document, mode=0o644)
            with self.assertRaisesRegex(
                checker.ScopeLedgerError,
                "disposition is not allowed",
            ):
                checker.read_and_validate_ledger(
                    root=fixture["root"],
                    require_pin=False,
                )

    def test_missing_identity_is_rejected(self) -> None:
        with self.fixture() as fixture:
            document = fixture["document"]
            document["swift"]["entries"] = []
            write_json(fixture["ledger"], document, mode=0o644)
            with self.assertRaisesRegex(
                checker.ScopeLedgerError,
                "entry count differs",
            ):
                checker.read_and_validate_ledger(
                    root=fixture["root"],
                    require_pin=False,
                )

    def test_source_drift_is_rejected(self) -> None:
        with self.fixture() as fixture:
            write_bytes(fixture["swift_source"], b"// drift\n")
            with self.assertRaisesRegex(
                checker.ScopeLedgerError,
                "source closure differs",
            ):
                checker.read_and_validate_ledger(
                    root=fixture["root"],
                    require_pin=False,
                )

    def test_ledger_mode_is_exact(self) -> None:
        with self.fixture() as fixture:
            fixture["ledger"].chmod(0o600)
            with self.assertRaisesRegex(checker.ScopeLedgerError, "file mode differs"):
                checker.read_and_validate_ledger(
                    root=fixture["root"],
                    require_pin=False,
                )

    def test_evidence_binds_exact_eligible_manifests(self) -> None:
        with self.fixture() as fixture:
            _ledger, swift, android = self.validate(fixture)
            swift_identity = fixture["swift_identity"]
            parent = {
                "artifacts": {},
                "contract": (
                    "aetherlink-g7-nonsecurity-merge-full-current-parent-v1"
                ),
                "coverage": {
                    "reviewedExecuted": {
                        "manifestSha256": checker.manifest_sha256(
                            (swift_identity,)
                        ),
                        "tests": 1,
                    },
                    "noSocketExecuted": {
                        "manifestSha256": checker.manifest_sha256(
                            (swift_identity,)
                        ),
                        "tests": 1,
                    },
                    "localSocketExecuted": {
                        "manifestSha256": checker.manifest_sha256(()),
                        "tests": 0,
                    },
                },
                "execution": {},
                "limitations": {
                    "canonicalG7ExitClaimed": False,
                    "canonicalMergeFullClaimed": False,
                    "completeSwiftSuiteClaimed": False,
                    "securityAuthenticationOrCryptographyExecuted": False,
                    "v1Claimed": False,
                },
                "result": "passed",
                "schemaVersion": 1,
                "sourceInputs": {},
            }
            write_json(
                fixture["root"] / checker.SWIFT_PARENT_RESULT_RELATIVE_PATH,
                parent,
                mode=0o600,
            )
            protocol_entries = [entry for entry in android]
            binding = {
                "contract": "fixture",
                "reports": [],
                "runMarker": {},
                "sourceInputs": {},
                "testcaseManifestSha256": (
                    checker.android_binding_manifest_sha256(protocol_entries)
                ),
                "tests": 1,
            }
            write_json(
                fixture["root"]
                / checker.ANDROID_BINDING_RELATIVE_PATHS["protocol"],
                binding,
                mode=0o600,
            )
            empty_binding = dict(binding)
            empty_binding["tests"] = 0
            empty_binding["testcaseManifestSha256"] = (
                checker.android_binding_manifest_sha256(())
            )
            write_json(
                fixture["root"]
                / checker.ANDROID_BINDING_RELATIVE_PATHS["transport"],
                empty_binding,
                mode=0o600,
            )
            checker.validate_swift_evidence(fixture["root"], swift)
            checker.validate_android_evidence(fixture["root"], android)
            parent["coverage"]["reviewedExecuted"]["tests"] = True
            write_json(
                fixture["root"] / checker.SWIFT_PARENT_RESULT_RELATIVE_PATH,
                parent,
                mode=0o600,
            )
            with self.assertRaises(checker.ScopeLedgerError):
                checker.validate_swift_evidence(fixture["root"], swift)


if __name__ == "__main__":
    unittest.main()
