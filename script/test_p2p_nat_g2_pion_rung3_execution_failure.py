#!/usr/bin/env python3
"""Tests for immutable G2 Pion rung-three failure evidence."""

from __future__ import annotations

import ast
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung3_execution_failure.py"


def read_exact_source(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(os.fspath(path), flags)
    try:
        identity = os.fstat(descriptor)
        remaining = identity.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                raise RuntimeError("unexpected EOF while loading checker")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise RuntimeError("checker grew while loading")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


CHECKER_SOURCE = read_exact_source(CHECKER_PATH)
CHECKER = types.ModuleType("g2_rung3_execution_failure_checker_under_test")
CHECKER.__file__ = os.fspath(CHECKER_PATH)
CHECKER.__package__ = None
exec(
    compile(
        CHECKER_SOURCE,
        os.fspath(CHECKER_PATH),
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    ),
    CHECKER.__dict__,
    CHECKER.__dict__,
)


def write_bytes_exclusive(path: Path, data: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(
        os.fspath(path),
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
        mode,
    )
    try:
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(path, mode, follow_symlinks=False)


@contextmanager
def synthetic_runtime_root():
    with tempfile.TemporaryDirectory(prefix="aetherlink-g2-r3-failure-") as temporary:
        root = Path(temporary).resolve()
        review = root.joinpath(*CHECKER.CLAIM_DIRECTORY_PARTS)
        review.mkdir(parents=True)
        os.chmod(review, 0o700)
        write_bytes_exclusive(
            review / CHECKER.CLAIM_NAME,
            CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM),
        )
        yield root, review


def load_json(path: str):
    raw = read_exact_source(ROOT / path)
    return CHECKER.strict_json(raw, path)


class StrictJsonTests(unittest.TestCase):
    def test_canonical_claim_shape_and_digest(self):
        raw = CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM)
        self.assertEqual(len(raw), CHECKER.EXPECTED_CLAIM_BYTES)
        self.assertEqual(CHECKER.sha256_bytes(raw), CHECKER.EXPECTED_CLAIM_RAW_SHA256)
        self.assertEqual(CHECKER.strict_json(raw, "claim"), CHECKER.EXPECTED_CLAIM)

    def test_duplicate_key_is_rejected(self):
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.strict_json(b'{"a":1,"a":2}\n', "duplicate")

    def test_cr_missing_lf_nonfinite_and_invalid_utf8_are_rejected(self):
        samples = (
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":NaN}\n',
            b'{"a":"\xff"}\n',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.strict_json(sample, "invalid")

    def test_placeholder_discovery_is_recursive(self):
        self.assertEqual(
            CHECKER.unresolved_placeholders(
                {"a": [{"b": "__PENDING_VALUE__"}]}, "root"
            ),
            ["root.a[0].b"],
        )


class SyntheticRuntimeTests(unittest.TestCase):
    def test_valid_claim_and_exact_absences_pass(self):
        with synthetic_runtime_root() as (root, _):
            observed = CHECKER.SafeClaimObservationReader(root).inspect()
        self.assertEqual(observed["claimPath"], CHECKER.CLAIM_PATH)
        self.assertEqual(observed["checkedAbsenceNames"], list(CHECKER.ABSENCE_NAMES))

    def test_every_checked_name_rejects_file_directory_and_links(self):
        variants = ("file", "directory", "symlink", "dangling_symlink")
        for name in CHECKER.ABSENCE_NAMES:
            for variant in variants:
                with self.subTest(name=name, variant=variant):
                    with synthetic_runtime_root() as (root, review):
                        target = review / name
                        if variant == "file":
                            write_bytes_exclusive(target, b"x\n")
                        elif variant == "directory":
                            target.mkdir()
                        elif variant == "symlink":
                            source = review / f"{name}.target"
                            write_bytes_exclusive(source, b"x\n")
                            os.symlink(source.name, target)
                        else:
                            os.symlink("missing-target", target)
                        with self.assertRaises(CHECKER.CheckError):
                            CHECKER.SafeClaimObservationReader(root).inspect()

    def test_missing_or_byte_mutated_claim_is_rejected(self):
        for variant in ("missing", "mutated"):
            with self.subTest(variant=variant):
                with synthetic_runtime_root() as (root, review):
                    claim = review / CHECKER.CLAIM_NAME
                    claim.unlink()
                    if variant == "mutated":
                        raw = bytearray(
                            CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM)
                        )
                        raw[0] = ord("[")
                        write_bytes_exclusive(claim, bytes(raw))
                    with self.assertRaises(CHECKER.CheckError):
                        CHECKER.SafeClaimObservationReader(root).inspect()

    def test_noncanonical_claim_encodings_are_rejected(self):
        canonical = CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM)
        variants = {
            "extra-key": canonical[:-2] + b',"x":0}\n',
            "duplicate-key": canonical[:-2]
            + b',"schemaVersion":"1.0"}\n',
            "crlf": canonical[:-1] + b"\r\n",
            "missing-lf": canonical[:-1],
        }
        for label, raw in variants.items():
            with self.subTest(label=label):
                with synthetic_runtime_root() as (root, review):
                    claim = review / CHECKER.CLAIM_NAME
                    claim.unlink()
                    write_bytes_exclusive(claim, raw)
                    with self.assertRaises(CHECKER.CheckError):
                        CHECKER.SafeClaimObservationReader(root).inspect()

    def test_wrong_claim_mode_hardlink_and_symlink_are_rejected(self):
        with synthetic_runtime_root() as (root, review):
            claim = review / CHECKER.CLAIM_NAME
            os.chmod(claim, 0o640)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.SafeClaimObservationReader(root).inspect()

        with synthetic_runtime_root() as (root, review):
            claim = review / CHECKER.CLAIM_NAME
            source = review / "claim-source"
            claim.rename(source)
            os.link(source, claim)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.SafeClaimObservationReader(root).inspect()

        with synthetic_runtime_root() as (root, review):
            claim = review / CHECKER.CLAIM_NAME
            source = review / "claim-source"
            claim.rename(source)
            os.symlink(source.name, claim)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.SafeClaimObservationReader(root).inspect()

    def test_wrong_review_directory_mode_is_rejected(self):
        with synthetic_runtime_root() as (root, review):
            os.chmod(review, 0o750)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.SafeClaimObservationReader(root).inspect()

    def test_symlinked_final_or_ancestor_directory_is_rejected(self):
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-g2-r3-final-link-"
        ) as temporary:
            root = Path(temporary).resolve()
            parent = root.joinpath(*CHECKER.CLAIM_DIRECTORY_PARTS[:-1])
            parent.mkdir(parents=True)
            target = root / "real-review"
            target.mkdir()
            os.chmod(target, 0o700)
            write_bytes_exclusive(
                target / CHECKER.CLAIM_NAME,
                CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM),
            )
            os.symlink(target, parent / CHECKER.CLAIM_DIRECTORY_PARTS[-1])
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.SafeClaimObservationReader(root).inspect()

        with tempfile.TemporaryDirectory(
            prefix="aetherlink-g2-r3-ancestor-link-"
        ) as temporary:
            root = Path(temporary).resolve()
            target = root / "real-build"
            review = target.joinpath(*CHECKER.CLAIM_DIRECTORY_PARTS[1:])
            review.mkdir(parents=True)
            os.chmod(review, 0o700)
            write_bytes_exclusive(
                review / CHECKER.CLAIM_NAME,
                CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM),
            )
            os.symlink(target, root / CHECKER.CLAIM_DIRECTORY_PARTS[0])
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.SafeClaimObservationReader(root).inspect()


class EvidenceSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.failure = load_json(CHECKER.FAILURE_PATH)
        cls.progress = load_json(CHECKER.PROGRESS_PATH)
        cls.supersession = load_json(CHECKER.SUPERSESSION_PATH)
        cls.manifest = load_json(CHECKER.MANIFEST_PATH)

    def test_documents_validate_and_observation_classes_are_separate(self):
        CHECKER.validate_failure(self.failure)
        CHECKER.validate_progress(self.progress)
        CHECKER.validate_supersession(self.supersession)
        self.assertEqual(
            self.failure["interactiveRunnerObservation"]["evidenceClass"],
            "current_session_process_result_not_independent_runtime_receipt",
        )
        self.assertEqual(
            self.failure["independentlyRecheckedState"]["evidenceClass"],
            "claim_identity_and_exact_report_name_absence_only",
        )
        self.assertFalse(
            self.failure["independentlyRecheckedState"][
                "archiveReadPassCountIndependentlyProven"
            ]
        )

    def test_failure_runtime_observation_mutations_are_rejected(self):
        mutations = (
            ("code", "other"),
            ("observedArchiveEntryPath", "other"),
            ("evidenceClass", "independent"),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                document = copy.deepcopy(self.failure)
                document["interactiveRunnerObservation"][key] = value
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.validate_failure(document)
        for key in self.failure["interactiveRunnerObservation"]["operationCounters"]:
            with self.subTest(counter=key):
                document = copy.deepcopy(self.failure)
                document["interactiveRunnerObservation"]["operationCounters"][key] += 1
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.validate_failure(document)

    def test_failure_nonclaims_cannot_be_promoted(self):
        for key, value in self.failure["executionBoundary"].items():
            if type(value) is bool:
                with self.subTest(key=key):
                    document = copy.deepcopy(self.failure)
                    document["executionBoundary"][key] = not value
                    with self.assertRaises(CHECKER.CheckError):
                        CHECKER.validate_failure(document)

    def test_progress_and_supersession_mutations_are_rejected(self):
        progress = copy.deepcopy(self.progress)
        progress["interactiveRunnerObservationSummary"]["completed"] = True
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_progress(progress)
        progress = copy.deepcopy(self.progress)
        progress["remainingVerification"][0]["status"] = "passed"
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_progress(progress)
        supersession = copy.deepcopy(self.supersession)
        supersession["currentState"]["automaticRetryAllowed"] = True
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_supersession(supersession)
        supersession = copy.deepcopy(self.supersession)
        supersession["semanticGuard"]["failureReinterpretedAsSuccess"] = True
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_supersession(supersession)

    def test_content_binding_rejects_semantic_mutation(self):
        for document, validator in (
            (self.failure, CHECKER.validate_failure),
            (self.progress, CHECKER.validate_progress),
            (self.supersession, CHECKER.validate_supersession),
        ):
            with self.subTest(document=document["documentType"]):
                mutated = copy.deepcopy(document)
                mutated["recordedDate"] = "2026-07-24"
                with self.assertRaises(CHECKER.CheckError):
                    validator(mutated)

    def test_manifest_and_collection_validate(self):
        reader = CHECKER.SafeTrackedReader(ROOT)
        CHECKER.validate_manifest(self.manifest, reader)
        self.assertEqual(
            self.manifest["collectionSha256"],
            CHECKER.collection_sha256(self.manifest["artifacts"]),
        )

    def test_manifest_identity_order_hash_role_collection_and_predecessor_drift_fail(self):
        mutations = []
        document = copy.deepcopy(self.manifest)
        document["artifacts"][0], document["artifacts"][1] = (
            document["artifacts"][1],
            document["artifacts"][0],
        )
        mutations.append(document)
        for key, value in (
            ("evidenceId", "G2R3E999"),
            ("path", CHECKER.PROGRESS_PATH),
            ("role", "other"),
            ("sha256", "0" * 64),
        ):
            document = copy.deepcopy(self.manifest)
            document["artifacts"][0][key] = value
            mutations.append(document)
        document = copy.deepcopy(self.manifest)
        document["collectionSha256"] = "0" * 64
        mutations.append(document)
        document = copy.deepcopy(self.manifest)
        document["predecessorManifestBinding"]["collectionSha256"] = "0" * 64
        mutations.append(document)
        for index, document in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.validate_manifest(
                        document, CHECKER.SafeTrackedReader(ROOT)
                    )

    def test_json_artifacts_have_no_placeholders_and_checker_pin_is_resolved(self):
        paths = (
            CHECKER.FAILURE_PATH,
            CHECKER.PROGRESS_PATH,
            CHECKER.SUPERSESSION_PATH,
            CHECKER.MANIFEST_PATH,
        )
        for path in paths:
            with self.subTest(path=path):
                raw = read_exact_source(ROOT / path)
                self.assertNotIn(b"__PENDING_", raw)
        self.assertRegex(CHECKER.EXPECTED_CHECKER_TEST_RAW_SHA256, r"^[0-9a-f]{64}$")


class CapabilityBoundaryTests(unittest.TestCase):
    def test_checker_imports_no_process_network_git_or_device_modules(self):
        tree = ast.parse(CHECKER_SOURCE, filename=os.fspath(CHECKER_PATH))
        forbidden = {
            "subprocess",
            "socket",
            "urllib",
            "http",
            "requests",
            "git",
            "adb",
        }
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.isdisjoint(forbidden), imports & forbidden)

    def test_checker_has_no_enumeration_or_write_apis(self):
        source = CHECKER_SOURCE.decode("utf-8")
        forbidden_tokens = (
            "os.listdir",
            "os.scandir",
            "os.walk",
            ".glob(",
            ".rglob(",
            "subprocess.",
            "socket.",
            "urlopen",
            "requests.",
            "os.remove",
            "os.unlink",
            "os.rename",
            "os.replace",
            "shutil.",
        )
        for token in forbidden_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, source)
        self.assertNotIn("source-cache", source)
        self.assertNotIn("archivePath", source)

    def test_generic_tracked_reader_cannot_read_build(self):
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_relative_tracked_path(CHECKER.CLAIM_PATH)
        self.assertTrue(all(not path.startswith("build/") for path in CHECKER.TRACKED_READ_ALLOWLIST))

    def test_absence_scope_is_exactly_four_names(self):
        self.assertEqual(
            CHECKER.ABSENCE_NAMES,
            (
                "offline-source-review-result-v1.json",
                "offline-source-review-manifest-v1.json",
                ".offline-source-review-result-v1.json.tmp",
                ".offline-source-review-manifest-v1.json.tmp",
            ),
        )


