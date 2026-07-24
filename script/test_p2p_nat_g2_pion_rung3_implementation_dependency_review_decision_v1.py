#!/usr/bin/env python3
"""Mutation tests for the G2 dependency-review selection checker."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG3 = f"{BASE}/rung-three"
CHECKER = (
    "script/"
    "check_p2p_nat_g2_pion_rung3_implementation_dependency_review_decision_v1.py"
)
DECISION = f"{RUNG3}/implementation-or-dependency-review-decision-v1.json"
DECISION_DIR = f"{RUNG3}/implementation-or-dependency-review-decision-v1"
PLAN = f"{DECISION_DIR}/implementation/staged-fixed-point-source-closure.md"
PREDECESSOR = f"{RUNG3}/patch-and-dependency-closure-decision-v1.json"
PREDECESSOR_CHECKER = (
    "script/check_p2p_nat_g2_pion_rung3_patch_dependency_decision_v1.py"
)
PREDECESSOR_TESTS = (
    "script/test_p2p_nat_g2_pion_rung3_patch_dependency_decision_v1.py"
)
PORTFOLIO = f"{RUNG3}/patch-and-dependency-closure-decision-v1"
CLASSIFICATIONS = f"{RUNG3}/semantic-source-review-classifications-v1.json"
RESULT = f"{RUNG3}/semantic-source-review-result-v1.json"
MANIFEST = f"{RUNG3}/semantic-source-review-manifest-v1.json"
ARCHIVE = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
FILES = (
    CHECKER,
    DECISION,
    PREDECESSOR,
    PREDECESSOR_CHECKER,
    PREDECESSOR_TESTS,
    CLASSIFICATIONS,
    RESULT,
    MANIFEST,
    ARCHIVE,
)
SUCCESS_MARKER = "G2 Pion dependency-review selection verified"


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


class DecisionCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="g2-pion-dependency-selection-")
        self.root = Path(self.temp.name)
        for relative in FILES:
            source = ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        shutil.copytree(ROOT / PORTFOLIO, self.root / PORTFOLIO)
        shutil.copytree(ROOT / DECISION_DIR, self.root / DECISION_DIR)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_checker(self, isolated: bool = True) -> subprocess.CompletedProcess[str]:
        command = [sys.executable]
        if isolated:
            command.extend(["-I", "-B", "-S"])
        command.append(str(self.root / CHECKER))
        return subprocess.run(
            command,
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
            env={"PATH": os.environ.get("PATH", "")},
        )

    def assert_rejected(
        self,
        result: subprocess.CompletedProcess[str],
        error_code: str,
    ) -> None:
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertNotIn(SUCCESS_MARKER, result.stdout)
        self.assertIn(error_code, output)

    def repin_checker_raw(self, constant_name: str, digest: str) -> None:
        path = self.root / CHECKER
        source = path.read_text(encoding="utf-8")
        pattern = rf'({re.escape(constant_name)}: ")[0-9a-f]{{64}}(")'
        changed, count = re.subn(pattern, rf"\g<1>{digest}\g<2>", source, count=1)
        self.assertEqual(count, 1, f"raw pin not found for {constant_name}")
        path.write_text(changed, encoding="utf-8")

    def write_decision(
        self,
        document: dict,
        *,
        update_self_binding: bool = True,
        repin_raw: bool = True,
    ) -> None:
        if update_self_binding:
            body = dict(document)
            body.pop("contentBinding", None)
            document["contentBinding"]["sha256"] = hashlib.sha256(
                canonical_bytes(body)
            ).hexdigest()
        data = (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode()
        (self.root / DECISION).write_bytes(data)
        if repin_raw:
            self.repin_checker_raw("DECISION_PATH", hashlib.sha256(data).hexdigest())

    def mutate_decision(self, mutation) -> None:
        path = self.root / DECISION
        document = json.loads(path.read_text(encoding="utf-8"))
        mutation(document)
        self.write_decision(document)

    def mutate_bound_predecessor(
        self,
        relative: str,
        raw_constant: str,
        decision_binding_key: str,
        mutation,
    ) -> None:
        path = self.root / relative
        document = json.loads(path.read_text(encoding="utf-8"))
        mutation(document)
        body = dict(document)
        body.pop("contentBinding", None)
        document["contentBinding"]["sha256"] = hashlib.sha256(
            canonical_bytes(body)
        ).hexdigest()
        data = (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode()
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        self.repin_checker_raw(raw_constant, digest)

        decision_path = self.root / DECISION
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["predecessorBinding"][decision_binding_key] = digest
        self.write_decision(decision)

    def rebind_plan_and_decision(self) -> None:
        plan_bytes = (self.root / PLAN).read_bytes()
        decision_path = self.root / DECISION
        document = json.loads(decision_path.read_text(encoding="utf-8"))
        document["implementationPlanBinding"]["byteSize"] = len(plan_bytes)
        document["implementationPlanBinding"]["rawSha256"] = hashlib.sha256(
            plan_bytes
        ).hexdigest()
        self.write_decision(document)

        checker_path = self.root / CHECKER
        source = checker_path.read_text(encoding="utf-8")
        plan_digest = hashlib.sha256(plan_bytes).hexdigest()
        pattern = r'(PLAN_PATH: ")[0-9a-f]{64}(")'
        source, count = re.subn(
            pattern,
            rf"\g<1>{plan_digest}\g<2>",
            source,
            count=1,
        )
        self.assertEqual(count, 1)
        source, count = re.subn(
            r'("byteSize": )[0-9_]+(,)',
            rf"\g<1>{len(plan_bytes)}\g<2>",
            source,
            count=1,
        )
        self.assertEqual(count, 1)
        checker_path.write_text(source, encoding="utf-8")

    def test_01_baseline_passes(self) -> None:
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(SUCCESS_MARKER, result.stdout)

    def test_02_nonisolated_interpreter_is_rejected_at_runtime_layer(self) -> None:
        self.assert_rejected(self.run_checker(isolated=False), "E_RUNTIME")

    def test_03_unrebound_decision_byte_drift_is_rejected_at_raw_layer(self) -> None:
        path = self.root / DECISION
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected(self.run_checker(), "E_RAW_DRIFT")

    def test_04_duplicate_json_key_reaches_json_layer(self) -> None:
        path = self.root / DECISION
        text = path.read_text(encoding="utf-8").replace(
            '"schemaVersion": "1.0",',
            '"schemaVersion": "1.0",\n  "schemaVersion": "1.0",',
            1,
        )
        data = text.encode()
        path.write_bytes(data)
        self.repin_checker_raw("DECISION_PATH", hashlib.sha256(data).hexdigest())
        self.assert_rejected(self.run_checker(), "E_JSON")

    def test_05_second_portfolio_option_selection_reaches_selection_layer(self) -> None:
        self.mutate_decision(
            lambda document: document["portfolioSelections"][1].__setitem__(
                "selected", True
            )
        )
        self.assert_rejected(self.run_checker(), "E_SELECTION")

    def test_06_root_treatment_selection_reaches_selection_layer(self) -> None:
        self.mutate_decision(
            lambda document: document["treatmentUnitSelections"][0].__setitem__(
                "selected", True
            )
        )
        self.assert_rejected(self.run_checker(), "E_SELECTION")

    def test_07_selected_portfolio_option_omission_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["selection"][
                "selectedPortfolioOptionIds"
            ].clear()
        )
        self.assert_rejected(self.run_checker(), "E_SELECTION")

    def test_08_selected_treatment_duplication_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["selection"][
                "selectedTreatmentUnitIds"
            ].append("dependency_source_license_security_closure_review")
        )
        self.assert_rejected(self.run_checker(), "E_SELECTION")

    def test_09_authority_escalation_reaches_authority_layer(self) -> None:
        self.mutate_decision(
            lambda document: document["authority"].__setitem__(
                "networkAuthorized", True
            )
        )
        self.assert_rejected(self.run_checker(), "E_AUTHORITY")

    def test_10_boolean_to_integer_authority_drift_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["authority"].__setitem__(
                "networkAuthorized", 0
            )
        )
        self.assert_rejected(self.run_checker(), "E_AUTHORITY")

    def test_11_unknown_nested_authority_claim_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["authority"].__setitem__(
                "ambientCredentialAuthorized", False
            )
        )
        self.assert_rejected(self.run_checker(), "E_AUTHORITY")

    def test_12_closure_overclaim_reaches_closure_layer(self) -> None:
        self.mutate_decision(
            lambda document: document["closure"].__setitem__(
                "dependencyClosureComplete", True
            )
        )
        self.assert_rejected(self.run_checker(), "E_CLOSURE")

    def test_13_closed_finding_count_reaches_finding_layer(self) -> None:
        self.mutate_decision(
            lambda document: document["findingBoundary"].__setitem__(
                "findingsClosedBySelection", 1
            )
        )
        self.assert_rejected(self.run_checker(), "E_FINDINGS")

    def test_14_missing_finding_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["findingBoundary"]["findings"].pop()
        )
        self.assert_rejected(self.run_checker(), "E_FINDINGS")

    def test_15_finding_disposition_drift_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["findingBoundary"]["findings"][0].__setitem__(
                "finalDisposition", "closed"
            )
        )
        self.assert_rejected(self.run_checker(), "E_FINDINGS")

    def test_16_sequence_execution_advance_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["sequence"][3].__setitem__("prepared", True)
        )
        self.assert_rejected(self.run_checker(), "E_SEQUENCE")

    def test_17_next_action_drift_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document.__setitem__(
                "nextAction", "acquire_dependencies_now"
            )
        )
        self.assert_rejected(self.run_checker(), "E_DECISION")

    def test_18_contract_overclaim_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["dependencyReviewContract"].__setitem__(
                "acquisitionBoundsFrozenByThisDecision", True
            )
        )
        self.assert_rejected(self.run_checker(), "E_CONTRACT")

    def test_19_predecessor_byte_drift_is_rejected_at_raw_layer(self) -> None:
        for relative in (
            PREDECESSOR,
            PREDECESSOR_CHECKER,
            PREDECESSOR_TESTS,
        ):
            with self.subTest(relative=relative):
                for bound in (
                    PREDECESSOR,
                    PREDECESSOR_CHECKER,
                    PREDECESSOR_TESTS,
                ):
                    shutil.copy2(ROOT / bound, self.root / bound)
                path = self.root / relative
                path.write_bytes(path.read_bytes() + b" ")
                self.assert_rejected(self.run_checker(), "E_RAW_DRIFT")

    def test_20_portfolio_byte_drift_is_rejected_at_bundle_layer(self) -> None:
        path = self.root / PORTFOLIO / "proposals" / "bounded-resource-lifecycle.md"
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected(self.run_checker(), "E_PORTFOLIO")

    def test_21_archive_byte_drift_is_rejected_at_raw_layer(self) -> None:
        path = self.root / ARCHIVE
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(bytes(data))
        self.assert_rejected(self.run_checker(), "E_RAW_DRIFT")

    def test_22_unrebound_plan_byte_drift_is_rejected_at_raw_layer(self) -> None:
        path = self.root / PLAN
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected(self.run_checker(), "E_RAW_DRIFT")

    def test_23_rebound_plan_contradiction_reaches_semantic_layer(self) -> None:
        for claim in (
            "Dependency acquisition is authorized for the next action.",
            "Dependency acquisition has been authorized.",
            "Dependency acquisition authority is granted.",
            "Dependency acquisition is now approved.",
            "We authorize dependency acquisition.",
            "Proceed with dependency acquisition.",
            "Network access is enabled.",
            "Git writes are approved.",
            "The 19 canonical findings are resolved.",
            "Candidate selection is complete.",
            "Library selection is complete.",
            "External authentication.",
            "User action.",
            "External authentication or user action.",
        ):
            with self.subTest(claim=claim):
                shutil.copy2(ROOT / PLAN, self.root / PLAN)
                shutil.copy2(ROOT / DECISION, self.root / DECISION)
                shutil.copy2(ROOT / CHECKER, self.root / CHECKER)
                path = self.root / PLAN
                path.write_text(
                    path.read_text(encoding="utf-8") + f"\n{claim}\n",
                    encoding="utf-8",
                )
                self.rebind_plan_and_decision()
                self.assert_rejected(self.run_checker(), "E_PLAN_SEMANTICS")

    def test_24_rebound_plan_summary_drift_reaches_semantic_layer(self) -> None:
        path = self.root / PLAN
        text = path.read_text(encoding="utf-8").replace(
            "selectedPortfolioOptionCount=1",
            "selectedPortfolioOptionCount=2",
            1,
        )
        path.write_text(text, encoding="utf-8")
        self.rebind_plan_and_decision()
        self.assert_rejected(self.run_checker(), "E_PLAN_SEMANTICS")

    def test_25_plan_binding_path_drift_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["implementationPlanBinding"].__setitem__(
                "path", "other-plan.md"
            )
        )
        self.assert_rejected(self.run_checker(), "E_PLAN_BINDING")

    def test_26_decision_symlink_is_rejected_by_inventory(self) -> None:
        path = self.root / DECISION
        real = path.with_name("decision-real.json")
        path.rename(real)
        path.symlink_to(real.name)
        self.assert_rejected(self.run_checker(), "E_INVENTORY")

    def test_27_plan_symlink_is_rejected_by_inventory(self) -> None:
        path = self.root / PLAN
        real = path.with_name("plan-real.md")
        path.rename(real)
        path.symlink_to(real.name)
        self.assert_rejected(self.run_checker(), "E_INVENTORY")

    def test_28_unexpected_file_and_prefixed_sibling_are_rejected(self) -> None:
        unexpected = self.root / DECISION_DIR / "network-authority.json"
        unexpected.write_text(
            "{}\n", encoding="utf-8"
        )
        self.assert_rejected(self.run_checker(), "E_INVENTORY")
        unexpected.unlink()

        prefixed_sibling = (
            self.root
            / RUNG3
            / "implementation-or-dependency-review-decision-v1-network-authority.json"
        )
        prefixed_sibling.write_text(
            '{"networkAuthorized":true}\n',
            encoding="utf-8",
        )
        self.assert_rejected(self.run_checker(), "E_INVENTORY")

    def test_29_unexpected_directory_is_rejected_by_inventory(self) -> None:
        (self.root / DECISION_DIR / "source").mkdir()
        self.assert_rejected(self.run_checker(), "E_INVENTORY")

    def test_30_fifo_is_rejected_by_inventory(self) -> None:
        os.mkfifo(self.root / DECISION_DIR / "credential-pipe")
        self.assert_rejected(self.run_checker(), "E_INVENTORY")

    def test_31_hardlinked_plan_is_rejected_by_inventory(self) -> None:
        plan = self.root / PLAN
        outside = self.root / "hardlink-plan-target.md"
        plan.rename(outside)
        os.link(outside, plan)
        self.assert_rejected(self.run_checker(), "E_INVENTORY")

    def test_32_replace_after_read_is_rejected_at_toctou_layer(self) -> None:
        checker_path = self.root / CHECKER
        source = checker_path.read_text(encoding="utf-8")
        needle = """        for path, maximum_bytes in limits.items():
            snapshots.append(secure_read(path, maximum_bytes))
