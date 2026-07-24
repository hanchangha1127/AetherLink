#!/usr/bin/env python3
"""Mutation tests for the G2 dependency wave-one preparation decision."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    ROOT
    / "script/check_p2p_nat_g2_pion_rung3_dependency_wave1_decision_v1.py"
)
SPEC = importlib.util.spec_from_file_location("dependency_wave1_checker", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class DependencyWaveOneDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.base_temp.name) / "base"
        cls.base.mkdir()
        cls.required_paths = (
            CHECKER.DECISION_PATH,
            CHECKER.READER_PATH,
            CHECKER.PREDECESSOR_PATH,
            CHECKER.PREDECESSOR_CHECKER_PATH,
            CHECKER.PREDECESSOR_TESTS_PATH,
            CHECKER.PLAN_PATH,
            CHECKER.PROFILE_PATH,
            CHECKER.PROVENANCE_PATH,
            CHECKER.RUNG_TWO_DECISION_PATH,
            CHECKER.RUNG_TWO_RECEIPT_PATH,
            CHECKER.OFFLINE_RESULT_PATH,
            CHECKER.CLASSIFICATIONS_PATH,
            CHECKER.SEMANTIC_RESULT_PATH,
            CHECKER.SEMANTIC_MANIFEST_PATH,
            CHECKER.PATCH_DECISION_PATH,
            CHECKER.SOURCE_ARCHIVE_PATH,
        )
        for relative in cls.required_paths:
            source = ROOT / relative
            target = cls.base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.base_temp.cleanup()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        shutil.copytree(self.base, self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @property
    def decision_path(self) -> Path:
        return self.root / CHECKER.DECISION_PATH

    def load_decision(self) -> dict:
        return json.loads(self.decision_path.read_text(encoding="utf-8"))

    def write_decision(self, decision: dict, *, rebind: bool = True) -> None:
        if rebind:
            payload = copy.deepcopy(decision)
            payload.pop("contentBinding", None)
            decision["contentBinding"] = {
                "algorithm": "sha256",
                "canonicalization": (
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf"
                ),
                "scope": "decision_without_contentBinding",
                "sha256": CHECKER.sha256(CHECKER.canonical_bytes(payload)),
            }
        self.decision_path.write_text(
            json.dumps(decision, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def mutate(self, callback) -> None:
        decision = self.load_decision()
        callback(decision)
        self.write_decision(decision)

    def assert_fails(self, code: str | None = None, hook=None) -> None:
        with self.assertRaises(CHECKER.CheckError) as captured:
            CHECKER.check(self.root, before_final_barrier=hook)
        if code is not None:
            self.assertEqual(captured.exception.code, code)

    def test_01_baseline(self) -> None:
        CHECKER.check(self.root)

    def test_02_duplicate_json_key_is_rejected(self) -> None:
        raw = self.decision_path.read_text(encoding="utf-8")
        raw = raw.replace(
            '  "schemaVersion": "1.0",',
            '  "schemaVersion": "1.0",\n  "schemaVersion": "1.0",',
            1,
        )
        self.decision_path.write_text(raw, encoding="utf-8")
        self.assert_fails("E_JSON")

    def test_03_non_finite_json_is_rejected(self) -> None:
        raw = self.decision_path.read_text(encoding="utf-8")
        raw = raw.replace('"requestCount": 0', '"requestCount": NaN', 1)
        self.decision_path.write_text(raw, encoding="utf-8")
        self.assert_fails("E_JSON")

    def test_04_missing_top_level_key_is_rejected(self) -> None:
        self.mutate(lambda d: d.pop("nonClaims"))
        self.assert_fails("E_SCHEMA")

    def test_05_unknown_top_level_key_is_rejected(self) -> None:
        self.mutate(lambda d: d.__setitem__("unexpected", False))
        self.assert_fails("E_SCHEMA")

    def test_06_status_drift_is_rejected(self) -> None:
        self.mutate(lambda d: d.__setitem__("status", "authorized_not_consumed"))
        self.assert_fails("E_STATE")

    def test_07_result_drift_is_rejected(self) -> None:
        self.mutate(lambda d: d.__setitem__("result", "acquisition_complete"))
        self.assert_fails("E_STATE")

    def test_08_next_action_drift_is_rejected(self) -> None:
        self.mutate(lambda d: d.__setitem__("nextAction", "execute_wave"))
        self.assert_fails("E_STATE")

    def test_09_content_binding_drift_is_rejected(self) -> None:
        decision = self.load_decision()
        decision["contentBinding"]["sha256"] = "0" * 64
        self.write_decision(decision, rebind=False)
        self.assert_fails("E_BINDING")

    def test_10_predecessor_binding_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["predecessorBinding"].__setitem__(
                "decisionRawSha256", "0" * 64
            )
        )
        self.assert_fails("E_LINEAGE")

    def test_11_predecessor_bytes_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.PREDECESSOR_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_fails("E_LINEAGE")

    def test_12_predecessor_checker_bytes_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.PREDECESSOR_CHECKER_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_fails("E_LINEAGE")

    def test_13_predecessor_tests_bytes_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.PREDECESSOR_TESTS_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_fails("E_LINEAGE")

    def test_14_plan_bytes_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.PLAN_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_fails("E_LINEAGE")

    def test_15_offline_result_bytes_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.OFFLINE_RESULT_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_fails("E_LINEAGE")

    def test_16_profile_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["productionProfiles"]["profiles"][0].__setitem__(
                "cgoEnabled", False
            )
        )
        self.assert_fails("E_PROFILE")

    def test_17_profile_build_tag_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["productionProfiles"]["profiles"][1][
                "explicitBuildTags"
            ].append("custom")
        )
        self.assert_fails("E_PROFILE")

    def test_18_graph_algorithm_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["productionProfiles"]["graphAlgorithm"].__setitem__(
                "unknownDirectiveRule", "ignore"
            )
        )
        self.assert_fails("E_PROFILE")

    def test_19_root_requirement_removal_is_rejected(self) -> None:
        self.mutate(lambda d: d["rootSeed"]["requirements"].pop())
        self.assert_fails("E_SEED")

    def test_20_root_requirement_reorder_is_rejected(self) -> None:
        def change(decision: dict) -> None:
            rows = decision["rootSeed"]["requirements"]
            rows[0], rows[1] = rows[1], rows[0]

        self.mutate(change)
        self.assert_fails("E_SEED")

    def test_21_checksum_context_promotion_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["rootSeed"]["checksumOnlyContextTuples"][0].__setitem__(
                "selected", True
            )
        )
        self.assert_fails("E_SEED")

    def test_22_wave_h1_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][0].__setitem__(
                "moduleZipH1", "h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
            )
        )
        self.assert_fails("E_WAVE")

    def test_23_wave_url_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][0].__setitem__(
                "url", d["wave"]["tuples"][0]["url"] + "?token=1"
            )
        )
        self.assert_fails("E_WAVE")

    def test_24_wave_output_collision_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][1].__setitem__(
                "outputPath", d["wave"]["tuples"][0]["outputPath"]
            )
        )
        self.assert_fails("E_WAVE")

    def test_25_wave_order_drift_is_rejected(self) -> None:
        self.mutate(lambda d: d["wave"]["tuples"][3].__setitem__("order", 5))
        self.assert_fails("E_WAVE")

    def test_26_tuple_identity_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][4].__setitem__(
                "tupleSha256", "f" * 64
            )
        )
        self.assert_fails("E_WAVE")

    def test_27_identity_overclaim_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["sourceIdentityPolicy"].__setitem__(
                "dependencyRepositoryOwnerAttestationClaimed", True
            )
        )
        self.assert_fails("E_IDENTITY")

    def test_28_direct_sumdb_proof_overclaim_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["sourceIdentityPolicy"].__setitem__(
                "dependencyDirectSumdbInclusionProofVerified", True
            )
        )
        self.assert_fails("E_IDENTITY")

    def test_29_resource_bound_bool_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["resourceLimits"].__setitem__(
                "maximumRequestCount", True
            )
        )
        self.assert_fails("E_BOUNDS")

    def test_30_resource_bound_expansion_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["resourceLimits"].__setitem__(
                "maximumAggregateResponseBytes", 134217729
            )
        )
        self.assert_fails("E_BOUNDS")

    def test_31_preparation_cannot_enable_network(self) -> None:
        self.mutate(
            lambda d: d["plannedAcquisitionContract"].__setitem__(
                "sourceAcquisitionNetworkIoAllowed", True
            )
        )
        self.assert_fails("E_AUTHORITY")

    def test_32_redirect_or_retry_cannot_be_enabled(self) -> None:
        self.mutate(
            lambda d: d["plannedAcquisitionContract"].__setitem__(
                "redirectsAllowed", True
            )
        )
        self.assert_fails("E_AUTHORITY")

    def test_33_filesystem_contract_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["filesystemContract"].__setitem__(
                "atomicNoReplaceFinalDirectoryPublicationRequired", False
            )
        )
        self.assert_fails("E_FILESYSTEM_CONTRACT")

    def test_34_receipt_contract_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["receiptContract"].__setitem__(
                "successRequiresManifestLastIndependentReadback", False
            )
        )
        self.assert_fails("E_RECEIPT")

    def test_35_sequence_execution_overclaim_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["sequence"][4].__setitem__("executed", True)
        )
        self.assert_fails("E_SEQUENCE")

    def test_36_authority_escalation_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["authority"].__setitem__(
                "dependencyAcquisitionAuthorized", True
            )
        )
        self.assert_fails("E_AUTHORITY")

    def test_37_authority_bool_int_confusion_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["authority"].__setitem__("gitWriteAuthorized", 0)
        )
        self.assert_fails("E_AUTHORITY")

    def test_38_execution_overclaim_is_rejected(self) -> None:
        self.mutate(lambda d: d["execution"].__setitem__("requestCount", 1))
        self.assert_fails("E_EXECUTION")

    def test_39_closure_overclaim_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["closure"].__setitem__(
                "dependencyClosureComplete", True
            )
        )
        self.assert_fails("E_CLOSURE")

    def test_40_candidate_selection_overclaim_is_rejected(self) -> None:
        self.mutate(lambda d: d["closure"].__setitem__("candidateSelected", True))
        self.assert_fails("E_CLOSURE")

    def test_41_nonclaim_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["nonClaims"].__setitem__(
                "goSumIsDirectDependencyRepositoryAttestation", True
            )
        )
        self.assert_fails("E_NONCLAIM")

    def test_42_reader_bytes_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.READER_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_fails("E_LINEAGE")

    def test_43_decision_symlink_is_rejected(self) -> None:
        target = self.decision_path.with_suffix(".real")
        os.replace(self.decision_path, target)
        os.symlink(target.name, self.decision_path)
        self.assert_fails("E_INVENTORY")

    def test_44_reader_hardlink_is_rejected(self) -> None:
        path = self.root / CHECKER.READER_PATH
        link = path.with_name("reader-hardlink")
        try:
            os.link(path, link)
        except OSError as exc:
            self.skipTest(f"hardlink unavailable: {exc}")
        self.assert_fails("E_INVENTORY")

    def test_45_unexpected_prefixed_sibling_is_rejected(self) -> None:
        sibling = (
            self.root
            / CHECKER.RUNG_THREE
            / "bounded-dependency-source-identity-and-acquisition-decision-v1.tmp"
        )
        sibling.write_text("staging\n", encoding="utf-8")
        self.assert_fails("E_INVENTORY")

    def test_46_replace_after_read_is_rejected(self) -> None:
        def hook(_snapshots) -> None:
            replacement = self.decision_path.with_suffix(".replacement")
            replacement.write_bytes(self.decision_path.read_bytes())
            os.replace(replacement, self.decision_path)

        self.assert_fails("E_TOCTOU", hook=hook)

    def test_47_in_place_mutation_after_read_is_rejected(self) -> None:
        def hook(_snapshots) -> None:
            with self.decision_path.open("r+b") as handle:
                handle.seek(0)
                first = handle.read(1)
                handle.seek(0)
                handle.write(b"[" if first != b"[" else b"{")
                handle.flush()
                os.fsync(handle.fileno())

        self.assert_fails("E_TOCTOU", hook=hook)

    def test_48_final_inventory_insertion_is_rejected(self) -> None:
        sibling = (
            self.root
            / CHECKER.RUNG_THREE
            / "bounded-dependency-source-identity-and-acquisition-decision-v1.late"
        )

        def hook(_snapshots) -> None:
            sibling.write_text("late\n", encoding="utf-8")

        self.assert_fails("E_TOCTOU", hook=hook)

    def test_49_missing_retained_source_archive_is_rejected(self) -> None:
        (self.root / CHECKER.SOURCE_ARCHIVE_PATH).unlink()
        self.assert_fails("E_FILESYSTEM")

    def test_50_changed_retained_source_archive_is_rejected(self) -> None:
        archive = self.root / CHECKER.SOURCE_ARCHIVE_PATH
        with archive.open("r+b") as handle:
            handle.seek(0)
            first = handle.read(1)
            handle.seek(0)
            handle.write(b"[" if first != b"[" else b"{")
        self.assert_fails("E_LINEAGE")

    def test_51_premature_terminal_artifacts_are_rejected(self) -> None:
        for relative in (
            CHECKER.WAVE_SUCCESS_RECEIPT_PATH,
            CHECKER.WAVE_FAILURE_RECEIPT_PATH,
            CHECKER.WAVE_MANIFEST_PATH,
        ):
            with self.subTest(relative=relative):
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("{}\n", encoding="utf-8")
                self.assert_fails("E_PREPARATION_STATE")
                target.unlink()

    def test_52_premature_claim_and_final_directory_are_rejected(self) -> None:
        claim = self.root / CHECKER.WAVE_CLAIM_PATH
        claim.parent.mkdir(parents=True, exist_ok=True)
        claim.write_text("claimed\n", encoding="utf-8")
        self.assert_fails("E_PREPARATION_STATE")
        claim.unlink()

        final_directory = self.root / CHECKER.WAVE_FINAL_DIRECTORY_PATH
        final_directory.mkdir(parents=True, exist_ok=True)
        self.assert_fails("E_PREPARATION_STATE")

    def test_53_premature_staging_prefix_is_rejected(self) -> None:
        staging = (
            self.root
            / CHECKER.WAVE_STAGING_PARENT_PATH
            / f"{CHECKER.WAVE_STAGING_NAME_PREFIX}fixture"
        )
        staging.mkdir(parents=True)
        self.assert_fails("E_PREPARATION_STATE")

    def test_54_late_execution_artifact_is_rejected(self) -> None:
        receipt = self.root / CHECKER.WAVE_SUCCESS_RECEIPT_PATH

        def hook(_snapshots) -> None:
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text("{}\n", encoding="utf-8")

        self.assert_fails("E_TOCTOU", hook=hook)

    def test_55_module_h1_canonicalization_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["receiptContract"]["moduleZipH1Canonicalization"].__setitem__(
                "directoryEntryRule", "include_empty_directory_rows"
            )
        )
        self.assert_fails("E_RECEIPT")

    def test_56_source_set_digest_canonicalization_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["receiptContract"][
                "orderedSourceSetDigestCanonicalization"
            ].__setitem__("sourceOrder", "module_lexical_order")
        )
        self.assert_fails("E_RECEIPT")


if __name__ == "__main__":
    unittest.main()