class RepositoryIntegrationTests(unittest.TestCase):
    def test_repository_validation_passes_with_claim_only_runtime_recheck(self):
        result = CHECKER.validate_repository(ROOT)
        self.assertEqual(result["status"], CHECKER.EXPECTED_STATUS)
        self.assertEqual(result["result"], CHECKER.EXPECTED_RESULT)
        self.assertEqual(result["checkedAbsenceNames"], list(CHECKER.ABSENCE_NAMES))

    def test_main_reports_narrow_non_independent_boundary(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            return_code = CHECKER.main([])
        self.assertEqual(return_code, 0, stderr.getvalue())
        output = json.loads(stdout.getvalue())
        self.assertTrue(output["claimReadByChecker"])
        self.assertFalse(output["archiveOpenByChecker"])
        self.assertFalse(output["archiveReadByChecker"])
        self.assertFalse(output["archiveStatByChecker"])
        self.assertFalse(output["buildDirectoryEnumerated"])
        self.assertFalse(output["interactiveRunnerObservationIndependentlyReproduced"])
        self.assertFalse(output["completed"])
        self.assertFalse(output["repositoryOwnerAuthenticationRequired"])
        self.assertFalse(output["externalIdentityProofRequired"])
        self.assertFalse(output["userActionRequired"])


if __name__ == "__main__":
    unittest.main()
