#!/usr/bin/env python3
"""No-archive, no-build tests for the G2 rung-three v3 permit checker."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_RELATIVE_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_permit_v3.py"
CHECKER_PATH = ROOT / CHECKER_RELATIVE_PATH
CHECKER_BYTES = CHECKER_PATH.read_bytes()
CHECKER = types.ModuleType("g2_rung3_v3_execution_permit_checker_under_test")
CHECKER.__dict__.update(
    {
        "__cached__": None,
        "__file__": str(CHECKER_PATH),
        "__loader__": None,
        "__package__": None,
    }
)
exec(
    compile(
        CHECKER_BYTES,
        CHECKER_RELATIVE_PATH,
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    ),
    CHECKER.__dict__,
    CHECKER.__dict__,
)


class V3ExecutionPermitCheckerTests(unittest.TestCase):
    def read_json(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_01_exact_runner_api_and_return_contract(self) -> None:
        validate_signature = inspect.signature(CHECKER.validate_repository)
        loader_signature = inspect.signature(CHECKER.load_validated_review_modules)
        self.assertEqual(tuple(validate_signature.parameters), ("root",))
        self.assertEqual(tuple(loader_signature.parameters), ("root",))
        self.assertEqual(validate_signature.parameters["root"].default, CHECKER.ROOT)
        self.assertEqual(loader_signature.parameters["root"].default, CHECKER.ROOT)
        result = CHECKER.validate_repository(ROOT)
        self.assertEqual(
            set(result),
            {
                "permit",
                "permitRawSha256",
                "permitSemanticSha256",
                "archiveOpenCount",
                "archiveReadPassCount",
                "buildPathReadCount",
                "outputPathReadCount",
                "fileWriteCount",
                "permitConsumptionState",
                "authorityReadPaths",
            },
        )

    def test_02_strict_json_rejects_duplicate_cr_missing_lf_and_nonfinite(self) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":NaN}\n',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.strict_json(raw, "fixture")

    def test_03_authority_allowlist_is_closed_and_observationally_disjoint(self) -> None:
        self.assertTrue(
            CHECKER.AUTHORITY_READ_ALLOWLIST.isdisjoint(
                CHECKER.OBSERVATIONAL_READ_ALLOWLIST
            )
        )
        self.assertNotIn(CHECKER.CHECKER_MANIFEST_PATH, CHECKER.AUTHORITY_READ_ALLOWLIST)
        self.assertNotIn(CHECKER.RUNNER_PATH, CHECKER.AUTHORITY_READ_ALLOWLIST)
        self.assertNotIn(CHECKER.CHECKER_PATH, CHECKER.AUTHORITY_READ_ALLOWLIST)
        for path in CHECKER.AUTHORITY_READ_ALLOWLIST:
            self.assertFalse(path.startswith("build/"))
            self.assertFalse(
                path.lower().endswith(
                    (".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z")
                )
            )
        for unsafe in (
            "build/offline-source/pion.zip",
            "../escape",
            "/absolute",
            "docs\\escape",
            CHECKER.RUNNER_PATH,
            CHECKER.CHECKER_PATH,
        ):
            with self.subTest(path=unsafe):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.validate_relative_path(unsafe)

    def test_04_preflight_opens_no_write_build_archive_or_output_path(self) -> None:
        original_open = CHECKER.os.open
        observed: list[tuple[object, int]] = []

        def guarded_open(path, flags, *args, **kwargs):
            observed.append((path, flags))
            self.assertEqual(
                flags
                & (
                    os.O_WRONLY
                    | os.O_RDWR
                    | os.O_CREAT
                    | os.O_TRUNC
                    | os.O_APPEND
                ),
                0,
            )
            rendered = os.fspath(path)
            self.assertNotIn("build/offline-source", rendered)
            self.assertFalse(
                rendered.lower().endswith(
                    (".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z")
                )
            )
            self.assertNotIn("offline-source-review-result-v3.json", rendered)
            self.assertNotIn("offline-source-review-manifest-v3.json", rendered)
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(CHECKER.os, "open", side_effect=guarded_open):
            result = CHECKER.validate_repository(ROOT)
        self.assertTrue(observed)
        self.assertEqual(result["archiveOpenCount"], 0)
        self.assertEqual(result["archiveReadPassCount"], 0)
        self.assertEqual(result["buildPathReadCount"], 0)
        self.assertEqual(result["outputPathReadCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertEqual(result["permitConsumptionState"], "not_inspected")

    def test_05_exact_policy_permit_core_and_tool_hashes(self) -> None:
        result = CHECKER.validate_repository(ROOT)
        self.assertEqual(result["permitRawSha256"], CHECKER.EXPECTED_PERMIT_RAW)
        self.assertEqual(
            result["permitSemanticSha256"], CHECKER.EXPECTED_PERMIT_SEMANTIC
        )
        for path, digest in (
            (CHECKER.POLICY_PATH, CHECKER.EXPECTED_POLICY_RAW),
            (CHECKER.CORE_MANIFEST_PATH, CHECKER.EXPECTED_CORE_RAW),
            (CHECKER.FAILURE_MANIFEST_PATH, CHECKER.EXPECTED_FAILURE_MANIFEST_RAW),
            (CHECKER.BASE_VALIDATOR_PATH, CHECKER.EXPECTED_BASE_RAW),
            (CHECKER.OVERLAY_PATH, CHECKER.EXPECTED_OVERLAY_RAW),
            (CHECKER.AGGREGATOR_PATH, CHECKER.EXPECTED_AGGREGATOR_RAW),
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                digest,
            )

    def test_06_content_binding_and_collection_digests_are_recomputed(self) -> None:
        permit = self.read_json(CHECKER.PERMIT_PATH)
        content = permit.pop("contentBinding")
        self.assertEqual(
            hashlib.sha256(CHECKER.canonical_json_bytes(permit)).hexdigest(),
            content["sha256"],
        )
        core = self.read_json(CHECKER.CORE_MANIFEST_PATH)
        failure = self.read_json(CHECKER.FAILURE_MANIFEST_PATH)
        self.assertEqual(
            CHECKER.collection_sha256(core["artifacts"]),
            core["collectionSha256"],
        )
        self.assertEqual(
            CHECKER.collection_sha256(failure["artifacts"]),
            failure["collectionSha256"],
        )

    def test_07_v1_v2_cannot_be_retried_and_v3_names_are_separate(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        permit = self.read_json(CHECKER.PERMIT_PATH)
        predecessor = permit["predecessorFailureBoundary"]
        self.assertFalse(predecessor["permitV1RetryAllowed"])
        self.assertFalse(predecessor["permitV2RetryAllowed"])
        self.assertTrue(predecessor["permitV1ClaimRetained"])
        self.assertTrue(predecessor["permitV2ClaimRetained"])
        self.assertFalse(predecessor["predecessorMutationAllowed"])
        self.assertEqual(
            predecessor["v2ClaimRawSha256RecordedOnlyNotReadByPreflight"],
            CHECKER.EXPECTED_V2_CLAIM_RAW_RECORDED_ONLY,
        )
        output = policy["outputContract"]
        self.assertIn("review-v3", output["directory"])
        self.assertTrue(output["claimFileName"].endswith("-v3.claim"))
        self.assertTrue(output["resultFileName"].endswith("-v3.json"))
        self.assertTrue(output["manifestFileName"].endswith("-v3.json"))

    def test_08_failure_claim_digest_is_tracked_evidence_only(self) -> None:
        failure = self.read_json(CHECKER.FAILURE_PATH)
        self.assertEqual(
            failure["claimEvidence"]["rawSha256"],
            CHECKER.EXPECTED_V2_CLAIM_RAW_RECORDED_ONLY,
        )
        result = CHECKER.validate_repository(ROOT)
        self.assertFalse(
            any(path.startswith("build/") for path in result["authorityReadPaths"])
        )
        self.assertNotIn(failure["claimEvidence"]["path"], result["authorityReadPaths"])

    def test_09_private_adapter_exposes_only_two_review_calls(self) -> None:
        adapter = CHECKER.load_validated_review_modules(ROOT)
        public = {name for name in vars(adapter) if not name.startswith("__")}
        self.assertEqual(
            public,
            {"inspect_module_zip", "aggregate_candidate_inventory"},
        )
        self.assertTrue(callable(adapter.inspect_module_zip))
        self.assertTrue(callable(adapter.aggregate_candidate_inventory))
        result = adapter.aggregate_candidate_inventory((("fixture.go", b"Dial\n"),))
        self.assertEqual(result["totals"]["hitCount"], 1)
        self.assertEqual(result["representativeLimitPerRule"], 8)

    def test_10_private_aggregator_preserves_complete_totals_digest_and_cap(self) -> None:
        adapter = CHECKER.load_validated_review_modules(ROOT)
        raw = b"".join(f"Dial // {index}\n".encode() for index in range(513))
        result = adapter.aggregate_candidate_inventory((("large.go", raw),))
        first = result["patchUnits"][0]
        rule = first["rules"][0]
        self.assertEqual(rule["totalHitCount"], 513)
        self.assertEqual(rule["recordedRepresentativeCount"], 8)
        self.assertEqual(rule["omittedHitCount"], 505)
        self.assertTrue(rule["truncated"])
        self.assertRegex(first["completeObservationSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(rule["representatives"]), 8)

    def test_11_private_loader_rejects_unlisted_aggregator_import(self) -> None:
        source = (ROOT / CHECKER.AGGREGATOR_PATH).read_bytes()
        poisoned = source.replace(
            b"import hashlib\n",
            b"import hashlib\nimport os\n",
            1,
        )
        with self.assertRaises(CHECKER.CheckError):
            CHECKER._private_module(
                name="poisoned",
                path=CHECKER.AGGREGATOR_PATH,
                source=poisoned,
                import_allowlist=CHECKER.AGGREGATOR_IMPORT_ALLOWLIST,
                builtin_allowlist=CHECKER.AGGREGATOR_BUILTIN_ALLOWLIST,
            )

    def test_12_source_capability_scan_forbids_io_process_and_dynamic_loading(self) -> None:
        checker_tree = ast.parse(CHECKER_BYTES.decode("utf-8"))
        imported = set()
        for node in ast.walk(checker_tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported.isdisjoint(
                {
                    "ctypes",
                    "http",
                    "importlib",
                    "mmap",
                    "requests",
                    "shutil",
                    "socket",
                    "subprocess",
                    "tempfile",
                    "urllib",
                    "zipfile",
                }
            )
        )

    def test_13_exact_isolated_no_site_no_pyc_interpreter(self) -> None:
        self.assertEqual(sys.flags.isolated, 1)
        self.assertEqual(sys.flags.ignore_environment, 1)
        self.assertEqual(sys.flags.no_user_site, 1)
        self.assertEqual(sys.flags.no_site, 1)
        self.assertEqual(sys.flags.dont_write_bytecode, 1)
        self.assertNotIn("site", sys.modules)
        for path in sys.path:
            self.assertNotIn("site-packages", path)

    def test_14_policy_personal_project_boundary_requires_no_user_auth_action(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        permit = self.read_json(CHECKER.PERMIT_PATH)
        core = self.read_json(CHECKER.CORE_MANIFEST_PATH)
        for boundary in (
            policy["personalProjectBoundary"],
            permit["personalProjectBoundary"],
            core["executionBoundary"],
        ):
            self.assertFalse(boundary["repositoryOwnerAuthenticationRequired"])
            self.assertFalse(boundary["externalIdentityProofRequired"])
            self.assertFalse(boundary["executionPermitAuthenticationRequired"])
            self.assertFalse(boundary["userActionRequired"])
        self.assertTrue(
            policy["personalProjectBoundary"]["productEndpointAuthenticationRequired"]
        )

    def test_15_mutated_authority_document_fails_closed(self) -> None:
        reader = CHECKER.SafeTrackedReader(ROOT)
        original = reader.read(CHECKER.PERMIT_PATH)
        mutated = original.replace(
            b'"automaticRetryAllowed": false',
            b'"automaticRetryAllowed": true ',
            1,
        )
        self.assertEqual(len(original), len(mutated))
        parsed = CHECKER.strict_json(mutated, "mutated permit")
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_permit(parsed, mutated, reader)


if __name__ == "__main__":
    unittest.main()
