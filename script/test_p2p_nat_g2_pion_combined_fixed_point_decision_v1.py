#!/usr/bin/env python3
"""Mutation tests for the combined fixed-point preparation decision."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("tests require unoptimized `python3 -I -B -S`")

import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / "check_p2p_nat_g2_pion_combined_fixed_point_decision_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "g2_pion_combined_fixed_point_decision_checker_v1",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load combined fixed-point decision checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class StdoutCapture:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


class CombinedFixedPointDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = checker.expected_decision(checker.ROOT)
        cls.decision_raw = (
            checker.ROOT / checker.DECISION_PATH
        ).read_bytes()
        cls.reader_raw = (checker.ROOT / checker.READER_PATH).read_bytes()

    def test_01_baseline_validates_exact_on_disk_package(self) -> None:
        result = checker.check_repository(checker.ROOT)
        self.assertTrue(result["validationPassed"])
        self.assertTrue(result["onDiskExactEqualityVerified"])
        self.assertEqual(result["heldSourceInputCount"], 69)
        self.assertEqual(
            result["status"],
            "validated_execution_not_authorized",
        )
        self.assertFalse(result["candidateOutputAcceptedAsEvidence"])
        self.assertFalse(result["fixedPointEvaluationAuthorized"])

    def test_02_print_expected_is_exact_canonical_disk_bytes(self) -> None:
        capture = StdoutCapture()
        with mock.patch.object(sys, "stdout", capture):
            result = checker.main(["--print-expected"])
        self.assertEqual(result, 0)
        self.assertEqual(capture.buffer.getvalue(), self.decision_raw)
        self.assertEqual(
            self.decision_raw,
            checker.canonical_bytes(self.expected),
        )

    def test_03_content_binding_is_strict_and_mutations_fail(self) -> None:
        parsed = checker.validate_decision_bytes(
            self.decision_raw,
            self.expected,
        )
        without = dict(parsed)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            checker.sha256(checker.canonical_bytes(without)),
        )

        mutated = copy.deepcopy(parsed)
        mutated["status"] = "execution_authorized"
        mutated.pop("contentBinding")
        rebound = checker.content_bound(mutated)
        with self.assertRaises(checker.CheckError) as caught:
            checker.validate_decision_bytes(
                checker.canonical_bytes(rebound),
                self.expected,
            )
        self.assertEqual(caught.exception.code, "E_DECISION")

        noncanonical = json.dumps(
            parsed,
            indent=2,
            ensure_ascii=True,
        ).encode() + b"\n"
        with self.assertRaises(checker.CheckError) as caught:
            checker.validate_decision_bytes(noncanonical, self.expected)
        self.assertEqual(caught.exception.code, "E_CANONICAL_DECISION")

    def test_04_duplicate_and_nonfinite_json_fail_closed(self) -> None:
        duplicate = self.decision_raw.replace(
            b'{"authority":',
            b'{"schemaVersion":"duplicate","authority":',
            1,
        )
        with self.assertRaises(checker.CheckError) as caught:
            checker.validate_decision_bytes(duplicate, self.expected)
        self.assertEqual(caught.exception.code, "E_JSON")
        with self.assertRaises(checker.CheckError) as caught:
            checker.strict_json(b'{"value":NaN}\n')
        self.assertEqual(caught.exception.code, "E_JSON")

    def test_05_exact_69_source_bindings_are_frozen(self) -> None:
        source_set = self.expected["sourceInputSet"]
        rows = source_set["bindings"]
        self.assertEqual(len(rows), 69)
        self.assertEqual(
            (1, 34, 34),
            (
                sum(row["kind"] == "root_zip" for row in rows),
                sum(row["kind"] == "mod" for row in rows),
                sum(row["kind"] == "zip" for row in rows),
            ),
        )
        self.assertEqual(len({row["path"] for row in rows}), 69)
        self.assertEqual(
            source_set["inputSetSha256"],
            checker.sha256(checker.canonical_bytes(rows)),
        )
        self.assertEqual(
            source_set["candidateSourceProjectionSha256"],
            checker.CANDIDATE_SOURCE_PROJECTION_SHA256,
        )
        self.assertEqual(
            source_set["decisionHeldBindingSetSha256"],
            checker.DECISION_HELD_BINDING_SET_SHA256,
        )
        self.assertEqual(
            source_set["decisionHeldBindingSetSha256"],
            checker.sha256(checker.canonical_bytes(rows)),
        )
        projection = checker.candidate_projection_from_decision_rows(rows)
        self.assertEqual(
            checker.sha256(checker.canonical_bytes(projection)),
            checker.CANDIDATE_SOURCE_PROJECTION_SHA256,
        )
        contract = source_set["projectionContract"]
        self.assertEqual(
            contract["candidateFieldSet"],
            list(checker.CANDIDATE_SOURCE_PROJECTION_FIELDS),
        )
        self.assertEqual(
            contract["decisionHeldBindingFieldSet"],
            list(checker.DECISION_HELD_BINDING_FIELDS),
        )
        self.assertEqual(
            contract["sortKeys"],
            list(checker.CANDIDATE_SOURCE_PROJECTION_SORT),
        )
        self.assertTrue(
            contract["decisionRowsProjectBackToCandidateDigest"]
        )
        self.assertTrue(all(row["mode"] == "0600" for row in rows))
        self.assertTrue(all(row["linkCount"] == 1 for row in rows))

    def test_06_predecessor_and_candidate_tool_pins_are_exact(self) -> None:
        chain = self.expected["canonicalPredecessorChain"]
        self.assertEqual(len(chain), 12)
        self.assertEqual(
            self.expected["canonicalPredecessorChainSha256"],
            checker.sha256(checker.canonical_bytes(chain)),
        )
        tools = self.expected["toolBindings"]
        self.assertEqual(
            tools["candidateChecker"]["rawSha256"],
            checker.CANDIDATE_CHECKER_SHA256,
        )
        self.assertEqual(
            tools["candidateCheckerTests"]["rawSha256"],
            checker.CANDIDATE_TESTS_SHA256,
        )
        self.assertEqual(
            tools["immutableWave1GraphRunner"],
            {
                "role": "immutable_wave1_graph_runner",
                "path": checker.WAVE1_RUNNER_PATH,
                "rawSha256": checker.WAVE1_RUNNER_SHA256,
            },
        )
        for key in (
            "candidateChecker",
            "candidateCheckerTests",
            "immutableWave1GraphRunner",
        ):
            binding = tools[key]
            self.assertEqual(
                hashlib.sha256(
                    (checker.ROOT / binding["path"]).read_bytes()
                ).hexdigest(),
                binding["rawSha256"],
            )
        runner_rows = [
            row
            for row in chain
            if row["role"] == "immutable_wave1_graph_runner"
        ]
        self.assertEqual(
            runner_rows,
            [
                {
                    "role": "immutable_wave1_graph_runner",
                    "path": checker.WAVE1_RUNNER_PATH,
                    "rawSha256": checker.WAVE1_RUNNER_SHA256,
                }
            ],
        )
        self.assertTrue(tools["immutableWave1GraphRunnerHeldDirectly"])
        self.assertFalse(tools["candidateCheckerOutputAcceptedAsEvidence"])

    def test_07_observation_is_not_fixed_point_evidence(self) -> None:
        observation = self.expected["candidateObservation"]
        self.assertFalse(observation["evidenceAccepted"])
        self.assertFalse(observation["durableCandidateArtifactExists"])
        self.assertFalse(observation["observationRecomputedByThisDecisionChecker"])
        self.assertFalse(observation["observedFixedPointReached"])
        self.assertFalse(observation["acceptanceSatisfied"])
        self.assertEqual(observation["observedNewTupleCount"], 16)
        acceptance = self.expected["fixedPointAcceptance"]
        self.assertEqual(acceptance["exactFrontierCountRequired"], 0)
        self.assertEqual(
            acceptance["unmappedExternalImportCountRequired"],
            0,
        )
        self.assertEqual(
            acceptance["unresolvedDeclaredExternalImportCountRequired"],
            0,
        )
        self.assertTrue(acceptance["independentReadbackRequired"])

    def test_08_authority_closure_and_authentication_remain_closed(self) -> None:
        authority = self.expected["authority"]
        self.assertTrue(authority["decisionRecorded"])
        self.assertTrue(
            all(
                value is False
                for key, value in authority.items()
                if key != "decisionRecorded"
            )
        )
        self.assertTrue(
            all(value is False for value in self.expected["closure"].values())
        )
        one_use = self.expected["futureOneUseContract"]
        self.assertFalse(one_use["permitAuthorizedByThisDecision"])
        self.assertFalse(one_use["automaticRetryAllowed"])
        self.assertFalse(one_use["secondExecutionAllowed"])
        self.assertTrue(one_use["separateExactPermitRequired"])
        for key in (
            "postClaimFailureConsumesPermit",
            "postClaimUncertaintyConsumesPermit",
            "claimCreationUncertaintyConsumesPermit",
            "claimPersistsAfterAnyEvaluationAttempt",
            "resultOrFailureMutuallyExclusive",
            "failureForbiddenAfterResultPublishAttempt",
            "separateReadbackClaimRequired",
            "readbackClaimCreationUncertaintyConsumesPermit",
            "readbackPostClaimFailureConsumesPermit",
            "readbackPostClaimUncertaintyConsumesPermit",
            "readbackReceiptOrFailureMutuallyExclusive",
            "readbackFailureForbiddenAfterReceiptPublishAttempt",
            "readbackManifestWrittenLast",
        ):
            self.assertTrue(one_use[key], key)
        for key in (
            "preClaimFailureConsumesPermit",
            "readbackPreClaimFailureConsumesPermit",
            "readbackSecondExecutionAllowed",
            "readbackAutomaticRetryAllowed",
        ):
            self.assertFalse(one_use[key], key)
        self.assertEqual(
            one_use["postPublishUncertainState"],
            "consumed_terminal_state_uncertain",
        )
        self.assertEqual(
            one_use["readbackPostPublishUncertainState"],
            "consumed_terminal_state_uncertain",
        )

    def test_09_future_namespace_is_independent_and_absent(self) -> None:
        namespace = self.expected["independentNamespace"]
        self.assertFalse(namespace["namespaceSharedWithWave1OrWave2"])
        self.assertFalse(namespace["namespaceReservationIsExecutionAuthority"])
        checker.validate_namespace_absent(checker.ROOT)
        self.assertEqual(
            len(set(checker.FUTURE_PATHS)),
            len(checker.FUTURE_PATHS),
        )
        self.assertEqual(
            namespace["readbackFailurePath"],
            checker.FUTURE_READBACK_FAILURE_PATH,
        )

    def test_10_reader_is_exact_and_bound(self) -> None:
        checker.validate_reader_bytes(self.reader_raw)
        self.assertEqual(
            self.expected["documentationBinding"]["rawSha256"],
            hashlib.sha256(self.reader_raw).hexdigest(),
        )
        with self.assertRaises(checker.CheckError) as caught:
            checker.validate_reader_bytes(self.reader_raw + b" ")
        self.assertEqual(caught.exception.code, "E_READER")

    def test_11_held_hash_link_and_named_barriers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            payload = b"bounded input\n"
            source = root / "input.bin"
            source.write_bytes(payload)
            os.chmod(source, 0o600)
            binding = {
                "path": "input.bin",
                "rawSha256": "0" * 64,
                "maximumBytes": len(payload),
                "ownerOnly": True,
            }
            with self.assertRaises(checker.CheckError) as caught:
                checker.HeldSet(root, [binding])
            self.assertEqual(caught.exception.code, "E_RAW_PIN")

            binding["rawSha256"] = hashlib.sha256(payload).hexdigest()
            linked = root / "linked.bin"
            os.link(source, linked)
            with self.assertRaises(checker.CheckError) as caught:
                checker.HeldSet(root, [binding])
            self.assertEqual(caught.exception.code, "E_HELD_SET")
            linked.unlink()

            held = checker.HeldSet(root, [binding])
            displaced = root / "input-original.bin"
            source.rename(displaced)
            source.write_bytes(payload)
            os.chmod(source, 0o600)
            try:
                with self.assertRaises(checker.CheckError) as caught:
                    held.final_barrier()
                self.assertEqual(caught.exception.code, "E_HELD_SET")
            finally:
                held.close()

    def test_12_static_checker_surface_is_offline_and_read_only(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported.isdisjoint(
                {
                    "socket",
                    "subprocess",
                    "urllib",
                    "http",
                    "ftplib",
                    "requests",
                    "ssl",
                    "zipfile",
                }
            )
        )
        for forbidden in (
            ".extract(",
            ".extractall(",
            "os.system(",
            "os.popen(",
            "os.fork(",
            "os.spawn",
            "os.exec",
            "os.mkdir(",
            "os.makedirs(",
            "os.rename(",
            "os.replace(",
            "os.unlink(",
            "os.remove(",
            ".write_bytes(",
            ".write_text(",
            "O_WRONLY",
            "O_RDWR",
            "O_CREAT",
            "O_TRUNC",
            "O_APPEND",
            "eval(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertEqual(source.count("exec(code, module.__dict__"), 1)
        self.assertNotIn("sys.stderr.buffer.write(", source)
        self.assertIn("sys.stdout.buffer.write(", source)
        self.assertNotIn("--output", source)
        self.assertNotIn("--record", source)
        self.assertNotIn("--root", source)
        with mock.patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit):
                checker.parse_arguments(["--output", "forbidden.json"])

    def test_13_projection_schema_order_and_digest_mutations_fail(self) -> None:
        rows = copy.deepcopy(self.expected["sourceInputSet"]["bindings"])
        rows[0]["unexpected"] = False
        with self.assertRaises(checker.CheckError) as caught:
            checker.candidate_projection_from_decision_rows(rows)
        self.assertEqual(caught.exception.code, "E_SOURCE_PROJECTION")

        rows = copy.deepcopy(self.expected["sourceInputSet"]["bindings"])
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaises(checker.CheckError) as caught:
            checker.candidate_projection_from_decision_rows(rows)
        self.assertEqual(caught.exception.code, "E_SOURCE_PROJECTION")

        rows = copy.deepcopy(self.expected["sourceInputSet"]["bindings"])
        rows[0]["rawSha256"] = "0" * 64
        projection = checker.candidate_projection_from_decision_rows(rows)
        self.assertNotEqual(
            checker.sha256(checker.canonical_bytes(projection)),
            checker.CANDIDATE_SOURCE_PROJECTION_SHA256,
        )

    def test_14_claim_and_staging_namespace_mutations_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            (root / checker.DEPENDENCY_ROOT).mkdir(
                parents=True,
                mode=0o700,
            )
            (root / checker.BASE).mkdir(parents=True, mode=0o700)
            with checker.HeldNamespace(root) as held_namespace:
                checker.validate_namespace_absent(root, held_namespace)
                claim = root / checker.FUTURE_CLAIM_PATH
                claim.write_bytes(b"claim")
                os.chmod(claim, 0o600)
                with self.assertRaises(checker.CheckError) as caught:
                    checker.validate_namespace_absent(root, held_namespace)
                self.assertEqual(caught.exception.code, "E_NAMESPACE")
                claim.unlink()

                staging = (
                    root
                    / checker.DEPENDENCY_ROOT
                    / f"{checker.FUTURE_STAGING_PREFIX}mutation"
                )
                staging.mkdir(mode=0o700)
                with self.assertRaises(checker.CheckError) as caught:
                    checker.validate_namespace_absent(root, held_namespace)
                self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_15_root_and_output_parent_replacements_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outer = Path(temporary)
            root = outer / "root"
            root.mkdir(mode=0o700)
            source = root / "input.bin"
            payload = b"held root\n"
            source.write_bytes(payload)
            os.chmod(source, 0o600)
            binding = {
                "path": "input.bin",
                "rawSha256": hashlib.sha256(payload).hexdigest(),
                "maximumBytes": len(payload),
                "ownerOnly": True,
            }
            held = checker.HeldSet(root, [binding])
            displaced = outer / "root-displaced"
            root.rename(displaced)
            root.mkdir(mode=0o700)
            try:
                with self.assertRaises(checker.CheckError) as caught:
                    held.final_barrier()
                self.assertEqual(caught.exception.code, "E_HELD_SET")
            finally:
                held.close()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            (root / checker.DEPENDENCY_ROOT).mkdir(
                parents=True,
                mode=0o700,
            )
            output_parent = root / checker.BASE
            output_parent.mkdir(parents=True, mode=0o700)
            held_namespace = checker.HeldNamespace(root)
            displaced = output_parent.with_name(
                output_parent.name + "-displaced"
            )
            output_parent.rename(displaced)
            output_parent.mkdir(mode=0o700)
            try:
                with self.assertRaises(checker.CheckError) as caught:
                    held_namespace.final_barrier()
                self.assertEqual(
                    caught.exception.code,
                    "E_NAMESPACE_IDENTITY",
                )
            finally:
                held_namespace.close()

    def test_16_callback_is_followed_by_final_namespace_rescan(self) -> None:
        callback_finished = False
        observed_after_callback = False
        real_validate = checker.validate_namespace_absent

        def callback() -> None:
            nonlocal callback_finished
            callback_finished = True

        def observe(
            root: Path,
            held_namespace: checker.HeldNamespace | None = None,
        ) -> None:
            nonlocal observed_after_callback
            if callback_finished:
                observed_after_callback = True
            real_validate(root, held_namespace)

        with mock.patch.object(
            checker,
            "validate_namespace_absent",
            side_effect=observe,
        ):
            checker.check_repository(
                checker.ROOT,
                before_final_barrier=callback,
            )
        self.assertTrue(observed_after_callback)


if __name__ == "__main__":
    unittest.main(verbosity=2)
