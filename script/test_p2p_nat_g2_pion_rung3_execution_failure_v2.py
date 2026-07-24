#!/usr/bin/env python3
"""Tests for immutable G2 Pion rung-three permit-v2 failure evidence."""

from __future__ import annotations

import ast
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung3_execution_failure_v2.py"


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
                raise RuntimeError("unexpected EOF")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise RuntimeError("file grew while reading")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


CHECKER_SOURCE = read_exact_source(CHECKER_PATH)
CHECKER = types.ModuleType("g2_rung3_execution_failure_v2_checker_under_test")
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
    with tempfile.TemporaryDirectory(
        prefix="aetherlink-g2-r3-failure-v2-"
    ) as temporary:
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
    return CHECKER.strict_json(read_exact_source(ROOT / path), path)


class StrictJsonTests(unittest.TestCase):
    def test_claim_is_canonical_and_exactly_bound(self):
        raw = CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM)
        self.assertEqual(len(raw), CHECKER.EXPECTED_CLAIM_BYTES)
        self.assertEqual(CHECKER.sha256_bytes(raw), CHECKER.EXPECTED_CLAIM_RAW_SHA256)
        self.assertEqual(CHECKER.strict_json(raw, "claim"), CHECKER.EXPECTED_CLAIM)

    def test_duplicate_nonfinite_crlf_and_missing_lf_fail(self):
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":NaN}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":"\xff"}\n',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.strict_json(raw, "invalid")

    def test_placeholder_detection_is_recursive(self):
        self.assertEqual(
            CHECKER.unresolved_placeholders(
                {"a": [{"b": "__PENDING_VALUE__"}]}, "root"
            ),
            ["root.a[0].b"],
        )


class SyntheticRuntimeTests(unittest.TestCase):
    def test_valid_claim_and_exact_four_absences_pass(self):
        with synthetic_runtime_root() as (root, _):
            observed = CHECKER.SafeClaimObservationReader(root).inspect()
        self.assertEqual(observed["claimPath"], CHECKER.CLAIM_PATH)
        self.assertEqual(observed["checkedAbsenceNames"], list(CHECKER.ABSENCE_NAMES))

    def test_each_fixed_name_rejects_file_directory_and_links(self):
        for name in CHECKER.ABSENCE_NAMES:
            for variant in ("file", "directory", "symlink", "dangling"):
                with self.subTest(name=name, variant=variant):
                    with synthetic_runtime_root() as (root, review):
                        target = review / name
                        if variant == "file":
                            write_bytes_exclusive(target, b"x\n")
                        elif variant == "directory":
                            target.mkdir()
                        elif variant == "symlink":
                            source = review / f"{name}.source"
                            write_bytes_exclusive(source, b"x\n")
                            os.symlink(source.name, target)
                        else:
                            os.symlink("missing-target", target)
                        with self.assertRaises(CHECKER.CheckError):
                            CHECKER.SafeClaimObservationReader(root).inspect()

    def test_missing_mutated_and_noncanonical_claims_fail(self):
        canonical = CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM)
        variants = {
            "missing": None,
            "mutated": b"[" + canonical[1:],
            "extra-key": canonical[:-2] + b',"x":0}\n',
            "duplicate-key": canonical[:-2] + b',"schemaVersion":"2.0"}\n',
            "crlf": canonical[:-1] + b"\r\n",
            "missing-lf": canonical[:-1],
        }
        for label, replacement in variants.items():
            with self.subTest(label=label):
                with synthetic_runtime_root() as (root, review):
                    claim = review / CHECKER.CLAIM_NAME
                    claim.unlink()
                    if replacement is not None:
                        write_bytes_exclusive(claim, replacement)
                    with self.assertRaises(CHECKER.CheckError):
                        CHECKER.SafeClaimObservationReader(root).inspect()

    def test_wrong_claim_mode_hardlink_and_symlink_fail(self):
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

    def test_wrong_review_mode_and_symlinked_directories_fail(self):
        with synthetic_runtime_root() as (root, review):
            os.chmod(review, 0o750)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.SafeClaimObservationReader(root).inspect()

        with tempfile.TemporaryDirectory(
            prefix="aetherlink-g2-r3-failure-v2-link-"
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

    def test_unlisted_absence_name_is_rejected(self):
        with synthetic_runtime_root() as (root, review):
            descriptor = os.open(
                os.fspath(review),
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.SafeClaimObservationReader._require_absent(
                        descriptor, "other"
                    )
            finally:
                os.close(descriptor)


class EvidenceSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.failure = load_json(CHECKER.FAILURE_PATH)
        cls.progress = load_json(CHECKER.PROGRESS_PATH)
        cls.supersession = load_json(CHECKER.SUPERSESSION_PATH)
        cls.manifest = load_json(CHECKER.MANIFEST_PATH)

    def test_documents_validate_and_observation_classes_are_distinct(self):
        CHECKER.validate_failure(self.failure)
        CHECKER.validate_progress(self.progress)
        CHECKER.validate_supersession(self.supersession)
        CHECKER.validate_manifest(self.manifest, CHECKER.SafeTrackedReader(ROOT))
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
                "runnerFailureReasonIndependentlyReproduced"
            ]
        )

    def test_failure_observation_and_independent_nonclaim_mutations_fail(self):
        for path, value in (
            (("interactiveRunnerObservation", "reason"), "different"),
            (("interactiveRunnerObservation", "processExitCode"), 0),
            (
                ("independentlyRecheckedState", "runnerFailureReasonIndependentlyReproduced"),
                True,
            ),
            (
                ("independentlyRecheckedState", "archiveReadPassCountIndependentlyProven"),
                True,
            ),
        ):
            with self.subTest(path=path):
                document = copy.deepcopy(self.failure)
                document[path[0]][path[1]] = value
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.validate_failure(document)

    def test_failure_execution_boundary_cannot_be_promoted(self):
        for key, value in self.failure["executionBoundary"].items():
            if type(value) is bool:
                with self.subTest(key=key):
                    document = copy.deepcopy(self.failure)
                    document["executionBoundary"][key] = not value
                    with self.assertRaises(CHECKER.CheckError):
                        CHECKER.validate_failure(document)

    def test_progress_and_supersession_mutations_fail(self):
        progress = copy.deepcopy(self.progress)
        progress["remainingVerification"][0]["status"] = "passed"
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_progress(progress)
        progress = copy.deepcopy(self.progress)
        progress["independentlyRecheckedState"][
            "failureReasonAndHitBoundIndependentlyReproduced"
        ] = True
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

    def test_content_bindings_reject_semantic_mutation(self):
        for document, validator in (
            (self.failure, CHECKER.validate_failure),
            (self.progress, CHECKER.validate_progress),
            (self.supersession, CHECKER.validate_supersession),
        ):
            with self.subTest(kind=document["documentType"]):
                changed = copy.deepcopy(document)
                changed["recordedDate"] = "2026-07-24"
                with self.assertRaises(CHECKER.CheckError):
                    validator(changed)

    def test_manifest_identity_hash_role_order_and_collection_mutations_fail(self):
        mutations = []
        changed = copy.deepcopy(self.manifest)
        changed["artifacts"][0], changed["artifacts"][1] = (
            changed["artifacts"][1],
            changed["artifacts"][0],
        )
        mutations.append(changed)
        for key, value in (
            ("evidenceId", "G2R3E999"),
            ("path", CHECKER.PROGRESS_PATH),
            ("role", "other"),
            ("sha256", "0" * 64),
        ):
            changed = copy.deepcopy(self.manifest)
            changed["artifacts"][0][key] = value
            mutations.append(changed)
        changed = copy.deepcopy(self.manifest)
        changed["collectionSha256"] = "0" * 64
        mutations.append(changed)
        changed = copy.deepcopy(self.manifest)
        changed["observationBoundary"]["failureReasonIndependentlyReproduced"] = True
        mutations.append(changed)
        for index, changed in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.validate_manifest(
                        changed, CHECKER.SafeTrackedReader(ROOT)
                    )

    def test_current_documents_have_no_placeholders(self):
        for path in (
            CHECKER.FAILURE_PATH,
            CHECKER.PROGRESS_PATH,
            CHECKER.SUPERSESSION_PATH,
            CHECKER.MANIFEST_PATH,
        ):
            with self.subTest(path=path):
                self.assertNotIn(b"__PENDING_", read_exact_source(ROOT / path))


