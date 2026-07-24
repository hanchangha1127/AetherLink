#!/usr/bin/env python3
"""Mutation tests for the preparation-only G2 wave2 decision checker."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    ROOT
    / "script/check_p2p_nat_g2_pion_rung3_dependency_wave2_decision_v1.py"
)
SPEC = importlib.util.spec_from_file_location("wave2_decision_checker", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)


class DependencyWaveTwoDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.pristine = Path(cls.temp.name) / "pristine"
        cls.pristine.mkdir()
        permit = json.loads((ROOT / CHECKER.REVIEW_PERMIT_PATH).read_text())
        required = {
            CHECKER.DECISION_PATH,
            CHECKER.READER_PATH,
            *(binding["path"] for binding in CHECKER.BINDING_INPUTS),
            *(
                edge["modPath"]
                for tuple_row in CHECKER.TUPLE_INPUTS
                for edge in tuple_row["parents"]
            ),
            permit["inputBindings"]["rootArchive"]["path"],
            *(
                resource["path"]
                for resource in permit["inputBindings"]["resources"]
                if resource["kind"] == "zip"
            ),
        }
        cls.required = tuple(sorted(required))
        for relative in cls.required:
            source = ROOT / relative
            target = cls.pristine / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def setUp(self) -> None:
        self.case = tempfile.TemporaryDirectory()
        self.root = Path(self.case.name) / "repo"
        shutil.copytree(self.pristine, self.root)

    def tearDown(self) -> None:
        self.case.cleanup()

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
        document = self.load_decision()
        callback(document)
        self.write_decision(document)

    def assert_fails(
        self,
        code: str | None = None,
        *,
        preflight: bool = False,
        hook=None,
    ) -> None:
        with self.assertRaises(CHECKER.CheckError) as captured:
            CHECKER.check(
                self.root,
                require_namespace_preflight=preflight,
                before_final_barrier=hook,
            )
        if code is not None:
            self.assertEqual(captured.exception.code, code)

    def test_01_baseline(self) -> None:
        result = CHECKER.check(self.root)
        self.assertEqual(result["tupleCount"], 15)
        self.assertEqual(result["resourceCount"], 30)
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])
        self.assertFalse(result["acquisitionAuthorized"])

    def test_02_empty_namespace_preflight(self) -> None:
        result = CHECKER.check(self.root, require_namespace_preflight=True)
        self.assertTrue(result["namespacePreflightChecked"])

    def test_03_duplicate_json_key_is_rejected(self) -> None:
        raw = self.decision_path.read_text(encoding="utf-8")
        raw = raw.replace(
            '  "schemaVersion": "1.0",',
            '  "schemaVersion": "1.0",\n  "schemaVersion": "1.0",',
            1,
        )
        self.decision_path.write_text(raw, encoding="utf-8")
        self.assert_fails("E_JSON")

    def test_04_non_finite_json_is_rejected(self) -> None:
        raw = self.decision_path.read_text(encoding="utf-8")
        raw = raw.replace('"requestCount": 30', '"requestCount": NaN', 1)
        self.decision_path.write_text(raw, encoding="utf-8")
        self.assert_fails("E_JSON")

    def test_05_unknown_top_level_key_is_rejected(self) -> None:
        self.mutate(lambda d: d.__setitem__("unexpected", False))
        self.assert_fails("E_DECISION")

    def test_06_content_binding_drift_is_rejected(self) -> None:
        document = self.load_decision()
        document["contentBinding"]["sha256"] = "0" * 64
        self.write_decision(document, rebind=False)
        self.assert_fails("E_DECISION")

    def test_07_predecessor_byte_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.READBACK_MANIFEST_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_fails("E_LINEAGE")

    def test_08_graph_digest_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["graphBinding"].__setitem__("graphSha256", "0" * 64)
        )
        self.assert_fails("E_DECISION")

    def test_09_tuple_version_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][0].__setitem__("version", "v0.2.0")
        )
        self.assert_fails("E_DECISION")

    def test_10_tuple_reordering_is_rejected(self) -> None:
        def change(document: dict) -> None:
            rows = document["wave"]["tuples"]
            rows[0], rows[1] = rows[1], rows[0]

        self.mutate(change)
        self.assert_fails("E_DECISION")

    def test_11_version_specific_tuple_deduplication_is_rejected(self) -> None:
        self.mutate(lambda d: d["wave"]["tuples"].pop(7))
        self.assert_fails("E_DECISION")

    def test_12_selected_flag_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][1].__setitem__(
                "selectedByGraphAlgorithm", True
            )
        )
        self.assert_fails("E_DECISION")

    def test_13_tuple_digest_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][2].__setitem__(
                "tupleDigestSha256", "0" * 64
            )
        )
        self.assert_fails("E_DECISION")

    def test_14_h1_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][3]["resources"][1].__setitem__(
                "expectedH1",
                "h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            )
        )
        self.assert_fails("E_DECISION")

    def test_15_checksum_evidence_source_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][4]["checksumEvidence"].__setitem__(
                "goSumMember", "different/go.sum"
            )
        )
        self.assert_fails("E_DECISION")

    def test_16_resource_order_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][5]["resources"][0].__setitem__(
                "order", 99
            )
        )
        self.assert_fails("E_DECISION")

    def test_17_query_bearing_url_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][6]["resources"][1].__setitem__(
                "url",
                d["wave"]["tuples"][6]["resources"][1]["url"] + "?token=1",
            )
        )
        self.assert_fails("E_DECISION")

    def test_18_wave1_output_path_reuse_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"]["tuples"][7]["resources"][0].__setitem__(
                "outputPath",
                (
                    "build/offline-source/pion-ice-v4.3.0/dependencies/"
                    "wave-1-v3/accepted/reused.mod"
                ),
            )
        )
        self.assert_fails("E_DECISION")

    def test_19_authentication_requirement_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["authority"].__setitem__(
                "externalAuthenticationRequired", True
            )
        )
        self.assert_fails("E_DECISION")

    def test_20_execution_counter_drift_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["execution"].__setitem__("requestCount", 1)
        )
        self.assert_fails("E_DECISION")

    def test_21_bool_in_integer_field_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["wave"].__setitem__("requestCount", True)
        )
        self.assert_fails("E_DECISION")

    def test_22_fixed_point_promotion_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["closure"].__setitem__(
                "dependencyFixedPointReached", True
            )
        )
        self.assert_fails("E_DECISION")

    def test_23_nonclaim_removal_is_rejected(self) -> None:
        self.mutate(lambda d: d["nonClaims"].pop())
        self.assert_fails("E_DECISION")

    def test_24_reader_byte_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.READER_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_fails("E_READER")

    def test_25_parent_mod_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.TUPLE_INPUTS[0]["parents"][0]["modPath"]
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_fails("E_PARENT")

    def test_26_checksum_archive_drift_is_rejected(self) -> None:
        path = self.root / CHECKER.TUPLE_INPUTS[0]["checksum"]["archivePath"]
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_fails("E_CHECKSUM")

    def test_27_claim_namespace_collision_is_rejected(self) -> None:
        path = self.root / CHECKER.WAVE2_CLAIM_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("occupied\n", encoding="utf-8")
        self.assert_fails("E_NAMESPACE", preflight=True)

    def test_28_staging_namespace_collision_is_rejected(self) -> None:
        path = (
            self.root
            / CHECKER.DEPENDENCY_ROOT
            / f"{CHECKER.WAVE2_STAGING_PREFIX}occupied"
        )
        path.mkdir()
        self.assert_fails("E_NAMESPACE", preflight=True)

    def test_29_foreign_child_in_wave_namespace_is_rejected(self) -> None:
        path = self.root / CHECKER.WAVE2_PARENT_PATH / "foreign"
        path.mkdir(parents=True)
        self.assert_fails("E_NAMESPACE", preflight=True)

    def test_30_namespace_final_barrier_detects_collision(self) -> None:
        def hook(_snapshots) -> None:
            path = self.root / CHECKER.WAVE2_PARENT_PATH / "foreign"
            path.mkdir(parents=True)

        self.assert_fails("E_NAMESPACE", preflight=True, hook=hook)

    def test_31_user_action_escalation_is_rejected(self) -> None:
        self.mutate(
            lambda d: d["authority"].__setitem__("userActionRequired", True)
        )
        self.assert_fails("E_DECISION")

    def test_32_symlink_decision_is_rejected(self) -> None:
        target = self.root / "decision-copy.json"
        shutil.copy2(self.decision_path, target)
        self.decision_path.unlink()
        self.decision_path.symlink_to(target)
        self.assert_fails("E_FILESYSTEM")

    def test_33_hardlinked_reader_is_rejected(self) -> None:
        source = self.root / CHECKER.READER_PATH
        duplicate = self.root / "reader-hardlink.md"
        os.link(source, duplicate)
        self.assert_fails("E_FILESYSTEM")

    def test_34_final_barrier_detects_mutation(self) -> None:
        def hook(_snapshots) -> None:
            path = self.root / CHECKER.READER_PATH
            path.write_bytes(path.read_bytes() + b" ")

        self.assert_fails("E_TOCTOU", hook=hook)

    def test_35_exact_resource_expansion_and_uniqueness(self) -> None:
        decision = self.load_decision()
        tuples = decision["wave"]["tuples"]
        resources = [resource for row in tuples for resource in row["resources"]]
        self.assertEqual(len(tuples), 15)
        self.assertEqual(len(resources), 30)
        self.assertEqual([r["order"] for r in resources], list(range(1, 31)))
        self.assertEqual(len({r["url"] for r in resources}), 30)
        self.assertEqual(len({r["outputPath"] for r in resources}), 30)
        self.assertTrue(all(r["expectedH1"].startswith("h1:") for r in resources))
        self.assertTrue(
            all(
                [r["kind"] for r in row["resources"]] == ["mod", "zip"]
                for row in tuples
            )
        )

    def test_36_same_module_versions_remain_distinct(self) -> None:
        tuples = self.load_decision()["wave"]["tuples"]
        by_module: dict[str, set[str]] = {}
        for row in tuples:
            by_module.setdefault(row["module"], set()).add(row["version"])
        self.assertEqual(
            by_module["golang.org/x/net"],
            {"v0.34.0", "v0.35.0"},
        )
        self.assertEqual(
            by_module["golang.org/x/sys"],
            {"v0.30.0", "v0.40.0"},
        )
        self.assertEqual(
            by_module["golang.org/x/term"],
            {"v0.39.0", "v0.40.0"},
        )
        self.assertEqual(
            by_module["golang.org/x/text"],
            {"v0.33.0", "v0.34.0"},
        )

    def test_37_checker_has_no_network_or_process_imports(self) -> None:
        tree = ast.parse(CHECKER_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported.isdisjoint(
                {
                    "http",
                    "requests",
                    "socket",
                    "subprocess",
                    "urllib",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
