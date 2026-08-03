#!/usr/bin/env python3
"""Regressions for independent current-source idle repeatability readback."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from script import check_macos_current_source_lane_a_idle_resource_repeatability as checker
from script import run_clean_release_reproducibility as producer


class IdleRepeatabilityReadbackTests(unittest.TestCase):
    release_id = "aetherlink-1.0.0+24-local-v1"
    label = "checker-fixture"

    def setUp(self) -> None:
        from script.test_run_clean_release_reproducibility import (
            CleanReleaseReproducibilityTests as Fixtures,
        )

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.lifecycle_root = self.root / "lifecycle"
        self.result_root = self.root / "reproducibility"
        self.lifecycle_root.mkdir(mode=0o700)
        self.result_root.mkdir(mode=0o700)
        evidence = Fixtures.evidence(self.root / "archive")
        self.evidence = replace(
            evidence,
            member_inventory=(
                {"path": "manifest.json"},
                {"path": "payload.bin"},
            ),
        )
        with mock.patch.object(
            producer,
            "LIFECYCLE_RESULT_ROOT",
            self.lifecycle_root,
        ):
            self.paths = producer.lane_a_local_dmg_suite_paths(
                self.label,
                expected_release_id=self.release_id,
            )
        fixture = Fixtures()
        self.suite = fixture.lane_a_suite(
            self.paths,
            release_id=self.release_id,
            evidence=self.evidence,
        )
        self.parent = fixture.lane_a_suite_parent_result(
            self.release_id,
            self.evidence,
        )
        self.parent["protectedArchive"] = {
            "afterIdentitySha256": "e" * 64,
            "beforeIdentitySha256": "e" * 64,
            "policy": producer.PROTECTED_RELEASE_POLICY,
            "relativePath": "dist/releases/aetherlink-1.0.0+23-local-v1",
            "unchanged": True,
        }
        self.parent_path = self.result_root / (
            f"{self.release_id}-two-root-v4-prepublication-{self.label}.json"
        )
        self.payloads = {
            self.parent_path: self.parent,
            self.paths.idle_resource_stability: (
                self.suite.idle_resource_stability
            ),
            self.paths.idle_resource_stability_repeat: (
                self.suite.idle_resource_stability_repeat
            ),
            self.paths.idle_resource_repeatability: (
                self.suite.idle_resource_repeatability
            ),
        }
        self.write_payloads()

    @staticmethod
    def write_bytes(path: Path, raw: bytes) -> None:
        path.write_bytes(raw)
        path.chmod(0o600)

    def write_payloads(self) -> None:
        for path, payload in self.payloads.items():
            self.write_bytes(path, checker.canonical_json_bytes(payload))

    def check(self) -> dict[str, object]:
        return checker.check(
            parent_path=self.parent_path,
            run_a_path=self.paths.idle_resource_stability,
            run_b_path=self.paths.idle_resource_stability_repeat,
            receipt_path=self.paths.idle_resource_repeatability,
        )

    def test_valid_two_run_receipt_passes_without_producer_import(self) -> None:
        result = self.check()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["runCount"], 2)
        self.assertEqual(result["releaseId"], self.release_id)
        source = Path(checker.__file__).read_text(encoding="utf-8")
        self.assertNotIn("run_clean_release_reproducibility", source)

    def test_result_measurements_may_differ_but_each_is_recomputed(self) -> None:
        self.assertNotEqual(
            self.paths.idle_resource_stability.read_bytes(),
            self.paths.idle_resource_stability_repeat.read_bytes(),
        )
        self.assertIs(
            self.suite.idle_resource_repeatability["resultBytesEqual"],
            False,
        )
        self.assertEqual(self.check()["status"], "passed")

        invalid = copy.deepcopy(self.suite.idle_resource_stability_repeat)
        invalid["measurement"]["run"]["samples"][0][
            "openFileDescriptorCount"
        ] = True
        self.write_bytes(
            self.paths.idle_resource_stability_repeat,
            checker.canonical_json_bytes(invalid),
        )
        with self.assertRaises(checker.IdleRepeatabilityCheckError):
            self.check()

    def test_parent_source_or_archive_drift_is_rejected(self) -> None:
        for label, mutate in (
            (
                "source",
                lambda value: value["source"].__setitem__(
                    "sha256",
                    "b" * 64,
                ),
            ),
            (
                "archive",
                lambda value: value["builds"][1]["archive"].__setitem__(
                    "sha256",
                    "c" * 64,
                ),
            ),
            (
                "bool-int",
                lambda value: value["comparison"].__setitem__(
                    "archiveBytesEqual",
                    1,
                ),
            ),
        ):
            candidate = copy.deepcopy(self.parent)
            mutate(candidate)
            self.write_bytes(
                self.parent_path,
                checker.canonical_json_bytes(candidate),
            )
            with self.subTest(label=label), self.assertRaises(
                checker.IdleRepeatabilityCheckError
            ):
                self.check()
        self.write_payloads()

    def test_invariant_or_receipt_identity_drift_is_rejected(self) -> None:
        invariant_drift = copy.deepcopy(
            self.suite.idle_resource_stability_repeat
        )
        invariant_drift["environment"]["architecture"] = "x86_64"
        self.write_bytes(
            self.paths.idle_resource_stability_repeat,
            checker.canonical_json_bytes(invariant_drift),
        )
        with self.assertRaises(checker.IdleRepeatabilityCheckError):
            self.check()
        self.write_payloads()

        for label, mutate in (
            (
                "hash",
                lambda value: value["runs"][1].__setitem__(
                    "sha256",
                    "d" * 64,
                ),
            ),
            (
                "bool-count",
                lambda value: value.__setitem__("runCount", True),
            ),
            (
                "absolute-path",
                lambda value: value["runs"][0].__setitem__(
                    "fileName",
                    "/private/tmp/result.json",
                ),
            ),
        ):
            candidate = copy.deepcopy(self.suite.idle_resource_repeatability)
            mutate(candidate)
            self.write_bytes(
                self.paths.idle_resource_repeatability,
                checker.canonical_json_bytes(candidate),
            )
            with self.subTest(label=label), self.assertRaises(
                checker.IdleRepeatabilityCheckError
            ):
                self.check()
        self.write_payloads()

    def test_duplicate_key_noncanonical_and_permissions_are_rejected(
        self,
    ) -> None:
        self.write_bytes(
            self.paths.idle_resource_repeatability,
            b'{"status":"passed","status":"passed"}\n',
        )
        with self.assertRaisesRegex(
            checker.IdleRepeatabilityCheckError,
            "duplicate JSON key",
        ):
            self.check()

        self.write_bytes(
            self.paths.idle_resource_repeatability,
            json.dumps(
                self.suite.idle_resource_repeatability,
                indent=2,
            ).encode("ascii"),
        )
        with self.assertRaisesRegex(
            checker.IdleRepeatabilityCheckError,
            "not canonical",
        ):
            self.check()

        self.write_payloads()
        self.parent_path.chmod(0o644)
        with self.assertRaisesRegex(
            checker.IdleRepeatabilityCheckError,
            "owner-only",
        ):
            self.check()

    def test_filename_set_is_closed_and_same_label(self) -> None:
        wrong = self.lifecycle_root / self.paths.idle_resource_stability_repeat.name.replace(
            self.label,
            "different-label",
        )
        self.write_bytes(
            wrong,
            self.paths.idle_resource_stability_repeat.read_bytes(),
        )
        with self.assertRaisesRegex(
            checker.IdleRepeatabilityCheckError,
            "filenames differ",
        ):
            checker.check(
                parent_path=self.parent_path,
                run_a_path=self.paths.idle_resource_stability,
                run_b_path=wrong,
                receipt_path=self.paths.idle_resource_repeatability,
            )


if __name__ == "__main__":
    unittest.main()
