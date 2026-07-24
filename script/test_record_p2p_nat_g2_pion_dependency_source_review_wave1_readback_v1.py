#!/usr/bin/env python3
"""Synthetic regression tests for the wave-one readback recorder."""

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
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


RECORDER_PATH = (
    Path(__file__).resolve().parent
    / "record_p2p_nat_g2_pion_dependency_source_review_wave1_readback_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "dependency_source_review_wave1_readback_recorder",
    RECORDER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load recorder")
recorder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recorder)


def write_file(
    root: Path,
    relative: str,
    payload: bytes,
    *,
    mode: int = 0o644,
) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(mode)


def bound(value: dict[str, object], scope: str) -> dict[str, object]:
    return recorder.content_bound(value, scope)


def graph_for(route: str, *, mixed_external: bool = False) -> dict[str, object]:
    root_module = "github.com/pion/ice/v4"
    root_version = "v4.3.0"
    selected: list[dict[str, object]] = [
        {"module": root_module, "version": root_version}
    ]
    module_nodes: list[dict[str, object]] = [
        {
            "module": root_module,
            "version": root_version,
            "isRoot": True,
            "sourceAvailable": True,
            "frontier": False,
            "selectedForModule": True,
        }
    ]
    module_edges: list[dict[str, object]] = []
    nodes: list[dict[str, object]] = [
        {
            "profileId": "android_api_26_through_36_arm64_v8a",
            "module": root_module,
            "package": root_module,
        },
        {
            "profileId": "macos_14_or_newer_arm64",
            "module": root_module,
            "package": root_module,
        },
    ]
    edges: list[dict[str, object]] = []
    if route == "new_tuple_wave_required":
        selected.append({"module": "example.com/new", "version": "v1.0.0"})
        module_nodes.append(
            {
                "module": "example.com/new",
                "version": "v1.0.0",
                "isRoot": False,
                "sourceAvailable": False,
                "frontier": True,
                "selectedForModule": True,
            }
        )
        module_edges.append(
            {
                "fromModule": root_module,
                "fromVersion": root_version,
                "requiredModule": "example.com/new",
                "requestedVersion": "v1.0.0",
                "selectedVersion": "v1.0.0",
                "targetSourceAvailable": False,
            }
        )
    if route == "external_import_resolution_required" or mixed_external:
        edges.append(
            {
                "profileId": "android_api_26_through_36_arm64_v8a",
                "fromPackage": root_module,
                "importPath": "example.net/unmapped/pkg",
                "targetModule": None,
                "targetVersion": None,
                "edgeClass": "unmapped_external",
            }
        )
    selected.sort(key=lambda row: (row["module"], row["version"]))
    module_nodes.sort(key=lambda row: (row["module"], row["version"]))
    module_edges.sort(
        key=lambda row: (
            row["fromModule"],
            row["fromVersion"],
            row["requiredModule"],
            row["requestedVersion"],
        )
    )
    edges.sort(
        key=lambda row: (
            row["profileId"],
            row["fromPackage"],
            row["importPath"],
        )
    )
    frontier = [
        {
            "module": row["module"],
            "version": row["version"],
            "selectedByGraphAlgorithm": row["selectedForModule"],
            "requiresSeparateWaveDecision": True,
            "acquisitionAuthorized": False,
        }
        for row in module_nodes
        if row["frontier"]
    ]
    unmapped = [
        {
            "profileId": row["profileId"],
            "fromPackage": row["fromPackage"],
            "importPath": row["importPath"],
        }
        for row in edges
        if row["edgeClass"] == "unmapped_external"
    ]
    declared: list[dict[str, object]] = []
    projection = {
        "selectedVersions": selected,
        "nodes": nodes,
        "edges": edges,
        "moduleNodes": module_nodes,
        "moduleEdges": module_edges,
        "exactFrontier": frontier,
        "unmappedExternalImports": unmapped,
        "unresolvedDeclaredExternalImports": declared,
    }
    projection_sha = recorder.digest(projection)
    module_sha = recorder.digest(
        {
            "selectedVersions": selected,
            "moduleNodes": module_nodes,
            "moduleEdges": module_edges,
            "exactFrontier": frontier,
        }
    )
    return {
        "algorithm": "go1.24_mvs_profile_union_fixed_point_v1",
        "versionSpecificVertexTraversal": True,
        "nodes": nodes,
        "edges": edges,
        "moduleNodes": module_nodes,
        "moduleEdges": module_edges,
        "selectedVersions": selected,
        "exactFrontier": frontier,
        "newlyReachableTuples": copy.deepcopy(frontier),
        "unmappedExternalImports": unmapped,
        "unresolvedDeclaredExternalImports": declared,
        "nodeSetSha256": recorder.digest(nodes),
        "edgeSetSha256": recorder.digest(edges),
        "moduleNodeSetSha256": recorder.digest(module_nodes),
        "moduleEdgeSetSha256": recorder.digest(module_edges),
        "moduleGraphAndFrontierSha256": module_sha,
        "reconstructionProjectionSha256": projection_sha,
        "unmappedExternalImportSetSha256": recorder.digest(unmapped),
        "unresolvedDeclaredExternalImportSetSha256": recorder.digest(declared),
        "graphSha256": projection_sha,
        "graphNodeCount": len(nodes),
        "graphEdgeCount": len(edges),
        "moduleNodeCount": len(module_nodes),
        "moduleEdgeCount": len(module_edges),
        "newTupleCount": len(frontier),
        "unmappedExternalImportCount": len(unmapped),
        "unresolvedDeclaredExternalImportCount": len(declared),
        "fixedPointReached": not frontier and not unmapped and not declared,
        "independentReproductionPassed": True,
        "reconstructionCount": 2,
        "reconstructions": [
            {
                "algorithm": "version_vertex_breadth_first_search",
                "nodeSetSha256": recorder.digest(nodes),
                "edgeSetSha256": recorder.digest(edges),
                "moduleGraphAndFrontierSha256": module_sha,
                "reconstructionSha256": projection_sha,
            },
            {
                "algorithm": "version_vertex_monotone_full_set_scan",
                "nodeSetSha256": recorder.digest(nodes),
                "edgeSetSha256": recorder.digest(edges),
                "moduleGraphAndFrontierSha256": module_sha,
                "reconstructionSha256": projection_sha,
            },
        ],
    }


