#!/usr/bin/env python3
"""Mutation tests for the G2 Pion patch/dependency decision checker."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import re


ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG3 = f"{BASE}/rung-three"
CHECKER = "script/check_p2p_nat_g2_pion_rung3_patch_dependency_decision_v1.py"
DECISION = f"{RUNG3}/patch-and-dependency-closure-decision-v1.json"
CLASSIFICATIONS = f"{RUNG3}/semantic-source-review-classifications-v1.json"
RESULT = f"{RUNG3}/semantic-source-review-result-v1.json"
MANIFEST = f"{RUNG3}/semantic-source-review-manifest-v1.json"
ANALYSIS = f"{RUNG3}/patch-and-dependency-closure-decision-v1/hardening.json"
PORTFOLIO = f"{RUNG3}/patch-and-dependency-closure-decision-v1"
ARCHIVE = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
FILES = (CHECKER, DECISION, CLASSIFICATIONS, RESULT, MANIFEST, ARCHIVE)
SUCCESS_MARKER = "G2 Pion patch/dependency decision preparation verified"


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


class DecisionCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="g2-pion-patch-decision-")
        self.root = Path(self.temp.name)
        for relative in FILES:
            source = ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        shutil.copytree(ROOT / PORTFOLIO, self.root / PORTFOLIO)

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
            timeout=15,
            env={"PATH": os.environ.get("PATH", "")},
        )

    def assert_rejected(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(SUCCESS_MARKER, result.stdout)

    def mutate_decision(self, mutation) -> None:
        path = self.root / DECISION
        document = json.loads(path.read_text(encoding="utf-8"))
        mutation(document)
        body = dict(document)
        body.pop("contentBinding", None)
        document["contentBinding"]["sha256"] = hashlib.sha256(
            canonical_bytes(body)
        ).hexdigest()
        data = (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode()
        path.write_bytes(data)
        checker_path = self.root / CHECKER
        checker_source = checker_path.read_text(encoding="utf-8")
        checker_source, count = re.subn(
            r'(DECISION_PATH: ")[0-9a-f]{64}(")',
            rf"\g<1>{hashlib.sha256(data).hexdigest()}\g<2>",
            checker_source,
            count=1,
        )
        self.assertEqual(count, 1)
        checker_path.write_text(checker_source, encoding="utf-8")

    def mutate_analysis(self, mutation) -> None:
        path = self.root / ANALYSIS
        original = path.read_bytes()
        document = json.loads(original.decode("utf-8"))
        mutation(document)
        changed = (
            json.dumps(document, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")
        path.write_bytes(changed)
        original_digest = hashlib.sha256(original).hexdigest()
        changed_digest = hashlib.sha256(changed).hexdigest()

        checker_path = self.root / CHECKER
        checker_source = checker_path.read_text(encoding="utf-8")
        checker_source, count = re.subn(
            r'(ANALYSIS_PATH: ")[0-9a-f]{64}(")',
            rf"\g<1>{changed_digest}\g<2>",
            checker_source,
            count=1,
        )
        self.assertEqual(count, 1)
        old_entry = (
            f"    (ANALYSIS_PATH, {len(original):_},\n"
            f'     "{original_digest}")'
        )
        new_entry = (
            f"    (ANALYSIS_PATH, {len(changed):_},\n"
            f'     "{changed_digest}")'
        )
        self.assertIn(old_entry, checker_source)
        checker_path.write_text(
            checker_source.replace(old_entry, new_entry, 1),
            encoding="utf-8",
        )
        self.mutate_decision(
            lambda decision: decision["analysisBinding"].__setitem__(
                "rawSha256", changed_digest
            )
        )

    def write_bound_portfolio_file(self, relative: str, changed: bytes) -> None:
        original = (ROOT / relative).read_bytes()
        path = self.root / relative
        path.write_bytes(changed)
        checker_path = self.root / CHECKER
        checker_source = checker_path.read_text(encoding="utf-8")
        portfolio_suffix = relative[len(PORTFOLIO) + 1:]
        manifest_path = f'f"{{ANALYSIS_DIR}}/{portfolio_suffix}"'
        old_entry = (
            f"    ({manifest_path}, {len(original):_},\n"
            f'     "{hashlib.sha256(original).hexdigest()}")'
        )
        new_entry = (
            f"    ({manifest_path}, {len(changed):_},\n"
            f'     "{hashlib.sha256(changed).hexdigest()}")'
        )
        self.assertIn(old_entry, checker_source)
        checker_path.write_text(
            checker_source.replace(old_entry, new_entry, 1),
            encoding="utf-8",
        )

    def test_01_baseline_passes(self) -> None:
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(SUCCESS_MARKER, result.stdout)

    def test_02_nonisolated_interpreter_is_rejected(self) -> None:
        self.assert_rejected(self.run_checker(isolated=False))

    def test_03_decision_self_binding_mutation_is_rejected(self) -> None:
        path = self.root / DECISION
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("prepared_options_unselected", "changed_unselected", 1),
                        encoding="utf-8")
        self.assert_rejected(self.run_checker())

    def test_04_duplicate_json_key_is_rejected(self) -> None:
        path = self.root / DECISION
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            '"schemaVersion": "1.0",',
            '"schemaVersion": "1.0",\n  "schemaVersion": "1.0",',
            1,
        )
        path.write_text(text, encoding="utf-8")
        self.assert_rejected(self.run_checker())

    def test_05_selected_option_is_rejected_even_when_rebound(self) -> None:
        def mutation(document: dict) -> None:
            document["options"][0]["selected"] = True
            document["selection"]["anyOptionSelected"] = True
            document["selection"]["selectedOptionIds"] = [
                document["options"][0]["optionId"]
            ]

        self.mutate_decision(mutation)
        self.assert_rejected(self.run_checker())

    def test_06_authority_escalation_is_rejected_even_when_rebound(self) -> None:
        for key, value in (
            ("dependencyAcquisitionAuthorized", True),
            ("networkAuthorized", 0),
        ):
            with self.subTest(key=key, value=value):
                shutil.copy2(ROOT / DECISION, self.root / DECISION)
                shutil.copy2(ROOT / CHECKER, self.root / CHECKER)
                self.mutate_decision(
                    lambda document, key=key, value=value: document[
                        "authority"
                    ].__setitem__(key, value)
                )
                self.assert_rejected(self.run_checker())

    def test_07_closure_overclaim_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(
            lambda document: document["closure"].__setitem__(
                "dependencyClosureComplete", True
            )
        )
        self.assert_rejected(self.run_checker())

    def test_08_missing_treatment_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(lambda document: document["treatments"].pop())
        self.assert_rejected(self.run_checker())

    def test_09_treatment_mapping_drift_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(
            lambda document: document["treatments"][0]["patchUnitIds"].clear()
        )
        self.assert_rejected(self.run_checker())

    def test_10_reverse_option_mapping_drift_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(
            lambda document: document["options"][0]["findingIds"].pop()
        )
        self.assert_rejected(self.run_checker())

    def test_11_requirement_tuple_drift_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(
            lambda document: document["dependencySeed"]["requirements"][0].__setitem__(
                "version", "v0.0.0"
            )
        )
        self.assert_rejected(self.run_checker())

    def test_12_checksum_context_selection_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(
            lambda document: document["dependencySeed"][
                "checksumOnlyContextTuples"
            ][0].__setitem__("selected", True)
        )
        self.assert_rejected(self.run_checker())

    def test_13_predecessor_byte_drift_is_rejected(self) -> None:
        path = self.root / CLASSIFICATIONS
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected(self.run_checker())

    def test_14_analysis_byte_drift_is_rejected(self) -> None:
        path = self.root / ANALYSIS
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected(self.run_checker())

        shutil.copy2(ROOT / ANALYSIS, path)
        shutil.copy2(ROOT / DECISION, self.root / DECISION)
        shutil.copy2(ROOT / CHECKER, self.root / CHECKER)
        self.mutate_analysis(
            lambda document: document["opportunities"][0]["options"][0].__setitem__(
                "networkAuthorized", True
            )
        )
        self.assert_rejected(self.run_checker())

    def test_15_archive_byte_drift_is_rejected(self) -> None:
        path = self.root / ARCHIVE
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(bytes(data))
        self.assert_rejected(self.run_checker())

    def test_16_decision_symlink_is_rejected(self) -> None:
        path = self.root / DECISION
        real = path.with_name("decision-real.json")
        path.rename(real)
        path.symlink_to(real.name)
        self.assert_rejected(self.run_checker())

    def test_17_implementation_directory_is_rejected(self) -> None:
        (self.root / RUNG3 / "patch-and-dependency-closure-decision-v1" /
         "implementation").mkdir()
        self.assert_rejected(self.run_checker())

    def test_18_nonclaim_overclaim_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(
            lambda document: document["nonClaims"].__setitem__(
                "productEndpointAuthenticationSatisfied", True
            )
        )
        self.assert_rejected(self.run_checker())

    def test_19_dependency_step_execution_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(
            lambda document: document["dependencyClosureSequence"][1].__setitem__(
                "executed", True
            )
        )
        self.assert_rejected(self.run_checker())

    def test_20_unknown_top_level_claim_is_rejected_even_when_rebound(self) -> None:
        self.mutate_decision(
            lambda document: document.__setitem__(
                "networkGitAuthenticationAndUserActionAuthorized", True
            )
        )
        self.assert_rejected(self.run_checker())

    def test_21_missing_authority_closure_and_nonclaim_keys_are_rejected(self) -> None:
        def mutation(document: dict) -> None:
            document["authority"].pop("networkAuthorized")
            document["closure"].pop("semanticClosureComplete")
            document["nonClaims"].pop("repositoryIdentityProofRequired")

        self.mutate_decision(mutation)
        self.assert_rejected(self.run_checker())

    def test_22_dependency_sequence_claim_drift_is_rejected(self) -> None:
        def mutation(document: dict) -> None:
            step = document["dependencyClosureSequence"][1]
            step["stepId"] = "authenticate_user_and_open_network"
            step["rule"] = "Network and Git authority granted."

        self.mutate_decision(mutation)
        self.assert_rejected(self.run_checker())

    def test_23_archive_binding_path_drift_is_rejected(self) -> None:
        self.mutate_decision(
            lambda document: document["archiveBinding"].__setitem__(
                "path", "attacker-selected.zip"
            )
        )
        self.assert_rejected(self.run_checker())

    def test_24_reader_facing_hardening_mutation_is_rejected(self) -> None:
        cases = (
            (
                f"{PORTFOLIO}/hardening.md",
                "Dependency acquisition has been authorized.",
            ),
            (
                f"{PORTFOLIO}/hardening.md",
                "All 19 findings have been closed.",
            ),
            (
                f"{PORTFOLIO}/context.md",
                "Dependency acquisition has been authorized.",
            ),
            (
                f"{PORTFOLIO}/context.md",
                "All 19 findings have been closed.",
            ),
            (
                f"{PORTFOLIO}/context.md",
                "Network authority has been granted.",
            ),
            (
                f"{PORTFOLIO}/hardening.md",
                "External authentication.",
            ),
            (
                f"{PORTFOLIO}/hardening.md",
                "User action.",
            ),
            (
                f"{PORTFOLIO}/context.md",
                "External authentication or user action.",
            ),
        )
        for relative, claim in cases:
            with self.subTest(relative=relative, claim=claim):
                shutil.copy2(ROOT / CHECKER, self.root / CHECKER)
                shutil.copy2(ROOT / relative, self.root / relative)
                original = (ROOT / relative).read_bytes()
                changed = original + f"\n{claim}\n".encode("utf-8")
                self.write_bound_portfolio_file(relative, changed)
                self.assert_rejected(self.run_checker())

    def test_25_missing_proposal_is_rejected(self) -> None:
        proposal = (
            self.root
            / PORTFOLIO
            / "proposals"
            / "typed-secret-free-diagnostics.md"
        )
        proposal.unlink()
        self.assert_rejected(self.run_checker())

        shutil.copy2(
            ROOT
            / PORTFOLIO
            / "proposals"
            / "typed-secret-free-diagnostics.md",
            proposal,
        )
        os.link(proposal, self.root / "portfolio-hardlink-alias.md")
        self.assert_rejected(self.run_checker())

    def test_26_unexpected_authority_and_source_artifacts_are_rejected(self) -> None:
        base = self.root / PORTFOLIO
        (base / "implementation.md").write_text("implemented\n", encoding="utf-8")
        (base / "network-authority.json").write_text("{}\n", encoding="utf-8")
        (base / "git-authority.json").write_text("{}\n", encoding="utf-8")
        (base / "source").mkdir()
        (base / "source" / "patch.diff").write_text("selected\n", encoding="utf-8")
        self.assert_rejected(self.run_checker())

    def test_27_replace_after_decision_read_is_rejected(self) -> None:
        checker_path = self.root / CHECKER
        checker_source = checker_path.read_text(encoding="utf-8")
        needle = """        for path, maximum_bytes in limits.items():
            snapshots.append(secure_read(path, maximum_bytes))
