#!/usr/bin/env python3
"""Regression tests for the bounded rung-three semantic review v1 runner."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).with_name(
    "run_p2p_nat_g2_pion_rung3_semantic_review_v1.py"
)
SPEC = importlib.util.spec_from_file_location("semantic_review_v1_runner", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load semantic review runner test target")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class BufferStream:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()


class SemanticReviewV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner_raw, _ = RUNNER.read_stable_relative_file(
            RUNNER.ROOT,
            RUNNER.RUNNER_PATH,
            maximum_bytes=RUNNER.MAXIMUM_JSON_BYTES,
        )
        decision_raw, _ = RUNNER.read_stable_relative_file(
            RUNNER.ROOT,
            RUNNER.DECISION_PATH,
            maximum_bytes=RUNNER.MAXIMUM_JSON_BYTES,
            expected_sha256=RUNNER.EXPECTED_DECISION_RAW_SHA256,
        )
        input_raw, _ = RUNNER.read_stable_relative_file(
            RUNNER.ROOT,
            RUNNER.PASS_INPUT_PATH,
            maximum_bytes=RUNNER.MAXIMUM_JSON_BYTES,
            expected_sha256=RUNNER.EXPECTED_INPUT_RAW_SHA256,
        )
        pass_record_raw = {}
        for pass_id in RUNNER.PASS_IDS:
            raw, _ = RUNNER.read_stable_relative_file(
                RUNNER.ROOT,
                RUNNER.PASS_RECORD_PATHS[pass_id],
                maximum_bytes=RUNNER.MAXIMUM_JSON_BYTES,
                expected_sha256=RUNNER.EXPECTED_PASS_RECORD_RAW_SHA256[pass_id],
            )
            pass_record_raw[pass_id] = raw
        archive_raw, cls.archive_metadata = RUNNER.read_stable_relative_file(
            RUNNER.ROOT,
            RUNNER.ARCHIVE_PATH,
            maximum_bytes=RUNNER.MAXIMUM_ARCHIVE_BYTES,
            expected_bytes=RUNNER.EXPECTED_ARCHIVE_BYTES,
            expected_sha256=RUNNER.EXPECTED_ARCHIVE_SHA256,
            required_mode=0o600,
        )
        cls.decision = RUNNER.strict_json(decision_raw, "test decision")
        cls.pass_input = RUNNER.strict_json(input_raw, "test pass input")
        cls.pass_records = {
            pass_id: RUNNER.strict_json(raw, f"test {pass_id} pass record")
            for pass_id, raw in pass_record_raw.items()
        }
        entries, cls.archive_inventory = RUNNER.inspect_retained_archive(archive_raw)
        cls.go_sources, cls.snapshot = RUNNER.build_go_snapshot(entries)
        cls.observations = RUNNER.aggregate_observations(cls.go_sources)
        cls.findings, cls.crosswalks = RUNNER.validate_pass_input(
            cls.pass_input,
            pass_records=cls.pass_records,
            decision=cls.decision,
            snapshot=cls.snapshot,
            observations=cls.observations,
        )
        cls.documents = RUNNER.build_output_documents(
            runner_binding={
                "path": RUNNER.RUNNER_PATH,
                "rawSha256": hashlib.sha256(cls.runner_raw).hexdigest(),
            },
            pass_record_bindings=[
                RUNNER.public_pass_record_binding(pass_id)
                for pass_id in RUNNER.PASS_IDS
            ],
            decision=cls.decision,
            pass_input=cls.pass_input,
            archive_metadata=cls.archive_metadata,
            archive_inventory=cls.archive_inventory,
            snapshot=cls.snapshot,
            observations=cls.observations,
            findings=cls.findings,
            crosswalks=cls.crosswalks,
        )
        cls.classifications = RUNNER.strict_json(
            cls.documents[RUNNER.CLASSIFICATIONS_NAME], "test classifications"
        )
        cls.result = RUNNER.strict_json(
            cls.documents[RUNNER.RESULT_NAME], "test result"
        )
        cls.manifest = RUNNER.strict_json(
            cls.documents[RUNNER.MANIFEST_NAME], "test manifest"
        )

    def test_input_raw_and_self_hash_are_exact(self) -> None:
        path = RUNNER.ROOT / RUNNER.PASS_INPUT_PATH
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), RUNNER.EXPECTED_INPUT_RAW_SHA256)
        document = json.loads(raw)
        binding = document.pop("contentBinding")
        self.assertEqual(
            hashlib.sha256(RUNNER.canonical_json_bytes(document)).hexdigest(),
            binding["sha256"],
        )
        self.assertEqual(binding["sha256"], RUNNER.EXPECTED_INPUT_CONTENT_SHA256)

    def test_runner_and_non_attesting_pass_records_are_bound_in_all_outputs(self) -> None:
        runner_sha256 = hashlib.sha256(self.runner_raw).hexdigest()
        expected_records = [
            RUNNER.public_pass_record_binding(pass_id)
            for pass_id in RUNNER.PASS_IDS
        ]
        expected_candidates = [
            RUNNER.public_pass_candidate_semantic_binding(pass_id)
            for pass_id in RUNNER.PASS_IDS
        ]
        self.assertEqual(self.pass_input["passRecordBindings"], expected_records)
        for pass_id in RUNNER.PASS_IDS:
            raw = (
                RUNNER.ROOT / RUNNER.PASS_RECORD_PATHS[pass_id]
            ).read_bytes()
            self.assertEqual(
                hashlib.sha256(raw).hexdigest(),
                RUNNER.EXPECTED_PASS_RECORD_RAW_SHA256[pass_id],
            )
            document = json.loads(raw)
            binding = document.pop("contentBinding")
            self.assertEqual(
                hashlib.sha256(RUNNER.canonical_json_bytes(document)).hexdigest(),
                RUNNER.EXPECTED_PASS_RECORD_CONTENT_SHA256[pass_id],
            )
            self.assertEqual(
                binding["sha256"],
                RUNNER.EXPECTED_PASS_RECORD_CONTENT_SHA256[pass_id],
            )
            self.assertEqual(
                document["candidateSemanticBinding"],
                {
                    key: value
                    for key, value in expected_candidates[
                        RUNNER.PASS_IDS.index(pass_id)
                    ].items()
                    if key != "passId"
                },
            )
            self.assertEqual(
                document["integrityLimitations"],
                RUNNER.INTEGRITY_LIMITATIONS,
            )
            self.assertEqual(
                document["locationValidationBoundary"],
                RUNNER.LOCATION_VALIDATION_BOUNDARY,
            )
        for document in (self.classifications, self.result, self.manifest):
            self.assertEqual(
                document["runnerBinding"],
                {"path": RUNNER.RUNNER_PATH, "rawSha256": runner_sha256},
            )
            self.assertEqual(document["passRecordBindings"], expected_records)
            self.assertEqual(
                document["passCandidateSemanticBindings"],
                expected_candidates,
            )
            self.assertFalse(
                document["semanticJudgmentsIndependentlyReproducedByRunner"]
            )
            self.assertTrue(document["passRecordsNonAttesting"])
            self.assertTrue(
                document["coverageAndLocationBoundsValidatedAgainstSnapshot"]
            )
            self.assertEqual(
                document["integrityLimitations"],
                RUNNER.INTEGRITY_LIMITATIONS,
            )
            self.assertEqual(
                document["locationValidationBoundary"],
                RUNNER.LOCATION_VALIDATION_BOUNDARY,
            )
            self.assertEqual(
                document["postRunEvidenceBoundary"],
                RUNNER.POST_RUN_EVIDENCE_BOUNDARY,
            )

    def test_candidate_semantic_digests_are_independently_recomputed(self) -> None:
        expected = {
            "primary": (
                14,
                "66481cfac724c39b2dd8a2a721b1afe939cbb3c95a7752fee62a72d61ddc4038",
            ),
            "independent": (
                15,
                "563eb28ca3aff18aa051584255bccf257ab80dbeb4f5ec1d9319dbad0d605edf",
            ),
        }
        for pass_id, (count, digest) in expected.items():
            rows = [
                row
                for row in self.pass_input["candidateFindings"]
                if row["passId"] == pass_id
            ]
            raw = (
                json.dumps(
                    rows,
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            self.assertEqual(len(rows), count)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            self.assertEqual(
                [row["candidateId"] for row in rows],
                next(
                    declaration["candidateIds"]
                    for declaration in self.pass_input["passDeclarations"]
                    if declaration["passId"] == pass_id
                ),
            )

    def test_input_integrity_location_and_digest_contracts_are_exact(self) -> None:
        self.assertEqual(
            self.pass_input["candidateSemanticDigestContract"],
            RUNNER.CANDIDATE_SEMANTIC_DIGEST_CONTRACT,
        )
        self.assertEqual(
            self.pass_input["integrityLimitations"],
            RUNNER.INTEGRITY_LIMITATIONS,
        )
        self.assertEqual(
            self.pass_input["locationValidationBoundary"],
            RUNNER.LOCATION_VALIDATION_BOUNDARY,
        )
        mutations = (
            (
                "digest contract",
                "candidateSemanticDigestContract",
                "algorithm",
                "sha512",
            ),
            (
                "integrity limitation",
                "integrityLimitations",
                "runnerBindingAttestsLoadedExecutingCode",
                True,
            ),
            (
                "location boundary",
                "locationValidationBoundary",
                "symbolResolutionPerformed",
                True,
            ),
        )
        for label, object_key, field, value in mutations:
            with self.subTest(label=label):
                mutated = json.loads(json.dumps(self.pass_input))
                mutated[object_key][field] = value
                with mock.patch.object(
                    RUNNER,
                    "validate_content_binding",
                    return_value=None,
                ), self.assertRaises(RUNNER.ReviewError):
                    RUNNER.validate_pass_input(
                        mutated,
                        pass_records=self.pass_records,
                        decision=self.decision,
                        snapshot=self.snapshot,
                        observations=self.observations,
                    )

    def test_pass_record_binding_and_semantic_mutations_fail_closed(self) -> None:
        mutated_input = json.loads(json.dumps(self.pass_input))
        mutated_input["passRecordBindings"][0]["rawSha256"] = "0" * 64
        with mock.patch.object(
            RUNNER,
            "validate_content_binding",
            return_value=None,
        ), self.assertRaises(RUNNER.ReviewError):
            RUNNER.validate_pass_input(
                mutated_input,
                pass_records=self.pass_records,
                decision=self.decision,
                snapshot=self.snapshot,
                observations=self.observations,
            )

        declaration_by_pass = {
            row["passId"]: row for row in self.pass_input["passDeclarations"]
        }
        mutations = (
            ("candidateIds", lambda record: record["candidateIds"].pop()),
            (
                "attempts",
                lambda record: record["attempts"][0].__setitem__(
                    "status",
                    "discarded",
                ),
            ),
            (
                "reviewed paths",
                lambda record: record["reviewedGoSourcePathSet"]["paths"].pop(),
            ),
            (
                "unit digest",
                lambda record: record["coverage"]["unitDigests"][0].__setitem__(
                    "totalHitCount",
                    0,
                ),
            ),
            (
                "attestation",
                lambda record: record.__setitem__("recordIsSigned", True),
            ),
            (
                "candidate semantic digest",
                lambda record: record["candidateSemanticBinding"].__setitem__(
                    "sha256",
                    "0" * 64,
                ),
            ),
            (
                "candidate semantic key",
                lambda record: record.pop("candidateSemanticBinding"),
            ),
            (
                "candidate semantic object",
                lambda record: record.__setitem__(
                    "candidateSemanticBinding",
                    "invalid",
                ),
            ),
            (
                "integrity limitation",
                lambda record: record["integrityLimitations"].__setitem__(
                    "sameUidConcurrentMutationPrevented",
                    True,
                ),
            ),
            (
                "location boundary",
                lambda record: record["locationValidationBoundary"].__setitem__(
                    "goParserUsed",
                    True,
                ),
            ),
        )
        primary_rows = [
            row
            for row in self.pass_input["candidateFindings"]
            if row["passId"] == "primary"
        ]
        expected_candidate_binding = RUNNER.candidate_semantic_binding(
            "primary",
            primary_rows,
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                record = json.loads(json.dumps(self.pass_records["primary"]))
                mutate(record)
                with mock.patch.object(
                    RUNNER,
                    "validate_content_binding",
                    return_value=None,
                ), self.assertRaises(RUNNER.ReviewError):
                    RUNNER.validate_pass_record(
                        record,
                        pass_id="primary",
                        expected_candidate_semantic_binding=(
                            expected_candidate_binding
                        ),
                        declaration=declaration_by_pass["primary"],
                        decision=self.decision,
                        snapshot=self.snapshot,
                        observations=self.observations,
                    )

    def test_candidate_rationale_and_same_pass_order_mutations_fail_digest(self) -> None:
        original_validate_binding = RUNNER.validate_content_binding

        def bypass_only_input_binding(
            document: object,
            *,
            expected_scope: str,
            expected_sha256: str,
            label: str,
        ) -> None:
            if label == "semantic pass input":
                return
            original_validate_binding(
                document,
                expected_scope=expected_scope,
                expected_sha256=expected_sha256,
                label=label,
            )

        mutations = []
        rationale = json.loads(json.dumps(self.pass_input))
        rationale["candidateFindings"][0]["rationale"] += " mutation"
        mutations.append(("rationale", rationale))
        reordered = json.loads(json.dumps(self.pass_input))
        primary_indices = [
            index
            for index, row in enumerate(reordered["candidateFindings"])
            if row["passId"] == "primary"
        ]
        left, right = primary_indices[:2]
        reordered["candidateFindings"][left], reordered["candidateFindings"][right] = (
            reordered["candidateFindings"][right],
            reordered["candidateFindings"][left],
        )
        mutations.append(("same-pass-order", reordered))

        for label, document in mutations:
            with self.subTest(label=label), mock.patch.object(
                RUNNER,
                "validate_content_binding",
                side_effect=bypass_only_input_binding,
            ), self.assertRaises(RUNNER.ReviewError):
                RUNNER.validate_pass_input(
                    document,
                    pass_records=self.pass_records,
                    decision=self.decision,
                    snapshot=self.snapshot,
                    observations=self.observations,
                )

    def test_runner_has_no_forbidden_imports_or_execution_calls(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_imports = {
            "asyncio",
            "ctypes",
            "http",
            "importlib",
            "multiprocessing",
            "requests",
            "shlex",
            "socket",
            "subprocess",
            "urllib",
        }
        imported: set[str] = set()
        forbidden_calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {
                    "compile",
                    "eval",
                    "exec",
                    "__import__",
                }:
                    forbidden_calls.append(node.func.id)
                if isinstance(node.func, ast.Attribute):
                    expression = ast.unparse(node.func)
                    if expression in {
                        "os.popen",
                        "os.spawnl",
                        "os.spawnle",
                        "os.spawnlp",
                        "os.spawnlpe",
                        "os.spawnv",
                        "os.spawnve",
                        "os.spawnvp",
                        "os.spawnvpe",
                        "os.system",
                    }:
                        forbidden_calls.append(expression)
        self.assertFalse(imported & forbidden_imports)
        self.assertEqual(forbidden_calls, [])

    def test_cli_requires_exact_explicit_mode(self) -> None:
        output_paths = [
            RUNNER.ROOT / RUNNER.RUNG3 / name
            for name in RUNNER.RESERVED_OUTPUT_NAMES
        ]
        self.assertTrue(all(not path.exists() for path in output_paths))
        self.assertTrue(RUNNER.parse_arguments(["--check"]).check)
        self.assertTrue(RUNNER.parse_arguments(["--publish"]).publish)
        mutation_cases = (
            [],
            ["--check", "--publish"],
            ["--pub"],
            ["--publ"],
            ["--p"],
            ["--c"],
            ["--che"],
            ["--chec"],
        )
        for arguments in mutation_cases:
            with self.subTest(arguments=arguments), mock.patch.object(
                RUNNER.sys, "stderr", io.StringIO()
            ):
                with self.assertRaises(SystemExit) as raised:
                    RUNNER.parse_arguments(arguments)
                self.assertNotEqual(raised.exception.code, 0)
                self.assertTrue(all(not path.exists() for path in output_paths))

    def test_archive_is_opened_exactly_once_per_check_build(self) -> None:
        original_open = RUNNER.os.open
        archive_name = Path(RUNNER.ARCHIVE_PATH).name
        archive_opens = 0

        def counting_open(path: object, *args: object, **kwargs: object) -> int:
            nonlocal archive_opens
            if path == archive_name:
                archive_opens += 1
            return original_open(path, *args, **kwargs)

        with mock.patch.object(RUNNER.os, "open", side_effect=counting_open):
            documents, summary = RUNNER.read_and_build(RUNNER.ROOT)
        self.assertEqual(archive_opens, 1)
        self.assertEqual(summary["archiveOpenCount"], 1)
        self.assertEqual(tuple(documents), (
            RUNNER.CLASSIFICATIONS_NAME,
            RUNNER.RESULT_NAME,
            RUNNER.MANIFEST_NAME,
        ))

    def test_complete_100_file_4701_observation_digest_contract(self) -> None:
        self.assertEqual(self.snapshot["goSourceBodyReadCount"], 100)
        self.assertEqual(self.snapshot["goSourceFileCount"], 100)
        self.assertEqual(self.snapshot["goSourceTotalBytes"], 1_077_591)
        self.assertEqual(self.snapshot["goSourceLogicalLineCount"], 39_064)
        self.assertEqual(self.observations["observationCount"], 4_701)
        actual = [
            (
                row["patchUnit"],
                row["totalHitCount"],
                row["completeObservationSha256"],
            )
            for row in self.observations["patchUnits"]
        ]
        expected = [
            (unit, total, digest)
            for unit, total, digest, _rules in RUNNER.EXPECTED_UNIT_ROWS
        ]
        self.assertEqual(actual, expected)

    def test_source_and_observation_classes_are_exact(self) -> None:
        self.assertEqual(
            self.snapshot["sourceFileClassCounts"],
            {"example": 4, "production": 52, "test": 44},
        )
        self.assertEqual(
            self.observations["sourceClassCounts"],
            {"example": 117, "production": 1546, "test": 3038},
        )
        self.assertEqual(
            RUNNER.CANDIDATE_SOURCE_CLASSES,
            frozenset({"example", "production", "test", "dependency"}),
        )
        candidates_by_id = {
            row["candidateId"]: row
            for row in self.pass_input["candidateFindings"]
        }
        self.assertEqual(
            candidates_by_id["P-SEM-010"]["sourceClasses"],
            ["production", "dependency"],
        )
        self.assertEqual(
            candidates_by_id["I-DEP-001"]["sourceClasses"],
            ["production", "dependency"],
        )

    def test_corrected_production_class_and_resolver_sink_crosswalks(self) -> None:
        by_id = {
            row["candidateId"]: row
            for row in self.pass_input["candidateFindings"]
        }
        self.assertEqual(
            by_id["P-SEM-002-PROMOTION"]["sourceClasses"],
            ["production"],
        )
        expected_sink = {
            "line": 1074,
            "path": "gather.go",
            "symbol": "(*Agent).gatherCandidatesRelay",
        }
        self.assertEqual(by_id["P-SEM-007"]["primarySink"], expected_sink)
        self.assertEqual(by_id["I-RESOLVE-001"]["primarySink"], expected_sink)
        self.assertIn(
            {
                "endLine": 1074,
                "path": "gather.go",
                "startLine": 1074,
                "symbol": "(*Agent).gatherCandidatesRelay",
            },
            by_id["I-RESOLVE-001"]["locations"],
        )

    def test_two_pass_default_and_attempt_records_are_complete(self) -> None:
        declarations = self.pass_input["passDeclarations"]
        self.assertEqual([row["passId"] for row in declarations], ["primary", "independent"])
        self.assertTrue(all(row["defaultDisposition"] == "unresolved" for row in declarations))
        self.assertTrue(all(row["reviewEngine"] == "gpt-5.6-sol" for row in declarations))
        self.assertTrue(all(row["engineIdentityAttested"] is False for row in declarations))
        self.assertEqual(declarations[0]["successfulAttempt"], 1)
        self.assertEqual(declarations[1]["successfulAttempt"], 2)
        self.assertEqual(declarations[1]["attempts"][0]["status"], "discarded")
        self.assertTrue(
            all(
                row["coverage"]["lexicalObservationCount"] == 4_701
                and row["coverage"]["allGoSourceBodiesReviewed"] is True
                and row["coverage"]["allLexicalObservationsClassified"] is True
                for row in declarations
            )
        )

    def test_missing_pass_or_candidate_mutation_fails_closed(self) -> None:
        missing_pass = json.loads(json.dumps(self.pass_input))
        missing_pass["passDeclarations"].pop()
        with self.assertRaises(RUNNER.ReviewError):
            RUNNER.validate_pass_input(
                missing_pass,
                pass_records=self.pass_records,
                decision=self.decision,
                snapshot=self.snapshot,
                observations=self.observations,
            )
        missing_candidate = json.loads(json.dumps(self.pass_input))
        missing_candidate["candidateFindings"].pop()
        with self.assertRaises(RUNNER.ReviewError):
            RUNNER.validate_pass_input(
                missing_candidate,
                pass_records=self.pass_records,
                decision=self.decision,
                snapshot=self.snapshot,
                observations=self.observations,
            )

    def test_disagreement_is_forced_unresolved(self) -> None:
        finding = next(
            row
            for row in self.findings
            if row["dedupGroupId"] == "G-RESOLUTION-GATHER"
        )
        self.assertEqual(finding["finalDisposition"], "unresolved")
        self.assertFalse(finding["dispositionAgreement"])
        reports = {row["passId"]: row["reportedDisposition"] for row in finding["passReports"]}
        self.assertEqual(reports, {"primary": "patch_required", "independent": "unresolved"})

    def test_zero_hit_one_use_is_a_missing_mechanism_gap(self) -> None:
        one_use_rule = next(
            rule
            for unit in self.observations["patchUnits"]
            for rule in unit["rules"]
            if rule["ruleId"] == "one-use"
        )
        self.assertEqual(one_use_rule["totalHitCount"], 0)
        finding = next(
            row for row in self.findings if row["dedupGroupId"] == "G-ONE-USE-GAP"
        )
        self.assertEqual(finding["findingKind"], "missing_required_mechanism")
        self.assertEqual(finding["finalDisposition"], "unresolved")
        self.assertEqual(finding["finalSeverity"], "none")
        self.assertEqual(len(finding["passReports"]), 2)

    def test_exact_dedup_merges_and_required_splits_are_preserved(self) -> None:
        by_group = {row["dedupGroupId"]: row for row in self.findings}
        self.assertEqual(len(by_group["G-EGRESS-WRITETO"]["passReports"]), 2)
        self.assertEqual(len(by_group["G-INGRESS-HANDLEPACKET"]["passReports"]), 2)
        self.assertNotEqual(
            by_group["G-PROMOTION-TRANSPORT"]["findingId"],
            by_group["G-PROMOTION-AGENT"]["findingId"],
        )
        self.assertNotEqual(
            by_group["G-DIAG-REMOTE-PASSWORD"]["findingId"],
            by_group["G-DIAG-RAW-CANDIDATE"]["findingId"],
        )

    def test_dependency_and_selection_overclaims_remain_false(self) -> None:
        closure = self.result["closure"]
        self.assertTrue(self.result["coverage"]["semanticSourceReviewPerformed"])
        self.assertFalse(closure["semanticClosureComplete"])
        self.assertFalse(closure["dependencySourceReviewed"])
        self.assertFalse(closure["dependencyClosureComplete"])
        self.assertFalse(closure["rungThreeComplete"])
        self.assertFalse(closure["candidateSelected"])
        self.assertFalse(closure["librarySelected"])
        self.assertEqual(
            self.result["status"],
            "rung3_semantic_source_review_v1_executed_semantic_closure_blocked",
        )

    def test_output_hygiene_size_and_p0_audit(self) -> None:
        for name, payload in self.documents.items():
            self.assertLessEqual(len(payload), RUNNER.MAXIMUM_JSON_BYTES, name)
            self.assertNotIn(os.fspath(RUNNER.ROOT).encode(), payload)
            self.assertNotIn(b"BEGIN PRIVATE KEY", payload)
            self.assertNotIn(b'"sourceBody"', payload)
            self.assertNotIn(b'"lineSha256"', payload)
            self.assertNotIn(
                b'"coverageAndLocationsValidatedAgainstSnapshot"',
                payload,
            )
        audit = self.result["findingAudit"]
        self.assertEqual(audit["severityCounts"]["P0"], 0)
        self.assertEqual(sum(audit["severityCounts"].values()), 19)
        self.assertEqual(audit["inputCandidateCount"], 29)
        self.assertEqual(audit["deduplicatedFindingCount"], 19)

    def test_check_mode_writes_zero_output_files(self) -> None:
        output_paths = [
            RUNNER.ROOT / RUNNER.RUNG3 / name
            for name in RUNNER.RESERVED_OUTPUT_NAMES
        ]
        self.assertTrue(all(not path.exists() for path in output_paths))
        stdout = BufferStream()
        stderr = BufferStream()
        with mock.patch.object(RUNNER.sys, "stdout", stdout), mock.patch.object(
            RUNNER.sys, "stderr", stderr
        ):
            result = RUNNER.main(["--check"])
        self.assertEqual(result, 0)
        summary = json.loads(stdout.buffer.getvalue())
        self.assertEqual(summary["fileWriteCount"], 0)
        self.assertFalse(summary["publicationAttempted"])
        self.assertEqual(
            summary["passCandidateSemanticBindings"],
            [
                RUNNER.public_pass_candidate_semantic_binding(pass_id)
                for pass_id in RUNNER.PASS_IDS
            ],
        )
        self.assertTrue(
            summary["coverageAndLocationBoundsValidatedAgainstSnapshot"]
        )
        self.assertEqual(
            summary["integrityLimitations"],
            RUNNER.INTEGRITY_LIMITATIONS,
        )
        self.assertEqual(
            summary["locationValidationBoundary"],
            RUNNER.LOCATION_VALIDATION_BOUNDARY,
        )
        self.assertEqual(
            summary["postRunEvidenceBoundary"],
            RUNNER.POST_RUN_EVIDENCE_BOUNDARY,
        )
        self.assertEqual(stderr.buffer.getvalue(), b"")
        self.assertTrue(all(not path.exists() for path in output_paths))

    def test_commit_marker_is_published_after_data_with_transactional_staging(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / RUNNER.RUNG3).mkdir(parents=True)
            order: list[str] = []
            original_publish = RUNNER.publish_one_transactional

            def recording_publish(
                directory_fd: int,
                name: str,
                payload: bytes,
            ) -> tuple[int, int]:
                order.append(name)
                return original_publish(directory_fd, name, payload)

            with mock.patch.object(
                RUNNER,
                "publish_one_transactional",
                side_effect=recording_publish,
            ):
                result = RUNNER.publish_documents(root, self.documents)
            self.assertEqual(
                order,
                [
                    RUNNER.CLASSIFICATIONS_NAME,
                    RUNNER.RESULT_NAME,
                    RUNNER.MANIFEST_NAME,
                ],
            )
            self.assertTrue(result["commitMarkerPublished"])
            self.assertTrue(result["commitMarkerPublishedAfterDataArtifacts"])
            self.assertTrue(result["postCommitFullSetReadbackCompleted"])
            self.assertFalse(result["failureArtifactPublished"])
            self.assertFalse(result["independentPostRunCheckerCompleted"])
            self.assertFalse(result["finalSuccessEvidenceEstablished"])
            for name in order:
                path = root / RUNNER.RUNG3 / name
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.stat().st_nlink, 1)
                self.assertEqual(path.read_bytes(), self.documents[name])
            for name in (RUNNER.FAILURE_NAME, *RUNNER.STAGING_NAMES.values()):
                self.assertFalse((root / RUNNER.RUNG3 / name).exists(), name)
            self.assertEqual(result["stagingCreateCount"], 3)
            self.assertEqual(result["atomicNoReplaceHardLinkPromotionCount"], 3)
            self.assertEqual(result["stagingUnlinkCount"], 3)
            self.assertEqual(result["finalArtifactDeletionCount"], 0)
            transactional = self.manifest["transactionalPublicationBoundary"]
            self.assertFalse(transactional["finalArtifactDeletionAllowed"])
            self.assertTrue(
                transactional["successfulPromotionStagingUnlinkRequired"]
            )

    def test_manifest_is_only_a_commit_marker_with_checker_pending(self) -> None:
        self.assertEqual(
            self.manifest["publicationContract"],
            {
                "manifestRole": "atomic_commit_marker",
                "classificationsAndResultFullSetReadbackCompletedBeforeCommitMarker": True,
                "perArtifactStagingAndFinalReadbackRequired": True,
                "postCommitFullSetReadbackAttemptRequiredBeforeSuccessfulRunnerReturn": True,
                "postCommitFullSetReadbackCompletionPersistedByManifest": False,
                "failureArtifactMayBePublishedAfterCommitMarker": True,
                "commitMarkerPresenceAloneIsFinalSuccessEvidence": False,
                "independentPostRunCheckerRequiredForFinalSuccessEvidence": True,
            },
        )
        self.assertEqual(
            self.manifest["postRunEvidenceBoundary"],
            RUNNER.POST_RUN_EVIDENCE_BOUNDARY,
        )
        counters = self.manifest["preCommitOperationCounters"]
        for forbidden_key in (
            "manifestCreateCount",
            "failureCreateCount",
            "postCommitFullSetReadbackCount",
        ):
            self.assertNotIn(forbidden_key, counters)
        serialized = self.documents[RUNNER.MANIFEST_NAME]
        self.assertNotIn(b'"failureCreateCount"', serialized)
        self.assertNotIn(b'"fullSetReadbackAfterManifestRequired"', serialized)
        self.assertNotIn(
            b'"postCommitFullSetReadbackCompleted"',
            serialized,
        )

    def test_every_reserved_name_blocks_before_any_publication(self) -> None:
        for reserved_name in RUNNER.RESERVED_OUTPUT_NAMES:
            with self.subTest(reserved_name=reserved_name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                output = root / RUNNER.RUNG3
                output.mkdir(parents=True)
                preexisting = output / reserved_name
                preexisting.write_bytes(b"occupied")
                with self.assertRaises(RUNNER.ReviewError):
                    RUNNER.publish_documents(root, self.documents)
                self.assertEqual(preexisting.read_bytes(), b"occupied")
                for other_name in RUNNER.RESERVED_OUTPUT_NAMES:
                    if other_name != reserved_name:
                        self.assertFalse((output / other_name).exists(), other_name)

    def test_partial_staging_write_is_retained_without_truncated_final(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / RUNNER.RUNG3).mkdir(parents=True)
            original_write_all = RUNNER.write_all
            first_write = True

            def interrupted_write(fd: int, payload: bytes) -> None:
                nonlocal first_write
                if first_write:
                    first_write = False
                    os.write(fd, payload[: max(1, len(payload) // 2)])
                    raise RUNNER.PublicationError("simulated staging write interruption")
                original_write_all(fd, payload)

            with mock.patch.object(
                RUNNER,
                "write_all",
                side_effect=interrupted_write,
            ):
                with self.assertRaises(RUNNER.PublicationError):
                    RUNNER.publish_documents(root, self.documents)
            output = root / RUNNER.RUNG3
            staging = output / RUNNER.STAGING_NAMES[RUNNER.CLASSIFICATIONS_NAME]
            self.assertTrue(staging.exists())
            self.assertGreater(staging.stat().st_size, 0)
            self.assertLess(
                staging.stat().st_size,
                len(self.documents[RUNNER.CLASSIFICATIONS_NAME]),
            )
            self.assertFalse((output / RUNNER.CLASSIFICATIONS_NAME).exists())
            self.assertTrue((output / RUNNER.FAILURE_NAME).exists())
            self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
            self.assertFalse(
                (output / RUNNER.STAGING_NAMES[RUNNER.FAILURE_NAME]).exists()
            )
            failure_path = output / RUNNER.FAILURE_NAME
            self.assertEqual(failure_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(failure_path.stat().st_nlink, 1)
            failure = json.loads(failure_path.read_bytes())
            self.assertFalse(failure["automaticRetryAllowed"])
            self.assertFalse(failure["overwriteAllowed"])
            self.assertFalse(failure["finalArtifactDeletionAllowed"])
            self.assertFalse(failure["failedStagingOrFinalCleanupAllowed"])
            self.assertFalse(failure["exceptionTextPublished"])
            self.assertFalse(failure["absolutePathPublished"])
            self.assertEqual(
                failure["runnerBinding"],
                self.classifications["runnerBinding"],
            )
            self.assertEqual(
                failure["passRecordBindings"],
                self.classifications["passRecordBindings"],
            )
            self.assertEqual(
                failure["passCandidateSemanticBindings"],
                self.classifications["passCandidateSemanticBindings"],
            )
            self.assertFalse(
                failure["semanticJudgmentsIndependentlyReproducedByRunner"]
            )
            self.assertTrue(failure["passRecordsNonAttesting"])
            self.assertTrue(
                failure["coverageAndLocationBoundsValidatedAgainstSnapshot"]
            )
            self.assertEqual(
                failure["integrityLimitations"],
                RUNNER.INTEGRITY_LIMITATIONS,
            )
            self.assertEqual(
                failure["locationValidationBoundary"],
                RUNNER.LOCATION_VALIDATION_BOUNDARY,
            )
            self.assertEqual(
                failure["postRunEvidenceBoundary"],
                RUNNER.POST_RUN_EVIDENCE_BOUNDARY,
            )
            self.assertFalse(failure["commitMarkerObservedBeforeFailureRecord"])
            self.assertTrue(failure["failureArtifactMayFollowCommitMarker"])
            self.assertFalse(
                failure["commitMarkerPresenceAloneIsFinalSuccessEvidence"]
            )
            self.assertFalse(
                failure[
                    "postCommitFullSetReadbackCompletionPersistedByCommitMarker"
                ]
            )

    def test_destination_race_never_replaces_existing_final(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / RUNNER.RUNG3
            output.mkdir(parents=True)
            original_link = RUNNER.os.link
            raced = False

            def racing_link(
                source: str,
                destination: str,
                *args: object,
                **kwargs: object,
            ) -> None:
                nonlocal raced
                if destination == RUNNER.CLASSIFICATIONS_NAME and not raced:
                    raced = True
                    directory_fd = kwargs["dst_dir_fd"]
                    fd = os.open(
                        destination,
                        RUNNER.create_file_flags(),
                        mode=0o600,
                        dir_fd=directory_fd,
                    )
                    os.write(fd, b"raced")
                    os.close(fd)
                original_link(source, destination, *args, **kwargs)

            with mock.patch.object(
                RUNNER.os,
                "link",
                side_effect=racing_link,
            ), self.assertRaises(RUNNER.PublicationError):
                RUNNER.publish_documents(root, self.documents)
            self.assertEqual(
                (output / RUNNER.CLASSIFICATIONS_NAME).read_bytes(),
                b"raced",
            )
            self.assertTrue(
                (output / RUNNER.STAGING_NAMES[RUNNER.CLASSIFICATIONS_NAME]).exists()
            )
            self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
            self.assertTrue((output / RUNNER.FAILURE_NAME).exists())

    def test_link_before_unlink_crash_retains_nlink_two_and_blocks_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / RUNNER.RUNG3
            output.mkdir(parents=True)
            original_unlink = RUNNER.os.unlink
            interrupted = False

            def interrupted_unlink(
                path: str,
                *args: object,
                **kwargs: object,
            ) -> None:
                nonlocal interrupted
                if (
                    path == RUNNER.STAGING_NAMES[RUNNER.CLASSIFICATIONS_NAME]
                    and not interrupted
                ):
                    interrupted = True
                    raise OSError("simulated crash before staging unlink")
                original_unlink(path, *args, **kwargs)

            with mock.patch.object(
                RUNNER.os,
                "unlink",
                side_effect=interrupted_unlink,
            ), self.assertRaises(RUNNER.PublicationError):
                RUNNER.publish_documents(root, self.documents)
            final_path = output / RUNNER.CLASSIFICATIONS_NAME
            staging_path = output / RUNNER.STAGING_NAMES[RUNNER.CLASSIFICATIONS_NAME]
            self.assertTrue(final_path.exists())
            self.assertTrue(staging_path.exists())
            self.assertEqual(final_path.stat().st_ino, staging_path.stat().st_ino)
            self.assertEqual(final_path.stat().st_nlink, 2)
            self.assertEqual(staging_path.stat().st_nlink, 2)
            self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
            with self.assertRaises(RUNNER.ReviewError):
                RUNNER.publish_documents(root, self.documents)

    def test_pre_commit_marker_full_set_mutation_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / RUNNER.RUNG3
            output.mkdir(parents=True)
            original_verify_set = RUNNER.verify_payload_set
            mutated = False

            def mutate_before_commit_marker(
                directory_fd: int,
                names: tuple[str, ...],
                documents: dict[str, bytes],
                identities: dict[str, tuple[int, int]],
            ) -> None:
                nonlocal mutated
                if len(names) == 2 and not mutated:
                    mutated = True
                    (output / RUNNER.CLASSIFICATIONS_NAME).write_bytes(b"mutated")
                original_verify_set(directory_fd, names, documents, identities)

            with mock.patch.object(
                RUNNER,
                "verify_payload_set",
                side_effect=mutate_before_commit_marker,
            ), self.assertRaises(RUNNER.ReviewError):
                RUNNER.publish_documents(root, self.documents)
            self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
            self.assertTrue((output / RUNNER.FAILURE_NAME).exists())

    def test_post_commit_marker_full_set_mutation_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / RUNNER.RUNG3
            output.mkdir(parents=True)
            original_verify_set = RUNNER.verify_payload_set
            mutated = False

            def mutate_after_commit_marker(
                directory_fd: int,
                names: tuple[str, ...],
                documents: dict[str, bytes],
                identities: dict[str, tuple[int, int]],
            ) -> None:
                nonlocal mutated
                if len(names) == 3 and not mutated:
                    mutated = True
                    (output / RUNNER.RESULT_NAME).write_bytes(b"mutated")
                original_verify_set(directory_fd, names, documents, identities)

            with mock.patch.object(
                RUNNER,
                "verify_payload_set",
                side_effect=mutate_after_commit_marker,
            ), self.assertRaises(RUNNER.ReviewError):
                RUNNER.publish_documents(root, self.documents)
            self.assertTrue((output / RUNNER.MANIFEST_NAME).exists())
            failure_path = output / RUNNER.FAILURE_NAME
            self.assertTrue(failure_path.exists())
            failure = json.loads(failure_path.read_bytes())
            self.assertTrue(failure["commitMarkerObservedBeforeFailureRecord"])
            self.assertTrue(failure["failureArtifactMayFollowCommitMarker"])
            self.assertFalse(
                failure["commitMarkerPresenceAloneIsFinalSuccessEvidence"]
            )
            self.assertFalse(
                failure[
                    "postCommitFullSetReadbackCompletionPersistedByCommitMarker"
                ]
            )
            self.assertEqual(
                failure["postRunEvidenceBoundary"],
                RUNNER.POST_RUN_EVIDENCE_BOUNDARY,
            )

    def test_symlinked_fixed_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "safe").mkdir()
            target = root / "target"
            target.write_bytes(b"{}\n")
            (root / "safe" / "input.json").symlink_to(target)
            with self.assertRaises(RUNNER.ReviewError):
                RUNNER.read_stable_relative_file(
                    root,
                    "safe/input.json",
                    maximum_bytes=1024,
                )

    def test_fifo_input_is_opened_nonblocking_and_rejected(self) -> None:
        self.assertTrue(RUNNER.file_open_flags() & os.O_NONBLOCK)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "safe").mkdir()
            fifo = root / "safe" / "input.fifo"
            os.mkfifo(fifo, 0o600)
            original_open = RUNNER.os.open

            def guarded_open(
                path: object,
                flags: int,
                *args: object,
                **kwargs: object,
            ) -> int:
                if path == "input.fifo" and not flags & os.O_NONBLOCK:
                    raise AssertionError("FIFO open attempted without O_NONBLOCK")
                return original_open(path, flags, *args, **kwargs)

            with mock.patch.object(
                RUNNER.os,
                "open",
                side_effect=guarded_open,
            ), self.assertRaises(RUNNER.ReviewError):
                RUNNER.read_stable_relative_file(
                    root,
                    "safe/input.fifo",
                    maximum_bytes=1024,
                )

    def _zip_bytes(
        self,
        rows: list[tuple[str, bytes, int, int]],
    ) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w") as archive:
            for path, body, creator, external in rows:
                info = zipfile.ZipInfo(path)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = creator
                info.external_attr = external
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(info, body)
        return output.getvalue()

    def test_zip_traversal_duplicate_utf8_and_symlink_inputs_are_rejected(self) -> None:
        prefix = RUNNER.MODULE_PREFIX
        cases = [
            self._zip_bytes([(prefix + "../escape.go", b"x", 0, 0)]),
            self._zip_bytes(
                [
                    (prefix + "same.go", b"x", 0, 0),
                    (prefix + "same.go", b"y", 0, 0),
                ]
            ),
            self._zip_bytes([(prefix + "\N{LATIN SMALL LETTER E WITH ACUTE}.go", b"x", 0, 0)]),
            self._zip_bytes(
                [(prefix + "link.go", b"x", 3, 0o120777 << 16)]
            ),
        ]
        expected = [(1, 1), (2, 2), (1, 1), (1, 1)]
        for raw, (entry_count, total_bytes) in zip(cases, expected):
            with self.subTest(raw_sha256=hashlib.sha256(raw).hexdigest()):
                with self.assertRaises(RUNNER.ReviewError):
                    RUNNER.inspect_zip_structure(
                        raw,
                        expected_entry_count=entry_count,
                        expected_total_uncompressed_bytes=total_bytes,
                    )

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(self) -> None:
        with self.assertRaises(RUNNER.ReviewError):
            RUNNER.strict_json(b'{"a":1,"a":2}\n', "duplicate")
        with self.assertRaises(RUNNER.ReviewError):
            RUNNER.strict_json(b'{"a":NaN}\n', "nonfinite")

    def test_output_paths_remain_absent_after_tests(self) -> None:
        for name in RUNNER.RESERVED_OUTPUT_NAMES:
            self.assertFalse((RUNNER.ROOT / RUNNER.RUNG3 / name).exists(), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