class CapabilityBoundaryTests(unittest.TestCase):
    def test_checker_imports_no_process_network_git_or_device_modules(self):
        tree = ast.parse(CHECKER_SOURCE, filename=os.fspath(CHECKER_PATH))
        forbidden = {"subprocess", "socket", "urllib", "http", "requests", "git", "adb"}
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.isdisjoint(forbidden), imports & forbidden)

    def test_checker_has_no_enumeration_write_or_archive_tokens(self):
        source = CHECKER_SOURCE.decode("utf-8")
        for token in (
            "os.listdir",
            "os.scandir",
            "os.walk",
            ".glob(",
            ".rglob(",
            "os.remove",
            "os.unlink",
            "os.rename",
            "os.replace",
            "os.mkdir",
            "os.makedirs",
            "subprocess.",
            "socket.",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, source)
        self.assertNotIn("source-acquisition-receipt", source)
        self.assertNotIn(".zip", source.lower())

    def test_tracked_allowlist_excludes_build_and_archive_paths(self):
        self.assertTrue(all(not path.startswith("build/") for path in CHECKER.TRACKED_READ_ALLOWLIST))
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_relative_tracked_path("build/anything")
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_relative_tracked_path("other")

    def test_exact_runtime_name_set_is_closed(self):
        self.assertEqual(len(CHECKER.ABSENCE_NAMES), 4)
        self.assertEqual(len(set(CHECKER.ABSENCE_NAMES)), 4)
        self.assertTrue(all("/" not in name and "\\" not in name for name in CHECKER.ABSENCE_NAMES))

    def test_interpreter_is_fully_isolated(self):
        self.assertEqual(sys.flags.isolated, 1)
        self.assertEqual(sys.flags.dont_write_bytecode, 1)
        self.assertEqual(sys.flags.no_site, 1)
        CHECKER.require_isolated_interpreter()

    def test_synthetic_claim_metadata_is_owner_only(self):
        with synthetic_runtime_root() as (_, review):
            claim = review / CHECKER.CLAIM_NAME
            identity = claim.lstat()
            self.assertTrue(stat.S_ISREG(identity.st_mode))
            self.assertEqual(stat.S_IMODE(identity.st_mode), 0o600)
            self.assertEqual(identity.st_nlink, 1)


if __name__ == "__main__":
    unittest.main()
