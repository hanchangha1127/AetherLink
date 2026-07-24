#!/usr/bin/env python3
"""Synthetic mutation tests for the independent wave-one v3 readback."""

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

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
import zipfile


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / "check_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
)
SPEC = importlib.util.spec_from_file_location("wave1_success_v3_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def bind(document: dict, scope: str) -> dict:
    result = dict(document)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": scope,
        "sha256": CHECKER.sha256_bytes(CHECKER.canonical_json_bytes(document)),
    }
    return result


def make_zip(
    module: str,
    version: str,
    external_mod: bytes,
    *,
    include_mod: bool,
    embedded_mod: bytes | None = None,
) -> bytes:
    output = io.BytesIO()
    prefix = f"{module}@{version}/"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        source_info = zipfile.ZipInfo(prefix + "source.go")
        source_info.create_system = 3
        source_info.external_attr = (stat.S_IFREG | 0o600) << 16
        source_info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(source_info, b"package fixture\n")
        if include_mod:
            mod_info = zipfile.ZipInfo(prefix + "go.mod")
            mod_info.create_system = 3
            mod_info.external_attr = (stat.S_IFREG | 0o600) << 16
            mod_info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(
                mod_info, external_mod if embedded_mod is None else embedded_mod
            )
    return output.getvalue()