"""
        replacement = needle + """            if path == DECISION_PATH:
                import time
                time.sleep(0.25)
"""
        self.assertIn(needle, checker_source)
        checker_path.write_text(
            checker_source.replace(needle, replacement, 1),
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
            import time
            time.sleep(0.08)
            path = self.root / DECISION
            document = json.loads(path.read_text(encoding="utf-8"))
            document["selection"]["anyOptionSelected"] = True
            document["selection"]["selectedOptionIds"] = [
                document["options"][0]["optionId"]
            ]
            document["options"][0]["selected"] = True
            body = dict(document)
            body.pop("contentBinding", None)
            document["contentBinding"]["sha256"] = hashlib.sha256(
                canonical_bytes(body)
            ).hexdigest()
            replacement_path = path.with_name("replacement-decision.json")
            replacement_path.write_text(
                json.dumps(document, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            os.replace(replacement_path, path)
            stdout, stderr = process.communicate(timeout=15)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        self.assert_rejected(result)

    def test_28_rehashed_reader_effect_drift_is_rejected_semantically(self) -> None:
        proposal_relative = (
            f"{PORTFOLIO}/proposals/capability-gated-network-boundary.md"
        )
        original = (ROOT / proposal_relative).read_bytes()
        needle = b"**Mitigates** regression risk by preserving the fixed buffers"
        for suffix in (
            b" but actually **Addresses** the finding",
            b" although it **Addresses** the finding",
            b"; however, it **Addresses** the finding",
            b" but it **Addresses** the finding",
        ):
            with self.subTest(suffix=suffix):
                shutil.copy2(ROOT / CHECKER, self.root / CHECKER)
                shutil.copy2(ROOT / proposal_relative, self.root / proposal_relative)
                changed = original.replace(needle, needle + suffix, 1)
                self.assertNotEqual(original, changed)
                self.write_bound_portfolio_file(proposal_relative, changed)
                self.assert_rejected(self.run_checker())


if __name__ == "__main__":
    unittest.main(verbosity=2)
