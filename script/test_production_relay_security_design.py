#!/usr/bin/env python3
"""Direct mutation tests for the production relay hardening JSON contract."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).resolve().parent / "check_production_relay_security_design.py"
SPEC = importlib.util.spec_from_file_location(
    "check_production_relay_security_design",
    SCRIPT_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load production relay security design checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class ProductionRelaySecurityDesignJSONTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = (CHECKER.DESIGN_ROOT / "hardening.json").read_text(encoding="utf-8")
        cls.canonical = json.loads(cls.raw)
        cls.artifact_count = len(CHECKER.EXPECTED_EVIDENCE_PATHS)

    def assert_document_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(ValueError):
            CHECKER.validate_json_document(candidate, self.artifact_count)

    def test_current_hardening_evidence_passes(self) -> None:
        document, referenced_paths = CHECKER.validate_json(self.artifact_count)
        self.assertEqual(document, self.canonical)
        self.assertEqual(len(referenced_paths), 14)

    def test_exact_manifest_paths_and_collection_hash_are_current(self) -> None:
        self.assertEqual(CHECKER.validate_evidence_manifest(), self.artifact_count)
        manifest = CHECKER.DESIGN_ROOT / "evidence.sha256"
        manifest_bytes = manifest.read_bytes()
        self.assertEqual(
            CHECKER.sha256_bytes(manifest_bytes),
            CHECKER.EVIDENCE_COLLECTION_SHA256,
        )
        ordered_paths = tuple(
            line.split("  ", 1)[1]
            for line in manifest_bytes.decode("utf-8").splitlines()
        )
        self.assertEqual(ordered_paths, CHECKER.EXPECTED_EVIDENCE_PATH_ORDER)
        self.assertEqual(set(ordered_paths), CHECKER.EXPECTED_EVIDENCE_PATHS)

    def test_base_revision_and_working_tree_drift_remain_explicit(self) -> None:
        source_evidence = self.canonical["sourceEvidence"]
        self.assertEqual(
            source_evidence["targetRevision"],
            CHECKER.EVIDENCE_BASE_REVISION,
        )
        self.assertEqual(source_evidence["sourceDrift"], "present")

    def test_authority_boundaries_fail_closed(self) -> None:
        mutations = (
            lambda value: value["implementationBoundary"].update(
                {"selectionGatedProductionDesign": "implemented"}
            ),
            lambda value: value["implementationBoundary"][
                "implementedTacticalControls"
            ].update({"scope": "production"}),
            lambda value: value["implementationBoundary"].update(
                {"notImplemented": ["production TLS and service authentication"]}
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_document_rejected(mutation)

    def test_duplicate_keys_are_rejected_at_top_level_and_nested(self) -> None:
        mutations = (
            self.raw.replace(
                '  "analysisId": "production_relay_v1_20260710",',
                '  "analysisId": "other",\n'
                '  "analysisId": "production_relay_v1_20260710",',
                1,
            ),
            self.raw.replace(
                '    "artifactCount": 17,',
                '    "artifactCount": 0,\n    "artifactCount": 17,',
                1,
            ),
            self.raw.replace(
                '              "tacticalFixRequired": true,',
                '              "tacticalFixRequired": false,\n'
                '              "tacticalFixRequired": true,',
                1,
            ),
        )
        for candidate in mutations:
            with self.subTest(candidate_length=len(candidate)):
                with self.assertRaises(CHECKER.HardeningJSONError):
                    CHECKER.strict_json_loads(candidate)

    def test_non_finite_numbers_are_rejected_by_the_loader(self) -> None:
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                candidate = self.raw.replace('"artifactCount": 17', f'"artifactCount": {token}', 1)
                with self.assertRaises(CHECKER.HardeningJSONError):
                    CHECKER.strict_json_loads(candidate)

    def test_unknown_authorization_looking_keys_are_rejected(self) -> None:
        mutations = (
            lambda value: value.update({"productionDeploymentAuthorized": False}),
            lambda value: value["sourceEvidence"].update(
                {"productionDeploymentAuthorized": False}
            ),
            lambda value: value["opportunities"][0]["options"][0][
                "implementationReadiness"
            ].update({"productionDeploymentAuthorized": False}),
        )
        for mutation in mutations:
            candidate = copy.deepcopy(self.canonical)
            mutation(candidate)
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError, "authorization-looking"):
                    CHECKER.validate_json_document(candidate, self.artifact_count)

    def test_unknown_nested_schema_fields_are_rejected(self) -> None:
        self.assert_document_rejected(
            lambda value: value["opportunities"][0]["options"][0]["tradeoffs"][0].update(
                {"notes": "not in the evidence contract"}
            )
        )

    def test_exact_scalar_types_reject_bool_int_and_float_confusion(self) -> None:
        mutations = (
            lambda value: value["sourceEvidence"].update({"artifactCount": False}),
            lambda value: value["opportunities"][0]["options"][0][
                "evidenceCoverage"
            ][0].update({"tacticalFixRequired": 1}),
            lambda value: value["sourceEvidence"].update(
                {"artifactCount": float(self.artifact_count)}
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_document_rejected(mutation)


if __name__ == "__main__":
    unittest.main()