class SyntheticSuccess:
    def __init__(
        self,
        root: Path,
        *,
        embedded_mismatch_order: int | None = None,
    ) -> None:
        self.root = root
        self.tuples: list[dict] = []
        self.rows: list[dict] = []
        self.resources: dict[str, bytes] = {}
        self.embedded_mismatch_order = embedded_mismatch_order
        self._build()

    def path(self, relative: str) -> Path:
        return self.root / relative

    def write_bytes(self, relative: str, payload: bytes, mode: int = 0o644) -> None:
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        path.chmod(mode)

    def write_json(self, relative: str, value: object, mode: int = 0o644) -> bytes:
        raw = CHECKER.canonical_json_bytes(value)
        self.write_bytes(relative, raw, mode)
        return raw

    def read_json(self, relative: str) -> dict:
        return json.loads(self.path(relative).read_text(encoding="utf-8"))

    def replace_json(
        self,
        relative: str,
        mutate,
        *,
        rebind_scope: str | None = None,
    ) -> None:
        value = self.read_json(relative)
        mutate(value)
        if rebind_scope is not None:
            value.pop("contentBinding", None)
            value = bind(value, rebind_scope)
        mode = stat.S_IMODE(self.path(relative).stat().st_mode)
        self.write_json(relative, value, mode)

    def _build(self) -> None:
        final = self.path(CHECKER.FINAL_DIRECTORY_PATH)
        final.mkdir(parents=True, exist_ok=True)
        final.chmod(0o700)
        staging_parent = self.path(CHECKER.STAGING_PARENT_PATH)
        staging_parent.chmod(0o700)

        aggregate_zip = 0
        aggregate_mod = 0
        aggregate_entries = 0
        aggregate_uncompressed = 0
        for order in range(1, 20):
            if order == 11:
                module = "github.com/davecgh/go-spew"
                version = "v1.1.1"
            else:
                module = f"example.com/dependency/mod{order}"
                version = f"v1.0.{order}"
            tuple_sha = hashlib.sha256(
                f"{module}@{version}".encode("utf-8")
            ).hexdigest()
            tuple_id = f"wave1-{order:03d}-{tuple_sha[:12]}"
            zip_url = f"https://proxy.golang.org/{module}/@v/{version}.zip"
            mod_url = zip_url[:-4] + ".mod"
            mod_payload = f"module {module}\n".encode("utf-8")
            include_mod = order != 11
            mismatch = self.embedded_mismatch_order == order
            zip_payload = make_zip(
                module,
                version,
                mod_payload,
                include_mod=include_mod or mismatch,
                embedded_mod=(
                    f"module example.com/wrong{order}\n".encode("utf-8")
                    if mismatch
                    else None
                ),
            )
            inspected = CHECKER.inspect_zip(zip_payload, module, version)
            zip_name = f"{order:03d}-{tuple_sha[:20]}.zip"
            mod_name = f"{order:03d}-{tuple_sha[:20]}.mod"
            self.resources[zip_name] = zip_payload
            self.resources[mod_name] = mod_payload
            self.write_bytes(
                f"{CHECKER.FINAL_DIRECTORY_PATH}/{zip_name}",
                zip_payload,
                0o600,
            )
            self.write_bytes(
                f"{CHECKER.FINAL_DIRECTORY_PATH}/{mod_name}",
                mod_payload,
                0o600,
            )
            module_h1 = inspected["moduleZipH1"]
            mod_h1 = CHECKER.single_go_mod_h1(mod_payload)
            item = {
                "order": order,
                "tupleId": tuple_id,
                "tupleSha256": tuple_sha,
                "module": module,
                "version": version,
                "url": zip_url,
                "scheme": "https",
                "host": "proxy.golang.org",
                "moduleZipH1": module_h1,
                "goModH1": mod_h1,
            }
            self.tuples.append(item)
            embedded = inspected["embeddedGoMod"]
            row = {
                "order": order,
                "tupleId": tuple_id,
                "module": module,
                "version": version,
                "zipUrl": zip_url,
                "modUrl": mod_url,
                "zipOutputFileName": zip_name,
                "modOutputFileName": mod_name,
                "zipRawByteSize": len(zip_payload),
                "zipRawSha256": CHECKER.sha256_bytes(zip_payload),
                "modRawByteSize": len(mod_payload),
                "modRawSha256": CHECKER.sha256_bytes(mod_payload),
                "moduleZipH1": module_h1,
                "goModH1": mod_h1,
                "entryCount": inspected["entryCount"],
                "uncompressedByteCount": inspected["uncompressedByteCount"],
                "modulePrefix": inspected["modulePrefix"],
                "embeddedGoModPresent": embedded is not None,
                "embeddedGoModByteParity": embedded is None or embedded == mod_payload,
                "zipMode": "0600",
                "zipLinkCount": 1,
                "modMode": "0600",
                "modLinkCount": 1,
            }
            if mismatch:
                row["embeddedGoModByteParity"] = True
            self.rows.append(row)
            aggregate_zip += len(zip_payload)
            aggregate_mod += len(mod_payload)
            aggregate_entries += inspected["entryCount"]
            aggregate_uncompressed += inspected["uncompressedByteCount"]

        source = bind(
            {
                "documentType": (
                    "aetherlink.g2-pion-rung3-bounded-dependency-source-"
                    "identity-and-acquisition-decision"
                ),
                "schemaVersion": "1.0",
                "decisionId": CHECKER.EXPECTED_SOURCE_DECISION_ID,
                "wave": {
                    "selectedTupleCount": 19,
                    "expectedSuccessRequestCount": 19,
                    "tuples": self.tuples,
                },
            },
            "decision_without_contentBinding",
        )
        source_raw = self.write_json(CHECKER.SOURCE_DECISION_PATH, source)
        source_content = source["contentBinding"]["sha256"]

        recovery = bind(
            {
                "documentType": "aetherlink.g2-pion-dependency-wave1-recovery-decision",
                "schemaVersion": "2.0",
                "decisionId": CHECKER.EXPECTED_RECOVERY_DECISION_ID,
                "status": (
                    "wave1_v2_failure_read_back_recovery_v3_design_selected_"
                    "execution_not_authorized"
                ),
                "predecessorBindings": {
                    "sourceIdentityDecision": {
                        "path": CHECKER.SOURCE_DECISION_PATH,
                        "rawSha256": CHECKER.sha256_bytes(source_raw),
                        "contentSha256": source_content,
                    }
                },
                "selectedV3Policy": {
                    "expectedSuccessRequestCount": 38,
                    "maximumRequestCount": 38,
                    "resourceCountPerTuple": 2,
                    "resourceModel": "fresh_exact_mod_then_zip_pair_for_each_tuple",
                    "requiredCounterSchema": {
                        "successValues": dict(CHECKER.SUCCESS_COUNTERS)
                        | {"acceptedArtifactCount": 38}
                    },
                },
                "v3NamespaceContract": {
                    "claimPath": CHECKER.CLAIM_PATH,
                    "failureReceiptPath": CHECKER.FAILURE_PATH,
                    "finalDirectoryPath": CHECKER.FINAL_DIRECTORY_PATH,
                    "manifestPath": CHECKER.ACQUISITION_MANIFEST_PATH,
                    "successReceiptPath": CHECKER.SUCCESS_RECEIPT_PATH,
                    "stagingParentPath": CHECKER.STAGING_PARENT_PATH,
                    "stagingNamePrefix": CHECKER.STAGING_PREFIX,
                    "fullFreshTupleCountRequired": 19,
                },
                "independentReadbackContract": {
                    "checkerPath": (
                        "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
                    ),
                    "checkerTestsPath": (
                        "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
                    ),
                    "exactRetainedResourceCount": 38,
                    "acquisitionSuccessRegularFileCount": 41,
                    "postReadbackRegularFileCount": 43,
                    "receiptPath": CHECKER.READBACK_RECEIPT_PATH,
                    "manifestPath": CHECKER.READBACK_MANIFEST_PATH,
                    "manifestWrittenLast": True,
                    "networkAllowed": False,
                    "sourceExtractionAllowed": False,
                    "sourceLoadOrExecutionAllowed": False,
                },
            },
            "decision_without_contentBinding",
        )
        recovery_raw = self.write_json(CHECKER.RECOVERY_DECISION_PATH, recovery)
        recovery_content = recovery["contentBinding"]["sha256"]

        permit = bind(
            {
                "documentType": (
                    "aetherlink.g2-pion-rung3-dependency-wave1-execution-permit"
                ),
                "schemaVersion": "3.0",
                "permitId": CHECKER.EXPECTED_PERMIT_ID,
                "status": (
                    "wave1_v3_dependency_source_acquisition_authorized_not_consumed"
                ),
                "sourceDecisionBinding": {
                    "path": CHECKER.SOURCE_DECISION_PATH,
                    "rawSha256": CHECKER.sha256_bytes(source_raw),
                    "contentSha256": source_content,
                },
                "recoveryBinding": {
                    "path": CHECKER.RECOVERY_DECISION_PATH,
                    "rawSha256": CHECKER.sha256_bytes(recovery_raw),
                    "contentSha256": recovery_content,
                },
            },
            "permit_without_contentBinding",
        )
        permit_raw = self.write_json(CHECKER.PERMIT_PATH, permit)
        permit_content = permit["contentBinding"]["sha256"]

        claim = {
            "claimType": "aetherlink.g2-pion-dependency-wave1-v3-one-use-claim",
            "schemaVersion": "3.0",
            "createdAt": "2026-07-24T00:00:00Z",
            "permitId": CHECKER.EXPECTED_PERMIT_ID,
            "permitContentSha256": permit_content,
            "recoveryDecisionId": CHECKER.EXPECTED_RECOVERY_DECISION_ID,
            "recoveryContentSha256": recovery_content,
            "rule": "v3_claim_persists_after_any_network_attempt_and_blocks_retry",
            "v1OrV2ArtifactReuseAllowed": False,
        }
        claim_raw = self.write_json(CHECKER.CLAIM_PATH, claim, 0o600)

        receipt = {
            "documentType": "aetherlink.g2-pion-dependency-wave1-v3-acquisition-receipt",
            "schemaVersion": "3.0",
            "status": "acquired_pending_independent_readback",
            "result": "fresh_exact_19_dependency_zip_mod_pairs_acquired_and_hash_verified",
            "permitId": CHECKER.EXPECTED_PERMIT_ID,
            "permitRawSha256": CHECKER.sha256_bytes(permit_raw),
            "permitContentSha256": permit_content,
            "recoveryDecisionId": CHECKER.EXPECTED_RECOVERY_DECISION_ID,
            "recoveryRawSha256": CHECKER.sha256_bytes(recovery_raw),
            "recoveryContentSha256": recovery_content,
            "decisionId": CHECKER.EXPECTED_SOURCE_DECISION_ID,
            "decisionRawSha256": CHECKER.sha256_bytes(source_raw),
            "decisionContentSha256": source_content,
            "claimRawSha256": CHECKER.sha256_bytes(claim_raw),
            **CHECKER.SUCCESS_COUNTERS,
            "acceptedArtifactCount": 38,
            "acceptedTupleCount": 19,
            "aggregateZipRawByteSize": aggregate_zip,
            "aggregateModRawByteSize": aggregate_mod,
            "aggregateRawByteSize": aggregate_zip + aggregate_mod,
            "aggregateEntryCount": aggregate_entries,
            "aggregateUncompressedByteCount": aggregate_uncompressed,
            "orderedSourceSetSha256": CHECKER.ordered_source_set_sha256(self.rows),
            "sources": self.rows,
            "legacyCompletedRequestCountForbidden": True,
            "independentReadbackPassed": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v3_independent_readback",
        }
        receipt_raw = self.write_json(CHECKER.SUCCESS_RECEIPT_PATH, receipt, 0o600)
        manifest = {
            "documentType": "aetherlink.g2-pion-dependency-wave1-v3-acquisition-manifest",
            "schemaVersion": "3.0",
            "status": (
                "wave1_v3_acquisition_publication_complete_pending_"
                "independent_readback"
            ),
            "result": (
                "receipt_and_fresh_exact_19_zip_mod_pairs_published_"
                "manifest_written_last"
            ),
            "permitId": CHECKER.EXPECTED_PERMIT_ID,
            "permitRawSha256": CHECKER.sha256_bytes(permit_raw),
            "permitContentSha256": permit_content,
            "recoveryRawSha256": CHECKER.sha256_bytes(recovery_raw),
            "recoveryContentSha256": recovery_content,
            "successReceiptPath": CHECKER.SUCCESS_RECEIPT_PATH,
            "successReceiptRawSha256": CHECKER.sha256_bytes(receipt_raw),
            "finalDirectoryPath": CHECKER.FINAL_DIRECTORY_PATH,
            **CHECKER.SUCCESS_COUNTERS,
            "acceptedArtifactCount": 38,
            "acceptedTupleCount": 19,
            "orderedSourceSetSha256": receipt["orderedSourceSetSha256"],
            "manifestWrittenLast": True,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v3_independent_readback",
        }
        self.write_json(CHECKER.ACQUISITION_MANIFEST_PATH, manifest, 0o600)


