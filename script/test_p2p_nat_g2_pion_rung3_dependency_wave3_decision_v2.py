#!/usr/bin/env python3
"""Tests for the Wave3 32/32 checksum-identity successor decision."""

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
    raise RuntimeError("tests require `python3 -I -B -S`")

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v2.py"
)
SPEC = importlib.util.spec_from_file_location("wave3_identity_decision_v2", PATH)
assert SPEC and SPEC.loader
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)


class Wave3IdentityDecisionV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = D.evaluate(False)[0]
        cls.v1 = D.verify_content_bound(
            D.stable_read(D.V1_PACKAGE[0]),
            D.V1_PACKAGE[0]["contentSha256"],
            "E_V1",
        )

    def test_01_live_exact_decision(self) -> None:
        expected, summary = D.evaluate(True)
        self.assertEqual(
            (D.ROOT / D.DECISION_PATH).read_bytes(),
            D.canonical_bytes(expected),
        )
        self.assertTrue(summary["validationPassed"])
        self.assertEqual(summary["identityRecordCount"], 32)
        self.assertTrue(summary["acquisitionReady"])
        self.assertFalse(summary["acquisitionAuthorized"])
        self.assertFalse(summary["sourceAcquired"])

    def test_02_v1_decision_package_is_exactly_bound(self) -> None:
        rows = self.expected["successorBindings"]["wave3V1DecisionPackage"][
            "files"
        ]
        self.assertEqual(rows, list(D.V1_PACKAGE))
        self.assertEqual(
            self.v1["contentBinding"]["sha256"],
            "e31e1bb96802082047e1a9c9d1c1cb43d8a8415f72294282d3b97c97b1cafc2a",
        )
        self.assertEqual(self.v1["wave"]["identityRecordCount"], 31)
        self.assertFalse(self.v1["wave"]["acquisitionReady"])

    def test_03_public_decision_and_execution_permit_packages_are_exact(self) -> None:
        bindings = self.expected["successorBindings"]
        self.assertEqual(
            bindings["publicChecksumDecisionPackage"]["files"],
            list(D.PUBLIC_DECISION_PACKAGE),
        )
        self.assertEqual(
            bindings["sumDbExecutionPermitPackage"]["files"],
            list(D.EXECUTION_PERMIT_PACKAGE),
        )
        for row in (
            *D.PUBLIC_DECISION_PACKAGE,
            *D.EXECUTION_PERMIT_PACKAGE,
        ):
            self.assertEqual(
                hashlib.sha256((D.ROOT / row["path"]).read_bytes()).hexdigest(),
                row["rawSha256"],
            )

    def test_04_execution_claim_evidence_receipt_manifest_are_exact(self) -> None:
        execution = self.expected["successorBindings"]["sumDbExecution"]
        self.assertEqual(execution["claim"], D.EXECUTION_CLAIM)
        self.assertEqual(execution["receipt"], D.EXECUTION_RECEIPT)
        self.assertEqual(execution["manifest"], D.EXECUTION_MANIFEST)
        directory = execution["evidenceDirectory"]
        self.assertEqual(directory["path"], D.EVIDENCE_ROOT)
        self.assertEqual(directory["mode"], "0700")
        self.assertEqual(directory["fileCount"], 11)
        self.assertEqual(directory["files"], list(D.EVIDENCE_FILES))
        self.assertEqual(execution["executionAttemptId"], D.EXECUTION_ATTEMPT_ID)
        self.assertEqual(execution["recordNumber"], 468)
        self.assertEqual(execution["treeSize"], 57_977_200)
        self.assertEqual(execution["networkRequestAttemptCount"], 10)
        self.assertEqual(execution["tileRequestCount"], 9)
        self.assertFalse(execution["sourceAcquired"])

    def test_05_readback_package_and_consumed_outputs_are_exact(self) -> None:
        bindings = self.expected["successorBindings"]
        self.assertEqual(
            bindings["independentReadbackPermitPackage"]["files"],
            list(D.READBACK_PERMIT_PACKAGE),
        )
        consumed = bindings["consumedIndependentReadback"]
        self.assertEqual(consumed["claim"], D.READBACK_CLAIM)
        self.assertEqual(consumed["receipt"], D.READBACK_RECEIPT)
        self.assertEqual(consumed["manifest"], D.READBACK_MANIFEST)
        self.assertEqual(consumed["executionAttemptId"], D.EXECUTION_ATTEMPT_ID)
        self.assertEqual(consumed["readbackAttemptId"], D.READBACK_ATTEMPT_ID)
        self.assertTrue(consumed["offline"])
        self.assertEqual(consumed["networkRequestAttemptCount"], 0)
        self.assertFalse(consumed["sourceAcquired"])

    def test_06_wave_identity_counts_are_exactly_32_of_32(self) -> None:
        wave = self.expected["wave"]
        self.assertEqual(wave["tupleCount"], 16)
        self.assertEqual(wave["goModH1Count"], 16)
        self.assertEqual(wave["moduleZipH1Count"], 16)
        self.assertEqual(wave["completeH1PairCount"], 16)
        self.assertEqual(wave["identityRecordCount"], 32)
        self.assertEqual(wave["requiredIdentityRecordCount"], 32)
        self.assertEqual(wave["blockedTupleCount"], 0)
        self.assertTrue(wave["acquisitionReady"])
        self.assertTrue(
            all(
                row["acquisitionReady"]
                and row["checksumIdentity"]["completePair"]
                for row in wave["tuples"]
            )
        )

    def test_07_kr_pty_pair_comes_from_consumed_readback(self) -> None:
        pty = self.expected["wave"]["tuples"][0]
        self.assertEqual(pty["module"], D.TARGET_MODULE)
        self.assertEqual(pty["version"], D.TARGET_VERSION)
        self.assertEqual(pty["checksumIdentity"]["goModH1"], D.TARGET_MOD_H1)
        self.assertEqual(pty["checksumIdentity"]["moduleZipH1"], D.TARGET_ZIP_H1)
        evidence = pty["checksumIdentity"]["moduleZipEvidence"]
        self.assertEqual(evidence["evidenceKind"], "independent_sumdb_readback")
        self.assertEqual(evidence["executionAttemptId"], D.EXECUTION_ATTEMPT_ID)
        self.assertEqual(evidence["readbackAttemptId"], D.READBACK_ATTEMPT_ID)
        self.assertEqual(
            evidence["independentReadback"]["rawSha256"],
            D.READBACK_RECEIPT["rawSha256"],
        )
        closure = self.expected["identityClosure"]
        self.assertTrue(closure["identityPairComplete"])
        self.assertTrue(closure["closedByConsumedIndependentOfflineReadback"])
        self.assertFalse(closure["sourceAcquired"])
        self.assertFalse(closure["sourceAuthorOrRepositoryAttested"])

    def test_08_non_pty_tuples_are_byte_semantically_unchanged(self) -> None:
        self.assertEqual(
            self.expected["wave"]["tuples"][1:],
            self.v1["wave"]["tuples"][1:],
        )

    def test_09_order_parents_selection_and_graph_are_preserved(self) -> None:
        new_tuples = self.expected["wave"]["tuples"]
        old_tuples = self.v1["wave"]["tuples"]
        for new, old in zip(new_tuples, old_tuples):
            for key in (
                "tupleOrder",
                "tupleId",
                "tupleDigestAlgorithm",
                "tupleDigestSha256",
                "module",
                "version",
                "selectedByGraphAlgorithm",
                "versionSpecificVertexRetained",
                "rejected",
                "parentDeclarations",
                "acquisitionAuthorized",
            ):
                self.assertEqual(new[key], old[key], (new["tupleOrder"], key))
        self.assertEqual(self.expected["graphBinding"], self.v1["graphBinding"])
        self.assertEqual(
            self.expected["predecessorBindings"],
            self.v1["predecessorBindings"],
        )
        self.assertEqual(
            sum(row["selectedByGraphAlgorithm"] for row in new_tuples),
            4,
        )
        self.assertEqual(
            sum(len(row["parentDeclarations"]) for row in new_tuples),
            18,
        )

    def test_10_authority_is_decision_only(self) -> None:
        authority = self.expected["authority"]
        for key, value in authority.items():
            self.assertEqual(value, key == "decisionRecorded", key)
        self.assertFalse(authority["acquisitionAuthorized"])
        self.assertFalse(authority["networkAuthorized"])
        self.assertFalse(authority["filesystemMutationAuthorized"])
        self.assertFalse(authority["sourceLoadAuthorized"])
        self.assertFalse(authority["sourceExecutionAuthorized"])
        self.assertFalse(authority["compileAuthorized"])

    def test_11_all_closure_and_release_claims_remain_false(self) -> None:
        closure = self.expected["closure"]
        for key, value in closure.items():
            self.assertFalse(value, key)
        self.assertFalse(closure["dependencyFixedPointReached"])
        self.assertFalse(closure["dependencySourceClosureComplete"])
        self.assertFalse(closure["dependencySourceReviewed"])
        self.assertFalse(closure["semanticClosureComplete"])
        self.assertFalse(closure["candidateSelected"])
        self.assertFalse(closure["librarySelected"])
        self.assertFalse(closure["releaseReady"])
        self.assertFalse(closure["rungThreeComplete"])

    def test_12_nonclaims_keep_identity_separate_from_source_attestation(self) -> None:
        text = "\n".join(self.expected["nonClaims"])
        for phrase in (
            "not a network or acquisition execution permit",
            "acquisition readiness not acquisition authority",
            "not source author or repository attestation",
            "no source bytes were acquired",
            "not dependency fixed point or source closure",
            "no semantic closure candidate library release",
        ):
            self.assertIn(phrase, text)

    def test_13_next_boundary_is_separate_32_resource_one_use_permit(self) -> None:
        preparation = self.expected["sourceAcquisitionPreparation"]
        self.assertTrue(preparation["separateExecutionPermitRequired"])
        self.assertTrue(preparation["oneUsePermitRequired"])
        self.assertEqual(preparation["tupleCount"], 16)
        self.assertEqual(preparation["resourcesPerTuple"], 2)
        self.assertEqual(preparation["resourceCount"], 32)
        self.assertEqual(
            preparation["requestOrder"],
            "tuple_order_ascending_mod_then_zip",
        )
        self.assertFalse(preparation["acquisitionAuthorizedByThisDecision"])
        self.assertTrue(preparation["independentPostConsumptionReadbackRequired"])
        self.assertIn(
            "one_use_32_resource_wave3_source_acquisition_permit",
            self.expected["nextAction"],
        )

    def test_14_wave3_acquisition_namespace_remains_absent(self) -> None:
        D.require_wave3_namespace_absent()
        self.assertFalse((D.ROOT / D.WAVE3_CLAIM_PATH).exists())
        self.assertFalse((D.ROOT / D.WAVE3_FINAL_PATH).exists())

    def test_15_reader_and_tool_bindings_are_exact(self) -> None:
        self.assertEqual(
            self.expected["readerDocumentBinding"],
            {"path": D.READER_PATH, "rawSha256": D.EXPECTED_READER_RAW},
        )
        tools = {
            row["path"]: row["rawSha256"]
            for row in self.expected["toolBindings"]
        }
        self.assertEqual(
            tools,
            {
                D.THIS_CHECKER_PATH: hashlib.sha256(PATH.read_bytes()).hexdigest(),
                D.THIS_TESTS_PATH: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
        )

    def test_16_external_raw_or_shape_mutations_fail_closed(self) -> None:
        changed = dict(D.READBACK_RECEIPT)
        changed["rawSha256"] = "0" * 64
        with self.assertRaises(D.DecisionError):
            D.stable_read(changed)
        changed = dict(D.READBACK_RECEIPT)
        changed["bytes"] += 1
        with self.assertRaises(D.DecisionError):
            D.stable_read(changed)
        raw = D.stable_read(D.READBACK_RECEIPT)
        mutated = raw.replace(D.TARGET_ZIP_H1.encode(), b"h1:" + b"A" * 44, 1)
        with self.assertRaises(D.DecisionError):
            D.verify_content_bound(
                mutated,
                D.READBACK_RECEIPT["contentSha256"],
                "E_MUTATION",
            )

    def test_17_strict_json_and_content_mutations_fail(self) -> None:
        with self.assertRaises(D.DecisionError):
            D.strict_json(b'{"a":1,"a":2}\n')
        changed = copy.deepcopy(self.expected)
        changed["authority"]["networkAuthorized"] = True
        self.assertNotEqual(changed, self.expected)
        changed_without_binding = copy.deepcopy(changed)
        changed_without_binding.pop("contentBinding")
        rebound = D.content_bound(changed_without_binding)
        self.assertNotEqual(
            D.canonical_bytes(rebound),
            D.canonical_bytes(self.expected),
        )

    def test_18_bool_integer_type_confusion_changes_exact_bytes(self) -> None:
        mutations = (
            ("authority", "networkAuthorized", 0),
            ("authority", "decisionRecorded", 1),
            ("wave", "identityRecordCount", 32.0),
            ("wave", "acquisitionReady", 1),
        )
        for section, key, value in mutations:
            changed = copy.deepcopy(self.expected)
            changed[section][key] = value
            self.assertEqual(changed, self.expected, (section, key))
            self.assertNotEqual(
                D.canonical_bytes(changed),
                D.canonical_bytes(self.expected),
                (section, key),
            )

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=D.ROOT,
            capture_output=True,
            check=False,
        )

    def test_19_canonical_cli_default_print_and_invalid(self) -> None:
        default = self.run_cli()
        self.assertEqual(default.returncode, 0)
        summary = json.loads(default.stdout)
        self.assertTrue(summary["validationPassed"])
        self.assertEqual(summary["identityRecordCount"], 32)
        self.assertFalse(summary["acquisitionAuthorized"])
        printed = self.run_cli("--print-expected")
        self.assertEqual(printed.returncode, 0)
        self.assertEqual(
            printed.stdout,
            (D.ROOT / D.DECISION_PATH).read_bytes(),
        )
        invalid = self.run_cli("--execute")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"execute", invalid.stdout)

    def test_20_checker_has_no_network_write_or_subprocess_surface(self) -> None:
        source = PATH.read_text()
        for token in (
            "socket.",
            "urllib.",
            "http.client",
            "requests.",
            "subprocess.",
            "os.write(",
            "O_CREAT",
            "O_TRUNC",
            "proxy.golang.org",
            "/@v/",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
