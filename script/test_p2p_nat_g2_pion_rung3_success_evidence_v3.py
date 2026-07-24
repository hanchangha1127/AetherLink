#!/usr/bin/env python3
"""Mutation tests for the tracked-only rung-three v3 success-evidence checker."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError("canonical v3 evidence tests require unoptimized `python3 -I -B -S`")


require_isolated_interpreter()

import copy
import hashlib
import json
import os
from pathlib import Path
import unittest
from typing import Any, Callable


ROOT = Path(os.path.abspath(__file__)).parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung3_success_evidence_v3.py"


def load_checker() -> dict[str, Any]:
    source = CHECKER_PATH.read_bytes()
    namespace: dict[str, Any] = {
        "__file__": os.fspath(CHECKER_PATH),
        "__name__": "_aetherlink_tested_success_evidence_v3",
        "__package__": None,
    }
    exec(
        compile(
            source,
            os.fspath(CHECKER_PATH.relative_to(ROOT)),
            "exec",
            dont_inherit=True,
            optimize=0,
        ),
        namespace,
    )
    return namespace


C = load_checker()


def encode_document(value: Any, *, compact: bool) -> bytes:
    if compact:
        return C["canonical_json_bytes"](value)
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def reseal(value: dict[str, Any], scope: str) -> None:
    payload = copy.deepcopy(value)
    payload.pop("contentBinding")
    value["contentBinding"]["sha256"] = hashlib.sha256(C["canonical_json_bytes"](payload)).hexdigest()
    value["contentBinding"]["scope"] = scope


class SuccessEvidenceV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        reader = C["FixedTrackedReader"](ROOT)
        cls.raw = reader.read_all()
        cls.postrun = C["load_postrun_namespace"](cls.raw[C["POSTRUN_CHECKER_PATH"]])

    def assert_check_error(self, callback: Callable[[], Any]) -> None:
        with self.assertRaises(C["CheckError"]):
            callback()

    def mutated_json(
        self,
        path: str,
        mutation: Callable[[dict[str, Any]], None],
        *,
        scope: str | None = None,
        compact: bool = False,
    ) -> dict[str, bytes]:
        raw = dict(self.raw)
        value = copy.deepcopy(json.loads(raw[path]))
        mutation(value)
        if scope is not None:
            reseal(value, scope)
        raw[path] = encode_document(value, compact=compact)
        return raw

    def validate_without_pins(self, raw: dict[str, bytes]) -> dict[str, Any]:
        return C["validate_documents"](
            raw,
            enforce_pins=False,
            postrun_namespace=self.postrun,
        )

    def test_repository_validation_passes_with_tracked_only_counters(self) -> None:
        result = C["validate_repository"](ROOT)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["trackedFileReadCount"], 12)
        for key in (
            "runtimeOutputReadCount",
            "buildReadCount",
            "buildDirectoryEnumerationCount",
            "archiveOpenReadOrStatCount",
            "fileWriteCount",
        ):
            self.assertEqual(result[key], 0)
        self.assertFalse(result["postrunFilesystemReadbackInvoked"])

    def test_allowlist_has_no_build_archive_or_runtime_path(self) -> None:
        paths = C["ALLOWED_PATHS"]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(all("build" not in Path(path).parts for path in paths))
        self.assertTrue(
            all(not path.casefold().endswith(C["ARCHIVE_SUFFIXES"]) for path in paths)
        )
        self.assert_check_error(lambda: C["_validate_allowed_path"]("build/offline-source/result.json"))
        self.assert_check_error(lambda: C["_validate_allowed_path"]("tracked/archive.zip"))

    def test_strict_json_rejects_duplicate_nonfinite_cr_and_missing_lf(self) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":NaN}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":1}\n\n',
        ):
            self.assert_check_error(lambda raw=raw: C["strict_canonical_json"](raw, "mutation"))

    def test_raw_pin_drift_fails_closed(self) -> None:
        raw = dict(self.raw)
        path = C["RECEIPT_PATH"]
        raw[path] = raw[path].replace(b'"result": "passed"', b'"result": "failed"', 1)
        self.assert_check_error(lambda: C["validate_documents"](raw))

    def test_predecessor_pin_drift_fails_closed(self) -> None:
        raw = dict(self.raw)
        path = C["PREVIOUS_PROGRESS_PATH"]
        raw[path] = raw[path][:-2] + b" \n"
        self.assert_check_error(lambda: C["validate_documents"](raw))

    def test_result_full_schema_rejects_missing_field(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value.pop("nextAction")

        raw = self.mutated_json(
            C["RESULT_PATH"],
            mutate,
            scope="result_without_contentBinding",
            compact=True,
        )
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_result_rejects_wrong_source_tree_even_when_content_resealed(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["sourceInventory"]["treeSha256"] = "0" * 64

        raw = self.mutated_json(
            C["RESULT_PATH"],
            mutate,
            scope="result_without_contentBinding",
            compact=True,
        )
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_result_rejects_wrong_creator_counts_even_when_content_resealed(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["creatorMetadataPolicy"]["msDosRegularFileCount"] = 128

        raw = self.mutated_json(
            C["RESULT_PATH"],
            mutate,
            scope="result_without_contentBinding",
            compact=True,
        )
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_runtime_manifest_full_schema_rejects_result_binding_drift(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["resultBinding"]["rawSha256"] = "0" * 64

        raw = self.mutated_json(
            C["RUNTIME_MANIFEST_PATH"],
            mutate,
            scope="manifest_without_contentBinding",
            compact=True,
        )
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_receipt_rejects_postrun_reproduction_overclaim(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            boundary = value["postRunIndependentReproductionBoundary"]
            boundary["candidateCountsIndependentlyReproduced"] = True

        raw = self.mutated_json(
            C["RECEIPT_PATH"],
            mutate,
            scope="receipt_without_contentBinding",
        )
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_receipt_rejects_runner_recomputation_underclaim(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["runnerIndependentRecomputation"]["performed"] = False

        raw = self.mutated_json(
            C["RECEIPT_PATH"],
            mutate,
            scope="receipt_without_contentBinding",
        )
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_progress_rejects_authentication_or_user_action_gate(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["personalProjectBoundary"]["repositoryOwnerAuthenticationRequired"] = True
            value["personalProjectBoundary"]["userActionRequired"] = True

        raw = self.mutated_json(
            C["PROGRESS_PATH"],
            mutate,
            scope="progress_without_contentBinding",
        )
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_supersession_rejects_schema_extension(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["unreviewedField"] = False

        raw = self.mutated_json(
            C["SUPERSESSION_PATH"],
            mutate,
            scope="supersession_without_contentBinding",
        )
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_manifest_rejects_artifact_and_collection_drift(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["artifacts"][0]["sha256"] = "0" * 64
            value["collectionSha256"] = C["collection_sha256"](value["artifacts"])

        raw = self.mutated_json(C["MANIFEST_PATH"], mutate)
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_manifest_rejects_runtime_read_or_auth_boundary(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["trustBoundary"]["runtimeOutputReadAllowed"] = True
            value["trustBoundary"]["externalIdentityProofRequired"] = True

        raw = self.mutated_json(C["MANIFEST_PATH"], mutate)
        self.assert_check_error(lambda: self.validate_without_pins(raw))

    def test_no_zero_digest_placeholders_in_new_canonical_documents(self) -> None:
        placeholder = b'"' + (b"0" * 64) + b'"'
        for path in (
            C["RECEIPT_PATH"],
            C["PROGRESS_PATH"],
            C["SUPERSESSION_PATH"],
            C["MANIFEST_PATH"],
        ):
            self.assertNotIn(placeholder, self.raw[path], path)

    def test_validation_uses_only_pure_postrun_functions(self) -> None:
        namespace = dict(self.postrun)

        def forbidden_readback(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("postrun filesystem readback must not be invoked")

        namespace["check_post_run"] = forbidden_readback
        result = C["validate_documents"](
            self.raw,
            enforce_pins=True,
            postrun_namespace=namespace,
        )
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["postrunFilesystemReadbackInvoked"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