class DependencyWaveOneV3ReadbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def success(self, **kwargs) -> SyntheticSuccess:
        return SyntheticSuccess(self.root, **kwargs)

    def assert_rejected(self) -> None:
        with self.assertRaises((CHECKER.CheckError, OSError)):
            CHECKER.validate_state(self.root)

    def test_01_absent_preflight_is_read_only_and_passes(self) -> None:
        state = CHECKER.validate_state(self.root)
        self.assertEqual(state["status"], "absent_not_acquired")
        self.assertEqual(state["fileWriteCount"], 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_02_exact_38_resource_success_passes(self) -> None:
        self.success()
        state = CHECKER.validate_state(self.root)
        self.assertEqual(state["status"], "acquired_pending_independent_readback")
        self.assertEqual(state["retainedResourceCount"], 38)
        self.assertEqual(state["observedRegularFileCount"], 41)

    def test_03_go_spew_without_embedded_go_mod_passes(self) -> None:
        fixture = self.success()
        state = CHECKER.validate_state(self.root)
        candidate = state["readbackReceiptCandidate"]
        observation = candidate["tupleObservations"][fixture.tuples[10]["tupleId"]]
        self.assertFalse(observation["embeddedGoModPresent"])
        self.assertTrue(observation["embeddedGoModByteParity"])

    def test_04_record_writes_receipt_then_manifest_only(self) -> None:
        self.success()
        before = {
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        result = CHECKER.record_readback(self.root)
        after = {
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(
            after - before,
            {CHECKER.READBACK_RECEIPT_PATH, CHECKER.READBACK_MANIFEST_PATH},
        )
        self.assertEqual(result["fileWriteCount"], 2)
        self.assertEqual(
            CHECKER.validate_state(self.root)["status"],
            "independent_readback_complete",
        )
        receipt_time = self.root.joinpath(CHECKER.READBACK_RECEIPT_PATH).stat().st_mtime_ns
        manifest_time = self.root.joinpath(CHECKER.READBACK_MANIFEST_PATH).stat().st_mtime_ns
        self.assertLessEqual(receipt_time, manifest_time)

    def test_05_missing_resource_is_rejected(self) -> None:
        fixture = self.success()
        self.root.joinpath(
            CHECKER.FINAL_DIRECTORY_PATH, fixture.rows[0]["zipOutputFileName"]
        ).unlink()
        self.assert_rejected()

    def test_06_extra_resource_is_rejected(self) -> None:
        self.success()
        path = self.root / CHECKER.FINAL_DIRECTORY_PATH / "extra.mod"
        path.write_bytes(b"module example.com/extra\n")
        path.chmod(0o600)
        self.assert_rejected()

    def test_07_resource_mode_drift_is_rejected(self) -> None:
        fixture = self.success()
        path = self.root / CHECKER.FINAL_DIRECTORY_PATH / fixture.rows[0]["modOutputFileName"]
        path.chmod(0o644)
        self.assert_rejected()

    def test_08_resource_hardlink_is_rejected(self) -> None:
        fixture = self.success()
        source = self.root / CHECKER.FINAL_DIRECTORY_PATH / fixture.rows[0]["modOutputFileName"]
        os.link(source, self.root / "second-link")
        self.assert_rejected()

    def test_09_resource_symlink_is_rejected(self) -> None:
        fixture = self.success()
        path = self.root / CHECKER.FINAL_DIRECTORY_PATH / fixture.rows[0]["modOutputFileName"]
        target = self.root / "target"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
        self.assert_rejected()

    def test_10_zip_raw_byte_mutation_is_rejected(self) -> None:
        fixture = self.success()
        path = self.root / CHECKER.FINAL_DIRECTORY_PATH / fixture.rows[0]["zipOutputFileName"]
        path.write_bytes(path.read_bytes() + b"x")
        path.chmod(0o600)
        self.assert_rejected()

    def test_11_mod_raw_byte_mutation_is_rejected(self) -> None:
        fixture = self.success()
        path = self.root / CHECKER.FINAL_DIRECTORY_PATH / fixture.rows[0]["modOutputFileName"]
        path.write_bytes(path.read_bytes() + b"// drift\n")
        path.chmod(0o600)
        self.assert_rejected()

    def test_12_embedded_external_mod_mismatch_is_rejected(self) -> None:
        self.success(embedded_mismatch_order=2)
        self.assert_rejected()

    def test_13_partial_claim_only_state_is_rejected(self) -> None:
        fixture = self.success()
        shutil.rmtree(self.root / CHECKER.FINAL_DIRECTORY_PATH)
        self.root.joinpath(CHECKER.SUCCESS_RECEIPT_PATH).unlink()
        self.root.joinpath(CHECKER.ACQUISITION_MANIFEST_PATH).unlink()
        self.assertTrue(self.root.joinpath(CHECKER.CLAIM_PATH).exists())
        self.assert_rejected()

    def test_14_failure_and_success_coexistence_is_rejected(self) -> None:
        fixture = self.success()
        fixture.write_json(CHECKER.FAILURE_PATH, {"failure": True}, 0o600)
        self.assert_rejected()

    def test_15_staging_residue_is_rejected(self) -> None:
        self.success()
        staging = self.root / CHECKER.STAGING_PARENT_PATH / (
            CHECKER.STAGING_PREFIX + "leftover"
        )
        staging.mkdir()
        self.assert_rejected()

    def test_16_claim_permit_binding_drift_is_rejected(self) -> None:
        fixture = self.success()
        fixture.replace_json(
            CHECKER.CLAIM_PATH,
            lambda value: value.update({"permitContentSha256": "0" * 64}),
        )
        self.assert_rejected()

    def test_17_receipt_claim_binding_drift_is_rejected(self) -> None:
        fixture = self.success()
        fixture.replace_json(
            CHECKER.SUCCESS_RECEIPT_PATH,
            lambda value: value.update({"claimRawSha256": "0" * 64}),
        )
        self.assert_rejected()

    def test_18_manifest_receipt_binding_drift_is_rejected(self) -> None:
        fixture = self.success()
        fixture.replace_json(
            CHECKER.ACQUISITION_MANIFEST_PATH,
            lambda value: value.update({"successReceiptRawSha256": "0" * 64}),
        )
        self.assert_rejected()

    def test_19_source_content_binding_drift_is_rejected(self) -> None:
        fixture = self.success()
        fixture.replace_json(
            CHECKER.SOURCE_DECISION_PATH,
            lambda value: value.update({"schemaVersion": "drift"}),
        )
        self.assert_rejected()

    def test_20_recovery_source_binding_drift_is_rejected(self) -> None:
        fixture = self.success()

        def mutate(value: dict) -> None:
            value["predecessorBindings"]["sourceIdentityDecision"]["rawSha256"] = "0" * 64

        fixture.replace_json(
            CHECKER.RECOVERY_DECISION_PATH,
            mutate,
            rebind_scope="decision_without_contentBinding",
        )
        self.assert_rejected()

    def test_21_permit_recovery_binding_drift_is_rejected(self) -> None:
        fixture = self.success()

        def mutate(value: dict) -> None:
            value["recoveryBinding"]["contentSha256"] = "0" * 64

        fixture.replace_json(
            CHECKER.PERMIT_PATH,
            mutate,
            rebind_scope="permit_without_contentBinding",
        )
        self.assert_rejected()

    def test_22_noncanonical_claim_json_is_rejected(self) -> None:
        fixture = self.success()
        claim = fixture.read_json(CHECKER.CLAIM_PATH)
        path = self.root / CHECKER.CLAIM_PATH
        path.write_text(json.dumps(claim, indent=2) + "\n", encoding="utf-8")
        path.chmod(0o600)
        self.assert_rejected()

    def test_23_boolean_counter_is_rejected(self) -> None:
        fixture = self.success()
        fixture.replace_json(
            CHECKER.SUCCESS_RECEIPT_PATH,
            lambda value: value.update({"networkRequestAttemptCount": True}),
        )
        self.assert_rejected()

    def test_24_ordered_source_digest_drift_is_rejected(self) -> None:
        fixture = self.success()
        fixture.replace_json(
            CHECKER.SUCCESS_RECEIPT_PATH,
            lambda value: value.update({"orderedSourceSetSha256": "0" * 64}),
        )
        self.assert_rejected()

    def test_25_module_zip_h1_drift_is_rejected(self) -> None:
        fixture = self.success()
        fixture.replace_json(
            CHECKER.SUCCESS_RECEIPT_PATH,
            lambda value: value["sources"][0].update({"moduleZipH1": "h1:" + "A" * 43 + "="}),
        )
        self.assert_rejected()

    def test_26_external_mod_h1_drift_is_rejected(self) -> None:
        fixture = self.success()
        fixture.replace_json(
            CHECKER.SUCCESS_RECEIPT_PATH,
            lambda value: value["sources"][0].update({"goModH1": "h1:" + "A" * 43 + "="}),
        )
        self.assert_rejected()

    def test_27_claim_owner_only_mode_is_required(self) -> None:
        self.success()
        self.root.joinpath(CHECKER.CLAIM_PATH).chmod(0o644)
        self.assert_rejected()

    def test_28_success_receipt_single_link_is_required(self) -> None:
        self.success()
        os.link(
            self.root / CHECKER.SUCCESS_RECEIPT_PATH,
            self.root / "receipt-second-link",
        )
        self.assert_rejected()

    def test_29_partial_readback_publication_is_rejected(self) -> None:
        state_fixture = self.success()
        state = CHECKER.validate_state(self.root)
        state_fixture.write_json(
            CHECKER.READBACK_RECEIPT_PATH,
            state["readbackReceiptCandidate"],
            0o600,
        )
        self.assert_rejected()

    def test_30_readback_receipt_mutation_is_rejected(self) -> None:
        fixture = self.success()
        CHECKER.record_readback(self.root)
        fixture.replace_json(
            CHECKER.READBACK_RECEIPT_PATH,
            lambda value: value.update({"networkUsed": True}),
            rebind_scope="readback_receipt_without_contentBinding",
        )
        self.assert_rejected()

    def test_31_readback_manifest_mutation_is_rejected(self) -> None:
        fixture = self.success()
        CHECKER.record_readback(self.root)
        fixture.replace_json(
            CHECKER.READBACK_MANIFEST_PATH,
            lambda value: value.update({"manifestWrittenLast": False}),
            rebind_scope="readback_manifest_without_contentBinding",
        )
        self.assert_rejected()

    def test_32_record_refuses_existing_readback(self) -> None:
        self.success()
        CHECKER.record_readback(self.root)
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.record_readback(self.root)

    def test_33_held_file_detects_between_pass_mutation(self) -> None:
        fixture = self.success()
        root_fd = CHECKER.open_root(self.root)
        held = None
        try:
            held = CHECKER.HeldFile(
                root_fd,
                CHECKER.CLAIM_PATH,
                maximum_bytes=CHECKER.MAXIMUM_JSON_BYTES,
                owner_only=True,
            )
            held.read_pass()
            path = self.root / CHECKER.CLAIM_PATH
            payload = path.read_bytes()
            path.write_bytes(payload + b" ")
            path.chmod(0o600)
            with self.assertRaises(CHECKER.CheckError):
                held.read_pass()
        finally:
            if held is not None:
                held.close()
            os.close(root_fd)

    def test_34_preflight_never_requires_authentication(self) -> None:
        self.success()
        state = CHECKER.validate_state(self.root)
        self.assertFalse(state["authenticationRequired"])
        self.assertEqual(state["networkOperationCount"], 0)
        self.assertEqual(state["fileWriteCount"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