"""
        replacement = needle + """            if path == DECISION_PATH:
                import time
                time.sleep(0.25)
"""
        self.assertIn(needle, source)
        checker_path.write_text(
            source.replace(needle, replacement, 1),
            encoding="utf-8",
        )
        command = [
            sys.executable,
            "-I",
            "-B",
            "-S",
            str(checker_path),
        ]
        process = subprocess.Popen(
            command,
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"PATH": os.environ.get("PATH", "")},
        )
        try:
            time.sleep(0.08)
            path = self.root / DECISION
            replacement_path = path.with_name("replacement-decision.json")
            shutil.copy2(path, replacement_path)
            os.replace(replacement_path, path)
            stdout, stderr = process.communicate(timeout=20)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        self.assert_rejected(result, "E_TOCTOU")

    def test_33_unknown_or_rebound_predecessor_claim_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document.__setitem__(
                "authenticationAndNetworkAuthorized", False
            )
        )
        self.assert_rejected(self.run_checker(), "E_SCHEMA")

        shutil.copy2(ROOT / DECISION, self.root / DECISION)
        shutil.copy2(ROOT / CHECKER, self.root / CHECKER)
        self.mutate_bound_predecessor(
            RESULT,
            "RESULT_PATH",
            "resultRawSha256",
            lambda document: document.__setitem__("networkAuthorized", True),
        )
        self.assert_rejected(self.run_checker(), "E_PREDECESSOR_SCHEMA")

        cases = (
            (
                RESULT,
                "RESULT_PATH",
                "resultRawSha256",
                "semantic review false",
                lambda document: document["coverage"].__setitem__(
                    "semanticSourceReviewPerformed", False
                ),
            ),
            (
                RESULT,
                "RESULT_PATH",
                "resultRawSha256",
                "semantic review bool-to-int",
                lambda document: document["coverage"].__setitem__(
                    "semanticSourceReviewPerformed", 1
                ),
            ),
            (
                RESULT,
                "RESULT_PATH",
                "resultRawSha256",
                "result nested authority",
                lambda document: document["coverage"].__setitem__(
                    "networkAuthorized", True
                ),
            ),
            (
                MANIFEST,
                "MANIFEST_PATH",
                "manifestRawSha256",
                "overwrite enabled",
                lambda document: document[
                    "transactionalPublicationBoundary"
                ].__setitem__("overwriteAllowed", True),
            ),
            (
                MANIFEST,
                "MANIFEST_PATH",
                "manifestRawSha256",
                "overwrite bool-to-int",
                lambda document: document[
                    "transactionalPublicationBoundary"
                ].__setitem__("overwriteAllowed", 0),
            ),
            (
                MANIFEST,
                "MANIFEST_PATH",
                "manifestRawSha256",
                "final artifact deletion enabled",
                lambda document: document[
                    "transactionalPublicationBoundary"
                ].__setitem__("finalArtifactDeletionAllowed", True),
            ),
            (
                MANIFEST,
                "MANIFEST_PATH",
                "manifestRawSha256",
                "manifest nested authority",
                lambda document: document[
                    "transactionalPublicationBoundary"
                ].__setitem__("networkAuthorized", True),
            ),
        )
        for relative, raw_constant, binding_key, label, mutation in cases:
            with self.subTest(label=label):
                for bound in (CHECKER, DECISION, RESULT, MANIFEST):
                    shutil.copy2(ROOT / bound, self.root / bound)
                self.mutate_bound_predecessor(
                    relative,
                    raw_constant,
                    binding_key,
                    mutation,
                )
                self.assert_rejected(self.run_checker(), "E_PREDECESSOR")

    def test_34_missing_nested_authority_key_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["authority"].pop("networkAuthorized")
        )
        self.assert_rejected(self.run_checker(), "E_AUTHORITY")

    def test_35_stale_self_binding_and_scope_swap_are_rejected(self) -> None:
        path = self.root / DECISION
        document = json.loads(path.read_text(encoding="utf-8"))
        document["status"] = "changed"
        self.write_decision(document, update_self_binding=False, repin_raw=True)
        self.assert_rejected(self.run_checker(), "E_BINDING")

        shutil.copy2(ROOT / DECISION, path)
        shutil.copy2(ROOT / CHECKER, self.root / CHECKER)
        self.mutate_decision(
            lambda current: current["contentBinding"].__setitem__(
                "scope", "result_without_contentBinding"
            )
        )
        self.assert_rejected(self.run_checker(), "E_BINDING")

    def test_36_boolean_to_integer_selection_drift_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["selection"].__setitem__(
                "dependencyReviewSelected", 1
            )
        )
        self.assert_rejected(self.run_checker(), "E_SELECTION")


if __name__ == "__main__":
    unittest.main(verbosity=2)