class SyntheticReviewFixture:
    def __init__(
        self,
        route: str = "fixed_point_candidate",
        *,
        mixed_external: bool = False,
    ) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.route = route
        for role, path in recorder.TOOL_PATHS.items():
            write_file(
                self.root,
                path,
                f"#!/usr/bin/env python3\n# synthetic {role}\n".encode(),
            )
        project_root = RECORDER_PATH.parents[1]
        historical_paths = (
            recorder.DECISION_PATH,
            recorder.V1_RECOVERY_DECISION_PATH,
            recorder.RECOVERY_DECISION_PATH,
            recorder.V1_PERMIT_PATH,
            recorder.V1_REVIEW_CLAIM_PATH,
            recorder.V1_FAILURE_PATH,
            recorder.V2_PERMIT_PATH,
            recorder.V2_REVIEW_CLAIM_PATH,
            recorder.V2_FAILURE_PATH,
        )
        owner_only_paths = {
            recorder.V1_REVIEW_CLAIM_PATH,
            recorder.V1_FAILURE_PATH,
            recorder.V2_REVIEW_CLAIM_PATH,
            recorder.V2_FAILURE_PATH,
        }
        for relative in historical_paths:
            write_file(
                self.root,
                relative,
                (project_root / relative).read_bytes(),
                mode=0o600 if relative in owner_only_paths else 0o644,
            )
        self.decision = recorder.strict_json(
            (self.root / recorder.DECISION_PATH).read_bytes(),
            "fixture decision",
        )
        self.v1_recovery = recorder.strict_json(
            (self.root / recorder.V1_RECOVERY_DECISION_PATH).read_bytes(),
            "fixture v1 recovery",
        )
        self.recovery = recorder.strict_json(
            (self.root / recorder.RECOVERY_DECISION_PATH).read_bytes(),
            "fixture recovery",
        )
        original_decision_binding = copy.deepcopy(
            self.recovery["decisionBinding"]
        )
        tool_bindings = [
            {
                "role": role,
                "path": path,
                "rawSha256": recorder.sha256_bytes(
                    (self.root / path).read_bytes()
                ),
            }
            for role, path in recorder.TOOL_PATHS.items()
        ]
        permit_body: dict[str, object] = {
            "documentType": (
                "aetherlink.g2-pion-bounded-dependency-source-review-"
                "wave1-execution-permit"
            ),
            "schemaVersion": "1.0",
            "permitId": recorder.PERMIT_ID,
            "status": (
                "dependency_source_review_wave1_execution_authorized_"
                "not_consumed"
            ),
            "decisionBinding": original_decision_binding,
            "recoveryDecisionBinding": {
                "path": recorder.RECOVERY_DECISION_PATH,
                "decisionId": recorder.RECOVERY_DECISION_ID,
                "requiredStatus": recorder.RECOVERY_DECISION_STATUS,
                "rawSha256": recorder.sha256_bytes(
                    (self.root / recorder.RECOVERY_DECISION_PATH).read_bytes()
                ),
                "contentSha256": self.recovery[
                    "contentBinding"
                ]["sha256"],
            },
            "priorRecoveryDecisionBinding": copy.deepcopy(
                self.recovery["priorRecoveryDecisionBinding"]
            ),
            "failedAttemptBindings": copy.deepcopy(
                self.recovery["failedAttemptBindings"]
            ),
            "failedAttemptNamespaceContracts": copy.deepcopy(
                self.recovery["failedAttemptNamespaceContracts"]
            ),
            "apfsRecoveryContract": copy.deepcopy(
                self.v1_recovery["selectedV2Correction"]
            ),
            "selectedV3Correction": copy.deepcopy(
                self.recovery["selectedV3Correction"]
            ),
            "v1PreservationContract": copy.deepcopy(
                self.recovery["v1PreservationContract"]
            ),
            "v2PreservationContract": copy.deepcopy(
                self.recovery["v2PreservationContract"]
            ),
            "v3NamespaceContract": copy.deepcopy(
                self.recovery["v3NamespaceContract"]
            ),
            "toolBindings": tool_bindings,
            "oneUseConsumption": {
                "claimPath": recorder.REVIEW_CLAIM_PATH,
                "secondExecutionAllowed": False,
            },
            "resultContract": {
                "resultPath": recorder.RESULT_PATH,
                "failurePath": recorder.FAILURE_PATH,
            },
            "manifestContract": {
                "manifestPath": recorder.REVIEW_MANIFEST_PATH,
                "independentReadbackRequired": True,
            },
            "independentReadbackContract": (
                recorder.expected_readback_contract()
            ),
            "personalProjectBoundary": recorder.personal_boundary(),
            "authority": {
                "networkAuthorized": False,
                "socketAuthorized": False,
                "dnsAuthorized": False,
                "shellOrSubprocessAuthorized": False,
                "reviewedSourceLoadOrExecutionAuthorized": False,
                "sourceMaterializationAuthorized": False,
                "filesystemExtractionAuthorized": False,
                "gitWriteAuthorized": False,
            },
        }
        self.permit = bound(permit_body, "permit_without_contentBinding")
        permit_raw = recorder.canonical_json_bytes(self.permit)
        write_file(self.root, recorder.PERMIT_PATH, permit_raw)
        claim = bound(
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "one-use-claim"
                ),
                "schemaVersion": "1.0",
                "permitId": recorder.PERMIT_ID,
                "permitContentSha256": self.permit["contentBinding"]["sha256"],
                "reviewId": recorder.REVIEW_ID,
                "automaticRetryAllowed": False,
                "repositoryOwnerIdentityProofRequired": False,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
                "productEndpointAuthenticationEvaluatedByThisReview": False,
                "productEndpointAuthenticationUserInputRequiredForThisReview": (
                    False
                ),
                "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
                "productEndpointAuthenticationRemainsSeparateRuntimeInvariant": (
                    True
                ),
            },
            "claim_without_contentBinding",
        )
        write_file(
            self.root,
            recorder.REVIEW_CLAIM_PATH,
            recorder.canonical_json_bytes(claim),
            mode=0o600,
        )
        graph = graph_for(route, mixed_external=mixed_external)
        effective_route = (
            "new_tuple_wave_required"
            if graph["newTupleCount"]
            else (
                "external_import_resolution_required"
                if (
                    graph["unmappedExternalImportCount"]
                    or graph["unresolvedDeclaredExternalImportCount"]
                )
                else "fixed_point_candidate"
            )
        )
        contract = recorder.ROUTES[effective_route]
        result = bound(
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-result"
                ),
                "schemaVersion": "1.0",
                "reviewId": recorder.REVIEW_ID,
                "status": contract["resultStatus"],
                "result": (
                    "exact_wave1_module_metadata_source_surface_and_new_"
                    "tuple_candidates_recorded"
                ),
                "decisionBinding": self.permit["decisionBinding"],
                "permitBinding": {
                    "permitId": recorder.PERMIT_ID,
                    "contentSha256": self.permit["contentBinding"]["sha256"],
                },
                "inputSet": {},
                "coverage": {},
                "moduleMetadata": {},
                "sourceSurface": {},
                "graphDiscovery": graph,
                "licenseInventory": {},
                "specialSourceInventory": {},
                "operationCounters": {
                    "archiveOpenCount": 1,
                    "archiveExtractionCount": 0,
                    "sourceExecutionCount": 0,
                    "subprocessCount": 0,
                    "networkOperationCount": 0,
                    "fileWriteCount": 3,
                },
                "closure": {
                    "openFindingCount": 19,
                    "findingsClosedByReview": 0,
                    "dependencySourceReviewed": False,
                    "graphFixedPointReached": False,
                    "dependencyClosureComplete": False,
                    "semanticClosureComplete": False,
                    "rungThreeComplete": False,
                    "candidateSelected": False,
                    "librarySelected": False,
                },
                "personalProjectBoundary": {
                    "repositoryOwnerIdentityProofRequired": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                    "productEndpointAuthenticationEvaluatedByThisReview": False,
                    "productEndpointAuthenticationUserInputRequiredForThisReview": (
                        False
                    ),
                    "productEndpointAuthenticationIsSeparateRuntimeInvariant": (
                        True
                    ),
                    "productEndpointAuthenticationRemainsSeparateRuntimeInvariant": (
                        True
                    ),
                },
                "nextAction": contract["resultNextAction"],
                "postReadbackNextAction": contract[
                    "postReadbackNextAction"
                ],
            },
            "result_without_contentBinding",
        )
        self.result = result
        result_raw = recorder.canonical_json_bytes(result)
        write_file(
            self.root,
            recorder.RESULT_PATH,
            result_raw,
            mode=0o600,
        )
        manifest = bound(
            {
                "documentType": (
                    "aetherlink.g2-pion-dependency-source-review-wave1-"
                    "manifest"
                ),
                "schemaVersion": "1.0",
                "reviewId": recorder.REVIEW_ID,
                "permitId": recorder.PERMIT_ID,
                "permitContentSha256": self.permit["contentBinding"]["sha256"],
                "resultPath": recorder.RESULT_PATH,
                "resultRawSha256": recorder.sha256_bytes(result_raw),
                "resultContentSha256": result["contentBinding"]["sha256"],
                "graphSha256": graph["graphSha256"],
                "resultStatus": result["status"],
                "manifestWrittenLast": True,
                "independentReadbackPassed": False,
                "networkOperationCount": 0,
                "sourceExecutionCount": 0,
                "productEndpointAuthenticationEvaluatedByThisReview": False,
                "productEndpointAuthenticationUserInputRequiredForThisReview": (
                    False
                ),
                "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
                "nextAction": (
                    "run_separate_dependency_source_review_wave1_"
                    "independent_readback"
                ),
            },
            "manifest_without_contentBinding",
        )
        self.manifest = manifest
        write_file(
            self.root,
            recorder.REVIEW_MANIFEST_PATH,
            recorder.canonical_json_bytes(manifest),
            mode=0o600,
        )

    def replace_json(
        self,
        relative: str,
        document: dict[str, object],
        scope: str,
        *,
        rebound: bool = True,
    ) -> None:
        value = bound(document, scope) if rebound else document
        write_file(
            self.root,
            relative,
            recorder.canonical_json_bytes(value),
            mode=0o600,
        )

    def close(self) -> None:
        self.temporary.cleanup()


