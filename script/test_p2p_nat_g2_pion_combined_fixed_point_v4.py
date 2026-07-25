#!/usr/bin/env python3
"""Focused tests for the offline Wave1+Wave2+Wave3+Wave4+Wave5 checker."""

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
        raise RuntimeError(
            "combined fixed-point v4 tests require unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import ast
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_combined_fixed_point_v4.py"
CHECKER_RAW_SHA256 = (
    "2576f7d2e0f0c8dffd2f4956254af3f62b39fdabb25b793242315f50b1373a52"
)
EXPECTED_CONTENT_SHA256 = (
    "c223cb039aa7e819e78cd1b27c360076c50197b0cd11a21dd447fcdcb01d23a6"
)


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "combined_fixed_point_v4_tests_target",
        CHECKER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("checker load failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()


@contextmanager
def held_wave5_documents():
    with CHECKER.PinnedCodeFile(
        ROOT,
        CHECKER.V1_CHECKER_PATH,
        CHECKER.V1_CHECKER_RAW_SHA256,
    ) as v1_held:
        v1 = CHECKER.load_v1_checker(v1_held)
        with v1.PinnedRunnerFile(ROOT) as provider_held:
            runner = v1.load_pinned_runner(provider_held)
            with runner.HeldInputSet(
                ROOT,
                CHECKER.wave5_control_bindings(),
            ) as control_held:
                documents = CHECKER.parse_wave5_documents(
                    runner,
                    control_held,
                )
                yield runner, documents


def assert_mutation_fails(
    testcase: unittest.TestCase,
    mutate,
    expected_code: str,
) -> None:
    with held_wave5_documents() as (runner, documents):
        mutated = copy.deepcopy(documents)
        mutate(mutated)
        with (
            mock.patch.object(
                CHECKER,
                "verify_wave5_content_bindings",
            ),
            testcase.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught,
        ):
            CHECKER.wave5_request_resources(runner, mutated)
        testcase.assertEqual(str(caught.exception), expected_code)


def deep_rebind_wave5_resource_mutation(runner, documents, mutate):
    """Rebind the complete acquisition and frozen-snapshot digest chain."""
    permit = documents[CHECKER.WAVE5_PERMIT_PATH]
    resources = permit["requestContract"]["resources"]
    mutate(resources)
    resources_sha256 = CHECKER.sha256_bytes(
        runner.canonical_json_bytes(resources)
    )
    permit["requestContract"][
        "resourcesCanonicalSha256"
    ] = resources_sha256

    def rebind_content(document):
        without = dict(document)
        without.pop("contentBinding")
        digest = CHECKER.sha256_bytes(
            runner.canonical_json_bytes(without)
        )
        document["contentBinding"]["sha256"] = digest
        return digest

    def raw_binding(document):
        raw = runner.canonical_json_bytes(document)
        return {
            "bytes": len(raw),
            "rawSha256": CHECKER.sha256_bytes(raw),
        }

    permit_content = rebind_content(permit)
    permit_raw = raw_binding(permit)

    receipt = documents[CHECKER.WAVE5_RECEIPT_PATH]
    receipt["permitContentSha256"] = permit_content
    receipt_raw = raw_binding(receipt)

    acquisition_manifest = documents[CHECKER.WAVE5_MANIFEST_PATH]
    acquisition_manifest["receiptRawSha256"] = receipt_raw["rawSha256"]
    acquisition_manifest_raw = raw_binding(acquisition_manifest)

    readback_permit = documents[CHECKER.WAVE5_READBACK_PERMIT_PATH]
    snapshot = readback_permit["frozenAcquisitionSnapshot"]
    snapshot["acquisitionPermitContentSha256"] = permit_content
    permit_rows = [
        row
        for row in snapshot["acquisitionAuthority"]
        if row["path"] == CHECKER.WAVE5_PERMIT_PATH
    ]
    if len(permit_rows) != 1:
        raise AssertionError("expected one acquisition permit authority row")
    permit_rows[0].update(permit_raw)
    snapshot["acquisitionReceipt"].update(receipt_raw)
    snapshot["acquisitionManifest"].update(acquisition_manifest_raw)
    frozen_canonical = [
        *snapshot["acquisitionAuthority"],
        snapshot["acquisitionClaim"],
        snapshot["evidence"],
        *snapshot["acceptedDirectory"]["files"],
        snapshot["acquisitionReceipt"],
        snapshot["acquisitionManifest"],
    ]
    frozen_sha256 = CHECKER.sha256_bytes(
        runner.canonical_json_bytes(frozen_canonical)
    )
    snapshot["frozenFileCount"] = len(frozen_canonical)
    snapshot["frozenFilesCanonicalSha256"] = frozen_sha256
    readback_permit_content = rebind_content(readback_permit)
    readback_permit_raw = raw_binding(readback_permit)

    readback = documents[CHECKER.WAVE5_READBACK_PATH]
    verified = readback["verified"]
    verified["permitContentSha256"] = permit_content
    verified["acquisitionReceiptRawSha256"] = receipt_raw["rawSha256"]
    verified[
        "acquisitionManifestRawSha256"
    ] = acquisition_manifest_raw["rawSha256"]
    readback["authorityBinding"]["permit"].update(
        {
            "contentSha256": readback_permit_content,
            "rawSha256": readback_permit_raw["rawSha256"],
        }
    )
    readback_content = rebind_content(readback)
    readback_raw = raw_binding(readback)

    readback_manifest = documents[CHECKER.WAVE5_READBACK_MANIFEST_PATH]
    readback_manifest["authorityBinding"]["permit"].update(
        {
            "contentSha256": readback_permit_content,
            "rawSha256": readback_permit_raw["rawSha256"],
        }
    )
    readback_manifest["receipt"].update(
        {
            "contentSha256": readback_content,
            **readback_raw,
        }
    )
    readback_manifest_content = rebind_content(readback_manifest)
    readback_manifest_raw = raw_binding(readback_manifest)

    return {
        "resourcesSha256": resources_sha256,
        "frozenFilesSha256": frozen_sha256,
        "contentSha256": {
            CHECKER.WAVE5_PERMIT_PATH: permit_content,
            CHECKER.WAVE5_READBACK_PERMIT_PATH: readback_permit_content,
            CHECKER.WAVE5_READBACK_PATH: readback_content,
            CHECKER.WAVE5_READBACK_MANIFEST_PATH:
                readback_manifest_content,
        },
        "rawSha256": {
            CHECKER.WAVE5_PERMIT_PATH: permit_raw["rawSha256"],
            CHECKER.WAVE5_RECEIPT_PATH: receipt_raw["rawSha256"],
            CHECKER.WAVE5_MANIFEST_PATH:
                acquisition_manifest_raw["rawSha256"],
            CHECKER.WAVE5_READBACK_PERMIT_PATH:
                readback_permit_raw["rawSha256"],
            CHECKER.WAVE5_READBACK_PATH: readback_raw["rawSha256"],
            CHECKER.WAVE5_READBACK_MANIFEST_PATH:
                readback_manifest_raw["rawSha256"],
        },
    }


def assert_deep_rebound_resource_mutation_fails(testcase, mutate):
    with held_wave5_documents() as (runner, documents):
        mutated = copy.deepcopy(documents)
        bindings = deep_rebind_wave5_resource_mutation(
            runner,
            mutated,
            mutate,
        )
        with (
            mock.patch.object(
                CHECKER,
                "WAVE5_PERMIT_RESOURCES_SHA256",
                bindings["resourcesSha256"],
            ),
            mock.patch.object(
                CHECKER,
                "WAVE5_FROZEN_FILE_SET_SHA256",
                bindings["frozenFilesSha256"],
            ),
            mock.patch.dict(
                CHECKER.WAVE5_CONTENT_SHA256,
                bindings["contentSha256"],
            ),
            mock.patch.dict(
                CHECKER.WAVE5_CONTROL_SHA256,
                bindings["rawSha256"],
            ),
            testcase.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught,
        ):
            CHECKER.wave5_request_resources(runner, mutated)
        testcase.assertEqual(
            str(caught.exception),
            "E_WAVE5_RESOURCE",
        )


class CombinedFixedPointV4Tests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.candidate = CHECKER.generate_candidate(ROOT)
        cls.canonical = (
            json.dumps(
                cls.candidate,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )

    def test_01_exact_self_predecessor_control_and_content_pins(self):
        raw = CHECKER_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), CHECKER_RAW_SHA256)
        self.assertEqual(
            hashlib.sha256(CHECKER.normalized_self_bytes(raw)).hexdigest(),
            CHECKER.SELF_NORMALIZED_SHA256,
        )
        for path, digest in (
            (CHECKER.V1_CHECKER_PATH, CHECKER.V1_CHECKER_RAW_SHA256),
            (CHECKER.V2_CHECKER_PATH, CHECKER.V2_CHECKER_RAW_SHA256),
            (CHECKER.V3_CHECKER_PATH, CHECKER.V3_CHECKER_RAW_SHA256),
            (CHECKER.V1_PROVIDER_PATH, CHECKER.V1_PROVIDER_RAW_SHA256),
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                digest,
            )
        for path, digest in CHECKER.WAVE5_CONTROL_SHA256.items():
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                digest,
            )
        self.assertEqual(
            self.candidate["contentBinding"]["sha256"],
            EXPECTED_CONTENT_SHA256,
        )

    def test_02_candidate_is_exact_non_authorizing_next_wave_result(self):
        candidate = self.candidate
        self.assertEqual(candidate["schemaVersion"], "4.0")
        self.assertEqual(
            candidate["status"],
            "combined_graph_discovery_complete_next_wave_required",
        )
        self.assertEqual(candidate["route"], "next_wave_required")
        self.assertEqual(
            candidate["nextAction"],
            "prepare_separate_versioned_dependency_wave_identity_and_"
            "acquisition_decision",
        )
        self.assertTrue(candidate["authority"])
        self.assertTrue(
            all(value is False for value in candidate["authority"].values())
        )
        without = dict(candidate)
        without.pop("contentBinding")
        self.assertEqual(
            hashlib.sha256(
                json.dumps(
                    without,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                + b"\n"
            ).hexdigest(),
            EXPECTED_CONTENT_SHA256,
        )

    def test_03_exact_input_and_coverage_totals(self):
        inputs = self.candidate["inputSet"]
        self.assertEqual(
            {
                key: inputs[key]
                for key in (
                    "heldSourceInputCount",
                    "resourceCount",
                    "modCount",
                    "zipCount",
                    "wave1ResourceCount",
                    "wave2ResourceCount",
                    "wave3ResourceCount",
                    "wave4ResourceCount",
                    "wave5ResourceCount",
                    "uniqueModuleVersionTupleCount",
                    "aggregateRawByteSize",
                )
            },
            {
                "heldSourceInputCount": 163,
                "resourceCount": 162,
                "modCount": 81,
                "zipCount": 81,
                "wave1ResourceCount": 38,
                "wave2ResourceCount": 30,
                "wave3ResourceCount": 32,
                "wave4ResourceCount": 32,
                "wave5ResourceCount": 30,
                "uniqueModuleVersionTupleCount": 81,
                "aggregateRawByteSize": 123_264_755,
            },
        )
        self.assertEqual(
            inputs["combinedInputSetSha256"],
            "b7eca5385fd0cf811d0eb7e8a00fe467bf64f8c10fa1ab998521f00510b0b8b2",
        )
        self.assertEqual(
            self.candidate["coverage"],
            {
                "archiveCount": 82,
                "aggregateEntryCount": 26_810,
                "aggregateUncompressedByteCount": 458_679_093,
                "goSourceFileCount": 21_480,
                "semanticParsedGoSourceCount": 19_497,
                "testdataSemanticExclusionCount": 1_983,
                "testdataSemanticExclusionSetSha256":
                    "b336a764ad42a005e06da9aadfde8679a39b3d5051f8feb84e3def7230382e05",
            },
        )

    def test_04_exact_graph_and_frontier(self):
        graph = self.candidate["graphDiscovery"]
        self.assertFalse(graph["fixedPointReached"])
        self.assertEqual(graph["graphNodeCount"], 132)
        self.assertEqual(graph["graphEdgeCount"], 1_047)
        self.assertEqual(graph["moduleNodeCount"], 100)
        self.assertEqual(graph["moduleEdgeCount"], 247)
        self.assertEqual(graph["newTupleCount"], 18)
        self.assertEqual(
            graph["moduleNodeSetSha256"],
            "7709c4570d773c630777814dde296cbb547891cc17f8833620ef8a28893e295c",
        )
        self.assertEqual(
            graph["moduleEdgeSetSha256"],
            "649d8296eadbd3972799fd4b391c33d8ab3448f041e774fafc37bad790f4fbed",
        )
        self.assertEqual(
            graph["moduleGraphAndFrontierSha256"],
            "a27185f3136ee694ba5e5e4d89d4eb985055b5c1d0599e826842169625d8c2e6",
        )
        self.assertEqual(
            hashlib.sha256(
                json.dumps(
                    graph["exactFrontier"],
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            ).hexdigest(),
            "a966326a38b3050ac6ad7387405d359488b049d86982cde27946008dd258a6ce",
        )
        self.assertTrue(
            all(
                row["selectedByGraphAlgorithm"] is False
                and row["acquisitionAuthorized"] is False
                for row in graph["exactFrontier"]
            )
        )

    def test_05_direct_inherited_total_counters_are_separate(self):
        verification = self.candidate["checkerVerification"]
        self.assertEqual(verification["directFullInputReconstructionCount"], 2)
        self.assertEqual(
            verification["inheritedFullInputReconstructionCount"],
            4,
        )
        self.assertEqual(verification["totalFullInputReconstructionCount"], 6)
        self.assertEqual(
            verification["underlyingIndependentGraphAlgorithmCount"],
            12,
        )
        counters = self.candidate["operationCounters"]
        self.assertEqual(counters["heldTerminalEvidenceCount"], 31)
        self.assertEqual(counters["heldToolInputCount"], 4)
        self.assertEqual(counters["transitiveDistinctToolPathCount"], 5)
        self.assertEqual(counters["archiveOpenCount"], 400)
        for key in (
            "networkOperationCount",
            "subprocessCount",
            "sourceExecutionCount",
            "archiveExtractionCount",
            "fileWriteCount",
        ):
            self.assertEqual(counters[key], 0)

    def test_06_wave5_documents_produce_exact_30_resources(self):
        with held_wave5_documents() as (runner, documents):
            resources = CHECKER.wave5_request_resources(runner, documents)
        self.assertEqual(len(resources), 30)
        self.assertEqual(sum(row["kind"] == "mod" for row in resources), 15)
        self.assertEqual(sum(row["kind"] == "zip" for row in resources), 15)
        self.assertEqual(
            sorted({row["tupleOrder"] for row in resources}),
            list(range(67, 82)),
        )

    def test_07_unknown_acquisition_authority_field_fails_closed(self):
        assert_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE5_PERMIT_PATH]["authority"].__setitem__(
                "unknownAuthority",
                False,
            ),
            "E_WAVE5_PERMIT",
        )

    def test_08_unknown_readback_authority_field_fails_closed(self):
        assert_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE5_READBACK_PERMIT_PATH][
                "authority"
            ].__setitem__("unknownAuthority", False),
            "E_WAVE5_READBACK_PERMIT",
        )

    def test_09_wave5_raw_binding_mutation_fails_closed(self):
        def mutate(docs):
            docs[CHECKER.WAVE5_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"]["files"][0]["rawSha256"] = "0" * 64

        assert_mutation_fails(self, mutate, "E_WAVE5_RESOURCE")

    def test_10_wave5_h1_deep_rebinding_reaches_cross_document_check(self):
        assert_deep_rebound_resource_mutation_fails(
            self,
            lambda resources: resources[0].__setitem__(
                "expectedH1",
                "h1:" + "A" * 43 + "=",
            ),
        )

    def test_11_wave5_order_deep_rebinding_reaches_cross_document_check(self):
        assert_deep_rebound_resource_mutation_fails(
            self,
            lambda resources: resources[0].__setitem__(
                "requestOrdinal",
                2,
            ),
        )

    def test_12_wave5_selection_deep_rebinding_reaches_cross_document_check(self):
        assert_deep_rebound_resource_mutation_fails(
            self,
            lambda resources: resources[0].__setitem__(
                "selectedByGraphAlgorithm",
                True,
            ),
        )

    def test_13_wave5_count_mutation_fails_closed(self):
        def mutate(docs):
            docs[CHECKER.WAVE5_PERMIT_PATH]["requestContract"][
                "resources"
            ].pop()

        assert_mutation_fails(self, mutate, "E_WAVE5_PERMIT")

    def test_14_readback_retained_snapshot_boundary_mutation_fails_closed(self):
        def mutate(docs):
            docs[CHECKER.WAVE5_READBACK_PATH][
                "currentPathIdentityGuaranteedThroughManifestPublication"
            ] = True

        assert_mutation_fails(self, mutate, "E_WAVE5_READBACK")

    def test_15_readback_claim_raw_mutation_fails_closed(self):
        def mutate(docs):
            docs[CHECKER.WAVE5_READBACK_PATH]["readbackClaim"][
                "rawSha256"
            ] = "0" * 64

        assert_mutation_fails(self, mutate, "E_WAVE5_READBACK")

    def test_16_static_surface_is_offline_read_only_and_auth_free(self):
        source = CHECKER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_imports = {
            "requests",
            "socket",
            "subprocess",
            "urllib",
            "http",
            "ftplib",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(
                    all(
                        alias.name.split(".")[0] not in forbidden_imports
                        for alias in node.names
                    )
                )
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(
                    (node.module or "").split(".")[0],
                    forbidden_imports,
                )
            if isinstance(node, ast.Call) and isinstance(
                node.func,
                ast.Attribute,
            ):
                self.assertNotIn(
                    node.func.attr,
                    {
                        "write_bytes",
                        "write_text",
                        "replace",
                        "rename",
                        "unlink",
                        "mkdir",
                        "makedirs",
                    },
                )
        self.assertNotIn("--execute", source)
        self.assertNotIn("--record", source)
        self.assertNotIn("input(", source)
        error = json.loads(CHECKER.error_document_bytes())
        self.assertFalse(error["externalAuthenticationRequired"])
        self.assertFalse(error["userActionRequired"])

    def test_17_self_body_drift_and_link_aliases_fail_closed(self):
        raw = CHECKER_PATH.read_bytes()
        changed = raw.replace(
            b'"fileWriteCount": 0',
            b'"fileWriteCount": 1',
            1,
        )
        self.assertNotEqual(
            hashlib.sha256(CHECKER.normalized_self_bytes(changed)).hexdigest(),
            CHECKER.SELF_NORMALIZED_SHA256,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "script"
            script.mkdir(mode=0o700)
            target = script / "tool.py"
            target.write_bytes(b"VALUE = 1\n")
            linked = script / "linked.py"
            os.link(target, linked)
            with self.assertRaises(CHECKER.CombinedCheckFailure):
                CHECKER.PinnedCodeFile(
                    root,
                    "script/tool.py",
                    hashlib.sha256(target.read_bytes()).hexdigest(),
                )


if __name__ == "__main__":
    unittest.main()