class ReadbackRecorderTests(unittest.TestCase):
    def test_01_three_routes_record_with_distinct_status_and_next_action(
        self,
    ) -> None:
        for route in recorder.ROUTES:
            fixture = SyntheticReviewFixture(route)
            try:
                output = recorder.record_readback(fixture.root)
                self.assertEqual(output["route"], route)
                self.assertEqual(
                    output["status"], recorder.ROUTES[route]["manifestStatus"]
                )
                self.assertEqual(
                    output["nextAction"],
                    recorder.ROUTES[route]["manifestNextAction"],
                )
                self.assertEqual(output["fileWriteCount"], 3)
                self.assertEqual(output["networkOperationCount"], 0)
                receipt = recorder.strict_json(
                    (
                        fixture.root / recorder.READBACK_RECEIPT_PATH
                    ).read_bytes(),
                    "recorded receipt",
                )
                self.assertEqual(
                    receipt["nextAction"],
                    recorder.ROUTES[route]["postReadbackNextAction"],
                )
                self.assertEqual(
                    receipt["recoveryDecisionBinding"]["decisionId"],
                    recorder.RECOVERY_DECISION_ID,
                )
                self.assertEqual(
                    receipt["priorRecoveryDecisionBinding"],
                    fixture.recovery["priorRecoveryDecisionBinding"],
                )
                self.assertEqual(
                    receipt["failedAttemptBindings"],
                    fixture.recovery["failedAttemptBindings"],
                )
                self.assertEqual(
                    receipt["failedAttemptNamespaceContracts"],
                    fixture.recovery["failedAttemptNamespaceContracts"],
                )
                for relative in (
                    recorder.READBACK_CLAIM_PATH,
                    recorder.READBACK_RECEIPT_PATH,
                    recorder.READBACK_MANIFEST_PATH,
                ):
                    info = (fixture.root / relative).stat()
                    self.assertEqual(info.st_mode & 0o777, 0o600)
            finally:
                fixture.close()

    def test_02_new_tuple_route_precedes_external_gap(self) -> None:
        fixture = SyntheticReviewFixture(
            "new_tuple_wave_required", mixed_external=True
        )
        try:
            output = recorder.record_readback(fixture.root)
            self.assertEqual(output["route"], "new_tuple_wave_required")
        finally:
            fixture.close()

    def test_03_second_record_and_partial_namespace_fail_closed(self) -> None:
        fixture = SyntheticReviewFixture()
        try:
            recorder.record_readback(fixture.root)
            before = [
                (fixture.root / path).read_bytes()
                for path in (
                    recorder.READBACK_CLAIM_PATH,
                    recorder.READBACK_RECEIPT_PATH,
                    recorder.READBACK_MANIFEST_PATH,
                )
            ]
            with self.assertRaises(recorder.ReadbackError):
                recorder.record_readback(fixture.root)
            after = [
                (fixture.root / path).read_bytes()
                for path in (
                    recorder.READBACK_CLAIM_PATH,
                    recorder.READBACK_RECEIPT_PATH,
                    recorder.READBACK_MANIFEST_PATH,
                )
            ]
            self.assertEqual(before, after)
            (fixture.root / recorder.READBACK_MANIFEST_PATH).unlink()
            with self.assertRaises(recorder.ReadbackError):
                recorder.preflight_status(fixture.root)
        finally:
            fixture.close()

    def test_04_failure_after_claim_consumes_readback_namespace(self) -> None:
        fixture = SyntheticReviewFixture()
        original = recorder.write_exclusive
        count = 0

        def fail_second(parent, relative: str, payload: bytes):
            nonlocal count
            count += 1
            if count == 2:
                raise recorder.ReadbackError("injected after claim")
            return original(parent, relative, payload)

        try:
            with mock.patch.object(
                recorder, "write_exclusive", side_effect=fail_second
            ):
                with self.assertRaises(recorder.ReadbackError):
                    recorder.record_readback(fixture.root)
            self.assertTrue(
                (fixture.root / recorder.READBACK_CLAIM_PATH).exists()
            )
            self.assertFalse(
                (fixture.root / recorder.READBACK_RECEIPT_PATH).exists()
            )
            with self.assertRaises(recorder.ReadbackError):
                recorder.record_readback(fixture.root)
        finally:
            fixture.close()

    def test_05_each_projection_field_mutation_is_rejected(self) -> None:
        graph = graph_for("new_tuple_wave_required", mixed_external=True)
        mutations = {
            "selectedVersions": {"module": "z.invalid", "version": "v1.0.0"},
            "nodes": {
                "profileId": "z",
                "module": "z.invalid",
                "package": "z.invalid",
            },
            "edges": {
                "profileId": "z",
                "fromPackage": "z",
                "importPath": "z.invalid/pkg",
                "targetModule": None,
                "targetVersion": None,
                "edgeClass": "unmapped_external",
            },
            "moduleNodes": {
                "module": "z.invalid",
                "version": "v1.0.0",
                "isRoot": False,
                "sourceAvailable": False,
                "frontier": True,
                "selectedForModule": True,
            },
            "moduleEdges": {
                "fromModule": "z.invalid",
                "fromVersion": "v1.0.0",
                "requiredModule": "z.invalid/two",
                "requestedVersion": "v1.0.0",
                "selectedVersion": "v1.0.0",
                "targetSourceAvailable": False,
            },
            "exactFrontier": {
                "module": "z.invalid",
                "version": "v1.0.0",
                "selectedByGraphAlgorithm": True,
                "requiresSeparateWaveDecision": True,
                "acquisitionAuthorized": False,
            },
            "unmappedExternalImports": {
                "profileId": "z",
                "fromPackage": "z",
                "importPath": "z.invalid/pkg",
            },
            "unresolvedDeclaredExternalImports": {
                "profileId": "z",
                "fromPackage": "z",
                "importPath": "z.invalid/pkg",
                "targetModule": "z.invalid",
                "targetVersion": "v1.0.0",
            },
        }
        for field, row in mutations.items():
            with self.subTest(field=field):
                modified = copy.deepcopy(graph)
                modified[field].append(row)
                with self.assertRaises(recorder.ReadbackError):
                    recorder.validate_graph(modified)

    def test_06_count_digest_and_reconstruction_mutations_are_rejected(
        self,
    ) -> None:
        graph = graph_for("fixed_point_candidate")
        for mutate in (
            lambda value: value.__setitem__("graphNodeCount", True),
            lambda value: value.__setitem__("graphSha256", "0" * 64),
            lambda value: value["reconstructions"][1].__setitem__(
                "reconstructionSha256", "1" * 64
            ),
            lambda value: value.__setitem__(
                "independentReproductionPassed", False
            ),
            lambda value: value.__setitem__(
                "versionSpecificVertexTraversal", False
            ),
            lambda value: value.__setitem__(
                "algorithm", "go1.24_mvs_version_vertex_profile_union_v2"
            ),
        ):
            modified = copy.deepcopy(graph)
            mutate(modified)
            with self.assertRaises(recorder.ReadbackError):
                recorder.validate_graph(modified)

    def test_07_post_readback_action_is_result_bound(self) -> None:
        fixture = SyntheticReviewFixture("new_tuple_wave_required")
        try:
            modified = copy.deepcopy(fixture.result)
            modified.pop("contentBinding")
            modified["postReadbackNextAction"] = "mutated"
            modified = bound(modified, "result_without_contentBinding")
            raw = recorder.canonical_json_bytes(modified)
            with self.assertRaises(recorder.ReadbackError):
                recorder.validate_result(
                    modified,
                    raw,
                    fixture.permit,
                    fixture.permit["contentBinding"]["sha256"],
                )
        finally:
            fixture.close()

    def test_08_result_and_manifest_raw_binding_drift_is_rejected(self) -> None:
        fixture = SyntheticReviewFixture()
        try:
            result_path = fixture.root / recorder.RESULT_PATH
            result_path.write_bytes(result_path.read_bytes()[:-1] + b" \n")
            with self.assertRaises(recorder.ReadbackError):
                recorder.preflight_status(fixture.root)
        finally:
            fixture.close()
        fixture = SyntheticReviewFixture()
        try:
            manifest = copy.deepcopy(fixture.manifest)
            manifest.pop("contentBinding")
            manifest["graphSha256"] = "0" * 64
            fixture.replace_json(
                recorder.REVIEW_MANIFEST_PATH,
                manifest,
                "manifest_without_contentBinding",
            )
            with self.assertRaises(recorder.ReadbackError):
                recorder.preflight_status(fixture.root)
        finally:
            fixture.close()

    def test_09_tool_drift_and_no_auth_overclaim_are_rejected(self) -> None:
        fixture = SyntheticReviewFixture()
        try:
            tool = fixture.root / recorder.TOOL_PATHS["review_runner"]
            tool.write_bytes(tool.read_bytes() + b"# drift\n")
            with self.assertRaises(recorder.ReadbackError):
                recorder.preflight_status(fixture.root)
        finally:
            fixture.close()
        fixture = SyntheticReviewFixture()
        try:
            result = copy.deepcopy(fixture.result)
            result.pop("contentBinding")
            result["personalProjectBoundary"][
                "externalAuthenticationRequired"
            ] = True
            fixture.replace_json(
                recorder.RESULT_PATH,
                result,
                "result_without_contentBinding",
            )
            with self.assertRaises(recorder.ReadbackError):
                recorder.preflight_status(fixture.root)
        finally:
            fixture.close()

    def test_10_strict_json_rejects_duplicate_float_and_bool_alias(self) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":1.0}\n',
            b'{"a":NaN}\n',
        ):
            with self.assertRaises(recorder.ReadbackError):
                recorder.strict_json(raw, "synthetic")
        graph = graph_for("fixed_point_candidate")
        graph["graphNodeCount"] = True
        with self.assertRaises(recorder.ReadbackError):
            recorder.validate_graph(graph)

    def test_11_symlink_hardlink_mode_and_final_name_replacement_rejected(
        self,
    ) -> None:
        fixture = SyntheticReviewFixture()
        try:
            result = fixture.root / recorder.RESULT_PATH
            original = result.read_bytes()
            result.unlink()
            result.symlink_to(fixture.root / recorder.REVIEW_CLAIM_PATH)
            with self.assertRaises((recorder.ReadbackError, OSError)):
                recorder.preflight_status(fixture.root)
            result.unlink()
            write_file(
                fixture.root,
                recorder.RESULT_PATH,
                original,
                mode=0o600,
            )
            sibling = result.with_name("hardlink-source.json")
            sibling.write_bytes(original)
            sibling.chmod(0o600)
            result.unlink()
            os.link(sibling, result)
            with self.assertRaises(recorder.ReadbackError):
                recorder.preflight_status(fixture.root)
        finally:
            fixture.close()
        fixture = SyntheticReviewFixture()
        try:
            result = fixture.root / recorder.RESULT_PATH
            result.chmod(0o644)
            with self.assertRaises(recorder.ReadbackError):
                recorder.preflight_status(fixture.root)
        finally:
            fixture.close()
        fixture = SyntheticReviewFixture()
        try:
            with recorder.ReviewInputs(fixture.root) as state:
                result = fixture.root / recorder.RESULT_PATH
                replacement = result.with_name(".replacement-result")
                replacement.write_bytes(result.read_bytes())
                replacement.chmod(0o600)
                os.replace(replacement, result)
                with self.assertRaises(recorder.ReadbackError):
                    state.final_barrier()
        finally:
            fixture.close()

    def test_12_casefold_output_collision_is_rejected(self) -> None:
        fixture = SyntheticReviewFixture()
        try:
            original = os.listdir

            def collision(path: int | str):
                values = original(path)
                if isinstance(path, int) and recorder.READBACK_CLAIM_PATH.rsplit(
                    "/", 1
                )[-1] not in values:
                    return values + [
                        recorder.READBACK_CLAIM_PATH.rsplit("/", 1)[-1].upper()
                    ]
                return values

            with mock.patch.object(recorder.os, "listdir", side_effect=collision):
                with self.assertRaises(recorder.ReadbackError):
                    recorder.preflight_status(fixture.root)
        finally:
            fixture.close()

    def test_13_recovery_history_and_v1_v2_absence_are_fail_closed(
        self,
    ) -> None:
        for relative in (
            recorder.V1_RECOVERY_DECISION_PATH,
            recorder.RECOVERY_DECISION_PATH,
            recorder.V1_PERMIT_PATH,
            recorder.V1_REVIEW_CLAIM_PATH,
            recorder.V1_FAILURE_PATH,
            recorder.V2_PERMIT_PATH,
            recorder.V2_REVIEW_CLAIM_PATH,
            recorder.V2_FAILURE_PATH,
        ):
            fixture = SyntheticReviewFixture()
            try:
                path = fixture.root / relative
                path.write_bytes(path.read_bytes()[:-1] + b" \n")
                with self.assertRaises(recorder.ReadbackError):
                    recorder.preflight_status(fixture.root)
            finally:
                fixture.close()
        for relative in (
            *recorder.expected_v1_absent_paths(),
            *recorder.expected_v2_absent_paths(),
        ):
            fixture = SyntheticReviewFixture()
            try:
                write_file(fixture.root, relative, b"historical backfill\n")
                with self.assertRaises(recorder.ReadbackError):
                    recorder.preflight_status(fixture.root)
            finally:
                fixture.close()

    def test_14_v1_v2_failures_are_history_but_v3_failure_blocks(
        self,
    ) -> None:
        fixture = SyntheticReviewFixture()
        try:
            self.assertTrue(
                (fixture.root / recorder.V1_FAILURE_PATH).is_file()
            )
            self.assertTrue(
                (fixture.root / recorder.V2_FAILURE_PATH).is_file()
            )
            historical_v2_failure = recorder.strict_json(
                (fixture.root / recorder.V2_FAILURE_PATH).read_bytes(),
                "historical v2 failure",
            )
            self.assertEqual(
                historical_v2_failure["failureCode"],
                "E_ARCHIVE_STRUCTURE",
            )
            self.assertEqual(historical_v2_failure["phase"], "archive")
            self.assertEqual(
                historical_v2_failure["failedTupleId"],
                "wave1-010-ec8b158caf64",
            )
            self.assertIsNone(historical_v2_failure["failedTupleOrder"])
            self.assertIsNone(historical_v2_failure["failedResourceKind"])
            self.assertTrue(
                recorder.preflight_status(fixture.root)["validationPassed"]
            )
            write_file(
                fixture.root,
                recorder.FAILURE_PATH,
                b"current v3 failure\n",
                mode=0o600,
            )
            with self.assertRaises(recorder.ReadbackError):
                recorder.preflight_status(fixture.root)
        finally:
            fixture.close()

    def test_15_held_publication_parent_rejects_ancestor_aba_without_write(
        self,
    ) -> None:
        fixture = SyntheticReviewFixture()
        root_fd = os.open(
            fixture.root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        parent_relative = recorder.READBACK_RECEIPT_PATH.rsplit("/", 1)[0]
        held = recorder.HeldDirectory(root_fd, parent_relative)
        try:
            ancestor = fixture.root / "docs" / "security-hardening"
            moved = fixture.root / "docs" / ".security-hardening-held"
            os.rename(ancestor, moved)
            replacement_parent = fixture.root / parent_relative
            replacement_parent.mkdir(parents=True)
            replacement_target = (
                fixture.root / recorder.READBACK_RECEIPT_PATH
            )
            with self.assertRaises((recorder.ReadbackError, OSError)):
                recorder.write_exclusive(
                    held,
                    recorder.READBACK_RECEIPT_PATH,
                    b"{}\n",
                )
            self.assertFalse(replacement_target.exists())
            self.assertNotIn(
                recorder.READBACK_RECEIPT_PATH.rsplit("/", 1)[-1],
                os.listdir(held.fd),
            )
        finally:
            held.close()
            os.close(root_fd)
            fixture.close()

    def test_16_directory_identity_ignores_sibling_link_count_churn(
        self,
    ) -> None:
        fixture = SyntheticReviewFixture()
        root_fd = os.open(
            fixture.root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        parent_relative = recorder.READBACK_RECEIPT_PATH.rsplit("/", 1)[0]
        held = recorder.HeldDirectory(root_fd, parent_relative)
        try:
            before = os.fstat(held.fd)
            (fixture.root / parent_relative / ".synthetic-sibling").mkdir()
            after = os.fstat(held.fd)
            self.assertEqual(
                recorder.directory_identity(before),
                recorder.directory_identity(after),
            )
            self.assertEqual(len(recorder.directory_identity(after)), 5)
            held.final_barrier()
        finally:
            held.close()
            os.close(root_fd)
            fixture.close()

    def test_17_final_parent_barrier_closes_post_file_barrier_aba_window(
        self,
    ) -> None:
        fixture = SyntheticReviewFixture()
        original = recorder.PublishedFile.barrier
        barrier_count = 0
        ancestor = fixture.root / "docs" / "security-hardening"
        moved = fixture.root / "docs" / ".security-hardening-post-barrier"

        def replace_after_last_file_barrier(published) -> None:
            nonlocal barrier_count
            original(published)
            barrier_count += 1
            if barrier_count == 3:
                os.rename(ancestor, moved)
                ancestor.mkdir()
                ancestor.chmod(0o755)

        try:
            with mock.patch.object(
                recorder.PublishedFile,
                "barrier",
                new=replace_after_last_file_barrier,
            ):
                with self.assertRaises((recorder.ReadbackError, OSError)):
                    recorder.record_readback(fixture.root)
            self.assertEqual(barrier_count, 3)
            self.assertFalse(
                (fixture.root / recorder.READBACK_RECEIPT_PATH).exists()
            )
            self.assertFalse(
                (fixture.root / recorder.READBACK_MANIFEST_PATH).exists()
            )
        finally:
            fixture.close()

    def test_18_static_surface_has_no_archive_network_or_execution_api(
        self,
    ) -> None:
        source = RECORDER_PATH.read_text()
        tree = ast.parse(source)
        imported = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            imported.isdisjoint(
                {
                    "zipfile",
                    "tarfile",
                    "socket",
                    "subprocess",
                    "urllib",
                    "http",
                    "ssl",
                    "requests",
                    "aiohttp",
                    "importlib",
                    "runpy",
                }
            )
        )
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(
            called.isdisjoint({"exec", "eval", "compile", "__import__"})
        )
        self.assertNotIn("zipfile", source)
        write_node = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "write_exclusive"
        )
        self.assertEqual(write_node.args.args[0].arg, "parent")
        write_source = ast.get_source_segment(source, write_node)
        self.assertIsNotNone(write_source)
        self.assertIn("dir_fd=parent.fd", write_source)
        self.assertNotIn("root_fd", write_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
